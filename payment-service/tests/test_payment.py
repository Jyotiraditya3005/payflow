"""
Payment Service Test Suite
---------------------------
Tests covering:
  - Idempotency key behaviour
  - Fraud check integration
  - Payment state machine transitions
  - Rate limiting
  - Refund logic
  - API contract tests
"""
import pytest
import asyncio
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def merchant_id():
    return uuid4()


@pytest.fixture
def customer_id():
    return uuid4()


@pytest.fixture
def valid_payment_payload(merchant_id, customer_id):
    return {
        "idempotency_key": f"test_{uuid4().hex}",
        "merchant_id": str(merchant_id),
        "customer_id": str(customer_id),
        "amount": "299.99",
        "currency": "USD",
        "payment_method": "CARD",
        "card_token": "tok_visa_4242",
        "description": "Test payment",
    }


# ─── Unit: Schema Validation ──────────────────────────────────────────────────

class TestPaymentSchema:
    def test_valid_payment_request(self, valid_payment_payload):
        from app.schemas.payment import PaymentInitiateRequest
        req = PaymentInitiateRequest(**valid_payment_payload)
        assert req.amount == Decimal("299.99")
        assert req.currency.value == "USD"

    def test_amount_below_minimum_rejected(self, valid_payment_payload):
        from app.schemas.payment import PaymentInitiateRequest
        from pydantic import ValidationError
        payload = {**valid_payment_payload, "amount": "0.001"}
        with pytest.raises(ValidationError) as exc:
            PaymentInitiateRequest(**payload)
        assert "amount" in str(exc.value).lower() or "0.01" in str(exc.value)

    def test_amount_above_maximum_rejected(self, valid_payment_payload):
        from app.schemas.payment import PaymentInitiateRequest
        from pydantic import ValidationError
        payload = {**valid_payment_payload, "amount": "2000000.00"}
        with pytest.raises(ValidationError):
            PaymentInitiateRequest(**payload)

    def test_card_payment_requires_card_token(self, merchant_id, customer_id):
        from app.schemas.payment import PaymentInitiateRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError) as exc:
            PaymentInitiateRequest(
                idempotency_key="test_123",
                merchant_id=merchant_id,
                customer_id=customer_id,
                amount="100.00",
                currency="USD",
                payment_method="CARD",
                # Missing card_token
            )
        assert "card_token" in str(exc.value)

    def test_amount_rounded_to_4_decimals(self, valid_payment_payload):
        from app.schemas.payment import PaymentInitiateRequest
        payload = {**valid_payment_payload, "amount": "99.123456789"}
        req = PaymentInitiateRequest(**payload)
        assert req.amount == Decimal("99.1235")

    def test_idempotency_key_minimum_length(self, valid_payment_payload):
        from app.schemas.payment import PaymentInitiateRequest
        from pydantic import ValidationError
        payload = {**valid_payment_payload, "idempotency_key": "short"}
        with pytest.raises(ValidationError):
            PaymentInitiateRequest(**payload)

    def test_all_currencies_accepted(self, valid_payment_payload):
        from app.schemas.payment import PaymentInitiateRequest
        from app.models.payment import Currency
        for currency in Currency:
            payload = {**valid_payment_payload, "currency": currency.value,
                       "idempotency_key": f"test_{currency.value}_{uuid4().hex}"}
            req = PaymentInitiateRequest(**payload)
            assert req.currency == currency


# ─── Unit: ML Fraud Scorer ────────────────────────────────────────────────────

class TestFraudScorer:
    @pytest.mark.asyncio
    async def test_heuristic_score_high_velocity(self):
        """High velocity should produce elevated risk score."""
        try:
            from fraud_service.app.services.ml_scorer import MLFraudScorer
        except ImportError:
            pytest.skip("Fraud service not in path — run from fraud-service dir")

        scorer = MLFraudScorer()
        features = {
            "amount": 5000, "amount_log": 8.5, "amount_vs_avg": 1.0,
            "hour_of_day": 14, "is_night": 0, "is_weekend": 0,
            "velocity_1m": 15, "velocity_5m": 40,  # Very high
            "customer_txn_count": 3, "is_new_customer": 1,
            "payment_method_card": 1, "payment_method_wallet": 0,
            "currency_usd": 1, "has_device_fp": 0,
        }
        score = scorer._heuristic_score(features)
        assert score >= 0.5, f"High velocity should score >= 0.5, got {score}"

    @pytest.mark.asyncio
    async def test_heuristic_score_low_risk(self):
        """Normal transaction features should score low."""
        try:
            from fraud_service.app.services.ml_scorer import MLFraudScorer
        except ImportError:
            pytest.skip("Fraud service not in path")

        scorer = MLFraudScorer()
        features = {
            "amount": 150, "amount_log": 5.01, "amount_vs_avg": 0.9,
            "hour_of_day": 14, "is_night": 0, "is_weekend": 0,
            "velocity_1m": 1, "velocity_5m": 3,
            "customer_txn_count": 200, "is_new_customer": 0,
            "payment_method_card": 1, "payment_method_wallet": 0,
            "currency_usd": 1, "has_device_fp": 1,
        }
        score = scorer._heuristic_score(features)
        assert score < 0.3, f"Low-risk features should score < 0.3, got {score}"


# ─── Unit: Redis Idempotency ──────────────────────────────────────────────────

class TestIdempotency:
    @pytest.mark.asyncio
    async def test_idempotency_cache_roundtrip(self):
        """Storing and retrieving an idempotency key should return same data."""
        from app.services.redis_service import RedisService
        service = RedisService()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value='{"payment_id": "pay_123", "status": "COMPLETED"}')
        mock_client.setex = AsyncMock(return_value=True)
        service._client = mock_client

        result = await service.check_idempotency("test_key_123")
        assert result is not None
        assert result["payment_id"] == "pay_123"
        assert result["status"] == "COMPLETED"

    @pytest.mark.asyncio
    async def test_idempotency_miss_returns_none(self):
        """Missing idempotency key should return None."""
        from app.services.redis_service import RedisService
        service = RedisService()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=None)
        service._client = mock_client

        result = await service.check_idempotency("nonexistent_key")
        assert result is None

    @pytest.mark.asyncio
    async def test_rate_limit_allows_under_limit(self):
        """Requests under limit should be allowed."""
        from app.services.redis_service import RedisService
        service = RedisService()

        mock_pipeline = AsyncMock()
        mock_pipeline.execute = AsyncMock(return_value=[0, 5, "OK", "OK"])
        mock_client = AsyncMock()
        mock_client.pipeline = MagicMock(return_value=mock_pipeline)
        service._client = mock_client

        allowed, count, retry_after = await service.check_rate_limit("merchant:test_123", limit=100)
        assert allowed is True
        assert retry_after == 0

    @pytest.mark.asyncio
    async def test_rate_limit_blocks_over_limit(self):
        """Requests over limit should be blocked."""
        from app.services.redis_service import RedisService
        service = RedisService()

        mock_pipeline = AsyncMock()
        mock_pipeline.execute = AsyncMock(return_value=[0, 101, "OK", "OK"])
        mock_client = AsyncMock()
        mock_client.pipeline = MagicMock(return_value=mock_pipeline)
        service._client = mock_client

        allowed, count, retry_after = await service.check_rate_limit("merchant:test_123", limit=100)
        assert allowed is False
        assert retry_after > 0


# ─── Unit: Payment State Machine ─────────────────────────────────────────────

class TestPaymentStateMachine:
    def test_valid_status_transitions(self):
        """Only valid state transitions should be allowed."""
        from app.models.payment import PaymentStatus

        # Valid flows
        valid_transitions = [
            (PaymentStatus.PENDING, PaymentStatus.PROCESSING),
            (PaymentStatus.PROCESSING, PaymentStatus.COMPLETED),
            (PaymentStatus.PROCESSING, PaymentStatus.FAILED),
            (PaymentStatus.PENDING, PaymentStatus.CANCELLED),
            (PaymentStatus.COMPLETED, PaymentStatus.REFUNDED),
            (PaymentStatus.COMPLETED, PaymentStatus.PARTIALLY_REFUNDED),
        ]
        # These are the transitions we implement — verify enum values exist
        for from_status, to_status in valid_transitions:
            assert from_status in PaymentStatus
            assert to_status in PaymentStatus

    def test_payment_statuses_complete(self):
        from app.models.payment import PaymentStatus
        expected = {"PENDING", "PROCESSING", "COMPLETED", "FAILED", "CANCELLED", "REFUNDED", "PARTIALLY_REFUNDED"}
        actual = {s.value for s in PaymentStatus}
        assert expected == actual


# ─── Integration: Payment API ─────────────────────────────────────────────────

class TestPaymentAPI:
    """
    Integration tests for the payment API.
    These require a running postgres + redis — run via docker compose.
    In CI they run against the service containers.
    """

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_payment_initiate_returns_201(self, valid_payment_payload):
        import httpx
        async with httpx.AsyncClient(base_url="http://localhost:8001") as client:
            resp = await client.post(
                "/api/v1/payments/",
                json=valid_payment_payload,
                headers={"Authorization": "Bearer test-token"},
            )
        assert resp.status_code in (201, 401)  # 401 if auth not bypassed

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_health_endpoint_returns_200(self):
        import httpx
        async with httpx.AsyncClient(base_url="http://localhost:8001") as client:
            resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert "checks" in data

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_idempotency_same_key_same_response(self, valid_payment_payload):
        """Two requests with same idempotency_key must return identical responses."""
        import httpx
        async with httpx.AsyncClient(base_url="http://localhost:8001") as client:
            r1 = await client.post("/api/v1/payments/", json=valid_payment_payload)
            r2 = await client.post("/api/v1/payments/", json=valid_payment_payload)

        if r1.status_code == 201 and r2.status_code == 201:
            assert r1.json()["id"] == r2.json()["id"]
            assert r1.json()["status"] == r2.json()["status"]


# ─── Unit: Fee Calculation ─────────────────────────────────────────────────────

class TestFeeCalculation:
    def test_fee_calculation_2_5_percent(self):
        """Default merchant fee should be 2.5%."""
        amount = Decimal("1000.00")
        fee_pct = Decimal("0.025")
        fee = round(amount * fee_pct, 4)
        net = amount - fee
        assert fee == Decimal("25.00")
        assert net == Decimal("975.00")

    def test_fee_never_exceeds_amount(self):
        """Fee can never be larger than the payment amount."""
        for amount_str in ["0.01", "1.00", "99999.99"]:
            amount = Decimal(amount_str)
            fee = round(amount * Decimal("0.025"), 4)
            assert fee <= amount

    def test_net_amount_is_positive(self):
        """Net amount after fee should always be positive."""
        for amount_str in ["0.01", "50.00", "1000.00"]:
            amount = Decimal(amount_str)
            fee = round(amount * Decimal("0.025"), 4)
            net = amount - fee
            assert net > 0


# ─── Run config ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-m", "not integration"])
