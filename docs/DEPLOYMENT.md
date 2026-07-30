# Deployment Guide

## Local (current, supported today)

```bash
git clone https://github.com/<your-username>/payflow.git
cd payflow
cp .env.example .env   # repeat per-service if you need different values
docker compose up -d
docker compose ps      # wait until all services report healthy (~60s)
```

Tear down with `docker compose down -v` (the `-v` also drops named volumes
like Postgres/Kafka data — omit it to keep data between runs).

### Common local overrides

- Ports are set per-service in `docker-compose.yml`; change the left side of
  a `HOST:CONTAINER` mapping if something on your machine already uses that
  port.
- Each service reads its own `.env` (see each service's `.env.example`) —
  secrets are never hardcoded into the compose file itself.

## Path to Cloud Deployment (not yet implemented — roadmap)

`.github/workflows/ci-cd.yml`'s `deploy-staging` job runs `kubectl set image`
/ `kubectl rollout status` against an EKS cluster named `payflow-staging`,
assuming Kubernetes `Deployment` objects (`payment-service`, `fraud-service`,
`auth-service`) already exist in a `payflow` namespace. **None of that
infrastructure exists yet** — no Kubernetes manifests, no Terraform, no EKS
cluster, no `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` repo secrets.

The job is now gated on those AWS secrets actually being set
(`secrets.AWS_ACCESS_KEY_ID != ''`). Without them, a separate
`deploy-staging-not-configured` job runs instead and prints a clear notice —
so the pipeline shows an honest "not configured" rather than a red X on
every push. Once the infrastructure below actually exists and the secrets
are added, the real `deploy-staging` job takes over automatically.

To take this to a real, reproducible cloud target:

1. **Containers → Registry**: push built images to GHCR/ECR (CI already
   builds them; add a push + tag-by-SHA step).
2. **Orchestration**: introduce Kubernetes manifests or Helm charts per
   service (Deployment, Service, Ingress, ConfigMap, Secret) — none exist
   yet in this repo.
3. **Infra as Code**: Terraform for the VPC, RDS (Postgres), ElastiCache
   (Redis), MSK (Kafka), and the EKS/ECS cluster itself.
4. **Secrets**: move from `.env` files to a managed secrets store (AWS
   Secrets Manager / SSM Parameter Store) referenced by the deployment
   manifests.
5. **CD**: extend the existing GitHub Actions workflow with a deploy job
   gated on the test jobs passing, targeting the environment from step 2.

Treat this section as a checklist, not a claim — nothing under it is wired
up yet, so don't describe the project as "deployed to AWS EKS" until it is.

## Observability Endpoints (local)

| Tool | URL |
|---|---|
| Grafana | http://localhost:3001 |
| Prometheus | http://localhost:9090 |
| Jaeger | http://localhost:16686 |
| Kafka UI | http://localhost:9080 |
