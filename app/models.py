from sqlalchemy import Column, Integer, String, Text, Numeric, ForeignKey, DateTime, Date, Enum as SQLEnum
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

# ==================== USERS ====================
class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(Text, nullable=False)
    full_name = Column(String(255))
    role = Column(SQLEnum(UserRole), nullable=False, default=UserRole.SHOP)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    supplier = relationship("Supplier", back_populates="user", uselist=False)
    shop = relationship("Shop", back_populates="user", uselist=False)

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
