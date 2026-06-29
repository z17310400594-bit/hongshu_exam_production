"""wp04_assets_versions_fragments

Revision ID: 8fb1d4ac20f4
Revises: 3d926df7447d
Create Date: 2026-06-29 17:20:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "8fb1d4ac20f4"
down_revision: str | None = "3d926df7447d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.execute("""
        CREATE TABLE knowledge.asset (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            code text NOT NULL UNIQUE,
            asset_type text NOT NULL CHECK (asset_type IN ('policy','textbook','handout','private','paper','manual')),
            title text NOT NULL,
            collection_id bigint NOT NULL REFERENCES knowledge.collection(id),
            owner_org_id bigint NOT NULL REFERENCES iam.organization_unit(id),
            confidentiality text NOT NULL CHECK (confidentiality IN ('public','internal','confidential','restricted')),
            copyright_owner text,
            allowed_use text[] NOT NULL DEFAULT ARRAY['retrieval']::text[],
            status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','reviewed','published','deprecated')),
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now()
        )
    """)

    op.execute("""
        CREATE TABLE knowledge.asset_version (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            asset_id bigint NOT NULL REFERENCES knowledge.asset(id),
            version_no integer NOT NULL CHECK (version_no > 0),
            object_key text,
            mime_type text,
            extracted_text text,
            content_sha256 text NOT NULL,
            valid_during daterange,
            review_status text NOT NULL DEFAULT 'pending' CHECK (review_status IN ('pending','approved','rejected')),
            reviewed_by text,
            reviewed_at timestamptz,
            created_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (asset_id, version_no),
            UNIQUE (content_sha256)
        )
    """)

    op.execute("""
        CREATE TABLE knowledge.fragment (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            asset_version_id bigint NOT NULL REFERENCES knowledge.asset_version(id) ON DELETE CASCADE,
            fragment_code text NOT NULL,
            fragment_type text NOT NULL CHECK (fragment_type IN ('chapter','section','clause','page','table')),
            parent_id bigint REFERENCES knowledge.fragment(id),
            sequence_no integer NOT NULL DEFAULT 0,
            heading text,
            content text NOT NULL,
            page_from integer,
            page_to integer,
            search_tsv tsvector GENERATED ALWAYS AS (to_tsvector('simple', coalesce(heading,'') || ' ' || content)) STORED,
            UNIQUE (asset_version_id, fragment_code),
            CHECK (page_from IS NULL OR page_from > 0),
            CHECK (page_to IS NULL OR page_from IS NULL OR page_to >= page_from)
        )
    """)
    op.execute("CREATE INDEX idx_fragment_search ON knowledge.fragment USING gin(search_tsv)")
    op.execute("CREATE INDEX idx_fragment_content_trgm ON knowledge.fragment USING gin(content gin_trgm_ops)")

    op.execute("""
        CREATE OR REPLACE FUNCTION knowledge.prevent_approved_asset_version_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF OLD.review_status = 'approved' AND (
                OLD.object_key IS DISTINCT FROM NEW.object_key OR
                OLD.mime_type IS DISTINCT FROM NEW.mime_type OR
                OLD.extracted_text IS DISTINCT FROM NEW.extracted_text OR
                OLD.content_sha256 IS DISTINCT FROM NEW.content_sha256
            ) THEN
                RAISE EXCEPTION 'approved asset versions are immutable';
            END IF;
            RETURN NEW;
        END;
        $$;
    """)
    op.execute("""
        CREATE TRIGGER trg_asset_version_immutable
        BEFORE UPDATE ON knowledge.asset_version
        FOR EACH ROW EXECUTE FUNCTION knowledge.prevent_approved_asset_version_mutation()
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_asset_version_immutable ON knowledge.asset_version")
    op.execute("DROP FUNCTION IF EXISTS knowledge.prevent_approved_asset_version_mutation()")
    op.execute("DROP INDEX IF EXISTS knowledge.idx_fragment_content_trgm")
    op.execute("DROP INDEX IF EXISTS knowledge.idx_fragment_search")
    op.execute("DROP TABLE IF EXISTS knowledge.fragment")
    op.execute("DROP TABLE IF EXISTS knowledge.asset_version")
    op.execute("DROP TABLE IF EXISTS knowledge.asset")
