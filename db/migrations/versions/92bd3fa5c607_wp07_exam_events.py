"""wp07_exam_events

Revision ID: 92bd3fa5c607
Revises: 7a6f2c9d4e11
Create Date: 2026-06-29 23:05:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "92bd3fa5c607"
down_revision: str | None = "7a6f2c9d4e11"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS assessment")

    op.execute("""
        CREATE TABLE assessment.exam_event (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            code text NOT NULL UNIQUE,
            certificate_id bigint NOT NULL REFERENCES core.certificate(id),
            exam_year integer NOT NULL CHECK (exam_year BETWEEN 2000 AND 2100),
            region_code text NOT NULL DEFAULT 'CN',
            status text NOT NULL DEFAULT 'scheduled'
                CHECK (status IN ('scheduled','published','completed','cancelled','needs_review')),
            UNIQUE (certificate_id, exam_year, region_code)
        )
    """)

    op.execute("""
        CREATE TABLE assessment.exam_phase (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            exam_event_id bigint NOT NULL REFERENCES assessment.exam_event(id) ON DELETE CASCADE,
            phase_type text NOT NULL CHECK (phase_type IN ('registration','practical','written','interview','result')),
            starts_on date NOT NULL,
            ends_on date,
            note text,
            UNIQUE (exam_event_id, phase_type, starts_on),
            CHECK (ends_on IS NULL OR starts_on <= ends_on)
        )
    """)

    op.execute("""
        CREATE TABLE assessment.subject_score_rule (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            exam_event_id bigint NOT NULL REFERENCES assessment.exam_event(id) ON DELETE CASCADE,
            subject_id bigint NOT NULL REFERENCES core.exam_subject(id),
            full_mark numeric(8,2) NOT NULL CHECK (full_mark > 0),
            pass_mark numeric(8,2) NOT NULL CHECK (pass_mark BETWEEN 0 AND full_mark),
            UNIQUE (exam_event_id, subject_id)
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS assessment.subject_score_rule")
    op.execute("DROP TABLE IF EXISTS assessment.exam_phase")
    op.execute("DROP TABLE IF EXISTS assessment.exam_event")
    op.execute("DROP SCHEMA IF EXISTS assessment")
