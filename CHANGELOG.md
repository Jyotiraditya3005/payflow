# Changelog

All notable changes to PayFlow are documented in this file.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- Project documentation set under `docs/` (architecture, API, database schema,
  Kafka event flows, deployment, troubleshooting, security model, ADRs)
- `LICENSE`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`
- GitHub issue templates and pull request template
- `frontend/package-lock.json` (was missing, breaking `npm ci` in CI)

### Fixed
- CI: `test-payment-service` job now starts the app (`uvicorn`) and waits for
  `/health` before running tests, and adds a Kafka service container —
  previously the test suite called a live server at `localhost:8001` that CI
  never started, and no Kafka broker existed in that job at all

### Changed
- Repository cleanup: removed stray template/brace-expansion directories and
  generated files left over from scaffolding

## [1.0.0] - 2026-05-28

### Added
- Initial release: 8-service architecture (API Gateway, Auth, Payment, Fraud,
  Transaction, Ledger, Notification, Frontend)
- Kafka-based event pipeline with retry and dead-letter queues
- Prometheus + Grafana + Jaeger observability stack
- GitHub Actions CI/CD pipeline
- ML-based fraud scoring (XGBoost + Isolation Forest)
