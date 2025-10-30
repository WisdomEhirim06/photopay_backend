import os
import aiohttp
from typing import Dict, Optional
from dotenv import load_dotenv

load_dotenv()

class SanctumGatewayService:
    def __init__(self):
        self.enabled = os.getenv("SANCTUM_GATEWAY_ENABLED", "true").lower() == "true"
        self.gateway_url = "https://transaction.sanctum.so"
        
    async def get_priority_fee_estimate(self) -> Optional[int]:
        if not self.enabled:
            return None
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.gateway_url}/v1/priority-fee") as response:
                    if response.status == 200:
                        result = await response.json()
                        return result.get("priorityFee", 5000)
            return 5000  # Default
        except:
            return 5000
    
    async def optimize_transaction(self, transaction_data: Dict, priority_fee: Optional[int] = None) -> Dict:
        if not self.enabled:
            return transaction_data
        
        transaction_data['priority_fee'] = priority_fee or 5000
        transaction_data['optimized_by'] = 'sanctum_gateway'
        return transaction_data
        
    async def optimize_transaction(
        self,
        transaction_data: Dict,
        priority_fee: Optional[int] = None
    ) -> Dict:
        """
        Optimize a transaction through Sanctum Gateway
        
        Args:
            transaction_data: Raw transaction data
            priority_fee: Optional priority fee in micro-lamports
            
        Returns:
            Optimized transaction data
        """
        if not self.enabled:
            return transaction_data
        
        try:
            url = f"{self.gateway_url}/v1/optimize"
            
            payload = {
                "transaction": transaction_data,
                "options": {
                    "priorityFee": priority_fee,
                    "skipPreflight": False,
                    "maxRetries": 3
                }
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result.get("optimizedTransaction", transaction_data)
                    else:
                        # Silently fallback - don't log in production
                        return transaction_data
                        
        except Exception as e:
            # Silently fallback - gateway is optional
            return transaction_data
    
    async def get_priority_fee_estimate(self) -> Optional[int]:
        """
        Get recommended priority fee from Sanctum Gateway
        
        Returns:
            Priority fee in micro-lamports
        """
        if not self.enabled:
            return None
        
        try:
            url = f"{self.gateway_url}/v1/priority-fee"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result.get("priorityFee")
                    return None
                    
        except Exception as e:
            print(f"Failed to get priority fee: {str(e)}")
            return None
    
    async def submit_transaction(
        self,
        signed_transaction: str,
        options: Optional[Dict] = None
    ) -> Dict:
        """
        Submit a signed transaction through Sanctum Gateway
        
        Args:
            signed_transaction: Base64 encoded signed transaction
            options: Optional submission parameters
            
        Returns:
            Transaction submission result with signature
        """
        if not self.enabled:
            return {
                "success": False,
                "error": "Gateway not enabled"
            }
        
        try:
            url = f"{self.gateway_url}/v1/submit"
            
            payload = {
                "transaction": signed_transaction,
                "options": options or {}
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as response:
                    result = await response.json()
                    
                    if response.status == 200:
                        return {
                            "success": True,
                            "signature": result.get("signature"),
                            "slot": result.get("slot")
                        }
                    else:
                        return {
                            "success": False,
                            "error": result.get("error", "Unknown error")
                        }
                        
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_transaction_status(self, signature: str) -> Dict:
        """
        Check transaction status through gateway
        
        Returns:
            Transaction status information
        """
        if not self.enabled:
            return {"status": "unknown"}
        
        try:
            url = f"{self.gateway_url}/v1/transaction/{signature}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        return await response.json()
                    return {"status": "unknown"}
                    
        except Exception as e:
            print(f"Failed to get transaction status: {str(e)}")
            return {"status": "error", "error": str(e)}

# Singleton instance
gateway_service = SanctumGatewayService()