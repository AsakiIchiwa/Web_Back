"""
Seed database with test data
Run: python -m app.seed
"""
import asyncio
from datetime import datetime, timedelta
from sqlalchemy import select
from app.database import AsyncSessionLocal, engine, Base
from app.models import User, Supplier, Shop, Product, RFQ, Quote, Contract, Negotiation, UserRole, ProductStatus, RFQStatus, QuoteStatus, ContractStatus
from app.auth import get_password_hash

async def seed():
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with AsyncSessionLocal() as db:
        # Check if data exists
        result = await db.execute(select(User).limit(1))
        if result.scalar_one_or_none():
            print("Database already seeded!")
            return
        
        print("Seeding database...")
        
        # Create Admin
        admin = User(
            email="admin@b2bmarket.com",
            password_hash=get_password_hash("Admin123!"),
            full_name="Admin User",
            role=UserRole.ADMIN
        )
        db.add(admin)
        
        # Create Suppliers
        suppliers_data = [
            {"email": "supplier1@techcorp.com", "name": "Tech Corp Vietnam", "company": "Tech Corp", "desc": "Nhà cung cấp linh kiện điện tử hàng đầu"},
            {"email": "supplier2@foodco.com", "name": "Food Co", "company": "Food & Beverage Co", "desc": "Thực phẩm và đồ uống chất lượng cao"},
            {"email": "supplier3@fashion.com", "name": "Fashion Style", "company": "Fashion Style Ltd", "desc": "Thời trang nam nữ cao cấp"},
        ]
        
        created_suppliers = []
        for s in suppliers_data:
            user = User(
                email=s["email"],
                password_hash=get_password_hash("Supplier123!"),
                full_name=s["name"],
                role=UserRole.SUPPLIER
            )
            db.add(user)
            await db.flush()
            
            supplier = Supplier(
                user_id=user.id,
                company_name=s["company"],
                description=s["desc"],
                address="123 Business Street, HCM",
                phone="0901234567"
            )
            db.add(supplier)
            await db.flush()
            created_suppliers.append(supplier)
        
        # Create Shops
        shops_data = [
            {"email": "shop1@retailplus.com", "name": "Retail Plus", "shop": "Retail Plus Store"},
            {"email": "shop2@minimart.com", "name": "Mini Mart", "shop": "Mini Mart Chain"},
        ]
        
        created_shops = []
        for s in shops_data:
            user = User(
                email=s["email"],
                password_hash=get_password_hash("Shop123!"),
                full_name=s["name"],
                role=UserRole.SHOP
            )
            db.add(user)
            await db.flush()
            
            shop = Shop(
                user_id=user.id,
                shop_name=s["shop"],
                address="456 Retail Street, HCM",
                phone="0909876543"
            )
            db.add(shop)
            await db.flush()
            created_shops.append(shop)
        
        # Create Products
        products_data = [
            # Tech Corp products
            {"name": "Laptop Dell XPS 15", "desc": "Laptop cao cấp cho doanh nghiệp", "price": 35000000, "stock": 50, "category": "Điện tử", "supplier_idx": 0},
            {"name": "iPhone 15 Pro", "desc": "Điện thoại flagship Apple", "price": 28000000, "stock": 100, "category": "Điện tử", "supplier_idx": 0},
            {"name": "Samsung Galaxy Tab S9", "desc": "Máy tính bảng Android cao cấp", "price": 18000000, "stock": 75, "category": "Điện tử", "supplier_idx": 0},
            # Food Co products
            {"name": "Cà phê Arabica Premium", "desc": "Cà phê nguyên chất 100%", "price": 250000, "stock": 500, "category": "Thực phẩm", "supplier_idx": 1},
            {"name": "Trà Oolong Đài Loan", "desc": "Trà cao cấp nhập khẩu", "price": 180000, "stock": 300, "category": "Thực phẩm", "supplier_idx": 1},
            {"name": "Nước ép trái cây hữu cơ", "desc": "100% trái cây tự nhiên", "price": 45000, "stock": 1000, "category": "Đồ uống", "supplier_idx": 1},
            # Fashion products
            {"name": "Áo sơ mi nam cao cấp", "desc": "Vải cotton Ai Cập", "price": 850000, "stock": 200, "category": "Thời trang", "supplier_idx": 2},
            {"name": "Váy đầm nữ công sở", "desc": "Thiết kế Hàn Quốc", "price": 1200000, "stock": 150, "category": "Thời trang", "supplier_idx": 2},
            {"name": "Giày da nam Italy", "desc": "Da bò thật 100%", "price": 2500000, "stock": 80, "category": "Giày dép", "supplier_idx": 2},
        ]
        
        created_products = []
        for p in products_data:
            product = Product(
                supplier_id=created_suppliers[p["supplier_idx"]].id,
                name=p["name"],
                description=p["desc"],
                price=p["price"],
                stock=p["stock"],
                category=p["category"],
                status=ProductStatus.ACTIVE
            )
            db.add(product)
            await db.flush()
            created_products.append(product)
        
        # Create RFQs (Request for Quotation) - Shop gửi yêu cầu báo giá
        rfqs_data = [
            {"shop_idx": 0, "product_idx": 0, "quantity": 10, "message": "Cần mua 10 laptop cho văn phòng mới", "status": RFQStatus.QUOTED},
            {"shop_idx": 0, "product_idx": 3, "quantity": 100, "message": "Đặt hàng cà phê cho quán cafe", "status": RFQStatus.QUOTED},
            {"shop_idx": 0, "product_idx": 6, "quantity": 50, "message": "Nhập áo sơ mi cho cửa hàng", "status": RFQStatus.PENDING},
            {"shop_idx": 1, "product_idx": 1, "quantity": 20, "message": "Cần iPhone cho đại lý", "status": RFQStatus.QUOTED},
            {"shop_idx": 1, "product_idx": 4, "quantity": 200, "message": "Đặt trà cho siêu thị", "status": RFQStatus.PENDING},
        ]
        
        created_rfqs = []
        for r in rfqs_data:
            rfq = RFQ(
                shop_id=created_shops[r["shop_idx"]].id,
                product_id=created_products[r["product_idx"]].id,
                quantity=r["quantity"],
                message=r["message"],
                status=r["status"]
            )
            db.add(rfq)
            await db.flush()
            created_rfqs.append(rfq)
        
        # Create Quotes - Supplier báo giá cho RFQ
        quotes_data = [
            {"rfq_idx": 0, "supplier_idx": 0, "price": 33000000, "min_qty": 5, "lead_time": "7 ngày", "message": "Giảm giá 5% cho đơn hàng trên 5 máy", "status": QuoteStatus.PENDING},
            {"rfq_idx": 1, "supplier_idx": 1, "price": 230000, "min_qty": 50, "lead_time": "3 ngày", "message": "Freeship cho đơn trên 50 gói", "status": QuoteStatus.ACCEPTED},
            {"rfq_idx": 3, "supplier_idx": 0, "price": 26500000, "min_qty": 10, "lead_time": "5 ngày", "message": "Giá sỉ đặc biệt cho đại lý", "status": QuoteStatus.PENDING},
        ]
        
        created_quotes = []
        for q in quotes_data:
            quote = Quote(
                rfq_id=created_rfqs[q["rfq_idx"]].id,
                supplier_id=created_suppliers[q["supplier_idx"]].id,
                price=q["price"],
                min_order_qty=q["min_qty"],
                lead_time=q["lead_time"],
                message=q["message"],
                status=q["status"]
            )
            db.add(quote)
            await db.flush()
            created_quotes.append(quote)
        
        # Create Negotiations - Đàm phán giá
        negotiations_data = [
            {"rfq_idx": 0, "sender_role": "shop", "sender_id": created_shops[0].id, "message": "Có thể giảm thêm không?", "proposed_price": 32000000},
            {"rfq_idx": 0, "sender_role": "supplier", "sender_id": created_suppliers[0].id, "message": "Nếu đặt 15 máy thì được 32tr/máy", "proposed_price": 32000000},
            {"rfq_idx": 3, "sender_role": "shop", "sender_id": created_shops[1].id, "message": "Giá này có bảo hành không?", "proposed_price": None},
        ]
        
        for n in negotiations_data:
            negotiation = Negotiation(
                rfq_id=created_rfqs[n["rfq_idx"]].id,
                sender_role=n["sender_role"],
                sender_id=n["sender_id"],
                message=n["message"],
                proposed_price=n["proposed_price"]
            )
            db.add(negotiation)
        
        # Create Contracts - Hợp đồng đã ký
        contracts_data = [
            {
                "supplier_idx": 1, 
                "shop_idx": 0, 
                "product_idx": 3, 
                "price": 230000, 
                "quantity": 100, 
                "status": ContractStatus.ACTIVE,
                "start_days_ago": 30,
                "end_days_future": 335
            },
            {
                "supplier_idx": 0, 
                "shop_idx": 1, 
                "product_idx": 1, 
                "price": 27000000, 
                "quantity": 50, 
                "status": ContractStatus.ACTIVE,
                "start_days_ago": 15,
                "end_days_future": 350
            },
            {
                "supplier_idx": 2, 
                "shop_idx": 0, 
                "product_idx": 8, 
                "price": 2300000, 
                "quantity": 30, 
                "status": ContractStatus.DRAFT,
                "start_days_ago": 0,
                "end_days_future": 365
            },
        ]
        
        for c in contracts_data:
            contract = Contract(
                supplier_id=created_suppliers[c["supplier_idx"]].id,
                shop_id=created_shops[c["shop_idx"]].id,
                product_id=created_products[c["product_idx"]].id,
                agreed_price=c["price"],
                quantity=c["quantity"],
                start_date=datetime.now() - timedelta(days=c["start_days_ago"]),
                end_date=datetime.now() + timedelta(days=c["end_days_future"]),
                status=c["status"]
            )
            db.add(contract)
        
        await db.commit()
        
        print("✅ Database seeded successfully!")
        print("\n📧 Test Accounts:")
        print("  Admin: admin@b2bmarket.com / Admin123!")
        print("  Supplier: supplier1@techcorp.com / Supplier123!")
        print("  Shop: shop1@retailplus.com / Shop123!")
        print("\n📊 Test Data Created:")
        print(f"  - {len(created_suppliers)} Suppliers")
        print(f"  - {len(created_shops)} Shops")
        print(f"  - {len(created_products)} Products")
        print(f"  - {len(created_rfqs)} RFQs")
        print(f"  - {len(created_quotes)} Quotes")
        print(f"  - {len(negotiations_data)} Negotiations")
        print(f"  - {len(contracts_data)} Contracts")

if __name__ == "__main__":
    asyncio.run(seed())
