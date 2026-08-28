import sys
import io
import os
import pandas as pd
import numpy as np
from typing import List

# Fix for Windows printing ₹ symbol
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

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
    
    from backend.utils import format_currency
    
    # 1. Baseline Cost (if we did nothing and allowed everything)
    total_baseline_fn_cost = sum(amount * 1.15 for amount, is_anom in zip(amounts, y_true) if is_anom == 1)
    print(f"Cost of doing nothing (100% missed fraud): {format_currency(total_baseline_fn_cost)}")
    
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
    print(f"Total Model Cost:  {format_currency(optimal['total_cost'])}")
    print(f"Savings vs Doing Nothing: {format_currency(total_baseline_fn_cost - optimal['total_cost'])}")
    print(f"Confusion Matrix:  TP: {optimal['tp']} | FP: {optimal['fp']} | FN: {optimal['fn']} | TN: {optimal['tn']}")
    print(f"Metrics:           Precision: {optimal['precision']:.3f} | Recall: {optimal['recall']:.3f} | F1: {optimal['f1']:.3f}")
    
    # --- NAIVE BASELINE ---
    print("\n--- Running Naive Baseline ---")
    from backend.baseline import detect_naive
    naive_scores = detect_naive(df)
    
    naive_thresholds = np.linspace(df['amount'].min(), df['amount'].max(), 100).tolist()
    
    optimal_naive = find_optimal_threshold(
        y_true=y_true,
        y_scores=naive_scores,
        thresholds=naive_thresholds,
        amounts=amounts,
        fn_multiplier=1.15,
        fp_multiplier=0.02
    )
    
    print(f"Naive Optimal Threshold (Amount): {optimal_naive['threshold']:.2f}")
    print(f"Naive Total Cost:  {format_currency(optimal_naive['total_cost'])}")
    print(f"Naive Metrics:     Precision: {optimal_naive['precision']:.3f} | Recall: {optimal_naive['recall']:.3f} | F1: {optimal_naive['f1']:.3f}")
    
    # --- COMPARISON TABLE ---
    print("\n" + "="*50)
    print("COMPARISON: Naive Baseline vs. Regime-Break Detector")
    print("="*50)
    print(f"{'Metric':<15} | {'Naive Baseline':<15} | {'Our Detector':<15}")
    print("-" * 50)
    print(f"{'Total Cost':<15} | {format_currency(optimal_naive['total_cost']):<14} | {format_currency(optimal['total_cost']):<14}")
    print(f"{'Precision':<15} | {optimal_naive['precision']:<15.3f} | {optimal['precision']:<15.3f}")
    print(f"{'Recall':<15} | {optimal_naive['recall']:<15.3f} | {optimal['recall']:<15.3f}")
    print(f"{'F1 Score':<15} | {optimal_naive['f1']:<15.3f} | {optimal['f1']:<15.3f}")
    print("="*50)
    print(f"TOTAL SAVINGS: {format_currency(optimal_naive['total_cost'] - optimal['total_cost'])}")
    
    # 3. Bootstrap CI for our model
    print("\nRunning Bootstrap Cost Estimate for Our Model (n=200)...")
    boot = bootstrap_cost_estimate(
        y_true=y_true,
        y_scores=y_scores,
        amounts=amounts,
        threshold=optimal['threshold']
    )
    
    mean_cost = boot['mean_cost']
    lower = boot['ci_lower_90']
    upper = boot['ci_upper_90']
    
    print(f"Expected Model Cost: {format_currency(mean_cost)}, with a 90% CI of [{format_currency(lower)}, {format_currency(upper)}]")
    
    # 4. Tiered Action Policy
    print("\n--- Running Tiered Action Policy (Allow, Review, Block) ---")
    from backend.cost_model import find_optimal_threshold_pair
    # Given larger amounts, review cost of 1.0 might be too small to skip. Wait, 
    # FP cost = amount * 0.02. Median amount ~1000, FP = 20. So review cost should be roughly 10-50 to be realistic.
    # Let's set review cost to 50.0
    optimal_pair = find_optimal_threshold_pair(
        y_true=y_true,
        y_scores=y_scores,
        thresholds=thresholds,
        amounts=amounts,
        fn_multiplier=1.15,
        fp_multiplier=0.02,
        cost_per_review=50.0
    )
    
    print(f"Tiered Optimal Thresholds: Lower={optimal_pair['lower_threshold']:.3f}, Upper={optimal_pair['upper_threshold']:.3f}")
    print(f"Tiered Total Cost: {format_currency(optimal_pair['total_cost'])}")
    print(f"Tier Breakdown:")
    print(f"  Allow:  {optimal_pair['allowed_fraud']} fraud, {optimal_pair['allowed_legit']} legit")
    print(f"  Review: {optimal_pair['reviewed_fraud']} fraud, {optimal_pair['reviewed_legit']} legit")
    print(f"  Block:  {optimal_pair['blocked_fraud']} fraud, {optimal_pair['blocked_legit']} legit")
    print(f"Cost Breakdown:")
    print(f"  FN Cost (Allowed Fraud): {format_currency(optimal_pair['fn_cost'])}")
    print(f"  FP Cost (Blocked Legit): {format_currency(optimal_pair['fp_cost'])}")
    print(f"  Review Cost:             {format_currency(optimal_pair['review_cost'])}")
    print(f"Savings vs Binary Policy:  {format_currency(optimal['total_cost'] - optimal_pair['total_cost'])}")
    
    # 5. Per-Segment Optimization
    print("\n--- Running Per-Segment Threshold Optimization ---")
    # Bucket merchants by volume
    merchant_vols = df.groupby('merchant_id').size()
    q33, q67 = merchant_vols.quantile([0.33, 0.67])
    
    def get_tier(vol):
        if vol <= q33: return "Low Volume"
        if vol <= q67: return "Medium Volume"
        return "High Volume"
        
    merchant_tiers = merchant_vols.apply(get_tier)
    df['merchant_tier'] = df['merchant_id'].map(merchant_tiers)
    
    total_segmented_cost = 0
    total_segmented_cost_tiered = 0
    
    for tier in ["Low Volume", "Medium Volume", "High Volume"]:
        tier_mask = df['merchant_tier'] == tier
        tier_df = df[tier_mask]
        
        y_true_tier = tier_df['is_anomaly'].astype(int).tolist()
        y_scores_tier = tier_df['model_score'].tolist()
        amounts_tier = tier_df['amount'].tolist()
        
        # We might not have flags in a small tier, so handle empty IF scores
        if_scores_tier = tier_df[tier_df['model_score'] > -10.0]['model_score']
        if if_scores_tier.empty:
            # All normal, cost is just missed fraud
            tier_cost = sum(a * 1.15 for a, y in zip(amounts_tier, y_true_tier) if y == 1)
            print(f"\n{tier} Tier: No flagged transactions.")
            print(f"Cost: {format_currency(tier_cost)}")
            total_segmented_cost += tier_cost
            total_segmented_cost_tiered += tier_cost
            continue
            
        min_s = float(if_scores_tier.min())
        max_s = float(if_scores_tier.max())
        thresh_tier = np.linspace(min_s - 0.1, max_s + 0.1, 50).tolist()
        
        opt_tier = find_optimal_threshold(
            y_true_tier, y_scores_tier, thresh_tier, amounts_tier, 1.15, 0.02
        )
        opt_pair_tier = find_optimal_threshold_pair(
            y_true_tier, y_scores_tier, thresh_tier, amounts_tier, 1.15, 0.02, 50.0
        )
        
        total_segmented_cost += opt_tier['total_cost']
        total_segmented_cost_tiered += opt_pair_tier['total_cost']
        
        print(f"\n{tier} Tier:")
        print(f"  Single Threshold: {opt_tier['threshold']:.3f} | Cost: {format_currency(opt_tier['total_cost'])}")
        print(f"  Tiered Thresholds: Lower={opt_pair_tier['lower_threshold']:.3f}, Upper={opt_pair_tier['upper_threshold']:.3f} | Cost: {format_currency(opt_pair_tier['total_cost'])}")

    print("\n--- Summary of Segmentation ---")
    print(f"Global Single Threshold Cost:   {format_currency(optimal['total_cost'])}")
    print(f"Segmented Single Threshold Cost:{format_currency(total_segmented_cost)}")
    print(f"Savings from Segmentation (1D): {format_currency(optimal['total_cost'] - total_segmented_cost)}")
    print(f"\nGlobal Tiered Cost:             {format_currency(optimal_pair['total_cost'])}")
    print(f"Segmented Tiered Cost:          {format_currency(total_segmented_cost_tiered)}")
    print(f"Savings from Seg + Tiers vs Global Binary: {format_currency(optimal['total_cost'] - total_segmented_cost_tiered)}")

if __name__ == "__main__":
    evaluate()
