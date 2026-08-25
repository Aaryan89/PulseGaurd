import sys
import os
import pandas as pd
import numpy as np
from typing import List

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), "backend"))
from backend.detector import detect, DetectionConfig
from backend.cost_model import find_optimal_threshold, bootstrap_cost_estimate

def evaluate():
    data_path = os.path.join(os.path.dirname(__file__), "data", "synthetic_transactions.csv")
    if not os.path.exists(data_path):
        print(f"Data file not found at {data_path}. Please generate it first.")
        return
        
    print("Loading synthetic dataset...")
    df = pd.read_csv(data_path)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Initialize all scores to an extremely low (normal) baseline
    # Isolation forest scores typically range roughly from -0.5 (very normal) to 0.5 (very anomalous).
    # We will assign -10.0 to all transactions that pass the Stage 1 filter safely.
    df['model_score'] = -10.0
    
    config = DetectionConfig(
        window_freq='1h',
        ewma_span=24,
        ewma_control_limit_std=3.0,
        cusum_threshold=3.0,
        cusum_drift=0.5,
        burn_in_periods=24
    )
    
    print("Running 2-Stage Detection across all merchants...")
    grouped = df.groupby('merchant_id')
    
    total_txns = len(df)
    txns_in_flagged_windows = 0
    total_flags = 0
    
    for merchant_id, m_df in grouped:
        print(f"  Processing Merchant {merchant_id} ({len(m_df)} txns)...")
        res = detect(m_df, config)
        
        score_dict = {ft['transaction_id']: ft['score'] for ft in res.flagged_transactions}
        
        if score_dict:
            txns_in_flagged_windows += len(score_dict)
            total_flags += len(res.flagged_windows)
            
            mask = df['merchant_id'] == merchant_id
            # Use mapping. Any missing transaction ID gets -10.0
            updated_scores = df.loc[mask, 'transaction_id'].map(score_dict).fillna(-10.0)
            df.loc[mask, 'model_score'] = updated_scores
            
    print(f"\nDetection Summary:")
    print(f"Total Transactions: {total_txns}")
    print(f"Stage 1 Flagged Windows: {total_flags}")
    print(f"Transactions routed to Stage 2 (Isolation Forest): {txns_in_flagged_windows} ({txns_in_flagged_windows/total_txns*100:.2f}%)")
    
    print("\nEvaluating Cost Model...")
    y_true = df['is_anomaly'].astype(int).tolist()
    y_scores = df['model_score'].tolist()
    amounts = df['amount'].tolist()
    
    # Generate an intelligent spread of thresholds. 
    # We only care about sweeping thresholds for things actually scored by IF.
    if_scores = df[df['model_score'] > -10.0]['model_score']
    if if_scores.empty:
        print("No transactions were flagged by Stage 1. Cost model cannot optimize.")
        return
        
    min_score = float(if_scores.min())
    max_score = float(if_scores.max())
    thresholds = np.linspace(min_score - 0.1, max_score + 0.1, 100).tolist()
    
    # 1. Baseline Cost (if we did nothing and allowed everything)
    total_baseline_fn_cost = sum(amount * 1.15 for amount, is_anom in zip(amounts, y_true) if is_anom == 1)
    print(f"Cost of doing nothing (100% missed fraud): ${total_baseline_fn_cost:,.2f}")
    
    # 2. Optimal operating point
    optimal = find_optimal_threshold(
        y_true=y_true,
        y_scores=y_scores,
        thresholds=thresholds,
        amounts=amounts,
        fn_multiplier=1.15,
        fp_multiplier=0.02
    )
    
    print(f"\n--- Model's Chosen Operating Point ---")
    print(f"Optimal Threshold: {optimal['threshold']:.3f}")
    print(f"Total Model Cost:  ${optimal['total_cost']:,.2f}")
    print(f"Savings vs Doing Nothing: ${total_baseline_fn_cost - optimal['total_cost']:,.2f}")
    print(f"Confusion Matrix:  TP: {optimal['tp']} | FP: {optimal['fp']} | FN: {optimal['fn']} | TN: {optimal['tn']}")
    print(f"Metrics:           Precision: {optimal['precision']:.3f} | Recall: {optimal['recall']:.3f} | F1: {optimal['f1']:.3f}")
    
    # 3. Bootstrap CI
    print("\nRunning Bootstrap Cost Estimate (n=200)...")
    boot = bootstrap_cost_estimate(
        y_true=y_true,
        y_scores=y_scores,
        amounts=amounts,
        threshold=optimal['threshold']
    )
    
    mean_cost = boot['mean_cost']
    lower = boot['ci_lower_90']
    upper = boot['ci_upper_90']
    
    print(f"Expected Model Cost: ${mean_cost:,.2f}, with a 90% CI of [${lower:,.2f}, ${upper:,.2f}]")

if __name__ == "__main__":
    evaluate()
