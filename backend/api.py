import os
import sys
import pandas as pd
import numpy as np
from fastapi import FastAPI, BackgroundTasks, Request, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime
import hmac
import hashlib
import json

# Local imports
from data.generator import generate_dataset
from backend.detector import detect, DetectionConfig, DetectionResult
from backend.cost_model import find_optimal_threshold, bootstrap_cost_estimate
from backend import razorpay_client

app = FastAPI(title="PulseGuard Risk Console API")

allowed_origins_env = os.getenv("ALLOWED_ORIGINS")
allowed_origins = [origin.strip() for origin in allowed_origins_env.split(",")] if allowed_origins_env else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
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
    ground_truth_labels: List[Dict[str, Any]] = []
    recalibration_report: Optional[Dict[str, Any]] = None

state = AppState()

def run_pipeline():
    state.is_refreshing = True
    try:
        # 1. Generate Data
        df = generate_dataset(num_merchants=5, days=15) # Smaller dataset for faster refresh during pitch
        df['created_at'] = pd.to_datetime(df['created_at'], unit='s')
        
        # Extract merchant_id and tier from notes
        df['merchant_id'] = df['notes'].apply(lambda x: x.get('merchant_id'))
        
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
                
            tier_df['time_diff'] = tier_df.groupby('merchant_id')['created_at'].diff().dt.total_seconds().fillna(0)
            
            # Aggregate by hour across all merchants in tier
            t_agg = tier_df.set_index('created_at').resample('1h').agg(
                volume=('id', 'count'),
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
            
            score_dict = {ft['id']: ft['score'] for ft in res.flagged_transactions}
            if score_dict:
                mask = df['merchant_id'] == merchant_id
                df.loc[mask, 'model_score'] = df.loc[mask, 'id'].map(score_dict).fillna(-10.0)
                
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
            review_cost = float(os.getenv("COST_PER_REVIEW", "5000.0"))
            
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
                        "id": txn['id'],
                        "merchant_id": m_id,
                        "tier": tier,
                        "anomaly_score": round(score, 3),
                        "reason": txn.get('reason', 'Anomaly detected')
                    })
            
        state.df = df
        state.merchant_results = merchant_results
        state.last_updated = datetime.now()
        webhook_manager.flush_batch()
        
    finally:
        state.is_refreshing = False

@app.on_event("startup")
async def startup_event():
    # Initial pipeline run
    import asyncio
    asyncio.create_task(asyncio.to_thread(run_pipeline))

@app.post("/refresh")
async def refresh_data(background_tasks: BackgroundTasks):
    if not state.is_refreshing:
        state.is_refreshing = True
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
            last_flag = max(fw['created_at'] for fw in res.flagged_windows).isoformat()
            
        tier = m_df['merchant_tier'].iloc[0] if 'merchant_tier' in m_df.columns else "Unknown"
        
        # Calculate blend progress
        from backend.detector import DetectionConfig
        config = DetectionConfig()
        hours_active = len(m_df.set_index('created_at').resample('1h'))
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
    df = df.set_index('created_at').resample('1h').agg(
        volume=('id', 'count'),
        ticket_size=('amount', 'mean'),
    ).fillna(0)
    
    # We'll just return the series data for the frontend to chart
    timeline = []
    for ts, row in df.iterrows():
        timeline.append({
            "created_at": ts.isoformat(),
            "volume": float(row['volume']),
            "ticket_size": float(row['ticket_size'])
        })
        
    res = state.merchant_results[merchant_id]
    windows = [{"created_at": fw["created_at"].isoformat(), "signal": fw["signal"], "detector": fw["detector"]} for fw in res.flagged_windows]
    
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
async def get_cost_curve(fn_multiplier: float = None, fp_multiplier: float = None):
    if state.df is None or not state.cost_data:
        return state.cost_data
        
    if fn_multiplier is None and fp_multiplier is None:
        return state.cost_data
        
    # User provided overrides
    fn_mult = fn_multiplier if fn_multiplier is not None else float(os.getenv("COST_FN_MULTIPLIER", "1.15"))
    fp_mult = fp_multiplier if fp_multiplier is not None else float(os.getenv("COST_FP_MULTIPLIER", "0.02"))
    
    df = state.df
    y_true = df['is_anomaly'].astype(int).tolist()
    y_scores = df['model_score'].tolist()
    amounts = df['amount'].tolist()
    
    if_scores = df[df['model_score'] > -10.0]['model_score']
    if if_scores.empty:
        return state.cost_data
        
    min_score, max_score = float(if_scores.min()), float(if_scores.max())
    thresholds = np.linspace(min_score - 0.1, max_score + 0.1, 50).tolist()
    
    optimal = find_optimal_threshold(
        y_true=y_true, y_scores=y_scores, thresholds=thresholds, 
        amounts=amounts, fn_multiplier=fn_mult, fp_multiplier=fp_mult
    )
    
    boot = bootstrap_cost_estimate(
        y_true=y_true, y_scores=y_scores, amounts=amounts, threshold=optimal['threshold']
    )
    
    from backend.cost_model import evaluate_threshold_costs
    curve = evaluate_threshold_costs(
        y_true, y_scores, thresholds, amounts, fn_multiplier=fn_mult, fp_multiplier=fp_mult
    )
    
    from backend.baseline import detect_naive
    naive_scores = detect_naive(df)
    naive_thresholds = np.linspace(df['amount'].min(), df['amount'].max(), 50).tolist()
    
    optimal_naive = find_optimal_threshold(
        y_true=y_true, y_scores=naive_scores, thresholds=naive_thresholds,
        amounts=amounts, fn_multiplier=fn_mult, fp_multiplier=fp_mult
    )
    
    new_cost_data = dict(state.cost_data)
    new_cost_data["curve"] = curve
    new_cost_data["optimal"] = optimal
    new_cost_data["bootstrap"] = boot
    new_cost_data["baseline_cost"] = sum(amount * fn_mult for amount, is_anom in zip(amounts, y_true) if is_anom == 1)
    new_cost_data["naive_optimal"] = optimal_naive
    
    # Recompute segments so sliders work everywhere
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
            
            # Keep original tiered_optimal for now since we aren't rebuilding that deeply
            orig_tiered = state.cost_data.get("segments", {}).get(tier, {}).get("tiered_optimal")
            
            segments_data[tier] = {
                "curve": t_curve,
                "optimal": t_opt,
                "tiered_optimal": orig_tiered
            }
        else:
            segments_data[tier] = None
            
    new_cost_data["segments"] = segments_data
    
    return new_cost_data
    
class TestOrderRequest(BaseModel):
    amount: int

@app.post("/razorpay/create-test-order")
async def create_test_order_endpoint(req: TestOrderRequest):
    """Creates a real test mode order for demo purposes."""
    order = razorpay_client.create_test_order(amount_paise=req.amount)
    if not order:
        raise HTTPException(status_code=503, detail="Razorpay credentials not configured")
    return {
        "order_id": order["id"], 
        "amount": order["amount"], 
        "currency": order["currency"],
        "key_id": razorpay_client.RAZORPAY_KEY_ID
    }

class IngestPaymentRequest(BaseModel):
    payment_id: str
    merchant_id: str = "M_001"

@app.post("/razorpay/ingest-test-payment")
async def ingest_test_payment(req: IngestPaymentRequest):
    """Fetches a completed payment and injects it into the pipeline."""
    payment = razorpay_client.fetch_payment(req.payment_id)
    if not payment:
        raise HTTPException(status_code=503, detail="Razorpay credentials not configured or payment not found")
        
    if state.df is None or state.df.empty:
        raise HTTPException(status_code=400, detail="Pipeline not initialized. Refresh data first.")
        
    new_txn = {
        'id': payment['id'],
        'entity': 'payment',
        'amount': payment['amount'],
        'currency': payment.get('currency', 'INR'),
        'status': payment.get('status', 'captured'),
        'method': payment.get('method', 'card'),
        'email': payment.get('email', 'demo@example.com'),
        'contact': payment.get('contact', '+919999999999'),
        'notes': {
            'merchant_id': req.merchant_id,
            'merchant_tier': 'Medium Volume',
            'location': 'domestic'
        },
        'created_at': pd.to_datetime(payment['created_at'], unit='s'),
        'is_anomaly': False,
        'anomaly_type': 'none',
        'merchant_id': req.merchant_id,
        'merchant_tier': 'Medium Volume'
    }
    
    merchant_mask = state.df['merchant_id'] == req.merchant_id
    if merchant_mask.any():
        new_txn['merchant_tier'] = state.df[merchant_mask]['merchant_tier'].iloc[0]
        
    new_row = pd.DataFrame([new_txn])
    
    import asyncio
    if not hasattr(state, 'lock'):
        state.lock = asyncio.Lock()
        
    async with state.lock:
        state.df = pd.concat([state.df, new_row], ignore_index=True)
        m_df = state.df[state.df['merchant_id'] == req.merchant_id].copy()
        tier = m_df['merchant_tier'].iloc[0]
        
        config = DetectionConfig()
        
        tier_df = state.df[state.df['merchant_tier'] == tier].copy()
        tier_df['time_diff'] = tier_df.groupby('merchant_id')['created_at'].diff().dt.total_seconds().fillna(0)
        
        t_agg = tier_df.set_index('created_at').resample('1h').agg(
            volume=('id', 'count'),
            ticket_size=('amount', 'mean'),
            velocity=('time_diff', 'mean')
        ).fillna(0)
        num_merch = tier_df['merchant_id'].nunique()
        t_agg['volume'] = t_agg['volume'] / num_merch
        
        config.tier_priors = {
            signal: {
                'volume': {'mean': t_agg['volume'].mean(), 'std': t_agg['volume'].std()},
                'ticket_size': {'mean': t_agg['ticket_size'].mean(), 'std': t_agg['ticket_size'].std()},
                'velocity': {'mean': t_agg['velocity'].mean(), 'std': t_agg['velocity'].std()}
            }.get(signal, {}) for signal in ['volume', 'ticket_size', 'velocity']
        }
        
        res = detect(m_df, config)
        state.merchant_results[req.merchant_id] = res
        
        score_dict = {ft['id']: ft['score'] for ft in res.flagged_transactions}
        if score_dict:
            state.df.loc[state.df['merchant_id'] == req.merchant_id, 'model_score'] = state.df.loc[state.df['merchant_id'] == req.merchant_id, 'id'].map(score_dict).fillna(-10.0)
    
    from backend.webhook_log import webhook_manager
    flagged = next((ft for ft in res.flagged_transactions if ft['id'] == payment['id']), None)
    if flagged and state.cost_data and "tiered_optimal" in state.cost_data:
        lower_thresh = state.cost_data["tiered_optimal"]["lower_threshold"]
        upper_thresh = state.cost_data["tiered_optimal"]["upper_threshold"]
        score = flagged['score']
        
        tier_action = None
        if score >= upper_thresh:
            tier_action = "block"
        elif score >= lower_thresh:
            tier_action = "review"
            
        if tier_action:
            webhook_manager.fire_webhook({
                "id": flagged['id'],
                "merchant_id": req.merchant_id,
                "tier": tier_action,
                "anomaly_score": round(score, 3),
                "reason": flagged.get('reason', 'Anomaly detected')
            })
            
    return {"status": "ok", "payment_id": payment['id'], "flagged": bool(flagged), "score": flagged['score'] if flagged else None}

@app.post("/webhooks/razorpay")
async def razorpay_webhook(request: Request, x_razorpay_signature: str = Header(None)):
    """
    Genuine Razorpay webhook receiver.
    PulseGuard can consume Razorpay's own dispute webhooks as real, delayed ground truth, 
    closing the loop between the delayed-label problem we identified and the cost model's assumptions — 
    this is a genuine integration point, not a simulated one.
    
    Signature verification is critical: without this, anyone could POST a fake payload 
    to the endpoint and trigger false actions.
    """
    if not os.getenv("ENABLE_REAL_WEBHOOKS", "false").lower() == "true":
        return {"status": "ignored", "reason": "real webhooks disabled by config"}
        
    secret = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")
    if not secret:
        raise HTTPException(status_code=500, detail="Webhook secret not configured")
        
    body = await request.body()
    
    # Verify signature
    if not x_razorpay_signature:
        raise HTTPException(status_code=400, detail="Missing signature")
        
    expected_signature = hmac.new(
        key=secret.encode(),
        msg=body,
        digestmod=hashlib.sha256
    ).hexdigest()
    
    if not hmac.compare_digest(expected_signature, x_razorpay_signature):
        raise HTTPException(status_code=400, detail="Invalid signature")
        
    try:
        payload = json.loads(body)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")
        
    event = payload.get("event")
    
    if event == "payment.dispute.created":
        # Handle ground truth delayed label
        payment_id = payload.get("payload", {}).get("payment", {}).get("entity", {}).get("id")
        amount = payload.get("payload", {}).get("payment", {}).get("entity", {}).get("amount", 0)
        
        state.ground_truth_labels.append({
            "payment_id": payment_id,
            "timestamp": datetime.now(),
            "amount": amount
        })
        
        # Build recalibration report
        fn_mult = float(os.getenv("COST_FN_MULTIPLIER", "1.15"))
        missed_cost = amount * fn_mult
        
        total_missed = sum(lbl["amount"] for lbl in state.ground_truth_labels) * fn_mult
        
        state.recalibration_report = {
            "new_confirmed_frauds": len(state.ground_truth_labels),
            "total_delayed_cost_impact": total_missed,
            "message": f"Incorporating this dispute adds {missed_cost} to the false negative cost penalty. If the model had caught this, it would have saved the merchant from the chargeback."
        }
        
    return {"status": "ok"}

@app.get("/recalibration-report")
async def get_recalibration_report():
    return state.recalibration_report or {
        "new_confirmed_frauds": 0, 
        "total_delayed_cost_impact": 0.0, 
        "message": "No new disputes received yet. Webhook receiver is listening."
    }

