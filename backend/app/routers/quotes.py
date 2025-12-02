from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import List

from app.database import get_db
from app.models import User, Quote, QuoteStatus
from app.schemas import QuoteResponse, QuoteWithDetails, QuoteUpdate
from app.auth import get_current_user

router = APIRouter()

@router.get("/", response_model=List[QuoteWithDetails])
async def list_quotes(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List quotes"""
    result = await db.execute(
        select(Quote)
        .options(selectinload(Quote.supplier), selectinload(Quote.rfq))
        .order_by(Quote.created_at.desc())
    )
    return result.scalars().all()

@router.get("/{quote_id}", response_model=QuoteWithDetails)
async def get_quote(
    quote_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get quote details"""
    result = await db.execute(
        select(Quote)
        .options(selectinload(Quote.supplier), selectinload(Quote.rfq))
        .where(Quote.id == quote_id)
    )
    quote = result.scalar_one_or_none()
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    return quote

@router.patch("/{quote_id}", response_model=QuoteResponse)
async def update_quote_status(
    quote_id: int,
    data: QuoteUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Accept/Reject quote"""
    result = await db.execute(select(Quote).where(Quote.id == quote_id))
    quote = result.scalar_one_or_none()
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    
    quote.status = data.status
    await db.commit()
    await db.refresh(quote)
    return quote
