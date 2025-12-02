from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.config import settings
from app.database import engine, Base
from app.routers import auth, users, suppliers, shops, products, rfq, quotes, negotiations, contracts, admin

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Shutdown
    await engine.dispose()

app = FastAPI(
    title="B2B Marketplace API",
    description="API cho sàn thương mại B2B kết nối Suppliers và Shops",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS - cho phép frontend truy cập
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(users.router, prefix="/users", tags=["Users"])
app.include_router(suppliers.router, prefix="/suppliers", tags=["Suppliers"])
app.include_router(shops.router, prefix="/shops", tags=["Shops"])
app.include_router(products.router, prefix="/products", tags=["Products"])
app.include_router(rfq.router, prefix="/rfq", tags=["RFQ"])
app.include_router(quotes.router, prefix="/quotes", tags=["Quotes"])
app.include_router(negotiations.router, prefix="/negotiations", tags=["Negotiations"])
app.include_router(contracts.router, prefix="/contracts", tags=["Contracts"])
app.include_router(admin.router, prefix="/admin", tags=["Admin"])

@app.get("/", tags=["Health"])
async def root():
    return {"status": "ok", "message": "B2B Marketplace API"}

@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "healthy", "version": "1.0.0"}
