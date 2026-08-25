import sys
import os
import numpy as np

# Add backend to path so we can import cost_model
sys.path.append(os.path.join(os.path.dirname(__file__), "backend"))
from backend.cost_model import find_optimal_threshold, bootstrap_cost_estimate

def main():
    np.random.seed(42)
    n_samples = 500
    
    # Generate toy data
    # 5% fraud
    y_true = np.random.choice([0, 1], size=n_samples, p=[0.95, 0.05])
    
    # True positives get higher scores, true negatives get lower scores with some overlap
    y_scores = np.where(y_true == 1, 
                        np.random.normal(loc=0.8, scale=0.15, size=n_samples),
                        np.random.normal(loc=0.3, scale=0.2, size=n_samples))
    y_scores = np.clip(y_scores, 0.0, 1.0)
    
    # Random amounts log-normally distributed
    amounts = np.random.lognormal(mean=3.0, sigma=1.0, size=n_samples)
    amounts = np.round(amounts, 2)
    
    thresholds = np.linspace(0.0, 1.0, 50).tolist()
    
    print("Running optimal threshold finder...")
    optimal = find_optimal_threshold(
        y_true=y_true.tolist(),
        y_scores=y_scores.tolist(),
        thresholds=thresholds,
        amounts=amounts.tolist()
    )
    
    print(f"\nOptimal Threshold: {optimal['threshold']:.3f}")
    print(f"Total Cost: ${optimal['total_cost']:.2f}")
    print(f"Confusion Matrix -> TP: {optimal['tp']}, FP: {optimal['fp']}, FN: {optimal['fn']}, TN: {optimal['tn']}")
    print(f"Metrics -> Precision: {optimal['precision']:.3f}, Recall: {optimal['recall']:.3f}, F1: {optimal['f1']:.3f}")
    
    print("\nRunning bootstrap cost estimate...")
    bootstrap_res = bootstrap_cost_estimate(
        y_true=y_true.tolist(),
        y_scores=y_scores.tolist(),
        amounts=amounts.tolist(),
        threshold=optimal['threshold']
    )
    
    mean_cost = bootstrap_res['mean_cost']
    lower = bootstrap_res['ci_lower_90']
    upper = bootstrap_res['ci_upper_90']
    
    print(f"\nBootstrap Results (n={bootstrap_res['n_bootstrap']}):")
    print(f"Expected Cost: ${mean_cost:.2f}, with a 90% CI of [${lower:.2f}, ${upper:.2f}]")

if __name__ == "__main__":
    main()
