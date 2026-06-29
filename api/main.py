"""Knowledge Platform V2 – FastAPI application entry point.

On Windows, start via 'python -m api.run' (not 'uvicorn api.main:app') so the
event-loop policy is set before the async engine is created.  See api/run.py.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine

from api.config import settings

engine = create_async_engine(settings.database_url_async, pool_size=5, max_overflow=10)
# Synchronous engine for /health/ready — no event-loop dependency
sync_engine = create_engine(settings.database_url, pool_size=1, pool_pre_ping=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()
    sync_engine.dispose()


app = FastAPI(title="Knowledge Platform V2", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:10086"],  # Taro dev server
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)


@app.get("/health/live")
async def health_live():
    """Liveness probe – no database dependency."""
    return {"status": "ok"}


@app.get("/health/ready")
async def health_ready():
    """Readiness probe — uses synchronous engine to avoid Windows event-loop issues."""
    try:
        with sync_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception:
        return Response(
            content='{"status":"ok","database":"disconnected"}',
            media_type="application/json",
            status_code=503,
        )
