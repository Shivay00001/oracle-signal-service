"""
Application configuration loaded from environment variables.
"""

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Settings:
    """Oracle service settings."""

    # Feature toggle
    ORACLE_ENABLED: bool = os.getenv("ORACLE_ENABLED", "false").lower() == "true"

    # Blockchain
    CHAIN_ID: int = int(os.getenv("CHAIN_ID", "1"))
    ETHEREUM_RPC: str = os.getenv("ETHEREUM_RPC", "")
    ORACLE_PRIVATE_KEY: str = os.getenv("ORACLE_PRIVATE_KEY", "")
    GUARDIAN_CONTRACT: str = os.getenv("GUARDIAN_CONTRACT", "")
    DAO_CONTRACT: str = os.getenv("DAO_CONTRACT", "")

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///oracle.db")

    # Redis (for job queue)
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # Debug
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"


settings = Settings()
