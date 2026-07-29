-- PayFlow PostgreSQL Initialization
-- Creates separate databases per microservice (database-per-service pattern)

-- Create databases
CREATE DATABASE payflow_auth;
CREATE DATABASE payflow_payments;
CREATE DATABASE payflow_fraud;
CREATE DATABASE payflow_transactions;
CREATE DATABASE payflow_ledger;

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE payflow_auth TO payflow;
GRANT ALL PRIVILEGES ON DATABASE payflow_payments TO payflow;
GRANT ALL PRIVILEGES ON DATABASE payflow_fraud TO payflow;
GRANT ALL PRIVILEGES ON DATABASE payflow_transactions TO payflow;
GRANT ALL PRIVILEGES ON DATABASE payflow_ledger TO payflow;

-- ─── Payments DB Extensions ──────────────────────────────────────────────────
\c payflow_payments
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";  -- Query performance monitoring
CREATE EXTENSION IF NOT EXISTS "pg_trgm";             -- Fuzzy text search

-- ─── Fraud DB Extensions ──────────────────────────────────────────────────────
\c payflow_fraud
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";

-- ─── Ledger DB ────────────────────────────────────────────────────────────────
\c payflow_ledger
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Double-entry ledger table (created manually for strict control)
CREATE TABLE IF NOT EXISTS ledger_entries (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    payment_id      UUID NOT NULL,
    entry_type      VARCHAR(20) NOT NULL CHECK (entry_type IN ('DEBIT', 'CREDIT')),
    account_type    VARCHAR(50) NOT NULL,   -- e.g. MERCHANT_RECEIVABLE, PLATFORM_FEE, CUSTOMER_PAYABLE
    account_id      UUID NOT NULL,
    amount          NUMERIC(20, 4) NOT NULL CHECK (amount > 0),
    currency        VARCHAR(10) NOT NULL,
    description     TEXT,
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_ledger_payment_id ON ledger_entries(payment_id);
CREATE INDEX idx_ledger_account_id ON ledger_entries(account_id);
CREATE INDEX idx_ledger_created_at ON ledger_entries(created_at DESC);
CREATE INDEX idx_ledger_account_type ON ledger_entries(account_type, currency);

-- Reconciliation view: sum all entries per payment (should always net to 0)
CREATE VIEW ledger_reconciliation AS
SELECT
    payment_id,
    currency,
    SUM(CASE WHEN entry_type = 'DEBIT' THEN amount ELSE -amount END) AS net_balance,
    COUNT(*) AS entry_count,
    MIN(created_at) AS first_entry,
    MAX(created_at) AS last_entry
FROM ledger_entries
GROUP BY payment_id, currency;

-- ─── Transactions DB ──────────────────────────────────────────────────────────
\c payflow_transactions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";

-- Partitioned transactions table (partition by month for performance)
CREATE TABLE IF NOT EXISTS transactions (
    id              UUID NOT NULL DEFAULT uuid_generate_v4(),
    payment_id      UUID NOT NULL,
    merchant_id     UUID NOT NULL,
    customer_id     UUID NOT NULL,
    amount          NUMERIC(20, 4) NOT NULL,
    currency        VARCHAR(10) NOT NULL,
    status          VARCHAR(30) NOT NULL,
    payment_method  VARCHAR(30) NOT NULL,
    fraud_risk      VARCHAR(20),
    fraud_score     NUMERIC(5, 4),
    processing_ms   INTEGER,    -- Time taken to process in ms
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (id, created_at)
) PARTITION BY RANGE (created_at);

-- Create partitions for current and next 3 months
CREATE TABLE transactions_2026_05 PARTITION OF transactions
    FOR VALUES FROM ('2026-05-01') TO ('2026-06-01');
CREATE TABLE transactions_2026_06 PARTITION OF transactions
    FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');
CREATE TABLE transactions_2026_07 PARTITION OF transactions
    FOR VALUES FROM ('2026-07-01') TO ('2026-08-01');
CREATE TABLE transactions_2026_08 PARTITION OF transactions
    FOR VALUES FROM ('2026-08-01') TO ('2026-09-01');

CREATE INDEX idx_txn_payment_id ON transactions(payment_id, created_at);
CREATE INDEX idx_txn_merchant_id ON transactions(merchant_id, created_at DESC);
CREATE INDEX idx_txn_customer_id ON transactions(customer_id, created_at DESC);
CREATE INDEX idx_txn_status ON transactions(status, created_at);

-- Analytics aggregation table (updated by Kafka consumer)
CREATE TABLE IF NOT EXISTS transaction_hourly_stats (
    hour            TIMESTAMPTZ NOT NULL,
    merchant_id     UUID NOT NULL,
    currency        VARCHAR(10) NOT NULL,
    total_count     INTEGER NOT NULL DEFAULT 0,
    total_volume    NUMERIC(20, 4) NOT NULL DEFAULT 0,
    success_count   INTEGER NOT NULL DEFAULT 0,
    fraud_count     INTEGER NOT NULL DEFAULT 0,
    avg_amount      NUMERIC(20, 4),
    PRIMARY KEY (hour, merchant_id, currency)
);

\echo 'PayFlow databases initialized successfully'
