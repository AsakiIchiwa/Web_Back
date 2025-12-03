"""
AI-powered price suggestion system for B2B Marketplace
Uses historical data and market analysis to suggest optimal prices
"""

from typing import Optional, List, Dict
from dataclasses import dataclass
from datetime import datetime, timedelta
import statistics
import math

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from app.models import Product, Quote, Contract, RFQ


@dataclass
class PriceSuggestion:
    """Price suggestion result"""
    suggested_price: float
    min_price: float
    max_price: float
    confidence: float  # 0-1
    market_trend: str  # "rising", "stable", "falling"
    reasoning: List[str]
    comparable_products: List[Dict]
    demand_score: float  # 0-100
    supply_score: float  # 0-100


@dataclass
class MarketAnalysis:
    """Market analysis data"""
    avg_price: float
    median_price: float
    std_dev: float
    price_range: tuple
    sample_size: int
    trend_direction: str
    trend_strength: float


class AIPriceSuggestionService:
    """
    AI-powered price suggestion engine
    
    Features:
    - Historical price analysis
    - Market trend detection
    - Demand/supply scoring
    - Confidence calculation
    - Similar product comparison
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
        
    async def get_price_suggestion(
        self,
        category: str,
        product_name: Optional[str] = None,
        quantity: int = 1,
        unit: str = "piece",
        supplier_id: Optional[int] = None
    ) -> PriceSuggestion:
        """
        Get AI-powered price suggestion for a product
        
        Args:
            category: Product category
            product_name: Optional product name for better matching
            quantity: Order quantity
            unit: Unit of measurement
            supplier_id: Optional supplier ID for supplier-specific pricing
            
        Returns:
            PriceSuggestion with recommended pricing
        """
        reasoning = []
        
        # Step 1: Get historical prices for similar products
        historical_prices = await self._get_historical_prices(
            category, product_name
        )
        
        # Step 2: Analyze market data
        if len(historical_prices) >= 3:
            market = self._analyze_market(historical_prices)
            reasoning.append(f"Phân tích {market.sample_size} sản phẩm tương tự")
        else:
            # Not enough data, use category average
            market = await self._get_category_average(category)
            reasoning.append("Sử dụng giá trung bình ngành hàng")
        
        # Step 3: Calculate demand score
        demand_score = await self._calculate_demand_score(category)
        reasoning.append(f"Nhu cầu thị trường: {self._demand_level(demand_score)}")
        
        # Step 4: Calculate supply score
        supply_score = await self._calculate_supply_score(category)
        reasoning.append(f"Nguồn cung: {self._supply_level(supply_score)}")
        
        # Step 5: Adjust price based on quantity
        quantity_discount = self._calculate_quantity_discount(quantity)
        if quantity_discount > 0:
            reasoning.append(f"Giảm giá số lượng lớn: -{quantity_discount*100:.1f}%")
        
        # Step 6: Adjust for demand/supply balance
        demand_supply_factor = self._calculate_demand_supply_factor(
            demand_score, supply_score
        )
        
        # Step 7: Calculate final price
        base_price = market.median_price if market.median_price > 0 else market.avg_price
        
        adjusted_price = base_price * (1 - quantity_discount) * demand_supply_factor
        
        # Step 8: Calculate price range
        min_price = max(
            adjusted_price * 0.85,
            market.price_range[0] if market.price_range[0] > 0 else adjusted_price * 0.7
        )
        max_price = min(
            adjusted_price * 1.15,
            market.price_range[1] if market.price_range[1] > 0 else adjusted_price * 1.3
        )
        
        # Step 9: Calculate confidence
        confidence = self._calculate_confidence(
            sample_size=market.sample_size,
            std_dev=market.std_dev,
            avg_price=market.avg_price
        )
        
        # Step 10: Get comparable products
        comparable = await self._get_comparable_products(category, adjusted_price)
        
        # Add market trend reasoning
        if market.trend_direction == "rising":
            reasoning.append("📈 Giá thị trường đang tăng")
        elif market.trend_direction == "falling":
            reasoning.append("📉 Giá thị trường đang giảm")
        else:
            reasoning.append("📊 Giá thị trường ổn định")
        
        return PriceSuggestion(
            suggested_price=round(adjusted_price, 2),
            min_price=round(min_price, 2),
            max_price=round(max_price, 2),
            confidence=confidence,
            market_trend=market.trend_direction,
            reasoning=reasoning,
            comparable_products=comparable,
            demand_score=demand_score,
            supply_score=supply_score
        )
    
    async def _get_historical_prices(
        self,
        category: str,
        product_name: Optional[str] = None
    ) -> List[float]:
        """Get historical prices from products and quotes"""
        prices = []
        
        # Get prices from products
        query = select(Product.price).where(
            and_(
                Product.category == category,
                Product.price > 0,
                Product.is_active == True
            )
        )
        
        if product_name:
            # Fuzzy match on product name
            query = query.where(
                Product.name.ilike(f"%{product_name}%")
            )
        
        result = await self.db.execute(query)
        product_prices = [row[0] for row in result.fetchall()]
        prices.extend(product_prices)
        
        # Get prices from recent quotes (last 90 days)
        ninety_days_ago = datetime.utcnow() - timedelta(days=90)
        quote_query = select(Quote.price_per_unit).join(
            RFQ, Quote.rfq_id == RFQ.id
        ).where(
            and_(
                RFQ.category == category,
                Quote.price_per_unit > 0,
                Quote.created_at >= ninety_days_ago
            )
        )
        
        result = await self.db.execute(quote_query)
        quote_prices = [row[0] for row in result.fetchall()]
        prices.extend(quote_prices)
        
        return prices
    
    def _analyze_market(self, prices: List[float]) -> MarketAnalysis:
        """Analyze market prices"""
        if not prices:
            return MarketAnalysis(
                avg_price=0, median_price=0, std_dev=0,
                price_range=(0, 0), sample_size=0,
                trend_direction="stable", trend_strength=0
            )
        
        avg_price = statistics.mean(prices)
        median_price = statistics.median(prices)
        std_dev = statistics.stdev(prices) if len(prices) > 1 else 0
        
        # Simple trend detection (compare recent vs older prices)
        mid_point = len(prices) // 2
        if mid_point > 0:
            older_avg = statistics.mean(prices[:mid_point])
            recent_avg = statistics.mean(prices[mid_point:])
            
            change = (recent_avg - older_avg) / older_avg if older_avg > 0 else 0
            
            if change > 0.05:
                trend_direction = "rising"
                trend_strength = min(change, 1.0)
            elif change < -0.05:
                trend_direction = "falling"
                trend_strength = min(abs(change), 1.0)
            else:
                trend_direction = "stable"
                trend_strength = 0
        else:
            trend_direction = "stable"
            trend_strength = 0
        
        return MarketAnalysis(
            avg_price=avg_price,
            median_price=median_price,
            std_dev=std_dev,
            price_range=(min(prices), max(prices)),
            sample_size=len(prices),
            trend_direction=trend_direction,
            trend_strength=trend_strength
        )
    
    async def _get_category_average(self, category: str) -> MarketAnalysis:
        """Get average price for entire category"""
        result = await self.db.execute(
            select(
                func.avg(Product.price),
                func.min(Product.price),
                func.max(Product.price),
                func.count(Product.id)
            ).where(
                and_(
                    Product.category == category,
                    Product.price > 0,
                    Product.is_active == True
                )
            )
        )
        row = result.fetchone()
        
        if row and row[0]:
            return MarketAnalysis(
                avg_price=float(row[0]),
                median_price=float(row[0]),  # Use avg as median fallback
                std_dev=0,
                price_range=(float(row[1] or 0), float(row[2] or 0)),
                sample_size=int(row[3] or 0),
                trend_direction="stable",
                trend_strength=0
            )
        
        # Default fallback
        return MarketAnalysis(
            avg_price=100000,  # 100,000 VND default
            median_price=100000,
            std_dev=0,
            price_range=(50000, 200000),
            sample_size=0,
            trend_direction="stable",
            trend_strength=0
        )
    
    async def _calculate_demand_score(self, category: str) -> float:
        """
        Calculate demand score based on RFQ activity
        Score: 0-100
        """
        # Count RFQs in last 30 days
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        
        result = await self.db.execute(
            select(func.count(RFQ.id)).where(
                and_(
                    RFQ.category == category,
                    RFQ.created_at >= thirty_days_ago
                )
            )
        )
        rfq_count = result.scalar() or 0
        
        # Normalize to 0-100 (assuming 50 RFQs/month is high demand)
        demand_score = min(rfq_count * 2, 100)
        
        return demand_score
    
    async def _calculate_supply_score(self, category: str) -> float:
        """
        Calculate supply score based on product availability
        Score: 0-100
        """
        result = await self.db.execute(
            select(func.count(Product.id)).where(
                and_(
                    Product.category == category,
                    Product.is_active == True,
                    Product.stock > 0
                )
            )
        )
        product_count = result.scalar() or 0
        
        # Normalize to 0-100 (assuming 100 products is high supply)
        supply_score = min(product_count, 100)
        
        return supply_score
    
    def _calculate_quantity_discount(self, quantity: int) -> float:
        """Calculate discount based on quantity"""
        if quantity >= 1000:
            return 0.15  # 15% discount
        elif quantity >= 500:
            return 0.10  # 10% discount
        elif quantity >= 100:
            return 0.05  # 5% discount
        elif quantity >= 50:
            return 0.03  # 3% discount
        return 0
    
    def _calculate_demand_supply_factor(
        self,
        demand_score: float,
        supply_score: float
    ) -> float:
        """
        Calculate price adjustment factor based on demand/supply
        
        High demand + Low supply = Higher price (factor > 1)
        Low demand + High supply = Lower price (factor < 1)
        """
        if supply_score == 0:
            supply_score = 1  # Avoid division by zero
        
        ratio = demand_score / supply_score
        
        # Normalize ratio to factor between 0.9 and 1.1
        if ratio > 1:
            factor = min(1 + (ratio - 1) * 0.1, 1.15)
        else:
            factor = max(1 - (1 - ratio) * 0.1, 0.85)
        
        return factor
    
    def _calculate_confidence(
        self,
        sample_size: int,
        std_dev: float,
        avg_price: float
    ) -> float:
        """Calculate confidence score based on data quality"""
        # Base confidence on sample size
        if sample_size >= 50:
            size_confidence = 1.0
        elif sample_size >= 20:
            size_confidence = 0.8
        elif sample_size >= 10:
            size_confidence = 0.6
        elif sample_size >= 5:
            size_confidence = 0.4
        else:
            size_confidence = 0.2
        
        # Adjust for price variance (lower is better)
        if avg_price > 0:
            cv = std_dev / avg_price  # Coefficient of variation
            variance_confidence = max(0, 1 - cv)
        else:
            variance_confidence = 0.5
        
        # Combined confidence
        confidence = (size_confidence * 0.6 + variance_confidence * 0.4)
        
        return round(confidence, 2)
    
    async def _get_comparable_products(
        self,
        category: str,
        target_price: float,
        limit: int = 5
    ) -> List[Dict]:
        """Get comparable products near the target price"""
        result = await self.db.execute(
            select(Product).where(
                and_(
                    Product.category == category,
                    Product.is_active == True,
                    Product.price.between(target_price * 0.7, target_price * 1.3)
                )
            ).order_by(
                func.abs(Product.price - target_price)
            ).limit(limit)
        )
        
        products = result.scalars().all()
        
        return [
            {
                "id": p.id,
                "name": p.name,
                "price": p.price,
                "unit": p.unit,
                "supplier_id": p.supplier_id
            }
            for p in products
        ]
    
    def _demand_level(self, score: float) -> str:
        """Convert demand score to text"""
        if score >= 70:
            return "Rất cao 🔥"
        elif score >= 50:
            return "Cao 📈"
        elif score >= 30:
            return "Trung bình"
        else:
            return "Thấp 📉"
    
    def _supply_level(self, score: float) -> str:
        """Convert supply score to text"""
        if score >= 70:
            return "Dồi dào ✅"
        elif score >= 50:
            return "Đủ cung"
        elif score >= 30:
            return "Hạn chế ⚠️"
        else:
            return "Khan hiếm 🔴"


# API endpoint helper
async def get_ai_price_suggestion(
    db: AsyncSession,
    category: str,
    product_name: Optional[str] = None,
    quantity: int = 1,
    unit: str = "piece"
) -> dict:
    """
    Helper function to get AI price suggestion
    Returns dict for API response
    """
    service = AIPriceSuggestionService(db)
    suggestion = await service.get_price_suggestion(
        category=category,
        product_name=product_name,
        quantity=quantity,
        unit=unit
    )
    
    return {
        "suggested_price": suggestion.suggested_price,
        "min_price": suggestion.min_price,
        "max_price": suggestion.max_price,
        "confidence": suggestion.confidence,
        "confidence_percent": f"{suggestion.confidence * 100:.0f}%",
        "market_trend": suggestion.market_trend,
        "reasoning": suggestion.reasoning,
        "comparable_products": suggestion.comparable_products,
        "demand_score": suggestion.demand_score,
        "supply_score": suggestion.supply_score,
        "demand_level": service._demand_level(suggestion.demand_score),
        "supply_level": service._supply_level(suggestion.supply_score)
    }
