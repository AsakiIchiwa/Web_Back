from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime, date
from decimal import Decimal
from app.models import UserRole, ProductStatus, RFQStatus, QuoteStatus, ContractStatus, NotificationType, OrderStatus, PaymentMethod

# ==================== AUTH ====================
class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    user_id: Optional[int] = None
    role: Optional[str] = None

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    full_name: str
    role: UserRole = UserRole.SHOP
    # Supplier fields
    company_name: Optional[str] = None
    # Shop fields
    shop_name: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None

# ==================== USER ====================
class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None
    role: UserRole

class UserCreate(UserBase):
    password: str

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    
class UserResponse(UserBase):
    id: int
    email_verified: bool = False
    is_approved: bool = False
    rejected_reason: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

class UserWithProfile(UserResponse):
    supplier: Optional["SupplierResponse"] = None
    shop: Optional["ShopResponse"] = None

# ==================== SUPPLIER ====================
class SupplierBase(BaseModel):
    company_name: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    description: Optional[str] = None

class SupplierCreate(SupplierBase):
    user_id: int

class SupplierUpdate(SupplierBase):
    pass

class SupplierResponse(SupplierBase):
    id: int
    user_id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

class SupplierWithUser(SupplierResponse):
    user: UserResponse

# ==================== SHOP ====================
class ShopBase(BaseModel):
    shop_name: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None

class ShopCreate(ShopBase):
    user_id: int

class ShopUpdate(ShopBase):
    pass

class ShopResponse(ShopBase):
    id: int
    user_id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

class ShopWithUser(ShopResponse):
    user: UserResponse

# ==================== PRODUCT ====================
class ProductBase(BaseModel):
    name: str
    description: Optional[str] = None
    price: Optional[Decimal] = None
    stock: Optional[int] = 0
    image_url: Optional[str] = None
    category: Optional[str] = None

class ProductCreate(ProductBase):
    pass

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[Decimal] = None
    stock: Optional[int] = None
    status: Optional[ProductStatus] = None
    image_url: Optional[str] = None
    category: Optional[str] = None

class ProductResponse(ProductBase):
    id: int
    supplier_id: int
    status: ProductStatus
    created_at: datetime
    
    class Config:
        from_attributes = True

class ProductWithSupplier(ProductResponse):
    supplier: SupplierResponse

# ==================== RFQ ====================
class RFQBase(BaseModel):
    product_id: int
    quantity: int = Field(gt=0)
    message: Optional[str] = None

class RFQCreate(RFQBase):
    pass

class RFQResponse(RFQBase):
    id: int
    shop_id: int
    status: RFQStatus
    created_at: datetime
    
    class Config:
        from_attributes = True

class RFQWithDetails(RFQResponse):
    shop: ShopResponse
    product: ProductResponse
    quotes: List["QuoteResponse"] = []

# ==================== QUOTE ====================
class QuoteBase(BaseModel):
    price: Decimal = Field(gt=0)
    min_order_qty: Optional[int] = None
    lead_time: Optional[int] = None
    message: Optional[str] = None

class QuoteCreate(QuoteBase):
    rfq_id: int

class QuoteUpdate(BaseModel):
    status: QuoteStatus

class QuoteResponse(QuoteBase):
    id: int
    rfq_id: int
    supplier_id: int
    status: QuoteStatus
    created_at: datetime
    
    class Config:
        from_attributes = True

class QuoteWithDetails(QuoteResponse):
    supplier: SupplierResponse
    rfq: RFQResponse

# ==================== NEGOTIATION ====================
class NegotiationBase(BaseModel):
    message: Optional[str] = None
    proposed_price: Optional[Decimal] = None

class NegotiationCreate(NegotiationBase):
    rfq_id: int

class NegotiationResponse(NegotiationBase):
    id: int
    rfq_id: int
    sender_role: UserRole
    sender_id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

# ==================== CONTRACT ====================
class ContractBase(BaseModel):
    product_id: int
    agreed_price: Decimal
    quantity: int
    start_date: Optional[date] = None
    end_date: Optional[date] = None

class ContractCreate(ContractBase):
    supplier_id: int

class ContractUpdate(BaseModel):
    status: Optional[ContractStatus] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None

class ContractResponse(ContractBase):
    id: int
    supplier_id: int
    shop_id: int
    status: ContractStatus
    created_at: datetime
    
    class Config:
        from_attributes = True

class ContractWithDetails(ContractResponse):
    supplier: SupplierResponse
    shop: ShopResponse
    product: ProductResponse

# ==================== PAGINATION ====================
class PaginatedResponse(BaseModel):
    items: List
    total: int
    page: int
    size: int
    pages: int

# ==================== NOTIFICATION ====================
class NotificationResponse(BaseModel):
    id: int
    user_id: int
    type: NotificationType
    title: str
    message: Optional[str] = None
    link: Optional[str] = None
    is_read: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

class NotificationUpdate(BaseModel):
    is_read: bool
    
# ==================== CHAT ====================
# ==================== CHAT ====================
class ChatMessageCreate(BaseModel):
    message: str  # <-- Đổi từ content thành message


class ChatMessageResponse(BaseModel):
    id: int
    chat_room_id: int  # <-- Đổi từ room_id thành chat_room_id (khớp với model)
    sender_id: int
    message: str  # <-- Đổi từ content thành message
    is_read: bool = False
    created_at: datetime
    sender: Optional[UserResponse] = None  # Thêm sender info
    
    class Config:
        from_attributes = True


class ChatRoomResponse(BaseModel):
    id: int
    supplier_id: int
    shop_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    supplier: Optional[SupplierResponse] = None
    shop: Optional[ShopResponse] = None
    last_message: Optional[ChatMessageResponse] = None
    unread_count: Optional[int] = 0
    messages: Optional[List[ChatMessageResponse]] = []
    
    class Config:
        from_attributes = True


# ==================== ORDER ====================
class OrderCreate(BaseModel):
    contract_id: int
    quantity: int = Field(gt=0)
    shipping_address: str
    note: Optional[str] = None
    payment_method: Optional[PaymentMethod] = PaymentMethod.BANK_TRANSFER


class OrderUpdate(BaseModel):
    status: Optional[OrderStatus] = None
    shipping_address: Optional[str] = None
    note: Optional[str] = None


class OrderResponse(BaseModel):
    id: int
    order_code: str
    contract_id: int
    supplier_id: int
    shop_id: int
    quantity: int
    unit_price: Decimal
    total_amount: Decimal
    shipping_address: Optional[str] = None
    note: Optional[str] = None
    status: OrderStatus
    payment_method: PaymentMethod
    payment_proof: Optional[str] = None
    paid_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class OrderTrackingResponse(BaseModel):
    id: int
    order_id: int
    status: OrderStatus
    note: Optional[str] = None
    updated_by: Optional[int] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class OrderWithDetails(OrderResponse):
    contract: Optional[dict] = None
    supplier: Optional[dict] = None
    shop: Optional[dict] = None
    tracking_history: Optional[List[OrderTrackingResponse]] = []
    
    class Config:
        from_attributes = True


# ==================== PAYMENT INFO ====================
class PaymentInfoCreate(BaseModel):
    bank_name: Optional[str] = None
    bank_account: Optional[str] = None
    account_holder: Optional[str] = None
    qr_code_url: Optional[str] = None


class PaymentInfoResponse(BaseModel):
    id: Optional[int] = None
    supplier_id: Optional[int] = None
    bank_name: Optional[str] = None
    bank_account: Optional[str] = None
    account_holder: Optional[str] = None
    qr_code_url: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True
        
# Update forward refs
UserWithProfile.model_rebuild()
RFQWithDetails.model_rebuild()
OrderWithDetails.model_rebuild()
