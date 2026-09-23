"""
Production entry point for the Oracle Signal Service.

Assembles the FastAPI application from the oracle_service package and
exposes it as ``main:app`` for uvicorn / gunicorn / Render.

Run locally:
    uvicorn main:app --host 0.0.0.0 --port 8000 --reload

Runs in simulation mode when no blockchain credentials are provided
(see .env.example).
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from oracle_service.db import engine
from oracle_service.models import Base
from oracle_service.routes import router as oracle_router

logger = logging.getLogger("oracle.main")

# Create tables (sqlite default; no-op if they already exist)
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Oracle Signal Service",
    description="Transmits analysis signals to an EVM Guardian contract; REST API for oracle signals.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(oracle_router)


@app.get("/health", tags=["ops"])
def health():
    """Container/orchestrator health check."""
    return {"status": "ok", "service": "oracle-signal-service"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000)
