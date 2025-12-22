from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from typing import List
from datetime import datetime
import uuid
import aiofiles
from pathlib import Path

from app.database import get_db
from app.models import (
    User, Supplier, Shop, Contract, ContractStatus, 
    Order, OrderStatus, OrderTracking, PaymentMethod,
    Notification, NotificationType, SupplierPaymentInfo
)
from app.schemas import (
    OrderCreate, OrderResponse, OrderWithDetails, OrderUpdate,
    OrderTrackingResponse, PaymentInfoCreate, PaymentInfoResponse
)
from app.auth import get_current_user, get_supplier_user, get_shop_user
from app.routers.notifications import create_notification

router = APIRouter()

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

def generate_order_code():
    """Generate unique order code: ORD-YYYYMMDD-XXXX"""
    now = datetime.now()
    random_part = uuid.uuid4().hex[:4].upper()
    return f"ORD-{now.strftime('%Y%m%d')}-{random_part}"

@router.post("/", response_model=OrderResponse)
async def create_order(
    data: OrderCreate,
    current_user: User = Depends(get_shop_user),
    db: AsyncSession = Depends(get_db)
):
    """Create order from contract (Shop only)"""
    # Get shop
    shop_result = await db.execute(
        select(Shop).where(Shop.user_id == current_user.id)
    )
    shop = shop_result.scalar_one_or_none()
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")
    
    # Get contract and verify
    contract_result = await db.execute(
        select(Contract)
        .options(selectinload(Contract.product), selectinload(Contract.supplier))
        .where(Contract.id == data.contract_id)
    )
    contract = contract_result.scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    
    if contract.shop_id != shop.id:
        raise HTTPException(status_code=403, detail="Không có quyền tạo đơn từ hợp đồng này")
    
    if contract.status != ContractStatus.ACTIVE:
        raise HTTPException(status_code=400, detail="Hợp đồng không còn hiệu lực")
    
    # Verify quantity
    if data.quantity > contract.quantity:
        raise HTTPException(status_code=400, detail=f"Số lượng không được vượt quá {contract.quantity}")
    
    # Create order
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
        payment_method=data.payment_method,
        status=OrderStatus.PENDING
    )
    db.add(order)
    await db.flush()
    
    # Create initial tracking
    tracking = OrderTracking(
        order_id=order.id,
        status=OrderStatus.PENDING,
        note="Đơn hàng được tạo",
        updated_by=current_user.id
    )
    db.add(tracking)
    
    # Notify supplier
    await create_notification(
        db=db,
        user_id=contract.supplier.user_id,
        type=NotificationType.ORDER_CREATED,
        title="Đơn hàng mới",
        message=f"Đơn hàng {order.order_code} từ {shop.shop_name}",
        link="/supplier/orders"
    )
    
    await db.commit()
    await db.refresh(order)
    return order

@router.get("/", response_model=List[OrderWithDetails])
async def get_orders(
    status: OrderStatus = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get orders for current user"""
    query = select(Order).options(
        selectinload(Order.contract).selectinload(Contract.product),
        selectinload(Order.supplier).selectinload(Supplier.user),
        selectinload(Order.shop).selectinload(Shop.user),
        selectinload(Order.tracking_history).selectinload(OrderTracking.user)
    )
    
    if current_user.role.value == "supplier":
        supplier_result = await db.execute(
            select(Supplier).where(Supplier.user_id == current_user.id)
        )
        supplier = supplier_result.scalar_one_or_none()
        if supplier:
            query = query.where(Order.supplier_id == supplier.id)
    elif current_user.role.value == "shop":
        shop_result = await db.execute(
            select(Shop).where(Shop.user_id == current_user.id)
        )
        shop = shop_result.scalar_one_or_none()
        if shop:
            query = query.where(Order.shop_id == shop.id)
    
    if status:
        query = query.where(Order.status == status)
    
    query = query.order_by(Order.created_at.desc())
    result = await db.execute(query)
    return result.scalars().all()

@router.get("/{order_id}", response_model=OrderWithDetails)
async def get_order(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get order details"""
    result = await db.execute(
        select(Order)
        .options(
            selectinload(Order.contract).selectinload(Contract.product),
            selectinload(Order.supplier).selectinload(Supplier.user),
            selectinload(Order.shop).selectinload(Shop.user),
            selectinload(Order.tracking_history).selectinload(OrderTracking.user)
        )
        .where(Order.id == order_id)
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Verify access
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
    
    return order

@router.patch("/{order_id}/status", response_model=OrderResponse)
async def update_order_status(
    order_id: int,
    new_status: OrderStatus,
    note: str = None,
    current_user: User = Depends(get_supplier_user),
    db: AsyncSession = Depends(get_db)
):
    """Update order status (Supplier only)"""
    # Get supplier
    supplier_result = await db.execute(
        select(Supplier).where(Supplier.user_id == current_user.id)
    )
    supplier = supplier_result.scalar_one_or_none()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    
    # Get order
    result = await db.execute(
        select(Order)
        .options(selectinload(Order.shop))
        .where(Order.id == order_id, Order.supplier_id == supplier.id)
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Update status
    old_status = order.status
    order.status = new_status
    
    # Create tracking record
    status_notes = {
        OrderStatus.CONFIRMED: "Đơn hàng đã được xác nhận",
        OrderStatus.PAYMENT_PENDING: "Chờ thanh toán",
        OrderStatus.PAID: "Đã nhận thanh toán",
        OrderStatus.PROCESSING: "Đang xử lý đơn hàng",
        OrderStatus.SHIPPING: "Đang vận chuyển",
        OrderStatus.DELIVERED: "Đã giao hàng",
        OrderStatus.COMPLETED: "Đơn hàng hoàn thành",
        OrderStatus.CANCELLED: "Đơn hàng đã hủy"
    }
    
    tracking = OrderTracking(
        order_id=order.id,
        status=new_status,
        note=note or status_notes.get(new_status, "Cập nhật trạng thái"),
        updated_by=current_user.id
    )
    db.add(tracking)
    
    # Notify shop
    await create_notification(
        db=db,
        user_id=order.shop.user_id,
        type=NotificationType.ORDER_UPDATED,
        title="Cập nhật đơn hàng",
        message=f"Đơn hàng {order.order_code}: {status_notes.get(new_status, new_status.value)}",
        link=f"/shop/orders/{order.id}"
    )
    
    await db.commit()
    await db.refresh(order)
    return order

@router.post("/{order_id}/payment-proof")
async def upload_payment_proof(
    order_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_shop_user),
    db: AsyncSession = Depends(get_db)
):
    """Upload payment proof (Shop only)"""
    # Get shop
    shop_result = await db.execute(
        select(Shop).where(Shop.user_id == current_user.id)
    )
    shop = shop_result.scalar_one_or_none()
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")
    
    # Get order
    result = await db.execute(
        select(Order)
        .options(selectinload(Order.supplier))
        .where(Order.id == order_id, Order.shop_id == shop.id)
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Validate file
    ext = Path(file.filename).suffix.lower()
    if ext not in {".jpg", ".jpeg", ".png", ".pdf"}:
        raise HTTPException(status_code=400, detail="File type not allowed")
    
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:  # 10MB
        raise HTTPException(status_code=400, detail="File too large")
    
    # Save file
    filename = f"payment_{order.id}_{uuid.uuid4().hex[:8]}{ext}"
    filepath = UPLOAD_DIR / filename
    async with aiofiles.open(filepath, 'wb') as f:
        await f.write(content)
    
    # Update order
    order.payment_proof = f"/uploads/{filename}"
    order.status = OrderStatus.PAID
    order.paid_at = datetime.now()
    
    # Add tracking
    tracking = OrderTracking(
        order_id=order.id,
        status=OrderStatus.PAID,
        note="Đã tải lên chứng từ thanh toán",
        updated_by=current_user.id
    )
    db.add(tracking)
    
    # Notify supplier
    await create_notification(
        db=db,
        user_id=order.supplier.user_id,
        type=NotificationType.PAYMENT_CONFIRMED,
        title="Thanh toán mới",
        message=f"Đơn hàng {order.order_code} đã được thanh toán",
        link=f"/supplier/orders/{order.id}"
    )
    
    await db.commit()
    
    return {"message": "Payment proof uploaded", "url": order.payment_proof}

# ==================== SUPPLIER PAYMENT INFO ====================
@router.get("/payment-info/me", response_model=PaymentInfoResponse)
async def get_my_payment_info(
    current_user: User = Depends(get_supplier_user),
    db: AsyncSession = Depends(get_db)
):
    """Get supplier's payment info"""
    supplier_result = await db.execute(
        select(Supplier).where(Supplier.user_id == current_user.id)
    )
    supplier = supplier_result.scalar_one_or_none()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    
    result = await db.execute(
        select(SupplierPaymentInfo).where(SupplierPaymentInfo.supplier_id == supplier.id)
    )
    info = result.scalar_one_or_none()
    
    if not info:
        # Create empty record
        info = SupplierPaymentInfo(supplier_id=supplier.id)
        db.add(info)
        await db.commit()
        await db.refresh(info)
    
    return info

@router.put("/payment-info/me", response_model=PaymentInfoResponse)
async def update_my_payment_info(
    data: PaymentInfoCreate,
    current_user: User = Depends(get_supplier_user),
    db: AsyncSession = Depends(get_db)
):
    """Update supplier's payment info"""
    supplier_result = await db.execute(
        select(Supplier).where(Supplier.user_id == current_user.id)
    )
    supplier = supplier_result.scalar_one_or_none()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    
    result = await db.execute(
        select(SupplierPaymentInfo).where(SupplierPaymentInfo.supplier_id == supplier.id)
    )
    info = result.scalar_one_or_none()
    
    if not info:
        info = SupplierPaymentInfo(supplier_id=supplier.id)
        db.add(info)
    
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(info, field, value)
    
    await db.commit()
    await db.refresh(info)
    return info

@router.post("/payment-info/qr-code")
async def upload_qr_code(
    file: UploadFile = File(...),
    current_user: User = Depends(get_supplier_user),
    db: AsyncSession = Depends(get_db)
):
    """Upload QR code image"""
    supplier_result = await db.execute(
        select(Supplier).where(Supplier.user_id == current_user.id)
    )
    supplier = supplier_result.scalar_one_or_none()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    
    # Validate file
    ext = Path(file.filename).suffix.lower()
    if ext not in {".jpg", ".jpeg", ".png"}:
        raise HTTPException(status_code=400, detail="File type not allowed")
    
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:  # 5MB
        raise HTTPException(status_code=400, detail="File too large")
    
    # Save file
    filename = f"qr_{supplier.id}_{uuid.uuid4().hex[:8]}{ext}"
    filepath = UPLOAD_DIR / filename
    async with aiofiles.open(filepath, 'wb') as f:
        await f.write(content)
    
    # Update payment info
    result = await db.execute(
        select(SupplierPaymentInfo).where(SupplierPaymentInfo.supplier_id == supplier.id)
    )
    info = result.scalar_one_or_none()
    
    if not info:
        info = SupplierPaymentInfo(supplier_id=supplier.id)
        db.add(info)
    
    info.qr_code_url = f"/uploads/{filename}"
    await db.commit()
    
    return {"message": "QR code uploaded", "url": info.qr_code_url}

@router.get("/payment-info/{supplier_id}", response_model=PaymentInfoResponse)
async def get_supplier_payment_info(
    supplier_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get supplier's payment info (for shop to see when paying)"""
    result = await db.execute(
        select(SupplierPaymentInfo).where(SupplierPaymentInfo.supplier_id == supplier_id)
    )
    info = result.scalar_one_or_none()
    
    if not info:
        raise HTTPException(status_code=404, detail="Payment info not found")
    
    return info
