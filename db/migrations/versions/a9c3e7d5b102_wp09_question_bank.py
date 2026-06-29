"""wp09_question_bank

Revision ID: a9c3e7d5b102
Revises: f4d8c2a1b907
Create Date: 2026-06-30 01:10:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "a9c3e7d5b102"
down_revision: str | None = "f4d8c2a1b907"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE assessment.paper (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            code text NOT NULL UNIQUE,
            paper_type text NOT NULL CHECK (paper_type IN ('official','mock','chapter_test')),
            certificate_id bigint NOT NULL REFERENCES core.certificate(id),
            subject_id bigint REFERENCES core.exam_subject(id),
            exam_year integer CHECK (exam_year IS NULL OR exam_year BETWEEN 2000 AND 2100),
            source_asset_version_id bigint NOT NULL REFERENCES knowledge.asset_version(id),
            owner_org_id bigint NOT NULL REFERENCES iam.organization_unit(id),
            title text NOT NULL,
            status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','published','archived')),
            review_status text NOT NULL DEFAULT 'pending' CHECK (review_status IN ('pending','approved','rejected')),
            reviewed_by text,
            CHECK (status <> 'published' OR review_status = 'approved')
        )
    """)
    op.execute("CREATE INDEX idx_assessment_paper_certificate_year ON assessment.paper(certificate_id, exam_year)")

    op.execute("""
        CREATE TABLE assessment.question (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            paper_id bigint NOT NULL REFERENCES assessment.paper(id) ON DELETE CASCADE,
            source_fragment_id bigint REFERENCES knowledge.fragment(id),
            question_no text NOT NULL,
            question_type text NOT NULL CHECK (question_type IN ('single','multiple','true_false','case','essay')),
            content text NOT NULL,
            options jsonb,
            answer jsonb NOT NULL,
            analysis text,
            difficulty smallint NOT NULL CHECK (difficulty BETWEEN 1 AND 5),
            review_status text NOT NULL DEFAULT 'pending' CHECK (review_status IN ('pending','approved','rejected')),
            UNIQUE (paper_id, question_no),
            CHECK (options IS NULL OR jsonb_typeof(options) = 'object'),
            CHECK (jsonb_typeof(answer) IN ('array','string','object','boolean')),
            CHECK (
                (
                    question_type = 'single'
                    AND jsonb_typeof(options) = 'object'
                    AND jsonb_typeof(answer) = 'string'
                ) OR (
                    question_type = 'multiple'
                    AND jsonb_typeof(options) = 'object'
                    AND jsonb_typeof(answer) = 'array'
                ) OR (
                    question_type = 'true_false'
                    AND (options IS NULL OR jsonb_typeof(options) = 'object')
                    AND jsonb_typeof(answer) IN ('boolean','string')
                ) OR (
                    question_type IN ('case','essay')
                    AND jsonb_typeof(answer) IN ('array','string','object')
                )
            )
        )
    """)
    op.execute("CREATE INDEX idx_assessment_question_paper_review ON assessment.question(paper_id, review_status)")

    op.execute("""
        CREATE TABLE assessment.question_knowledge_point (
            question_id bigint NOT NULL REFERENCES assessment.question(id) ON DELETE CASCADE,
            kp_id bigint NOT NULL REFERENCES knowledge.knowledge_point(id),
            role text NOT NULL CHECK (role IN ('primary','secondary')),
            score_weight numeric(6,3) CHECK (score_weight IS NULL OR score_weight BETWEEN 0 AND 1),
            PRIMARY KEY (question_id, kp_id)
        )
    """)
    op.execute("CREATE INDEX idx_assessment_question_kp_lookup ON assessment.question_knowledge_point(kp_id, role)")

    op.execute("""
        CREATE OR REPLACE FUNCTION assessment.validate_question_source()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            v_paper_asset_version_id bigint;
            v_fragment_asset_version_id bigint;
        BEGIN
            IF NEW.source_fragment_id IS NULL THEN
                RETURN NEW;
            END IF;

            SELECT p.source_asset_version_id
              INTO v_paper_asset_version_id
              FROM assessment.paper p
             WHERE p.id = NEW.paper_id;

            SELECT f.asset_version_id
              INTO v_fragment_asset_version_id
              FROM knowledge.fragment f
             WHERE f.id = NEW.source_fragment_id;

            IF v_fragment_asset_version_id IS DISTINCT FROM v_paper_asset_version_id THEN
                RAISE EXCEPTION 'question source fragment must belong to paper source asset version';
            END IF;

            RETURN NEW;
        END;
        $$;
    """)
    op.execute("""
        CREATE TRIGGER trg_assessment_question_source
        BEFORE INSERT OR UPDATE ON assessment.question
        FOR EACH ROW EXECUTE FUNCTION assessment.validate_question_source()
    """)

    op.execute("""
        CREATE OR REPLACE FUNCTION assessment.validate_paper_publish()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF NEW.status = 'published' AND (
                NEW.review_status <> 'approved'
                OR EXISTS (
                    SELECT 1
                      FROM assessment.question q
                     WHERE q.paper_id = NEW.id
                       AND q.review_status <> 'approved'
                )
            ) THEN
                RAISE EXCEPTION 'cannot publish paper with unapproved questions';
            END IF;
            RETURN NEW;
        END;
        $$;
    """)
    op.execute("""
        CREATE TRIGGER trg_assessment_paper_publish
        BEFORE INSERT OR UPDATE ON assessment.paper
        FOR EACH ROW EXECUTE FUNCTION assessment.validate_paper_publish()
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_assessment_paper_publish ON assessment.paper")
    op.execute("DROP FUNCTION IF EXISTS assessment.validate_paper_publish()")
    op.execute("DROP TRIGGER IF EXISTS trg_assessment_question_source ON assessment.question")
    op.execute("DROP FUNCTION IF EXISTS assessment.validate_question_source()")
    op.execute("DROP INDEX IF EXISTS assessment.idx_assessment_question_kp_lookup")
    op.execute("DROP TABLE IF EXISTS assessment.question_knowledge_point")
    op.execute("DROP INDEX IF EXISTS assessment.idx_assessment_question_paper_review")
    op.execute("DROP TABLE IF EXISTS assessment.question")
    op.execute("DROP INDEX IF EXISTS assessment.idx_assessment_paper_certificate_year")
    op.execute("DROP TABLE IF EXISTS assessment.paper")
