# PhotoPay — Backend Service (backend/)

Technical README — detailed developer guide for the backend service used by the PhotoPay project.

## Overview

This repository folder implements the PhotoPay backend service:
- Asynchronous FastAPI-based HTTP API.
- Stores metadata and user/listing info in a SQL database (default: SQLite, configurable for Postgres).
- Stores images in Google Cloud Storage (GCS).
- Interacts with Solana (devnet/mainnet) to create and verify SOL transfer transactions.
- Uses aiohttp / requests for HTTP-based integrations (IPFS/Pinata or equivalent).
- Designed for production-like development (uvicorn with reload for local dev).

Primary goals:
- Provide REST endpoints for users, listings, and purchases.
- Provide endpoints for transaction creation and verification on Solana.
- Store and serve media via GCS.

## Architecture & Components

- FastAPI app entrypoint: `backend/main.py`
- Database layer: `backend/database.py` (SQLAlchemy engine + base)
- Data models: `backend/models.py` (SQLAlchemy models)
- Pydantic schemas: `backend/schemas.py`
- Services:
  - `backend/services/storage_service.py` — GCS interactions (upload, download, signed URLs)
  - `backend/services/solana_service.py` — Solana RPC interactions (create transaction, verify, status)
  - `backend/services/gateway_service.py` — optional gateway for sending transactions or wrappers
- Utility helpers: `backend/utils/helper.py`
- Credentials: `backend/credentials/gcs-credentials.json` (kept out of source control; local dev only)

All services are written with async I/O in mind and expect to be used in async FastAPI endpoints.

## Runtime Requirements

- Python 3.10+ (project uses modern async and type features; verify local compatibility)
- Virtual environment recommended (e.g., `.venv`)
- Key Python libraries (see `requirements.txt` in project root):
  - fastapi, uvicorn, sqlalchemy, pydantic, aiohttp, requests
  - google-cloud-storage, google-auth, google-api-core, google-resumable-media
  - solana (solana-py) and solders (native wheel)
  - python-dotenv

Note: some packages (e.g., `solders`) ship as compiled wheels; static analysis tools may show "could not be resolved from source" — this is an analyzer warning (Pylance) and not a runtime error.

## Environment Variables

The backend reads configuration from a `.env` file. Notable keys:

Required / Common:
- DATABASE_URL — e.g. `sqlite:///./photopay.db` or `postgresql://user:pass@host/db`
- GOOGLE_APPLICATION_CREDENTIALS — absolute path to GCS service account JSON (local dev)
- GCS_BUCKET_NAME — GCS bucket name for storing images
- GCS_PROJECT_ID — GCS project id
- SOLANA_RPC_URL — e.g. `https://api.devnet.solana.com` or `https://api.mainnet-beta.solana.com`
- SOLANA_NETWORK — `devnet` | `testnet` | `mainnet`
- SANCTUM_GATEWAY_ENABLED — `true`/`false` (optional gateway)
- SANCTUM_GATEWAY_URL / SANCTUM_GATEWAY_API_KEY — if using Sanctum RPC gateway
- APP_NAME / APP_VERSION / DEBUG — application metadata



Keep secrets out of version control. Use environment-managed secrets in production.

## Setup (local dev)

1. Clone repo and open backend folder:
   - cd to `c:\Users\madus\photopay\photopay_backend\backend`

2. Create and activate venv (Windows PowerShell):
   - python -m venv .venv
   - .venv\Scripts\Activate.ps1

3. Install dependencies (from project root where requirements.txt exists):
   - python -m pip install --upgrade pip
   - pip install -r ..\requirements.txt
   (If you are running from the `backend` folder, adjust path to requirements accordingly.)

4. Create `.env` file (use provided `.env` template in project root). Example snippet: