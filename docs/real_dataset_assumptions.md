# Real Dataset Adaptation Assumptions

This project uses the Kaggle "Credit Card Fraud Detection" dataset (anonymized European cardholder transactions) to benchmark the generalization of our anomaly-scoring approach on real-world data.

## Limitations and Adaptations

Our synthetic dataset is explicitly designed to simulate merchant-level regime breaks (e.g., card testing spikes, volume surges). Real public datasets like the Kaggle dataset present several structural differences that require adaptation:

1. **Lack of Merchant IDs:** The Kaggle dataset does not provide merchant identifiers. To run our merchant-level two-stage pipeline, we treat the entire dataset as a single "global" merchant. This violates the core design of per-merchant baselining, meaning the EWMA/CUSUM stage is tracking global volume rather than merchant-specific behavior.

2. **Time Feature:** The `Time` feature in the dataset is the number of seconds elapsed between the transaction and the first transaction. We map this to a synthetic `timestamp` starting from an arbitrary date (e.g., 2023-01-01) to satisfy our pipeline's time-series requirements.

3. **Feature Space:** Our Stage 2 Isolation Forest in the synthetic pipeline uses raw features (Amount, etc.). The Kaggle dataset contains 28 PCA-transformed features (`V1` to `V28`) alongside `Amount`. We feed these PCA features into the Isolation Forest, which means the model is scoring based on a fundamentally different (and pre-processed) feature space than our synthetic implementation.

4. **Cost Model Mappings:** The Kaggle dataset contains real EUR amounts (converted to USD typically). Since our cost model is localized to INR, we use illustrative cost multipliers (e.g., assuming `Amount` represents INR directly or applying a fixed conversion) for benchmarking purposes. We apply the same 1.15 false-negative multiplier and 0.02 false-positive multiplier.

## Conclusion

This validation demonstrates whether our two-stage architecture (volume-based pre-filtering followed by multivariate isolation) can successfully generalize to score anomalies in a completely different, real-world feature space. It does **not** prove that the Kaggle dataset exhibits the exact merchant-level regime breaks our pipeline was optimized for.
