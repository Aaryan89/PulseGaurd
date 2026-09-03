# PulseGuard: Risk & Fraud Console

> A two-stage regime-break fraud detection engine and amount-weighted cost model for payment aggregators.

**The Headline:** Our two-stage detection and tiered cost model reduces expected operating costs by **75.0%** compared to a baseline of no detector, and **48.6%** compared to a naive static threshold.

### 🎥 Replay Mode Demo
<!-- ![Replay Mode Demo](./docs/replay-demo.gif) -->
*(A placeholder for your screen capture of Replay Mode is above!)*

### Quick Start
To spin up the entire application stack locally (including auto-generating 30 days of synthetic data):
```bash
docker-compose up --build
```
Open **`http://localhost:3000`**. 

*(For manual setup or testing the automated suite, see [TESTING.md](./TESTING.md))*

**Live Deployment:** [pulse-gaurd.vercel.app]

### What it does

*   **Two-Stage Detection:** Instead of flat classification, PulseGuard uses an EWMA/CUSUM macro-level regime-break detector to spot anomalous windows against a merchant's specific historical baseline, passing only those windows to a transaction-level Isolation Forest.
*   **Amount-Weighted Cost Model:** It dynamically calculates optimal thresholds to minimize total operating cost (False Negatives * Chargeback Fee vs. False Positives * Churn Risk), factoring in the exact monetary amount of each transaction rather than treating all errors equally.
*   **Tiered Policy Engine:** It calculates dual thresholds (`lower_threshold`, `upper_threshold`) to route transactions into `allow`, `review`, and `block` buckets, dynamically optimizing the trade-off between operational review costs and automated blocking errors.
*   **Auto-Responder:** Transactions flagged as `review` or `block` instantly fire batched webhooks, complete with rate-limiting and Isolation Forest feature attribution (e.g., `amount (+2.1σ)`).
*   **Razorpay Integration:** Features a live checkout modal integrated with Razorpay's test SDK, alongside a verified webhook receiver endpoint that can consume real Razorpay dispute webhooks to simulate delayed-label ground truth.

### Architecture
Read the full system design, Mermaid diagrams, design rationale, and production limitations in **[ARCHITECTURE.md](./ARCHITECTURE.md)**.

### Hackathon Track Alignment
We built this explicitly for the Razorpay track. Here is how we checked the boxes:
*   **Detector, Verifier, or Auto-Responder?** We built a **Detector** (Regime breaks + IF) and an **Auto-Responder** (Batched Webhook Manager).
*   **Honest Metrics:** We completely discarded standard F1 scores. Our entire evaluation is built around a custom financial Cost Curve that explicitly penalizes **False Positive Cost** (customer churn and insult rates).
*   **Strictly Defense-Only:** The engine is purely defensive, analyzing transaction metadata to protect the aggregator from chargeback liability and merchant busts without interacting with consumer-facing flows (aside from the internal checkout stub).
