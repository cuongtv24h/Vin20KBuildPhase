import logging
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from src.agents.pre_sales.graph import PreSalesSessionRunner
from src.api.pricing_mock import router as pricing_router
from src.api.routes import router
from src.config import get_settings
from src.contracts.errors import DomainError, current_correlation_id
from src.orchestrator.checkpointer import CheckpointManager, configure_app_checkpointer

logger = logging.getLogger(__name__)


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """
    Middleware injecting and propagating correlation_id (M-02) across request lifecycle.
    Reads X-Correlation-ID / X-Request-ID or generates a fresh UUID.
    """

    async def dispatch(self, request: Request, call_next):
        cid = (
            request.headers.get("X-Correlation-ID")
            or request.headers.get("X-Request-ID")
            or f"trace-{uuid4().hex[:12]}"
        )
        token = current_correlation_id.set(cid)
        try:
            response: Response = await call_next(request)
            response.headers["X-Correlation-ID"] = cid
            response.headers["X-Request-ID"] = cid
            return response
        finally:
            current_correlation_id.reset(token)


async def _bootstrap_database() -> None:
    """Tạo schema khi DB chưa có bảng nào (idempotent, không đè schema có sẵn).

    - SQLite dev: tạo file ./data/app.db với toàn bộ bảng của Base.metadata.
    - Postgres/Supabase đã có DDL: bỏ qua hoàn toàn (count > 0), không alter.
    """

    from src.db import models  # noqa: F401 — import để đăng ký mọi model vào Base.metadata
    from src.db.session import Base, engine

    async with engine.begin() as conn:
        # Base.metadata.create_all(checkfirst=True) tự động chỉ tạo bảng chưa tồn tại (idempotent)
        await conn.run_sync(Base.metadata.create_all)



@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    print(f"Starting {settings.app_name} in {settings.app_env} mode")

    manager: CheckpointManager | None = None
    if settings.use_postgres_checkpointer and settings.checkpoint_db_uri:
        # INV-RT-04: persistent checkpointing qua AsyncPostgresSaver (Spike 2).
        manager = CheckpointManager(db_uri=settings.checkpoint_db_uri)
        await manager.initialize()
        saver = manager.get_async_postgres_checkpointer()
        configure_app_checkpointer(saver)
        app.state.checkpointer = saver
        app.state.checkpoint_manager = manager
        print("Checkpointing: AsyncPostgresSaver (persistent) enabled")
    elif settings.checkpoint_db_uri and not settings.use_postgres_checkpointer:
        logger.warning(
            "CHECKPOINT_DB_URI is configured but USE_POSTGRES_CHECKPOINTER is false. "
            "Persistent checkpointing is DISABLED. Operating with in-memory MemorySaver."
        )
        print("Checkpointing: MemorySaver (in-memory) — dùng cho dev/test offline")
    else:
        if settings.app_env == "production":
            print(
                "WARNING [INV-RT-04]: production đang chạy MemorySaver in-memory — "
                "đặt USE_POSTGRES_CHECKPOINTER=true và CHECKPOINT_DB_URI để bật persistence."
            )
        print("Checkpointing: MemorySaver (in-memory) — dùng cho dev/test offline")

    # Initialize shared pre-sales runner on app state for multi-process safety (L-01)
    app.state.pre_sales_runner = PreSalesSessionRunner(
        checkpointer=getattr(app.state, "checkpointer", None)
    )

    await _bootstrap_database()

    yield

    if manager is not None:
        await manager.close()
    print("Shutting down...")


app = FastAPI(
    title="PricePolicy AI Agent",
    description="Enterprise PricePolicy AI Agent (BDS020-06)",
    version="1.0.0",
    lifespan=lifespan,
)

settings = get_settings()
app.add_middleware(CorrelationIdMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Idempotent-Replayed", "X-Action", "X-Correlation-ID", "Content-Disposition"],
)


@app.exception_handler(DomainError)
async def domain_error_exception_handler(request: Request, exc: DomainError):
    return JSONResponse(
        status_code=exc.http_status if exc.http_status >= 400 else 400,
        content={"detail": exc.to_envelope().model_dump()},
    )


app.include_router(router)
app.include_router(pricing_router, prefix="/api/v1/pricing", tags=["Pricing Engine Mock"])


@app.get("/health")
@app.get("/api/v1/health")
async def health():
    return {"status": "ok", "env": settings.app_env}

