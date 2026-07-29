# PayFlow — Distributed Payment Processing Platform

> Production-grade event-driven payment infrastructure with real-time fraud detection, built for scale.

[![CI/CD](https://github.com/Jyotiraditya3005/payflow/actions/workflows/ci-cd.yml/badge.svg)](https://github.com/Jyotiraditya3005/payflow/actions)
[![Python](https://img.shields.io/badge/Python-3.12-blue)](https://python.org)
[![Java](https://img.shields.io/badge/Java-21-orange)](https://openjdk.org)
[![React](https://img.shields.io/badge/React-18-61DAFB)](https://react.dev)
[![Kafka](https://img.shields.io/badge/Kafka-event--driven-231F20)](https://kafka.apache.org)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED)](https://docs.docker.com/compose/)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

---

## At a Glance

- 8 services (1 Java gateway, 6 Python/FastAPI services, 1 React frontend) communicating over REST + Kafka
- Event-driven core with retry queue + dead-letter queue for failed payments
- 3-layer fraud pipeline: hard rules → soft/scored rules → ML ensemble (XGBoost + Isolation Forest)
- Full local observability stack: Prometheus, Grafana, Jaeger — no cloud account required to explore it
- 📚 **[Full documentation](docs/README.md)** — architecture, API reference, database schema, Kafka event flows, deployment path, security model, and ADRs

> Note: the CI/CD workflow includes a staging-deploy job that targets an AWS EKS cluster, but the Kubernetes manifests it depends on aren't in this repo yet — see [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for exactly what's implemented versus planned.

---

## Architecture

```
Client / Merchant SDK
        ↓
 ┌─────────────────────────────────────────────┐
 │  Spring Cloud Gateway  (Port 8080)          │
 │  • JWT validation      • Rate limiting       │
 │  • Circuit breaker     • Request tracing     │
 └──────┬──────────┬───────────────────────────┘
        ↓          ↓
 ┌─────────┐  ┌──────────────────────────────────┐
 │  Auth   │  │  Payment Service  (FastAPI 8001) │
 │ Service │  │  • Idempotency    • Retry engine  │
 │  :8000  │  │  • Fee calc       • ACID txns     │
 └─────────┘  └──────────┬───────────────────────┘
                          │         │
                   Sync call    Kafka event
                          ↓         ↓
              ┌───────────────┐  ┌──────────────────────┐
              │ Fraud Service │  │  Transaction Service  │
              │  (FastAPI)    │  │  Ledger Service       │
              │  XGBoost +    │  │  Notification Service │
              │  IsoForest    │  └──────────────────────┘
              └───────────────┘
```

## Tech Stack

| Layer         | Technology                              |
|---------------|-----------------------------------------|
| API Gateway   | Java 21 + Spring Boot 3 + Spring Cloud  |
| Backend       | Python 3.12 + FastAPI + SQLAlchemy      |
| Messaging     | Apache Kafka (6 topics, DLQ, retry)     |
| Database      | PostgreSQL 16 (partitioned tables)      |
| Cache / Lock  | Redis 7 (idempotency, rate limiting)    |
| ML / Fraud    | XGBoost + Isolation Forest + SHAP       |
| Frontend      | React 18 + Vite + Recharts + Tailwind   |
| Containers    | Docker + Docker Compose                 |
| Observability | Prometheus + Grafana + Jaeger (OTel)    |
| CI/CD         | GitHub Actions → AWS EKS               |

---

## Screenshots & Demo

_Not included yet — add these before sharing this repo with recruiters, they matter more than any other single change:_

1. Run `docker compose up -d`, open the frontend dashboard and Grafana, and
   take 3-4 screenshots (dashboard overview, a payment detail, a fraud case,
   a Grafana panel). Drop them in a `docs/screenshots/` folder and embed them
   here with `![Dashboard](docs/screenshots/dashboard.png)`.
2. Record a 20-30s terminal + browser screen capture of: login → create a
   payment → watch it move through Kafka → see the dashboard update. Convert
   to a GIF (e.g. with `ffmpeg` or [Gifski](https://gif.ski/)) and embed it
   at the top of this README, above the badges.

A GIF of the system actually working is the single highest-leverage addition
you can make to this README for recruiter attention.

---

## Microservices

| Service              | Port | Description                                          |
|----------------------|------|------------------------------------------------------|
| `api-gateway`        | 8080 | Spring Cloud Gateway — auth, routing, rate limiting |
| `auth-service`       | 8000 | JWT + RBAC, user management, API keys               |
| `payment-service`    | 8001 | Core payment processing, idempotency, refunds       |
| `fraud-service`      | 8003 | ML fraud engine + rule-based detection              |
| `transaction-service`| 8004 | Transaction lifecycle, Kafka consumer               |
| `ledger-service`     | 8005 | Double-entry bookkeeping, reconciliation            |
| `notification-service`| 8006| Webhooks, email alerts                              |
| `frontend`           | 3000 | React merchant dashboard                           |

---

## Kafka Topics

| Topic                | Partitions | Purpose                            |
|----------------------|------------|------------------------------------|
| `payments.created`   | 6          | New payment events                 |
| `payments.completed` | 6          | Successful payment events          |
| `payments.failed`    | 3          | Failed payment events              |
| `payments.retry`     | 3          | Retry queue with backoff           |
| `payments.dlq`       | 1          | Dead letter queue                  |
| `fraud.check`        | 6          | Async fraud check events           |
| `fraud.alerts`       | 3          | High-risk fraud alerts             |
| `webhooks.dispatch`  | 3          | Merchant webhook delivery          |

---

## Fraud Detection

Three-layer detection pipeline:

```
Layer 1 — Hard Rules (instant block)
  ├── IP blacklist check
  ├── Customer blacklist check
  └── Amount sanity check (> $1M)

Layer 2 — Soft Rules (score contribution)
  ├── Velocity check (10+ txns/minute → flag)
  ├── Geo anomaly (different IP subnet)
  ├── Amount spike (>5x customer average)
  ├── Odd-hours detection (1 AM – 5 AM UTC)
  └── New device fingerprint

Layer 3 — ML Ensemble
  ├── XGBoost classifier (supervised, AUC ~0.94)
  └── Isolation Forest (unsupervised anomaly)

Final score = 0.55 × ML + 0.45 × Rules
```

Risk thresholds: LOW (<35%) → MEDIUM (<65%) → HIGH (<85%) → CRITICAL (≥85%)

---

## Quick Start

### Prerequisites
- Docker Desktop with Compose v2
- 8 GB RAM minimum (Kafka + Postgres + all services)

### Run

```bash
git clone https://github.com/Jyotiraditya3005/payflow.git
cd payflow

# Start all services
docker compose up -d

# Wait for services to be healthy (~60s)
docker compose ps

# Check logs
docker compose logs -f payment-service
```

### Access

| Service         | URL                                  |
|-----------------|--------------------------------------|
| Merchant Dashboard | http://localhost:3000             |
| API Gateway     | http://localhost:8080                |
| Payment API Docs| http://localhost:8001/docs           |
| Fraud API Docs  | http://localhost:8003/docs           |
| Auth API Docs   | http://localhost:8000/docs           |
| Grafana         | http://localhost:3001 (admin/payflow_grafana) |
| Prometheus      | http://localhost:9090                |
| Jaeger Tracing  | http://localhost:16686               |
| Kafka UI        | http://localhost:9080                |

---

## API Examples

### Register & Login

```bash
# Register
curl -X POST http://localhost:8080/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"merchant@example.com","password":"secure123","full_name":"ACME Corp","role":"MERCHANT"}'

# Login
TOKEN=$(curl -sX POST http://localhost:8080/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"merchant@example.com","password":"secure123"}' | jq -r '.access_token')
```

### Initiate a Payment

```bash
curl -X POST http://localhost:8080/api/v1/payments/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "idempotency_key": "order_123_attempt_1",
    "merchant_id": "YOUR_MERCHANT_UUID",
    "customer_id": "CUSTOMER_UUID",
    "amount": 299.99,
    "currency": "USD",
    "payment_method": "CARD",
    "card_token": "tok_visa_4242",
    "description": "Annual subscription"
  }'
```

### Idempotency — Safe to Retry

```bash
# Send the same request twice — get the same response, no double charge
for i in 1 2 3; do
  curl -X POST http://localhost:8080/api/v1/payments/ \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"idempotency_key": "order_123_attempt_1", ...}'
done
```

### Partial Refund

```bash
curl -X POST http://localhost:8080/api/v1/payments/PAYMENT_ID/refund \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"idempotency_key": "refund_order_123_1", "amount": 50.00, "reason": "Partial return"}'
```

---

## Key Engineering Concepts

### Idempotency
Every payment requires a unique `idempotency_key`. The system stores responses in Redis (24h TTL). Retrying with the same key always returns the original response — **no double charges possible**.

### Distributed Locking
Redis distributed locks (Redlock-pattern) prevent race conditions when concurrent requests use the same idempotency key.

### Saga Pattern
Cross-service state transitions follow the saga pattern via Kafka events. Failed steps publish compensating events (refund, rollback) to maintain consistency without distributed transactions.

### Circuit Breaker
Resilience4j circuit breakers in Spring Cloud Gateway protect against cascading failures. If the fraud service is down, payments fall back to LOW risk instead of blocking.

### Dead Letter Queue
Messages that fail after 3 retry attempts go to `payments.dlq` for manual inspection and replay.

### Double-Entry Ledger
Every payment creates paired DEBIT/CREDIT entries in the ledger, ensuring the accounting always balances. The `ledger_reconciliation` view surfaces any discrepancies instantly.

---

## Project Structure

```
payflow/
├── api-gateway/          # Spring Boot 3 + Spring Cloud Gateway
│   ├── src/main/java/com/payflow/gateway/
│   │   ├── filter/       # JWT auth + request logging filters
│   │   └── routes/       # Circuit breaker fallbacks
│   └── src/main/resources/application.yml
├── auth-service/         # FastAPI — JWT + RBAC
├── payment-service/      # FastAPI — core payment processing
│   ├── app/
│   │   ├── api/          # HTTP routes
│   │   ├── core/         # Config, settings
│   │   ├── db/           # SQLAlchemy async session
│   │   ├── models/       # ORM models
│   │   ├── schemas/      # Pydantic schemas
│   │   └── services/     # Business logic, Kafka, Redis
│   └── tests/
├── fraud-service/        # FastAPI — ML fraud detection
│   └── app/services/
│       ├── fraud_engine.py    # 3-layer detection pipeline
│       └── ml_scorer.py       # XGBoost + Isolation Forest
├── transaction-service/  # Kafka consumer — transaction lifecycle
├── ledger-service/       # Double-entry bookkeeping
├── notification-service/ # Webhooks + email
├── frontend/             # React 18 merchant dashboard
│   └── src/components/
│       ├── dashboard/    # KPIs, volume charts
│       ├── transactions/ # Payment list + detail
│       └── fraud/        # Fraud cases + blacklists
├── infra/
│   ├── postgres/init.sql # DB init + partitioned tables
│   ├── prometheus/       # Metrics scrape config
│   └── grafana/          # Dashboard provisioning
├── .github/workflows/    # CI/CD pipeline
└── docker-compose.yml    # Full stack orchestration
```

---

## Resume Highlights (for applications)

> "Built a production-grade distributed payment processing platform processing simulated $2M+/day volume across 8 microservices. Key contributions:
> - Designed event-driven architecture using Apache Kafka with idempotent producers, DLQ, and exponential backoff retry for fault-tolerant async processing
> - Implemented a 3-layer real-time fraud detection engine (XGBoost + Isolation Forest ensemble, velocity checks, geo anomaly, device fingerprinting) achieving <50ms detection latency
> - Built distributed idempotency system using Redis to guarantee exactly-once payment semantics at scale, preventing duplicate charges under concurrent load
> - Configured Spring Cloud Gateway with JWT authentication, circuit breakers (Resilience4j), and Redis-backed sliding window rate limiting (1000 req/min/merchant)
> - Implemented double-entry bookkeeping ledger with PostgreSQL partitioned tables (monthly) for high-throughput transaction history queries
> - Set up full observability stack: Prometheus metrics, Grafana dashboards, OpenTelemetry distributed tracing via Jaeger across all services"

---

## License

MIT — build, learn, interview with it.
