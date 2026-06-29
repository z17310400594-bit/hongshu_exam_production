"""Asset storage service — versioned files, dedupe, ACL-protected presigned URLs."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from io import BytesIO
from typing import Any, Protocol

from minio import Minio
from sqlalchemy import text
from sqlalchemy.engine import Engine

from api.auth import check_collection_access
from api.config import settings

DEFAULT_ALLOWED_USE = ("retrieval",)
RESTRICTED_PREFIX = "restricted-assets"
STANDARD_PREFIX = "assets"


@dataclass(frozen=True)
class UploadResult:
    status: str
    asset_version_id: int
    object_key: str
    content_sha256: str


class ObjectStorage(Protocol):
    def bucket_exists(self, bucket_name: str) -> bool: ...

    def make_bucket(self, bucket_name: str) -> None: ...

    def put_object(
        self,
        bucket_name: str,
        object_name: str,
        data: Any,
        length: int,
        content_type: str = "application/octet-stream",
    ) -> Any: ...

    def presigned_get_object(self, bucket_name: str, object_name: str, expires: timedelta) -> str: ...


def get_minio_client() -> Minio:
    return Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )


def _bucket_exists(client: ObjectStorage, bucket: str) -> bool:
    return client.bucket_exists(bucket)


def _ensure_bucket(client: ObjectStorage, bucket: str) -> None:
    if not _bucket_exists(client, bucket):
        client.make_bucket(bucket)


def _generate_object_key(confidentiality: str, content_sha256: str) -> str:
    prefix = RESTRICTED_PREFIX if confidentiality == "restricted" else STANDARD_PREFIX
    return f"{prefix}/{content_sha256[:2]}/{content_sha256}"


def create_asset(
    engine: Engine,
    *,
    code: str,
    asset_type: str,
    title: str,
    collection_code: str,
    owner_org_code: str,
    confidentiality: str,
    copyright_owner: str | None = None,
    allowed_use: tuple[str, ...] = DEFAULT_ALLOWED_USE,
    status: str = "draft",
) -> dict:
    """Create an asset under an existing collection and owner organization."""
    with engine.begin() as conn:
        row = conn.execute(
            text("""
                WITH refs AS (
                    SELECT c.id AS collection_id, o.id AS owner_org_id
                      FROM knowledge.collection c
                      JOIN iam.organization_unit o ON o.code = :owner_org_code
                     WHERE c.code = :collection_code
                )
                INSERT INTO knowledge.asset (
                    code, asset_type, title, collection_id, owner_org_id,
                    confidentiality, copyright_owner, allowed_use, status
                )
                SELECT :code, :asset_type, :title, collection_id, owner_org_id,
                       :confidentiality, :copyright_owner, :allowed_use, :status
                  FROM refs
                RETURNING id, code, title, confidentiality
            """),
            {
                "code": code,
                "asset_type": asset_type,
                "title": title,
                "collection_code": collection_code,
                "owner_org_code": owner_org_code,
                "confidentiality": confidentiality,
                "copyright_owner": copyright_owner,
                "allowed_use": list(allowed_use),
                "status": status,
            },
        ).fetchone()
    if row is None:
        raise ValueError("asset references must exist")
    return dict(row._mapping)


def create_fragment(
    engine: Engine,
    *,
    asset_code: str,
    version_no: int,
    fragment_code: str,
    fragment_type: str,
    content: str,
    parent_fragment_code: str | None = None,
    sequence_no: int = 0,
    heading: str | None = None,
    page_from: int | None = None,
    page_to: int | None = None,
) -> dict:
    """Create a locatable fragment for one asset version."""
    with engine.begin() as conn:
        row = conn.execute(
            text("""
                WITH version AS (
                    SELECT av.id
                      FROM knowledge.asset_version av
                      JOIN knowledge.asset a ON a.id = av.asset_id
                     WHERE a.code = :asset_code
                       AND av.version_no = :version_no
                ),
                parent AS (
                    SELECT f.id
                      FROM knowledge.fragment f
                      JOIN version v ON v.id = f.asset_version_id
                     WHERE f.fragment_code = :parent_fragment_code
                )
                INSERT INTO knowledge.fragment (
                    asset_version_id, fragment_code, fragment_type, parent_id,
                    sequence_no, heading, content, page_from, page_to
                )
                SELECT v.id, :fragment_code, :fragment_type,
                       CASE WHEN :parent_fragment_code IS NULL THEN NULL ELSE p.id END,
                       :sequence_no, :heading, :content, :page_from, :page_to
                  FROM version v
                  LEFT JOIN parent p ON true
                 WHERE :parent_fragment_code IS NULL OR p.id IS NOT NULL
                RETURNING id, asset_version_id, fragment_code, parent_id, page_from, page_to
            """),
            {
                "asset_code": asset_code,
                "version_no": version_no,
                "fragment_code": fragment_code,
                "fragment_type": fragment_type,
                "parent_fragment_code": parent_fragment_code,
                "sequence_no": sequence_no,
                "heading": heading,
                "content": content,
                "page_from": page_from,
                "page_to": page_to,
            },
        ).fetchone()
    if row is None:
        raise ValueError("asset version or parent fragment not found")
    return dict(row._mapping)


def upload_asset_version(
    engine: Engine,
    *,
    client: ObjectStorage,
    bucket: str,
    asset_code: str,
    version_no: int,
    content: bytes,
    mime_type: str,
    extracted_text: str | None = None,
    review_status: str = "pending",
    reviewed_by: str | None = None,
    object_key_factory: Callable[[str, str], str] = _generate_object_key,
) -> UploadResult:
    """Upload content to MinIO and create an immutable asset version row.

    Object keys are always generated by the service from confidentiality and SHA256;
    callers never provide a path, so path traversal and restricted-prefix injection
    are ignored by construction.
    """
    digest = sha256(content).hexdigest()

    with engine.connect() as conn:
        existing = conn.execute(
            text("""
                SELECT id, object_key, content_sha256
                  FROM knowledge.asset_version
                 WHERE content_sha256 = :digest
            """),
            {"digest": digest},
        ).fetchone()
        if existing is not None:
            return UploadResult("duplicate", existing.id, existing.object_key, existing.content_sha256)

        asset = conn.execute(
            text("""
                SELECT id, confidentiality
                  FROM knowledge.asset
                 WHERE code = :asset_code
            """),
            {"asset_code": asset_code},
        ).fetchone()
        if asset is None:
            raise ValueError("asset not found")

        version_exists = conn.execute(
            text("""
                SELECT 1
                  FROM knowledge.asset_version
                 WHERE asset_id = :asset_id
                   AND version_no = :version_no
            """),
            {"asset_id": asset.id, "version_no": version_no},
        ).fetchone()
        if version_exists is not None:
            raise ValueError("asset version already exists")

    object_key = object_key_factory(asset.confidentiality, digest)
    _ensure_bucket(client, bucket)
    client.put_object(bucket, object_key, BytesIO(content), len(content), content_type=mime_type)
    reviewed_at = datetime.now(UTC) if reviewed_by is not None else None

    with engine.begin() as conn:
        row = conn.execute(
            text("""
                INSERT INTO knowledge.asset_version (
                    asset_id, version_no, object_key, mime_type, extracted_text,
                    content_sha256, review_status, reviewed_by, reviewed_at
                )
                VALUES (
                    :asset_id, :version_no, :object_key, :mime_type, :extracted_text,
                    :digest, :review_status, :reviewed_by, :reviewed_at
                )
                RETURNING id, object_key, content_sha256
            """),
            {
                "asset_id": asset.id,
                "version_no": version_no,
                "object_key": object_key,
                "mime_type": mime_type,
                "extracted_text": extracted_text,
                "digest": digest,
                "review_status": review_status,
                "reviewed_by": reviewed_by,
                "reviewed_at": reviewed_at,
            },
        ).fetchone()
    if row is None:
        raise RuntimeError("asset version insert failed")
    return UploadResult("created", row.id, row.object_key, row.content_sha256)


def create_download_url(
    engine: Engine,
    *,
    client: ObjectStorage,
    bucket: str,
    asset_code: str,
    version_no: int,
    principal_type: str,
    principal_code: str,
    expires_seconds: int = 300,
) -> str:
    """Return a short-lived MinIO URL only after collection ACL succeeds."""
    with engine.connect() as conn:
        row = conn.execute(
            text("""
                SELECT av.object_key, c.code AS collection_code
                  FROM knowledge.asset_version av
                  JOIN knowledge.asset a ON a.id = av.asset_id
                  JOIN knowledge.collection c ON c.id = a.collection_id
                 WHERE a.code = :asset_code
                   AND av.version_no = :version_no
            """),
            {"asset_code": asset_code, "version_no": version_no},
        ).fetchone()
    if row is None or row.object_key is None:
        raise ValueError("asset version not found")

    check_collection_access(
        engine,
        principal_type=principal_type,
        principal_code=principal_code,
        collection_code=row.collection_code,
        required_permission="read",
    )
    return client.presigned_get_object(
        bucket,
        row.object_key,
        expires=timedelta(seconds=expires_seconds),
    )
