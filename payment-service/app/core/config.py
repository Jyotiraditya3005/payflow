from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # App
    APP_NAME: str = "PayFlow Payment Service"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"

    # API
    API_V1_PREFIX: str = "/api/v1"
    SERVICE_PORT: int = 8001

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://payflow:payflow@postgres:5432/payflow_payments"
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10

    # Redis
    REDIS_URL: str = "redis://redis:6379/0"
    REDIS_IDEMPOTENCY_TTL: int = 86400  # 24 hours
    REDIS_RATE_LIMIT_WINDOW: int = 60   # 1 minute

    # Kafka
    KAFKA_BOOTSTRAP_SERVERS: str = "kafka:9092"
    KAFKA_TOPIC_PAYMENT_CREATED: str = "payments.created"
    KAFKA_TOPIC_PAYMENT_COMPLETED: str = "payments.completed"
    KAFKA_TOPIC_PAYMENT_FAILED: str = "payments.failed"
    KAFKA_TOPIC_FRAUD_CHECK: str = "fraud.check"
    KAFKA_CONSUMER_GROUP: str = "payment-service-group"
    KAFKA_RETRY_TOPIC: str = "payments.retry"
    KAFKA_DLQ_TOPIC: str = "payments.dlq"

    # JWT
    JWT_SECRET_KEY: str = "super-secret-jwt-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Auth Service
    AUTH_SERVICE_URL: str = "http://auth-service:8000"

    # Fraud Service
    FRAUD_SERVICE_URL: str = "http://fraud-service:8003"

    # Rate Limiting
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = 100
    RATE_LIMIT_MERCHANT_PER_MINUTE: int = 1000

    # Payment Settings
    MAX_TRANSACTION_AMOUNT: float = 1_000_000.0
    MIN_TRANSACTION_AMOUNT: float = 0.01
    PAYMENT_TIMEOUT_SECONDS: int = 30
    MAX_RETRY_ATTEMPTS: int = 3

    # Observability
    JAEGER_HOST: str = "jaeger"
    JAEGER_PORT: int = 6831
    PROMETHEUS_PORT: int = 9001

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
