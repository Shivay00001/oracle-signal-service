"""
YOU.AI Oracle Service
Blockchain integration for on-chain signal transmission
"""
import os
import time
import logging
from typing import Optional, Dict, Any
from web3 import Web3
from web3.middleware import geth_poa_middleware
import json
from datetime import datetime
import redis
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class OracleService:
    """
    Oracle service for transmitting analysis signals to blockchain
    """
    
    def __init__(self):
        # Load environment variables
        self.rpc_url = os.getenv('ETHEREUM_RPC', '')
        self.private_key = os.getenv('ORACLE_PRIVATE_KEY', '')
        self.guardian_address = os.getenv('GUARDIAN_CONTRACT', '')
        self.dao_address = os.getenv('DAO_CONTRACT', '')
        self.chain_id = int(os.getenv('CHAIN_ID', '1'))
        
        # Database connection
        db_url = os.getenv('DATABASE_URL', '')
        self.engine = create_engine(db_url)
        self.Session = sessionmaker(bind=self.engine)
        
        # Redis connection
        redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
        self.redis_client = redis.from_url(redis_url)
        
        # Web3 setup
        self.w3: Optional[Web3] = None
        self.account = None
        
        if self.rpc_url and self.private_key:
            self._initialize_web3()
    
    def _initialize_web3(self):
        """Initialize Web3 connection"""
        try:
            self.w3 = Web3(Web3.HTTPProvider(self.rpc_url))
            self.w3.middleware_onion.inject(geth_poa_middleware, layer=0)
            
            if not self.w3.is_connected():
                logger.error("Failed to connect to Ethereum RPC")
                return
            
            self.account = self.w3.eth.account.from_key(self.private_key)
            logger.info(f"Oracle connected to blockchain: {self.account.address}")
            
        except Exception as e:
            logger.error(f"Error initializing Web3: {e}")
    
    def send_signal(
        self,
        analysis_result_id: int,
        severity: str,
        metrics: Dict[str, Any]
    ) -> Optional[str]:
        """
        Send analysis signal to blockchain
        
        Args:
            analysis_result_id: ID of analysis result
            severity: Severity level
            metrics: Analysis metrics
        
        Returns:
            Transaction hash or None
        """
        if not self.w3 or not self.account:
            logger.warning("Web3 not initialized - skipping blockchain transmission")
            return None
        
        try:
            # Prepare signal data
            signal_data = self._prepare_signal(analysis_result_id, severity, metrics)
            
            # Build transaction
            tx = self._build_transaction(signal_data)
            
            # Sign transaction
            signed_tx = self.w3.eth.account.sign_transaction(tx, self.private_key)
            
            # Send transaction
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            tx_hash_hex = tx_hash.hex()
            
            logger.info(f"Signal sent to blockchain: {tx_hash_hex}")
            
            # Wait for receipt (optional)
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            
            if receipt['status'] == 1:
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
        metrics: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Prepare signal data for transmission"""
        
        # Map severity to numeric value
        severity_map = {
            'low': 1,
            'medium': 2,
            'high': 3,
            'critical': 4
        }
        
        return {
            'analysis_id': analysis_id,
            'severity_level': severity_map.get(severity, 1),
            'timestamp': int(datetime.utcnow().timestamp()),
            'metrics_hash': self._hash_metrics(metrics)
        }
    
    def _hash_metrics(self, metrics: Dict[str, Any]) -> str:
        """Create hash of metrics for on-chain verification"""
        metrics_str = json.dumps(metrics, sort_keys=True)
        return self.w3.keccak(text=metrics_str).hex() if self.w3 else ""
    
    def _build_transaction(self, signal_data: Dict[str, Any]) -> Dict[str, Any]:
        """Build blockchain transaction"""
        
        # Load contract ABI (simplified - in production, load from file)
        guardian_abi = [
            {
                "inputs": [
                    {"name": "analysisId", "type": "uint256"},
                    {"name": "severityLevel", "type": "uint8"},
                    {"name": "timestamp", "type": "uint256"},
                    {"name": "metricsHash", "type": "bytes32"}
                ],
                "name": "submitSignal",
                "outputs": [],
                "stateMutability": "nonpayable",
                "type": "function"
            }
        ]
        
        contract = self.w3.eth.contract(
            address=self.guardian_address,
            abi=guardian_abi
        )
        
        # Build transaction
        nonce = self.w3.eth.get_transaction_count(self.account.address)
        
        tx = contract.functions.submitSignal(
            signal_data['analysis_id'],
            signal_data['severity_level'],
            signal_data['timestamp'],
            bytes.fromhex(signal_data['metrics_hash'][2:])  # Remove '0x' prefix
        ).build_transaction({
            'from': self.account.address,
            'nonce': nonce,
            'gas': 200000,
            'gasPrice': self.w3.eth.gas_price,
            'chainId': self.chain_id
        })
        
        return tx
    
    def monitor_and_send(self, poll_interval: int = 60):
        """
        Monitor for new high-severity analysis results and send signals
        
        Args:
            poll_interval: Seconds between polls
        """
        logger.info("Oracle monitoring started")
        
        while True:
            try:
                session = self.Session()
                
                # Query for pending oracle signals
                from app.models.oracle_signal import OracleSignal
                from app.models.analysis_result import AnalysisResult
                
                pending_signals = session.query(OracleSignal).filter(
                    OracleSignal.status == 'pending',
                    OracleSignal.severity.in_(['high', 'critical'])
                ).all()
                
                for signal in pending_signals:
                    # Get associated analysis result
                    analysis = session.query(AnalysisResult).filter(
                        AnalysisResult.id == signal.analysis_result_id
                    ).first()
                    
                    if not analysis:
                        continue
                    
                    # Send signal to blockchain
                    tx_hash = self.send_signal(
                        analysis.id,
                        signal.severity,
                        analysis.metrics
                    )
                    
                    if tx_hash:
                        signal.status = 'sent'
                        signal.tx_hash = tx_hash
                        signal.tx_status = 'confirmed'
                        signal.sent_at = datetime.utcnow()
                    else:
                        signal.status = 'failed'
                    
                    session.commit()
                
                session.close()
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
            
            time.sleep(poll_interval)

def main():
    """Main entry point"""
    oracle = OracleService()
    
    if not oracle.w3:
        logger.warning("Oracle running in simulation mode (no blockchain connection)")
    
    # Start monitoring
    oracle.monitor_and_send(poll_interval=30)

if __name__ == "__main__":
    main()
