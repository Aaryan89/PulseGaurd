import pandas as pd
from typing import List

def detect_naive(df: pd.DataFrame) -> List[float]:
    """
    A deliberately naive baseline detector that uses the raw transaction amount
    as the anomaly score.
    
    This simulates a simple "flag if amount > global threshold" approach.
    By returning the raw amount, the cost model can sweep over amounts to find
    the optimal global threshold.
    
    Args:
        df: DataFrame containing transaction data with an 'amount' column.
        
    Returns:
        List of continuous scores (raw amounts).
    """
    return df['amount'].tolist()
