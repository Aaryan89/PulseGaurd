"""
PulseGuard Detection Layer

This module implements a two-stage anomaly detection architecture for financial transaction streams.
The two-stage structure is a deliberate design choice optimized for cost and compute efficiency:
1. Stage 1 (Cheap Statistical Filter): Uses fast, lightweight statistical trackers (EWMA and CUSUM)
   to monitor aggregated hourly signals (volume, ticket size, velocity). It flags "regime breaks"
   where a merchant deviates from their own historical baseline.
2. Stage 2 (Expensive ML Model): Only runs within the specific time windows flagged by Stage 1.
   It uses an Isolation Forest to score individual transactions, isolating the exact anomalous
   events from the surrounding legitimate traffic.

This ensures we don't waste compute running complex multivariate ML models on perfectly normal
baseline traffic, which is critical for scaling to millions of merchants.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any
import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline

@dataclass
class DetectionConfig:
    window_freq: str = '1h'
    ewma_span: int = 24
    ewma_control_limit_std: float = 3.0
    cusum_threshold: float = 3.0
    cusum_drift: float = 0.5
    iforest_contamination: float = 0.1
    iforest_random_state: int = 42
    burn_in_periods: int = 24
    num_features: List[str] = field(default_factory=lambda: ['amount', 'hour_of_day', 'day_of_week'])
    cat_features: List[str] = field(default_factory=lambda: ['payment_method', 'location'])
    rolling_rebaseline: bool = False
    rolling_rebaseline_window: int = 168 # 1 week of hours

@dataclass
class DetectionResult:
    flagged_windows: List[Dict[str, Any]] = field(default_factory=list)
    flagged_transactions: List[Dict[str, Any]] = field(default_factory=list)
    audit_log: List[str] = field(default_factory=list)

def detect(merchant_transactions_df: pd.DataFrame, config: DetectionConfig = None) -> DetectionResult:
    """
    Runs the two-stage detection pipeline on a single merchant's transaction history.
    
    Args:
        merchant_transactions_df: DataFrame containing the merchant's transactions.
        config: Configuration parameters for the detectors.
        
    Returns:
        DetectionResult containing flagged windows, anomalous transactions, and the audit log.
    """
    if config is None:
        config = DetectionConfig()
        
    df = merchant_transactions_df.copy()
    if not np.issubdtype(df['timestamp'].dtype, np.datetime64):
        df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    df = df.sort_values('timestamp')
    if df.empty:
        return DetectionResult()
        
    df['time_diff'] = df['timestamp'].diff().dt.total_seconds().fillna(0)
    
    agg_df = df.set_index('timestamp').resample(config.window_freq).agg(
        volume=('transaction_id', 'count'),
        ticket_size=('amount', 'mean'),
        velocity=('time_diff', 'mean')
    )
    
    agg_df['ticket_size'] = agg_df['ticket_size'].ffill().fillna(0)
    agg_df['velocity'] = agg_df['velocity'].ffill().fillna(0)
    
    flagged_windows = []
    audit_log = []
    
    for signal in ['volume', 'ticket_size', 'velocity']:
        series = agg_df[signal]
        if len(series) < 2:
            continue
            
        if config.rolling_rebaseline:
            mean = series.rolling(window=config.rolling_rebaseline_window, min_periods=config.burn_in_periods).mean()
            std = series.rolling(window=config.rolling_rebaseline_window, min_periods=config.burn_in_periods).std().fillna(0)
        else:
            hist_mean = series.iloc[:config.burn_in_periods].mean()
            hist_std = series.iloc[:config.burn_in_periods].std()
            if pd.isna(hist_std) or hist_std == 0:
                hist_std = 1.0
                
            mean = pd.Series(hist_mean, index=series.index)
            std = pd.Series(hist_std, index=series.index)
            
        upper_limit = mean + config.ewma_control_limit_std * std
        lower_limit = mean - config.ewma_control_limit_std * std
        
        z_scores = (series - mean) / (std + 1e-5)
        
        cusum_pos = np.zeros(len(series))
        cusum_neg = np.zeros(len(series))
        
        for i in range(1, len(series)):
            cusum_pos[i] = max(0, cusum_pos[i-1] + z_scores.iloc[i] - config.cusum_drift)
            cusum_neg[i] = max(0, cusum_neg[i-1] - z_scores.iloc[i] - config.cusum_drift)
            
        ewma_upper_breach = series > upper_limit
        ewma_lower_breach = series < lower_limit
        cusum_pos_breach = cusum_pos > config.cusum_threshold
        cusum_neg_breach = cusum_neg > config.cusum_threshold
        
        for i in range(config.burn_in_periods, len(series)):
            ts = agg_df.index[i]
            val = series.iloc[i]
            if pd.isna(upper_limit.iloc[i]):
                continue
            
            if ewma_upper_breach.iloc[i]:
                margin = val - upper_limit.iloc[i]
                flagged_windows.append({"timestamp": ts, "signal": signal, "detector": "EWMA High", "margin": margin})
                audit_log.append(f"EWMA breach: {signal} value of {val:.2f} exceeded upper limit of {upper_limit.iloc[i]:.2f} by {margin:.2f} at {ts}")
                
            if ewma_lower_breach.iloc[i]:
                margin = lower_limit.iloc[i] - val
                flagged_windows.append({"timestamp": ts, "signal": signal, "detector": "EWMA Low", "margin": margin})
                audit_log.append(f"EWMA breach: {signal} value of {val:.2f} fell below lower limit of {lower_limit.iloc[i]:.2f} by {margin:.2f} at {ts}")
                
            if cusum_pos_breach[i]:
                margin = cusum_pos[i] - config.cusum_threshold
                flagged_windows.append({"timestamp": ts, "signal": signal, "detector": "CUSUM High", "margin": margin})
                audit_log.append(f"CUSUM breach: {signal} cumulative positive deviation of {cusum_pos[i]:.2f} exceeded threshold of {config.cusum_threshold} at {ts}")
                
            if cusum_neg_breach[i]:
                margin = cusum_neg[i] - config.cusum_threshold
                flagged_windows.append({"timestamp": ts, "signal": signal, "detector": "CUSUM Low", "margin": margin})
                audit_log.append(f"CUSUM breach: {signal} cumulative negative deviation of {cusum_neg[i]:.2f} exceeded threshold of {config.cusum_threshold} at {ts}")

    flagged_timestamps = set(fw['timestamp'] for fw in flagged_windows)
    
    flagged_transactions = []
    
    if flagged_timestamps and len(df) > 20:
        if 'hour_of_day' in config.num_features and 'hour_of_day' not in df.columns:
            df['hour_of_day'] = df['timestamp'].dt.hour
        if 'day_of_week' in config.num_features and 'day_of_week' not in df.columns:
            df['day_of_week'] = df['timestamp'].dt.dayofweek
            
        features = config.num_features + config.cat_features
        
        unflagged_mask = np.ones(len(df), dtype=bool)
        for ts in flagged_timestamps:
            window_start = ts
            window_end = ts + pd.Timedelta(config.window_freq)
            unflagged_mask &= ~((df['timestamp'] >= window_start) & (df['timestamp'] < window_end))
            
        baseline_df = df[unflagged_mask]
        
        if len(baseline_df) > 10:
            transformers = []
            if config.num_features:
                transformers.append(('num', StandardScaler(), config.num_features))
            if config.cat_features:
                transformers.append(('cat', OneHotEncoder(handle_unknown='ignore'), config.cat_features))
                
            preprocessor = ColumnTransformer(transformers=transformers)
                
            pipeline = Pipeline([
                ('preprocessor', preprocessor),
                ('model', IsolationForest(contamination=config.iforest_contamination, random_state=config.iforest_random_state))
            ])
            
            pipeline.fit(baseline_df[features])
            
            flagged_mask = ~unflagged_mask
            if flagged_mask.any():
                flagged_df = df[flagged_mask].copy()
                scores = -pipeline.decision_function(flagged_df[features])
                
                for idx, (_, txn) in enumerate(flagged_df.iterrows()):
                    flagged_transactions.append({
                        'transaction_id': txn['transaction_id'],
                        'score': float(scores[idx]),
                        'window': txn['timestamp'].floor(config.window_freq)
                    })
                    
    return DetectionResult(
        flagged_windows=flagged_windows,
        flagged_transactions=flagged_transactions,
        audit_log=audit_log
    )
