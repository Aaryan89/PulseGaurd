import pytest
from data.generator import generate_dataset

def test_generate_dataset_schema_and_labels():
    df = generate_dataset(num_merchants=2, days=2)
    
    # 1. Schema check
    expected_cols = {
        'transaction_id', 'merchant_id', 'timestamp', 'amount', 
        'payment_method', 'location', 'is_anomaly', 'anomaly_type'
    }
    assert set(df.columns) == expected_cols, "Generated dataframe is missing expected columns"
    
    # 2. Check types
    assert df['is_anomaly'].dtype == bool, "is_anomaly should be a boolean"
    assert df['amount'].dtype == float, "amount should be float"
    
    # 3. Check labels alignment
    anomalies_by_flag = df[df['is_anomaly'] == True]
    anomalies_by_type = df[df['anomaly_type'] != 'none']
    
    assert len(anomalies_by_flag) == len(anomalies_by_type), "is_anomaly and anomaly_type mismatch"
    if not anomalies_by_flag.empty:
        assert (anomalies_by_flag['anomaly_type'] != 'none').all(), "Flagged anomalies must have a type"
