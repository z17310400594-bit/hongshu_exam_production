"""Knowledge Platform V2 — FastAPI application entry point."""

from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from api.auth import AuthorizationError, check_collection_access
from api.database import engine, sync_engine
from api.deps import get_current_principal


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
async def get_collection(code: str, principal: Annotated[dict, Depends(get_current_principal)]):
    check_collection_access(
        sync_engine,
        principal_type=principal["principal_type"],
        principal_code=principal["principal_code"],
        collection_code=code,
        required_permission="read",
    )
    return {"status": "ok", "collection": code}
