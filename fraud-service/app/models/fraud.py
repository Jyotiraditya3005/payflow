import uuid
from datetime import datetime

from sqlalchemy import Column, String, Numeric, DateTime, Integer, Float, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.sql import func

from app.db.session import Base


class FraudCase(Base):
    __tablename__ = "fraud_cases"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    payment_id = Column(UUID(as_uuid=True), nullable=False, index=True, unique=True)
    customer_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    merchant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    amount = Column(Numeric(precision=20, scale=4), nullable=False)
    risk_score = Column(Float, nullable=False)
    risk_level = Column(String(20), nullable=False, index=True)
    flags = Column(JSONB, default=list)
    ip_address = Column(String(50))
    device_fingerprint = Column(String(255))
    status = Column(String(50), default="OPEN")  # OPEN, REVIEWED, CLOSED
    reviewer_notes = Column(String(1000))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    reviewed_at = Column(DateTime(timezone=True))


class FraudRule(Base):
    __tablename__ = "fraud_rules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), unique=True, nullable=False)
    description = Column(String(1000))
    rule_type = Column(String(50))  # VELOCITY, AMOUNT, GEO, BLACKLIST, etc.
    is_active = Column(Boolean, default=True)
    weight = Column(Float, default=0.5)
    config = Column(JSONB, default=dict)  # Rule-specific configuration
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class CustomerRiskProfile(Base):
    __tablename__ = "customer_risk_profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id = Column(UUID(as_uuid=True), nullable=False, unique=True, index=True)
    avg_risk_score = Column(Float, default=0.0)
    total_transactions = Column(Integer, default=0)
    fraud_count = Column(Integer, default=0)
    last_transaction_at = Column(DateTime(timezone=True))
    is_flagged = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
