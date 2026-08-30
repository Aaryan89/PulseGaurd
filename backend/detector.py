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
    
    # Cold Start Configuration
    cold_start_threshold: int = 48 # Number of periods (e.g. hours) before merchant fully owns baseline
    cold_start_blend_rate: float = 1.0 # Exponent for blending: 1.0 is linear, <1.0 blends faster
    tier_priors: Dict[str, Dict[str, float]] = field(default_factory=dict) # Prior mean/std by signal

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
            
        mean_arr = np.zeros(len(series))
        std_arr = np.zeros(len(series))
        
        prior_mean = config.tier_priors.get(signal, {}).get('mean', 0.0) if config.tier_priors else 0.0
        prior_std = config.tier_priors.get(signal, {}).get('std', 1.0) if config.tier_priors else 1.0
        
        for i in range(len(series)):
            hist = series.iloc[:i]
            n = len(hist)
            
            if n < 2:
                own_mean, own_std = 0.0, 1.0
            else:
                if config.rolling_rebaseline and n > config.rolling_rebaseline_window:
                    own_mean = hist.iloc[-config.rolling_rebaseline_window:].mean()
                    own_std = hist.iloc[-config.rolling_rebaseline_window:].std()
                else:
                    own_mean = hist.mean()
                    own_std = hist.std()
                    
            if pd.isna(own_std) or own_std == 0:
                own_std = 1.0
                
            if n >= config.cold_start_threshold:
                alpha = 1.0
            else:
                alpha = (n / config.cold_start_threshold) ** config.cold_start_blend_rate
                
            if config.tier_priors and signal in config.tier_priors:
                mean_arr[i] = alpha * own_mean + (1 - alpha) * prior_mean
                std_arr[i] = alpha * own_std + (1 - alpha) * prior_std
            else:
                if n < 2:
                    mean_arr[i] = series.iloc[i]
                    std_arr[i] = 1.0
                else:
                    mean_arr[i] = own_mean
                    std_arr[i] = own_std
                    
        mean = pd.Series(mean_arr, index=series.index)
        std = pd.Series(std_arr, index=series.index)
        
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
        
        start_idx = 0 if (config.tier_priors and signal in config.tier_priors) else config.burn_in_periods
        for i in range(start_idx, len(series)):
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
                
                # Pragmatic fallback for explainability: computing z-scores against merchant baseline
                # Using SHAP with IsolationForest inside a ColumnTransformer pipeline can be fiddly
                # (mapping one-hot encoded features back to originals) and potentially slow.
                # Here we use standard deviations from the historical (unflagged) mean.
                
                # Calculate baselines for numerical features
                baselines = {}
                for num_feat in config.num_features:
                    mean_val = baseline_df[num_feat].mean()
                    std_val = baseline_df[num_feat].std()
                    if pd.isna(std_val) or std_val == 0:
                        std_val = 1e-5
                    baselines[num_feat] = {'mean': mean_val, 'std': std_val}

                # Calculate baselines for categorical features
                cat_baselines = {}
                for cat_feat in config.cat_features:
                    cat_baselines[cat_feat] = baseline_df[cat_feat].value_counts(normalize=True)

                for idx, (_, txn) in enumerate(flagged_df.iterrows()):
                    score = float(scores[idx])
                    
                    # Generate explanation drivers
                    drivers = []
                    for num_feat in config.num_features:
                        b = baselines[num_feat]
                        dev = (txn[num_feat] - b['mean']) / b['std']
                        if abs(dev) > 2.0:
                            drivers.append(f"{num_feat} ({dev:+.1f}σ from baseline)")
                    
                    # Add categorical drivers if they were rare in baseline
                    for cat_feat in config.cat_features:
                        cat_val = txn[cat_feat]
                        freq = cat_baselines[cat_feat].get(cat_val, 0)
                        if freq < 0.05:
                            drivers.append(f"unfamiliar {cat_feat} ('{cat_val}')")
                            
                    driver_str = ", ".join(drivers) if drivers else "complex multi-feature anomaly"
                    reason = f"Isolation forest anomaly score {score:.2f}. Primary drivers: {driver_str}."
                    
                    flagged_transactions.append({
                        'transaction_id': txn['transaction_id'],
                        'score': score,
                        'window': txn['timestamp'].floor(config.window_freq),
                        'reason': reason
                    })
                    
    return DetectionResult(
        flagged_windows=flagged_windows,
        flagged_transactions=flagged_transactions,
        audit_log=audit_log
    )
