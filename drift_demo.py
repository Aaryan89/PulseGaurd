import sys
import io
import os
import pandas as pd
from datetime import datetime, timedelta

if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.append(os.path.join(os.path.dirname(__file__), "backend"))
from backend.detector import detect, DetectionConfig
from data.generator import MerchantSimulator

def demonstrate_drift():
    print("Generating synthetic data for Concept Drift (Legitimate Growth)...")
    simulator = MerchantSimulator("M_DRIFT", "medium")
    
    # Generate 14 days of data.
    # First 7 days: baseline.
    # Next 7 days: gradual legitimate growth (4x volume by end).
    start_date = datetime.now() - timedelta(days=14)
    txns = []
    
    total_hours = 14 * 24
    for h in range(total_hours):
        current_time = start_date + timedelta(hours=h)
        if h < 7 * 24:
            txns.extend(simulator.generate_baseline_hour(current_time))
        else:
            progress = (h - 7 * 24) / (7 * 24)
            txns.extend(simulator.generate_anomaly_hour(current_time, 'legitimate_growth', progress))
            
    df = pd.DataFrame(txns)
    df = df.sort_values('timestamp').reset_index(drop=True)
    print(f"Generated {len(df)} transactions over 14 days.")
    
    # 1. Run with Fixed Baseline
    print("\n--- 1. Fixed Baseline (Default) ---")
    config_fixed = DetectionConfig(rolling_rebaseline=False)
    res_fixed = detect(df, config_fixed)
    
    # Count how many of the flagged windows were in the "growth" period (false positives)
    growth_start = start_date + timedelta(days=7)
    fp_fixed = sum(1 for fw in res_fixed.flagged_windows if fw['timestamp'] >= growth_start)
    print(f"False Positive Windows (flagged legitimate growth): {fp_fixed}")
    
    # 2. Run with Rolling Re-baseline
    print("\n--- 2. Rolling Re-baseline ---")
    # We use a rolling window to adapt the baseline, and increase cusum_drift 
    # to absorb gradual sustained changes (z-scores < 1.5) without accumulating,
    # while still catching sudden spikes (z-scores >> 1.5).
    config_rolling = DetectionConfig(
        rolling_rebaseline=True, 
        rolling_rebaseline_window=24*3, # 3 day window
        cusum_drift=1.5
    )
    res_rolling = detect(df, config_rolling)
    
    fp_rolling = sum(1 for fw in res_rolling.flagged_windows if fw['timestamp'] >= growth_start)
    print(f"False Positive Windows (flagged legitimate growth): {fp_rolling}")
    
    print("\nConclusion:")
    print(f"Fixed baseline generated {fp_fixed} false alarms due to legitimate business growth.")
    print(f"Rolling baseline adapted to the growth and reduced false alarms to {fp_rolling} ({(fp_fixed - fp_rolling)/fp_fixed*100:.1f}% reduction).")

if __name__ == "__main__":
    demonstrate_drift()
