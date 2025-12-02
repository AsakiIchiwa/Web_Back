from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from typing import List, Optional

from app.database import get_db
from app.models import User, Supplier, Product, Quote, UserRole, ProductStatus
from app.schemas import (
    SupplierResponse, SupplierUpdate, SupplierWithUser,
    ProductCreate, ProductResponse, ProductUpdate,
    QuoteCreate, QuoteResponse, QuoteWithDetails
)
from app.auth import get_current_user, get_supplier_user

router = APIRouter()

# ==================== SUPPLIER PROFILE (đặt trước /{supplier_id}) ====================
@router.get("/me", response_model=SupplierResponse)
async def get_my_profile(
    current_user: User = Depends(get_supplier_user),
    db: AsyncSession = Depends(get_db)
):
    """Get supplier's own profile"""
    result = await db.execute(
        select(Supplier).where(Supplier.user_id == current_user.id)
    )
    supplier = result.scalar_one_or_none()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier profile not found")
    return supplier

@router.patch("/me", response_model=SupplierResponse)
async def update_my_profile(
    data: SupplierUpdate,
    current_user: User = Depends(get_supplier_user),
    db: AsyncSession = Depends(get_db)
):
    """Update supplier profile"""
    result = await db.execute(
        select(Supplier).where(Supplier.user_id == current_user.id)
    )
    supplier = result.scalar_one_or_none()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier profile not found")
    
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(supplier, field, value)
    
    await db.commit()
    await db.refresh(supplier)
    return supplier

# ==================== SUPPLIER PRODUCTS (đặt trước /{supplier_id}) ====================
@router.get("/me/products", response_model=List[ProductResponse])
async def get_my_products(
    current_user: User = Depends(get_supplier_user),
    db: AsyncSession = Depends(get_db)
):
    """Get supplier's own products"""
    result = await db.execute(
        select(Supplier).where(Supplier.user_id == current_user.id)
    )
    supplier = result.scalar_one_or_none()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier profile not found")
    
    result = await db.execute(
        select(Product).where(Product.supplier_id == supplier.id)
    )
    return result.scalars().all()

@router.post("/me/products", response_model=ProductResponse)
async def create_product(
    data: ProductCreate,
    current_user: User = Depends(get_supplier_user),
    db: AsyncSession = Depends(get_db)
):
    """Create new product"""
    result = await db.execute(
        select(Supplier).where(Supplier.user_id == current_user.id)
    )
    supplier = result.scalar_one_or_none()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier profile not found")
    
    product = Product(
        supplier_id=supplier.id,
        **data.model_dump()
    )
    db.add(product)
    await db.commit()
    await db.refresh(product)
    return product

@router.patch("/me/products/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: int,
    data: ProductUpdate,
    current_user: User = Depends(get_supplier_user),
    db: AsyncSession = Depends(get_db)
):
    """Update product"""
    result = await db.execute(
        select(Supplier).where(Supplier.user_id == current_user.id)
    )
    supplier = result.scalar_one_or_none()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier profile not found")
    
    result = await db.execute(
        select(Product).where(
            Product.id == product_id,
            Product.supplier_id == supplier.id
        )
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(product, field, value)
    
    await db.commit()
    await db.refresh(product)
    return product

@router.delete("/me/products/{product_id}")
async def delete_product(
    product_id: int,
    current_user: User = Depends(get_supplier_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete product"""
    result = await db.execute(
        select(Supplier).where(Supplier.user_id == current_user.id)
    )
    supplier = result.scalar_one_or_none()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier profile not found")
    
    result = await db.execute(
        select(Product).where(
            Product.id == product_id,
            Product.supplier_id == supplier.id
        )
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    await db.delete(product)
    await db.commit()
    return {"message": "Product deleted"}

# ==================== SUPPLIER QUOTES ====================
@router.get("/me/quotes", response_model=List[QuoteWithDetails])
async def get_received_rfqs(
    current_user: User = Depends(get_supplier_user),
    db: AsyncSession = Depends(get_db)
):
    """Get RFQs received (quotes supplier has made)"""
    result = await db.execute(
        select(Supplier).where(Supplier.user_id == current_user.id)
    )
    supplier = result.scalar_one_or_none()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier profile not found")
    
    result = await db.execute(
        select(Quote)
        .options(selectinload(Quote.rfq), selectinload(Quote.supplier))
        .where(Quote.supplier_id == supplier.id)
    )
    return result.scalars().all()

@router.post("/me/quotes", response_model=QuoteResponse)
async def respond_to_rfq(
    data: QuoteCreate,
    current_user: User = Depends(get_supplier_user),
    db: AsyncSession = Depends(get_db)
):
    """Respond to RFQ with a quote"""
    result = await db.execute(
        select(Supplier).where(Supplier.user_id == current_user.id)
    )
    supplier = result.scalar_one_or_none()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier profile not found")
    
    quote = Quote(
        supplier_id=supplier.id,
        **data.model_dump()
    )
    db.add(quote)
    await db.commit()
    await db.refresh(quote)
    return quote

# ==================== PUBLIC ====================
@router.get("/", response_model=List[SupplierWithUser])
async def list_suppliers(
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db)
):
    """List all suppliers (public)"""
    query = select(Supplier).options(selectinload(Supplier.user))
    
    if search:
        query = query.where(Supplier.company_name.ilike(f"%{search}%"))
    
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()

@router.get("/{supplier_id}", response_model=SupplierWithUser)
async def get_supplier(supplier_id: int, db: AsyncSession = Depends(get_db)):
    """Get supplier by ID"""
    result = await db.execute(
        select(Supplier)
        .options(selectinload(Supplier.user))
        .where(Supplier.id == supplier_id)
    )
    supplier = result.scalar_one_or_none()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return supplier
