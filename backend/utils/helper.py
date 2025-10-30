from typing import Optional
import re
from datetime import datetime

def is_valid_solana_address(address: str) -> bool:
    """Validate Solana wallet address format"""
    # Solana addresses are base58 encoded and 32-44 characters long
    pattern = r'^[1-9A-HJ-NP-Za-km-z]{32,44}$'
    return bool(re.match(pattern, address))

def format_sol_amount(amount: float) -> str:
    """Format SOL amount for display"""
    return f"{amount:.9f} SOL"

def format_datetime(dt: datetime) -> str:
    """Format datetime for API responses"""
    return dt.isoformat()

def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe storage"""
    # Remove path separators and special characters
    sanitized = re.sub(r'[^\w\s.-]', '', filename)
    return sanitized[:255]  # Limit length

def calculate_platform_fee(amount_sol: float, fee_percentage: float = 2.5) -> dict:
    """
    Calculate platform fee
    
    Args:
        amount_sol: Total transaction amount
        fee_percentage: Platform fee percentage (default 2.5%)
        
    Returns:
        Dictionary with creator_amount and platform_fee
    """
    platform_fee = amount_sol * (fee_percentage / 100)
    creator_amount = amount_sol - platform_fee
    
    return {
        "total_amount": amount_sol,
        "creator_amount": round(creator_amount, 9),
        "platform_fee": round(platform_fee, 9),
        "fee_percentage": fee_percentage
    }

def generate_listing_preview_url(file_url: str) -> str:
    """
    Generate a preview URL for listings
    In production, this could point to a watermarked version
    """
    return file_url  # For MVP, return the same URL

class ValidationError(Exception):
    """Custom validation error"""
    pass

def validate_listing_data(title: str, price_sol: float, creator_wallet: str):
    """Validate listing creation data"""
    if not title or len(title.strip()) == 0:
        raise ValidationError("Title cannot be empty")
    
    if len(title) > 200:
        raise ValidationError("Title too long (max 200 characters)")
    
    if price_sol <= 0:
        raise ValidationError("Price must be greater than 0")
    
    if not is_valid_solana_address(creator_wallet):
        raise ValidationError("Invalid Solana wallet address")

def validate_wallet_address(address: str, field_name: str = "Wallet address"):
    """Validate wallet address with custom field name"""
    if not address:
        raise ValidationError(f"{field_name} is required")
    
    if not is_valid_solana_address(address):
        raise ValidationError(f"Invalid {field_name}")