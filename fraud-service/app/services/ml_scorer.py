"""
ML-based fraud scorer using an ensemble of:
1. XGBoost classifier (trained on synthetic fraud data)
2. Isolation Forest (unsupervised anomaly detection)

In production: retrain periodically on labeled transaction data.
This module pre-trains on startup with synthetic data for demo purposes.
"""

import asyncio
import numpy as np
import joblib
import os
import structlog
from pathlib import Path
from typing import Optional

from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

logger = structlog.get_logger()

FEATURE_NAMES = [
    "amount",
    "amount_log",
    "amount_vs_avg",
    "hour_of_day",
    "is_night",
    "is_weekend",
    "velocity_1m",
    "velocity_5m",
    "customer_txn_count",
    "is_new_customer",
    "payment_method_card",
    "payment_method_wallet",
    "currency_usd",
    "has_device_fp",
]

MODEL_PATH = Path("/tmp/payflow_models")


class MLFraudScorer:
    """
    Ensemble fraud scorer. Falls back to rule-only scoring if models not loaded.
    Uses XGBoost for supervised scoring + Isolation Forest for anomaly detection.
    """

    def __init__(self):
        self._xgb_model = None
        self._isolation_forest: Optional[IsolationForest] = None
        self._scaler: Optional[StandardScaler] = None
        self._loaded = False

    async def initialize(self):
        """Load or train models on startup."""
        MODEL_PATH.mkdir(parents=True, exist_ok=True)
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._load_or_train)

    def _load_or_train(self):
        xgb_path = MODEL_PATH / "xgb_fraud.joblib"
        iso_path = MODEL_PATH / "iso_forest.joblib"
        scaler_path = MODEL_PATH / "scaler.joblib"

        if xgb_path.exists() and iso_path.exists():
            logger.info("Loading pre-trained fraud models")
            try:
                self._xgb_model = joblib.load(xgb_path)
                self._isolation_forest = joblib.load(iso_path)
                self._scaler = joblib.load(scaler_path)
                self._loaded = True
                logger.info("Fraud models loaded successfully")
                return
            except Exception as e:
                logger.warning("Failed to load models, retraining", error=str(e))

        logger.info("Training fraud detection models on synthetic data")
        self._train_models()

        # Save for reuse
        if self._xgb_model:
            joblib.dump(self._xgb_model, xgb_path)
        joblib.dump(self._isolation_forest, iso_path)
        joblib.dump(self._scaler, scaler_path)
        logger.info("Fraud models trained and saved")

    def _generate_synthetic_data(self, n_samples: int = 10000):
        """
        Generate synthetic transaction data for training.
        Fraud patterns baked in:
        - High amount + high velocity = fraud
        - Night transactions + new customer = suspicious
        - Amount spikes = fraud
        """
        rng = np.random.RandomState(42)

        # Legitimate transactions (90%)
        n_legit = int(n_samples * 0.90)
        legit = np.column_stack([
            rng.lognormal(4, 1.5, n_legit),         # amount: ~$55 avg
            np.zeros(n_legit),                        # amount_log (computed)
            rng.uniform(0.5, 2.0, n_legit),           # amount_vs_avg: near avg
            rng.randint(7, 22, n_legit),              # hour: business hours
            np.zeros(n_legit),                        # is_night: no
            rng.randint(0, 2, n_legit),               # is_weekend
            rng.randint(0, 3, n_legit),               # velocity_1m: low
            rng.randint(0, 10, n_legit),              # velocity_5m: low
            rng.randint(5, 500, n_legit),             # customer_txn_count: established
            np.zeros(n_legit),                        # is_new_customer: no
            rng.randint(0, 2, n_legit),               # payment_method_card
            rng.randint(0, 2, n_legit),               # payment_method_wallet
            rng.randint(0, 2, n_legit),               # currency_usd
            np.ones(n_legit),                         # has_device_fp: yes
        ])

        # Fraudulent transactions (10%)
        n_fraud = n_samples - n_legit
        fraud = np.column_stack([
            rng.lognormal(7, 1.0, n_fraud),          # amount: high
            np.zeros(n_fraud),
            rng.uniform(5, 50, n_fraud),              # amount_vs_avg: huge spike
            rng.choice([2, 3, 4, 23, 0, 1], n_fraud), # hour: night
            np.ones(n_fraud),                         # is_night: yes
            rng.randint(0, 2, n_fraud),
            rng.randint(8, 20, n_fraud),              # velocity_1m: high
            rng.randint(20, 50, n_fraud),             # velocity_5m: very high
            rng.randint(0, 5, n_fraud),               # customer_txn_count: new
            np.ones(n_fraud),                         # is_new_customer: yes
            np.ones(n_fraud),                         # payment_method_card
            np.zeros(n_fraud),
            rng.randint(0, 2, n_fraud),
            np.zeros(n_fraud),                        # has_device_fp: no
        ])

        X = np.vstack([legit, fraud])
        y = np.array([0] * n_legit + [1] * n_fraud)

        # Fix amount_log column (index 1)
        X[:, 1] = np.log1p(X[:, 0])

        # Shuffle
        idx = rng.permutation(len(y))
        return X[idx], y[idx]

    def _train_models(self):
        X, y = self._generate_synthetic_data(n_samples=15000)

        # Scale features
        self._scaler = StandardScaler()
        X_scaled = self._scaler.fit_transform(X)

        # Isolation Forest for unsupervised anomaly detection
        self._isolation_forest = IsolationForest(
            n_estimators=200,
            contamination=0.1,  # Expected fraud rate
            random_state=42,
            n_jobs=-1,
        )
        self._isolation_forest.fit(X_scaled)

        # Try XGBoost, fall back to GradientBoosting
        try:
            import xgboost as xgb
            self._xgb_model = xgb.XGBClassifier(
                n_estimators=200,
                max_depth=6,
                learning_rate=0.05,
                subsample=0.8,
                colsample_bytree=0.8,
                scale_pos_weight=9,  # Handle class imbalance (9:1 ratio)
                random_state=42,
                eval_metric="auc",
                use_label_encoder=False,
            )
            self._xgb_model.fit(X_scaled, y)
            logger.info("XGBoost model trained")
        except Exception as e:
            logger.warning("XGBoost unavailable, using GradientBoosting fallback", error=str(e))
            from sklearn.ensemble import GradientBoostingClassifier
            self._xgb_model = GradientBoostingClassifier(
                n_estimators=100, max_depth=5, learning_rate=0.05, random_state=42
            )
            self._xgb_model.fit(X_scaled, y)

        self._loaded = True

    async def score(self, features: dict) -> float:
        """
        Score a transaction. Returns probability of fraud [0.0, 1.0].
        """
        if not self._loaded:
            logger.warning("Models not loaded, returning heuristic score")
            return self._heuristic_score(features)

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._score_sync, features)

    def _score_sync(self, features: dict) -> float:
        try:
            X = np.array([[features.get(f, 0) for f in FEATURE_NAMES]])
            X_scaled = self._scaler.transform(X)

            # XGBoost probability
            xgb_prob = self._xgb_model.predict_proba(X_scaled)[0][1]

            # Isolation Forest anomaly score (convert to [0, 1])
            iso_raw = self._isolation_forest.score_samples(X_scaled)[0]
            # score_samples returns negative values; more negative = more anomalous
            iso_score = 1.0 - (iso_raw - (-0.5)) / 0.5  # Normalize roughly to [0, 1]
            iso_score = max(0.0, min(1.0, iso_score))

            # Ensemble: weight XGBoost more (supervised > unsupervised)
            final = 0.7 * xgb_prob + 0.3 * iso_score
            return float(max(0.0, min(1.0, final)))

        except Exception as e:
            logger.error("ML scoring failed", error=str(e))
            return self._heuristic_score(features)

    def _heuristic_score(self, features: dict) -> float:
        """Simple heuristic fallback when models aren't available."""
        score = 0.0
        if features.get("velocity_1m", 0) > 5:
            score += 0.3
        if features.get("amount_vs_avg", 1) > 5:
            score += 0.3
        if features.get("is_night", 0):
            score += 0.1
        if features.get("is_new_customer", 0):
            score += 0.2
        if not features.get("has_device_fp", 0):
            score += 0.1
        return min(score, 1.0)
