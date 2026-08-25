import numpy as np

def calculate_cost(
    true_positives: int,
    false_positives: int,
    false_negatives: int,
    true_negatives: int = 0,
    cost_per_fn: float = 100.0,
    cost_per_fp: float = 50.0,
    cost_per_tp: float = 0.0,
    cost_per_tn: float = 0.0
) -> float:
    """
    Calculate the total business cost of a fraud detection model's performance
    using flat dollar costs.
    
    Args:
        true_positives: Number of correctly flagged fraud transactions.
        false_positives: Number of incorrectly flagged legitimate transactions (false alarms).
        false_negatives: Number of missed fraud transactions.
        true_negatives: Number of correctly allowed legitimate transactions.
        cost_per_fn: Flat cost of a missed fraud spike.
        cost_per_fp: Flat cost of a false positive.
        cost_per_tp: Cost associated with a true positive.
        cost_per_tn: Cost associated with a true negative.
        
    Returns:
        float: The total cost in dollars.
    """
    return (
        true_positives * cost_per_tp +
        false_positives * cost_per_fp +
        false_negatives * cost_per_fn +
        true_negatives * cost_per_tn
    )

def evaluate_threshold_costs(
    y_true: list[int],
    y_scores: list[float],
    thresholds: list[float],
    amounts: list[float],
    fn_multiplier: float = 1.15,
    fp_multiplier: float = 0.02
) -> list[dict]:
    """
    Evaluate the cost model across different operating thresholds using amount-weighted costs.
    
    Args:
        y_true: Ground truth binary labels (1 for fraud, 0 for legitimate).
        y_scores: Continuous anomaly scores or probabilities from the model.
        thresholds: List of thresholds to evaluate.
        amounts: List of transaction amounts aligned with y_true and y_scores.
        fn_multiplier: Multiplier for false negatives (e.g., 1.0 + chargeback fee percentage).
        fp_multiplier: Multiplier for false positives (e.g., customer LTV risk percentage).
        
    Returns:
        List of dictionaries containing threshold, confusion matrix, total cost, and metrics.
    """
    y_true_arr = np.array(y_true)
    y_scores_arr = np.array(y_scores)
    thresh_arr = np.array(thresholds)
    amounts_arr = np.array(amounts)
    
    preds = y_scores_arr >= thresh_arr[:, np.newaxis]
    
    is_positive = (y_true_arr == 1)
    is_negative = (y_true_arr == 0)
    
    tp_mask = preds & is_positive
    fp_mask = preds & is_negative
    fn_mask = (~preds) & is_positive
    tn_mask = (~preds) & is_negative
    
    tp_counts = tp_mask.sum(axis=1)
    fp_counts = fp_mask.sum(axis=1)
    fn_counts = fn_mask.sum(axis=1)
    tn_counts = tn_mask.sum(axis=1)
    
    fn_costs = fn_mask * (amounts_arr * fn_multiplier)
    fp_costs = fp_mask * (amounts_arr * fp_multiplier)
    
    total_costs = fn_costs.sum(axis=1) + fp_costs.sum(axis=1)
    
    precision = np.divide(
        tp_counts, 
        (tp_counts + fp_counts), 
        out=np.zeros_like(tp_counts, dtype=float), 
        where=(tp_counts + fp_counts) != 0
    )
    recall = np.divide(
        tp_counts, 
        (tp_counts + fn_counts), 
        out=np.zeros_like(tp_counts, dtype=float), 
        where=(tp_counts + fn_counts) != 0
    )
    f1 = np.divide(
        2 * precision * recall, 
        (precision + recall), 
        out=np.zeros_like(precision, dtype=float), 
        where=(precision + recall) != 0
    )
    
    results = []
    for i in range(len(thresh_arr)):
        results.append({
            "threshold": float(thresh_arr[i]),
            "tp": int(tp_counts[i]),
            "fp": int(fp_counts[i]),
            "fn": int(fn_counts[i]),
            "tn": int(tn_counts[i]),
            "total_cost": float(total_costs[i]),
            "precision": float(precision[i]),
            "recall": float(recall[i]),
            "f1": float(f1[i])
        })
        
    return results

def find_optimal_threshold(
    y_true: list[int],
    y_scores: list[float],
    thresholds: list[float],
    amounts: list[float],
    fn_multiplier: float = 1.15,
    fp_multiplier: float = 0.02
) -> dict:
    """
    Finds the threshold that yields the minimum total cost.
    
    Args:
        y_true: Ground truth binary labels.
        y_scores: Continuous anomaly scores or probabilities.
        thresholds: List of thresholds to evaluate.
        amounts: List of transaction amounts.
        fn_multiplier: Multiplier for false negatives.
        fp_multiplier: Multiplier for false positives.
        
    Returns:
        Dictionary representing the best operating point (minimum cost).
    """
    results = evaluate_threshold_costs(
        y_true, y_scores, thresholds, amounts, fn_multiplier, fp_multiplier
    )
    return min(results, key=lambda x: x["total_cost"])

def bootstrap_cost_estimate(
    y_true: list[int],
    y_scores: list[float],
    amounts: list[float],
    threshold: float = None,
    thresholds: list[float] = None,
    fn_multiplier: float = 1.15,
    fp_multiplier: float = 0.02,
    n_bootstrap: int = 200
) -> dict:
    """
    Computes a confidence interval for the expected cost via bootstrapping.
    
    This function resamples the dataset with replacement to provide a limitation-aware
    statement about the expected cost (e.g., "expected cost: X, with a 90% CI of [Y, Z]")
    rather than relying on a single deterministic point estimate that could be fragile.
    
    Args:
        y_true: Ground truth binary labels.
        y_scores: Continuous anomaly scores or probabilities.
        amounts: List of transaction amounts.
        threshold: A specific operating threshold to evaluate. If None, thresholds must be provided.
        thresholds: A list of thresholds to find the optimal one if threshold is None.
        fn_multiplier: Multiplier for false negatives.
        fp_multiplier: Multiplier for false positives.
        n_bootstrap: Number of bootstrap iterations.
        
    Returns:
        Dictionary containing the mean cost and the 90% confidence interval (5th and 95th percentiles).
    """
    if threshold is None:
        if thresholds is None:
            raise ValueError("Must provide either a specific threshold or a list of thresholds to find the optimal one.")
        optimal = find_optimal_threshold(
            y_true, y_scores, thresholds, amounts, fn_multiplier, fp_multiplier
        )
        threshold = optimal["threshold"]
        
    y_true_arr = np.array(y_true)
    y_scores_arr = np.array(y_scores)
    amounts_arr = np.array(amounts)
    n_samples = len(y_true_arr)
    
    costs = []
    for _ in range(n_bootstrap):
        indices = np.random.choice(n_samples, size=n_samples, replace=True)
        
        sample_res = evaluate_threshold_costs(
            y_true=y_true_arr[indices].tolist(),
            y_scores=y_scores_arr[indices].tolist(),
            thresholds=[threshold],
            amounts=amounts_arr[indices].tolist(),
            fn_multiplier=fn_multiplier,
            fp_multiplier=fp_multiplier
        )
        costs.append(sample_res[0]["total_cost"])
        
    costs_arr = np.array(costs)
    
    return {
        "threshold": threshold,
        "mean_cost": float(np.mean(costs_arr)),
        "ci_lower_90": float(np.percentile(costs_arr, 5)),
        "ci_upper_90": float(np.percentile(costs_arr, 95)),
        "n_bootstrap": n_bootstrap
    }
