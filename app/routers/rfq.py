from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import List

from app.database import get_db
from app.models import User, Supplier, RFQ, RFQStatus, Product
from app.schemas import RFQResponse, RFQWithDetails
from app.auth import get_current_user

router = APIRouter()

@router.get("/", response_model=List[RFQWithDetails])
async def list_rfqs(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List RFQs relevant to current user"""
    query = select(RFQ).options(
        selectinload(RFQ.shop),
        selectinload(RFQ.product).selectinload(Product.supplier),
        selectinload(RFQ.quotes)
    )
    
    if current_user.role.value == "supplier":
        # Get supplier's products RFQs
        result = await db.execute(
            select(Supplier).where(Supplier.user_id == current_user.id)
        )
        supplier = result.scalar_one_or_none()
        if supplier:
            subquery = select(Product.id).where(Product.supplier_id == supplier.id)
            query = query.where(RFQ.product_id.in_(subquery))
    elif current_user.role.value == "shop":
        # Get shop's own RFQs
        from app.models import Shop
        result = await db.execute(
            select(Shop).where(Shop.user_id == current_user.id)
        )
        shop = result.scalar_one_or_none()
        if shop:
            query = query.where(RFQ.shop_id == shop.id)
    
    query = query.order_by(RFQ.created_at.desc())
    result = await db.execute(query)
    return result.scalars().all()

@router.get("/{rfq_id}", response_model=RFQWithDetails)
async def get_rfq(
    rfq_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get RFQ details"""
    result = await db.execute(
        select(RFQ)
        .options(
            selectinload(RFQ.shop),
            selectinload(RFQ.product),
            selectinload(RFQ.quotes)
        )
        .where(RFQ.id == rfq_id)
    )
    rfq = result.scalar_one_or_none()
    if not rfq:
        raise HTTPException(status_code=404, detail="RFQ not found")
    return rfq

@router.patch("/{rfq_id}/status")
async def update_rfq_status(
    rfq_id: int,
    status: RFQStatus,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update RFQ status"""
    result = await db.execute(select(RFQ).where(RFQ.id == rfq_id))
    rfq = result.scalar_one_or_none()
    if not rfq:
        raise HTTPException(status_code=404, detail="RFQ not found")
    
    rfq.status = status
    await db.commit()
    return {"message": "Status updated", "status": status}
