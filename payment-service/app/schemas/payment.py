from datetime import datetime
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.payment import Currency, FraudRisk, PaymentMethod, PaymentStatus


# ─── Request Schemas ──────────────────────────────────────────────────────────

class PaymentInitiateRequest(BaseModel):
    idempotency_key: str = Field(..., min_length=8, max_length=255, description="Client-generated unique key to prevent duplicates")
    merchant_id: UUID
    customer_id: UUID
    amount: Decimal = Field(..., gt=0, le=1_000_000)
    currency: Currency = Currency.USD
    payment_method: PaymentMethod
    description: Optional[str] = Field(None, max_length=500)
    metadata: Optional[dict[str, Any]] = Field(default_factory=dict)

    # Card details (would be tokenized in real system)
    card_token: Optional[str] = None
    bank_account_token: Optional[str] = None

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v):
        if v < Decimal("0.01"):
            raise ValueError("Amount must be at least 0.01")
        return round(v, 4)

    @model_validator(mode="after")
    def validate_payment_method_tokens(self):
        if self.payment_method == PaymentMethod.CARD and not self.card_token:
            raise ValueError("card_token required for CARD payment method")
        if self.payment_method == PaymentMethod.BANK_TRANSFER and not self.bank_account_token:
            raise ValueError("bank_account_token required for BANK_TRANSFER")
        return self


class RefundRequest(BaseModel):
    idempotency_key: str = Field(..., min_length=8, max_length=255)
    amount: Optional[Decimal] = Field(None, gt=0, description="Partial refund amount. Full refund if not specified.")
    reason: Optional[str] = Field(None, max_length=500)


class PaymentListParams(BaseModel):
    merchant_id: Optional[UUID] = None
    customer_id: Optional[UUID] = None
    status: Optional[PaymentStatus] = None
    fraud_risk: Optional[FraudRisk] = None
    currency: Optional[Currency] = None
    from_date: Optional[datetime] = None
    to_date: Optional[datetime] = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


# ─── Response Schemas ─────────────────────────────────────────────────────────

class PaymentEventResponse(BaseModel):
    id: UUID
    event_type: str
    from_status: Optional[PaymentStatus]
    to_status: Optional[PaymentStatus]
    actor: Optional[str]
    payload: dict
    created_at: datetime

    model_config = {"from_attributes": True}


class RefundResponse(BaseModel):
    id: UUID
    payment_id: UUID
    amount: Decimal
    currency: Currency
    reason: Optional[str]
    status: str
    created_at: datetime
    processed_at: Optional[datetime]

    model_config = {"from_attributes": True}


class PaymentResponse(BaseModel):
    id: UUID
    idempotency_key: str
    merchant_id: UUID
    customer_id: UUID
    amount: Decimal
    currency: Currency
    fee_amount: Decimal
    net_amount: Optional[Decimal]
    status: PaymentStatus
    payment_method: PaymentMethod
    fraud_risk: Optional[FraudRisk]
    fraud_score: Optional[Decimal]
    fraud_flags: Optional[list]
    description: Optional[str]
    metadata: Optional[dict] = Field(alias="metadata_")
    error_code: Optional[str]
    error_message: Optional[str]
    retry_count: int
    created_at: datetime
    updated_at: datetime
    processed_at: Optional[datetime]
    events: Optional[list[PaymentEventResponse]] = None
    refunds: Optional[list[RefundResponse]] = None

    model_config = {"from_attributes": True, "populate_by_name": True}


class PaymentListResponse(BaseModel):
    items: list[PaymentResponse]
    total: int
    page: int
    page_size: int
    pages: int


class PaymentSummaryResponse(BaseModel):
    total_payments: int
    total_volume: Decimal
    success_rate: float
    fraud_rate: float
    avg_processing_time_ms: float
    payments_by_status: dict[str, int]
    payments_by_currency: dict[str, Decimal]
    payments_by_method: dict[str, int]


# ─── Internal Schemas (service-to-service) ────────────────────────────────────

class FraudCheckRequest(BaseModel):
    payment_id: UUID
    merchant_id: UUID
    customer_id: UUID
    amount: Decimal
    currency: Currency
    payment_method: PaymentMethod
    ip_address: Optional[str] = None
    device_fingerprint: Optional[str] = None
    metadata: dict = {}


class FraudCheckResponse(BaseModel):
    payment_id: UUID
    risk_level: FraudRisk
    risk_score: float = Field(..., ge=0.0, le=1.0)
    flags: list[str] = []
    recommendation: str  # "APPROVE", "REVIEW", "DECLINE"
    details: dict = {}


class KafkaPaymentEvent(BaseModel):
    event_type: str
    payment_id: str
    merchant_id: str
    customer_id: str
    amount: float
    currency: str
    status: str
    timestamp: str
    metadata: dict = {}
