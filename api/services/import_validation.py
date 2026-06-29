"""Import validation service — WP11 MVP idempotent batch/error recording."""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

BLOCKING_SEVERITIES = {"P0", "P1"}


def record_import_validation(
    engine: Engine,
    *,
    filename: str,
    content_sha256: str,
    imported_by: str,
    total_rows: int,
    validation_errors: list[dict[str, Any]],
) -> dict[str, Any]:
    """Record one import validation result.

    Reusing the same `content_sha256` is idempotent: the original batch and
    validation errors are returned without inserting duplicates.
    """
    with engine.begin() as conn:
        existing = conn.execute(
            text("""
                SELECT id
                  FROM ingestion.import_batch
                 WHERE content_sha256 = :content_sha256
            """),
            {"content_sha256": content_sha256},
        ).fetchone()
        if existing is not None:
            result = get_import_batch(engine, batch_id=existing.id)
            result["idempotent"] = True
            return result

        blocking_errors = [error for error in validation_errors if error["severity"] in BLOCKING_SEVERITIES]
        failed_rows = len({error.get("row_number") or error["row_key"] for error in blocking_errors})
        success_rows = max(total_rows - failed_rows, 0)
        status = "failed" if blocking_errors else "committed"

        batch = conn.execute(
            text("""
                INSERT INTO ingestion.import_batch (
                    filename, content_sha256, imported_by, status,
                    total_rows, success_rows, failed_rows
                )
                VALUES (
                    :filename, :content_sha256, :imported_by, :status,
                    :total_rows, :success_rows, :failed_rows
                )
                RETURNING id
            """),
            {
                "filename": filename,
                "content_sha256": content_sha256,
                "imported_by": imported_by,
                "status": status,
                "total_rows": total_rows,
                "success_rows": success_rows,
                "failed_rows": failed_rows,
            },
        ).fetchone()
        if batch is None:
            raise RuntimeError("import batch insert failed")

        for error in validation_errors:
            conn.execute(
                text("""
                    INSERT INTO ingestion.validation_error (
                        batch_id, row_number, row_key, field_name,
                        error_code, error_message, severity
                    )
                    VALUES (
                        :batch_id, :row_number, :row_key, :field_name,
                        :error_code, :error_message, :severity
                    )
                """),
                {
                    "batch_id": batch.id,
                    "row_number": error.get("row_number"),
                    "row_key": error["row_key"],
                    "field_name": error["field_name"],
                    "error_code": error["error_code"],
                    "error_message": error["error_message"],
                    "severity": error["severity"],
                },
            )

    result = get_import_batch(engine, batch_id=batch.id)
    result["idempotent"] = False
    return result


def get_import_batch(engine: Engine, *, batch_id: int) -> dict[str, Any]:
    """Return one import batch and its validation errors."""
    with engine.connect() as conn:
        batch = conn.execute(
            text("""
                SELECT
                    id,
                    filename,
                    content_sha256,
                    imported_by,
                    status,
                    total_rows,
                    success_rows,
                    failed_rows,
                    imported_at
                  FROM ingestion.import_batch
                 WHERE id = :batch_id
            """),
            {"batch_id": batch_id},
        ).fetchone()
        if batch is None:
            raise ValueError("import batch not found")

        rows = conn.execute(
            text("""
                SELECT
                    id,
                    row_number,
                    row_key,
                    field_name,
                    error_code,
                    error_message,
                    severity
                  FROM ingestion.validation_error
                 WHERE batch_id = :batch_id
                 ORDER BY severity, row_number NULLS LAST, row_key, field_name, error_code
            """),
            {"batch_id": batch_id},
        ).fetchall()

    return {
        "batch": {
            "id": batch.id,
            "filename": batch.filename,
            "contentSha256": batch.content_sha256,
            "importedBy": batch.imported_by,
            "status": batch.status,
            "totalRows": batch.total_rows,
            "successRows": batch.success_rows,
            "failedRows": batch.failed_rows,
            "importedAt": batch.imported_at.isoformat(),
        },
        "validationErrors": [
            {
                "id": row.id,
                "rowNumber": row.row_number,
                "rowKey": row.row_key,
                "fieldName": row.field_name,
                "errorCode": row.error_code,
                "errorMessage": row.error_message,
                "severity": row.severity,
            }
            for row in rows
        ],
    }
