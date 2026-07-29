from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID, uuid4
import structlog
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy import Column, String, Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func
from sqlalchemy import select
from app.db.session import Base, get_db, create_tables

structlog.configure(processors=[structlog.contextvars.merge_contextvars, structlog.processors.add_log_level, structlog.processors.TimeStamper(fmt="iso"), structlog.processors.JSONRenderer()], wrapper_class=structlog.BoundLogger, logger_factory=structlog.PrintLoggerFactory())
logger = structlog.get_logger()

SECRET_KEY = "super-secret-jwt-key-change-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

class User(Base):
    __tablename__ = "users"
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255))
    role = Column(String(50), default="READONLY")
    merchant_id = Column(PGUUID(as_uuid=True))
    is_active = Column(Boolean, default=True)
    api_key = Column(String(255), unique=True, index=True)
    permissions = Column(JSONB, default=list)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_login = Column(DateTime(timezone=True))

class RegisterRequest(BaseModel):
    email: str; password: str; full_name: str; role: str = "READONLY"; merchant_id: Optional[UUID] = None

class LoginRequest(BaseModel):
    email: str; password: str

class TokenResponse(BaseModel):
    access_token: str; refresh_token: str; token_type: str = "bearer"; expires_in: int = ACCESS_TOKEN_EXPIRE_MINUTES * 60; user_id: str; role: str

class UserResponse(BaseModel):
    id: UUID; email: str; full_name: Optional[str]; role: str; merchant_id: Optional[UUID]; is_active: bool; created_at: datetime
    model_config = {"from_attributes": True}

def create_access_token(user_id: str, role: str, merchant_id: Optional[str] = None) -> str:
    return jwt.encode({"sub": user_id, "role": role, "merchant_id": merchant_id, "type": "access", "iat": datetime.now(timezone.utc), "exp": datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)}, SECRET_KEY, algorithm=ALGORITHM)

def create_refresh_token(user_id: str) -> str:
    return jwt.encode({"sub": user_id, "type": "refresh", "exp": datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)}, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError as e:
        raise HTTPException(status_code=401, detail={"error_code": "INVALID_TOKEN", "message": str(e)}, headers={"WWW-Authenticate": "Bearer"})

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), db: AsyncSession = Depends(get_db)) -> User:
    payload = verify_token(credentials.credentials)
    result = await db.execute(select(User).where(User.id == payload.get("sub")))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail={"error_code": "USER_NOT_FOUND"})
    return user

def require_role(*roles: str):
    async def checker(current_user: User = Depends(get_current_user)):
        if current_user.role not in roles:
            raise HTTPException(status_code=403, detail={"error_code": "INSUFFICIENT_PERMISSIONS"})
        return current_user
    return checker

@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_tables(); yield

app = FastAPI(title="PayFlow Auth Service", version="1.0.0", lifespan=lifespan)

@app.post("/api/v1/auth/register", response_model=UserResponse, status_code=201, tags=["Auth"])
async def register(request: RegisterRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == request.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail={"error_code": "EMAIL_EXISTS"})
    user = User(email=request.email, hashed_password=pwd_context.hash(request.password), full_name=request.full_name, role=request.role, merchant_id=request.merchant_id, api_key=f"pk_live_{uuid4().hex[:32]}")
    db.add(user); await db.commit(); await db.refresh(user)
    return UserResponse.model_validate(user)

@app.post("/api/v1/auth/login", response_model=TokenResponse, tags=["Auth"])
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == request.email))
    user = result.scalar_one_or_none()
    if not user or not pwd_context.verify(request.password, user.hashed_password):
        raise HTTPException(status_code=401, detail={"error_code": "INVALID_CREDENTIALS"})
    user.last_login = datetime.now(timezone.utc); await db.commit()
    return TokenResponse(access_token=create_access_token(str(user.id), user.role, str(user.merchant_id) if user.merchant_id else None), refresh_token=create_refresh_token(str(user.id)), user_id=str(user.id), role=user.role)

@app.post("/api/v1/auth/verify", tags=["Auth"])
async def verify_token_endpoint(credentials: HTTPAuthorizationCredentials = Depends(security)):
    payload = verify_token(credentials.credentials)
    return {"valid": True, "user_id": payload.get("sub"), "role": payload.get("role"), "merchant_id": payload.get("merchant_id")}

@app.get("/api/v1/auth/me", response_model=UserResponse, tags=["Auth"])
async def get_me(current_user: User = Depends(get_current_user)):
    return UserResponse.model_validate(current_user)

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "auth-service"}
