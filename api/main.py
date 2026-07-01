"""Knowledge Platform V2 鈥?FastAPI application entry point."""

from contextlib import asynccontextmanager
from datetime import date
from typing import Annotated
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from api.auth import AuthorizationError, check_collection_access
from api.config import settings
from api.database import engine, sync_engine
from api.deps import get_current_principal
from api.services.assets import create_download_url, get_minio_client
from api.services.content_products import get_content_product_chapters
from api.services.eligibility import evaluate_eligibility
from api.services.exam_events import get_exam_events
from api.services.generation_audit import get_generation_run_audit
from api.services.generation_workflow import create_generation, get_generation_v2
from api.services.import_validation import get_import_batch, record_import_validation
from api.services.knowledge_points import list_approved_fragments_for_knowledge_point
from api.services.question_bank import get_paper_questions
from api.services.v2_api import (
    evaluate_eligibility_v2,
    get_certificate_detail,
    get_certificate_exam_events_v2,
    list_certificates,
    search_knowledge,
)
from api.services.xhs_content import (
    DEFAULT_CERTIFICATE_CODE,
    XhsContentError,
    generate_xhs_content,
    get_xhs_chapter,
    list_xhs_chapters,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()
    sync_engine.dispose()


app = FastAPI(title="Knowledge Platform V2", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:10086", "http://localhost:10087"],
    allow_origin_regex=(
        r"^http://("
        r"localhost|127\.0\.0\.1|"
        r"10(?:\.\d{1,3}){3}|"
        r"192\.168(?:\.\d{1,3}){2}|"
        r"172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2}"
        r"):(10086|10087)$"
    ),
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-Org-Code"],
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or f"req_{uuid4().hex}"
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


class EligibilityEvaluateRequest(BaseModel):
    certificate_code: str
    as_of: date = Field(default_factory=date.today)
    region_code: str = "CN"
    qualification_level: str | None = None
    degree_level_code: str | None = None
    major_category_code: str | None = None
    education_type_code: str | None = None
    total_work_months: int | None = Field(default=None, ge=0)
    relevant_work_months: int | None = Field(default=None, ge=0)
    admission_date: date | None = None


class ImportValidationErrorPayload(BaseModel):
    row_number: int | None = Field(default=None, ge=1)
    row_key: str
    field_name: str
    error_code: str = Field(pattern=r"^[A-Z0-9_]+$")
    error_message: str
    severity: str = Field(default="P1", pattern=r"^P[0-3]$")


class ImportValidationRequest(BaseModel):
    filename: str
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    total_rows: int = Field(ge=0)
    validation_errors: list[ImportValidationErrorPayload] = Field(default_factory=list)


class V2EligibilityEvaluateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    certificate_code: str = Field(alias="certificateCode")
    as_of: date = Field(default_factory=date.today, alias="asOf")
    region_code: str = Field(default="CN", alias="regionCode")
    qualification_level: str | None = Field(default=None, alias="qualificationLevel")
    degree_level_code: str | None = Field(default=None, alias="degreeLevelCode")
    major_category_code: str | None = Field(default=None, alias="majorCategoryCode")
    education_type_code: str | None = Field(default=None, alias="educationTypeCode")
    total_work_months: int | None = Field(default=None, ge=0, alias="totalWorkMonths")
    relevant_work_months: int | None = Field(default=None, ge=0, alias="relevantWorkMonths")
    admission_date: date | None = Field(default=None, alias="admissionDate")


class V2KnowledgeSearchRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    query: str = ""
    collection_codes: list[str] = Field(default_factory=list, alias="collectionCodes")
    knowledge_point_codes: list[str] = Field(default_factory=list, alias="knowledgePointCodes")
    asset_types: list[str] = Field(default_factory=list, alias="assetTypes")
    top_k: int = Field(default=8, ge=1, le=20, alias="topK")


class V2GenerationRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    application_code: str = Field(default="exam_article", alias="applicationCode")
    output_type: str = Field(default="card_set", alias="outputType")
    certificate_code: str | None = Field(default=None, alias="certificateCode")
    collection_codes: list[str] = Field(default_factory=list, alias="collectionCodes")
    knowledge_point_codes: list[str] = Field(default_factory=list, alias="knowledgePointCodes")
    card_sequence: list[str] = Field(default_factory=list, alias="cardSequence")
    inputs: dict = Field(default_factory=dict)
    idempotency_key: str | None = Field(default=None, alias="idempotencyKey")


class XhsContentGenerateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    source_mode: str = Field(default="database", alias="sourceMode")
    chapter_id: str = Field(default="", alias="chapterId")
    custom_text: str = Field(default="", alias="customText")
    knowledge_keyword: str = Field(default="", alias="knowledgeKeyword")
    angle_type: str = Field(default="错因诊断", alias="angleType")
    target_user: str = Field(default="学了一段但做题总错", alias="targetUser")
    tone: str = "备考陪跑"
    density: str = "短平快"
    cta_type: str = Field(default="收藏+评论卡点", alias="ctaType")
    extra_requirement: str = Field(default="", alias="extraRequirement")


def _v2_error_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    field_errors: list[dict] | None = None,
) -> JSONResponse:
    request_id = getattr(request.state, "request_id", f"req_{uuid4().hex}")
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "fieldErrors": field_errors or [],
                "requestId": request_id,
            }
        },
        headers={"X-Request-ID": request_id},
    )


@app.exception_handler(AuthorizationError)
async def authorization_error_handler(request: Request, exc: AuthorizationError):
    if request.url.path.startswith("/api/v2/"):
        code = "UNAUTHENTICATED" if exc.status_code == 401 else "ACCESS_DENIED"
        return _v2_error_response(request, status_code=exc.status_code, code=code, message=exc.detail)
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if request.url.path.startswith("/api/v2/"):
        code = "NOT_FOUND" if exc.status_code == 404 else "BAD_REQUEST"
        if exc.status_code >= 500:
            code = "INTERNAL_ERROR"
        return _v2_error_response(
            request,
            status_code=exc.status_code,
            code=code,
            message=str(exc.detail),
        )
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_error_handler(request: Request, exc: SQLAlchemyError):
    _ = exc
    if request.url.path.startswith("/api/v2/"):
        return _v2_error_response(
            request,
            status_code=503,
            code="DATABASE_UNAVAILABLE",
            message="Database unavailable",
        )
    return Response(
        content='{"status":"ok","database":"disconnected"}',
        media_type="application/json",
        status_code=503,
    )


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


@app.get("/content-products/{product_code}/chapters")
async def get_content_product_chapter_tree(
    product_code: str,
    principal: Annotated[dict, Depends(get_current_principal)],
    version_no: Annotated[int | None, Query(ge=1)] = None,
):
    try:
        result = get_content_product_chapters(
            sync_engine,
            product_code=product_code,
            principal_type=principal["principal_type"],
            principal_code=principal["principal_code"],
            version_no=version_no,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Content product version not found") from exc
    return {"status": "ok", **result}


@app.get("/papers/{paper_code}/questions")
async def get_paper_question_list(
    paper_code: str,
    principal: Annotated[dict, Depends(get_current_principal)],
):
    try:
        result = get_paper_questions(
            sync_engine,
            paper_code=paper_code,
            principal_type=principal["principal_type"],
            principal_code=principal["principal_code"],
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Paper not found") from exc
    return {"status": "ok", **result}


@app.get("/generation-runs/{run_id}")
async def get_generation_run(
    run_id: int,
    principal: Annotated[dict, Depends(get_current_principal)],
):
    try:
        result = get_generation_run_audit(
            sync_engine,
            run_id=run_id,
            principal_type=principal["principal_type"],
            principal_code=principal["principal_code"],
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Generation run not found") from exc
    return {"status": "ok", **result}


@app.post("/import-batches/validate")
async def post_import_batch_validation(
    payload: ImportValidationRequest,
    principal: Annotated[dict, Depends(get_current_principal)],
):
    result = record_import_validation(
        sync_engine,
        filename=payload.filename,
        content_sha256=payload.content_sha256,
        imported_by=principal["principal_code"],
        total_rows=payload.total_rows,
        validation_errors=[error.model_dump() for error in payload.validation_errors],
    )
    return {"status": "ok", **result}


@app.get("/import-batches/{batch_id}")
async def get_import_batch_status(
    batch_id: int,
    principal: Annotated[dict, Depends(get_current_principal)],
):
    _ = principal
    try:
        result = get_import_batch(sync_engine, batch_id=batch_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Import batch not found") from exc
    return {"status": "ok", **result}


@app.post("/eligibility/evaluate")
async def post_eligibility_evaluate(
    payload: EligibilityEvaluateRequest,
    principal: Annotated[dict, Depends(get_current_principal)],
):
    try:
        result = evaluate_eligibility(
            sync_engine,
            certificate_code=payload.certificate_code,
            principal_type=principal["principal_type"],
            principal_code=principal["principal_code"],
            as_of=payload.as_of,
            region_code=payload.region_code,
            qualification_level=payload.qualification_level,
            degree_level_code=payload.degree_level_code,
            major_category_code=payload.major_category_code,
            education_type_code=payload.education_type_code,
            total_work_months=payload.total_work_months,
            relevant_work_months=payload.relevant_work_months,
            admission_date=payload.admission_date,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Certificate not found") from exc
    return {"status": "ok", **result}


@app.get("/exam-events/{certificate_code}")
async def get_certificate_exam_events(
    certificate_code: str,
    principal: Annotated[dict, Depends(get_current_principal)],
    region_code: str = "CN",
    exam_year: Annotated[int | None, Query(ge=2000, le=2100)] = None,
    as_of: date | None = None,
):
    _ = principal
    try:
        result = get_exam_events(
            sync_engine,
            certificate_code=certificate_code,
            region_code=region_code,
            exam_year=exam_year,
            as_of=as_of,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Certificate not found") from exc
    return {"status": "ok", **result}


@app.get("/api/v2/certificates")
async def v2_list_certificates(
    principal: Annotated[dict, Depends(get_current_principal)],
    query: str | None = None,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
):
    _ = principal
    try:
        return list_certificates(sync_engine, query=query, cursor=cursor, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid cursor") from exc


@app.get("/api/v2/certificates/{certificate_code}")
async def v2_get_certificate(
    certificate_code: str,
    principal: Annotated[dict, Depends(get_current_principal)],
):
    _ = principal
    try:
        return get_certificate_detail(sync_engine, certificate_code=certificate_code)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Certificate not found") from exc


@app.get("/api/v2/certificates/{certificate_code}/exam-events")
async def v2_get_certificate_exam_events(
    certificate_code: str,
    principal: Annotated[dict, Depends(get_current_principal)],
    region_code: str = "CN",
    exam_year: Annotated[int | None, Query(ge=2000, le=2100)] = None,
):
    _ = principal
    try:
        return get_certificate_exam_events_v2(
            sync_engine,
            certificate_code=certificate_code,
            region_code=region_code,
            exam_year=exam_year,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Certificate not found") from exc


@app.post("/api/v2/eligibility/evaluate")
async def v2_post_eligibility_evaluate(
    payload: V2EligibilityEvaluateRequest,
    principal: Annotated[dict, Depends(get_current_principal)],
):
    try:
        return evaluate_eligibility_v2(
            sync_engine,
            certificate_code=payload.certificate_code,
            principal_type=principal["principal_type"],
            principal_code=principal["principal_code"],
            as_of=payload.as_of,
            region_code=payload.region_code,
            qualification_level=payload.qualification_level,
            degree_level_code=payload.degree_level_code,
            major_category_code=payload.major_category_code,
            education_type_code=payload.education_type_code,
            total_work_months=payload.total_work_months,
            relevant_work_months=payload.relevant_work_months,
            admission_date=payload.admission_date,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Certificate not found") from exc


@app.post("/api/v2/knowledge/search")
async def v2_post_knowledge_search(
    payload: V2KnowledgeSearchRequest,
    principal: Annotated[dict, Depends(get_current_principal)],
):
    return search_knowledge(
        sync_engine,
        principal_type=principal["principal_type"],
        principal_code=principal["principal_code"],
        query=payload.query,
        collection_codes=payload.collection_codes,
        knowledge_point_codes=payload.knowledge_point_codes,
        asset_types=payload.asset_types,
        top_k=payload.top_k,
    )


@app.get("/api/xhs-content/chapters")
async def xhs_content_chapters(
    principal: Annotated[dict, Depends(get_current_principal)],
    certificate_code: str = Query(default=DEFAULT_CERTIFICATE_CODE),
    query: str = Query(default=""),
    asset_type: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
):
    return list_xhs_chapters(
        sync_engine,
        principal_type=principal["principal_type"],
        principal_code=principal["principal_code"],
        certificate_code=certificate_code,
        query=query,
        asset_type=asset_type,
        limit=limit,
    )


@app.get("/api/xhs-content/chapters/{chapter_id}")
async def xhs_content_chapter_detail(
    chapter_id: str,
    principal: Annotated[dict, Depends(get_current_principal)],
):
    try:
        return get_xhs_chapter(
            sync_engine,
            principal_type=principal["principal_type"],
            principal_code=principal["principal_code"],
            chapter_id=chapter_id,
        )
    except XhsContentError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc


@app.post("/api/xhs-content/generate")
async def xhs_content_generate(
    payload: XhsContentGenerateRequest,
    principal: Annotated[dict, Depends(get_current_principal)],
):
    return generate_xhs_content(
        sync_engine,
        principal_type=principal["principal_type"],
        principal_code=principal["principal_code"],
        payload=payload.model_dump(),
    )


@app.post("/api/v2/generations")
async def v2_post_generation(
    payload: V2GenerationRequest,
    principal: Annotated[dict, Depends(get_current_principal)],
):
    return create_generation(
        sync_engine,
        principal_type=principal["principal_type"],
        principal_code=principal["principal_code"],
        application_code=payload.application_code,
        output_type=payload.output_type,
        certificate_code=payload.certificate_code,
        collection_codes=payload.collection_codes,
        knowledge_point_codes=payload.knowledge_point_codes,
        inputs=payload.inputs,
        idempotency_key=payload.idempotency_key,
        card_sequence=payload.card_sequence,
    )


@app.get("/api/v2/generations/{run_id}")
async def v2_get_generation(
    run_id: int,
    principal: Annotated[dict, Depends(get_current_principal)],
):
    try:
        return get_generation_v2(
            sync_engine,
            run_id=run_id,
            principal_type=principal["principal_type"],
            principal_code=principal["principal_code"],
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Generation run not found") from exc
