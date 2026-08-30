# PulseGuard Risk Console

## Quick Start
1. **Clone the repo**
   ```bash
   git clone https://github.com/Aaryan89/PulseGaurd.git
   cd PulseGaurd
   ```

2. **Start the application**
   ```bash
   docker-compose up -d
   ```

3. **Open the Dashboard**
   Open your browser to: [http://localhost:3000](http://localhost:3000)

*That's it! The backend automatically seeds itself with synthetic data and runs detection on startup. No manual data generation required.*

---

## Local Development Workflow
If you want to run the application outside of Docker for quick debugging:

1. **Start the backend (from the root directory):**
   ```bash
   pip install -r requirements.txt
   uvicorn backend.api:app --host 0.0.0.0 --port 8000
   ```

2. **Start the frontend:**
   ```bash
   cd frontend
   npm install
   npm run dev
   ```
   (The frontend will proxy `/api` requests to `localhost:8000` automatically during local dev).

## Configuration
See `.env.example` for configurable variables, including ports, webhook settings, and cost model defaults.
