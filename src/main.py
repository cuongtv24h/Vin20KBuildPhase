from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.endpoints.compliance import messages_router
from src.api.endpoints.compliance import router as compliance_router
from src.api.endpoints.policies import router as policies_router
from src.api.pricing_mock import router as pricing_router
from src.api.routes import router
from src.config import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    print(f"Starting {settings.app_name} in {settings.app_env} mode")
    yield
    print("Shutting down...")


app = FastAPI(
    title="PricePolicy AI Agent",
    description="Enterprise PricePolicy AI Agent (BDS020-06)",
    version="1.0.0",
    lifespan=lifespan,
)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")
app.include_router(compliance_router, prefix="/api/v1")
app.include_router(messages_router, prefix="/api/v1")
app.include_router(policies_router, prefix="/api/v1")
app.include_router(pricing_router, prefix="/api/v1/pricing", tags=["Pricing Engine Mock"])


@app.get("/health")
async def health():
    return {"status": "ok", "env": settings.app_env}
