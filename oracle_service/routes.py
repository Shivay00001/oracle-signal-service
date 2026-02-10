"""
FastAPI routes for Oracle / Blockchain integration.

Provides endpoints for managing oracle signals and monitoring transactions.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta
import logging

from .db import get_db
from .config import settings
from .models.oracle_signal import OracleSignal
from .models.analysis_result import AnalysisResult
from .models.job import Job
from .schemas.oracle import OracleSignalResponse
from .worker import enqueue_oracle_job

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/")
async def oracle_health():
    """Health check endpoint."""
    return {"status": "ok", "service": "oracle"}


@router.get("/status")
async def get_oracle_status():
    """Get oracle service status and configuration."""
    return {
        "enabled": settings.ORACLE_ENABLED,
        "chain_id": settings.CHAIN_ID if settings.ORACLE_ENABLED else None,
        "rpc_connected": bool(settings.ETHEREUM_RPC) if settings.ORACLE_ENABLED else False,
        "guardian_contract": settings.GUARDIAN_CONTRACT if settings.ORACLE_ENABLED else None,
        "dao_contract": settings.DAO_CONTRACT if settings.ORACLE_ENABLED else None,
    }


@router.get("/signals", response_model=List[OracleSignalResponse])
async def list_oracle_signals(
    skip: int = 0,
    limit: int = 100,
    signal_status: Optional[str] = None,
    severity: Optional[str] = None,
    since_hours: Optional[int] = Query(default=168, ge=1, le=720),
    db: Session = Depends(get_db),
):
    """List oracle signals with filtering."""
    if not settings.ORACLE_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Oracle service is not enabled",
        )

    query = db.query(OracleSignal)

    if signal_status:
        query = query.filter(OracleSignal.status == signal_status)

    if severity:
        query = query.filter(OracleSignal.severity == severity)

    if since_hours:
        cutoff_time = datetime.utcnow() - timedelta(hours=since_hours)
        query = query.filter(OracleSignal.created_at >= cutoff_time)

    query = query.order_by(OracleSignal.created_at.desc())
    signals = query.offset(skip).limit(limit).all()
    return signals


@router.get("/signals/{signal_id}", response_model=OracleSignalResponse)
async def get_oracle_signal(signal_id: int, db: Session = Depends(get_db)):
    """Get specific oracle signal details."""
    if not settings.ORACLE_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Oracle service is not enabled",
        )

    signal = db.query(OracleSignal).filter(OracleSignal.id == signal_id).first()

    if not signal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Oracle signal {signal_id} not found",
        )

    return signal


@router.post("/signals/create")
async def create_oracle_signal(
    analysis_result_id: int, db: Session = Depends(get_db)
):
    """
    Create and enqueue an oracle signal for an analysis result.

    Only creates signals for high/critical severity results.
    """
    if not settings.ORACLE_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Oracle service is not enabled",
        )

    analysis = (
        db.query(AnalysisResult)
        .filter(AnalysisResult.id == analysis_result_id)
        .first()
    )

    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analysis result {analysis_result_id} not found",
        )

    if analysis.severity not in ["high", "critical"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Analysis severity '{analysis.severity}' is not high enough for oracle signal",
        )

    existing_signal = (
        db.query(OracleSignal)
        .filter(OracleSignal.analysis_result_id == analysis_result_id)
        .first()
    )

    if existing_signal:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Oracle signal already exists for analysis {analysis_result_id}",
        )

    oracle_signal = OracleSignal(
        analysis_result_id=analysis_result_id,
        severity=analysis.severity,
        signal_type="alert",
        payload={
            "dataset_id": analysis.dataset_id,
            "category": analysis.category,
            "quality_score": analysis.quality_score,
            "metrics_summary": {
                k: v for k, v in list(analysis.metrics.items())[:5]
            },
        },
        status="pending",
    )

    db.add(oracle_signal)
    db.commit()
    db.refresh(oracle_signal)

    job = Job(
        type="oracle_signal",
        status="pending",
        input_data={
            "oracle_signal_id": oracle_signal.id,
            "analysis_result_id": analysis_result_id,
        },
    )

    db.add(job)
    db.commit()
    db.refresh(job)

    enqueue_oracle_job(job.id, analysis_result_id)

    logger.info(
        f"Created oracle signal {oracle_signal.id} for analysis {analysis_result_id}"
    )

    return {
        "signal_id": oracle_signal.id,
        "job_id": job.id,
        "status": "pending",
        "message": "Oracle signal created and queued for transmission",
    }


@router.post("/signals/{signal_id}/retry")
async def retry_oracle_signal(signal_id: int, db: Session = Depends(get_db)):
    """Retry sending a failed oracle signal."""
    if not settings.ORACLE_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Oracle service is not enabled",
        )

    signal = db.query(OracleSignal).filter(OracleSignal.id == signal_id).first()

    if not signal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Oracle signal {signal_id} not found",
        )

    if signal.status not in ["failed", "pending"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot retry signal with status '{signal.status}'",
        )

    signal.status = "pending"
    signal.tx_hash = None
    signal.tx_status = None
    signal.sent_at = None

    db.commit()

    job = Job(
        type="oracle_signal",
        status="pending",
        input_data={
            "oracle_signal_id": signal.id,
            "analysis_result_id": signal.analysis_result_id,
        },
    )

    db.add(job)
    db.commit()
    db.refresh(job)

    enqueue_oracle_job(job.id, signal.analysis_result_id)

    logger.info(f"Retrying oracle signal {signal_id}")

    return {
        "signal_id": signal.id,
        "job_id": job.id,
        "status": "pending",
        "message": "Oracle signal retry queued",
    }


@router.get("/stats/summary")
async def get_oracle_stats(db: Session = Depends(get_db)):
    """Get oracle statistics summary."""
    if not settings.ORACLE_ENABLED:
        return {"enabled": False, "message": "Oracle service is not enabled"}

    total_signals = db.query(OracleSignal).count()
    pending = db.query(OracleSignal).filter(OracleSignal.status == "pending").count()
    sent = db.query(OracleSignal).filter(OracleSignal.status == "sent").count()
    failed = db.query(OracleSignal).filter(OracleSignal.status == "failed").count()

    signals_by_severity = {}
    for severity_level in ["low", "medium", "high", "critical"]:
        count = (
            db.query(OracleSignal)
            .filter(OracleSignal.severity == severity_level)
            .count()
        )
        signals_by_severity[severity_level] = count

    cutoff = datetime.utcnow() - timedelta(hours=24)
    recent_signals = (
        db.query(OracleSignal).filter(OracleSignal.created_at >= cutoff).count()
    )

    total_processed = sent + failed
    success_rate = (sent / total_processed * 100) if total_processed > 0 else 0

    return {
        "enabled": True,
        "total_signals": total_signals,
        "by_status": {"pending": pending, "sent": sent, "failed": failed},
        "by_severity": signals_by_severity,
        "recent_24h": recent_signals,
        "success_rate": round(success_rate, 2),
        "chain_id": settings.CHAIN_ID,
        "contracts": {
            "guardian": settings.GUARDIAN_CONTRACT,
            "dao": settings.DAO_CONTRACT,
        },
    }


@router.get("/transactions/{tx_hash}")
async def get_transaction_status(tx_hash: str):
    """Get blockchain transaction status (requires Web3 connection)."""
    if not settings.ORACLE_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Oracle service is not enabled",
        )

    return {
        "tx_hash": tx_hash,
        "status": "use_oracle_service_to_check",
        "message": "Transaction status check requires Oracle service access",
    }
