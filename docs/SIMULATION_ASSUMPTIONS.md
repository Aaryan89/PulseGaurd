# Simulation Assumptions

This document outlines the statistical and behavioral assumptions used to generate synthetic transaction data for PulseGuard. Because we evaluate on cost and regime breaks rather than static per-transaction thresholds, it is critical that our baseline behavior resembles reality.

## 1. Merchant Baselines
We model merchants as distinct entities, each with a stable, characteristic baseline behavior.
- **Transaction Arrivals**: The number of transactions per hour follows a **Poisson distribution** ($\lambda$). Different merchant tiers have different $\lambda$ values (e.g., small merchants have $\lambda=5$/hr, large merchants have $\lambda=500$/hr).
- **Ticket Size**: Transaction amounts follow a **Log-Normal distribution**. This correctly captures the right-skewed nature of financial transactions, where most transactions are close to a typical average (e.g., $20-$50), but there is a long tail of very large legitimate purchases. We parameterize this using $\mu$ and $\sigma$ for each merchant.
- **Payment Mix**: Each merchant has a fixed probability distribution over payment methods (e.g., Credit Card, Debit Card, UPI, NetBanking).
- **Geography Mix**: Each merchant has a characteristic distribution of transaction origins (e.g., 90% Domestic, 10% International).

## 2. Anomalies (Regime Breaks)
Anomalies are injected as temporary deviations from these baselines, reflecting specific real-world fraud patterns. Each anomaly type is assigned a boolean ground-truth label in the dataset.

- **Volume Spikes**:
  - *Mechanism*: A sudden multiplicative scaling of the Poisson arrival rate ($\lambda \times \text{spike\_factor}$) for a specific time window.
  - *Rationale*: Mimics a sudden rush of fraudulent transactions or a bot-driven checkout attack, distinct from organic viral traffic by its velocity and lack of corresponding geography/payment mix shifts.
  
- **Card Testing**:
  - *Mechanism*: A burst of high-frequency, extremely small transactions (amounts tightly clustered around $1.00 - $2.00) using a specific payment method (usually Credit Card).
  - *Rationale*: Fraudsters running stolen card numbers through a merchant's gateway to see which ones are valid before making larger purchases elsewhere.
  
- **Geographic Shifts**:
  - *Mechanism*: A sudden structural change in the geography mix (e.g., going from 1% International to 60% International) without necessarily changing the overall volume.
  - *Rationale*: Compromised merchant accounts or coordinated fraud rings operating from a new region.

## 3. Data Representation
The simulation runs over a defined period (e.g., 30 days) to allow regime-detection models (like EWMA or Isolation Forests on sliding windows) enough time to learn the baseline. 
The resulting dataset includes explicit timestamp, merchant_id, amount, payment_method, location, and a `is_anomaly` column which represents the absolute ground-truth for evaluation.
