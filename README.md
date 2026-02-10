# Oracle Service

A self-contained Python service for transmitting analysis signals to an Ethereum-compatible blockchain via smart contract interactions.

## What This Project Is

This is a backend service that:

1. **Monitors** a database for high-severity analysis results.
2. **Transmits** signed transactions to a Guardian smart contract on-chain.
3. **Exposes** a FastAPI REST API for managing oracle signals (create, retry, list, stats).
4. **Integrates** with a DAO governance framework (proposals, voting, IP licensing).

## What This Project Is NOT

- This is **NOT** a price oracle (e.g., Chainlink-style).
- This does **NOT** make autonomous financial decisions.
- This does **NOT** require blockchain to function — it runs in simulation mode without Web3 credentials.

## Architecture

```
oracle_service/
├── service.py      — Web3 connection, transaction building, signal monitor
├── routes.py       — FastAPI REST API endpoints
├── config.py       — Environment-based settings
├── db.py           — SQLAlchemy session management
├── worker.py       — Job queue stub (replace with Celery for production)
├── models/         — SQLAlchemy models (OracleSignal, AnalysisResult, Job)
└── schemas/        — Pydantic response schemas
```

## API Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/` | Health check |
| GET | `/status` | Oracle configuration status |
| GET | `/signals` | List signals (filterable) |
| GET | `/signals/{id}` | Get signal details |
| POST | `/signals/create` | Create signal from analysis result |
| POST | `/signals/{id}/retry` | Retry failed signal |
| GET | `/stats/summary` | Signal statistics |
| GET | `/transactions/{hash}` | Transaction status (placeholder) |

## Prerequisites

- Python 3.10+
- PostgreSQL or SQLite
- Redis (optional, for production job queue)
- Ethereum RPC endpoint (optional, runs in simulation without it)

## Installation

```bash
pip install -r requirements.txt
```

## Configuration

Set environment variables:

```bash
# Required for blockchain mode
export ORACLE_ENABLED=true
export ETHEREUM_RPC=https://your-rpc-endpoint
export ORACLE_PRIVATE_KEY=0x...
export GUARDIAN_CONTRACT=0x...
export DAO_CONTRACT=0x...
export CHAIN_ID=1

# Database
export DATABASE_URL=postgresql://user:pass@localhost/oracle

# Optional
export REDIS_URL=redis://localhost:6379/0
export DEBUG=false
```

## Usage

Run the signal monitor:

```bash
python -m oracle_service.service
```

Run the API server (integrate with FastAPI app):

```python
from fastapi import FastAPI
from oracle_service.routes import router

app = FastAPI()
app.include_router(router, prefix="/oracle")
```

## Smart Contracts

The service interacts with three Solidity contracts (see `contracts/test/`):

- **YOUDAO** — Governance: proposals, voting, staking, IP licensing
- **YOUAIGuardian** — Oracle signal submission, heartbeat monitoring
- **TreasuryMultiSig** — Multi-signature fund management

## Disclaimer

This software is provided "as is" without warranty. The authors are not responsible for any financial losses resulting from blockchain transactions.
