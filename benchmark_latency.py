import os
import sys
import time
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

sys.path.append(os.path.join(os.path.dirname(__file__), "backend"))
from backend.detector import detect, DetectionConfig
from data.generator import MerchantSimulator

def benchmark_latency():
    print("Preparing latency benchmark...")
    # Generate 1 week of baseline data for a medium merchant to fit the pipeline state
    simulator = MerchantSimulator("M_BENCH", "medium")
    start_date = datetime.now() - timedelta(days=7)
    
    baseline_txns = []
    for i in range(7 * 24):
        baseline_txns.extend(simulator.generate_baseline_hour(start_date + timedelta(hours=i)))
        
    df_baseline = pd.DataFrame(baseline_txns)
    df_baseline = df_baseline.sort_values(by='timestamp').reset_index(drop=True)
    
    config = DetectionConfig()
    
    print("--- Single Transaction Latency ---")
    single_latencies = []
    
    # Pre-warm the pipeline (in reality, state would be held in memory)
    # We will measure the time it takes to process the baseline + 1 new transaction
    # Since our `detect` function processes a dataframe all at once, 
    # to simulate streaming latency, we just pass the historical window + 1 txn.
    # Note: A real streaming system would hold the EWMA state and IF model in memory,
    # so we measure the overhead of running `detect` on a small window.
    # To be fair to the architecture, let's measure processing a 24-hour window + 1 txn.
    
    # However, `detect` fits the IF model from scratch if a window is flagged.
    # Let's measure the "happy path" (no stage 2) and "flagged path" (stage 2).
    
    window_df = df_baseline.tail(2000).copy() # roughly a few days of txns
    
    # 1. Happy path (Stage 1 only)
    for _ in range(50):
        new_txn = simulator.generate_baseline_hour(datetime.now())[0]
        test_df = pd.concat([window_df, pd.DataFrame([new_txn])], ignore_index=True)
        
        t0 = time.perf_counter()
        _ = detect(test_df, config)
        t1 = time.perf_counter()
        single_latencies.append((t1 - t0) * 1000) # ms
        
    p50_single = np.percentile(single_latencies, 50)
    p95_single = np.percentile(single_latencies, 95)
    p99_single = np.percentile(single_latencies, 99)
    
    print(f"Single Txn (Stage 1 only): p50={p50_single:.2f}ms, p95={p95_single:.2f}ms, p99={p99_single:.2f}ms")
    
    # 2. Flagged path (Stage 1 + Stage 2)
    flagged_latencies = []
    for _ in range(20):
        new_txns = simulator.generate_anomaly_hour(datetime.now(), 'volume_spike')
        test_df = pd.concat([window_df, pd.DataFrame(new_txns)], ignore_index=True)
        
        t0 = time.perf_counter()
        _ = detect(test_df, config)
        t1 = time.perf_counter()
        flagged_latencies.append((t1 - t0) * 1000)
        
    p50_flag = np.percentile(flagged_latencies, 50)
    p95_flag = np.percentile(flagged_latencies, 95)
    p99_flag = np.percentile(flagged_latencies, 99)
    print(f"Batch/Flagged (Stage 1+2 on anomalous hour): p50={p50_flag:.2f}ms, p95={p95_flag:.2f}ms, p99={p99_flag:.2f}ms")

if __name__ == "__main__":
    benchmark_latency()
