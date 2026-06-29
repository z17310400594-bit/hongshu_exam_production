"""WP03 database constraint tests — FK, CHECK, UNIQUE, ON DELETE CASCADE."""

import pytest
from alembic import command
from alembic.config import Config as AlembicConfig
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError


@pytest.fixture(scope="module", autouse=True)
def _migrate_module(alembic_cfg: AlembicConfig):
    command.upgrade(alembic_cfg, "head")


def _seed_cert(engine: Engine, code: str = "cert_test", name: str = "Test Cert"):
    with engine.connect() as conn:
        conn.execute(text(f"INSERT INTO core.certificate (code, name) VALUES ('{code}', '{name}') ON CONFLICT DO NOTHING"))  # noqa: E501
        conn.commit()


# ── certificate ─────────────────────────────────────────────────

def test_cert_code_must_be_unique(engine: Engine):
    with engine.connect() as conn:
        conn.execute(text("INSERT INTO core.certificate (code, name) VALUES ('c1', 'Cert One')"))  # noqa: E501
        conn.commit()
        with pytest.raises(IntegrityError):  # noqa: SIM117
            conn.execute(text("INSERT INTO core.certificate (code, name) VALUES ('c1', 'Duplicate')"))  # noqa: E501
            conn.commit()
        conn.rollback()


def test_cert_name_must_be_unique(engine: Engine):
    with engine.connect() as conn:
        conn.execute(text("INSERT INTO core.certificate (code, name) VALUES ('c2a', 'Same Name')"))  # noqa: E501
        conn.commit()
        with pytest.raises(IntegrityError):  # noqa: SIM117
            conn.execute(text("INSERT INTO core.certificate (code, name) VALUES ('c2b', 'Same Name')"))  # noqa: E501
            conn.commit()
        conn.rollback()


def test_cert_status_rejects_invalid(engine: Engine):
    with pytest.raises(IntegrityError):  # noqa: SIM117
        with engine.connect() as conn:
            conn.execute(text("INSERT INTO core.certificate (code, name, status) VALUES ('c3', 'Bad', 'deleted')"))  # noqa: E501
            conn.commit()


# ── certificate_alias ────────────────────────────────────────────

def test_alias_normalized_must_be_unique(engine: Engine):
    _seed_cert(engine, "cert_a1", "Cert A1")
    with engine.connect() as conn:
        conn.execute(text("INSERT INTO core.certificate_alias (certificate_id, alias, normalized_alias, alias_type) SELECT id, 'short1', 'norm', 'short' FROM core.certificate WHERE code='cert_a1'"))  # noqa: E501
        conn.commit()
        with pytest.raises(IntegrityError):  # noqa: SIM117
            conn.execute(text("INSERT INTO core.certificate_alias (certificate_id, alias, normalized_alias, alias_type) SELECT id, 'short2', 'norm', 'short' FROM core.certificate WHERE code='cert_a1'"))  # noqa: E501
            conn.commit()
        conn.rollback()


def test_alias_type_rejects_invalid(engine: Engine):
    _seed_cert(engine, "cert_a2", "Cert A2")
    with pytest.raises(IntegrityError):  # noqa: SIM117
        with engine.connect() as conn:
            conn.execute(text("INSERT INTO core.certificate_alias (certificate_id, alias, normalized_alias, alias_type) SELECT id, 'xyz', 'n2', 'invalid' FROM core.certificate WHERE code='cert_a2'"))  # noqa: E501
            conn.commit()


def test_alias_cert_fk_must_exist(engine: Engine):
    with pytest.raises(IntegrityError):  # noqa: SIM117
        with engine.connect() as conn:
            conn.execute(text("INSERT INTO core.certificate_alias (certificate_id, alias, normalized_alias, alias_type) VALUES (99999, 'orphan', 'orphan_norm', 'common')"))  # noqa: E501
            conn.commit()


def test_alias_cascade_on_cert_delete(engine: Engine):
    _seed_cert(engine, "cert_cascade", "Cascade Test")
    with engine.connect() as conn:
        conn.execute(text("INSERT INTO core.certificate_alias (certificate_id, alias, normalized_alias, alias_type) SELECT id, 'casc_alias', 'casc_norm', 'common' FROM core.certificate WHERE code='cert_cascade'"))  # noqa: E501
        conn.commit()
        conn.execute(text("DELETE FROM core.certificate WHERE code='cert_cascade'"))  # noqa: E501
        conn.commit()
        count = conn.execute(text("SELECT count(*) FROM core.certificate_alias WHERE normalized_alias='casc_norm'")).scalar()
        assert count == 0


# ── exam_subject ──────────────────────────────────────────────────

def test_subject_code_must_be_unique(engine: Engine):
    _seed_cert(engine, "cert_s1", "Cert S1")
    with engine.connect() as conn:
        conn.execute(text("INSERT INTO core.exam_subject (certificate_id, code, name) SELECT id, 'subj_code', 'Subject' FROM core.certificate WHERE code='cert_s1'"))  # noqa: E501
        conn.commit()
        with pytest.raises(IntegrityError):  # noqa: SIM117
            conn.execute(text("INSERT INTO core.exam_subject (certificate_id, code, name) SELECT id, 'subj_code', 'Subject 2' FROM core.certificate WHERE code='cert_s1'"))  # noqa: E501
            conn.commit()
        conn.rollback()


def test_subject_cert_name_must_be_unique(engine: Engine):
    _seed_cert(engine, "cert_s2", "Cert S2")
    with engine.connect() as conn:
        conn.execute(text("INSERT INTO core.exam_subject (certificate_id, code, name) SELECT id, 'subj_a', 'Same Subject' FROM core.certificate WHERE code='cert_s2'"))  # noqa: E501
        conn.commit()
        with pytest.raises(IntegrityError):  # noqa: SIM117
            conn.execute(text("INSERT INTO core.exam_subject (certificate_id, code, name) SELECT id, 'subj_b', 'Same Subject' FROM core.certificate WHERE code='cert_s2'"))  # noqa: E501
            conn.commit()
        conn.rollback()


def test_subject_cert_fk_must_exist(engine: Engine):
    with pytest.raises(IntegrityError):  # noqa: SIM117
        with engine.connect() as conn:
            conn.execute(text("INSERT INTO core.exam_subject (certificate_id, code, name) VALUES (99999, 'orphan_subj', 'Orphan Subject')"))  # noqa: E501
            conn.commit()
