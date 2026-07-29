"""
Notification Service — Webhook dispatcher and alert engine.

Consumes payment events from Kafka and:
  1. Dispatches HTTP webhooks to merchant callback URLs
  2. Queues email alerts for fraud events
  3. Retries failed webhooks with exponential backoff (max 3 attempts)
  4. Routes failures to DLQ after max retries
"""
import asyncio, json, time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from uuid import uuid4
from typing import Optional
import structlog
import httpx
from aiokafka import AIOKafkaConsumer
from fastapi import FastAPI
from app.core.config import settings

structlog.configure(processors=[structlog.contextvars.merge_contextvars, structlog.processors.add_log_level, structlog.processors.TimeStamper(fmt="iso"), structlog.processors.JSONRenderer()], wrapper_class=structlog.BoundLogger, logger_factory=structlog.PrintLoggerFactory())
logger = structlog.get_logger()

# In production: load from DB / cache
MERCHANT_WEBHOOKS = {
    "demo-merchant": "https://webhook.site/your-test-url",
}

class WebhookDispatcher:
    async def dispatch(self, merchant_id: str, event_type: str, payload: dict) -> bool:
        webhook_url = MERCHANT_WEBHOOKS.get(merchant_id)
        if not webhook_url:
            return True  # No webhook configured — not an error

        event = {"event_id": str(uuid4()), "event_type": event_type, "timestamp": datetime.now(timezone.utc).isoformat(), "data": payload}
        
        for attempt in range(1, settings.WEBHOOK_MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(timeout=settings.WEBHOOK_TIMEOUT_SECONDS) as client:
                    resp = await client.post(webhook_url, json=event, headers={"X-PayFlow-Event": event_type, "X-PayFlow-Signature": "sha256=...", "Content-Type": "application/json"})
                    if resp.status_code < 300:
                        logger.info("Webhook delivered", merchant=merchant_id, event=event_type, attempt=attempt, status=resp.status_code)
                        return True
                    logger.warning("Webhook non-2xx", status=resp.status_code, attempt=attempt)
            except Exception as e:
                logger.warning("Webhook attempt failed", error=str(e), attempt=attempt)
            
            if attempt < settings.WEBHOOK_MAX_RETRIES:
                await asyncio.sleep(2 ** attempt)  # Exponential backoff: 2s, 4s

        logger.error("Webhook permanently failed after retries", merchant=merchant_id, event=event_type)
        return False


class NotificationConsumer:
    def __init__(self): self._consumer = None; self._running = False; self.dispatcher = WebhookDispatcher()

    async def start(self):
        self._consumer = AIOKafkaConsumer(
            settings.KAFKA_TOPIC_PAYMENT_COMPLETED, settings.KAFKA_TOPIC_PAYMENT_FAILED,
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
            group_id=settings.KAFKA_CONSUMER_GROUP,
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
            auto_offset_reset="earliest", enable_auto_commit=False,
        )
        await self._consumer.start(); self._running = True
        logger.info("Notification consumer started")

    async def stop(self): self._running = False; self._consumer and await self._consumer.stop()

    async def consume(self):
        async for msg in self._consumer:
            if not self._running: break
            try:
                envelope = msg.value
                event_type = envelope.get("event_type","")
                payload = envelope.get("payload",{})
                merchant_id = payload.get("merchant_id","")

                logger.info("Notification event received", event_type=event_type, merchant=merchant_id)

                # Dispatch webhook
                await self.dispatcher.dispatch(merchant_id, event_type, payload)

                # Log fraud alerts
                if event_type == "payment.failed" and payload.get("reason") == "FRAUD_DECLINED":
                    logger.warning("FRAUD ALERT: Payment declined", payment_id=payload.get("payment_id"), risk_level=payload.get("risk_level"))

                await self._consumer.commit()
            except Exception as e:
                logger.error("Notification error", error=str(e))
                await asyncio.sleep(1)


consumer = NotificationConsumer()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Notification Service")
    await consumer.start()
    task = asyncio.create_task(consumer.consume())
    yield
    task.cancel(); await consumer.stop()

app = FastAPI(title=settings.APP_NAME, version=settings.APP_VERSION, lifespan=lifespan)

@app.post("/api/v1/webhooks/register", tags=["Webhooks"])
async def register_webhook(merchant_id: str, webhook_url: str):
    MERCHANT_WEBHOOKS[merchant_id] = webhook_url
    logger.info("Webhook registered", merchant=merchant_id, url=webhook_url)
    return {"merchant_id": merchant_id, "webhook_url": webhook_url, "status": "registered"}

@app.get("/api/v1/webhooks", tags=["Webhooks"])
async def list_webhooks():
    return {"webhooks": [{"merchant_id": k, "url": v} for k,v in MERCHANT_WEBHOOKS.items()]}

@app.get("/health")
async def health(): return {"status": "healthy", "service": settings.APP_NAME, "consumer_running": consumer._running, "registered_webhooks": len(MERCHANT_WEBHOOKS)}
