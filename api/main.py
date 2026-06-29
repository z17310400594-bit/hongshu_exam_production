"""Knowledge Platform V2 — FastAPI application entry point."""

from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from api.auth import AuthorizationError, check_collection_access
from api.config import settings
from api.database import engine, sync_engine
from api.deps import get_current_principal
from api.services.assets import create_download_url, get_minio_client
from api.services.knowledge_points import list_approved_fragments_for_knowledge_point


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


@app.get("/assets/{code}/versions/{version_no}/download-url")
async def get_asset_version_download_url(
    code: str,
    version_no: int,
    principal: Annotated[dict, Depends(get_current_principal)],
):
    try:
        url = create_download_url(
            sync_engine,
            client=get_minio_client(),
            bucket=settings.minio_bucket,
            asset_code=code,
            version_no=version_no,
            principal_type=principal["principal_type"],
            principal_code=principal["principal_code"],
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Asset version not found") from exc
    return {"status": "ok", "downloadUrl": url, "expiresInSeconds": 300}


@app.get("/knowledge-points/{code}/fragments")
async def get_knowledge_point_fragments(
    code: str,
    principal: Annotated[dict, Depends(get_current_principal)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
):
    try:
        result = list_approved_fragments_for_knowledge_point(
            sync_engine,
            kp_code=code,
            principal_type=principal["principal_type"],
            principal_code=principal["principal_code"],
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Knowledge point not found") from exc
    return {"status": "ok", **result}
