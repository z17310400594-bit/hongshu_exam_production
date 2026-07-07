"""WP11 database constraint tests — import batches and validation errors."""

import pytest
from alembic import command
from alembic.config import Config as AlembicConfig
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError


@pytest.fixture(scope="module", autouse=True)
def _migrate_module(alembic_cfg: AlembicConfig, engine: Engine):
    command.upgrade(alembic_cfg, "head")


def _seed_batch(engine: Engine, *, content_sha256: str = "d" * 64, status: str = "validating") -> int:
    with engine.begin() as conn:
        row = conn.execute(
            text("""
                INSERT INTO ingestion.import_batch (
                    filename, content_sha256, imported_by, status,
                    total_rows, success_rows, failed_rows
                )
                VALUES ('fixture.csv', :content_sha256, 'tester', :status, 2, 2, 0)
                RETURNING id
            """),
            {"content_sha256": content_sha256, "status": status},
        ).fetchone()
    if row is None:
        raise RuntimeError("batch insert failed")
    return row.id


def test_import_batch_constraints_and_idempotency_key(engine: Engine):
    batch_id = _seed_batch(engine, content_sha256="e" * 64)
    assert batch_id > 0

    bad_rows = [
        {"sha": "not-a-sha", "status": "uploaded", "total": 1, "success": 1, "failed": 0},
        {"sha": "f" * 64, "status": "done", "total": 1, "success": 1, "failed": 0},
        {"sha": "1" * 64, "status": "uploaded", "total": -1, "success": 0, "failed": 0},
        {"sha": "2" * 64, "status": "uploaded", "total": 1, "success": 2, "failed": 0},
        {"sha": "e" * 64, "status": "uploaded", "total": 1, "success": 1, "failed": 0},
    ]
    for row in bad_rows:
        with pytest.raises(IntegrityError), engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO ingestion.import_batch (
                        filename, content_sha256, imported_by, status,
                        total_rows, success_rows, failed_rows
                    )
                    VALUES (
                        'bad.csv', :sha, 'tester', :status,
                        :total, :success, :failed
                    )
                """),
                row,
            )


def test_validation_error_constraints_cascade_and_blocking_trigger(engine: Engine):
    batch_id = _seed_batch(engine, content_sha256="3" * 64)
    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO ingestion.validation_error (
                    batch_id, row_number, row_key, field_name,
                    error_code, error_message, severity
                )
                VALUES (
                    :batch_id, 2, 'ROW_2', 'code',
                    'FK_CERTIFICATE', 'certificate missing', 'P1'
                )
            """),
            {"batch_id": batch_id},
        )
        status = conn.execute(
            text("SELECT status FROM ingestion.import_batch WHERE id = :batch_id"),
            {"batch_id": batch_id},
        ).scalar_one()
    assert status == "failed"

    bad_errors = [
        {"batch_id": batch_id, "row_number": 0, "row_key": "R1", "field": "code", "code": "BAD_ROW", "severity": "P1"},
        {"batch_id": batch_id, "row_number": 1, "row_key": "R2", "field": "code", "code": "bad-code", "severity": "P1"},
        {"batch_id": batch_id, "row_number": 1, "row_key": "R3", "field": "code", "code": "BAD_SEVERITY", "severity": "P9"},
        {"batch_id": 999999, "row_number": 1, "row_key": "R4", "field": "code", "code": "BAD_FK", "severity": "P1"},
        {"batch_id": batch_id, "row_number": 2, "row_key": "ROW_2", "field": "code", "code": "FK_CERTIFICATE", "severity": "P1"},
    ]
    for row in bad_errors:
        with pytest.raises(IntegrityError), engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO ingestion.validation_error (
                        batch_id, row_number, row_key, field_name,
                        error_code, error_message, severity
                    )
                    VALUES (
                        :batch_id, :row_number, :row_key, :field,
                        :code, 'bad validation error', :severity
                    )
                """),
                row,
            )

    with engine.begin() as conn:
        conn.execute(text("DELETE FROM ingestion.import_batch WHERE id = :batch_id"), {"batch_id": batch_id})
        count = conn.execute(
            text("SELECT count(*) FROM ingestion.validation_error WHERE batch_id = :batch_id"),
            {"batch_id": batch_id},
        ).scalar_one()
    assert count == 0
