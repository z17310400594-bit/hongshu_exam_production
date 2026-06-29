"""Knowledge Platform V2 – FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from api.config import settings

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
    """Readiness probe – verifies database connectivity."""
    try:
        async with AsyncSession(engine) as session:
            await session.execute(text("SELECT 1"))
            return {"status": "ok", "database": "connected"}
    except Exception:
        return {"status": "unhealthy", "database": "disconnected"}
