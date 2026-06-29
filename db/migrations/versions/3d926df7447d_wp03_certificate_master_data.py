"""wp03_certificate_master_data

Revision ID: 3d926df7447d
Revises: 46e840ed00f1
Create Date: 2026-06-29 16:22:18.085512
"""

from collections.abc import Sequence

from alembic import op

revision: str = "3d926df7447d"
down_revision: str | None = "46e840ed00f1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS core")

    op.execute("""
        CREATE TABLE core.certificate (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            code text NOT NULL UNIQUE,
            name text NOT NULL UNIQUE,
            category_code text,
            issuing_authority text,
            exam_authority text,
            nationwide boolean NOT NULL DEFAULT true,
            status text NOT NULL DEFAULT 'active' CHECK (status IN ('active','inactive')),
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now()
        )
    """)

    op.execute("""
        CREATE TABLE core.certificate_alias (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            certificate_id bigint NOT NULL REFERENCES core.certificate(id) ON DELETE CASCADE,
            alias text NOT NULL,
            normalized_alias text NOT NULL UNIQUE,
            alias_type text NOT NULL CHECK (alias_type IN ('short','common','legacy'))
        )
    """)

    op.execute("""
        CREATE TABLE core.exam_subject (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            certificate_id bigint NOT NULL REFERENCES core.certificate(id),
            code text NOT NULL UNIQUE,
            name text NOT NULL,
            UNIQUE (certificate_id, name)
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS core.exam_subject")
    op.execute("DROP TABLE IF EXISTS core.certificate_alias")
    op.execute("DROP TABLE IF EXISTS core.certificate")
    op.execute("DROP SCHEMA IF EXISTS core")
