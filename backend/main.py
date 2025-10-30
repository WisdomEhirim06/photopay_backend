from fastapi import FastAPI, Depends, HTTPException, status, Request, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from contextlib import asynccontextmanager
import os
from dotenv import load_dotenv

# Internal imports
from backend.database import engine, Base, get_db
from backend.models import User, Listing, Purchase, UserRole, TransactionStatus
from backend.schemas import (
    UserCreate, UserResponse, ListingResponse, ListingDetailResponse,
    CreatorStats, PurchaseCreate, PurchaseInitResponse, PurchaseConfirm,
    PurchaseResponse, UnlockedContent
)
from backend.utils.helper import (
    is_valid_solana_address, ValidationError,
    validate_listing_data, sanitize_filename
)
from backend.services.storage_service import gcs_service
from backend.services.solana_service import solana_service
from backend.services.gateway_service import gateway_service

# --------------------------------------------------------------------
# 🏁 ENV SETUP AND APP INITIALIZATION
# --------------------------------------------------------------------
load_dotenv()
Base.metadata.create_all(bind=engine)

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 PhotoPay API Starting...")
    print(f"📊 Database: {os.getenv('DATABASE_URL', 'sqlite:///./photopay.db')}")
    print(f"🔗 Solana RPC: #")
    print("📦 Storage: GCS")
    sanctum_enabled = os.getenv("SANCTUM_GATEWAY_ENABLED", "false").lower() == "true"
    print(f"⚡ Sanctum Gateway: {'Enabled' if sanctum_enabled else 'Disabled'}")
    yield
    print("👋 PhotoPay API Shutting down...")
    await solana_service.close()

app = FastAPI(
    title=os.getenv("APP_NAME", "PhotoPay"),
    version=os.getenv("APP_VERSION", "1.0.0"),
    description="Decentralized Photo/Art Marketplace Backend API",
    lifespan=lifespan
)

# --------------------------------------------------------------------
# 🌐 MIDDLEWARE
# --------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



# --------------------------------------------------------------------
# 👤 USERS ENDPOINTS
# --------------------------------------------------------------------
@app.post("/api/users/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(user_data: UserCreate, db: Session = Depends(get_db)):
    if not is_valid_solana_address(user_data.wallet_address):
        raise HTTPException(400, "Invalid Solana wallet address")

    existing_user = db.query(User).filter(User.wallet_address == user_data.wallet_address).first()
    if existing_user:
        raise HTTPException(409, "User with this wallet address already exists")

    if user_data.username:
        existing_username = db.query(User).filter(User.username == user_data.username).first()
        if existing_username:
            raise HTTPException(409, "Username already taken")

    new_user = User(
        wallet_address=user_data.wallet_address,
        username=user_data.username,
        role=user_data.role
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@app.get("/api/users/{wallet_address}", response_model=UserResponse)
async def get_user(wallet_address: str, db: Session = Depends(get_db)):
    if not is_valid_solana_address(wallet_address):
        raise HTTPException(400, "Invalid wallet address")

    user = db.query(User).filter(User.wallet_address == wallet_address).first()
    if not user:
        raise HTTPException(404, "User not found")
    return user


@app.get("/api/users/", response_model=List[UserResponse])
async def list_users(skip: int = 0, limit: int = 100, role: Optional[UserRole] = None, db: Session = Depends(get_db)):
    query = db.query(User)
    if role:
        query = query.filter(User.role == role)
    return query.offset(skip).limit(limit).all()


@app.put("/api/users/{wallet_address}", response_model=UserResponse)
async def update_user(wallet_address: str, username: Optional[str] = None, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.wallet_address == wallet_address).first()
    if not user:
        raise HTTPException(404, "User not found")

    if username:
        existing = db.query(User).filter(User.username == username, User.wallet_address != wallet_address).first()
        if existing:
            raise HTTPException(409, "Username already taken")
        user.username = username

    db.commit()
    db.refresh(user)
    return user

# --------------------------------------------------------------------
# 🖼️ LISTINGS ENDPOINTS
# --------------------------------------------------------------------
@app.post("/api/listings/", response_model=ListingResponse, status_code=status.HTTP_201_CREATED)
async def create_listing(
    title: str = Form(...),
    description: Optional[str] = Form(None),
    price_sol: float = Form(...),
    creator_wallet: str = Form(...),
    image_file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    try:
        validate_listing_data(title, price_sol, creator_wallet)

        creator = db.query(User).filter(User.wallet_address == creator_wallet).first()
        if not creator:
            creator = User(wallet_address=creator_wallet, role=UserRole.CREATOR)
            db.add(creator)
            db.commit()

        file_content = await image_file.read()
        if len(file_content) == 0:
            raise HTTPException(400, "Empty file uploaded")

        max_size = 50 * 1024 * 1024
        if len(file_content) > max_size:
            raise HTTPException(400, "File too large (max 50MB)")

        safe_filename = sanitize_filename(image_file.filename)
        file_result = await gcs_service.upload_file(file_content, safe_filename)

        new_listing = Listing(
            title=title,
            description=description,
            price_sol=round(price_sol, 9),
            creator_wallet=creator_wallet,
            file_id=file_result["file_id"],
            file_url=file_result["file_url"],
            preview_url=file_result["file_url"]
        )
        db.add(new_listing)
        db.commit()
        db.refresh(new_listing)
        return new_listing

    except ValidationError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        db.rollback()
        print(f"❌ Listing creation failed: {e}")
        raise HTTPException(500, f"Failed to create listing: {str(e)}")


@app.get("/api/listings/", response_model=List[ListingResponse])
async def list_listings(skip: int = 0, limit: int = 50, creator_wallet: Optional[str] = None,
                        is_active: bool = True, db: Session = Depends(get_db)):
    query = db.query(Listing)
    if creator_wallet:
        if not is_valid_solana_address(creator_wallet):
            raise HTTPException(400, "Invalid wallet address")
        query = query.filter(Listing.creator_wallet == creator_wallet)

    if is_active is not None:
        query = query.filter(Listing.is_active == is_active)

    return query.order_by(Listing.created_at.desc()).offset(skip).limit(limit).all()


@app.get("/api/listings/{listing_id}", response_model=ListingDetailResponse)
async def get_listing(listing_id: str, db: Session = Depends(get_db)):
    listing = db.query(Listing).filter(Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(404, "Listing not found")
    return listing


@app.delete("/api/listings/{listing_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_listing(listing_id: str, creator_wallet: str, db: Session = Depends(get_db)):
    listing = db.query(Listing).filter(Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(404, "Listing not found")
    if listing.creator_wallet != creator_wallet:
        raise HTTPException(403, "Not authorized to delete this listing")

    listing.is_active = False
    db.commit()
    return None


@app.get("/api/listings/creator/{wallet_address}/sales", response_model=CreatorStats)
async def get_creator_stats(wallet_address: str, db: Session = Depends(get_db)):
    if not is_valid_solana_address(wallet_address):
        raise HTTPException(400, "Invalid wallet address")

    creator = db.query(User).filter(User.wallet_address == wallet_address).first()
    if not creator:
        raise HTTPException(404, "Creator not found")

    purchases = db.query(Purchase).join(Listing).filter(
        Listing.creator_wallet == wallet_address,
        Purchase.status == "confirmed"
    ).all()

    total_sales = len(purchases)
    total_earnings = sum(p.amount_sol for p in purchases)
    active_listings = db.query(Listing).filter(
        Listing.creator_wallet == wallet_address,
        Listing.is_active == True
    ).count()
    recent_sales = db.query(Purchase).join(Listing).filter(
        Listing.creator_wallet == wallet_address,
        Purchase.status == "confirmed"
    ).order_by(Purchase.confirmed_at.desc()).limit(10).all()

    return CreatorStats(
        total_sales=total_sales,
        total_earnings_sol=round(total_earnings, 9),
        active_listings=active_listings,
        recent_sales=recent_sales
    )

# --------------------------------------------------------------------
# 💳 PURCHASES ENDPOINTS
# --------------------------------------------------------------------
@app.post("/", response_model=PurchaseInitResponse)
async def initiate_purchase(
    purchase_data: PurchaseCreate,
    db: Session = Depends(get_db)
):
    """
    Initiate a purchase - creates transaction data for frontend to sign
    """
    # Validate wallet address
    if not is_valid_solana_address(purchase_data.buyer_wallet):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid buyer wallet address"
        )
    
    # Get listing
    listing = db.query(Listing).filter(
        Listing.id == purchase_data.listing_id,
        Listing.is_active == True
    ).first()
    
    if not listing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Listing not found or inactive"
        )
    
    # Check if already purchased
    existing_purchase = db.query(Purchase).filter(
        Purchase.listing_id == purchase_data.listing_id,
        Purchase.buyer_wallet == purchase_data.buyer_wallet,
        Purchase.status == TransactionStatus.CONFIRMED
    ).first()
    
    if existing_purchase:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You already own this artwork"
        )
    
    # Ensure buyer exists
    buyer = db.query(User).filter(User.wallet_address == purchase_data.buyer_wallet).first()
    if not buyer:
        buyer = User(
            wallet_address=purchase_data.buyer_wallet,
            role=UserRole.BUYER
        )
        db.add(buyer)
        db.commit()
    
    try:
        # Create Solana transfer transaction
        transaction_data = await solana_service.create_transfer_transaction(
            from_wallet=purchase_data.buyer_wallet,
            to_wallet=listing.creator_wallet,
            amount_sol=listing.price_sol
        )
        
        # Use Sanctum Gateway for optimization if enabled
        from backend.services.gateway_service import gateway_service
        if gateway_service.enabled:
            # Get priority fee recommendation
            priority_fee = await gateway_service.get_priority_fee_estimate()
            if priority_fee:
                transaction_data['priority_fee'] = priority_fee
                transaction_data['optimized'] = True
        
        return PurchaseInitResponse(
            transaction_data=transaction_data,
            listing=listing,
            amount_sol=listing.price_sol
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create transaction: {str(e)}"
        )

@app.post("/confirm", response_model=PurchaseResponse)
async def confirm_purchase(
    confirm_data: PurchaseConfirm,
    db: Session = Depends(get_db)
):
    """
    Confirm purchase after transaction is signed and sent
    Verifies the transaction on-chain
    """
    # Get listing
    listing = db.query(Listing).filter(Listing.id == confirm_data.listing_id).first()
    
    if not listing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Listing not found"
        )
    
    # Check if transaction signature already used
    existing = db.query(Purchase).filter(
        Purchase.transaction_signature == confirm_data.transaction_signature
    ).first()
    
    if existing:
        if existing.status == TransactionStatus.CONFIRMED:
            return existing
        elif existing.status == TransactionStatus.PENDING:
            # Re-verify if still pending
            pass
    
    try:
        # Verify transaction on-chain
        is_valid = await solana_service.verify_transaction(
            signature=confirm_data.transaction_signature,
            expected_sender=confirm_data.buyer_wallet,
            expected_receiver=listing.creator_wallet,
            expected_amount_sol=listing.price_sol
        )
        
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Transaction verification failed. Please ensure transaction is confirmed on-chain."
            )
        
        # Create or update purchase record
        if existing:
            existing.status = TransactionStatus.CONFIRMED
            existing.confirmed_at = datetime.utcnow()
            db.commit()
            db.refresh(existing)
            return existing
        else:
            new_purchase = Purchase(
                listing_id=confirm_data.listing_id,
                buyer_wallet=confirm_data.buyer_wallet,
                transaction_signature=confirm_data.transaction_signature,
                amount_sol=listing.price_sol,
                status=TransactionStatus.CONFIRMED,
                confirmed_at=datetime.utcnow()
            )
            
            db.add(new_purchase)
            db.commit()
            db.refresh(new_purchase)
            
            return new_purchase
            
    except HTTPException:
        raise
    except Exception as e:
        # Create pending purchase for retry
        if not existing:
            pending_purchase = Purchase(
                listing_id=confirm_data.listing_id,
                buyer_wallet=confirm_data.buyer_wallet,
                transaction_signature=confirm_data.transaction_signature,
                amount_sol=listing.price_sol,
                status=TransactionStatus.PENDING
            )
            db.add(pending_purchase)
            db.commit()
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to verify transaction: {str(e)}"
        )

@app.get("/unlocked/{buyer_wallet}", response_model=List[UnlockedContent])
async def get_unlocked_content(
    buyer_wallet: str,
    db: Session = Depends(get_db)
):
    """
    Get all unlocked artwork for a buyer
    Returns full IPFS URLs for purchased items
    """
    if not is_valid_solana_address(buyer_wallet):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid wallet address"
        )
    
    # Get all confirmed purchases for this buyer
    purchases = db.query(Purchase).join(Listing).filter(
        Purchase.buyer_wallet == buyer_wallet,
        Purchase.status == TransactionStatus.CONFIRMED
    ).all()
    
    unlocked = []
    for purchase in purchases:
        # Handle both ipfs_url and file_url (for different storage backends)
        file_url = getattr(purchase.listing, 'file_url', None) or getattr(purchase.listing, 'file_url', None)
        file_id = getattr(purchase.listing, 'file_id', None) or purchase.listing.id
        
        unlocked.append(UnlockedContent(
            listing_id=purchase.listing.id,
            title=purchase.listing.title,
            file_url=file_url,
            fie_id=file_id,
            purchased_at=purchase.confirmed_at or purchase.purchased_at
        ))
    
    return unlocked

@app.get("/history/{wallet_address}", response_model=List[PurchaseResponse])
async def get_purchase_history(
    wallet_address: str,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """
    Get purchase history for a wallet (as buyer)
    """
    if not is_valid_solana_address(wallet_address):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid wallet address"
        )
    
    purchases = db.query(Purchase).filter(
        Purchase.buyer_wallet == wallet_address
    ).order_by(Purchase.purchased_at.desc()).offset(skip).limit(limit).all()
    
    return purchases

@app.get("/verify/{transaction_signature}")
async def verify_transaction_status(transaction_signature: str):
    """
    Check the status of a transaction
    """
    try:
        status = await solana_service.get_transaction_status(transaction_signature)
        
        if gateway_service.enabled:
            gateway_status = await gateway_service.get_transaction_status(transaction_signature)
            return {
                "signature": transaction_signature,
                "solana_status": status,
                "gateway_status": gateway_status
            }
        
        return {
            "signature": transaction_signature,
            "status": status
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to check transaction status: {str(e)}"
        )
    try:
        status_ = await solana_service.get_transaction_status(transaction_signature)
        if gateway_service.enabled:
            gateway_status = await gateway_service.get_transaction_status(transaction_signature)
            return {"signature": transaction_signature, "solana_status": status_, "gateway_status": gateway_status}
        return {"signature": transaction_signature, "status": status_}
    except Exception as e:
        raise HTTPException(500, f"Failed to check transaction status: {str(e)}")

# --------------------------------------------------------------------
# 🏠 ROOT & HEALTH
# --------------------------------------------------------------------
@app.get("/")
async def root():
    return {
        "message": "Welcome to PhotoPay API",
        "version": os.getenv("APP_VERSION", "1.0.0"),
        "docs": "/docs",
        "status": "operational"
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy", "database": "connected", "solana": "connected"}

# --------------------------------------------------------------------
# ⚠️ GLOBAL ERROR HANDLER
# --------------------------------------------------------------------
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "error": str(exc) if os.getenv("DEBUG") == "true" else "An error occurred"
        }
    )

# --------------------------------------------------------------------
# 🚀 RUN SERVER
# --------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
