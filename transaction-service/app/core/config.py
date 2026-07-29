from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    APP_NAME: str = "PayFlow Transaction Service"
    APP_VERSION: str = "1.0.0"
    SERVICE_PORT: int = 8004
    DATABASE_URL: str = "postgresql+asyncpg://payflow:payflow@postgres:5432/payflow_transactions"
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10
    REDIS_URL: str = "redis://redis:6379/0"
    KAFKA_BOOTSTRAP_SERVERS: str = "kafka:9092"
    KAFKA_CONSUMER_GROUP: str = "transaction-service-group"
    KAFKA_TOPIC_PAYMENT_CREATED: str = "payments.created"
    KAFKA_TOPIC_PAYMENT_COMPLETED: str = "payments.completed"
    KAFKA_TOPIC_PAYMENT_FAILED: str = "payments.failed"

    class Config:
        env_file = ".env"

@lru_cache()
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
