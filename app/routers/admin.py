from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from typing import List

from app.database import get_db
from app.models import User, Product, ProductStatus, Contract, RFQ, Supplier, Shop
from app.schemas import ProductResponse, ProductUpdate, UserResponse, SupplierWithUser, ShopWithUser
from app.auth import get_current_user, get_admin_user

router = APIRouter()

@router.get("/stats")
async def get_stats(
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Get admin dashboard stats"""
    users_count = await db.execute(select(func.count(User.id)))
    suppliers_count = await db.execute(select(func.count(Supplier.id)))
    shops_count = await db.execute(select(func.count(Shop.id)))
    products_count = await db.execute(select(func.count(Product.id)))
    pending_products = await db.execute(
        select(func.count(Product.id)).where(Product.status == ProductStatus.PENDING)
    )
    contracts_count = await db.execute(select(func.count(Contract.id)))
    rfqs_count = await db.execute(select(func.count(RFQ.id)))
    
    return {
        "total_users": users_count.scalar(),
        "total_suppliers": suppliers_count.scalar(),
        "total_shops": shops_count.scalar(),
        "total_products": products_count.scalar(),
        "pending_products": pending_products.scalar(),
        "total_contracts": contracts_count.scalar(),
        "total_rfqs": rfqs_count.scalar()
    }

@router.get("/products/pending", response_model=List[ProductResponse])
async def get_pending_products(
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Get products pending approval"""
    result = await db.execute(
        select(Product)
        .options(selectinload(Product.supplier))
        .where(Product.status == ProductStatus.PENDING)
    )
    return result.scalars().all()

@router.patch("/products/{product_id}/approve", response_model=ProductResponse)
async def approve_product(
    product_id: int,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Approve product"""
    result = await db.execute(
        select(Product).where(Product.id == product_id)
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    product.status = ProductStatus.ACTIVE
    await db.commit()
    await db.refresh(product)
    return product

@router.patch("/products/{product_id}/reject", response_model=ProductResponse)
async def reject_product(
    product_id: int,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Reject product"""
    result = await db.execute(
        select(Product).where(Product.id == product_id)
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    product.status = ProductStatus.INACTIVE
    await db.commit()
    await db.refresh(product)
    return product

@router.get("/users", response_model=List[UserResponse])
async def list_users(
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """List all users"""
    result = await db.execute(
        select(User).order_by(User.created_at.desc())
    )
    return result.scalars().all()

@router.get("/suppliers", response_model=List[SupplierWithUser])
async def list_all_suppliers(
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """List all suppliers (admin)"""
    result = await db.execute(
        select(Supplier).options(selectinload(Supplier.user))
    )
    return result.scalars().all()

@router.get("/shops", response_model=List[ShopWithUser])
async def list_all_shops(
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """List all shops (admin)"""
    result = await db.execute(
        select(Shop).options(selectinload(Shop.user))
    )
    return result.scalars().all()
