# Database Schema

Each service owns its own tables in PostgreSQL 16 — there is no shared schema
or cross-service foreign key. This doc summarizes the core tables as
currently defined in code.

## `payment-service` (`app/models/payment.py`)

### `payments`
Primary payment record.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID (PK) | |
| `idempotency_key` | string, unique | dedupes retried requests |
| `merchant_id`, `customer_id` | UUID, indexed | |
| `amount`, `fee_amount`, `net_amount` | numeric(20,4) | decimal precision for money |
| `currency` | enum (`USD`,`EUR`,`GBP`,`INR`,`JPY`,`SGD`) | |
| `status` | enum (`PENDING`→`PROCESSING`→`COMPLETED`/`FAILED`/`CANCELLED`, plus `REFUNDED`/`PARTIALLY_REFUNDED`) | indexed |
| `payment_method` | enum (`CARD`,`BANK_TRANSFER`,`WALLET`,`UPI`,`NET_BANKING`) | |
| `fraud_risk`, `fraud_score`, `fraud_flags` | enum / numeric / JSONB | result of fraud-service check |
| `retry_count`, `max_retries` | int | |
| `created_at`, `updated_at`, `processed_at`, `expires_at` | timestamptz | |

Composite indexes: `(merchant_id, status)`, `(customer_id, status)`,
`created_at desc`, `fraud_risk`.

### `payment_events`
Immutable audit log of every status transition (`from_status` → `to_status`,
`actor`, `payload`, `error`), FK'd to `payments.id`.

### `refunds`
FK'd to `payments.id`; own `idempotency_key`, `amount`, `currency`, `reason`,
`status`.

### `merchants`
Referenced by `payments.merchant_id`; merchant account/config record.

## `fraud-service` (`app/models/fraud.py`)

- **`fraud_cases`** — a flagged case for manual/automated review.
- **`fraud_rules`** — configurable rule definitions (thresholds, weights).
- **`customer_risk_profiles`** — rolling risk signal per customer, used as
  input to the velocity/anomaly checks.

## `auth-service`

- **`users`** — currently defined directly in `app/main.py` rather than
  under `app/models/`, which is inconsistent with the other services'
  layering. Moving it to `app/models/user.py` is a good first refactor
  (see roadmap item "Microservice Improvements").

## Indexing Strategy

- Every foreign key and every column used in a `WHERE`/`ORDER BY` on a hot
  path (`status`, `merchant_id`, `customer_id`, `created_at`) has an index.
- Money columns use `numeric(20,4)`, not floating point, to avoid rounding
  drift.
- `idempotency_key` is uniquely indexed so duplicate submission is a DB-level
  guarantee, not just an application-level check.

## Gaps / Follow-ups

- No read replicas or partitioning configured yet (listed in the roadmap
  under "Database" improvements) — fine at current scale, worth adding before
  claiming high-volume production readiness.
- No migration tool (Alembic/Flyway) is wired in yet; schema is created from
  models directly, which is fine for a demo but should be replaced with
  versioned migrations before this is treated as a real service.
