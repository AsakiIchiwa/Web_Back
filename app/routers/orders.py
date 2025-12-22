import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query  # <-- Thêm Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from datetime import datetime
from pathlib import Path

from app.database import get_db
from app.models import (
    User, Supplier, Shop, Contract, ContractStatus, 
    Order, OrderStatus, PaymentMethod, SupplierPaymentInfo
)
from app.schemas import OrderCreate, OrderResponse, OrderWithDetails, PaymentInfoCreate, PaymentInfoResponse
from app.auth import get_current_user, get_supplier_user, get_shop_user

router = APIRouter()

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


def generate_order_code():
    now = datetime.now()
    random_part = uuid.uuid4().hex[:4].upper()
    return f"ORD-{now.strftime('%Y%m%d')}-{random_part}"


# ==================== PAYMENT INFO ENDPOINTS (PHẢI ĐẶT TRƯỚC /{order_id}) ====================

@router.get("/payment-info/me")
async def get_my_payment_info(
    current_user: User = Depends(get_supplier_user),
    db: AsyncSession = Depends(get_db)
):
    """Get current supplier's payment info"""
    result = await db.execute(select(Supplier).where(Supplier.user_id == current_user.id))
    supplier = result.scalar_one_or_none()
    
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    
    result = await db.execute(
        select(SupplierPaymentInfo).where(SupplierPaymentInfo.supplier_id == supplier.id)
    )
    payment_info = result.scalar_one_or_none()
    
    if not payment_info:
        return {
            "id": None,
            "supplier_id": supplier.id,
            "bank_name": None,
            "bank_account": None,
            "account_holder": None,
            "qr_code_url": None
        }
    
    return {
        "id": payment_info.id,
        "supplier_id": payment_info.supplier_id,
        "bank_name": payment_info.bank_name,
        "bank_account": payment_info.bank_account,
        "account_holder": payment_info.account_holder,
        "qr_code_url": payment_info.qr_code_url
    }


@router.post("/payment-info/me")
async def create_my_payment_info(
    data: PaymentInfoCreate,
    current_user: User = Depends(get_supplier_user),
    db: AsyncSession = Depends(get_db)
):
    """Create/Update current supplier's payment info (POST)"""
    return await _update_payment_info(data, current_user, db)


@router.put("/payment-info/me")
async def update_my_payment_info_put(
    data: PaymentInfoCreate,
    current_user: User = Depends(get_supplier_user),
    db: AsyncSession = Depends(get_db)
):
    """Update current supplier's payment info (PUT)"""
    return await _update_payment_info(data, current_user, db)


@router.patch("/payment-info/me")
async def update_my_payment_info_patch(
    data: PaymentInfoCreate,
    current_user: User = Depends(get_supplier_user),
    db: AsyncSession = Depends(get_db)
):
    """Update current supplier's payment info (PATCH)"""
    return await _update_payment_info(data, current_user, db)


async def _update_payment_info(data: PaymentInfoCreate, current_user: User, db: AsyncSession):
    """Helper function to update payment info"""
    result = await db.execute(select(Supplier).where(Supplier.user_id == current_user.id))
    supplier = result.scalar_one_or_none()
    
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    
    result = await db.execute(
        select(SupplierPaymentInfo).where(SupplierPaymentInfo.supplier_id == supplier.id)
    )
    payment_info = result.scalar_one_or_none()
    
    if not payment_info:
        payment_info = SupplierPaymentInfo(supplier_id=supplier.id)
        db.add(payment_info)
    
    if data.bank_name is not None:
        payment_info.bank_name = data.bank_name
    if data.bank_account is not None:
        payment_info.bank_account = data.bank_account
    if data.account_holder is not None:
        payment_info.account_holder = data.account_holder
    if data.qr_code_url is not None:
        payment_info.qr_code_url = data.qr_code_url
    
    payment_info.updated_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(payment_info)
    
    return {
        "id": payment_info.id,
        "supplier_id": payment_info.supplier_id,
        "bank_name": payment_info.bank_name,
        "bank_account": payment_info.bank_account,
        "account_holder": payment_info.account_holder,
        "qr_code_url": payment_info.qr_code_url
    }


@router.post("/payment-info/qr-code")
async def upload_qr_code(
    file: UploadFile = File(...),
    current_user: User = Depends(get_supplier_user),
    db: AsyncSession = Depends(get_db)
):
    """Upload QR code image"""
    result = await db.execute(select(Supplier).where(Supplier.user_id == current_user.id))
    supplier = result.scalar_one_or_none()
    
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    
    file_ext = file.filename.split(".")[-1] if file.filename else "png"
    filename = f"qr_{supplier.id}_{uuid.uuid4().hex[:8]}.{file_ext}"
    file_path = UPLOAD_DIR / "qrcodes" / filename
    file_path.parent.mkdir(parents=True, exist_ok=True)
    
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)
    
    qr_url = f"/uploads/qrcodes/{filename}"
    
    result = await db.execute(
        select(SupplierPaymentInfo).where(SupplierPaymentInfo.supplier_id == supplier.id)
    )
    payment_info = result.scalar_one_or_none()
    
    if not payment_info:
        payment_info = SupplierPaymentInfo(supplier_id=supplier.id, qr_code_url=qr_url)
        db.add(payment_info)
    else:
        payment_info.qr_code_url = qr_url
    
    payment_info.updated_at = datetime.utcnow()
    await db.commit()
    
    return {"message": "QR code uploaded", "url": qr_url}


@router.get("/payment-info/{supplier_id}")
async def get_supplier_payment_info(
    supplier_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get supplier's payment info by ID"""
    result = await db.execute(
        select(SupplierPaymentInfo).where(SupplierPaymentInfo.supplier_id == supplier_id)
    )
    payment_info = result.scalar_one_or_none()
    
    if not payment_info:
        return {
            "id": None,
            "supplier_id": supplier_id,
            "bank_name": None,
            "bank_account": None,
            "account_holder": None,
            "qr_code_url": None
        }
    
    return {
        "id": payment_info.id,
        "supplier_id": payment_info.supplier_id,
        "bank_name": payment_info.bank_name,
        "bank_account": payment_info.bank_account,
        "account_holder": payment_info.account_holder,
        "qr_code_url": payment_info.qr_code_url
    }


# ==================== ORDER ENDPOINTS (SAU PAYMENT INFO) ====================

@router.get("/")
async def get_orders(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get all orders for current user"""
    query = select(Order).options(
        selectinload(Order.contract).selectinload(Contract.product),
        selectinload(Order.supplier),
        selectinload(Order.shop)
    )
    
    if current_user.role.value == "supplier":
        result = await db.execute(select(Supplier).where(Supplier.user_id == current_user.id))
        supplier = result.scalar_one_or_none()
        if supplier:
            query = query.where(Order.supplier_id == supplier.id)
    elif current_user.role.value == "shop":
        result = await db.execute(select(Shop).where(Shop.user_id == current_user.id))
        shop = result.scalar_one_or_none()
        if shop:
            query = query.where(Order.shop_id == shop.id)
    
    query = query.order_by(Order.created_at.desc())
    result = await db.execute(query)
    orders = result.scalars().all()
    
    orders_data = []
    for order in orders:
        order_dict = {
            "id": order.id,
            "order_code": order.order_code,
            "contract_id": order.contract_id,
            "supplier_id": order.supplier_id,
            "shop_id": order.shop_id,
            "quantity": order.quantity,
            "unit_price": float(order.unit_price) if order.unit_price else 0,
            "total_amount": float(order.total_amount) if order.total_amount else 0,
            "shipping_address": order.shipping_address,
            "note": order.note,
            "status": order.status.value if order.status else "pending",
            "payment_method": order.payment_method.value if order.payment_method else "bank_transfer",
            "payment_proof": order.payment_proof,
            "paid_at": order.paid_at.isoformat() if order.paid_at else None,
            "created_at": order.created_at.isoformat() if order.created_at else None,
            "updated_at": order.updated_at.isoformat() if order.updated_at else None,
            "contract": {
                "id": order.contract.id,
                "contract_code": getattr(order.contract, 'contract_code', None),
                "agreed_price": float(order.contract.agreed_price) if order.contract.agreed_price else 0,
                "status": order.contract.status.value if order.contract.status else None,
                "product": {
                    "id": order.contract.product.id,
                    "name": order.contract.product.name,
                    "image_url": order.contract.product.image_url,
                } if order.contract.product else None
            } if order.contract else None,
            "supplier": {
                "id": order.supplier.id,
                "company_name": order.supplier.company_name,
                "phone": order.supplier.phone,
                "address": order.supplier.address,
            } if order.supplier else None,
            "shop": {
                "id": order.shop.id,
                "shop_name": order.shop.shop_name,
                "phone": order.shop.phone,
                "address": order.shop.address,
            } if order.shop else None,
        }
        orders_data.append(order_dict)
    
    return orders_data


@router.post("/", response_model=OrderResponse)
async def create_order(
    data: OrderCreate,
    current_user: User = Depends(get_shop_user),
    db: AsyncSession = Depends(get_db)
):
    """Create new order from contract (Shop only)"""
    result = await db.execute(select(Shop).where(Shop.user_id == current_user.id))
    shop = result.scalar_one_or_none()
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")
    
    result = await db.execute(
        select(Contract).where(Contract.id == data.contract_id)
    )
    contract = result.scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    
    if contract.shop_id != shop.id:
        raise HTTPException(status_code=403, detail="Contract does not belong to you")
    
    if contract.status != ContractStatus.ACTIVE:
        raise HTTPException(status_code=400, detail="Contract is not active")
    
    order = Order(
        order_code=generate_order_code(),
        contract_id=contract.id,
        supplier_id=contract.supplier_id,
        shop_id=shop.id,
        quantity=data.quantity,
        unit_price=contract.agreed_price,
        total_amount=contract.agreed_price * data.quantity,
        shipping_address=data.shipping_address,
        note=data.note,
        status=OrderStatus.PENDING,
        payment_method=data.payment_method or PaymentMethod.BANK_TRANSFER,
    )
    
    db.add(order)
    await db.commit()
    await db.refresh(order)
    
    return order


@router.get("/{order_id}")
async def get_order(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get order by ID"""
    result = await db.execute(
        select(Order)
        .options(
            selectinload(Order.contract).selectinload(Contract.product),
            selectinload(Order.supplier),
            selectinload(Order.shop)
        )
        .where(Order.id == order_id)
    )
    order = result.scalar_one_or_none()
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    return {
        "id": order.id,
        "order_code": order.order_code,
        "contract_id": order.contract_id,
        "supplier_id": order.supplier_id,
        "shop_id": order.shop_id,
        "quantity": order.quantity,
        "unit_price": float(order.unit_price) if order.unit_price else 0,
        "total_amount": float(order.total_amount) if order.total_amount else 0,
        "shipping_address": order.shipping_address,
        "note": order.note,
        "status": order.status.value if order.status else "pending",
        "payment_method": order.payment_method.value if order.payment_method else "bank_transfer",
        "payment_proof": order.payment_proof,
        "paid_at": order.paid_at.isoformat() if order.paid_at else None,
        "created_at": order.created_at.isoformat() if order.created_at else None,
        "updated_at": order.updated_at.isoformat() if order.updated_at else None,
        "contract": {
            "id": order.contract.id,
            "contract_code": getattr(order.contract, 'contract_code', None),
            "agreed_price": float(order.contract.agreed_price) if order.contract.agreed_price else 0,
            "status": order.contract.status.value if order.contract.status else None,
            "product": {
                "id": order.contract.product.id,
                "name": order.contract.product.name,
                "image_url": order.contract.product.image_url,
            } if order.contract.product else None
        } if order.contract else None,
        "supplier": {
            "id": order.supplier.id,
            "company_name": order.supplier.company_name,
            "phone": order.supplier.phone,
            "address": order.supplier.address,
        } if order.supplier else None,
        "shop": {
            "id": order.shop.id,
            "shop_name": order.shop.shop_name,
            "phone": order.shop.phone,
            "address": order.shop.address,
        } if order.shop else None,
    }


@router.patch("/{order_id}/status")
async def update_order_status(
    order_id: int,
    new_status: str = Query(...),  # <-- Nhận từ query param
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update order status"""
    result = await db.execute(
        select(Order).where(Order.id == order_id)
    )
    order = result.scalar_one_or_none()
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Check permission
    if current_user.role.value == "supplier":
        supplier_result = await db.execute(
            select(Supplier).where(Supplier.user_id == current_user.id)
        )
        supplier = supplier_result.scalar_one_or_none()
        if not supplier or order.supplier_id != supplier.id:
            raise HTTPException(status_code=403, detail="Access denied")
    elif current_user.role.value == "shop":
        shop_result = await db.execute(
            select(Shop).where(Shop.user_id == current_user.id)
        )
        shop = shop_result.scalar_one_or_none()
        if not shop or order.shop_id != shop.id:
            raise HTTPException(status_code=403, detail="Access denied")
    
    # Convert string to enum
    try:
        status = OrderStatus(new_status)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid status: {new_status}. Valid: pending, confirmed, processing, shipped, delivered, cancelled, paid")
    
    order.status = status
    order.updated_at = datetime.utcnow()
    
    if status == OrderStatus.PAID:
        order.paid_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(order)
    
    return {"message": "Order status updated", "status": order.status.value}


@router.post("/{order_id}/payment-proof")
async def upload_payment_proof(
    order_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_shop_user),
    db: AsyncSession = Depends(get_db)
):
    """Upload payment proof (Shop only)"""
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    file_ext = file.filename.split(".")[-1] if file.filename else "png"
    filename = f"payment_{order.order_code}_{uuid.uuid4().hex[:8]}.{file_ext}"
    file_path = UPLOAD_DIR / "payments" / filename
    file_path.parent.mkdir(parents=True, exist_ok=True)
    
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)
    
    order.payment_proof = f"/uploads/payments/{filename}"
    order.status = OrderStatus.PAID
    order.paid_at = datetime.utcnow()
    
    await db.commit()
    
    return {"message": "Payment proof uploaded", "url": order.payment_proof}