from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.config import settings
from app.database import engine, Base
from app.routers import auth, users, suppliers, shops, products, rfq, quotes, negotiations, contracts, admin, ai  # ← ADD ai HERE
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Create tables
    print(f"🚀 Starting B2B Marketplace API...")
    print(f"📋 CORS_ORIGINS env: {settings.CORS_ORIGINS}")
    print(f"📋 CORS origins list: {settings.get_cors_origins()}")
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

# Get CORS origins
cors_origins = settings.get_cors_origins()
print(f"🔧 Configuring CORS with origins: {cors_origins}")

# CORS - cho phép frontend truy cập
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
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
app.include_router(ai.router, prefix="/ai", tags=["AI Features"])
app.include_router(negotiations.router, prefix="/negotiations", tags=["Negotiations"])
app.include_router(contracts.router, prefix="/contracts", tags=["Contracts"])
app.include_router(admin.router, prefix="/admin", tags=["Admin"])

@app.get("/", tags=["Health"])
async def root():
    return {"status": "ok", "message": "B2B Marketplace API"}

@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "healthy", "version": "1.0.0"}

@app.get("/debug/cors", tags=["Debug"])
async def debug_cors():
    """Debug endpoint to check CORS configuration"""
    return {
        "cors_env": settings.CORS_ORIGINS,
        "cors_origins": settings.get_cors_origins(),
        "message": "Check if your frontend URL is in cors_origins list"
    }
