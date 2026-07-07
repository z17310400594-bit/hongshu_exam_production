"""wp02_iam_knowledge_base

Revision ID: 46e840ed00f1
Revises: 4709dba680c9
Create Date: 2026-06-29 15:21:52.576443
"""

from collections.abc import Sequence

from alembic import op

revision: str = "46e840ed00f1"
down_revision: str | None = "4709dba680c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS iam")
    op.execute("CREATE SCHEMA IF NOT EXISTS knowledge")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.execute("""
        CREATE TABLE iam.organization_unit (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            code text NOT NULL UNIQUE,
            name text NOT NULL,
            parent_id bigint REFERENCES iam.organization_unit(id),
            status text NOT NULL DEFAULT 'active' CHECK (status IN ('active','inactive')),
            created_at timestamptz NOT NULL DEFAULT now()
        )
    """)

    op.execute("""
        CREATE TABLE knowledge.collection (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            code text NOT NULL UNIQUE,
            name text NOT NULL,
            owner_org_id bigint NOT NULL REFERENCES iam.organization_unit(id),
            confidentiality text NOT NULL CHECK (confidentiality IN ('public','internal','confidential','restricted')),
            default_allowed_use text[] NOT NULL DEFAULT ARRAY['retrieval']::text[],
            status text NOT NULL DEFAULT 'active'
        )
    """)

    op.execute("""
        CREATE TABLE knowledge.collection_acl (
            collection_id bigint NOT NULL REFERENCES knowledge.collection(id) ON DELETE CASCADE,
            principal_type text NOT NULL CHECK (principal_type IN ('user','role','org')),
            principal_code text NOT NULL,
            permission text NOT NULL CHECK (permission IN ('read','contribute','review','admin')),
            PRIMARY KEY (collection_id, principal_type, principal_code, permission)
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS knowledge.collection_acl")
    op.execute("DROP TABLE IF EXISTS knowledge.collection")
    op.execute("DROP TABLE IF EXISTS iam.organization_unit")
    op.execute("DROP SCHEMA IF EXISTS knowledge")
    op.execute("DROP SCHEMA IF EXISTS iam")
