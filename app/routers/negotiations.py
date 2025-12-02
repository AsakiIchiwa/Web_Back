from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from app.database import get_db
from app.models import User, Supplier, Shop, Negotiation
from app.schemas import NegotiationCreate, NegotiationResponse
from app.auth import get_current_user

router = APIRouter()

@router.post("/", response_model=NegotiationResponse)
async def create_negotiation(
    data: NegotiationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Send negotiation message"""
    # Get sender ID based on role
    sender_id = current_user.id
    if current_user.role.value == "supplier":
        result = await db.execute(
            select(Supplier).where(Supplier.user_id == current_user.id)
        )
        supplier = result.scalar_one_or_none()
        if supplier:
            sender_id = supplier.id
    elif current_user.role.value == "shop":
        result = await db.execute(
            select(Shop).where(Shop.user_id == current_user.id)
        )
        shop = result.scalar_one_or_none()
        if shop:
            sender_id = shop.id
    
    negotiation = Negotiation(
        rfq_id=data.rfq_id,
        sender_role=current_user.role,
        sender_id=sender_id,
        message=data.message,
        proposed_price=data.proposed_price
    )
    db.add(negotiation)
    await db.commit()
    await db.refresh(negotiation)
    return negotiation

@router.get("/{rfq_id}", response_model=List[NegotiationResponse])
async def get_negotiations(
    rfq_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get all negotiations for an RFQ"""
    result = await db.execute(
        select(Negotiation)
        .where(Negotiation.rfq_id == rfq_id)
        .order_by(Negotiation.created_at.asc())
    )
    return result.scalars().all()
