# API Reference

Every FastAPI service also exposes interactive Swagger/OpenAPI docs at
`/docs` and a raw schema at `/openapi.json` once running (see README "Access"
table for ports). This file is a quick-reference map of what exists today.

## Auth Service (`:8000`, prefix `/api/v1/auth`)

| Method | Path | Purpose |
|---|---|---|
| POST | `/register` | Create a new user/merchant account |
| POST | `/login` | Exchange credentials for a JWT |
| POST | `/verify` | Verify a token / email verification step |
| GET | `/me` | Return the authenticated user's profile |
| GET | `/health` | Liveness/readiness probe |

## Payment Service (`:8001`, prefix `/api/v1/payments`)

| Method | Path | Purpose |
|---|---|---|
| POST | `/` | Initiate a payment (idempotency key required) |
| GET | `/{payment_id}` | Fetch a single payment |
| GET | `/` | List payments (filterable) |
| POST | `/{payment_id}/refund` | Issue a full or partial refund |
| GET | `/summary` | Aggregate payment summary |
| POST | `/{payment_id}/cancel` | Cancel a pending payment |
| GET | `/health`, `/metrics` | Health check and Prometheus metrics |

## Fraud Service (`:8003`, prefix `/api/v1/fraud`)

| Method | Path | Purpose |
|---|---|---|
| POST | `/check` | Run a synchronous fraud check for a payment |
| GET | `/cases` | List flagged fraud cases |
| POST | `/blacklist/ip` | Add an IP to the blacklist |
| POST | `/blacklist/customer` | Add a customer to the blacklist |
| GET | `/health` | Health check |

## Transaction Service (`:8004`, prefix `/api/v1/transactions`)

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | List transactions |
| GET | `/{payment_id}` | Transaction detail for a payment |
| GET | `/health` | Health check |

## Ledger Service (`:8005`, prefix `/api/v1/ledger`)

| Method | Path | Purpose |
|---|---|---|
| GET | `/{payment_id}` | Ledger entries for a payment |
| GET | `/account/{account_id}` | Ledger entries for an account |
| GET | `/health` | Health check |

## Notification Service (`:8006`, prefix `/api/v1/webhooks`)

| Method | Path | Purpose |
|---|---|---|
| POST | `/register` | Register a merchant webhook endpoint |
| GET | `/` | List registered webhooks |
| GET | `/health` | Health check |

## Auth Flow

1. `POST /api/v1/auth/register` creates the account.
2. `POST /api/v1/auth/login` returns a JWT.
3. The JWT is sent as `Authorization: Bearer <token>` on every subsequent
   request through the API Gateway, which validates it before routing.

## Notes for API consumers

- All money fields are decimal strings (not floats) to avoid rounding errors.
- Every payment-initiating request should send a client-generated
  `Idempotency-Key` header — retries with the same key return the original
  result instead of creating a duplicate payment.
