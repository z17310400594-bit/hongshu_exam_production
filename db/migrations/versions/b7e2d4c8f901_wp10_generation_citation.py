"""wp10_generation_citation

Revision ID: b7e2d4c8f901
Revises: a9c3e7d5b102
Create Date: 2026-06-30 02:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "b7e2d4c8f901"
down_revision: str | None = "a9c3e7d5b102"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS generation")

    op.execute("""
        CREATE TABLE generation.run (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            application_code text NOT NULL,
            user_code text NOT NULL,
            model_provider text NOT NULL,
            model_name text NOT NULL,
            model_route text NOT NULL DEFAULT 'internal'
                CHECK (model_route IN ('internal','approved_external','unapproved_external')),
            prompt_version text NOT NULL,
            confidentiality text NOT NULL CHECK (confidentiality IN ('public','internal','confidential','restricted')),
            status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','running','succeeded','failed','cancelled')),
            created_at timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX idx_generation_run_application_status ON generation.run(application_code, status)")

    op.execute("""
        CREATE TABLE generation.citation (
            generation_run_id bigint NOT NULL REFERENCES generation.run(id) ON DELETE CASCADE,
            fragment_id bigint NOT NULL REFERENCES knowledge.fragment(id),
            citation_order integer NOT NULL CHECK (citation_order > 0),
            usage_type text NOT NULL DEFAULT 'reference' CHECK (usage_type IN ('reference','evidence','prompt_context')),
            PRIMARY KEY (generation_run_id, fragment_id),
            UNIQUE (generation_run_id, citation_order)
        )
    """)
    op.execute("CREATE INDEX idx_generation_citation_fragment ON generation.citation(fragment_id)")

    op.execute("""
        CREATE TABLE generation.output (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            generation_run_id bigint NOT NULL REFERENCES generation.run(id) ON DELETE CASCADE,
            output_type text NOT NULL
                CHECK (output_type IN ('article','card_set','textbook_draft','question_draft','policy_article','policy_card')),
            content jsonb NOT NULL CHECK (jsonb_typeof(content) = 'object'),
            confidentiality text NOT NULL CHECK (confidentiality IN ('public','internal','confidential','restricted')),
            status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','reviewed','approved','rejected')),
            approved_by text,
            approved_at timestamptz,
            created_at timestamptz NOT NULL DEFAULT now(),
            CHECK (status <> 'approved' OR approved_by IS NOT NULL)
        )
    """)
    op.execute("CREATE INDEX idx_generation_output_run_status ON generation.output(generation_run_id, status)")

    op.execute("""
        CREATE OR REPLACE FUNCTION generation.confidentiality_rank(level text)
        RETURNS integer
        LANGUAGE sql
        IMMUTABLE
        AS $$
            SELECT CASE level
                WHEN 'public' THEN 1
                WHEN 'internal' THEN 2
                WHEN 'confidential' THEN 3
                WHEN 'restricted' THEN 4
                ELSE 0
            END
        $$;
    """)

    op.execute("""
        CREATE OR REPLACE FUNCTION generation.validate_run_security()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF EXISTS (
                SELECT 1
                  FROM generation.citation c
                  JOIN knowledge.fragment f ON f.id = c.fragment_id
                  JOIN knowledge.asset_version av ON av.id = f.asset_version_id
                  JOIN knowledge.asset a ON a.id = av.asset_id
                 WHERE c.generation_run_id = NEW.id
                   AND generation.confidentiality_rank(NEW.confidentiality)
                       < generation.confidentiality_rank(a.confidentiality)
            ) THEN
                RAISE EXCEPTION 'generation run confidentiality cannot be lower than cited fragments';
            END IF;

            IF NEW.model_route = 'unapproved_external' AND EXISTS (
                SELECT 1
                  FROM generation.citation c
                  JOIN knowledge.fragment f ON f.id = c.fragment_id
                  JOIN knowledge.asset_version av ON av.id = f.asset_version_id
                  JOIN knowledge.asset a ON a.id = av.asset_id
                 WHERE c.generation_run_id = NEW.id
                   AND a.confidentiality = 'restricted'
            ) THEN
                RAISE EXCEPTION 'restricted fragments cannot route to unapproved external models';
            END IF;

            RETURN NEW;
        END;
        $$;
    """)
    op.execute("""
        CREATE TRIGGER trg_generation_run_security
        BEFORE INSERT OR UPDATE ON generation.run
        FOR EACH ROW EXECUTE FUNCTION generation.validate_run_security()
    """)

    op.execute("""
        CREATE OR REPLACE FUNCTION generation.validate_citation_security()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            v_run_confidentiality text;
            v_model_route text;
            v_fragment_confidentiality text;
        BEGIN
            SELECT r.confidentiality, r.model_route
              INTO v_run_confidentiality, v_model_route
              FROM generation.run r
             WHERE r.id = NEW.generation_run_id;

            SELECT a.confidentiality
              INTO v_fragment_confidentiality
              FROM knowledge.fragment f
              JOIN knowledge.asset_version av ON av.id = f.asset_version_id
              JOIN knowledge.asset a ON a.id = av.asset_id
             WHERE f.id = NEW.fragment_id;

            IF generation.confidentiality_rank(v_run_confidentiality)
               < generation.confidentiality_rank(v_fragment_confidentiality) THEN
                RAISE EXCEPTION 'generation run confidentiality cannot be lower than cited fragment';
            END IF;

            IF v_model_route = 'unapproved_external' AND v_fragment_confidentiality = 'restricted' THEN
                RAISE EXCEPTION 'restricted fragments cannot route to unapproved external models';
            END IF;

            RETURN NEW;
        END;
        $$;
    """)
    op.execute("""
        CREATE TRIGGER trg_generation_citation_security
        BEFORE INSERT OR UPDATE ON generation.citation
        FOR EACH ROW EXECUTE FUNCTION generation.validate_citation_security()
    """)

    op.execute("""
        CREATE OR REPLACE FUNCTION generation.validate_output_security()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            v_run_confidentiality text;
        BEGIN
            SELECT r.confidentiality
              INTO v_run_confidentiality
              FROM generation.run r
             WHERE r.id = NEW.generation_run_id;

            IF generation.confidentiality_rank(NEW.confidentiality)
               < generation.confidentiality_rank(v_run_confidentiality) THEN
                RAISE EXCEPTION 'generation output confidentiality cannot be lower than run confidentiality';
            END IF;

            IF NEW.output_type IN ('policy_article','policy_card') AND NOT EXISTS (
                SELECT 1
                  FROM generation.citation c
                 WHERE c.generation_run_id = NEW.generation_run_id
            ) THEN
                RAISE EXCEPTION 'policy generation output must have at least one citation';
            END IF;

            RETURN NEW;
        END;
        $$;
    """)
    op.execute("""
        CREATE TRIGGER trg_generation_output_security
        BEFORE INSERT OR UPDATE ON generation.output
        FOR EACH ROW EXECUTE FUNCTION generation.validate_output_security()
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_generation_output_security ON generation.output")
    op.execute("DROP FUNCTION IF EXISTS generation.validate_output_security()")
    op.execute("DROP TRIGGER IF EXISTS trg_generation_citation_security ON generation.citation")
    op.execute("DROP FUNCTION IF EXISTS generation.validate_citation_security()")
    op.execute("DROP TRIGGER IF EXISTS trg_generation_run_security ON generation.run")
    op.execute("DROP FUNCTION IF EXISTS generation.validate_run_security()")
    op.execute("DROP FUNCTION IF EXISTS generation.confidentiality_rank(text)")
    op.execute("DROP INDEX IF EXISTS generation.idx_generation_output_run_status")
    op.execute("DROP TABLE IF EXISTS generation.output")
    op.execute("DROP INDEX IF EXISTS generation.idx_generation_citation_fragment")
    op.execute("DROP TABLE IF EXISTS generation.citation")
    op.execute("DROP INDEX IF EXISTS generation.idx_generation_run_application_status")
    op.execute("DROP TABLE IF EXISTS generation.run")
    op.execute("DROP SCHEMA IF EXISTS generation")
