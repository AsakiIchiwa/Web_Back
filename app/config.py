from pydantic_settings import BaseSettings
from typing import List, Optional
from urllib.parse import urlparse, urlencode, parse_qs, urlunparse
import os

class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql://bmdtlab_postgres_user:2kbLp1bXScsHybzNfim5sQHghAilNRXG@dpg-d4nado4hg0os73cidjug-a.singapore-postgres.render.com/bmdtlab_postgres"
    
    # JWT
    SECRET_KEY: str = "ddd8483072cef66d7e8d71bc67cc4006"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # CORS
    CORS_ORIGINS: str = ""
    
    # SMTP Email Settings
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    
    # Resend API
    RESEND_API_KEY: Optional[str] = "re_YivFiCdu_FTCnoD2JbtgGGFQLNfMTYiwT"
    EMAIL_FROM: Optional[str] = "B2B Marketplace <noreply@bmdtlab.site>"
    
    # Frontend URL
    FRONTEND_URL: str = "https://b2b-marketplace-zeta.vercel.app"
    
    # App
    DEBUG: bool = False
    
    class Config:
        env_file = ".env"
        extra = "allow"

    def get_cors_origins(self) -> List[str]:
        default_origins = [
            "https://b2b-marketplace-zeta.vercel.app",
            "http://localhost:3000",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]
        if self.CORS_ORIGINS == "*":
            return ["*"]
        if self.CORS_ORIGINS:
            env_origins = [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]
            return list(set(default_origins + env_origins))
        return default_origins

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        # Fix driver: postgres:// or postgresql:// → postgresql+asyncpg://
        if self.DATABASE_URL.startswith("postgres://"):
            self.DATABASE_URL = self.DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
        elif self.DATABASE_URL.startswith("postgresql://") and "+asyncpg" not in self.DATABASE_URL:
            self.DATABASE_URL = self.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
        
        # Strip sslmode from URL (asyncpg rejects it as a query param)
        if "sslmode=" in self.DATABASE_URL:
            parsed = urlparse(self.DATABASE_URL)
            params = {k: v for k, v in parse_qs(parsed.query).items() if k != "sslmode"}
            clean_query = urlencode({k: v[0] for k, v in params.items()})
            self.DATABASE_URL = urlunparse(parsed._replace(query=clean_query))

settings = Settings()
