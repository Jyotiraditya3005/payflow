from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    APP_NAME: str = "PayFlow Fraud Detection Service"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"
    API_V1_PREFIX: str = "/api/v1"
    SERVICE_PORT: int = 8003

    DATABASE_URL: str = "postgresql+asyncpg://payflow:payflow@postgres:5432/payflow_fraud"
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 5

    REDIS_URL: str = "redis://redis:6379/0"

    KAFKA_BOOTSTRAP_SERVERS: str = "kafka:9092"
    KAFKA_TOPIC_FRAUD_ALERTS: str = "fraud.alerts"

    MAX_TRANSACTION_AMOUNT: float = 1_000_000.0

    class Config:
        env_file = ".env"

@lru_cache()
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
