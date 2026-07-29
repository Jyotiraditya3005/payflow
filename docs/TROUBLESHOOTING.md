# Troubleshooting

## Stack won't come up / services stuck "unhealthy"

- Run `docker compose ps` — Kafka and Postgres take the longest to become
  healthy (~30-60s). Services with a `depends_on: condition: service_healthy`
  will wait for them.
- Check the specific service: `docker compose logs -f <service-name>`.
- If Kafka never becomes healthy, confirm `zookeeper` came up first —
  `kafka` depends on it in `docker-compose.yml`.

## Port already in use

Something on your machine (often Postgres, Redis, or Grafana if installed
locally) is already bound to a port PayFlow wants. Edit the left-hand side of
the `HOST:CONTAINER` mapping for that service in `docker-compose.yml`.

## Payments stuck in `PENDING` / never reach `COMPLETED`

1. Check `payment-service` logs for the synchronous fraud-service call
   failing — if `fraud-service` is unhealthy, `payment-service` may block or
   error depending on its timeout/fallback config.
2. Confirm the Kafka topic name the producer is publishing to actually
   matches what consumers subscribe to — there's a known singular/plural
   mismatch (`payment.created` vs `payments.created`) documented in
   [KAFKA_EVENTS.md](KAFKA_EVENTS.md). This is the most likely cause of
   "payment says complete but transaction/ledger never updates."
3. Check `docker compose logs -f kafka-ui` or open the Kafka UI at
   http://localhost:9080 to see whether messages are actually landing on the
   topic you expect.

## Idempotency-Key conflicts

A `409`/duplicate error on `POST /payments` usually means the same
`Idempotency-Key` header was reused with a different payload. Generate a
fresh key per logical payment attempt, and only replay the same key when
retrying the exact same request.

## CI `deploy-staging` job fails

This is expected if you haven't manually created the `payflow-staging` EKS
cluster and the underlying Kubernetes `Deployment` objects — see
[DEPLOYMENT.md](DEPLOYMENT.md) for what's actually missing versus what the
workflow assumes.

## Grafana/Prometheus/Jaeger show no data

- Confirm the service you're checking actually exposes a `/metrics` endpoint
  (currently only `payment-service` is confirmed to have one — see
  [API.md](API.md)) and that Prometheus is configured to scrape it
  (`infra/prometheus/`).
- For Jaeger, confirm the service has OpenTelemetry instrumentation wired in;
  don't assume every service exports traces just because Jaeger is running.
