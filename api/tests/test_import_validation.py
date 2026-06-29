"""WP11 import validation service/API tests — MVP staging gate."""

from __future__ import annotations

from collections.abc import Generator
from urllib.parse import urlparse, urlunparse

import pytest
from alembic import command
from alembic.config import Config as AlembicConfig
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from api.config import settings
from api.services.import_validation import get_import_batch, record_import_validation
from db.tests.fixtures_wp11 import INVALID_FIXTURE, VALID_FIXTURE, WARN_FIXTURE


@pytest.fixture(scope="module")
def engine() -> Generator[Engine, None, None]:
    test_db_name = "knowledge_platform_v2_test_wp11_api"
    parsed = urlparse(settings.database_url)
    parsed = parsed._replace(path=test_db_name)
    test_url = urlunparse(parsed)

    admin_url = settings.database_url.replace(f"/{settings.db_name}", "/postgres")
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {test_db_name}"))
        conn.execute(text(f"CREATE DATABASE {test_db_name} OWNER {settings.db_user}"))
    admin_engine.dispose()

    eng = create_engine(test_url, pool_size=1)
    cfg = AlembicConfig("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", test_url)
    command.upgrade(cfg, "head")

    yield eng
    eng.dispose()

    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {test_db_name}"))
    admin_engine.dispose()


def test_valid_fixture_commits_successfully(engine: Engine):
    result = record_import_validation(engine, **VALID_FIXTURE)

    assert result["batch"]["status"] == "committed"
    assert result["batch"]["totalRows"] == 2
    assert result["batch"]["successRows"] == 2
    assert result["batch"]["failedRows"] == 0
    assert result["validationErrors"] == []
    assert result["idempotent"] is False


def test_invalid_fixture_hits_expected_error_codes_and_fails(engine: Engine):
    result = record_import_validation(engine, **INVALID_FIXTURE)

    assert result["batch"]["status"] == "failed"
    assert result["batch"]["failedRows"] == 2
    assert {error["errorCode"] for error in result["validationErrors"]} == {
        "FK_RULE_EVIDENCE",
        "UQ_CERTIFICATE_ALIAS",
    }
    assert {error["severity"] for error in result["validationErrors"]} == {"P0", "P1"}


def test_non_blocking_fixture_keeps_batch_committed_with_review_errors(engine: Engine):
    result = record_import_validation(engine, **WARN_FIXTURE)

    assert result["batch"]["status"] == "committed"
    assert result["batch"]["successRows"] == 1
    assert result["batch"]["failedRows"] == 0
    assert result["validationErrors"][0]["errorCode"] == "NEEDS_BUSINESS_REVIEW"
    assert result["validationErrors"][0]["severity"] == "P2"


def test_same_file_hash_is_idempotent(engine: Engine):
    first = record_import_validation(
        engine,
        filename="valid/idempotent.csv",
        content_sha256="4" * 64,
        imported_by="org_teaching_materials",
        total_rows=1,
        validation_errors=[],
    )
    second = record_import_validation(
        engine,
        filename="valid/idempotent-renamed.csv",
        content_sha256="4" * 64,
        imported_by="org_teaching_materials",
        total_rows=99,
        validation_errors=[
            {
                "row_number": 1,
                "row_key": "SHOULD_NOT_INSERT",
                "field_name": "code",
                "error_code": "SHOULD_NOT_INSERT",
                "error_message": "idempotent retry should return original batch",
                "severity": "P1",
            }
        ],
    )

    assert second["idempotent"] is True
    assert second["batch"]["id"] == first["batch"]["id"]
    assert second["batch"]["filename"] == "valid/idempotent.csv"
    assert second["validationErrors"] == []


def test_get_import_batch_unknown_raises(engine: Engine):
    with pytest.raises(ValueError):
        get_import_batch(engine, batch_id=999999)


def test_api_route_requires_identity_records_valid_invalid_and_gets_batch(engine: Engine, monkeypatch: pytest.MonkeyPatch):
    import api.main as main

    monkeypatch.setattr(main, "sync_engine", engine)

    from fastapi.testclient import TestClient

    client = TestClient(main.app)
    payload = {
        "filename": "invalid/api_duplicate_alias.csv",
        "content_sha256": "5" * 64,
        "total_rows": 1,
        "validation_errors": [
            {
                "row_number": 1,
                "row_key": "一建",
                "field_name": "normalized_alias",
                "error_code": "UQ_CERTIFICATE_ALIAS",
                "error_message": "normalized alias must be unique",
                "severity": "P1",
            }
        ],
    }

    anonymous = client.post("/import-batches/validate", json=payload)
    created = client.post("/import-batches/validate", json=payload, headers={"X-Org-Code": "org_teaching_materials"})
    duplicate = client.post("/import-batches/validate", json=payload, headers={"X-Org-Code": "org_teaching_materials"})
    fetched = client.get(f"/import-batches/{created.json()['batch']['id']}", headers={"X-Org-Code": "org_teaching_materials"})
    unknown = client.get("/import-batches/999999", headers={"X-Org-Code": "org_teaching_materials"})

    assert anonymous.status_code == 401
    assert created.status_code == 200
    assert created.json()["batch"]["status"] == "failed"
    assert created.json()["validationErrors"][0]["errorCode"] == "UQ_CERTIFICATE_ALIAS"
    assert duplicate.status_code == 200
    assert duplicate.json()["idempotent"] is True
    assert fetched.status_code == 200
    assert fetched.json()["batch"]["id"] == created.json()["batch"]["id"]
    assert unknown.status_code == 404
