"""WP04 asset service tests — MinIO, dedupe, permissions, fragments."""

from __future__ import annotations

import socket
import subprocess
import time
import warnings
from collections.abc import Generator
from typing import Any
from urllib.parse import urlparse, urlunparse

import pytest
from alembic import command
from alembic.config import Config as AlembicConfig
from minio import Minio
from minio.deleteobjects import DeleteObject
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from api.auth import AuthorizationError
from api.config import settings
from api.services.assets import (
    create_asset,
    create_download_url,
    create_fragment,
    upload_asset_version,
)
from db.tests.fixtures_wp02 import seed_fixtures as seed_wp02

TEST_MINIO_CONTAINER = "v2-minio-wp04-test"
TEST_MINIO_ENDPOINT = "localhost:9100"
TEST_MINIO_ACCESS_KEY = "minioadmin"
TEST_MINIO_SECRET_KEY = "wp04test123"
TEST_MINIO_IMAGE = "minio/minio:RELEASE.2024-11-07T00-52-20Z"


class FakeMinio:
    def __init__(self, *, fail_put: bool = False):
        self.fail_put = fail_put
        self.puts: list[tuple[str, str]] = []
        self.presigned: list[tuple[str, str, object]] = []
        self.buckets: set[str] = set()

    def bucket_exists(self, bucket_name: str) -> bool:
        return bucket_name in self.buckets

    def make_bucket(self, bucket_name: str) -> None:
        self.buckets.add(bucket_name)

    def put_object(self, bucket_name: str, object_name: str, data, length: int, content_type: str = "application/octet-stream"):
        if self.fail_put:
            raise RuntimeError("minio unavailable")
        self.puts.append((bucket_name, object_name))
        data.read(length)

    def presigned_get_object(self, bucket_name: str, object_name: str, expires):
        self.presigned.append((bucket_name, object_name, expires))
        return f"http://minio.local/{bucket_name}/{object_name}?X-Amz-Expires={int(expires.total_seconds())}"


@pytest.fixture(scope="module")
def engine() -> Generator[Engine, None, None]:
    parsed = urlparse(settings.database_url)
    parsed = parsed._replace(path="knowledge_platform_v2_test")
    test_url = urlunparse(parsed)

    admin_url = settings.database_url.replace(f"/{settings.db_name}", "/postgres")
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        conn.execute(text("DROP DATABASE IF EXISTS knowledge_platform_v2_test"))
        conn.execute(text(f"CREATE DATABASE knowledge_platform_v2_test OWNER {settings.db_user}"))
    admin_engine.dispose()

    eng = create_engine(test_url, pool_size=1)
    cfg = AlembicConfig("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", test_url)
    command.upgrade(cfg, "head")
    seed_wp02(eng)

    yield eng
    eng.dispose()

    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        conn.execute(text("DROP DATABASE IF EXISTS knowledge_platform_v2_test"))
    admin_engine.dispose()


@pytest.fixture
def fake_minio() -> FakeMinio:
    return FakeMinio()


def _is_test_minio_port_open() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", 9100), timeout=0.5):
            return True
    except OSError:
        return False


def _ensure_test_minio_container() -> bool:
    """Start an isolated, non-persistent MinIO container if port 9100 is closed."""
    if _is_test_minio_port_open():
        return False
    subprocess.run(["docker", "rm", "-f", TEST_MINIO_CONTAINER], check=False, capture_output=True, text=True)
    subprocess.run(
        [
            "docker",
            "run",
            "-d",
            "--rm",
            "--name",
            TEST_MINIO_CONTAINER,
            "-p",
            "9100:9000",
            "-e",
            f"MINIO_ROOT_USER={TEST_MINIO_ACCESS_KEY}",
            "-e",
            f"MINIO_ROOT_PASSWORD={TEST_MINIO_SECRET_KEY}",
            TEST_MINIO_IMAGE,
            "server",
            "/data",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    for _ in range(30):
        if _is_test_minio_port_open():
            return True
        time.sleep(0.5)
    raise RuntimeError("WP04 MinIO test container did not become ready")


@pytest.fixture(scope="module")
def real_minio_bucket() -> Generator[tuple[Any, str], None, None]:
    started_container = _ensure_test_minio_container()
    client = Minio(
        TEST_MINIO_ENDPOINT,
        access_key=TEST_MINIO_ACCESS_KEY,
        secret_key=TEST_MINIO_SECRET_KEY,
        secure=False,
    )
    bucket = "knowledge-assets-test-wp04"
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)
    try:
        yield client, bucket
    finally:
        object_names = [obj.object_name for obj in client.list_objects(bucket, recursive=True) if obj.object_name]
        objects = [DeleteObject(object_name) for object_name in object_names]
        if objects:
            list(client.remove_objects(bucket, objects))
        if client.bucket_exists(bucket):
            client.remove_bucket(bucket)
        if started_container:
            subprocess.run(["docker", "rm", "-f", TEST_MINIO_CONTAINER], check=False, capture_output=True, text=True)


def test_upload_creates_two_versions_and_generated_standard_keys(engine: Engine, fake_minio: FakeMinio):
    create_asset(
        engine,
        code="WP04_TEXTBOOK",
        asset_type="textbook",
        title="2026 textbook",
        collection_code="coll_internal",
        owner_org_code="org_teaching_materials",
        confidentiality="internal",
        status="published",
    )

    v1 = upload_asset_version(
        engine,
        client=fake_minio,
        bucket="bucket",
        asset_code="WP04_TEXTBOOK",
        version_no=1,
        content=b"version one",
        mime_type="text/plain",
        extracted_text="parse placeholder v1",
        review_status="approved",
        reviewed_by="reviewer_01",
    )
    v2 = upload_asset_version(
        engine,
        client=fake_minio,
        bucket="bucket",
        asset_code="WP04_TEXTBOOK",
        version_no=2,
        content=b"version two",
        mime_type="text/plain",
    )

    assert v1.status == "created"
    assert v2.status == "created"
    assert v1.object_key.startswith("assets/")
    assert v2.object_key.startswith("assets/")
    assert not v1.object_key.startswith("restricted-assets/")
    assert len(fake_minio.puts) == 2


def test_restricted_assets_use_separate_prefix_without_title_leak(engine: Engine, fake_minio: FakeMinio):
    create_asset(
        engine,
        code="WP04_PRIVATE_NOTE",
        asset_type="private",
        title="教辅部内部授课经验",
        collection_code="coll_restricted",
        owner_org_code="org_teaching_aids",
        confidentiality="restricted",
        status="reviewed",
    )

    result = upload_asset_version(
        engine,
        client=fake_minio,
        bucket="bucket",
        asset_code="WP04_PRIVATE_NOTE",
        version_no=1,
        content=b"private note",
        mime_type="application/octet-stream",
    )

    assert result.object_key.startswith("restricted-assets/")
    assert "教辅" not in result.object_key
    assert ".." not in result.object_key


def test_duplicate_sha_returns_existing_version_without_second_upload(engine: Engine, fake_minio: FakeMinio):
    create_asset(
        engine,
        code="WP04_DUP_A",
        asset_type="manual",
        title="Duplicate A",
        collection_code="coll_public",
        owner_org_code="org_teaching_materials",
        confidentiality="public",
    )
    create_asset(
        engine,
        code="WP04_DUP_B",
        asset_type="manual",
        title="Duplicate B",
        collection_code="coll_public",
        owner_org_code="org_teaching_materials",
        confidentiality="public",
    )

    first = upload_asset_version(
        engine,
        client=fake_minio,
        bucket="bucket",
        asset_code="WP04_DUP_A",
        version_no=1,
        content=b"same content",
        mime_type="text/plain",
    )
    second = upload_asset_version(
        engine,
        client=fake_minio,
        bucket="bucket",
        asset_code="WP04_DUP_B",
        version_no=1,
        content=b"same content",
        mime_type="text/plain",
    )

    assert first.status == "created"
    assert second.status == "duplicate"
    assert second.asset_version_id == first.asset_version_id
    assert len(fake_minio.puts) == 1


def test_minio_failure_leaves_no_asset_version_row(engine: Engine):
    create_asset(
        engine,
        code="WP04_MINIO_FAIL",
        asset_type="manual",
        title="MinIO Fail",
        collection_code="coll_public",
        owner_org_code="org_teaching_materials",
        confidentiality="public",
    )

    with pytest.raises(RuntimeError):
        upload_asset_version(
            engine,
            client=FakeMinio(fail_put=True),
            bucket="bucket",
            asset_code="WP04_MINIO_FAIL",
            version_no=1,
            content=b"will fail",
            mime_type="text/plain",
        )

    with engine.connect() as conn:
        count = conn.execute(
            text("""
                SELECT count(*)
                  FROM knowledge.asset_version av
                  JOIN knowledge.asset a ON a.id = av.asset_id
                 WHERE a.code = 'WP04_MINIO_FAIL'
            """)
        ).scalar_one()
    assert count == 0


def test_download_url_requires_acl_before_presign(engine: Engine, fake_minio: FakeMinio):
    create_asset(
        engine,
        code="WP04_DOWNLOAD",
        asset_type="policy",
        title="Download Policy",
        collection_code="coll_internal",
        owner_org_code="org_teaching_materials",
        confidentiality="internal",
    )
    upload_asset_version(
        engine,
        client=fake_minio,
        bucket="bucket",
        asset_code="WP04_DOWNLOAD",
        version_no=1,
        content=b"download body",
        mime_type="text/plain",
    )

    url = create_download_url(
        engine,
        client=fake_minio,
        bucket="bucket",
        asset_code="WP04_DOWNLOAD",
        version_no=1,
        principal_type="org",
        principal_code="org_teaching_materials",
    )
    assert "X-Amz-Expires=300" in url
    assert len(fake_minio.presigned) == 1

    with pytest.raises(AuthorizationError) as exc:
        create_download_url(
            engine,
            client=fake_minio,
            bucket="bucket",
            asset_code="WP04_DOWNLOAD",
            version_no=1,
            principal_type="org",
            principal_code="org_operations",
        )
    assert exc.value.detail == "Access denied"
    assert len(fake_minio.presigned) == 1


def test_download_url_route_denies_anonymous_and_unauthorized_without_presign(engine: Engine, monkeypatch: pytest.MonkeyPatch):
    import api.main as main

    fake = FakeMinio()
    create_asset(
        engine,
        code="WP04_ROUTE",
        asset_type="policy",
        title="Restricted Route Title",
        collection_code="coll_internal",
        owner_org_code="org_teaching_materials",
        confidentiality="internal",
    )
    upload_asset_version(
        engine,
        client=fake,
        bucket="bucket",
        asset_code="WP04_ROUTE",
        version_no=1,
        content=b"route body",
        mime_type="text/plain",
    )

    monkeypatch.setattr(main, "sync_engine", engine)
    monkeypatch.setattr(main, "get_minio_client", lambda: fake)
    monkeypatch.setattr(main.settings, "minio_bucket", "bucket")

    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="Using `httpx` with `starlette.testclient` is deprecated")
        from fastapi.testclient import TestClient

        client = TestClient(main.app)
    anonymous = client.get("/assets/WP04_ROUTE/versions/1/download-url")
    denied = client.get(
        "/assets/WP04_ROUTE/versions/1/download-url",
        headers={"X-Org-Code": "org_operations"},
    )
    allowed = client.get(
        "/assets/WP04_ROUTE/versions/1/download-url",
        headers={"X-Org-Code": "org_teaching_materials"},
    )

    assert anonymous.status_code == 401
    assert "Restricted Route Title" not in anonymous.text
    assert denied.status_code == 403
    assert "Restricted Route Title" not in denied.text
    assert allowed.status_code == 200
    assert len(fake.presigned) == 1


def test_fragment_locates_version_parent_sequence_and_pages(engine: Engine, fake_minio: FakeMinio):
    create_asset(
        engine,
        code="WP04_FRAGMENT",
        asset_type="textbook",
        title="Fragment Textbook",
        collection_code="coll_internal",
        owner_org_code="org_teaching_materials",
        confidentiality="internal",
    )
    upload_asset_version(
        engine,
        client=fake_minio,
        bucket="bucket",
        asset_code="WP04_FRAGMENT",
        version_no=1,
        content=b"fragment body",
        mime_type="text/plain",
    )

    parent = create_fragment(
        engine,
        asset_code="WP04_FRAGMENT",
        version_no=1,
        fragment_code="CH03",
        fragment_type="chapter",
        sequence_no=3,
        heading="第三章",
        content="本章介绍法律职业资格考试报考制度。",
        page_from=40,
        page_to=68,
    )
    child = create_fragment(
        engine,
        asset_code="WP04_FRAGMENT",
        version_no=1,
        fragment_code="CH03_SEC02",
        fragment_type="section",
        parent_fragment_code="CH03",
        sequence_no=2,
        heading="报考条件",
        content="非法学本科人员需结合入学时间和法律工作经历判断。",
        page_from=45,
        page_to=48,
    )

    assert child["asset_version_id"] == parent["asset_version_id"]
    assert child["parent_id"] == parent["id"]
    assert child["page_from"] == 45
    assert child["page_to"] == 48

    with pytest.raises(ValueError):
        create_fragment(
            engine,
            asset_code="WP04_FRAGMENT",
            version_no=1,
            fragment_code="ORPHAN_PARENT",
            fragment_type="section",
            parent_fragment_code="MISSING",
            content="x",
        )


def test_upload_uses_real_minio_test_bucket(engine: Engine, real_minio_bucket: tuple[object, str]):
    client, bucket = real_minio_bucket
    create_asset(
        engine,
        code="WP04_REAL_MINIO",
        asset_type="manual",
        title="Real MinIO",
        collection_code="coll_public",
        owner_org_code="org_teaching_materials",
        confidentiality="public",
    )

    client_any: Any = client
    result = upload_asset_version(
        engine,
        client=client_any,
        bucket=bucket,
        asset_code="WP04_REAL_MINIO",
        version_no=1,
        content=b"real minio content",
        mime_type="text/plain",
    )

    stat = client_any.stat_object(bucket, result.object_key)
    assert result.status == "created"
    assert stat.size == len(b"real minio content")
