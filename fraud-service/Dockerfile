FROM python:3.12-slim AS builder
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev g++ && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r requirements.txt

FROM python:3.12-slim AS runtime
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libpq5 curl libgomp1 && rm -rf /var/lib/apt/lists/*
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY app/ ./app/
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/app
VOLUME ["/tmp/payflow_models"]
EXPOSE 8003
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=5 CMD curl -f http://localhost:8003/health || exit 1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8003", "--workers", "2", "--loop", "uvloop"]
