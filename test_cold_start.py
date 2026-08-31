import sys
import pandas as pd
from data.generator import generate_dataset
from backend.detector import detect, DetectionConfig

def evaluate_new_merchant():
    # 1. Generate data with a new merchant
    df = generate_dataset(num_merchants=5, days=15)
    df['created_at'] = pd.to_datetime(df['created_at'])
    
    # Identify the new merchant
    new_merchant_id = [m for m in df['merchant_id'].unique() if "NEW" in m][0]
    new_m_df = df[df['merchant_id'] == new_merchant_id]
    
    print(f"New merchant {new_merchant_id} has {len(new_m_df)} total transactions.")
    total_anomalies = new_m_df['is_anomaly'].sum()
    print(f"True anomalies injected: {total_anomalies}")
    
    # Get tier priors
    merchant_vols = df.groupby('merchant_id').size()
    q33, q67 = merchant_vols.quantile([0.33, 0.67])
    def get_tier(vol):
        if vol <= q33: return "Low Volume"
        if vol <= q67: return "Medium Volume"
        return "High Volume"
        
    df['merchant_tier'] = df['merchant_id'].map(merchant_vols.apply(get_tier))
    
    tier_priors_map = {}
    for tier in ["Low Volume", "Medium Volume", "High Volume"]:
        tier_df = df[df['merchant_tier'] == tier].copy()
        if tier_df.empty: continue
        tier_df['time_diff'] = tier_df.groupby('merchant_id')['created_at'].diff().dt.total_seconds().fillna(0)
        t_agg = tier_df.set_index('created_at').resample('1h').agg(
            volume=('id', 'count'), ticket_size=('amount', 'mean'), velocity=('time_diff', 'mean')
        ).fillna(0)
        t_agg['volume'] = t_agg['volume'] / tier_df['merchant_id'].nunique()
        tier_priors_map[tier] = {
            'volume': {'mean': t_agg['volume'].mean(), 'std': t_agg['volume'].std()},
            'ticket_size': {'mean': t_agg['ticket_size'].mean(), 'std': t_agg['ticket_size'].std()},
            'velocity': {'mean': t_agg['velocity'].mean(), 'std': t_agg['velocity'].std()}
        }
    new_m_df = df[df['merchant_id'] == new_merchant_id].copy()
    tier = new_m_df['merchant_tier'].iloc[0]
    
    # 2. Run detection WITHOUT tier priors (Before)
    config_before = DetectionConfig()
    config_before.tier_priors = None # No priors
    res_before = detect(new_m_df, config_before)
    
    flagged_txns_before = res_before.flagged_transactions
    flagged_ids_before = {t['id'] for t in flagged_txns_before}
    
    tp_before = new_m_df[new_m_df['id'].isin(flagged_ids_before)]['is_anomaly'].sum()
    fp_before = len(flagged_txns_before) - tp_before
    fn_before = total_anomalies - tp_before
    
    print("\n--- BEFORE (No Priors) ---")
    print(f"Flagged total: {len(flagged_txns_before)}")
    print(f"True Positives: {tp_before}")
    print(f"False Positives: {fp_before}")
    print(f"Missed Detections (FN): {fn_before}")
    
    # 3. Run detection WITH tier priors (After)
    config_after = DetectionConfig()
    config_after.tier_priors = tier_priors_map[tier]
    res_after = detect(new_m_df, config_after)
    
    flagged_txns_after = res_after.flagged_transactions
    flagged_ids_after = {t['id'] for t in flagged_txns_after}
    
    tp_after = new_m_df[new_m_df['id'].isin(flagged_ids_after)]['is_anomaly'].sum()
    fp_after = len(flagged_txns_after) - tp_after
    fn_after = total_anomalies - tp_after
    
    print("\n--- AFTER (With Tier Priors) ---")
    print(f"Flagged total: {len(flagged_txns_after)}")
    print(f"True Positives: {tp_after}")
    print(f"False Positives: {fp_after}")
    print(f"Missed Detections (FN): {fn_after}")

if __name__ == "__main__":
    evaluate_new_merchant()
