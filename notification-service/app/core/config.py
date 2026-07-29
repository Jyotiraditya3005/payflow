from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    APP_NAME: str = "PayFlow Notification Service"
    APP_VERSION: str = "1.0.0"
    SERVICE_PORT: int = 8006
    KAFKA_BOOTSTRAP_SERVERS: str = "kafka:9092"
    KAFKA_CONSUMER_GROUP: str = "notification-service-group"
    KAFKA_TOPIC_PAYMENT_COMPLETED: str = "payments.completed"
    KAFKA_TOPIC_PAYMENT_FAILED: str = "payments.failed"
    KAFKA_TOPIC_WEBHOOKS: str = "webhooks.dispatch"
    WEBHOOK_TIMEOUT_SECONDS: int = 10
    WEBHOOK_MAX_RETRIES: int = 3
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""

    class Config:
        env_file = ".env"

@lru_cache()
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
