# Security Model

## Authentication & Authorization

- `auth-service` issues JWTs on login; all other traffic goes through
  `api-gateway`, which validates the token in
  `AuthenticationFilter` (`api-gateway/src/main/java/com/payflow/gateway/filter/AuthenticationFilter.java`)
  before routing to a downstream service.
- Role-based access control is planned per the roadmap (Admin Panel,
  Permission Matrix) but full RBAC enforcement should be verified against
  current code rather than assumed — audit `auth-service` before advertising
  it as complete.

## Secrets

- Every service reads config from its own `.env` file (`.env.example`
  committed, real `.env` gitignored) — no secrets are hardcoded in
  `docker-compose.yml` or source.
- For any deployment beyond local Docker Compose, move secrets to a managed
  store (AWS Secrets Manager / SSM Parameter Store, or Kubernetes `Secret`
  objects sourced from one) rather than shipping `.env` files to servers.

## Data Handling

- Money fields use `numeric` types end-to-end (see
  [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md)) to avoid floating-point rounding
  errors that could misstate balances.
- `payment_events` is an append-only audit trail of every status
  transition — useful for reconciliation and incident review.

## Known Gaps (be upfront about these — don't claim otherwise in interviews)

- No formal third-party security audit or penetration test has been done.
- No Web Application Firewall / CSP / rate-limit tuning has been verified in
  code beyond whatever the gateway filter currently implements — confirm
  before claiming "rate limiting" as a completed feature rather than a
  roadmap item.
- No dependency/SAST scanning is wired into CI yet (`ci-cd.yml` currently
  runs tests and builds/pushes images — no Trivy/Snyk/CodeQL step).
- No secrets manager integration — `.env`-based config only.

Being explicit about what's implemented vs. planned is more credible to an
interviewer than a README that implies everything is finished.
