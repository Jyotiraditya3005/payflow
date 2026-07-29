from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Header, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.payment import (
    PaymentInitiateRequest,
    PaymentListParams,
    PaymentListResponse,
    PaymentResponse,
    PaymentSummaryResponse,
    RefundRequest,
    RefundResponse,
)
from app.services.payment_service import PaymentProcessingError, payment_service
from app.core.config import settings

import structlog

logger = structlog.get_logger()

router = APIRouter(prefix="/payments", tags=["Payments"])


def get_client_ip(request: Request) -> Optional[str]:
    forwarded = request.headers.get("X-Forwarded-For")
    return forwarded.split(",")[0].strip() if forwarded else request.client.host


@router.post(
    "/",
    response_model=PaymentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Initiate a payment",
    description="""
    Create and process a new payment.

    **Idempotency**: Include an `Idempotency-Key` header or set `idempotency_key` in the body.
    Repeated requests with the same key return the original response without reprocessing.

    **Fraud Detection**: Every payment is scored by the fraud engine. HIGH/CRITICAL risk payments
    are automatically declined.

    **Rate Limiting**: Merchants are limited to 1000 requests/minute by default.
    """,
)
async def initiate_payment(
    request: Request,
    payload: PaymentInitiateRequest,
    db: AsyncSession = Depends(get_db),
    x_device_fingerprint: Optional[str] = Header(None),
):
    try:
        return await payment_service.initiate_payment(
            request=payload,
            db=db,
            ip_address=get_client_ip(request),
            device_fingerprint=x_device_fingerprint,
        )
    except PaymentProcessingError as e:
        logger.warning("Payment processing error", error=e.message, code=e.error_code)
        status_map = {
            "RATE_LIMIT_EXCEEDED": status.HTTP_429_TOO_MANY_REQUESTS,
            "INVALID_MERCHANT": status.HTTP_422_UNPROCESSABLE_ENTITY,
            "NOT_FOUND": status.HTTP_404_NOT_FOUND,
            "CONCURRENT_REQUEST": status.HTTP_409_CONFLICT,
        }
        http_status = status_map.get(e.error_code, status.HTTP_400_BAD_REQUEST)
        raise HTTPException(
            status_code=http_status,
            detail={"error_code": e.error_code, "message": e.message},
        )
    except Exception as e:
        logger.error("Unexpected error in payment initiation", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "INTERNAL_ERROR", "message": "An unexpected error occurred"},
        )


@router.get(
    "/{payment_id}",
    response_model=PaymentResponse,
    summary="Get payment details",
)
async def get_payment(
    payment_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    payment = await payment_service.get_payment(payment_id, db)
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "NOT_FOUND", "message": f"Payment {payment_id} not found"},
        )
    return payment


@router.get(
    "/",
    response_model=PaymentListResponse,
    summary="List payments with filtering",
)
async def list_payments(
    merchant_id: Optional[UUID] = None,
    customer_id: Optional[UUID] = None,
    status_filter: Optional[str] = None,
    fraud_risk: Optional[str] = None,
    currency: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
):
    params = PaymentListParams(
        merchant_id=merchant_id,
        customer_id=customer_id,
        status=status_filter,
        fraud_risk=fraud_risk,
        currency=currency,
        page=page,
        page_size=page_size,
    )
    return await payment_service.list_payments(params, db)


@router.post(
    "/{payment_id}/refund",
    response_model=PaymentResponse,
    summary="Initiate a refund",
    description="Refund a completed payment. Supports partial refunds.",
)
async def refund_payment(
    payment_id: UUID,
    request: RefundRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        return await payment_service.initiate_refund(payment_id, request, db)
    except PaymentProcessingError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": e.error_code, "message": e.message},
        )


@router.get(
    "/summary/stats",
    response_model=PaymentSummaryResponse,
    summary="Get payment analytics summary",
)
async def get_summary(
    merchant_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db),
):
    return await payment_service.get_summary(merchant_id, db)


@router.post(
    "/{payment_id}/cancel",
    response_model=PaymentResponse,
    summary="Cancel a pending payment",
)
async def cancel_payment(
    payment_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select
    from app.models.payment import Payment, PaymentEvent, PaymentStatus
    from datetime import datetime, timezone

    result = await db.execute(
        select(Payment).where(Payment.id == payment_id)
    )
    payment = result.scalar_one_or_none()

    if not payment:
        raise HTTPException(status_code=404, detail={"error_code": "NOT_FOUND", "message": "Payment not found"})

    if payment.status != PaymentStatus.PENDING:
        raise HTTPException(
            status_code=400,
            detail={
                "error_code": "INVALID_STATUS",
                "message": f"Cannot cancel payment in {payment.status} status. Only PENDING payments can be cancelled."
            }
        )

    payment.status = PaymentStatus.CANCELLED
    db.add(PaymentEvent(
        payment_id=payment_id,
        event_type="payment.cancelled",
        from_status=PaymentStatus.PENDING,
        to_status=PaymentStatus.CANCELLED,
        actor="merchant",
    ))
    await db.commit()

    return PaymentResponse.model_validate(payment)
