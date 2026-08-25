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
        
        # 2. Detect
        config = DetectionConfig()
        merchant_results = {}
        df['model_score'] = -10.0
        
        for merchant_id, m_df in df.groupby('merchant_id'):
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
            
            optimal = find_optimal_threshold(
                y_true=y_true, y_scores=y_scores, thresholds=thresholds, 
                amounts=amounts, fn_multiplier=1.15, fp_multiplier=0.02
            )
            
            boot = bootstrap_cost_estimate(
                y_true=y_true, y_scores=y_scores, amounts=amounts, threshold=optimal['threshold']
            )
            
            # Reconstruct the full curve for plotting
            # We don't have evaluate_threshold_costs exposed directly here so we'll just run find_optimal which returns the min,
            # wait, we need the full curve. evaluate_threshold_costs isn't imported. Let me import it.
            from backend.cost_model import evaluate_threshold_costs
            curve = evaluate_threshold_costs(
                y_true, y_scores, thresholds, amounts, fn_multiplier=1.15, fp_multiplier=0.02
            )
            
            state.cost_data = {
                "curve": curve,
                "optimal": optimal,
                "bootstrap": boot,
                "baseline_cost": sum(amount * 1.15 for amount, is_anom in zip(amounts, y_true) if is_anom == 1)
            }
        else:
            state.cost_data = {}
            
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
            
        summaries.append(MerchantSummary(
            merchant_id=merchant_id,
            total_transactions=len(m_df),
            flagged_windows=flag_count,
            status=status,
            last_flag=last_flag
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
    
    return {
        "timeline": timeline,
        "flagged_windows": windows
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

@app.get("/cost-curve")
async def get_cost_curve():
    return state.cost_data
