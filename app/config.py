from pydantic_settings import BaseSettings
from typing import List, Optional
import os

class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/b2b_marketplace"
    
    # JWT
    SECRET_KEY: str = "your-secret-key-change-in-production-min-32-chars"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # CORS - as string, will be parsed manually
    CORS_ORIGINS: str = ""
    
    # SMTP Email Settings
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    
    # Frontend URL (for email links)
    FRONTEND_URL: str = "http://localhost:5173"
    
    # App
    DEBUG: bool = False
    
    class Config:
        env_file = ".env"
        extra = "allow"

    def get_cors_origins(self) -> List[str]:
        """Parse CORS_ORIGINS string to list"""
        # Default origins
        default_origins = [
            "http://localhost:3000",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]
        
        # If CORS_ORIGINS is "*", allow all
        if self.CORS_ORIGINS == "*":
            return ["*"]
        
        # Parse from environment
        if self.CORS_ORIGINS:
            env_origins = [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]
            # Combine with defaults (avoid duplicates)
            all_origins = list(set(default_origins + env_origins))
            return all_origins
        
        return default_origins

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        # Fix DATABASE_URL for asyncpg (Render uses postgres://)
        if self.DATABASE_URL.startswith("postgres://"):
            self.DATABASE_URL = self.DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
        elif self.DATABASE_URL.startswith("postgresql://") and "+asyncpg" not in self.DATABASE_URL:
            self.DATABASE_URL = self.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

settings = Settings()
