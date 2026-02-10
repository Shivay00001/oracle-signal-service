"""
Oracle Service — Blockchain integration for on-chain signal transmission.

Manages Web3 connection, transaction building, and signal monitoring.
"""

import os
import time
import json
import logging
from typing import Optional, Dict, Any
from datetime import datetime

from .config import settings
from .db import engine, SessionLocal

logger = logging.getLogger(__name__)


class OracleService:
    """
    Oracle service for transmitting analysis signals to blockchain.

    Connects to an Ethereum-compatible RPC endpoint and submits
    signed transactions to the Guardian smart contract.
    """

    def __init__(self):
        self.rpc_url = settings.ETHEREUM_RPC
        self.private_key = settings.ORACLE_PRIVATE_KEY
        self.guardian_address = settings.GUARDIAN_CONTRACT
        self.dao_address = settings.DAO_CONTRACT
        self.chain_id = settings.CHAIN_ID

        # Web3 (lazy-loaded to avoid import errors when web3 is not installed)
        self.w3 = None
        self.account = None

        if self.rpc_url and self.private_key:
            self._initialize_web3()

    def _initialize_web3(self):
        """Initialize Web3 connection."""
        try:
            from web3 import Web3
            from web3.middleware import geth_poa_middleware

            self.w3 = Web3(Web3.HTTPProvider(self.rpc_url))
            self.w3.middleware_onion.inject(geth_poa_middleware, layer=0)

            if not self.w3.is_connected():
                logger.error("Failed to connect to Ethereum RPC")
                return

            self.account = self.w3.eth.account.from_key(self.private_key)
            logger.info(f"Oracle connected to blockchain: {self.account.address}")

        except ImportError:
            logger.error("web3 package not installed. Run: pip install web3")
        except Exception as e:
            logger.error(f"Error initializing Web3: {e}")

    def send_signal(
        self,
        analysis_result_id: int,
        severity: str,
        metrics: Dict[str, Any],
    ) -> Optional[str]:
        """
        Send analysis signal to blockchain.

        Args:
            analysis_result_id: ID of the analysis result.
            severity: Severity level (low/medium/high/critical).
            metrics: Analysis metrics dictionary.

        Returns:
            Transaction hash hex string, or None on failure.
        """
        if not self.w3 or not self.account:
            logger.warning("Web3 not initialized — skipping blockchain transmission")
            return None

        try:
            signal_data = self._prepare_signal(analysis_result_id, severity, metrics)
            tx = self._build_transaction(signal_data)
            signed_tx = self.w3.eth.account.sign_transaction(tx, self.private_key)
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            tx_hash_hex = tx_hash.hex()

            logger.info(f"Signal sent to blockchain: {tx_hash_hex}")

            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

            if receipt["status"] == 1:
                logger.info(f"Transaction confirmed: {tx_hash_hex}")
                return tx_hash_hex
            else:
                logger.error(f"Transaction failed: {tx_hash_hex}")
                return None

        except Exception as e:
            logger.error(f"Error sending signal to blockchain: {e}")
            return None

    def _prepare_signal(
        self,
        analysis_id: int,
        severity: str,
        metrics: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Prepare signal data for transmission."""
        severity_map = {"low": 1, "medium": 2, "high": 3, "critical": 4}

        return {
            "analysis_id": analysis_id,
            "severity_level": severity_map.get(severity, 1),
            "timestamp": int(datetime.utcnow().timestamp()),
            "metrics_hash": self._hash_metrics(metrics),
        }

    def _hash_metrics(self, metrics: Dict[str, Any]) -> str:
        """Create keccak256 hash of metrics for on-chain verification."""
        metrics_str = json.dumps(metrics, sort_keys=True)
        return self.w3.keccak(text=metrics_str).hex() if self.w3 else ""

    def _build_transaction(self, signal_data: Dict[str, Any]) -> Dict[str, Any]:
        """Build and return an unsigned blockchain transaction."""
        guardian_abi = [
            {
                "inputs": [
                    {"name": "analysisId", "type": "uint256"},
                    {"name": "severityLevel", "type": "uint8"},
                    {"name": "timestamp", "type": "uint256"},
                    {"name": "metricsHash", "type": "bytes32"},
                ],
                "name": "submitSignal",
                "outputs": [],
                "stateMutability": "nonpayable",
                "type": "function",
            }
        ]

        contract = self.w3.eth.contract(
            address=self.guardian_address, abi=guardian_abi
        )

        nonce = self.w3.eth.get_transaction_count(self.account.address)

        tx = contract.functions.submitSignal(
            signal_data["analysis_id"],
            signal_data["severity_level"],
            signal_data["timestamp"],
            bytes.fromhex(signal_data["metrics_hash"][2:]),
        ).build_transaction(
            {
                "from": self.account.address,
                "nonce": nonce,
                "gas": 200000,
                "gasPrice": self.w3.eth.gas_price,
                "chainId": self.chain_id,
            }
        )

        return tx

    def monitor_and_send(self, poll_interval: int = 60):
        """
        Poll for pending high-severity signals and transmit them on-chain.

        Args:
            poll_interval: Seconds between database polls.
        """
        logger.info("Oracle monitoring started")

        while True:
            try:
                session = SessionLocal()

                from .models.oracle_signal import OracleSignal
                from .models.analysis_result import AnalysisResult

                pending_signals = (
                    session.query(OracleSignal)
                    .filter(
                        OracleSignal.status == "pending",
                        OracleSignal.severity.in_(["high", "critical"]),
                    )
                    .all()
                )

                for signal in pending_signals:
                    analysis = (
                        session.query(AnalysisResult)
                        .filter(AnalysisResult.id == signal.analysis_result_id)
                        .first()
                    )

                    if not analysis:
                        continue

                    tx_hash = self.send_signal(
                        analysis.id, signal.severity, analysis.metrics
                    )

                    if tx_hash:
                        signal.status = "sent"
                        signal.tx_hash = tx_hash
                        signal.tx_status = "confirmed"
                        signal.sent_at = datetime.utcnow()
                    else:
                        signal.status = "failed"

                    session.commit()

                session.close()

            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")

            time.sleep(poll_interval)


def main():
    """CLI entry point for running the oracle monitor."""
    logging.basicConfig(level=logging.INFO)

    oracle = OracleService()

    if not oracle.w3:
        logger.warning("Oracle running in simulation mode (no blockchain connection)")

    oracle.monitor_and_send(poll_interval=30)


if __name__ == "__main__":
    main()
