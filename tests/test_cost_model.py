import pytest
from backend.cost_model import (
    calculate_cost, 
    evaluate_threshold_costs, 
    find_optimal_threshold, 
    bootstrap_cost_estimate,
    find_optimal_threshold_pair
)

def test_calculate_cost():
    # Basic math sanity check
    cost = calculate_cost(
        true_positives=10, false_positives=5, false_negatives=2, true_negatives=100,
        cost_per_fn=100.0, cost_per_fp=50.0, cost_per_tp=0.0, cost_per_tn=0.0
    )
    # Expected: 5 * 50 + 2 * 100 = 450
    assert cost == 450.0

def test_evaluate_threshold_costs():
    # 5 txns:
    # 0: legit, score 0.1, amount 100
    # 1: fraud, score 0.9, amount 200
    # 2: legit, score 0.8, amount 50
    # 3: fraud, score 0.3, amount 300
    # 4: legit, score 0.4, amount 10
    
    y_true = [0, 1, 0, 1, 0]
    y_scores = [0.1, 0.9, 0.8, 0.3, 0.4]
    amounts = [100, 200, 50, 300, 10]
    
    # Threshold 0.5:
    # Preds: [False, True, True, False, False]
    # TP: idx 1 (1)
    # FP: idx 2 (1)
    # FN: idx 3 (1)
    # TN: idx 0, 4 (2)
    # FP Cost = 50 * 0.02 = 1.0
    # FN Cost = 300 * 1.15 = 345.0
    # Total = 346.0
    
    res = evaluate_threshold_costs(
        y_true, y_scores, [0.5], amounts, fn_multiplier=1.15, fp_multiplier=0.02
    )
    
    assert len(res) == 1
    m = res[0]
    assert m["tp"] == 1
    assert m["fp"] == 1
    assert m["fn"] == 1
    assert m["tn"] == 2
    assert m["total_cost"] == 346.0
    
def test_find_optimal_threshold():
    y_true = [0, 1, 0, 1, 0]
    y_scores = [0.1, 0.9, 0.8, 0.3, 0.4]
    amounts = [100, 200, 50, 300, 10]
    thresholds = [0.0, 0.5, 1.0]
    
    # At 0.0: all true. TP=2, FP=3, FN=0. FP cost = (100+50+10)*0.02 = 160 * 0.02 = 3.2. Total = 3.2
    # At 0.5: Total = 346.0
    # At 1.0: all false. TP=0, FP=0, FN=2. FN cost = (200+300)*1.15 = 500 * 1.15 = 575. Total = 575
    
    optimal = find_optimal_threshold(
        y_true, y_scores, thresholds, amounts, fn_multiplier=1.15, fp_multiplier=0.02
    )
    assert optimal["threshold"] == 0.0
    assert optimal["total_cost"] == 3.2

def test_bootstrap_cost_estimate():
    y_true = [0, 1, 0, 1, 0] * 20
    y_scores = [0.1, 0.9, 0.8, 0.3, 0.4] * 20
    amounts = [100, 200, 50, 300, 10] * 20
    
    boot = bootstrap_cost_estimate(
        y_true, y_scores, amounts, threshold=0.5, fn_multiplier=1.15, fp_multiplier=0.02, n_bootstrap=50
    )
    assert "mean_cost" in boot
    assert "ci_lower_90" in boot
    assert "ci_upper_90" in boot
    assert boot["ci_lower_90"] <= boot["ci_upper_90"]

def test_find_optimal_threshold_pair():
    y_true = [0, 1, 0, 1, 0]
    y_scores = [0.1, 0.9, 0.8, 0.3, 0.4]
    amounts = [100, 200, 50, 300, 10]
    thresholds = [0.2, 0.5, 0.8]
    
    optimal = find_optimal_threshold_pair(
        y_true, y_scores, thresholds, amounts, fn_multiplier=1.15, fp_multiplier=0.02, cost_per_review=5.0
    )
    assert optimal["lower_threshold"] <= optimal["upper_threshold"]
    assert "total_cost" in optimal
