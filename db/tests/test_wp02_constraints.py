"""WP02 database constraint tests — FK, CHECK, UNIQUE for iam + knowledge tables."""

import pytest
from alembic import command
from alembic.config import Config as AlembicConfig
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError


@pytest.fixture(scope="module", autouse=True)
def _migrate_module(alembic_cfg: AlembicConfig):
    """Ensure the test database has all migrations applied before constraint tests."""
    command.upgrade(alembic_cfg, "head")


# ── organization_unit ──────────────────────────────────────────

def test_org_code_must_be_unique(engine: Engine):
    with engine.connect() as conn:
        conn.execute(text("INSERT INTO iam.organization_unit (code, name) VALUES ('org_uniq', 'Test Org')"))
        conn.commit()
        with pytest.raises(IntegrityError):  # noqa: SIM117
            conn.execute(text("INSERT INTO iam.organization_unit (code, name) VALUES ('org_uniq', 'Duplicate')"))
            conn.commit()
        conn.rollback()


def test_org_status_rejects_invalid(engine: Engine):
    with pytest.raises(IntegrityError), engine.connect() as conn:
        conn.execute(text("INSERT INTO iam.organization_unit (code, name, status) VALUES ('org_bad', 'Bad', 'deleted')"))
        conn.commit()


def test_org_parent_must_exist(engine: Engine):
    with pytest.raises(IntegrityError), engine.connect() as conn:
        conn.execute(text("INSERT INTO iam.organization_unit (code, name, parent_id) VALUES ('org_orphan', 'Orphan', 99999)"))
        conn.commit()


# ── collection ──────────────────────────────────────────────────

def test_collection_code_must_be_unique(engine: Engine):
    with engine.connect() as conn:
        conn.execute(text("INSERT INTO iam.organization_unit (code, name) VALUES ('org_c1', 'Coll Owner')"))
        conn.execute(text("INSERT INTO knowledge.collection (code, name, owner_org_id, confidentiality) SELECT 'col_uniq', 'Test', id, 'public' FROM iam.organization_unit WHERE code='org_c1'"))  # noqa: E501
        conn.commit()
        with pytest.raises(IntegrityError):  # noqa: SIM117
            conn.execute(text("INSERT INTO knowledge.collection (code, name, owner_org_id, confidentiality) SELECT 'col_uniq', 'Dup', id, 'public' FROM iam.organization_unit WHERE code='org_c1'"))  # noqa: E501
            conn.commit()
        conn.rollback()


def test_collection_confidentiality_rejects_invalid(engine: Engine):
    with pytest.raises(IntegrityError):  # noqa: SIM117
        with engine.connect() as conn:  # noqa: SIM117
            conn.execute(text("INSERT INTO iam.organization_unit (code, name) VALUES ('org_c2', 'BadConf')"))
            conn.execute(text("INSERT INTO knowledge.collection (code, name, owner_org_id, confidentiality) SELECT 'col_badconf', 'Bad', id, 'top_secret' FROM iam.organization_unit WHERE code='org_c2'"))  # noqa: E501
            conn.commit()


def test_collection_owner_org_must_exist(engine: Engine):
    with pytest.raises(IntegrityError):  # noqa: SIM117
        with engine.connect() as conn:  # noqa: SIM117
            conn.execute(text("INSERT INTO knowledge.collection (code, name, owner_org_id, confidentiality) VALUES ('col_badorg', 'NoOrg', 99999, 'public')"))  # noqa: E501
            conn.commit()


# ── collection_acl ──────────────────────────────────────────────

def _setup_collection(engine: Engine, org_code: str, coll_code: str, confidentiality: str = "public"):
    with engine.connect() as conn:
        conn.execute(text(f"INSERT INTO iam.organization_unit (code, name) VALUES ('{org_code}', 'Org') ON CONFLICT DO NOTHING"))
        conn.execute(text(f"INSERT INTO knowledge.collection (code, name, owner_org_id, confidentiality) SELECT '{coll_code}', 'Coll', id, '{confidentiality}' FROM iam.organization_unit WHERE code='{org_code}' ON CONFLICT DO NOTHING"))  # noqa: E501
        conn.commit()


def test_acl_principal_type_rejects_invalid(engine: Engine):
    _setup_collection(engine, "org_acl1", "col_acl1")
    with pytest.raises(IntegrityError):  # noqa: SIM117
        with engine.connect() as conn:  # noqa: SIM117
            conn.execute(text("INSERT INTO knowledge.collection_acl (collection_id, principal_type, principal_code, permission) SELECT id, 'department', 'sales', 'read' FROM knowledge.collection WHERE code='col_acl1'"))  # noqa: E501
            conn.commit()


def test_acl_permission_rejects_invalid(engine: Engine):
    _setup_collection(engine, "org_acl2", "col_acl2")
    with pytest.raises(IntegrityError):  # noqa: SIM117
        with engine.connect() as conn:  # noqa: SIM117
            conn.execute(text("INSERT INTO knowledge.collection_acl (collection_id, principal_type, principal_code, permission) SELECT id, 'org', 'sales', 'delete' FROM knowledge.collection WHERE code='col_acl2'"))  # noqa: E501
            conn.commit()


def test_acl_pk_prevents_duplicate(engine: Engine):
    _setup_collection(engine, "org_acl3", "col_acl3")
    with engine.connect() as conn:
        conn.execute(text("INSERT INTO knowledge.collection_acl (collection_id, principal_type, principal_code, permission) SELECT id, 'org', 'sales', 'read' FROM knowledge.collection WHERE code='col_acl3'"))  # noqa: E501
        conn.commit()
        with pytest.raises(IntegrityError):  # noqa: SIM117
            conn.execute(text("INSERT INTO knowledge.collection_acl (collection_id, principal_type, principal_code, permission) SELECT id, 'org', 'sales', 'read' FROM knowledge.collection WHERE code='col_acl3'"))  # noqa: E501
            conn.commit()
        conn.rollback()


def test_acl_collection_fk_must_exist(engine: Engine):
    """collection_acl must reference an existing collection."""
    with pytest.raises(IntegrityError):  # noqa: SIM117
        with engine.connect() as conn:
            conn.execute(text("INSERT INTO knowledge.collection_acl (collection_id, principal_type, principal_code, permission) VALUES (99999, 'org', 'test', 'read')"))  # noqa: E501
            conn.commit()

