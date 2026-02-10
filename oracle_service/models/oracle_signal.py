"""
OracleSignal model — tracks blockchain signal transmission state.
"""

from sqlalchemy import Column, Integer, String, Float, JSON, DateTime, ForeignKey
from sqlalchemy.sql import func
from .base import Base


class OracleSignal(Base):
    __tablename__ = "oracle_signals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    analysis_result_id = Column(Integer, ForeignKey("analysis_results.id"), nullable=False)
    severity = Column(String(20), nullable=False)  # low, medium, high, critical
    signal_type = Column(String(50), default="alert")
    payload = Column(JSON, nullable=True)
    status = Column(String(20), default="pending")  # pending, sent, failed
    tx_hash = Column(String(66), nullable=True)  # Ethereum tx hash (0x + 64 hex chars)
    tx_status = Column(String(20), nullable=True)  # confirmed, failed
    sent_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
