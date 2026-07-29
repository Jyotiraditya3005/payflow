import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum as PyEnum

from sqlalchemy import (
    Column, String, Numeric, DateTime, ForeignKey,
    Enum, Boolean, Text, Integer, Index, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.session import Base


class PaymentStatus(str, PyEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    REFUNDED = "REFUNDED"
    PARTIALLY_REFUNDED = "PARTIALLY_REFUNDED"


class PaymentMethod(str, PyEnum):
    CARD = "CARD"
    BANK_TRANSFER = "BANK_TRANSFER"
    WALLET = "WALLET"
    UPI = "UPI"
    NET_BANKING = "NET_BANKING"


class Currency(str, PyEnum):
    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"
    INR = "INR"
    JPY = "JPY"
    SGD = "SGD"


class FraudRisk(str, PyEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class Payment(Base):
    __tablename__ = "payments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    idempotency_key = Column(String(255), unique=True, nullable=False, index=True)

    # Parties
    merchant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    customer_id = Column(UUID(as_uuid=True), nullable=False, index=True)

    # Amount
    amount = Column(Numeric(precision=20, scale=4), nullable=False)
    currency = Column(Enum(Currency), nullable=False, default=Currency.USD)
    fee_amount = Column(Numeric(precision=20, scale=4), default=Decimal("0.0"))
    net_amount = Column(Numeric(precision=20, scale=4))

    # Status
    status = Column(Enum(PaymentStatus), nullable=False, default=PaymentStatus.PENDING, index=True)
    payment_method = Column(Enum(PaymentMethod), nullable=False)

    # Fraud
    fraud_risk = Column(Enum(FraudRisk), default=FraudRisk.LOW)
    fraud_score = Column(Numeric(precision=5, scale=4), default=Decimal("0.0"))
    fraud_flags = Column(JSONB, default=list)

    # Metadata
    description = Column(Text)
    metadata_ = Column("metadata", JSONB, default=dict)
    error_code = Column(String(100))
    error_message = Column(Text)

    # Retry
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    processed_at = Column(DateTime(timezone=True))
    expires_at = Column(DateTime(timezone=True))

    # Relations
    events = relationship("PaymentEvent", back_populates="payment", cascade="all, delete-orphan")
    refunds = relationship("Refund", back_populates="payment", cascade="all, delete-orphan")

    # Indexes for common query patterns
    __table_args__ = (
        Index("ix_payments_merchant_status", "merchant_id", "status"),
        Index("ix_payments_customer_status", "customer_id", "status"),
        Index("ix_payments_created_at_desc", "created_at"),
        Index("ix_payments_fraud_risk", "fraud_risk"),
    )

    def __repr__(self):
        return f"<Payment {self.id} | {self.amount} {self.currency} | {self.status}>"


class PaymentEvent(Base):
    """Immutable audit log for all payment state changes."""
    __tablename__ = "payment_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    payment_id = Column(UUID(as_uuid=True), ForeignKey("payments.id"), nullable=False, index=True)

    event_type = Column(String(100), nullable=False)
    from_status = Column(Enum(PaymentStatus))
    to_status = Column(Enum(PaymentStatus))
    actor = Column(String(255))  # service or user that triggered event
    payload = Column(JSONB, default=dict)
    error = Column(Text)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    payment = relationship("Payment", back_populates="events")


class Refund(Base):
    __tablename__ = "refunds"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    payment_id = Column(UUID(as_uuid=True), ForeignKey("payments.id"), nullable=False, index=True)
    idempotency_key = Column(String(255), unique=True, nullable=False)

    amount = Column(Numeric(precision=20, scale=4), nullable=False)
    currency = Column(Enum(Currency), nullable=False)
    reason = Column(Text)
    status = Column(String(50), default="PENDING")

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    processed_at = Column(DateTime(timezone=True))

    payment = relationship("Payment", back_populates="refunds")


class Merchant(Base):
    __tablename__ = "merchants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    api_key = Column(String(255), unique=True, nullable=False, index=True)
    webhook_url = Column(String(500))
    is_active = Column(Boolean, default=True)

    # Rate limits (per minute)
    rate_limit = Column(Integer, default=1000)

    # Settlement
    settlement_account = Column(String(255))
    fee_percentage = Column(Numeric(precision=5, scale=4), default=Decimal("0.025"))  # 2.5%

    metadata_ = Column("metadata", JSONB, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
