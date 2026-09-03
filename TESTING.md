# Local Testing & Setup Guide

This document explains how to run and test PulseGuard entirely locally from a clean clone. The core console, synthetic data generation, detector, and cost models are designed to run fully locally without relying on live Razorpay credentials or deployed URLs.

## 1. Prerequisites
Before beginning, ensure you have the following installed:
- **Python 3.9+** (Check with `python --version`)
- **Node.js 18+** (Check with `node -v`)
- **Docker & Docker Compose** (Optional, but highly recommended for the quickest path)

---

## 2. Quickest path: Docker Compose
If you have Docker installed, you can spin up the entire application stack in one command:

```bash
docker-compose up --build
```

**What this does:**
- Builds the backend and frontend containers.
- Automatically generates 30 days of synthetic merchant data on boot.
- Runs the two-stage detection pipeline and cost model over the data.
- Starts the FastAPI backend and Vite/React frontend.

**Where to go:** Once you see `Uvicorn running` in the logs (takes ~15-30s for the data pipeline to initialize), open **`http://localhost:3000`** in your browser.

---

## 3. Manual local setup (without Docker)

If you prefer to run the services natively:

### Backend Setup
```bash
# Create and activate a virtual environment
python -m venv venv
# On Windows:
venv\Scripts\activate
# On Mac/Linux:
# source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start the FastAPI backend
uvicorn backend.api:app --host 0.0.0.0 --port 8000
```
*(Note: The backend automatically runs the synthetic data generation and detection pipeline as a background task on startup. You do not need to run the generator manually, though you can via `python data/generator.py` if you simply want to inspect the generated CSV.)*

### Frontend Setup
Open a new terminal window:
```bash
cd frontend
npm install
npm run dev
```
**Where to go:** Open **`http://localhost:5173`** in your browser.

**Environment Variables:** 
No environment variables are required to run the core app locally. The `[FIRE_LIVE_TXN]` feature will safely degrade and show a clean alert if Razorpay credentials are not provided in a `.env` file.

---

## 4. Running the automated test suite

To run the unit and integration tests:

```bash
# Ensure your virtual environment is activated, then run:
pytest
```

**What it covers:** 
- `tests/test_cost_model.py` (Optimal threshold calculation, bounding, math checks)
- `tests/test_detector.py` (EWMA baseline, Isolation Forest edge cases)
- `tests/test_generator.py` (Synthetic data shape and integrity)

A successful run should pass all 8 tests and typically takes between 2 to 5 seconds.

---

## 5. Manually verifying each core capability

Use this checklist to manually verify the features in the local UI:

- [ ] **Synthetic data generation & anomaly injection:** Open the home page. The data pipeline runs on boot, so you will immediately see simulated merchants populated with transaction volumes and flagged windows.
- [ ] **Two-stage detection:** Click on a merchant ID tagged as `REVIEW` or `BLOCK`. Scroll to the audit log to see explanations from both Stage 1 (regime breaks) and Stage 2 (Isolation Forest feature attribution like `amount (+2.1s)`).
- [ ] **Cost model threshold sweep & optimal threshold:** Click `COST CURVE` in the top navigation. View the chart to see the expected operating cost mapped across thresholds, with the mathematical optimal threshold marked.
- [ ] **Naive-vs-ours ablation:** On the Cost Curve page, look at the top metrics row to compare `BASELINE_NO_DETECTOR` (cost of missing 100% of fraud) versus `EXPECTED_OPERATING_COST` (using the detector).
- [ ] **Tiered policy (allow/review/block):** The Cost Curve page displays the Tiered Policy savings box if the tier warrants it. On the home page, merchants are assigned NORMAL, REVIEW, or BLOCK statuses.
- [ ] **Cold-start onboarding behavior:** On the home page, find the merchant tagged `COLD_START`. Clicking it will show a unique purple progress bar detailing its blending state.
- [ ] **Cost dashboard sliders responding live:** At the bottom of the Cost Curve page, drag the `CHARGEBACK_FEE_RATE` and `CHURN_RISK_RATE` sliders. The API will recalculate dynamically, and the chart will redraw instantly to show the new optimal threshold.
- [ ] **Replay mode:** On any Merchant Detail page, click `[PLAY]` in the Replay Controls. Watch the timeline advance and historical transactions plot sequentially.
- [ ] **Local webhook stub firing:** While in Replay mode, watch the `RECENT_ACTIONS (AUTO_RESPONDER)` pane on the home page dynamically populate as flags are triggered.
- [ ] **Real-data validation script:** Run `python backend/real_data_validation.py` in your terminal to see the pipeline tested against real-world data. *(Requires downloading the Kaggle IEEE-CIS Fraud Detection `creditcard.csv` dataset separately and placing it in the `data/` directory).*

---

## 6. What requires external setup

The core product works seamlessly without external services. However, if you want to test the live Razorpay API integrations, you must provide your own accounts:

1. **Live Razorpay Transactions:**
   - Create a `.env` file in the root directory.
   - Add `RAZORPAY_KEY_ID="rzp_test_..."` and `RAZORPAY_KEY_SECRET="..."`.
   - Click `[FIRE_LIVE_TXN]` in the UI to trigger the real Razorpay checkout modal and ingestion loop.

2. **Real Webhook Delivery:**
   - Add `ENABLE_REAL_WEBHOOKS=true` and a custom `RAZORPAY_WEBHOOK_SECRET="..."` to your `.env` file.
   - Use a tool like [ngrok](https://ngrok.com/) to expose your local backend: `ngrok http 8000`.
   - Register your ngrok URL (`https://<your-ngrok>.ngrok-free.app/webhooks/razorpay`) in the Razorpay dashboard.
   - Trigger a live transaction or dispute to see Razorpay hit your local server, where the payload signature will be verified.
