"""Knowledge Platform V2 – FastAPI application entry point."""

import asyncio
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

# On Windows, the default ProactorEventLoop does not support psycopg async.
# Switch to SelectorEventLoop so the async engine can connect to PostgreSQL.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from api.config import settings  # noqa: E402  — placed after event-loop fix

engine = create_async_engine(settings.database_url_async, pool_size=5, max_overflow=10)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()


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
    """Readiness probe – returns 503 when database is unreachable."""
    try:
        async with AsyncSession(engine) as session:
            await session.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception:
        return Response(
            content='{"status":"unhealthy","database":"disconnected"}',
            media_type="application/json",
            status_code=503,
        )
