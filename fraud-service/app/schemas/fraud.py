from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class FraudFlag(BaseModel):
    flag_type: str
    severity: str
    description: str
    contribution: float = Field(..., ge=0.0, le=1.0)


class FraudCheckRequest(BaseModel):
    payment_id: UUID
    merchant_id: UUID
    customer_id: UUID
    amount: Decimal
    currency: Any  # Currency enum from payment service
    payment_method: Any  # PaymentMethod enum
    ip_address: Optional[str] = None
    device_fingerprint: Optional[str] = None
    metadata: dict = {}


class FraudCheckResponse(BaseModel):
    payment_id: UUID
    risk_level: RiskLevel
    risk_score: float = Field(..., ge=0.0, le=1.0)
    flags: list[str] = []
    recommendation: str  # APPROVE | REVIEW | DECLINE
    details: dict = {}


class FraudCaseResponse(BaseModel):
    id: UUID
    payment_id: UUID
    customer_id: UUID
    amount: Decimal
    risk_score: float
    risk_level: RiskLevel
    flags: list[str]
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class CustomerRiskProfileResponse(BaseModel):
    customer_id: UUID
    avg_risk_score: float
    total_transactions: int
    fraud_count: int
    last_transaction_at: Optional[datetime]
    risk_level: RiskLevel

    model_config = {"from_attributes": True}


class FraudStatsResponse(BaseModel):
    total_checks: int
    approved: int
    reviewed: int
    declined: int
    avg_risk_score: float
    fraud_rate: float
    top_flags: list[dict]
