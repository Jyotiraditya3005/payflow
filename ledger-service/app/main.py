"""
Ledger Service — double-entry bookkeeping via Kafka consumer.
Every payment.completed event creates 3 ledger entries that net to 0.
"""
import asyncio, json
from contextlib import asynccontextmanager
from decimal import Decimal
from typing import Optional
from uuid import uuid4
import structlog
from aiokafka import AIOKafkaConsumer
from fastapi import FastAPI, Depends
from sqlalchemy import Column, String, Numeric, DateTime, CheckConstraint, and_
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func
from sqlalchemy import select
from app.core.config import settings
from app.db.session import Base, get_db, create_tables

structlog.configure(processors=[structlog.contextvars.merge_contextvars, structlog.processors.add_log_level, structlog.processors.TimeStamper(fmt="iso"), structlog.processors.JSONRenderer()], wrapper_class=structlog.BoundLogger, logger_factory=structlog.PrintLoggerFactory())
logger = structlog.get_logger()

class LedgerEntry(Base):
    __tablename__ = "ledger_entries_svc"
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    payment_id = Column(PGUUID(as_uuid=True), nullable=False, index=True)
    entry_type = Column(String(10), nullable=False)
    account_type = Column(String(60), nullable=False)
    account_id = Column(PGUUID(as_uuid=True), nullable=False, index=True)
    amount = Column(Numeric(20, 4), nullable=False)
    currency = Column(String(10), nullable=False)
    description = Column(String(500))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    __table_args__ = (CheckConstraint("entry_type IN ('DEBIT','CREDIT')", name="chk_entry_type"), CheckConstraint("amount > 0", name="chk_positive_amount"))

class LedgerConsumer:
    def __init__(self): self._consumer = None; self._running = False
    async def start(self):
        self._consumer = AIOKafkaConsumer(settings.KAFKA_TOPIC_PAYMENT_COMPLETED, bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS, group_id=settings.KAFKA_CONSUMER_GROUP, value_deserializer=lambda v: json.loads(v.decode("utf-8")), auto_offset_reset="earliest", enable_auto_commit=False)
        await self._consumer.start(); self._running = True; logger.info("Ledger consumer started")
    async def stop(self): self._running = False; self._consumer and await self._consumer.stop()
    async def consume(self):
        from app.db.session import AsyncSessionLocal
        async for msg in self._consumer:
            if not self._running: break
            try:
                envelope = msg.value; event_type = envelope.get("event_type",""); payload = envelope.get("payload",{})
                if event_type != "payment.completed": await self._consumer.commit(); continue
                payment_id = payload.get("payment_id"); merchant_id = payload.get("merchant_id"); customer_id = payload.get("customer_id")
                amount = Decimal(str(payload.get("amount","0"))); net_amount = Decimal(str(payload.get("net_amount", str(amount)))); fee = amount - net_amount; currency = payload.get("currency","USD")
                if not payment_id or amount <= 0: await self._consumer.commit(); continue
                async with AsyncSessionLocal() as session:
                    if (await session.execute(select(LedgerEntry).where(LedgerEntry.payment_id == payment_id).limit(1))).scalar_one_or_none():
                        await self._consumer.commit(); continue
                    entries = [LedgerEntry(payment_id=payment_id, entry_type="DEBIT",  account_type="CUSTOMER_PAYABLE",    account_id=customer_id, amount=amount,     currency=currency, description=f"Payment {payment_id} customer charge"),
                               LedgerEntry(payment_id=payment_id, entry_type="CREDIT", account_type="MERCHANT_RECEIVABLE", account_id=merchant_id, amount=net_amount, currency=currency, description=f"Payment {payment_id} merchant settlement")]
                    if fee > Decimal("0.0001"):
                        entries.append(LedgerEntry(payment_id=payment_id, entry_type="CREDIT", account_type="PLATFORM_FEE_REVENUE", account_id=uuid4(), amount=fee, currency=currency, description=f"Payment {payment_id} platform fee"))
                    session.add_all(entries); await session.commit()
                    logger.info("Ledger entries recorded", payment_id=payment_id, entries=len(entries))
                await self._consumer.commit()
            except Exception as e: logger.error("Ledger error", error=str(e)); await asyncio.sleep(1)

consumer = LedgerConsumer()

@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_tables(); await consumer.start(); task = asyncio.create_task(consumer.consume()); yield; task.cancel(); await consumer.stop()

app = FastAPI(title=settings.APP_NAME, version=settings.APP_VERSION, lifespan=lifespan)

@app.get("/api/v1/ledger/{payment_id}", tags=["Ledger"])
async def get_ledger(payment_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(LedgerEntry).where(LedgerEntry.payment_id == payment_id).order_by(LedgerEntry.created_at))
    entries = result.scalars().all()
    debits = sum(e.amount for e in entries if e.entry_type == "DEBIT")
    credits = sum(e.amount for e in entries if e.entry_type == "CREDIT")
    return {"payment_id": payment_id, "entries": [{"id": str(e.id), "type": e.entry_type, "account": e.account_type, "amount": str(e.amount), "currency": e.currency} for e in entries], "reconciliation": {"debits": str(debits), "credits": str(credits), "balanced": abs(debits - credits) < Decimal("0.001")}}

@app.get("/api/v1/ledger/account/{account_id}", tags=["Ledger"])
async def get_balance(account_id: str, currency: str = "USD", db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(LedgerEntry).where(and_(LedgerEntry.account_id == account_id, LedgerEntry.currency == currency)))
    entries = result.scalars().all()
    credits = sum(e.amount for e in entries if e.entry_type == "CREDIT")
    debits  = sum(e.amount for e in entries if e.entry_type == "DEBIT")
    return {"account_id": account_id, "currency": currency, "net_balance": str(credits - debits), "total_credits": str(credits), "total_debits": str(debits), "entry_count": len(entries)}

@app.get("/health")
async def health(): return {"status": "healthy", "service": settings.APP_NAME, "consumer_running": consumer._running}
