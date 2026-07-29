from contextlib import asynccontextmanager
import structlog
from fastapi import FastAPI, Depends, HTTPException, Header, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db, create_tables
from app.schemas.fraud import FraudCheckRequest, FraudCheckResponse, FraudCaseResponse
from app.services.fraud_engine import fraud_engine
from app.services.redis_service import redis_service

structlog.configure(
    processors=[structlog.contextvars.merge_contextvars, structlog.processors.add_log_level, structlog.processors.TimeStamper(fmt="iso"), structlog.processors.JSONRenderer()],
    wrapper_class=structlog.BoundLogger, logger_factory=structlog.PrintLoggerFactory(),
)
logger = structlog.get_logger()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting PayFlow Fraud Detection Service")
    await redis_service.connect()
    await create_tables()
    await fraud_engine.ml_scorer.initialize()
    logger.info("Fraud models loaded, service ready")
    yield
    await redis_service.disconnect()

app = FastAPI(title="PayFlow Fraud Detection Service", version="1.0.0", lifespan=lifespan)

def verify_internal(x_internal_service: str = Header(None)):
    if not x_internal_service:
        raise HTTPException(status_code=403, detail="Internal service header required")
    return x_internal_service

@app.post("/api/v1/fraud/check", response_model=FraudCheckResponse, tags=["Fraud Detection"])
async def check_fraud(request: FraudCheckRequest, db: AsyncSession = Depends(get_db), _: str = Depends(verify_internal)):
    return await fraud_engine.check(request, db)

@app.get("/api/v1/fraud/cases", tags=["Cases"])
async def list_fraud_cases(risk_level: str = None, case_status: str = "OPEN", page: int = 1, page_size: int = 20, db: AsyncSession = Depends(get_db)):
    from sqlalchemy import select
    from app.models.fraud import FraudCase
    query = select(FraudCase)
    if risk_level:
        query = query.where(FraudCase.risk_level == risk_level)
    if case_status:
        query = query.where(FraudCase.status == case_status)
    result = await db.execute(query.order_by(FraudCase.created_at.desc()).offset((page-1)*page_size).limit(page_size))
    return [FraudCaseResponse.model_validate(c) for c in result.scalars().all()]

@app.post("/api/v1/fraud/blacklist/ip", tags=["Blacklists"])
async def blacklist_ip(ip_address: str):
    await redis_service.client.sadd("blacklist:ips", ip_address)
    return {"message": f"IP {ip_address} blacklisted"}

@app.post("/api/v1/fraud/blacklist/customer", tags=["Blacklists"])
async def blacklist_customer(customer_id: str):
    await redis_service.client.sadd("blacklist:customers", customer_id)
    return {"message": f"Customer {customer_id} blacklisted"}

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "fraud-service", "ml_models_loaded": fraud_engine.ml_scorer._loaded}
