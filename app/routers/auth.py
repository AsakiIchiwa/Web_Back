from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime

from app.database import get_db
from app.models import User, Supplier, Shop, UserRole
from app.schemas import Token, LoginRequest, RegisterRequest, UserResponse, UserWithProfile
from app.auth import (
    verify_password, get_password_hash, create_access_token, 
    create_refresh_token, decode_token, get_current_user
)
from app.email import (
    generate_verification_token, get_token_expiry,
    send_verification_email, send_approval_notification
)

router = APIRouter()


@router.post("/register", response_model=UserResponse)
async def register(
    data: RegisterRequest, 
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """Register new user (Supplier or Shop) - requires email verification"""
    # Check if email exists
    result = await db.execute(select(User).where(User.email == data.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Generate verification token
    verification_token = generate_verification_token()
    
    # Create user with verification pending
    user = User(
        email=data.email,
        password_hash=get_password_hash(data.password),
        full_name=data.full_name,
        role=data.role,
        email_verified=False,
        is_approved=False,
        verification_token=verification_token,
        verification_token_expires=get_token_expiry()
    )
    db.add(user)
    await db.flush()
    
    # Create profile based on role
    if data.role == UserRole.SUPPLIER:
        supplier = Supplier(
            user_id=user.id,
            company_name=data.company_name or data.full_name,
            address=data.address,
            phone=data.phone
        )
        db.add(supplier)
    elif data.role == UserRole.SHOP:
        shop = Shop(
            user_id=user.id,
            shop_name=data.shop_name or data.full_name,
            address=data.address,
            phone=data.phone
        )
        db.add(shop)
    
    await db.commit()
    await db.refresh(user)
    
    # Send verification email in background
    background_tasks.add_task(
        send_verification_email,
        to_email=user.email,
        full_name=user.full_name or user.email,
        verification_token=verification_token
    )
    
    return user


@router.get("/verify-email")
async def verify_email(token: str, db: AsyncSession = Depends(get_db)):
    """Verify email with token"""
    result = await db.execute(
        select(User).where(User.verification_token == token)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=400, detail="Invalid verification token")
    
    if user.email_verified:
        return {
            "message": "Email already verified", 
            "status": "already_verified",
            "email": user.email
        }
    
    # Check if token expired
    if user.verification_token_expires and user.verification_token_expires.replace(tzinfo=None) < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Verification token expired. Please request a new one.")
    
    # Mark email as verified
    user.email_verified = True
    user.verification_token = None
    user.verification_token_expires = None
    
    await db.commit()
    
    return {
        "message": "Email verified successfully! Please wait for admin approval.",
        "status": "verified",
        "email": user.email,
        "awaiting_approval": not user.is_approved
    }


@router.post("/resend-verification")
async def resend_verification(
    email: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """Resend verification email"""
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.email_verified:
        raise HTTPException(status_code=400, detail="Email already verified")
    
    # Generate new token
    verification_token = generate_verification_token()
    user.verification_token = verification_token
    user.verification_token_expires = get_token_expiry()
    
    await db.commit()
    
    # Send email in background
    background_tasks.add_task(
        send_verification_email,
        to_email=user.email,
        full_name=user.full_name or user.email,
        verification_token=verification_token
    )
    
    return {"message": "Verification email sent"}


@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    """Login and get access token"""
    result = await db.execute(select(User).where(User.email == form_data.username))
    user = result.scalar_one_or_none()
    
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Check email verification (skip for admin)
    if user.role != UserRole.ADMIN and not user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Please verify your email first. Check your inbox for verification link."
        )
    
    # Check admin approval (skip for admin)
    if user.role != UserRole.ADMIN and not user.is_approved:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account is pending admin approval. You will receive an email once approved."
        )
    
    # Convert user.id to string for JWT
    access_token = create_access_token(data={"sub": str(user.id), "role": user.role.value})
    refresh_token = create_refresh_token(data={"sub": str(user.id), "role": user.role.value})
    
    return Token(access_token=access_token, refresh_token=refresh_token)


@router.post("/login/json", response_model=Token)
async def login_json(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Login with JSON body"""
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()
    
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    # Check email verification (skip for admin)
    if user.role != UserRole.ADMIN and not user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Please verify your email first. Check your inbox for verification link."
        )
    
    # Check admin approval (skip for admin)
    if user.role != UserRole.ADMIN and not user.is_approved:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account is pending admin approval. You will receive an email once approved."
        )
    
    # Convert user.id to string for JWT
    access_token = create_access_token(data={"sub": str(user.id), "role": user.role.value})
    refresh_token = create_refresh_token(data={"sub": str(user.id), "role": user.role.value})
    
    return Token(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=Token)
async def refresh_token(refresh_token: str, db: AsyncSession = Depends(get_db)):
    """Get new access token using refresh token"""
    token_data = decode_token(refresh_token)
    if not token_data:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    
    result = await db.execute(select(User).where(User.id == token_data.user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    
    # Convert user.id to string for JWT
    access_token = create_access_token(data={"sub": str(user.id), "role": user.role.value})
    new_refresh_token = create_refresh_token(data={"sub": str(user.id), "role": user.role.value})
    
    return Token(access_token=access_token, refresh_token=new_refresh_token)


@router.get("/check-status")
async def check_account_status(email: str, db: AsyncSession = Depends(get_db)):
    """Check account verification and approval status"""
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {
        "email": user.email,
        "email_verified": user.email_verified,
        "is_approved": user.is_approved,
        "role": user.role.value,
        "status": "active" if (user.email_verified and user.is_approved) else "pending"
    }
