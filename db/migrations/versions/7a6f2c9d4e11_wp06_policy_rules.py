"""wp06_policy_rules

Revision ID: 7a6f2c9d4e11
Revises: b1d2f7a9c805
Create Date: 2026-06-29 22:10:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "7a6f2c9d4e11"
down_revision: str | None = "b1d2f7a9c805"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS policy")

    op.execute("""
        CREATE TABLE policy.document (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            asset_id bigint NOT NULL UNIQUE REFERENCES knowledge.asset(id),
            document_code text NOT NULL UNIQUE,
            doc_number text,
            issuing_authority text NOT NULL,
            official_url text
        )
    """)

    op.execute("""
        CREATE TABLE policy.document_version (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            document_id bigint NOT NULL REFERENCES policy.document(id),
            asset_version_id bigint NOT NULL UNIQUE REFERENCES knowledge.asset_version(id),
            version_no integer NOT NULL CHECK (version_no > 0),
            published_on date,
            valid_during daterange NOT NULL,
            status text NOT NULL CHECK (status IN ('draft','reviewed','published','superseded','repealed')),
            supersedes_version_id bigint REFERENCES policy.document_version(id),
            UNIQUE (document_id, version_no),
            CHECK (NOT isempty(valid_during))
        )
    """)

    op.execute("""
        CREATE TABLE policy.clause (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            document_version_id bigint NOT NULL REFERENCES policy.document_version(id) ON DELETE CASCADE,
            fragment_id bigint NOT NULL UNIQUE REFERENCES knowledge.fragment(id),
            clause_code text NOT NULL,
            section_path text,
            summary text,
            UNIQUE (document_version_id, clause_code)
        )
    """)

    op.execute("""
        CREATE TABLE policy.eligibility_rule (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            code text NOT NULL UNIQUE,
            certificate_id bigint NOT NULL REFERENCES core.certificate(id),
            knowledge_point_id bigint NOT NULL REFERENCES knowledge.knowledge_point(id),
            qualification_level text,
            route_code text NOT NULL DEFAULT 'normal' CHECK (route_code IN ('normal','grandfathered','title_substitute')),
            degree_level_code text,
            major_category_code text,
            education_type_code text,
            min_total_work_months integer NOT NULL DEFAULT 0 CHECK (min_total_work_months >= 0),
            min_relevant_work_months integer NOT NULL DEFAULT 0 CHECK (min_relevant_work_months >= 0),
            admission_before date,
            region_code text NOT NULL DEFAULT 'CN',
            extra_conditions jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(extra_conditions) = 'object'),
            valid_during daterange NOT NULL,
            status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','published','superseded','repealed')),
            review_status text NOT NULL DEFAULT 'pending' CHECK (review_status IN ('pending','approved','rejected')),
            reviewed_by text,
            reviewed_at timestamptz,
            created_at timestamptz NOT NULL DEFAULT now(),
            CHECK (review_status <> 'approved' OR reviewed_by IS NOT NULL),
            CHECK (NOT isempty(valid_during))
        )
    """)
    op.execute("""
        CREATE INDEX idx_eligibility_lookup ON policy.eligibility_rule
            (certificate_id, region_code, degree_level_code, major_category_code)
            WHERE status = 'published' AND review_status = 'approved'
    """)

    op.execute("""
        CREATE TABLE policy.eligibility_rule_evidence (
            eligibility_rule_id bigint NOT NULL REFERENCES policy.eligibility_rule(id) ON DELETE CASCADE,
            clause_id bigint NOT NULL REFERENCES policy.clause(id),
            evidence_role text NOT NULL CHECK (evidence_role IN ('primary','supporting','exception')),
            PRIMARY KEY (eligibility_rule_id, clause_id)
        )
    """)

    op.execute("""
        CREATE OR REPLACE FUNCTION policy.check_published_eligibility_rule(rule_id bigint)
        RETURNS void
        LANGUAGE plpgsql
        AS $$
        DECLARE
            rule_status text;
            rule_review_status text;
            rule_reviewed_by text;
        BEGIN
            SELECT status, review_status, reviewed_by
              INTO rule_status, rule_review_status, rule_reviewed_by
              FROM policy.eligibility_rule
             WHERE id = rule_id;

            IF NOT FOUND THEN
                RETURN;
            END IF;

            IF rule_status = 'published' THEN
                IF rule_review_status <> 'approved' OR rule_reviewed_by IS NULL THEN
                    RAISE EXCEPTION 'published eligibility rules must be approved and reviewed';
                END IF;

                IF NOT EXISTS (
                    SELECT 1
                      FROM policy.eligibility_rule_evidence
                     WHERE eligibility_rule_id = rule_id
                       AND evidence_role = 'primary'
                ) THEN
                    RAISE EXCEPTION 'published eligibility rules require primary evidence';
                END IF;
            END IF;
        END;
        $$;
    """)
    op.execute("""
        CREATE OR REPLACE FUNCTION policy.enforce_eligibility_rule_publishable_from_rule()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            PERFORM policy.check_published_eligibility_rule(NEW.id);
            RETURN NEW;
        END;
        $$;
    """)
    op.execute("""
        CREATE OR REPLACE FUNCTION policy.enforce_eligibility_rule_publishable_from_evidence()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            PERFORM policy.check_published_eligibility_rule(COALESCE(NEW.eligibility_rule_id, OLD.eligibility_rule_id));
            RETURN COALESCE(NEW, OLD);
        END;
        $$;
    """)
    op.execute("""
        CREATE CONSTRAINT TRIGGER trg_eligibility_rule_publishable_rule
        AFTER INSERT OR UPDATE ON policy.eligibility_rule
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION policy.enforce_eligibility_rule_publishable_from_rule()
    """)
    op.execute("""
        CREATE CONSTRAINT TRIGGER trg_eligibility_rule_publishable_evidence
        AFTER INSERT OR UPDATE OR DELETE ON policy.eligibility_rule_evidence
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION policy.enforce_eligibility_rule_publishable_from_evidence()
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_eligibility_rule_publishable_evidence ON policy.eligibility_rule_evidence")
    op.execute("DROP TRIGGER IF EXISTS trg_eligibility_rule_publishable_rule ON policy.eligibility_rule")
    op.execute("DROP FUNCTION IF EXISTS policy.enforce_eligibility_rule_publishable_from_evidence()")
    op.execute("DROP FUNCTION IF EXISTS policy.enforce_eligibility_rule_publishable_from_rule()")
    op.execute("DROP FUNCTION IF EXISTS policy.check_published_eligibility_rule(bigint)")
    op.execute("DROP TABLE IF EXISTS policy.eligibility_rule_evidence")
    op.execute("DROP INDEX IF EXISTS policy.idx_eligibility_lookup")
    op.execute("DROP TABLE IF EXISTS policy.eligibility_rule")
    op.execute("DROP TABLE IF EXISTS policy.clause")
    op.execute("DROP TABLE IF EXISTS policy.document_version")
    op.execute("DROP TABLE IF EXISTS policy.document")
    op.execute("DROP SCHEMA IF EXISTS policy")
