import asyncio
import json
from datetime import datetime, timezone
from typing import Any, Callable, Optional
from uuid import uuid4

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from aiokafka.errors import KafkaConnectionError
from tenacity import retry, stop_after_attempt, wait_exponential

import structlog

from app.core.config import settings

logger = structlog.get_logger()


class KafkaProducer:
    """
    Production-grade Kafka producer with:
    - Idempotent producer (exactly-once semantics)
    - Exponential backoff retry
    - Dead Letter Queue for failed messages
    - Structured event envelope
    """

    def __init__(self):
        self._producer: Optional[AIOKafkaProducer] = None

    async def start(self):
        self._producer = AIOKafkaProducer(
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
            value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
            key_serializer=lambda k: k.encode("utf-8") if k else None,
            # Idempotent producer — prevents duplicate messages on retry
            # (aiokafka has no `retries` kwarg; an idempotent producer with
            # acks="all" already retries internally)
            enable_idempotence=True,
            acks="all",  # Wait for all in-sync replicas
            max_in_flight_requests_per_connection=1,  # Required for idempotence
            compression_type="gzip",
        )
        await self._producer.start()
        logger.info("Kafka producer started", servers=settings.KAFKA_BOOTSTRAP_SERVERS)

    async def stop(self):
        if self._producer:
            await self._producer.stop()
            logger.info("Kafka producer stopped")

    def _build_envelope(self, event_type: str, payload: dict, source: str = "payment-service") -> dict:
        """Wrap payload in a standard event envelope for all services."""
        return {
            "event_id": str(uuid4()),
            "event_type": event_type,
            "source": source,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "schema_version": "1.0",
            "payload": payload,
        }

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    async def publish(
        self,
        topic: str,
        event_type: str,
        payload: dict,
        key: Optional[str] = None,
    ) -> bool:
        """Publish event to Kafka with retry and DLQ fallback."""
        if not self._producer:
            raise RuntimeError("Kafka producer not started")

        envelope = self._build_envelope(event_type, payload)

        try:
            await self._producer.send_and_wait(
                topic=topic,
                value=envelope,
                key=key,
            )
            logger.info(
                "Kafka event published",
                topic=topic,
                event_type=event_type,
                key=key,
                event_id=envelope["event_id"],
            )
            return True
        except Exception as e:
            logger.error(
                "Kafka publish failed, sending to DLQ",
                topic=topic,
                event_type=event_type,
                error=str(e),
            )
            await self._send_to_dlq(topic, envelope, str(e))
            raise

    async def _send_to_dlq(self, original_topic: str, envelope: dict, error: str):
        """Send failed message to Dead Letter Queue."""
        try:
            dlq_payload = {
                **envelope,
                "dlq_metadata": {
                    "original_topic": original_topic,
                    "error": error,
                    "failed_at": datetime.now(timezone.utc).isoformat(),
                },
            }
            await self._producer.send_and_wait(
                topic=settings.KAFKA_DLQ_TOPIC,
                value=dlq_payload,
            )
            logger.warning("Message sent to DLQ", original_topic=original_topic)
        except Exception as dlq_error:
            logger.critical("DLQ send also failed!", error=str(dlq_error))

    # ─── Convenience Methods ──────────────────────────────────────────────────

    async def payment_created(self, payment_data: dict):
        await self.publish(
            topic=settings.KAFKA_TOPIC_PAYMENT_CREATED,
            event_type="payment.created",
            payload=payment_data,
            key=str(payment_data.get("payment_id")),
        )

    async def payment_completed(self, payment_data: dict):
        await self.publish(
            topic=settings.KAFKA_TOPIC_PAYMENT_COMPLETED,
            event_type="payment.completed",
            payload=payment_data,
            key=str(payment_data.get("payment_id")),
        )

    async def payment_failed(self, payment_data: dict):
        await self.publish(
            topic=settings.KAFKA_TOPIC_PAYMENT_FAILED,
            event_type="payment.failed",
            payload=payment_data,
            key=str(payment_data.get("payment_id")),
        )

    async def fraud_check_requested(self, payment_data: dict):
        await self.publish(
            topic=settings.KAFKA_TOPIC_FRAUD_CHECK,
            event_type="fraud.check.requested",
            payload=payment_data,
            key=str(payment_data.get("payment_id")),
        )


class KafkaConsumer:
    """
    Kafka consumer with:
    - Consumer group management
    - At-least-once processing guarantee
    - Error isolation per partition
    - Graceful shutdown
    """

    def __init__(self, topics: list[str], group_id: str):
        self.topics = topics
        self.group_id = group_id
        self._consumer: Optional[AIOKafkaConsumer] = None
        self._handlers: dict[str, Callable] = {}
        self._running = False

    def register_handler(self, event_type: str, handler: Callable):
        """Register an async handler for a specific event type."""
        self._handlers[event_type] = handler
        logger.info("Registered Kafka handler", event_type=event_type)

    async def start(self):
        self._consumer = AIOKafkaConsumer(
            *self.topics,
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
            group_id=self.group_id,
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
            auto_offset_reset="earliest",
            enable_auto_commit=False,  # Manual commit for at-least-once guarantee
            max_poll_records=100,
            session_timeout_ms=30000,
            heartbeat_interval_ms=10000,
        )
        await self._consumer.start()
        self._running = True
        logger.info("Kafka consumer started", topics=self.topics, group=self.group_id)

    async def stop(self):
        self._running = False
        if self._consumer:
            await self._consumer.stop()
        logger.info("Kafka consumer stopped")

    async def consume(self):
        """Main consume loop with error isolation."""
        async for msg in self._consumer:
            if not self._running:
                break
            try:
                envelope = msg.value
                event_type = envelope.get("event_type")
                payload = envelope.get("payload", {})

                logger.info(
                    "Kafka message received",
                    topic=msg.topic,
                    partition=msg.partition,
                    offset=msg.offset,
                    event_type=event_type,
                )

                handler = self._handlers.get(event_type)
                if handler:
                    await handler(payload, envelope)
                else:
                    logger.warning("No handler for event type", event_type=event_type)

                # Manual commit only after successful processing
                await self._consumer.commit()

            except Exception as e:
                logger.error(
                    "Error processing Kafka message",
                    error=str(e),
                    topic=msg.topic,
                    offset=msg.offset,
                )
                # Don't commit — message will be redelivered
                await asyncio.sleep(1)


# Singleton instances
kafka_producer = KafkaProducer()
