"""
AnalysisResult model — stores output from data analysis pipelines.
"""

from sqlalchemy import Column, Integer, String, Float, JSON, DateTime
from sqlalchemy.sql import func
from .base import Base


class AnalysisResult(Base):
    __tablename__ = "analysis_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    dataset_id = Column(String(100), nullable=True)
    category = Column(String(100), nullable=True)
    severity = Column(String(20), nullable=False)  # low, medium, high, critical
    quality_score = Column(Float, nullable=True)
    metrics = Column(JSON, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
