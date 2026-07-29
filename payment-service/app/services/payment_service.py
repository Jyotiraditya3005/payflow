import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID, uuid4

import httpx
import structlog
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.core.config import settings
from app.models.payment import (
    Payment, PaymentEvent, Refund, Merchant,
    PaymentStatus, FraudRisk
)
from app.schemas.payment import (
    PaymentInitiateRequest, PaymentResponse, RefundRequest,
    FraudCheckRequest, FraudCheckResponse, PaymentListParams,
    PaymentListResponse, PaymentSummaryResponse
)
from app.services.kafka_service import kafka_producer
from app.services.redis_service import redis_service, LockAcquisitionError

logger = structlog.get_logger()


class PaymentProcessingError(Exception):
    def __init__(self, message: str, error_code: str):
        self.message = message
        self.error_code = error_code
        super().__init__(message)


class PaymentService:

    # ─── Payment Initiation ───────────────────────────────────────────────────

    async def initiate_payment(
        self,
        request: PaymentInitiateRequest,
        db: AsyncSession,
        ip_address: Optional[str] = None,
        device_fingerprint: Optional[str] = None,
    ) -> PaymentResponse:

        log = logger.bind(
            idempotency_key=request.idempotency_key,
            merchant_id=str(request.merchant_id),
            amount=str(request.amount),
        )

        # 1. Idempotency check — return cached response if key was already used
        cached = await redis_service.check_idempotency(request.idempotency_key)
        if cached:
            log.info("Returning cached idempotent response")
            return PaymentResponse(**cached)

        # 2. Rate limiting per merchant
        allowed, count, retry_after = await redis_service.check_rate_limit(
            identifier=f"merchant:{request.merchant_id}",
            limit=settings.RATE_LIMIT_MERCHANT_PER_MINUTE,
        )
        if not allowed:
            raise PaymentProcessingError(
                f"Rate limit exceeded. Retry after {retry_after}s",
                "RATE_LIMIT_EXCEEDED"
            )

        # 3. Distributed lock to prevent race conditions on same idempotency key
        try:
            async with redis_service.distributed_lock(
                f"payment:{request.idempotency_key}", ttl=30
            ):
                return await self._process_payment_locked(
                    request, db, ip_address, device_fingerprint, log
                )
        except LockAcquisitionError:
            # Another request is processing same key — check DB
            existing = await self._get_by_idempotency_key(request.idempotency_key, db)
            if existing:
                return PaymentResponse.model_validate(existing)
            raise PaymentProcessingError("Concurrent request in progress", "CONCURRENT_REQUEST")

    async def _process_payment_locked(
        self,
        request: PaymentInitiateRequest,
        db: AsyncSession,
        ip_address: Optional[str],
        device_fingerprint: Optional[str],
        log,
    ) -> PaymentResponse:

        # 4. Validate merchant
        merchant = await self._get_merchant(str(request.merchant_id), db)
        if not merchant or not merchant.is_active:
            raise PaymentProcessingError("Merchant not found or inactive", "INVALID_MERCHANT")

        # 5. Calculate fees
        fee_amount = round(request.amount * merchant.fee_percentage, 4)
        net_amount = request.amount - fee_amount

        # 6. Create payment record in PENDING state
        payment = Payment(
            id=uuid4(),
            idempotency_key=request.idempotency_key,
            merchant_id=request.merchant_id,
            customer_id=request.customer_id,
            amount=request.amount,
            currency=request.currency,
            payment_method=request.payment_method,
            fee_amount=fee_amount,
            net_amount=net_amount,
            description=request.description,
            metadata_=request.metadata,
            status=PaymentStatus.PENDING,
        )
        db.add(payment)

        # Log creation event
        db.add(PaymentEvent(
            payment_id=payment.id,
            event_type="payment.created",
            to_status=PaymentStatus.PENDING,
            actor="payment-service",
            payload={"amount": str(request.amount), "currency": request.currency},
        ))

        await db.flush()  # Get ID without committing
        log = log.bind(payment_id=str(payment.id))
        log.info("Payment record created")

        # 7. Fraud check (async call to fraud service)
        fraud_result = await self._request_fraud_check(
            payment, ip_address, device_fingerprint
        )

        payment.fraud_score = Decimal(str(fraud_result.risk_score))
        payment.fraud_risk = fraud_result.risk_level
        payment.fraud_flags = fraud_result.flags

        if fraud_result.recommendation == "DECLINE":
            payment.status = PaymentStatus.FAILED
            payment.error_code = "FRAUD_DECLINED"
            payment.error_message = f"Payment declined due to fraud risk: {fraud_result.risk_level}"
            db.add(PaymentEvent(
                payment_id=payment.id,
                event_type="payment.fraud_declined",
                from_status=PaymentStatus.PENDING,
                to_status=PaymentStatus.FAILED,
                actor="fraud-service",
                payload={"risk_level": fraud_result.risk_level, "flags": fraud_result.flags},
            ))
            await db.commit()
            log.warning("Payment declined by fraud service", risk_level=fraud_result.risk_level)

            # Publish fraud alert
            await kafka_producer.payment_failed({
                "payment_id": str(payment.id),
                "reason": "FRAUD_DECLINED",
                "risk_level": fraud_result.risk_level,
            })

            response = PaymentResponse.model_validate(payment)
            await redis_service.set_idempotency(request.idempotency_key, response.model_dump())
            return response

        # 8. Process payment (simulate actual payment processor)
        payment.status = PaymentStatus.PROCESSING
        db.add(PaymentEvent(
            payment_id=payment.id,
            event_type="payment.processing",
            from_status=PaymentStatus.PENDING,
            to_status=PaymentStatus.PROCESSING,
            actor="payment-service",
        ))

        try:
            await self._execute_payment(payment)

            payment.status = PaymentStatus.COMPLETED
            payment.processed_at = datetime.now(timezone.utc)
            db.add(PaymentEvent(
                payment_id=payment.id,
                event_type="payment.completed",
                from_status=PaymentStatus.PROCESSING,
                to_status=PaymentStatus.COMPLETED,
                actor="payment-processor",
            ))

            await db.commit()
            log.info("Payment completed successfully")

            # Publish success event
            await kafka_producer.payment_completed({
                "payment_id": str(payment.id),
                "merchant_id": str(payment.merchant_id),
                "customer_id": str(payment.customer_id),
                "amount": str(payment.amount),
                "currency": payment.currency,
                "net_amount": str(payment.net_amount),
            })

        except PaymentProcessingError as e:
            payment.status = PaymentStatus.FAILED
            payment.error_code = e.error_code
            payment.error_message = e.message
            db.add(PaymentEvent(
                payment_id=payment.id,
                event_type="payment.failed",
                from_status=PaymentStatus.PROCESSING,
                to_status=PaymentStatus.FAILED,
                actor="payment-processor",
                error=e.message,
            ))
            await db.commit()
            log.error("Payment processing failed", error=e.message, code=e.error_code)

            # Schedule retry if eligible
            if payment.retry_count < payment.max_retries:
                await kafka_producer.publish(
                    topic=settings.KAFKA_RETRY_TOPIC,
                    event_type="payment.retry_scheduled",
                    payload={"payment_id": str(payment.id), "attempt": payment.retry_count + 1},
                )

            await kafka_producer.payment_failed({
                "payment_id": str(payment.id),
                "error_code": e.error_code,
                "merchant_id": str(payment.merchant_id),
            })

        # 9. Cache response for idempotency
        response = PaymentResponse.model_validate(payment)
        await redis_service.set_idempotency(request.idempotency_key, response.model_dump())

        return response

    async def _execute_payment(self, payment: Payment):
        """
        Simulate payment execution. In production: integrate with
        Stripe, Razorpay, payment network gateway, etc.
        """
        await asyncio.sleep(0.1)  # Simulate network call

        # Simulate occasional processing failure (5% failure rate for demo)
        import random
        if random.random() < 0.05:
            raise PaymentProcessingError("Payment processor timeout", "PROCESSOR_TIMEOUT")

    # ─── Fraud Check ──────────────────────────────────────────────────────────

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=3),
        retry=retry_if_exception_type(httpx.TimeoutException),
        reraise=False,
    )
    async def _request_fraud_check(
        self,
        payment: Payment,
        ip_address: Optional[str],
        device_fingerprint: Optional[str],
    ) -> FraudCheckResponse:
        """Call fraud service. Falls back to LOW risk on timeout."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(
                    f"{settings.FRAUD_SERVICE_URL}/api/v1/fraud/check",
                    json=FraudCheckRequest(
                        payment_id=payment.id,
                        merchant_id=payment.merchant_id,
                        customer_id=payment.customer_id,
                        amount=payment.amount,
                        currency=payment.currency,
                        payment_method=payment.payment_method,
                        ip_address=ip_address,
                        device_fingerprint=device_fingerprint,
                    ).model_dump(mode="json"),
                    headers={"X-Internal-Service": "payment-service"},
                )
                resp.raise_for_status()
                return FraudCheckResponse(**resp.json())
        except Exception as e:
            logger.warning("Fraud service unavailable, using default LOW risk", error=str(e))
            # Fail open — process payment with low risk if fraud service is down
            return FraudCheckResponse(
                payment_id=payment.id,
                risk_level=FraudRisk.LOW,
                risk_score=0.0,
                flags=[],
                recommendation="APPROVE",
                details={"fallback": True},
            )

    # ─── Refunds ──────────────────────────────────────────────────────────────

    async def initiate_refund(
        self,
        payment_id: UUID,
        request: RefundRequest,
        db: AsyncSession,
    ) -> PaymentResponse:

        payment = await self._get_payment_with_lock(payment_id, db)

        if payment.status not in (PaymentStatus.COMPLETED, PaymentStatus.PARTIALLY_REFUNDED):
            raise PaymentProcessingError(
                f"Cannot refund payment in {payment.status} status",
                "INVALID_STATUS_FOR_REFUND"
            )

        refund_amount = request.amount or payment.amount

        # Check if refund amount is valid
        already_refunded = sum(
            r.amount for r in payment.refunds if r.status == "COMPLETED"
        )
        refundable = payment.amount - already_refunded
        if refund_amount > refundable:
            raise PaymentProcessingError(
                f"Refund amount {refund_amount} exceeds refundable amount {refundable}",
                "REFUND_AMOUNT_EXCEEDED"
            )

        refund = Refund(
            id=uuid4(),
            payment_id=payment_id,
            idempotency_key=request.idempotency_key,
            amount=refund_amount,
            currency=payment.currency,
            reason=request.reason,
            status="COMPLETED",
            processed_at=datetime.now(timezone.utc),
        )
        db.add(refund)

        # Update payment status
        total_refunded = already_refunded + refund_amount
        if total_refunded >= payment.amount:
            payment.status = PaymentStatus.REFUNDED
        else:
            payment.status = PaymentStatus.PARTIALLY_REFUNDED

        db.add(PaymentEvent(
            payment_id=payment_id,
            event_type="payment.refunded",
            from_status=PaymentStatus.COMPLETED,
            to_status=payment.status,
            actor="payment-service",
            payload={"refund_amount": str(refund_amount)},
        ))

        await db.commit()

        await kafka_producer.publish(
            topic=settings.KAFKA_TOPIC_PAYMENT_COMPLETED,
            event_type="payment.refunded",
            payload={
                "payment_id": str(payment_id),
                "refund_amount": str(refund_amount),
                "merchant_id": str(payment.merchant_id),
            },
        )

        return PaymentResponse.model_validate(payment)

    # ─── Queries ──────────────────────────────────────────────────────────────

    async def get_payment(self, payment_id: UUID, db: AsyncSession) -> Optional[PaymentResponse]:
        result = await db.execute(
            select(Payment)
            .where(Payment.id == payment_id)
            .options(selectinload(Payment.events), selectinload(Payment.refunds))
        )
        payment = result.scalar_one_or_none()
        if not payment:
            return None
        return PaymentResponse.model_validate(payment)

    async def list_payments(
        self, params: PaymentListParams, db: AsyncSession
    ) -> PaymentListResponse:

        query = select(Payment)
        filters = []

        if params.merchant_id:
            filters.append(Payment.merchant_id == params.merchant_id)
        if params.customer_id:
            filters.append(Payment.customer_id == params.customer_id)
        if params.status:
            filters.append(Payment.status == params.status)
        if params.fraud_risk:
            filters.append(Payment.fraud_risk == params.fraud_risk)
        if params.currency:
            filters.append(Payment.currency == params.currency)
        if params.from_date:
            filters.append(Payment.created_at >= params.from_date)
        if params.to_date:
            filters.append(Payment.created_at <= params.to_date)

        if filters:
            query = query.where(and_(*filters))

        count_result = await db.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar()

        offset = (params.page - 1) * params.page_size
        result = await db.execute(
            query.order_by(Payment.created_at.desc())
            .offset(offset)
            .limit(params.page_size)
        )
        payments = result.scalars().all()

        return PaymentListResponse(
            items=[PaymentResponse.model_validate(p) for p in payments],
            total=total,
            page=params.page,
            page_size=params.page_size,
            pages=(total + params.page_size - 1) // params.page_size,
        )

    async def get_summary(self, merchant_id: Optional[UUID], db: AsyncSession) -> PaymentSummaryResponse:
        query = select(Payment)
        if merchant_id:
            query = query.where(Payment.merchant_id == merchant_id)

        result = await db.execute(query)
        payments = result.scalars().all()

        total = len(payments)
        completed = [p for p in payments if p.status == PaymentStatus.COMPLETED]
        fraud_payments = [p for p in payments if p.fraud_risk in (FraudRisk.HIGH, FraudRisk.CRITICAL)]

        by_status = {}
        for p in payments:
            by_status[p.status.value] = by_status.get(p.status.value, 0) + 1

        by_currency = {}
        for p in completed:
            key = p.currency.value
            by_currency[key] = by_currency.get(key, Decimal("0")) + p.amount

        by_method = {}
        for p in payments:
            key = p.payment_method.value
            by_method[key] = by_method.get(key, 0) + 1

        return PaymentSummaryResponse(
            total_payments=total,
            total_volume=sum(p.amount for p in completed),
            success_rate=len(completed) / total if total > 0 else 0.0,
            fraud_rate=len(fraud_payments) / total if total > 0 else 0.0,
            avg_processing_time_ms=50.0,
            payments_by_status=by_status,
            payments_by_currency={k: v for k, v in by_currency.items()},
            payments_by_method=by_method,
        )

    # ─── Helpers ──────────────────────────────────────────────────────────────

    async def _get_payment_with_lock(self, payment_id: UUID, db: AsyncSession) -> Payment:
        result = await db.execute(
            select(Payment)
            .where(Payment.id == payment_id)
            .with_for_update()  # Pessimistic lock for concurrent updates
            .options(selectinload(Payment.refunds))
        )
        payment = result.scalar_one_or_none()
        if not payment:
            raise PaymentProcessingError(f"Payment {payment_id} not found", "NOT_FOUND")
        return payment

    async def _get_by_idempotency_key(self, key: str, db: AsyncSession) -> Optional[Payment]:
        result = await db.execute(
            select(Payment).where(Payment.idempotency_key == key)
        )
        return result.scalar_one_or_none()

    async def _get_merchant(self, merchant_id: str, db: AsyncSession) -> Optional[Merchant]:
        # Try cache first
        cached = await redis_service.get_merchant(merchant_id)
        if cached:
            return type("Merchant", (), cached)()

        result = await db.execute(
            select(Merchant).where(Merchant.id == merchant_id)
        )
        merchant = result.scalar_one_or_none()
        if merchant:
            await redis_service.cache_merchant(merchant_id, {
                "is_active": merchant.is_active,
                "fee_percentage": float(merchant.fee_percentage),
                "rate_limit": merchant.rate_limit,
            })
        return merchant


payment_service = PaymentService()
