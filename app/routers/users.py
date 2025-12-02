from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import User
from app.schemas import UserResponse, UserUpdate, UserWithProfile
from app.auth import get_current_user

router = APIRouter()

@router.get("/me", response_model=UserWithProfile)
async def get_current_user_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get current user profile with supplier/shop details"""
    result = await db.execute(
        select(User)
        .options(selectinload(User.supplier), selectinload(User.shop))
        .where(User.id == current_user.id)
    )
    user = result.scalar_one_or_none()
    return user

@router.patch("/me", response_model=UserResponse)
async def update_current_user(
    data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update current user profile"""
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(current_user, field, value)
    
    await db.commit()
    await db.refresh(current_user)
    return current_user
