import sys
import io
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Fix for Windows printing ₹ symbol
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.append(os.path.join(os.path.dirname(__file__), "backend"))
from backend.detector import detect, DetectionConfig
from backend.cost_model import find_optimal_threshold
from backend.utils import format_currency

def evaluate_real_data():
    print("Loading Kaggle Credit Card Fraud Dataset...")
    data_path = os.path.join(os.path.dirname(__file__), "data", "creditcard.csv")
    
    if not os.path.exists(data_path):
        print(f"Error: {data_path} not found.")
        return
        
    df = pd.read_csv(data_path)
    print(f"Loaded {len(df)} transactions.")
    
    # Adapt schema
    # The real dataset has 'Time' in seconds from the first transaction.
    # We map this to a synthetic timestamp.
    base_time = datetime(2023, 1, 1)
    df['timestamp'] = base_time + pd.to_timedelta(df['Time'], unit='s')
    
    # It lacks a transaction_id and merchant_id
    df['transaction_id'] = [f"tx_{i}" for i in range(len(df))]
    df['merchant_id'] = "Global_Merchant" # Treat all as one merchant
    
    # Rename columns to match what our pipeline expects
    df = df.rename(columns={'Amount': 'amount', 'Class': 'is_anomaly'})
    
    # PCA features V1-V28 are numerical.
    pca_features = [f"V{i}" for i in range(1, 29)]
    
    config = DetectionConfig(
        num_features=['amount', 'hour_of_day', 'day_of_week'] + pca_features,
        cat_features=[], # No categorical features in this dataset
        iforest_contamination=0.05 # Lower contamination for real dataset which has ~0.17% fraud
    )
    
    print("\nRunning Two-Stage Detection Pipeline on real dataset...")
    result = detect(df, config=config)
    
    print(f"Stage 1 Flagged Windows: {len(result.flagged_windows)}")
    
    if not result.flagged_transactions:
        print("No transactions were flagged by Stage 1.")
        return
        
    print(f"Transactions routed to Stage 2: {len(result.flagged_transactions)} ({(len(result.flagged_transactions) / len(df)) * 100:.2f}%)")
    
    # Merge scores
    scores_df = pd.DataFrame(result.flagged_transactions)[['transaction_id', 'score']]
    df = df.merge(scores_df, on='transaction_id', how='left')
    
    # Debug: how many frauds in stage 2?
    frauds_in_stage2 = df[(df['is_anomaly'] == 1) & (df['score'].notna())]
    print(f"True fraud transactions routed to Stage 2: {len(frauds_in_stage2)} out of {df['is_anomaly'].sum()}")
    
    # Unflagged transactions get a very low score
    min_score = df['score'].min()
    df['score'] = df['score'].fillna(min_score - 1.0)
    
    y_true = df['is_anomaly'].tolist()
    y_scores = df['score'].tolist()
    amounts = df['amount'].tolist()
    
    # Evaluate purely on F1 to show model performance independent of cost constraints
    from sklearn.metrics import precision_recall_curve
    precisions, recalls, thresholds = precision_recall_curve(y_true, y_scores)
    f1_scores = 2 * (precisions * recalls) / (precisions + recalls + 1e-10)
    best_idx = np.argmax(f1_scores)
    best_f1_threshold = thresholds[best_idx] if best_idx < len(thresholds) else thresholds[-1]
    print(f"\nBest Possible F1 Score on Real Data: {f1_scores[best_idx]:.3f} (at threshold {best_f1_threshold:.3f})")
    
    threshold_grid = np.linspace(df['score'].min() - 0.01, df['score'].max() + 0.01, 100).tolist()
    
    optimal = find_optimal_threshold(
        y_true=y_true,
        y_scores=y_scores,
        thresholds=threshold_grid,
        amounts=amounts,
        fn_multiplier=1.15,
        fp_multiplier=0.005  # Adjusted for Kaggle dataset's extreme class imbalance
    )
    
    # Naive baseline for comparison
    from backend.baseline import detect_naive
    naive_scores = detect_naive(df)
    naive_thresholds = np.linspace(df['amount'].min(), df['amount'].max(), 50).tolist()
    optimal_naive = find_optimal_threshold(
        y_true, naive_scores, naive_thresholds, amounts, 1.15, 0.005
    )
    
    print("\n" + "="*50)
    print("COMPARISON: Naive Baseline vs. Our Detector (Real Data)")
    print("="*50)
    print(f"{'Metric':<15} | {'Naive Baseline':<15} | {'Our Detector':<15}")
    print("-" * 50)
    print(f"{'Total Cost':<15} | {format_currency(optimal_naive['total_cost']):<14} | {format_currency(optimal['total_cost']):<14}")
    print(f"{'Precision':<15} | {optimal_naive['precision']:<15.3f} | {optimal['precision']:<15.3f}")
    print(f"{'Recall':<15} | {optimal_naive['recall']:<15.3f} | {optimal['recall']:<15.3f}")
    print(f"{'F1 Score':<15} | {optimal_naive['f1']:<15.3f} | {optimal['f1']:<15.3f}")
    print("="*50)

if __name__ == "__main__":
    evaluate_real_data()
