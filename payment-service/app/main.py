import time
import uuid
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

from app.core.config import settings
from app.db.session import create_tables
from app.services.kafka_service import kafka_producer
from app.services.redis_service import redis_service
from app.api.payments import router as payments_router

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.BoundLogger,
    logger_factory=structlog.PrintLoggerFactory(),
)
logger = structlog.get_logger()

REQUEST_COUNT = Counter("payflow_http_requests_total", "Total HTTP requests", ["method", "endpoint", "status_code"])
REQUEST_LATENCY = Histogram("payflow_http_request_duration_seconds", "HTTP request latency", ["method", "endpoint"], buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0])

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting PayFlow Payment Service", version=settings.APP_VERSION)
    await redis_service.connect()
    await kafka_producer.start()
    await create_tables()
    logger.info("All connections established")
    yield
    logger.info("Shutting down")
    await kafka_producer.stop()
    await redis_service.disconnect()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Production-grade distributed payment processing service",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.add_middleware(GZipMiddleware, minimum_size=1000)

@app.middleware("http")
async def request_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    start_time = time.perf_counter()
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id=request_id, method=request.method, path=request.url.path)
    response = await call_next(request)
    duration = time.perf_counter() - start_time
    REQUEST_COUNT.labels(method=request.method, endpoint=request.url.path, status_code=response.status_code).inc()
    REQUEST_LATENCY.labels(method=request.method, endpoint=request.url.path).observe(duration)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Response-Time"] = f"{duration:.4f}s"
    logger.info("Request completed", status_code=response.status_code, duration_ms=round(duration * 1000, 2))
    return response

app.include_router(payments_router, prefix=settings.API_V1_PREFIX)

@app.get("/health", tags=["Health"])
async def health_check():
    checks = {}
    try:
        await redis_service.client.ping()
        checks["redis"] = "healthy"
    except Exception:
        checks["redis"] = "unhealthy"
    checks["kafka"] = "healthy" if kafka_producer._producer else "not_started"
    overall = "healthy" if all(v == "healthy" for v in checks.values()) else "degraded"
    return {"status": overall, "service": settings.APP_NAME, "version": settings.APP_VERSION, "checks": checks}

@app.get("/metrics", tags=["Observability"])
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.get("/")
async def root():
    return {"service": settings.APP_NAME, "version": settings.APP_VERSION, "docs": "/docs"}
