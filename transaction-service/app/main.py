"""
Transaction Service — Kafka consumer that materialises payment events
into queryable transaction_records and exposes a REST query API.
"""
import asyncio
import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

import structlog
from aiokafka import AIOKafkaConsumer
from fastapi import FastAPI, Depends, Query, HTTPException
from sqlalchemy import Column, String, Numeric, DateTime, Float
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func
from sqlalchemy import select

from app.core.config import settings
from app.db.session import Base, get_db, create_tables

structlog.configure(processors=[structlog.contextvars.merge_contextvars, structlog.processors.add_log_level, structlog.processors.TimeStamper(fmt="iso"), structlog.processors.JSONRenderer()], wrapper_class=structlog.BoundLogger, logger_factory=structlog.PrintLoggerFactory())
logger = structlog.get_logger()


class Transaction(Base):
    __tablename__ = "transaction_records"
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    payment_id = Column(PGUUID(as_uuid=True), nullable=False, index=True, unique=True)
    merchant_id = Column(PGUUID(as_uuid=True), nullable=False, index=True)
    customer_id = Column(PGUUID(as_uuid=True), nullable=False, index=True)
    amount = Column(Numeric(20, 4), nullable=False)
    currency = Column(String(10), nullable=False)
    status = Column(String(30), nullable=False, index=True)
    payment_method = Column(String(30))
    fraud_risk = Column(String(20))
    fraud_score = Column(Float)
    net_amount = Column(Numeric(20, 4))
    fee_amount = Column(Numeric(20, 4))
    event_type = Column(String(100))
    raw_payload = Column(JSONB, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class TransactionConsumer:
    def __init__(self):
        self._consumer = None
        self._running = False

    async def start(self):
        self._consumer = AIOKafkaConsumer(
            settings.KAFKA_TOPIC_PAYMENT_CREATED,
            settings.KAFKA_TOPIC_PAYMENT_COMPLETED,
            settings.KAFKA_TOPIC_PAYMENT_FAILED,
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
            group_id=settings.KAFKA_CONSUMER_GROUP,
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
            auto_offset_reset="earliest",
            enable_auto_commit=False,
        )
        await self._consumer.start()
        self._running = True
        logger.info("Transaction consumer started")

    async def stop(self):
        self._running = False
        if self._consumer:
            await self._consumer.stop()

    async def consume(self):
        from app.db.session import AsyncSessionLocal
        async for msg in self._consumer:
            if not self._running:
                break
            try:
                envelope = msg.value
                event_type = envelope.get("event_type", "")
                payload = envelope.get("payload", {})
                payment_id = payload.get("payment_id")
                if not payment_id:
                    await self._consumer.commit()
                    continue

                async with AsyncSessionLocal() as session:
                    existing = await session.execute(select(Transaction).where(Transaction.payment_id == payment_id))
                    txn = existing.scalar_one_or_none()
                    if txn:
                        txn.status = payload.get("status", txn.status)
                        txn.event_type = event_type
                        txn.raw_payload = payload
                        txn.updated_at = datetime.now(timezone.utc)
                    else:
                        txn = Transaction(
                            payment_id=payment_id,
                            merchant_id=payload.get("merchant_id", str(uuid4())),
                            customer_id=payload.get("customer_id", str(uuid4())),
                            amount=payload.get("amount", 0),
                            currency=payload.get("currency", "USD"),
                            status=payload.get("status", "UNKNOWN"),
                            payment_method=payload.get("payment_method"),
                            fraud_risk=payload.get("fraud_risk"),
                            fraud_score=payload.get("fraud_score"),
                            net_amount=payload.get("net_amount"),
                            fee_amount=payload.get("fee_amount"),
                            event_type=event_type,
                            raw_payload=payload,
                        )
                        session.add(txn)
                    await session.commit()
                    logger.info("Transaction upserted", payment_id=payment_id, event=event_type)
                await self._consumer.commit()
            except Exception as e:
                logger.error("Consumer error", error=str(e))
                await asyncio.sleep(1)


consumer = TransactionConsumer()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Transaction Service")
    await create_tables()
    await consumer.start()
    task = asyncio.create_task(consumer.consume())
    yield
    task.cancel()
    await consumer.stop()


app = FastAPI(title=settings.APP_NAME, version=settings.APP_VERSION, lifespan=lifespan)


@app.get("/api/v1/transactions", tags=["Transactions"])
async def list_transactions(merchant_id: Optional[str] = None, customer_id: Optional[str] = None, status: Optional[str] = None, page: int = Query(default=1, ge=1), page_size: int = Query(default=20, ge=1, le=100), db: AsyncSession = Depends(get_db)):
    query = select(Transaction)
    if merchant_id: query = query.where(Transaction.merchant_id == merchant_id)
    if customer_id: query = query.where(Transaction.customer_id == customer_id)
    if status:      query = query.where(Transaction.status == status)
    result = await db.execute(query.order_by(Transaction.created_at.desc()).offset((page-1)*page_size).limit(page_size))
    txns = result.scalars().all()
    return {"items": [{"id": str(t.id), "payment_id": str(t.payment_id), "amount": str(t.amount), "currency": t.currency, "status": t.status, "fraud_risk": t.fraud_risk, "created_at": t.created_at.isoformat() if t.created_at else None} for t in txns], "page": page, "page_size": page_size}


@app.get("/api/v1/transactions/{payment_id}", tags=["Transactions"])
async def get_transaction(payment_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Transaction).where(Transaction.payment_id == payment_id))
    txn = result.scalar_one_or_none()
    if not txn:
        raise HTTPException(status_code=404, detail={"message": "Not found"})
    return {"id": str(txn.id), "payment_id": str(txn.payment_id), "amount": str(txn.amount), "currency": txn.currency, "status": txn.status, "payment_method": txn.payment_method, "fraud_risk": txn.fraud_risk, "net_amount": str(txn.net_amount) if txn.net_amount else None, "event_type": txn.event_type, "created_at": txn.created_at.isoformat() if txn.created_at else None}


@app.get("/health")
async def health():
    return {"status": "healthy", "service": settings.APP_NAME, "consumer_running": consumer._running}
