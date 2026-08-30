import os
import sys
import pandas as pd
import numpy as np
from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime

# Local imports
from data.generator import generate_dataset
from backend.detector import detect, DetectionConfig, DetectionResult
from backend.cost_model import find_optimal_threshold, bootstrap_cost_estimate

app = FastAPI(title="PulseGuard Risk Console API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AppState:
    df: pd.DataFrame = None
    merchant_results: Dict[str, DetectionResult] = {}
    cost_data: Dict[str, Any] = {}
    last_updated: datetime = None
    is_refreshing: bool = False

state = AppState()

def run_pipeline():
    state.is_refreshing = True
    try:
        # 1. Generate Data
        df = generate_dataset(num_merchants=5, days=15) # Smaller dataset for faster refresh during pitch
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # --- Tier Assignment & Priors ---
        merchant_vols = df.groupby('merchant_id').size()
        q33, q67 = merchant_vols.quantile([0.33, 0.67])
        def get_tier(vol):
            if vol <= q33: return "Low Volume"
            if vol <= q67: return "Medium Volume"
            return "High Volume"
            
        df['merchant_tier'] = df['merchant_id'].map(merchant_vols.apply(get_tier))
        
        # Calculate priors for each tier
        tier_priors_map = {}
        agg_cols = ['volume', 'ticket_size', 'velocity']
        
        for tier in ["Low Volume", "Medium Volume", "High Volume"]:
            tier_df = df[df['merchant_tier'] == tier].copy()
            if tier_df.empty:
                continue
                
            tier_df['time_diff'] = tier_df.groupby('merchant_id')['timestamp'].diff().dt.total_seconds().fillna(0)
            
            # Aggregate by hour across all merchants in tier
            t_agg = tier_df.set_index('timestamp').resample('1h').agg(
                volume=('transaction_id', 'count'),
                ticket_size=('amount', 'mean'),
                velocity=('time_diff', 'mean')
            ).fillna(0)
            
            # Normalize volume per merchant
            num_merch_in_tier = tier_df['merchant_id'].nunique()
            t_agg['volume'] = t_agg['volume'] / num_merch_in_tier
            
            tier_priors_map[tier] = {
                'volume': {'mean': t_agg['volume'].mean(), 'std': t_agg['volume'].std()},
                'ticket_size': {'mean': t_agg['ticket_size'].mean(), 'std': t_agg['ticket_size'].std()},
                'velocity': {'mean': t_agg['velocity'].mean(), 'std': t_agg['velocity'].std()}
            }
            
        # 2. Detect
        merchant_results = {}
        df['model_score'] = -10.0
        
        for merchant_id, m_df in df.groupby('merchant_id'):
            tier = m_df['merchant_tier'].iloc[0]
            config = DetectionConfig()
            config.tier_priors = tier_priors_map.get(tier, {})
            
            res = detect(m_df, config)
            merchant_results[merchant_id] = res
            
            score_dict = {ft['transaction_id']: ft['score'] for ft in res.flagged_transactions}
            if score_dict:
                mask = df['merchant_id'] == merchant_id
                df.loc[mask, 'model_score'] = df.loc[mask, 'transaction_id'].map(score_dict).fillna(-10.0)
                
        # 3. Cost Model
        y_true = df['is_anomaly'].astype(int).tolist()
        y_scores = df['model_score'].tolist()
        amounts = df['amount'].tolist()
        
        if_scores = df[df['model_score'] > -10.0]['model_score']
        if not if_scores.empty:
            min_score, max_score = float(if_scores.min()), float(if_scores.max())
            thresholds = np.linspace(min_score - 0.1, max_score + 0.1, 50).tolist()
            
            # Get cost defaults from env
            fn_mult = float(os.getenv("COST_FN_MULTIPLIER", "1.15"))
            fp_mult = float(os.getenv("COST_FP_MULTIPLIER", "0.02"))
            review_cost = float(os.getenv("COST_PER_REVIEW", "50.0"))
            
            optimal = find_optimal_threshold(
                y_true=y_true, y_scores=y_scores, thresholds=thresholds, 
                amounts=amounts, fn_multiplier=fn_mult, fp_multiplier=fp_mult
            )
            
            boot = bootstrap_cost_estimate(
                y_true=y_true, y_scores=y_scores, amounts=amounts, threshold=optimal['threshold']
            )
            
            # Reconstruct the full curve for plotting
            from backend.cost_model import evaluate_threshold_costs
            curve = evaluate_threshold_costs(
                y_true, y_scores, thresholds, amounts, fn_multiplier=fn_mult, fp_multiplier=fp_mult
            )
            
            # --- Naive Baseline ---
            from backend.baseline import detect_naive
            naive_scores = detect_naive(df)
            naive_thresholds = np.linspace(df['amount'].min(), df['amount'].max(), 50).tolist()
            
            optimal_naive = find_optimal_threshold(
                y_true=y_true, y_scores=naive_scores, thresholds=naive_thresholds,
                amounts=amounts, fn_multiplier=fn_mult, fp_multiplier=fp_mult
            )
            
            # --- Tiered Action Policy ---
            from backend.cost_model import find_optimal_threshold_pair
            optimal_tiered = find_optimal_threshold_pair(
                y_true=y_true, y_scores=y_scores, thresholds=thresholds,
                amounts=amounts, fn_multiplier=fn_mult, fp_multiplier=fp_mult, cost_per_review=review_cost
            )
            
            # --- Per-Segment ---
            segments_data = {}
            for tier in ["Low Volume", "Medium Volume", "High Volume"]:
                t_df = df[df['merchant_tier'] == tier]
                ty_true = t_df['is_anomaly'].astype(int).tolist()
                ty_scores = t_df['model_score'].tolist()
                tamounts = t_df['amount'].tolist()
                
                tif_scores = t_df[t_df['model_score'] > -10.0]['model_score']
                if not tif_scores.empty:
                    t_thresh = np.linspace(float(tif_scores.min()) - 0.1, float(tif_scores.max()) + 0.1, 50).tolist()
                    t_curve = evaluate_threshold_costs(ty_true, ty_scores, t_thresh, tamounts, fn_mult, fp_mult)
                    t_opt = find_optimal_threshold(ty_true, ty_scores, t_thresh, tamounts, fn_mult, fp_mult)
                    t_opt_tiered = find_optimal_threshold_pair(ty_true, ty_scores, t_thresh, tamounts, fn_mult, fp_mult, review_cost)
                    segments_data[tier] = {
                        "curve": t_curve,
                        "optimal": t_opt,
                        "tiered_optimal": t_opt_tiered
                    }
                else:
                    segments_data[tier] = None
                    
            state.cost_data = {
                "curve": curve,
                "optimal": optimal,
                "bootstrap": boot,
                "baseline_cost": sum(amount * 1.15 for amount, is_anom in zip(amounts, y_true) if is_anom == 1),
                "naive_optimal": optimal_naive,
                "tiered_optimal": optimal_tiered,
                "segments": segments_data
            }
        else:
            state.cost_data = {}
            
        # Trigger Auto-Responder Webhooks
        from backend.webhook_log import webhook_manager
        if state.cost_data and "tiered_optimal" in state.cost_data:
            lower_thresh = state.cost_data["tiered_optimal"]["lower_threshold"]
            upper_thresh = state.cost_data["tiered_optimal"]["upper_threshold"]
            
            for m_id, res in merchant_results.items():
                for txn in res.flagged_transactions:
                    score = txn['score']
                    if score >= upper_thresh:
                        tier = "block"
                    elif score >= lower_thresh:
                        tier = "review"
                    else:
                        continue
                        
                    webhook_manager.fire_webhook({
                        "transaction_id": txn['transaction_id'],
                        "merchant_id": m_id,
                        "tier": tier,
                        "anomaly_score": round(score, 3),
                        "reason": txn.get('reason', 'Anomaly detected')
                    })
            
        state.df = df
        state.merchant_results = merchant_results
        state.last_updated = datetime.now()
        
    finally:
        state.is_refreshing = False

@app.on_event("startup")
async def startup_event():
    # Initial pipeline run
    run_pipeline()

@app.post("/refresh")
async def refresh_data(background_tasks: BackgroundTasks):
    if not state.is_refreshing:
        background_tasks.add_task(run_pipeline)
        return {"status": "refreshing"}
    return {"status": "already_refreshing"}

class MerchantSummary(BaseModel):
    merchant_id: str
    total_transactions: int
    flagged_windows: int
    status: str
    last_flag: Optional[str] = None
    is_new: bool = False
    tier: str = "Unknown"
    blend_progress: float = 1.0

@app.get("/merchants", response_model=List[MerchantSummary])
async def get_merchants():
    if state.df is None:
        return []
        
    summaries = []
    for merchant_id, m_df in state.df.groupby('merchant_id'):
        res = state.merchant_results.get(merchant_id)
        flag_count = len(res.flagged_windows) if res else 0
        
        status = "normal"
        if flag_count > 5:
            status = "flagged"
        elif flag_count > 0:
            status = "watch"
            
        last_flag = None
        if flag_count > 0:
            last_flag = max(fw['timestamp'] for fw in res.flagged_windows).isoformat()
            
        tier = m_df['merchant_tier'].iloc[0] if 'merchant_tier' in m_df.columns else "Unknown"
        
        # Calculate blend progress
        from backend.detector import DetectionConfig
        config = DetectionConfig()
        hours_active = len(m_df.set_index('timestamp').resample('1h'))
        blend_progress = min(1.0, hours_active / config.cold_start_threshold)
        is_new = blend_progress < 1.0
            
        summaries.append(MerchantSummary(
            merchant_id=merchant_id,
            total_transactions=len(m_df),
            flagged_windows=flag_count,
            status=status,
            last_flag=last_flag,
            is_new=is_new,
            tier=tier,
            blend_progress=blend_progress
        ))
    return summaries

@app.get("/merchants/{merchant_id}/timeline")
async def get_merchant_timeline(merchant_id: str):
    if state.df is None or merchant_id not in state.merchant_results:
        return {}
        
    df = state.df[state.df['merchant_id'] == merchant_id].copy()
    df = df.set_index('timestamp').resample('1h').agg(
        volume=('transaction_id', 'count'),
        ticket_size=('amount', 'mean'),
    ).fillna(0)
    
    # We'll just return the series data for the frontend to chart
    timeline = []
    for ts, row in df.iterrows():
        timeline.append({
            "timestamp": ts.isoformat(),
            "volume": float(row['volume']),
            "ticket_size": float(row['ticket_size'])
        })
        
    res = state.merchant_results[merchant_id]
    windows = [{"timestamp": fw["timestamp"].isoformat(), "signal": fw["signal"], "detector": fw["detector"]} for fw in res.flagged_windows]
    
    raw_m_df = state.df[state.df['merchant_id'] == merchant_id]
    tier = raw_m_df['merchant_tier'].iloc[0] if 'merchant_tier' in raw_m_df.columns else "Unknown"
    from backend.detector import DetectionConfig
    config = DetectionConfig()
    hours_active = len(df)
    blend_progress = min(1.0, hours_active / config.cold_start_threshold)
    is_new = blend_progress < 1.0
    
    return {
        "timeline": timeline,
        "flagged_windows": windows,
        "is_new": is_new,
        "tier": tier,
        "blend_progress": blend_progress
    }

@app.get("/merchants/{merchant_id}/flags")
async def get_merchant_flags(merchant_id: str):
    if state.df is None or merchant_id not in state.merchant_results:
        return {}
        
    res = state.merchant_results[merchant_id]
    
    return {
        "audit_log": res.audit_log,
        "flagged_transactions": res.flagged_transactions
    }

@app.get("/webhooks/recent")
async def get_recent_webhooks():
    from backend.webhook_log import webhook_manager
    return webhook_manager.get_recent_notifications()

@app.get("/cost-curve")
async def get_cost_curve():
    return state.cost_data
