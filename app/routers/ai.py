"""
AI-powered features API router
Includes both rule-based and ChatGPT-powered features
"""

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from pydantic import BaseModel

from app.database import get_db
from app.ai.price_suggestion import get_ai_price_suggestion
from app.ai.chatgpt_service import ChatGPTService
from app.auth import get_current_user
from app.models import User

router = APIRouter()


# ==================== PYDANTIC MODELS ====================

class ChatMessage(BaseModel):
    message: str
    context: Optional[dict] = None

class ProductDescriptionRequest(BaseModel):
    product_name: str
    category: str
    features: Optional[str] = None
    target_audience: str = "doanh nghiệp B2B"

class PricingStrategyRequest(BaseModel):
    product_name: str
    category: str
    cost_price: float
    competitor_prices: Optional[list] = None
    target_margin: float = 20

class QuoteResponseRequest(BaseModel):
    product_name: str
    quantity: int
    customer_message: Optional[str] = None
    proposed_price: float
    delivery_days: int
    company_name: str

class NegotiationRequest(BaseModel):
    product_name: str
    listed_price: float
    quantity: int
    market_avg_price: Optional[float] = None

class RFQDraftRequest(BaseModel):
    product_name: str
    quantity: int
    requirements: Optional[str] = None
    deadline: Optional[str] = None

class ContractTermsRequest(BaseModel):
    product_name: str
    quantity: int
    price: float
    delivery_terms: str = "FOB"
    payment_terms: str = "30 ngày"


# ==================== RULE-BASED AI ENDPOINTS ====================

@router.get("/price-suggestion")
async def ai_price_suggestion(
    category: str = Query(..., description="Product category"),
    product_name: Optional[str] = Query(None, description="Product name for better matching"),
    quantity: int = Query(1, ge=1, description="Order quantity"),
    unit: str = Query("piece", description="Unit of measurement"),
    db: AsyncSession = Depends(get_db)
):
    """Get AI-powered price suggestion (rule-based)"""
    result = await get_ai_price_suggestion(
        db=db,
        category=category,
        product_name=product_name,
        quantity=quantity,
        unit=unit
    )
    return result


@router.get("/market-analysis")
async def market_analysis(
    category: str = Query(..., description="Product category"),
    db: AsyncSession = Depends(get_db)
):
    """Get market analysis for a category"""
    from sqlalchemy import select, func, and_
    from datetime import datetime, timedelta
    from app.models import Product, RFQ, Supplier
    
    product_result = await db.execute(
        select(
            func.count(Product.id).label("total_products"),
            func.avg(Product.price).label("avg_price"),
            func.min(Product.price).label("min_price"),
            func.max(Product.price).label("max_price")
        ).where(
            and_(
                Product.category == category,
                Product.is_active == True,
                Product.price > 0
            )
        )
    )
    product_stats = product_result.fetchone()
    
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    rfq_result = await db.execute(
        select(func.count(RFQ.id)).where(
            and_(
                RFQ.category == category,
                RFQ.created_at >= thirty_days_ago
            )
        )
    )
    rfq_count = rfq_result.scalar() or 0
    
    supplier_result = await db.execute(
        select(func.count(func.distinct(Product.supplier_id))).where(
            and_(
                Product.category == category,
                Product.is_active == True
            )
        )
    )
    supplier_count = supplier_result.scalar() or 0
    
    return {
        "category": category,
        "market_overview": {
            "total_products": product_stats.total_products or 0,
            "avg_price": round(float(product_stats.avg_price or 0), 2),
            "min_price": round(float(product_stats.min_price or 0), 2),
            "max_price": round(float(product_stats.max_price or 0), 2),
            "active_suppliers": supplier_count
        },
        "demand_indicators": {
            "rfqs_last_30_days": rfq_count,
            "demand_level": "high" if rfq_count > 30 else "medium" if rfq_count > 10 else "low"
        },
        "market_health": {
            "competition_level": "high" if supplier_count > 10 else "medium" if supplier_count > 3 else "low",
            "price_stability": "stable" if product_stats.total_products and product_stats.avg_price and (
                (product_stats.max_price - product_stats.min_price) / product_stats.avg_price < 0.5
            ) else "volatile"
        }
    }


@router.get("/categories")
async def get_categories(db: AsyncSession = Depends(get_db)):
    """Get all available product categories"""
    from sqlalchemy import select, func
    from app.models import Product
    
    result = await db.execute(
        select(
            Product.category,
            func.count(Product.id).label("product_count")
        ).where(
            Product.is_active == True
        ).group_by(
            Product.category
        ).order_by(
            func.count(Product.id).desc()
        )
    )
    
    categories = [
        {"name": row.category, "product_count": row.product_count}
        for row in result.fetchall()
    ]
    
    return {"categories": categories}


# ==================== CHATGPT-POWERED ENDPOINTS ====================

@router.post("/chat")
async def ai_chat(
    request: ChatMessage,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Chat with AI assistant
    Supports both suppliers and shops
    """
    service = ChatGPTService(db)
    response = await service.chat_assistant(
        message=request.message,
        user_role=current_user.role.value,
        context=request.context
    )
    return {"response": response}


@router.post("/generate-description")
async def generate_product_description(
    request: ProductDescriptionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Generate professional product description using ChatGPT
    For suppliers creating new products
    """
    if current_user.role.value != "supplier":
        raise HTTPException(status_code=403, detail="Only suppliers can use this feature")
    
    service = ChatGPTService(db)
    result = await service.generate_product_description(
        product_name=request.product_name,
        category=request.category,
        features=request.features,
        target_audience=request.target_audience
    )
    return result


@router.post("/pricing-strategy")
async def suggest_pricing_strategy(
    request: PricingStrategyRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get AI-powered pricing strategy suggestions
    For suppliers setting product prices
    """
    if current_user.role.value != "supplier":
        raise HTTPException(status_code=403, detail="Only suppliers can use this feature")
    
    service = ChatGPTService(db)
    result = await service.suggest_pricing_strategy(
        product_name=request.product_name,
        category=request.category,
        cost_price=request.cost_price,
        competitor_prices=request.competitor_prices,
        target_margin=request.target_margin
    )
    return result


@router.post("/draft-quote")
async def draft_quote_response(
    request: QuoteResponseRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Draft professional quote response using ChatGPT
    For suppliers responding to RFQs
    """
    if current_user.role.value != "supplier":
        raise HTTPException(status_code=403, detail="Only suppliers can use this feature")
    
    service = ChatGPTService(db)
    response = await service.draft_quote_response(
        rfq_details={
            "product_name": request.product_name,
            "quantity": request.quantity,
            "message": request.customer_message
        },
        supplier_info={"company_name": request.company_name},
        proposed_price=request.proposed_price,
        delivery_days=request.delivery_days
    )
    return {"draft": response}


@router.post("/negotiation-strategy")
async def suggest_negotiation_strategy(
    request: NegotiationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get negotiation strategy suggestions for buyers
    For shops negotiating with suppliers
    """
    if current_user.role.value != "shop":
        raise HTTPException(status_code=403, detail="Only shops can use this feature")
    
    service = ChatGPTService(db)
    result = await service.suggest_negotiation_strategy(
        product_name=request.product_name,
        listed_price=request.listed_price,
        quantity=request.quantity,
        market_avg_price=request.market_avg_price
    )
    return result


@router.post("/draft-rfq")
async def draft_rfq_message(
    request: RFQDraftRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Draft professional RFQ message using ChatGPT
    For shops creating RFQ requests
    """
    if current_user.role.value != "shop":
        raise HTTPException(status_code=403, detail="Only shops can use this feature")
    
    service = ChatGPTService(db)
    response = await service.draft_rfq_message(
        product_name=request.product_name,
        quantity=request.quantity,
        requirements=request.requirements,
        deadline=request.deadline
    )
    return {"draft": response}


@router.get("/analyze-supplier/{supplier_id}")
async def analyze_supplier(
    supplier_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get AI analysis of a supplier
    For shops evaluating suppliers
    """
    if current_user.role.value != "shop":
        raise HTTPException(status_code=403, detail="Only shops can use this feature")
    
    service = ChatGPTService(db)
    result = await service.analyze_supplier(supplier_id)
    return result


@router.post("/contract-terms")
async def generate_contract_terms(
    request: ContractTermsRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Generate contract terms template using ChatGPT
    For both suppliers and shops
    """
    service = ChatGPTService(db)
    response = await service.generate_contract_terms(
        product_name=request.product_name,
        quantity=request.quantity,
        price=request.price,
        delivery_terms=request.delivery_terms,
        payment_terms=request.payment_terms
    )
    return {"terms": response}


@router.get("/market-insights/{category}")
async def get_market_insights(
    category: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get AI-powered market insights for a category
    Uses ChatGPT to analyze market data
    """
    service = ChatGPTService(db)
    result = await service.market_insights(category)
    return result

