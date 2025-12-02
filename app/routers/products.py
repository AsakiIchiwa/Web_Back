from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from typing import List, Optional

from app.database import get_db
from app.models import Product, ProductStatus
from app.schemas import ProductResponse, ProductWithSupplier

router = APIRouter()

@router.get("/", response_model=List[ProductWithSupplier])
async def list_products(
    search: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[ProductStatus] = ProductStatus.ACTIVE,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    supplier_id: Optional[int] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """List all products (public)"""
    query = select(Product).options(selectinload(Product.supplier))
    
    if status:
        query = query.where(Product.status == status)
    if search:
        query = query.where(Product.name.ilike(f"%{search}%"))
    if category:
        query = query.where(Product.category == category)
    if min_price is not None:
        query = query.where(Product.price >= min_price)
    if max_price is not None:
        query = query.where(Product.price <= max_price)
    if supplier_id:
        query = query.where(Product.supplier_id == supplier_id)
    
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()

@router.get("/categories")
async def get_categories(db: AsyncSession = Depends(get_db)):
    """Get all product categories"""
    result = await db.execute(
        select(Product.category)
        .where(Product.category.isnot(None))
        .distinct()
    )
    categories = [row[0] for row in result.all() if row[0]]
    return {"categories": categories}

@router.get("/{product_id}", response_model=ProductWithSupplier)
async def get_product(product_id: int, db: AsyncSession = Depends(get_db)):
    """Get product by ID"""
    result = await db.execute(
        select(Product)
        .options(selectinload(Product.supplier))
        .where(Product.id == product_id)
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product
