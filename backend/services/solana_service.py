import os
import base64
from solana.rpc.async_api import AsyncClient
from solders.pubkey import Pubkey
from solana.transaction import Transaction
from solders.system_program import TransferParams, transfer
from solders.signature import Signature
from typing import Dict, Optional
from dotenv import load_dotenv

load_dotenv()

class SolanaService:
    def __init__(self):
        self.rpc_url = os.getenv("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com")
        self.client = AsyncClient(self.rpc_url)
        
    def lamports_to_sol(self, lamports: int) -> float:
        """Convert lamports to SOL"""
        return lamports / 1_000_000_000
    
    def sol_to_lamports(self, sol: float) -> int:
        """Convert SOL to lamports"""
        return int(sol * 1_000_000_000)
    
    async def get_balance(self, wallet_address: str) -> float:
        """Get wallet balance in SOL"""
        try:
            pubkey = Pubkey.from_string(wallet_address)
            response = await self.client.get_balance(pubkey)
            if response.value is not None:
                return self.lamports_to_sol(response.value)
            return 0.0
        except Exception as e:
            raise Exception(f"Failed to get balance: {str(e)}")
    
    async def create_transfer_transaction(
        self,
        from_wallet: str,
        to_wallet: str,
        amount_sol: float
    ) -> Dict[str, any]:
        """
        Create a transfer transaction instruction data
        Returns data for frontend to build, sign, and send the transaction
        """
        try:
            from_pubkey = Pubkey.from_string(from_wallet)
            to_pubkey = Pubkey.from_string(to_wallet)
            lamports = self.sol_to_lamports(amount_sol)
            
            # Get recent blockhash
            response = await self.client.get_latest_blockhash()
            if not hasattr(response, "value"):
                raise Exception(f"Invalid RPC response: {response}")
            
            recent_blockhash = response.value.blockhash
            last_valid_block_height = response.value.last_valid_block_height
            
            # Return instruction data for frontend to build transaction
            # Frontend will use this to create the transaction with wallet adapter
            return {
                "instruction_type": "transfer",
                "from_pubkey": from_wallet,
                "to_pubkey": to_wallet,
                "lamports": lamports,
                "amount_sol": amount_sol,
                "recent_blockhash": str(recent_blockhash),
                "last_valid_block_height": last_valid_block_height,
                "message": "Build transaction in frontend using this data"
            }
            
        except Exception as e:
            raise Exception(f"Failed to create transaction: {str(e)}")
    
    async def verify_transaction(
        self,
        signature: str,
        expected_sender: str,
        expected_receiver: str,
        expected_amount_sol: float
    ) -> bool:
        """
        Verify a transaction has been confirmed on-chain
        """
        try:
            sig = Signature.from_string(signature)
            
            # Get transaction details
            response = await self.client.get_transaction(
                sig,
                encoding="jsonParsed",
                max_supported_transaction_version=0
            )
            
            if response.value is None:
                return False
            
            tx = response.value
            
            # Check if transaction is confirmed
            if tx.transaction.meta.err is not None:
                return False
            
            # Parse transaction to verify sender, receiver, and amount
            instructions = tx.transaction.transaction.message.instructions
            
            for ix in instructions:
                if hasattr(ix, 'parsed'):
                    parsed = ix.parsed
                    if parsed['type'] == 'transfer':
                        info = parsed['info']
                        
                        sender = info['source']
                        receiver = info['destination']
                        lamports = int(info['lamports'])
                        amount_sol = self.lamports_to_sol(lamports)
                        
                        # Verify transaction details
                        if (sender == expected_sender and
                            receiver == expected_receiver and
                            abs(amount_sol - expected_amount_sol) < 0.000001):  # Allow small floating point difference
                            return True
            
            return False
            
        except Exception as e:
            print(f"Transaction verification error: {str(e)}")
            return False
    
    async def get_transaction_status(self, signature: str) -> Optional[str]:
        """Get transaction confirmation status"""
        try:
            sig = Signature.from_string(signature)
            response = await self.client.get_signature_statuses([sig])
            
            if response.value and response.value[0]:
                status = response.value[0]
                if status.confirmation_status:
                    return status.confirmation_status.value
            return None
            
        except Exception as e:
            print(f"Error getting transaction status: {str(e)}")
            return None
    
    async def close(self):
        """Close the RPC client connection"""
        await self.client.close()

# Singleton instance
solana_service = SolanaService()