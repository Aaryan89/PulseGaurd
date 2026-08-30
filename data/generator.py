import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random
from typing import List, Dict, Any
import os

class MerchantSimulator:
    """
    Simulates transaction streams for a single merchant, capturing their 
    baseline behavior and specific regime-break anomalies.
    """
    def __init__(self, merchant_id: str, tier: str):
        self.merchant_id = merchant_id
        self.tier = tier
        
        # We parameterize behavior based on merchant tier
        if tier == 'small':
            self.base_lambda = 5  # average txns per hour
            self.mu_log = 6.2     # log mean of amount (~₹490)
            self.sigma_log = 0.8  # variance of amount
            self.payment_mix = {'credit_card': 0.4, 'debit_card': 0.3, 'upi': 0.3}
            self.geo_mix = {'domestic': 0.95, 'international': 0.05}
        elif tier == 'medium':
            self.base_lambda = 40
            self.mu_log = 7.3     # log mean (~₹1480)
            self.sigma_log = 1.0
            self.payment_mix = {'credit_card': 0.6, 'debit_card': 0.2, 'upi': 0.2}
            self.geo_mix = {'domestic': 0.85, 'international': 0.15}
        else: # large
            self.base_lambda = 200
            self.mu_log = 8.0     # log mean (~₹2980)
            self.sigma_log = 1.2
            self.payment_mix = {'credit_card': 0.7, 'debit_card': 0.1, 'upi': 0.1, 'netbanking': 0.1}
            self.geo_mix = {'domestic': 0.70, 'international': 0.30}

    def generate_baseline_hour(self, timestamp: datetime) -> List[Dict[str, Any]]:
        n_txns = np.random.poisson(self.base_lambda)
        return self._generate_transactions(n_txns, timestamp, is_anomaly=False, anomaly_type='none')

    def generate_anomaly_hour(self, timestamp: datetime, anomaly_type: str, progress: float = 0.0) -> List[Dict[str, Any]]:
        if anomaly_type == 'legitimate_growth':
            # Gradual ramp up: progress is from 0.0 to 1.0
            # By the end, volume is 4x higher
            current_lambda = self.base_lambda * (1 + 3 * progress)
            n_txns = np.random.poisson(current_lambda)
            return self._generate_transactions(n_txns, timestamp, is_anomaly=False, anomaly_type='none')
            
        elif anomaly_type == 'volume_spike':
            # Sudden burst in volume, maintaining normal characteristics
            n_txns = np.random.poisson(self.base_lambda * 6)
            return self._generate_transactions(n_txns, timestamp, is_anomaly=True, anomaly_type='volume_spike')
            
        elif anomaly_type == 'card_testing':
            # Normal baseline volume plus a burst of tiny credit card transactions
            n_txns = np.random.poisson(self.base_lambda)
            normal_txns = self._generate_transactions(n_txns, timestamp, is_anomaly=False, anomaly_type='none')
            
            burst_size = np.random.poisson(self.base_lambda * 4)
            burst_txns = []
            for _ in range(burst_size):
                burst_txns.append({
                    'transaction_id': f"tx_{random.randint(10000000, 99999999)}",
                    'merchant_id': self.merchant_id,
                    'timestamp': timestamp + timedelta(minutes=random.uniform(0, 59), seconds=random.uniform(0, 59)),
                    'amount': round(random.uniform(50.0, 150.0), 2), # Card testing amounts in INR (₹50 - ₹150)
                    'payment_method': 'credit_card',
                    'location': 'international', # Often cross-border
                    'is_anomaly': True,
                    'anomaly_type': 'card_testing'
                })
            return normal_txns + burst_txns
            
        elif anomaly_type == 'geo_shift':
            # Complete shift to international transactions without major volume change
            n_txns = np.random.poisson(self.base_lambda)
            txns = []
            for _ in range(n_txns):
                txns.append({
                    'transaction_id': f"tx_{random.randint(10000000, 99999999)}",
                    'merchant_id': self.merchant_id,
                    'timestamp': timestamp + timedelta(minutes=random.uniform(0, 59), seconds=random.uniform(0, 59)),
                    'amount': round(np.random.lognormal(self.mu_log, self.sigma_log), 2),
                    'payment_method': np.random.choice(list(self.payment_mix.keys()), p=list(self.payment_mix.values())),
                    'location': 'international', # Forced shift
                    'is_anomaly': True,
                    'anomaly_type': 'geo_shift'
                })
            return txns
            
        return self.generate_baseline_hour(timestamp)

    def _generate_transactions(self, n_txns: int, base_time: datetime, is_anomaly: bool, anomaly_type: str) -> List[Dict[str, Any]]:
        txns = []
        for _ in range(n_txns):
            txns.append({
                'transaction_id': f"tx_{random.randint(10000000, 99999999)}",
                'merchant_id': self.merchant_id,
                'timestamp': base_time + timedelta(minutes=random.uniform(0, 59), seconds=random.uniform(0, 59)),
                'amount': round(np.random.lognormal(self.mu_log, self.sigma_log), 2),
                'payment_method': np.random.choice(list(self.payment_mix.keys()), p=list(self.payment_mix.values())),
                'location': np.random.choice(list(self.geo_mix.keys()), p=list(self.geo_mix.values())),
                'is_anomaly': is_anomaly,
                'anomaly_type': anomaly_type
            })
        return txns

def generate_dataset(num_merchants: int = 10, days: int = 30) -> pd.DataFrame:
    """
    Generate a full dataset spanning multiple merchants over a time period,
    injecting anomalies at random intervals.
    """
    np.random.seed(42)
    random.seed(42)
    
    merchants = []
    tiers = ['small', 'medium', 'large']
    for i in range(num_merchants):
        tier = np.random.choice(tiers, p=[0.7, 0.2, 0.1])
        m = MerchantSimulator(f"M_{i+1:03d}", tier)
        # Make the last merchant a cold-start example
        if i == num_merchants - 1:
            m.is_new_merchant = True
            m.merchant_id = f"{m.merchant_id}_NEW"
        merchants.append(m)
        
    start_date = datetime.now() - timedelta(days=days)
    all_transactions = []
    
    total_hours = days * 24
    anomaly_schedule = {}
    
    for m in merchants:
        # Roughly 1.5% of hours have an anomaly for a given merchant
        anomaly_hours = np.random.choice(total_hours, size=int(total_hours * 0.015), replace=False)
        anomaly_types = np.random.choice(['volume_spike', 'card_testing', 'geo_shift'], size=len(anomaly_hours))
        anomaly_schedule[m.merchant_id] = dict(zip(anomaly_hours, anomaly_types))
        
    for hour_offset in range(total_hours):
        current_time = start_date + timedelta(hours=hour_offset)
        
        for m in merchants:
            # If it's the cold start merchant, skip generating data until the last 1.5 days (36 hours)
            if hasattr(m, 'is_new_merchant') and m.is_new_merchant:
                if hour_offset < total_hours - 36:
                    continue
                    
            if hour_offset in anomaly_schedule[m.merchant_id]:
                anomaly_type = anomaly_schedule[m.merchant_id][hour_offset]
                txns = m.generate_anomaly_hour(current_time, anomaly_type)
            else:
                txns = m.generate_baseline_hour(current_time)
                
            all_transactions.extend(txns)
            
    df = pd.DataFrame(all_transactions)
    df = df.sort_values(by='timestamp').reset_index(drop=True)
    return df

if __name__ == "__main__":
    print("Generating synthetic dataset (30 days, 10 merchants)...")
    df = generate_dataset(num_merchants=10, days=30)
    
    output_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(output_dir, "synthetic_transactions.csv")
    
    df.to_csv(output_path, index=False)
    print(f"Generated {len(df)} transactions.")
    print(f"Saved to {output_path}")
    print("\nAnomaly Breakdown:")
    print(df['anomaly_type'].value_counts())
