# Contributing to PayFlow

Thanks for your interest in improving PayFlow. This project follows a standard fork-and-PR workflow.

## Getting Started

1. Fork the repo and clone your fork.
2. Copy each service's `.env.example` to `.env` and adjust values as needed.
3. Bring the stack up: `docker compose up -d`
4. Confirm services are healthy: `docker compose ps`

## Development Workflow

1. Create a branch off `develop`: `git checkout -b feature/short-description`
2. Make your changes, keeping each service's existing layering
   (`api/`, `services/`, `models/`, `schemas/`, `core/`, `db/`) intact.
3. Add or update tests alongside any behavior change.
4. Run the relevant service's test suite locally before pushing (see each
   service's `tests/` directory; Python services use `pytest`, the gateway
   uses Maven's `mvn test`).
5. Push and open a PR against `develop`, filling in the PR template.

## Commit Messages

Use [Conventional Commits](https://www.conventionalcommits.org/) style where practical:

```
feat(fraud-service): add velocity-based rule
fix(payment-service): correct idempotency key TTL
docs(readme): update Kafka topic table
```

## Code Style

- **Python services**: format with `black`, lint with `ruff` (or `flake8` if not configured yet).
- **API Gateway (Java)**: follow standard Spring Boot conventions; run `mvn spotless:apply` if configured.
- **Frontend**: `npm run lint` before committing.

## Reporting Bugs / Requesting Features

Please use the issue templates under `.github/ISSUE_TEMPLATE/` so reports include the context needed to reproduce or evaluate them.

## Security Issues

Do not open a public issue for security vulnerabilities — see [SECURITY.md](SECURITY.md).
