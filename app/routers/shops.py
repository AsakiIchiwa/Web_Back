from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import List, Optional

from app.database import get_db
from app.models import User, Shop, Supplier, Product, RFQ, Contract, UserRole, ProductStatus, RFQStatus
from app.schemas import (
    ShopResponse, ShopUpdate,
    ProductResponse, ProductWithSupplier,
    SupplierWithUser,
    RFQCreate, RFQResponse, RFQWithDetails,
    ContractCreate, ContractResponse,
    NegotiationCreate, NegotiationResponse
)
from app.auth import get_current_user, get_shop_user

router = APIRouter()

# ==================== SEARCH ====================
@router.get("/products", response_model=List[ProductWithSupplier])
async def search_products(
    search: Optional[str] = None,
    category: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    skip: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db)
):
    """Search products (for shop)"""
    query = select(Product).options(selectinload(Product.supplier)).where(
        Product.status == ProductStatus.ACTIVE
    )
    
    if search:
        query = query.where(Product.name.ilike(f"%{search}%"))
    if category:
        query = query.where(Product.category == category)
    if min_price is not None:
        query = query.where(Product.price >= min_price)
    if max_price is not None:
        query = query.where(Product.price <= max_price)
    
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()

@router.get("/suppliers", response_model=List[SupplierWithUser])
async def search_suppliers(
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db)
):
    """Search suppliers (for shop)"""
    query = select(Supplier).options(selectinload(Supplier.user))
    
    if search:
        query = query.where(Supplier.company_name.ilike(f"%{search}%"))
    
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()

# ==================== RFQ ====================
@router.post("/rfq", response_model=RFQResponse)
async def create_rfq(
    data: RFQCreate,
    current_user: User = Depends(get_shop_user),
    db: AsyncSession = Depends(get_db)
):
    """Create Request for Quotation"""
    result = await db.execute(
        select(Shop).where(Shop.user_id == current_user.id)
    )
    shop = result.scalar_one_or_none()
    if not shop:
        raise HTTPException(status_code=404, detail="Shop profile not found")
    
    # Verify product exists
    result = await db.execute(
        select(Product).where(Product.id == data.product_id)
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    rfq = RFQ(
        shop_id=shop.id,
        **data.model_dump()
    )
    db.add(rfq)
    await db.commit()
    await db.refresh(rfq)
    return rfq

@router.get("/rfq", response_model=List[RFQWithDetails])
async def get_my_rfqs(
    current_user: User = Depends(get_shop_user),
    db: AsyncSession = Depends(get_db)
):
    """Get shop's RFQs"""
    result = await db.execute(
        select(Shop).where(Shop.user_id == current_user.id)
    )
    shop = result.scalar_one_or_none()
    if not shop:
        raise HTTPException(status_code=404, detail="Shop profile not found")
    
    result = await db.execute(
        select(RFQ)
        .options(
            selectinload(RFQ.shop),
            selectinload(RFQ.product),
            selectinload(RFQ.quotes)
        )
        .where(RFQ.shop_id == shop.id)
        .order_by(RFQ.created_at.desc())
    )
    return result.scalars().all()

@router.get("/rfq/{rfq_id}", response_model=RFQWithDetails)
async def get_rfq(
    rfq_id: int,
    current_user: User = Depends(get_shop_user),
    db: AsyncSession = Depends(get_db)
):
    """Get RFQ details"""
    result = await db.execute(
        select(Shop).where(Shop.user_id == current_user.id)
    )
    shop = result.scalar_one_or_none()
    if not shop:
        raise HTTPException(status_code=404, detail="Shop profile not found")
    
    result = await db.execute(
        select(RFQ)
        .options(
            selectinload(RFQ.shop),
            selectinload(RFQ.product),
            selectinload(RFQ.quotes)
        )
        .where(RFQ.id == rfq_id, RFQ.shop_id == shop.id)
    )
    rfq = result.scalar_one_or_none()
    if not rfq:
        raise HTTPException(status_code=404, detail="RFQ not found")
    return rfq

# ==================== CONTRACTS ====================
@router.post("/contracts", response_model=ContractResponse)
async def create_contract(
    data: ContractCreate,
    current_user: User = Depends(get_shop_user),
    db: AsyncSession = Depends(get_db)
):
    """Create contract (accept quote)"""
    result = await db.execute(
        select(Shop).where(Shop.user_id == current_user.id)
    )
    shop = result.scalar_one_or_none()
    if not shop:
        raise HTTPException(status_code=404, detail="Shop profile not found")
    
    contract = Contract(
        shop_id=shop.id,
        **data.model_dump()
    )
    db.add(contract)
    await db.commit()
    await db.refresh(contract)
    return contract

@router.get("/contracts", response_model=List[ContractResponse])
async def get_my_contracts(
    current_user: User = Depends(get_shop_user),
    db: AsyncSession = Depends(get_db)
):
    """Get shop's contracts"""
    result = await db.execute(
        select(Shop).where(Shop.user_id == current_user.id)
    )
    shop = result.scalar_one_or_none()
    if not shop:
        raise HTTPException(status_code=404, detail="Shop profile not found")
    
    result = await db.execute(
        select(Contract).where(Contract.shop_id == shop.id)
    )
    return result.scalars().all()

# ==================== PROFILE ====================
@router.get("/me", response_model=ShopResponse)
async def get_my_profile(
    current_user: User = Depends(get_shop_user),
    db: AsyncSession = Depends(get_db)
):
    """Get shop profile"""
    result = await db.execute(
        select(Shop).where(Shop.user_id == current_user.id)
    )
    shop = result.scalar_one_or_none()
    if not shop:
        raise HTTPException(status_code=404, detail="Shop profile not found")
    return shop

@router.patch("/me", response_model=ShopResponse)
async def update_my_profile(
    data: ShopUpdate,
    current_user: User = Depends(get_shop_user),
    db: AsyncSession = Depends(get_db)
):
    """Update shop profile"""
    result = await db.execute(
        select(Shop).where(Shop.user_id == current_user.id)
    )
    shop = result.scalar_one_or_none()
    if not shop:
        raise HTTPException(status_code=404, detail="Shop profile not found")
    
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(shop, field, value)
    
    await db.commit()
    await db.refresh(shop)
    return shop
