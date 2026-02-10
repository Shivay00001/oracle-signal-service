"""
Pydantic response schemas for Oracle API.
"""

from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime


class OracleSignalResponse(BaseModel):
    """Response schema for oracle signal endpoints."""

    id: int
    analysis_result_id: int
    severity: str
    signal_type: str
    payload: Optional[Dict[str, Any]] = None
    status: str
    tx_hash: Optional[str] = None
    tx_status: Optional[str] = None
    sent_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True
