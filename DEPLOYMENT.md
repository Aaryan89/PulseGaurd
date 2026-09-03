# Deployment Guide

This repository is configured to be deployed easily to Railway (Backend) and Vercel (Frontend). 

## 1. Deploy the Backend (Railway)
The backend is built with FastAPI and runs from memory. It does not require a persistent database for the demo (the synthetic data pipeline will run automatically on startup to populate the system).

1. Go to Railway and create a new project from your GitHub repository.
2. Railway will automatically detect the `railway.json` file and use Nixpacks to build and deploy the Python app.
3. Go to the **Variables** tab for your backend service and add the following:
   - `RAZORPAY_KEY_ID`: Your test key ID
   - `RAZORPAY_KEY_SECRET`: Your test key secret
   - `RAZORPAY_WEBHOOK_SECRET`: Your webhook secret
   - `ENABLE_REAL_WEBHOOKS`: `true`
4. Wait for the deployment to finish and generate a public domain (e.g., `https://pulseguard-production.up.railway.app`). Copy this URL.

## 2. Deploy the Frontend (Vercel)
The frontend is a Vite + React Single Page Application (SPA). The `vercel.json` file is already included to handle routing properly.

1. Go to Vercel and import the repository.
2. Select the `frontend` directory as the Root Directory (if it prompts you, or just configure the build settings to point to it).
3. In the Environment Variables section, add:
   - `VITE_API_URL`: Paste the backend URL you copied from Railway (e.g., `https://pulseguard-production.up.railway.app`). **Do not add a trailing slash**.
4. Click Deploy. Vercel will build the frontend and give you a public URL (e.g., `https://pulseguard.vercel.app`). Copy this URL.

## 3. Configure CORS on the Backend
To secure the backend and allow the Vercel frontend to talk to it:

1. Go back to your Railway project dashboard.
2. Open the **Variables** tab for the backend.
3. Add a new variable:
   - `ALLOWED_ORIGINS`: Paste your Vercel frontend URL (e.g., `https://pulseguard.vercel.app`).
4. Railway will automatically redeploy the backend with the new CORS settings.

Your system is now live! 

*Note: Because the backend uses in-memory data, the data will reset every time the Railway container restarts. The startup pipeline will automatically regenerate synthetic data upon boot (takes ~15-30 seconds).*
