"""
AI-powered features API router
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.database import get_db
from app.ai.price_suggestion import get_ai_price_suggestion

router = APIRouter()


@router.get("/price-suggestion")
async def ai_price_suggestion(
    category: str = Query(..., description="Product category"),
    product_name: Optional[str] = Query(None, description="Product name for better matching"),
    quantity: int = Query(1, ge=1, description="Order quantity"),
    unit: str = Query("piece", description="Unit of measurement"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get AI-powered price suggestion
    
    This endpoint analyzes historical data, market trends, and demand/supply
    to suggest optimal pricing for a product.
    
    **Response includes:**
    - Suggested price with confidence score
    - Min/Max price range
    - Market trend (rising/stable/falling)
    - Demand and supply scores
    - Reasoning explanation
    - Comparable products
    
    **Example request:**
    ```
    GET /ai/price-suggestion?category=electronics&product_name=laptop&quantity=100
    ```
    """
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
    """
    Get market analysis for a category
    
    Returns market overview including:
    - Average prices
    - Price trends
    - Demand/supply indicators
    - Active suppliers count
    """
    from sqlalchemy import select, func, and_
    from datetime import datetime, timedelta
    from app.models import Product, RFQ, Supplier
    
    # Get product stats
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
    
    # Get RFQ stats (demand indicator)
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
    
    # Get active suppliers
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
            "price_stability": "stable" if product_stats.total_products and (
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
