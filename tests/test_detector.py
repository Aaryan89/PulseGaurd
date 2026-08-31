import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from backend.detector import detect, DetectionConfig

def test_ewma_cusum_flat_vs_spike():
    # Generate flat data
    start_time = datetime(2026, 1, 1)
    flat_data = []
    for i in range(100):
        flat_data.append({
            "created_at": start_time + timedelta(hours=i),
            "id": f"tx_{i}",
            "amount": 100.0,
            "method": "card",
            "location": "US"
        })
        
    df_flat = pd.DataFrame(flat_data)
    config = DetectionConfig(burn_in_periods=24)
    res_flat = detect(df_flat, config)
    assert len(res_flat.flagged_windows) == 0, "Flat data should not trigger EWMA/CUSUM"
    
    # Generate spike data
    spike_data = list(flat_data)
    # Add a huge volume spike at hour 50
    for i in range(100):
        spike_data.append({
            "created_at": start_time + timedelta(hours=50, minutes=i%60),
            "id": f"tx_spike_{i}",
            "amount": 100.0,
            "method": "card",
            "location": "US"
        })
        
    df_spike = pd.DataFrame(spike_data)
    res_spike = detect(df_spike, config)
    assert len(res_spike.flagged_windows) > 0, "Spike data should trigger EWMA/CUSUM"
    
    # Verify isolation forest scores
    assert len(res_spike.flagged_transactions) > 0, "Spike data should trigger IF"
    scores = [t['score'] for t in res_spike.flagged_transactions]
    assert all(isinstance(s, float) for s in scores)
    
def test_cold_start_onboarding():
    # 5 hours of data
    start_time = datetime(2026, 1, 1)
    data = []
    for i in range(10):
        data.append({
            "created_at": start_time + timedelta(hours=i//2), # 2 txns per hour
            "id": f"tx_{i}",
            "amount": 100.0,
            "method": "card",
            "location": "US"
        })
    df = pd.DataFrame(data)
    
    # 1. No priors -> burn_in skips
    config_no_priors = DetectionConfig(burn_in_periods=24, cold_start_threshold=48)
    config_no_priors.tier_priors = None
    res_no = detect(df, config_no_priors)
    assert len(res_no.flagged_windows) == 0 # Skipped due to burn-in
    
    # 2. With priors -> starts immediately
    config_priors = DetectionConfig(burn_in_periods=24, cold_start_threshold=48)
    config_priors.tier_priors = {
        'volume': {'mean': 100.0, 'std': 1.0}, # Prior says expect 100 txns/hr
        'ticket_size': {'mean': 100.0, 'std': 1.0},
        'velocity': {'mean': 3600.0, 'std': 1.0}
    }
    res_priors = detect(df, config_priors)
    # Since actual volume is 2, and prior is 100, this should heavily trigger EWMA Low or CUSUM Low
    assert len(res_priors.flagged_windows) > 0, "Prior mismatch should trigger immediate flags"
