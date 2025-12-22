from sqlalchemy import Column, Integer, String, Text, Numeric, ForeignKey, DateTime, Date, Enum as SQLEnum, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import enum

class UserRole(str, enum.Enum):
    ADMIN = "admin"
    SUPPLIER = "supplier"
    SHOP = "shop"

class ProductStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"

class RFQStatus(str, enum.Enum):
    PENDING = "pending"
    QUOTED = "quoted"
    CLOSED = "closed"

class QuoteStatus(str, enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"

class ContractStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    EXPIRED = "expired"
    TERMINATED = "terminated"

class NotificationType(str, enum.Enum):
    RFQ_RECEIVED = "rfq_received"           # Supplier nhận RFQ mới
    QUOTE_RECEIVED = "quote_received"       # Shop nhận báo giá
    QUOTE_ACCEPTED = "quote_accepted"       # Supplier: báo giá được chấp nhận
    QUOTE_REJECTED = "quote_rejected"       # Supplier: báo giá bị từ chối
    CONTRACT_CREATED = "contract_created"   # Cả 2: hợp đồng mới
    PRODUCT_APPROVED = "product_approved"   # Supplier: sản phẩm được duyệt
    PRODUCT_REJECTED = "product_rejected"   # Supplier: sản phẩm bị từ chối
    ORDER_CREATED = "order_created"         # Cả 2: đơn hàng mới
    ORDER_UPDATED = "order_updated"         # Shop: cập nhật trạng thái đơn
    PAYMENT_CONFIRMED = "payment_confirmed" # Supplier: thanh toán được xác nhận
    NEW_MESSAGE = "new_message"             # Tin nhắn mới
    SYSTEM = "system"                       # Thông báo hệ thống

class OrderStatus(str, enum.Enum):
    PENDING = "pending"                     # Chờ xác nhận
    CONFIRMED = "confirmed"                 # Đã xác nhận
    PAYMENT_PENDING = "payment_pending"     # Chờ thanh toán
    PAID = "paid"                           # Đã thanh toán
    PROCESSING = "processing"               # Đang xử lý
    SHIPPING = "shipping"                   # Đang vận chuyển
    DELIVERED = "delivered"                 # Đã giao hàng
    COMPLETED = "completed"                 # Hoàn thành
    CANCELLED = "cancelled"                 # Đã hủy

class PaymentMethod(str, enum.Enum):
    BANK_TRANSFER = "bank_transfer"         # Chuyển khoản
    QR_CODE = "qr_code"                     # QR Code
    COD = "cod"                             # Thanh toán khi nhận hàng

# ==================== USERS ====================
class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(Text, nullable=False)
    full_name = Column(String(255))
    role = Column(SQLEnum(UserRole), nullable=False, default=UserRole.SHOP)
    
    # Verification & Approval
    email_verified = Column(Boolean, default=False)
    is_approved = Column(Boolean, default=False)
    verification_token = Column(String(255), nullable=True)
    verification_token_expires = Column(DateTime(timezone=True), nullable=True)
    rejected_reason = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    supplier = relationship("Supplier", back_populates="user", uselist=False)
    shop = relationship("Shop", back_populates="user", uselist=False)
    notifications = relationship("Notification", back_populates="user")

# ==================== SUPPLIER ====================
class Supplier(Base):
    __tablename__ = "suppliers"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    company_name = Column(String(255))
    address = Column(Text)
    phone = Column(String(50))
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    user = relationship("User", back_populates="supplier")
    products = relationship("Product", back_populates="supplier")
    quotes = relationship("Quote", back_populates="supplier")
    contracts = relationship("Contract", back_populates="supplier")
    orders = relationship("Order", back_populates="supplier")
    chat_rooms = relationship("ChatRoom", back_populates="supplier")

# ==================== SHOP ====================
class Shop(Base):
    __tablename__ = "shops"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    shop_name = Column(String(255))
    address = Column(Text)
    phone = Column(String(50))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    user = relationship("User", back_populates="shop")
    rfqs = relationship("RFQ", back_populates="shop")
    contracts = relationship("Contract", back_populates="shop")
    orders = relationship("Order", back_populates="shop")
    chat_rooms = relationship("ChatRoom", back_populates="shop")

# ==================== PRODUCTS ====================
class Product(Base):
    __tablename__ = "products"
    
    id = Column(Integer, primary_key=True, index=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    price = Column(Numeric(12, 2))
    stock = Column(Integer, default=0)
    status = Column(SQLEnum(ProductStatus), default=ProductStatus.PENDING)
    image_url = Column(String(500))
    category = Column(String(100))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    supplier = relationship("Supplier", back_populates="products")
    rfqs = relationship("RFQ", back_populates="product")
    contracts = relationship("Contract", back_populates="product")

# ==================== RFQ ====================
class RFQ(Base):
    __tablename__ = "rfq"
    
    id = Column(Integer, primary_key=True, index=True)
    shop_id = Column(Integer, ForeignKey("shops.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    quantity = Column(Integer, nullable=False)
    message = Column(Text)
    status = Column(SQLEnum(RFQStatus), default=RFQStatus.PENDING)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    shop = relationship("Shop", back_populates="rfqs")
    product = relationship("Product", back_populates="rfqs")
    quotes = relationship("Quote", back_populates="rfq")
    negotiations = relationship("Negotiation", back_populates="rfq")

# ==================== QUOTES ====================
class Quote(Base):
    __tablename__ = "quotes"
    
    id = Column(Integer, primary_key=True, index=True)
    rfq_id = Column(Integer, ForeignKey("rfq.id"), nullable=False)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=False)
    price = Column(Numeric(12, 2), nullable=False)
    min_order_qty = Column(Integer)
    lead_time = Column(Integer)  # days
    message = Column(Text)
    status = Column(SQLEnum(QuoteStatus), default=QuoteStatus.PENDING)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    rfq = relationship("RFQ", back_populates="quotes")
    supplier = relationship("Supplier", back_populates="quotes")

# ==================== NEGOTIATIONS ====================
class Negotiation(Base):
    __tablename__ = "negotiations"
    
    id = Column(Integer, primary_key=True, index=True)
    rfq_id = Column(Integer, ForeignKey("rfq.id"), nullable=False)
    sender_role = Column(SQLEnum(UserRole), nullable=False)
    sender_id = Column(Integer, nullable=False)
    message = Column(Text)
    proposed_price = Column(Numeric(12, 2))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    rfq = relationship("RFQ", back_populates="negotiations")

# ==================== CONTRACTS ====================
class Contract(Base):
    __tablename__ = "contracts"
    
    id = Column(Integer, primary_key=True, index=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=False)
    shop_id = Column(Integer, ForeignKey("shops.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    agreed_price = Column(Numeric(12, 2), nullable=False)
    quantity = Column(Integer, nullable=False)
    start_date = Column(Date)
    end_date = Column(Date)
    status = Column(SQLEnum(ContractStatus), default=ContractStatus.DRAFT)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    supplier = relationship("Supplier", back_populates="contracts")
    shop = relationship("Shop", back_populates="contracts")
    product = relationship("Product", back_populates="contracts")
    orders = relationship("Order", back_populates="contract")

# ==================== NOTIFICATIONS ====================
class Notification(Base):
    __tablename__ = "notifications"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    type = Column(SQLEnum(NotificationType), nullable=False)
    title = Column(String(255), nullable=False)
    message = Column(Text)
    link = Column(String(500))  # Link to related page
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    user = relationship("User", back_populates="notifications")

# ==================== CHAT ====================
class ChatRoom(Base):
    __tablename__ = "chat_rooms"
    
    id = Column(Integer, primary_key=True, index=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=False)
    shop_id = Column(Integer, ForeignKey("shops.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    supplier = relationship("Supplier", back_populates="chat_rooms")
    shop = relationship("Shop", back_populates="chat_rooms")
    messages = relationship("ChatMessage", back_populates="chat_room", order_by="ChatMessage.created_at")

class ChatMessage(Base):
    __tablename__ = "chat_messages"
    
    id = Column(Integer, primary_key=True, index=True)
    chat_room_id = Column(Integer, ForeignKey("chat_rooms.id"), nullable=False)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    message = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    chat_room = relationship("ChatRoom", back_populates="messages")
    sender = relationship("User")

# ==================== ORDERS ====================
class Order(Base):
    __tablename__ = "orders"
    
    id = Column(Integer, primary_key=True, index=True)
    order_code = Column(String(50), unique=True, nullable=False)  # Mã đơn hàng: ORD-YYYYMMDD-XXX
    contract_id = Column(Integer, ForeignKey("contracts.id"), nullable=False)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=False)
    shop_id = Column(Integer, ForeignKey("shops.id"), nullable=False)
    
    # Order details
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Numeric(12, 2), nullable=False)
    total_amount = Column(Numeric(12, 2), nullable=False)
    shipping_address = Column(Text)
    note = Column(Text)
    
    # Status & Payment
    status = Column(SQLEnum(OrderStatus), default=OrderStatus.PENDING)
    payment_method = Column(SQLEnum(PaymentMethod), default=PaymentMethod.BANK_TRANSFER)
    payment_proof = Column(String(500))  # URL ảnh chứng từ thanh toán
    paid_at = Column(DateTime(timezone=True))
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    contract = relationship("Contract", back_populates="orders")
    supplier = relationship("Supplier", back_populates="orders")
    shop = relationship("Shop", back_populates="orders")
    tracking_history = relationship("OrderTracking", back_populates="order", order_by="OrderTracking.created_at.desc()")

class OrderTracking(Base):
    __tablename__ = "order_tracking"
    
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    status = Column(SQLEnum(OrderStatus), nullable=False)
    note = Column(Text)
    updated_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    order = relationship("Order", back_populates="tracking_history")
    user = relationship("User")

# ==================== SUPPLIER PAYMENT INFO ====================
class SupplierPaymentInfo(Base):
    __tablename__ = "supplier_payment_info"
    
    id = Column(Integer, primary_key=True, index=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), unique=True, nullable=False)
    
    # Bank info
    bank_name = Column(String(255))
    bank_account = Column(String(50))
    account_holder = Column(String(255))
    
    # QR Code
    qr_code_url = Column(String(500))  # URL ảnh QR code
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
