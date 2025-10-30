from sqlalchemy import Column, String, Float, DateTime, Enum, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum
from backend.database import Base

class UserRole(str, enum.Enum):
    CREATOR = "creator"
    BUYER = "buyer"

class TransactionStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    FAILED = "failed"

class User(Base):
    __tablename__ = "users"

    wallet_address = Column(String, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=True)
    role = Column(Enum(UserRole), default=UserRole.BUYER)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    listings = relationship("Listing", back_populates="creator", foreign_keys="Listing.creator_wallet")
    purchases = relationship("Purchase", back_populates="buyer", foreign_keys="Purchase.buyer_wallet")

class Listing(Base):
    __tablename__ = "listings"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String, nullable=False)
    description = Column(String)
    price_sol = Column(Float, nullable=False)
    creator_wallet = Column(String, ForeignKey("users.wallet_address"), nullable=False)
    file_id = Column(String, nullable=False)
    file_url = Column(String, nullable=False)
    preview_url = Column(String, nullable=True)  # Optional watermarked preview
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    creator = relationship("User", back_populates="listings", foreign_keys=[creator_wallet])
    purchases = relationship("Purchase", back_populates="listing")

class Purchase(Base):
    __tablename__ = "purchases"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    listing_id = Column(String, ForeignKey("listings.id"), nullable=False)
    buyer_wallet = Column(String, ForeignKey("users.wallet_address"), nullable=False)
    transaction_signature = Column(String, unique=True, nullable=False)
    amount_sol = Column(Float, nullable=False)
    status = Column(Enum(TransactionStatus), default=TransactionStatus.PENDING)
    purchased_at = Column(DateTime, default=datetime.utcnow)
    confirmed_at = Column(DateTime, nullable=True)
    
    # Relationships
    listing = relationship("Listing", back_populates="purchases")
    buyer = relationship("User", back_populates="purchases", foreign_keys=[buyer_wallet])