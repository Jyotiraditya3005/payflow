import asyncio
import hashlib
import json
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Optional
from uuid import UUID

import numpy as np
import structlog
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.fraud import FraudCase, FraudRule, CustomerRiskProfile
from app.schemas.fraud import (
    FraudCheckRequest, FraudCheckResponse,
    RiskLevel, FraudFlag
)
from app.services.ml_scorer import MLFraudScorer
from app.services.redis_service import redis_service

logger = structlog.get_logger()


class FraudDetectionEngine:
    """
    Multi-layer fraud detection engine:

    Layer 1 — Hard Rules (instant blocking)
        • Blacklisted IPs / customers
        • Transaction amount limits
        • Impossible velocity

    Layer 2 — Soft Rules (score contribution)
        • Velocity checks (frequency analysis)
        • Geo anomaly detection
        • Time-of-day patterns
        • Merchant category risk

    Layer 3 — ML Scoring (XGBoost + Isolation Forest)
        • Feature engineering from transaction history
        • Anomaly detection
        • Ensemble risk score

    Final Score = weighted(rule_score, ml_score)
    """

    # Score thresholds → risk levels
    THRESHOLDS = {
        RiskLevel.LOW: 0.0,
        RiskLevel.MEDIUM: 0.35,
        RiskLevel.HIGH: 0.65,
        RiskLevel.CRITICAL: 0.85,
    }

    def __init__(self):
        self.ml_scorer = MLFraudScorer()
        self._rule_weights = {
            "velocity_exceeded": 0.4,
            "geo_anomaly": 0.3,
            "amount_spike": 0.25,
            "odd_hours": 0.1,
            "new_device": 0.15,
            "blacklisted": 1.0,  # Instant block
        }

    async def check(
        self,
        request: FraudCheckRequest,
        db: AsyncSession,
    ) -> FraudCheckResponse:

        log = logger.bind(
            payment_id=str(request.payment_id),
            customer_id=str(request.customer_id),
            amount=str(request.amount),
        )
        log.info("Fraud check initiated")

        flags: list[FraudFlag] = []
        rule_score = 0.0

        # ── Layer 1: Hard Rules ──────────────────────────────────────────────
        hard_block = await self._check_blacklists(request, db)
        if hard_block:
            flags.append(FraudFlag(
                flag_type="BLACKLISTED",
                severity="CRITICAL",
                description=hard_block,
                contribution=1.0,
            ))
            return self._build_response(
                request, risk_score=1.0, flags=flags,
                recommendation="DECLINE",
                details={"hard_block": hard_block}
            )

        # ── Layer 2: Rule-Based Scoring ───────────────────────────────────────
        velocity_flag = await self._check_velocity(request)
        if velocity_flag:
            flags.append(velocity_flag)
            rule_score += velocity_flag.contribution * self._rule_weights["velocity_exceeded"]

        geo_flag = await self._check_geo_anomaly(request, db)
        if geo_flag:
            flags.append(geo_flag)
            rule_score += geo_flag.contribution * self._rule_weights["geo_anomaly"]

        amount_flag = await self._check_amount_spike(request, db)
        if amount_flag:
            flags.append(amount_flag)
            rule_score += amount_flag.contribution * self._rule_weights["amount_spike"]

        time_flag = self._check_odd_hours(request)
        if time_flag:
            flags.append(time_flag)
            rule_score += time_flag.contribution * self._rule_weights["odd_hours"]

        device_flag = await self._check_new_device(request)
        if device_flag:
            flags.append(device_flag)
            rule_score += device_flag.contribution * self._rule_weights["new_device"]

        rule_score = min(rule_score, 1.0)

        # ── Layer 3: ML Scoring ───────────────────────────────────────────────
        features = await self._extract_features(request, db)
        ml_score = await self.ml_scorer.score(features)

        # ── Ensemble: weighted combination ────────────────────────────────────
        final_score = (0.55 * ml_score) + (0.45 * rule_score)
        final_score = min(final_score, 1.0)

        # ── Determine risk level ──────────────────────────────────────────────
        risk_level = self._score_to_risk(final_score)

        # ── Recommendation ────────────────────────────────────────────────────
        if risk_level == RiskLevel.CRITICAL:
            recommendation = "DECLINE"
        elif risk_level == RiskLevel.HIGH:
            recommendation = "REVIEW"  # Manual review queue
        else:
            recommendation = "APPROVE"

        # ── Store fraud case if high risk ─────────────────────────────────────
        if risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
            await self._log_fraud_case(request, final_score, risk_level, flags, db)

        # ── Update customer risk profile ──────────────────────────────────────
        await self._update_customer_profile(request, final_score, db)

        log.info(
            "Fraud check completed",
            risk_level=risk_level,
            final_score=round(final_score, 4),
            ml_score=round(ml_score, 4),
            rule_score=round(rule_score, 4),
            flags=[f.flag_type for f in flags],
        )

        return self._build_response(
            request,
            risk_score=final_score,
            flags=flags,
            recommendation=recommendation,
            details={
                "ml_score": round(ml_score, 4),
                "rule_score": round(rule_score, 4),
                "features": features,
            }
        )

    # ─── Layer 1: Hard Rules ──────────────────────────────────────────────────

    async def _check_blacklists(
        self, request: FraudCheckRequest, db: AsyncSession
    ) -> Optional[str]:
        """Check against known bad actors — IPs, customers, cards."""
        # Check IP blacklist
        if request.ip_address:
            is_blacklisted = await redis_service.client.sismember(
                "blacklist:ips", request.ip_address
            )
            if is_blacklisted:
                return f"IP {request.ip_address} is blacklisted"

        # Check customer blacklist
        is_customer_blacklisted = await redis_service.client.sismember(
            "blacklist:customers", str(request.customer_id)
        )
        if is_customer_blacklisted:
            return f"Customer {request.customer_id} is blacklisted"

        # Sanity check: impossible amount
        if float(request.amount) > settings.MAX_TRANSACTION_AMOUNT:
            return f"Amount {request.amount} exceeds maximum allowed"

        return None

    # ─── Layer 2: Rule-Based Checks ───────────────────────────────────────────

    async def _check_velocity(self, request: FraudCheckRequest) -> Optional["FraudFlag"]:
        """
        Velocity check: too many transactions from same customer in short window.
        Uses Redis sliding window counter.
        """
        customer_key = f"velocity:customer:{request.customer_id}:1m"
        count_1m = await redis_service.increment(customer_key, ttl=60)

        if count_1m > 10:  # More than 10 transactions/minute
            return FraudFlag(
                flag_type="VELOCITY_EXCEEDED",
                severity="HIGH",
                description=f"Customer made {count_1m} transactions in 1 minute",
                contribution=min(count_1m / 20, 1.0),
            )

        # 5-minute window
        key_5m = f"velocity:customer:{request.customer_id}:5m"
        count_5m = await redis_service.increment(key_5m, ttl=300)
        if count_5m > 30:
            return FraudFlag(
                flag_type="VELOCITY_EXCEEDED_5M",
                severity="MEDIUM",
                description=f"Customer made {count_5m} transactions in 5 minutes",
                contribution=0.5,
            )

        return None

    async def _check_geo_anomaly(
        self, request: FraudCheckRequest, db: AsyncSession
    ) -> Optional["FraudFlag"]:
        """
        Geo anomaly: transaction from unusual location for this customer.
        Compares current IP against customer's historical IP pattern.
        """
        if not request.ip_address:
            return None

        # Get last known IP for this customer from Redis
        last_ip_key = f"customer:last_ip:{request.customer_id}"
        last_ip = await redis_service.client.get(last_ip_key)

        if last_ip and last_ip != request.ip_address:
            # Check if IPs are in drastically different subnets (simplified geo check)
            last_octets = last_ip.split(".")
            curr_octets = request.ip_address.split(".")
            if len(last_octets) == 4 and len(curr_octets) == 4:
                if last_octets[0] != curr_octets[0]:
                    # Different /8 subnet — could be different country
                    return FraudFlag(
                        flag_type="GEO_ANOMALY",
                        severity="MEDIUM",
                        description=f"Transaction from unusual IP: {request.ip_address} (last: {last_ip})",
                        contribution=0.6,
                    )

        # Store current IP for future comparison
        await redis_service.client.setex(last_ip_key, 86400, request.ip_address)
        return None

    async def _check_amount_spike(
        self, request: FraudCheckRequest, db: AsyncSession
    ) -> Optional["FraudFlag"]:
        """Check if transaction amount is anomalous vs customer's history."""
        avg_key = f"customer:avg_amount:{request.customer_id}"
        avg_amount_str = await redis_service.client.get(avg_key)

        if avg_amount_str:
            avg_amount = float(avg_amount_str)
            current_amount = float(request.amount)

            if avg_amount > 0 and current_amount > avg_amount * 5:
                ratio = current_amount / avg_amount
                return FraudFlag(
                    flag_type="AMOUNT_SPIKE",
                    severity="HIGH",
                    description=f"Transaction is {ratio:.1f}x customer's average ({avg_amount:.2f})",
                    contribution=min(ratio / 20, 1.0),
                )

        # Update running average
        count_key = f"customer:txn_count:{request.customer_id}"
        count = await redis_service.increment(count_key, ttl=2592000)  # 30 days
        if avg_amount_str:
            new_avg = (float(avg_amount_str) * (count - 1) + float(request.amount)) / count
        else:
            new_avg = float(request.amount)
        await redis_service.client.setex(avg_key, 2592000, str(new_avg))

        return None

    def _check_odd_hours(self, request: FraudCheckRequest) -> Optional["FraudFlag"]:
        """Transactions between 1 AM - 5 AM local time are slightly suspicious."""
        hour = datetime.now(timezone.utc).hour
        if 1 <= hour <= 5:
            return FraudFlag(
                flag_type="ODD_HOURS",
                severity="LOW",
                description=f"Transaction at unusual hour: {hour}:00 UTC",
                contribution=0.3,
            )
        return None

    async def _check_new_device(self, request: FraudCheckRequest) -> Optional["FraudFlag"]:
        """Flag transactions from a device fingerprint we haven't seen for this customer."""
        if not request.device_fingerprint:
            return None

        device_key = f"customer:devices:{request.customer_id}"
        known = await redis_service.client.sismember(device_key, request.device_fingerprint)

        if not known:
            await redis_service.client.sadd(device_key, request.device_fingerprint)
            await redis_service.client.expire(device_key, 2592000)

            # Check how many devices this customer has used
            device_count = await redis_service.client.scard(device_key)
            if device_count > 5:
                return FraudFlag(
                    flag_type="NEW_DEVICE",
                    severity="MEDIUM",
                    description=f"New device fingerprint (customer has {device_count} devices)",
                    contribution=0.4,
                )

        return None

    # ─── Layer 3: Feature Extraction ─────────────────────────────────────────

    async def _extract_features(
        self, request: FraudCheckRequest, db: AsyncSession
    ) -> dict:
        """Build feature vector for ML model."""
        hour = datetime.now(timezone.utc).hour

        # Velocity features from Redis
        v1m = int(await redis_service.client.get(f"velocity:customer:{request.customer_id}:1m") or 0)
        v5m = int(await redis_service.client.get(f"velocity:customer:{request.customer_id}:5m") or 0)
        avg_amount = float(await redis_service.client.get(f"customer:avg_amount:{request.customer_id}") or request.amount)
        txn_count = int(await redis_service.client.get(f"customer:txn_count:{request.customer_id}") or 1)

        amount = float(request.amount)

        return {
            "amount": amount,
            "amount_log": np.log1p(amount),
            "amount_vs_avg": amount / avg_amount if avg_amount > 0 else 1.0,
            "hour_of_day": hour,
            "is_night": 1 if 22 <= hour or hour <= 5 else 0,
            "is_weekend": 1 if datetime.now().weekday() >= 5 else 0,
            "velocity_1m": v1m,
            "velocity_5m": v5m,
            "customer_txn_count": min(txn_count, 1000),
            "is_new_customer": 1 if txn_count <= 3 else 0,
            "payment_method_card": 1 if request.payment_method.value == "CARD" else 0,
            "payment_method_wallet": 1 if request.payment_method.value == "WALLET" else 0,
            "currency_usd": 1 if request.currency.value == "USD" else 0,
            "has_device_fp": 1 if request.device_fingerprint else 0,
        }

    # ─── Helpers ──────────────────────────────────────────────────────────────

    def _score_to_risk(self, score: float) -> "RiskLevel":
        if score >= self.THRESHOLDS[RiskLevel.CRITICAL]:
            return RiskLevel.CRITICAL
        elif score >= self.THRESHOLDS[RiskLevel.HIGH]:
            return RiskLevel.HIGH
        elif score >= self.THRESHOLDS[RiskLevel.MEDIUM]:
            return RiskLevel.MEDIUM
        return RiskLevel.LOW

    def _build_response(
        self,
        request: FraudCheckRequest,
        risk_score: float,
        flags: list,
        recommendation: str,
        details: dict,
    ) -> FraudCheckResponse:
        return FraudCheckResponse(
            payment_id=request.payment_id,
            risk_level=self._score_to_risk(risk_score),
            risk_score=round(risk_score, 4),
            flags=[f.flag_type for f in flags],
            recommendation=recommendation,
            details=details,
        )

    async def _log_fraud_case(
        self, request: FraudCheckRequest, score: float,
        risk_level: "RiskLevel", flags: list, db: AsyncSession
    ):
        case = FraudCase(
            payment_id=request.payment_id,
            customer_id=request.customer_id,
            merchant_id=request.merchant_id,
            amount=request.amount,
            risk_score=score,
            risk_level=risk_level,
            flags=[f.flag_type for f in flags],
            ip_address=request.ip_address,
        )
        db.add(case)
        await db.flush()

    async def _update_customer_profile(
        self, request: FraudCheckRequest, score: float, db: AsyncSession
    ):
        result = await db.execute(
            select(CustomerRiskProfile).where(
                CustomerRiskProfile.customer_id == request.customer_id
            )
        )
        profile = result.scalar_one_or_none()

        if profile:
            # Exponential moving average of risk score
            profile.avg_risk_score = 0.8 * profile.avg_risk_score + 0.2 * score
            profile.total_transactions += 1
            profile.last_transaction_at = datetime.now(timezone.utc)
        else:
            profile = CustomerRiskProfile(
                customer_id=request.customer_id,
                avg_risk_score=score,
                total_transactions=1,
                last_transaction_at=datetime.now(timezone.utc),
            )
            db.add(profile)

        await db.flush()


fraud_engine = FraudDetectionEngine()
