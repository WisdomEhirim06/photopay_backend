from pydantic import BaseModel, Field, validator
from datetime import datetime
from typing import Optional, List
from enum import Enum

class UserRole(str, Enum):
    CREATOR = "creator"
    BUYER = "buyer"
    
    
class TransactionStatus(str, Enum):
    PENDING =  "pending"
    CONFIRMED = "confirmed"
    FAILED = "failed"
    
# For the user schemas
class UserCreate(BaseModel):
    wallet_address: str
    username: Optional[str] = None
    role: UserRole = UserRole.BUYER
    

class UserResponse(BaseModel):
    wallet_address: str
    username: Optional[str]
    role: UserRole
    created_at: datetime

    class Config:
        from_attributes = True

# Listing Schemas
class ListingCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    price_sol: float = Field(..., gt=0)
    creator_wallet: str

    @validator('price_sol')
    def validate_price(cls, v):
        if v <= 0:
            raise ValueError('Price must be greater than 0')
        return round(v, 9)  # SOL has 9 decimals

class ListingResponse(BaseModel):
    id: str
    title: str
    description: Optional[str]
    price_sol: float
    creator_wallet: str
    file_url: str
    preview_url: Optional[str]
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

class ListingDetailResponse(ListingResponse):
    creator: UserResponse

# Purchase Schemas
class PurchaseCreate(BaseModel):
    listing_id: str
    buyer_wallet: str

class PurchaseInitResponse(BaseModel):
    transaction_data: dict
    listing: ListingResponse
    amount_sol: float

class PurchaseConfirm(BaseModel):
    listing_id: str
    buyer_wallet: str
    transaction_signature: str

class PurchaseResponse(BaseModel):
    id: str
    listing_id: str
    buyer_wallet: str
    transaction_signature: str
    amount_sol: float
    status: TransactionStatus
    purchased_at: datetime
    confirmed_at: Optional[datetime]

    class Config:
        from_attributes = True

class PurchaseDetailResponse(PurchaseResponse):
    listing: ListingResponse

# Creator Dashboard Schemas
class CreatorStats(BaseModel):
    total_sales: int
    total_earnings_sol: float
    active_listings: int
    recent_sales: List[PurchaseDetailResponse]

# Unlocked Content
class UnlockedContent(BaseModel):
    listing_id: str
    title: str
    file_url: str
    purchased_at: datetime