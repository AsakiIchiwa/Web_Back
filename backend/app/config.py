from pydantic_settings import BaseSettings
from typing import List
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
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173"
    
    # App
    DEBUG: bool = False
    
    class Config:
        env_file = ".env"
        extra = "allow"

    def get_cors_origins(self) -> List[str]:
        """Parse CORS_ORIGINS string to list"""
        if not self.CORS_ORIGINS:
            return ["http://localhost:3000", "http://localhost:5173"]
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        # Fix DATABASE_URL for asyncpg (Render uses postgres://)
        if self.DATABASE_URL.startswith("postgres://"):
            self.DATABASE_URL = self.DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
        elif self.DATABASE_URL.startswith("postgresql://") and "+asyncpg" not in self.DATABASE_URL:
            self.DATABASE_URL = self.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

settings = Settings()
