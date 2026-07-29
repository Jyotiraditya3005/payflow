from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    APP_NAME: str = "PayFlow Auth Service"
    APP_VERSION: str = "1.0.0"
    SERVICE_PORT: int = 8000
    DATABASE_URL: str = "postgresql+asyncpg://payflow:payflow@postgres:5432/payflow_auth"
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 5

    class Config:
        env_file = ".env"

@lru_cache()
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
