from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from typing import List, Optional
from pydantic import BaseModel

from app.database import get_db
from app.models import User, Product, ProductStatus, Contract, RFQ, Supplier, Shop, UserRole
from app.schemas import ProductResponse, ProductUpdate, UserResponse, SupplierWithUser, ShopWithUser
from app.auth import get_current_user, get_admin_user
from app.email import send_approval_notification

router = APIRouter()


class RejectRequest(BaseModel):
    reason: Optional[str] = None


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
    
    # Count pending user approvals
    pending_users = await db.execute(
        select(func.count(User.id)).where(
            User.email_verified == True,
            User.is_approved == False,
            User.role != UserRole.ADMIN
        )
    )
    
    return {
        "total_users": users_count.scalar(),
        "total_suppliers": suppliers_count.scalar(),
        "total_shops": shops_count.scalar(),
        "total_products": products_count.scalar(),
        "pending_products": pending_products.scalar(),
        "pending_users": pending_users.scalar(),
        "total_contracts": contracts_count.scalar(),
        "total_rfqs": rfqs_count.scalar()
    }


# ==================== USER APPROVAL ====================

@router.get("/users/pending", response_model=List[UserResponse])
async def get_pending_users(
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Get users pending approval (email verified but not approved)"""
    result = await db.execute(
        select(User)
        .where(
            User.email_verified == True,
            User.is_approved == False,
            User.role != UserRole.ADMIN
        )
        .order_by(User.created_at.desc())
    )
    return result.scalars().all()


@router.get("/users/unverified", response_model=List[UserResponse])
async def get_unverified_users(
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Get users with unverified email"""
    result = await db.execute(
        select(User)
        .where(
            User.email_verified == False,
            User.role != UserRole.ADMIN
        )
        .order_by(User.created_at.desc())
    )
    return result.scalars().all()


@router.patch("/users/{user_id}/verify-email", response_model=UserResponse)
async def admin_verify_email(
    user_id: int,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Admin manually verify user email (for testing/support)"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.email_verified:
        raise HTTPException(status_code=400, detail="Email already verified")
    
    user.email_verified = True
    user.verification_token = None
    user.verification_token_expires = None
    
    await db.commit()
    await db.refresh(user)
    return user


@router.patch("/users/{user_id}/approve", response_model=UserResponse)
async def approve_user(
    user_id: int,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Approve user account"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.role == UserRole.ADMIN:
        raise HTTPException(status_code=400, detail="Cannot modify admin user")
    
    if user.is_approved:
        raise HTTPException(status_code=400, detail="User already approved")
    
    if not user.email_verified:
        raise HTTPException(status_code=400, detail="User email not verified yet")
    
    user.is_approved = True
    user.rejected_reason = None
    await db.commit()
    await db.refresh(user)
    
    # Send approval notification email
    background_tasks.add_task(
        send_approval_notification,
        to_email=user.email,
        full_name=user.full_name or user.email,
        approved=True
    )
    
    return user


@router.patch("/users/{user_id}/reject")
async def reject_user(
    user_id: int,
    data: RejectRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Reject user account"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.role == UserRole.ADMIN:
        raise HTTPException(status_code=400, detail="Cannot modify admin user")
    
    user.is_approved = False
    user.rejected_reason = data.reason
    await db.commit()
    
    # Send rejection notification email
    background_tasks.add_task(
        send_approval_notification,
        to_email=user.email,
        full_name=user.full_name or user.email,
        approved=False,
        rejected_reason=data.reason
    )
    
    return {"message": "User rejected", "user_id": user_id}


# ==================== PRODUCTS ====================

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


# ==================== USERS LIST ====================

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


@router.get("/rfqs")
async def list_all_rfqs(
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """List all RFQs with full details (admin)"""
    from app.models import Quote
    
    result = await db.execute(
        select(RFQ).options(
            selectinload(RFQ.product).selectinload(Product.supplier).selectinload(Supplier.user),
            selectinload(RFQ.shop).selectinload(Shop.user),
            selectinload(RFQ.quotes).selectinload(Quote.supplier)
        ).order_by(RFQ.created_at.desc())
    )
    rfqs = result.scalars().all()
    
    return [
        {
            "id": rfq.id,
            "product_id": rfq.product_id,
            "shop_id": rfq.shop_id,
            "quantity": rfq.quantity,
            "target_price": rfq.target_price,
            "message": rfq.message,
            "status": rfq.status.value if rfq.status else "pending",
            "created_at": rfq.created_at.isoformat() if rfq.created_at else None,
            "product": {
                "id": rfq.product.id,
                "name": rfq.product.name,
                "category": rfq.product.category,
                "unit": rfq.product.unit,
                "supplier": {
                    "id": rfq.product.supplier.id,
                    "company_name": rfq.product.supplier.company_name,
                    "phone": rfq.product.supplier.phone,
                    "user": {
                        "id": rfq.product.supplier.user.id,
                        "full_name": rfq.product.supplier.user.full_name,
                        "email": rfq.product.supplier.user.email,
                    } if rfq.product.supplier.user else None
                } if rfq.product.supplier else None
            } if rfq.product else None,
            "shop": {
                "id": rfq.shop.id,
                "shop_name": rfq.shop.shop_name,
                "phone": rfq.shop.phone,
                "address": rfq.shop.address,
                "user": {
                    "id": rfq.shop.user.id,
                    "full_name": rfq.shop.user.full_name,
                    "email": rfq.shop.user.email,
                    "phone": rfq.shop.user.phone,
                } if rfq.shop.user else None
            } if rfq.shop else None,
            "quotes": [
                {
                    "id": q.id,
                    "price_per_unit": q.price_per_unit,
                    "delivery_time": q.delivery_time,
                    "note": q.note,
                    "status": q.status.value if q.status else "pending",
                    "created_at": q.created_at.isoformat() if q.created_at else None,
                    "supplier": {
                        "company_name": q.supplier.company_name if q.supplier else None
                    }
                }
                for q in rfq.quotes
            ] if rfq.quotes else []
        }
        for rfq in rfqs
    ]


@router.get("/contracts")
async def list_all_contracts(
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """List all contracts with full details (admin)"""
    result = await db.execute(
        select(Contract).options(
            selectinload(Contract.product),
            selectinload(Contract.supplier).selectinload(Supplier.user),
            selectinload(Contract.shop).selectinload(Shop.user)
        ).order_by(Contract.created_at.desc())
    )
    contracts = result.scalars().all()
    
    return [
        {
            "id": c.id,
            "quantity": c.quantity,
            "agreed_price": c.agreed_price,
            "status": c.status.value if c.status else "draft",
            "start_date": c.start_date.isoformat() if c.start_date else None,
            "end_date": c.end_date.isoformat() if c.end_date else None,
            "terms": c.terms,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "product": {
                "id": c.product.id,
                "name": c.product.name,
                "category": c.product.category,
                "unit": c.product.unit,
            } if c.product else None,
            "supplier": {
                "id": c.supplier.id,
                "company_name": c.supplier.company_name,
                "phone": c.supplier.phone,
                "address": c.supplier.address,
                "user": {
                    "id": c.supplier.user.id,
                    "full_name": c.supplier.user.full_name,
                    "email": c.supplier.user.email,
                } if c.supplier.user else None
            } if c.supplier else None,
            "shop": {
                "id": c.shop.id,
                "shop_name": c.shop.shop_name,
                "phone": c.shop.phone,
                "address": c.shop.address,
                "user": {
                    "id": c.shop.user.id,
                    "full_name": c.shop.user.full_name,
                    "email": c.shop.user.email,
                } if c.shop.user else None
            } if c.shop else None,
        }
        for c in contracts
    ]
