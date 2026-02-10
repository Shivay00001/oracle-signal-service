"""
Job queue — stub for background task processing.
Replace with Celery, RQ, or similar for production use.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# In-memory queue for development. Replace with Redis/Celery in production.
_pending_jobs: list = []


def enqueue_oracle_job(job_id: int, analysis_result_id: int) -> None:
    """
    Enqueue an oracle signal job for background processing.

    In production, this should push to a Redis-backed queue (e.g., Celery, RQ).
    Current implementation is a no-op stub that logs the intent.
    """
    _pending_jobs.append({
        "job_id": job_id,
        "analysis_result_id": analysis_result_id,
    })
    logger.info(f"Enqueued oracle job {job_id} for analysis {analysis_result_id}")


def get_pending_jobs() -> list:
    """Return pending jobs (development only)."""
    return list(_pending_jobs)


def clear_pending_jobs() -> None:
    """Clear pending jobs (development only)."""
    _pending_jobs.clear()
