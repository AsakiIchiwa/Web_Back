"""
ChatGPT-powered AI Assistant for B2B Marketplace
Uses OpenAI GPT API for intelligent features
"""

import os
import json
from typing import Optional, List, Dict, Any
from datetime import datetime
import httpx

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from app.models import Product, Quote, Contract, RFQ, Supplier, Shop, ProductStatus


class ChatGPTService:
    """
    ChatGPT-powered AI features for B2B Marketplace
    
    Features:
    - Product description generation
    - Price negotiation suggestions
    - Market analysis & insights
    - RFQ response drafting
    - Contract term suggestions
    - Business chat assistant
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.api_url = "https://api.openai.com/v1/chat/completions"
        self.model = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
    
    async def _call_gpt(
        self, 
        system_prompt: str, 
        user_message: str,
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> str:
        """Call ChatGPT API"""
        if not self.api_key:
            return "⚠️ OpenAI API key chưa được cấu hình. Vui lòng thêm OPENAI_API_KEY vào file .env"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.api_url,
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"]
        except httpx.TimeoutException:
            return "⚠️ Yêu cầu timeout. Vui lòng thử lại."
        except httpx.HTTPStatusError as e:
            return f"⚠️ Lỗi API: {e.response.status_code}"
        except Exception as e:
            return f"⚠️ Lỗi: {str(e)}"
    
    # ==================== SUPPLIER FEATURES ====================
    
    async def generate_product_description(
        self,
        product_name: str,
        category: str,
        features: Optional[str] = None,
        target_audience: str = "doanh nghiệp B2B"
    ) -> Dict[str, str]:
        """Generate professional product description"""
        system_prompt = """Bạn là chuyên gia marketing B2B tại Việt Nam. 
        Tạo mô tả sản phẩm chuyên nghiệp, hấp dẫn cho doanh nghiệp.
        Sử dụng tiếng Việt, ngắn gọn nhưng đầy đủ thông tin.
        Trả về JSON với format: {"short_desc": "...", "full_desc": "...", "key_features": ["...", "..."], "seo_keywords": ["...", "..."]}"""
        
        user_message = f"""Tạo mô tả sản phẩm:
- Tên: {product_name}
- Danh mục: {category}
- Đặc điểm: {features or 'Chưa có'}
- Đối tượng: {target_audience}"""
        
        result = await self._call_gpt(system_prompt, user_message, temperature=0.7)
        
        try:
            # Try to parse JSON
            return json.loads(result)
        except:
            return {
                "short_desc": result[:200],
                "full_desc": result,
                "key_features": [],
                "seo_keywords": []
            }
    
    async def suggest_pricing_strategy(
        self,
        product_name: str,
        category: str,
        cost_price: float,
        competitor_prices: Optional[List[float]] = None,
        target_margin: float = 20
    ) -> Dict[str, Any]:
        """Suggest optimal pricing strategy"""
        # Get market data
        market_data = await self._get_market_context(category)
        
        system_prompt = """Bạn là chuyên gia định giá B2B. Phân tích và đề xuất chiến lược giá.
        Trả về JSON: {"suggested_price": number, "min_price": number, "max_price": number, "strategy": "...", "reasoning": ["...", "..."], "tips": ["...", "..."]}"""
        
        user_message = f"""Phân tích chiến lược giá:
- Sản phẩm: {product_name}
- Danh mục: {category}
- Giá vốn: {cost_price:,.0f} VND
- Giá đối thủ: {competitor_prices or 'Chưa có'}
- Mục tiêu lợi nhuận: {target_margin}%
- Dữ liệu thị trường: {json.dumps(market_data, ensure_ascii=False)}"""
        
        result = await self._call_gpt(system_prompt, user_message, temperature=0.5)
        
        try:
            return json.loads(result)
        except:
            return {"raw_response": result}
    
    async def draft_quote_response(
        self,
        rfq_details: Dict,
        supplier_info: Dict,
        proposed_price: float,
        delivery_days: int
    ) -> str:
        """Draft professional quote response"""
        system_prompt = """Bạn là nhân viên kinh doanh B2B chuyên nghiệp. 
        Viết phản hồi báo giá lịch sự, chuyên nghiệp, thuyết phục.
        Sử dụng tiếng Việt, ngắn gọn, đi vào trọng tâm."""
        
        user_message = f"""Viết phản hồi báo giá:
- Sản phẩm: {rfq_details.get('product_name', 'N/A')}
- Số lượng yêu cầu: {rfq_details.get('quantity', 0)}
- Giá đề xuất: {proposed_price:,.0f} VND/đơn vị
- Thời gian giao hàng: {delivery_days} ngày
- Nhà cung cấp: {supplier_info.get('company_name', 'N/A')}
- Ghi chú từ khách: {rfq_details.get('message', 'Không có')}"""
        
        return await self._call_gpt(system_prompt, user_message, temperature=0.6)
    
    # ==================== SHOP FEATURES ====================
    
    async def analyze_supplier(
        self,
        supplier_id: int
    ) -> Dict[str, Any]:
        """Analyze supplier reliability and performance"""
        # Get supplier data
        supplier_data = await self._get_supplier_data(supplier_id)
        
        system_prompt = """Bạn là chuyên gia đánh giá nhà cung cấp B2B.
        Phân tích và đưa ra nhận xét về nhà cung cấp.
        Trả về JSON: {"score": 1-10, "strengths": ["...", "..."], "concerns": ["...", "..."], "recommendation": "...", "negotiation_tips": ["...", "..."]}"""
        
        user_message = f"""Đánh giá nhà cung cấp:
{json.dumps(supplier_data, ensure_ascii=False, indent=2)}"""
        
        result = await self._call_gpt(system_prompt, user_message, temperature=0.5)
        
        try:
            return json.loads(result)
        except:
            return {"raw_response": result}
    
    async def suggest_negotiation_strategy(
        self,
        product_name: str,
        listed_price: float,
        quantity: int,
        market_avg_price: Optional[float] = None
    ) -> Dict[str, Any]:
        """Suggest negotiation strategy for buyers"""
        system_prompt = """Bạn là chuyên gia đàm phán mua hàng B2B.
        Đưa ra chiến lược đàm phán hiệu quả.
        Trả về JSON: {"target_price": number, "opening_offer": number, "walk_away_price": number, "strategy": "...", "talking_points": ["...", "..."], "counter_arguments": ["...", "..."]}"""
        
        user_message = f"""Đề xuất chiến lược đàm phán:
- Sản phẩm: {product_name}
- Giá niêm yết: {listed_price:,.0f} VND
- Số lượng cần mua: {quantity}
- Giá thị trường trung bình: {f'{market_avg_price:,.0f} VND' if market_avg_price else 'Chưa có'}"""
        
        result = await self._call_gpt(system_prompt, user_message, temperature=0.6)
        
        try:
            return json.loads(result)
        except:
            return {"raw_response": result}
    
    async def draft_rfq_message(
        self,
        product_name: str,
        quantity: int,
        requirements: Optional[str] = None,
        deadline: Optional[str] = None
    ) -> str:
        """Draft professional RFQ message"""
        system_prompt = """Bạn là chuyên viên thu mua B2B chuyên nghiệp.
        Viết yêu cầu báo giá rõ ràng, đầy đủ thông tin, lịch sự."""
        
        user_message = f"""Viết yêu cầu báo giá:
- Sản phẩm: {product_name}
- Số lượng: {quantity}
- Yêu cầu đặc biệt: {requirements or 'Không có'}
- Deadline: {deadline or 'Linh hoạt'}"""
        
        return await self._call_gpt(system_prompt, user_message, temperature=0.6)
    
    # ==================== SHARED FEATURES ====================
    
    async def chat_assistant(
        self,
        message: str,
        user_role: str,
        context: Optional[Dict] = None
    ) -> str:
        """General chat assistant for marketplace"""
        role_context = {
            "supplier": "Bạn đang hỗ trợ một nhà cung cấp trên sàn B2B",
            "shop": "Bạn đang hỗ trợ một cửa hàng/doanh nghiệp mua hàng trên sàn B2B",
            "admin": "Bạn đang hỗ trợ quản trị viên sàn B2B"
        }
        
        system_prompt = f"""Bạn là trợ lý AI thông minh cho sàn thương mại B2B Việt Nam.
        {role_context.get(user_role, '')}
        
        Bạn có thể giúp:
        - Tư vấn chiến lược kinh doanh
        - Phân tích thị trường
        - Hỗ trợ đàm phán
        - Giải đáp thắc mắc về quy trình
        - Đề xuất cải thiện
        
        Trả lời bằng tiếng Việt, thân thiện, chuyên nghiệp."""
        
        if context:
            system_prompt += f"\n\nContext: {json.dumps(context, ensure_ascii=False)}"
        
        return await self._call_gpt(system_prompt, message, temperature=0.7, max_tokens=1500)
    
    async def generate_contract_terms(
        self,
        product_name: str,
        quantity: int,
        price: float,
        delivery_terms: str = "FOB",
        payment_terms: str = "30 ngày"
    ) -> str:
        """Generate contract terms template"""
        system_prompt = """Bạn là chuyên gia pháp lý thương mại B2B Việt Nam.
        Tạo điều khoản hợp đồng mẫu, đầy đủ, rõ ràng, bảo vệ quyền lợi cả hai bên."""
        
        user_message = f"""Tạo điều khoản hợp đồng:
- Sản phẩm: {product_name}
- Số lượng: {quantity}
- Giá trị: {price:,.0f} VND
- Điều kiện giao hàng: {delivery_terms}
- Điều khoản thanh toán: {payment_terms}"""
        
        return await self._call_gpt(system_prompt, user_message, temperature=0.3, max_tokens=2000)
    
    async def market_insights(
        self,
        category: str
    ) -> Dict[str, Any]:
        """Get AI-powered market insights"""
        market_data = await self._get_market_context(category)
        
        system_prompt = """Bạn là chuyên gia phân tích thị trường B2B Việt Nam.
        Phân tích dữ liệu và đưa ra insights hữu ích.
        Trả về JSON: {"summary": "...", "trends": ["...", "..."], "opportunities": ["...", "..."], "risks": ["...", "..."], "recommendations": ["...", "..."]}"""
        
        user_message = f"""Phân tích thị trường ngành {category}:
{json.dumps(market_data, ensure_ascii=False, indent=2)}"""
        
        result = await self._call_gpt(system_prompt, user_message, temperature=0.6)
        
        try:
            return json.loads(result)
        except:
            return {"raw_response": result}
    
    # ==================== HELPER METHODS ====================
    
    async def _get_market_context(self, category: str) -> Dict:
        """Get market context data for AI"""
        # Products count and price range - FIXED: Use status instead of is_active
        result = await self.db.execute(
            select(
                func.count(Product.id),
                func.avg(Product.price),
                func.min(Product.price),
                func.max(Product.price)
            ).where(
                and_(
                    Product.category == category,
                    Product.status == ProductStatus.ACTIVE  # FIXED: Changed from is_active
                )
            )
        )
        row = result.fetchone()
        
        # RFQ count (demand indicator)
        rfq_result = await self.db.execute(
            select(func.count(RFQ.id)).where(RFQ.category == category)
        )
        rfq_count = rfq_result.scalar() or 0
        
        # Supplier count
        supplier_result = await self.db.execute(
            select(func.count(func.distinct(Product.supplier_id))).where(
                Product.category == category
            )
        )
        supplier_count = supplier_result.scalar() or 0
        
        return {
            "category": category,
            "total_products": row[0] if row else 0,
            "avg_price": float(row[1]) if row and row[1] else 0,
            "min_price": float(row[2]) if row and row[2] else 0,
            "max_price": float(row[3]) if row and row[3] else 0,
            "total_rfqs": rfq_count,
            "total_suppliers": supplier_count
        }
    
    async def _get_supplier_data(self, supplier_id: int) -> Dict:
        """Get supplier data for analysis"""
        # Get supplier
        result = await self.db.execute(
            select(Supplier).where(Supplier.id == supplier_id)
        )
        supplier = result.scalar_one_or_none()
        
        if not supplier:
            return {"error": "Supplier not found"}
        
        # Get products count - FIXED: Use status instead of is_active
        products_result = await self.db.execute(
            select(func.count(Product.id)).where(
                and_(
                    Product.supplier_id == supplier_id,
                    Product.status == ProductStatus.ACTIVE  # FIXED: Changed from is_active
                )
            )
        )
        products_count = products_result.scalar() or 0
        
        # Get contracts count
        contracts_result = await self.db.execute(
            select(func.count(Contract.id)).where(
                Contract.supplier_id == supplier_id
            )
        )
        contracts_count = contracts_result.scalar() or 0
        
        # Get quotes count
        quotes_result = await self.db.execute(
            select(func.count(Quote.id)).where(
                Quote.supplier_id == supplier_id
            )
        )
        quotes_count = quotes_result.scalar() or 0
        
        return {
            "company_name": supplier.company_name,
            "description": supplier.description,
            "address": supplier.address,
            "total_products": products_count,
            "total_contracts": contracts_count,
            "total_quotes": quotes_count,
            "member_since": supplier.created_at.isoformat() if supplier.created_at else None
        }


# API helper functions
async def get_chatgpt_service(db: AsyncSession) -> ChatGPTService:
    """Get ChatGPT service instance"""
    return ChatGPTService(db)