"""WP10 database constraint tests — generation runs, citations, and outputs."""

import json

import pytest
from alembic import command
from alembic.config import Config as AlembicConfig
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from db.tests.fixtures_wp02 import seed_fixtures as seed_wp02
from db.tests.fixtures_wp03 import seed_fixtures as seed_wp03
from db.tests.fixtures_wp10 import (
    seed_generation_citation,
    seed_generation_output,
    seed_generation_run,
    seed_generation_source_asset,
)


@pytest.fixture(scope="module", autouse=True)
def _migrate_module(alembic_cfg: AlembicConfig, engine: Engine):
    command.upgrade(alembic_cfg, "head")
    seed_wp02(engine)
    seed_wp03(engine)


def test_generation_run_status_route_and_confidentiality_constraints(engine: Engine):
    run = seed_generation_run(engine, confidentiality="internal", model_route="approved_external")
    assert run["status"] == "succeeded"

    bad_rows = [
        {"route": "external", "conf": "internal", "status": "succeeded"},
        {"route": "approved_external", "conf": "secret", "status": "succeeded"},
        {"route": "approved_external", "conf": "internal", "status": "done"},
    ]
    for row in bad_rows:
        with pytest.raises(IntegrityError), engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO generation.run (
                        application_code, user_code, model_provider, model_name,
                        model_route, prompt_version, confidentiality, status
                    )
                    VALUES (
                        'app', 'user', 'provider', 'model',
                        :route, 'prompt_v1', :conf, :status
                    )
                """),
                row,
            )


def test_citation_constraints_confidentiality_and_external_route(engine: Engine):
    internal_source = seed_generation_source_asset(engine, asset_code="WP10_INTERNAL_ASSET", confidentiality="internal")
    restricted_source = seed_generation_source_asset(
        engine,
        asset_code="WP10_RESTRICTED_ASSET",
        collection_code="coll_restricted",
        confidentiality="restricted",
    )
    run = seed_generation_run(engine, confidentiality="internal", model_route="approved_external")
    seed_generation_citation(engine, run_id=run["id"], fragment_id=internal_source["fragment_ids"]["GEN_REF_01"])

    bad_citations = [
        {"run_id": run["id"], "fragment_id": internal_source["fragment_ids"]["GEN_REF_02"], "order": 1, "usage": "reference"},
        {"run_id": run["id"], "fragment_id": internal_source["fragment_ids"]["GEN_REF_02"], "order": 2, "usage": "quote"},
        {"run_id": run["id"], "fragment_id": internal_source["fragment_ids"]["GEN_REF_02"], "order": 0, "usage": "reference"},
        {"run_id": 999999, "fragment_id": internal_source["fragment_ids"]["GEN_REF_02"], "order": 2, "usage": "reference"},
        {"run_id": run["id"], "fragment_id": 999999, "order": 2, "usage": "reference"},
        {"run_id": run["id"], "fragment_id": restricted_source["fragment_ids"]["GEN_REF_01"], "order": 2, "usage": "reference"},
    ]
    for row in bad_citations:
        with pytest.raises(SQLAlchemyError), engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO generation.citation (
                        generation_run_id, fragment_id, citation_order, usage_type
                    )
                    VALUES (:run_id, :fragment_id, :order, :usage)
                """),
                row,
            )

    restricted_run = seed_generation_run(
        engine,
        confidentiality="restricted",
        model_route="unapproved_external",
    )
    with pytest.raises(SQLAlchemyError):
        seed_generation_citation(
            engine,
            run_id=restricted_run["id"],
            fragment_id=restricted_source["fragment_ids"]["GEN_REF_01"],
        )

    approved_restricted_run = seed_generation_run(
        engine,
        confidentiality="restricted",
        model_route="approved_external",
    )
    seed_generation_citation(
        engine,
        run_id=approved_restricted_run["id"],
        fragment_id=restricted_source["fragment_ids"]["GEN_REF_01"],
    )
    with pytest.raises(SQLAlchemyError), engine.begin() as conn:
        conn.execute(
            text("UPDATE generation.run SET model_route = 'unapproved_external' WHERE id = :run_id"),
            {"run_id": approved_restricted_run["id"]},
        )


def test_output_constraints_policy_citation_and_confidentiality(engine: Engine):
    source = seed_generation_source_asset(engine, asset_code="WP10_OUTPUT_ASSET", confidentiality="internal")
    run_without_citation = seed_generation_run(engine, confidentiality="internal")
    with pytest.raises(SQLAlchemyError):
        seed_generation_output(
            engine,
            run_id=run_without_citation["id"],
            output_type="policy_article",
            confidentiality="internal",
        )

    run = seed_generation_run(engine, confidentiality="internal")
    seed_generation_citation(engine, run_id=run["id"], fragment_id=source["fragment_ids"]["GEN_REF_01"])
    output = seed_generation_output(
        engine,
        run_id=run["id"],
        output_type="policy_article",
        confidentiality="internal",
        status="approved",
        approved_by="wp10_reviewer",
    )
    assert output["status"] == "approved"

    bad_outputs = [
        {"type": "video", "content": {"body": "x"}, "conf": "internal", "status": "draft", "approved_by": None},
        {"type": "article", "content": ["not-object"], "conf": "internal", "status": "draft", "approved_by": None},
        {"type": "article", "content": {"body": "x"}, "conf": "public", "status": "draft", "approved_by": None},
        {"type": "article", "content": {"body": "x"}, "conf": "internal", "status": "approved", "approved_by": None},
    ]
    for row in bad_outputs:
        with pytest.raises(SQLAlchemyError), engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO generation.output (
                        generation_run_id, output_type, content,
                        confidentiality, status, approved_by
                    )
                    VALUES (
                        :run_id, :type, CAST(:content_json AS jsonb),
                        :conf, :status, :approved_by
                    )
                """),
                {
                    "run_id": run["id"],
                    "type": row["type"],
                    "content_json": json.dumps(row["content"], ensure_ascii=False),
                    "conf": row["conf"],
                    "status": row["status"],
                    "approved_by": row["approved_by"],
                },
            )

    with pytest.raises(IntegrityError):
        seed_generation_output(
            engine,
            run_id=999999,
            output_type="article",
            confidentiality="internal",
        )
