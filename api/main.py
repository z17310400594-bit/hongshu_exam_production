"""Knowledge Platform V2 — FastAPI application entry point.

On Windows, start via 'python -m api.run'.
"""

from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine

from api.config import settings

engine = create_async_engine(settings.database_url_async, pool_size=5, max_overflow=10)
sync_engine = create_engine(settings.database_url, pool_size=1, pool_pre_ping=True)

from api.auth import AuthorizationError, check_collection_access  # noqa: E402
from api.deps import get_current_principal  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()
    sync_engine.dispose()


app = FastAPI(title="Knowledge Platform V2", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:10086"],
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-Org-Code"],
)


@app.exception_handler(AuthorizationError)
async def authorization_error_handler(request: Request, exc: AuthorizationError):
    """Return 403/401 without leaking collection names, titles, or internal codes."""
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.get("/health/live")
async def health_live():
    return {"status": "ok"}


@app.get("/health/ready")
async def health_ready():
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


@app.get("/collections/{code}")
async def get_collection(
    code: str,
    principal: Annotated[dict, Depends(get_current_principal)],
):
    """Protected endpoint: returns 403 if X-Org-Code lacks ACL read permission."""
    check_collection_access(
        sync_engine,
        principal_type=principal["principal_type"],
        principal_code=principal["principal_code"],
        collection_code=code,
        required_permission="read",
    )
    return {"status": "ok", "collection": code}
