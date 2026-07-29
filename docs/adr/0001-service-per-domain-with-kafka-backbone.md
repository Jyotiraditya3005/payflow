# ADR 0001: Service-per-domain with a Kafka event backbone

## Status
Accepted

## Context

PayFlow needs to model a payment's lifecycle (creation, fraud check,
settlement, ledger posting, notification) across concerns that scale and
fail independently. A single monolith would couple fraud-model changes to
payment API deploys, and a pure request/response chain across services would
mean a slow or down downstream service (e.g. notifications) could block the
payment response itself.

## Decision

Split by business domain (auth, payment, fraud, transaction, ledger,
notification) with:
- **One synchronous call** on the critical path: payment-service →
  fraud-service, because the caller needs an inline risk decision before
  responding.
- **Everything else asynchronous** via Kafka (`payments.created`,
  `payments.completed`, `payments.failed`, plus a retry/DLQ pair), so
  transaction, ledger, and notification services each consume independently
  without blocking the payment response or each other.

## Consequences

- **Positive**: downstream outages (e.g. notification-service down) don't
  block payment creation; each service can be scaled, deployed, and owned
  independently; Kafka gives a natural retry/DLQ mechanism for transient
  failures.
- **Negative**: eventual consistency between `payments` and
  `transactions`/`ledger` — a client checking the ledger immediately after a
  payment response may see a lag. Requires idempotent consumers and careful
  event-schema discipline (see [KAFKA_EVENTS.md](../KAFKA_EVENTS.md) for the
  topic-naming inconsistency this design already surfaced).
- **Negative**: cross-service debugging needs distributed tracing (Jaeger)
  rather than a single stack trace — instrumentation coverage should be
  verified per service, not assumed.

## Alternatives Considered

- **Monolith**: simpler locally, but couples fraud-model iteration speed to
  the payment API's release cadence — rejected given fraud rules need to
  change independently and often.
- **Fully synchronous service chain**: simpler mental model, but makes the
  payment response latency equal to the slowest downstream step and removes
  the retry/DLQ safety net Kafka provides for free.
