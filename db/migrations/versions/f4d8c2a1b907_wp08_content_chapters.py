"""wp08_content_chapters

Revision ID: f4d8c2a1b907
Revises: 92bd3fa5c607
Create Date: 2026-06-30 00:20:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "f4d8c2a1b907"
down_revision: str | None = "92bd3fa5c607"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS content")

    op.execute("""
        CREATE TABLE content.product (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            code text NOT NULL UNIQUE,
            certificate_id bigint NOT NULL REFERENCES core.certificate(id),
            product_type text NOT NULL CHECK (product_type IN ('textbook','teaching_aid','handout','courseware')),
            title text NOT NULL,
            owner_org_id bigint NOT NULL REFERENCES iam.organization_unit(id),
            status text NOT NULL DEFAULT 'active' CHECK (status IN ('active','deprecated')),
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now()
        )
    """)

    op.execute("""
        CREATE TABLE content.product_version (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            product_id bigint NOT NULL REFERENCES content.product(id) ON DELETE CASCADE,
            version_no integer NOT NULL CHECK (version_no > 0),
            source_asset_version_id bigint NOT NULL REFERENCES knowledge.asset_version(id),
            title text NOT NULL,
            summary text,
            confidentiality text NOT NULL CHECK (confidentiality IN ('public','internal','confidential','restricted')),
            status text NOT NULL DEFAULT 'drafting'
                CHECK (status IN ('drafting','reviewing','approved','published','archived')),
            review_status text NOT NULL DEFAULT 'pending' CHECK (review_status IN ('pending','approved','rejected')),
            reviewed_by text,
            published_at timestamptz,
            created_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (product_id, version_no),
            CHECK (status <> 'published' OR (review_status = 'approved' AND reviewed_by IS NOT NULL))
        )
    """)

    op.execute("""
        CREATE TABLE content.chapter (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            product_version_id bigint NOT NULL REFERENCES content.product_version(id) ON DELETE CASCADE,
            parent_id bigint REFERENCES content.chapter(id),
            source_fragment_id bigint NOT NULL REFERENCES knowledge.fragment(id),
            chapter_code text NOT NULL,
            title text NOT NULL,
            body text,
            sequence_no integer NOT NULL DEFAULT 0 CHECK (sequence_no >= 0),
            confidentiality text NOT NULL CHECK (confidentiality IN ('public','internal','confidential','restricted')),
            review_status text NOT NULL DEFAULT 'pending' CHECK (review_status IN ('pending','approved','rejected')),
            status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','published','archived')),
            UNIQUE (product_version_id, chapter_code),
            CHECK (parent_id IS NULL OR parent_id <> id),
            CHECK (status <> 'published' OR review_status = 'approved')
        )
    """)
    op.execute("CREATE INDEX idx_content_chapter_parent ON content.chapter(parent_id)")
    op.execute("CREATE INDEX idx_content_chapter_version_order ON content.chapter(product_version_id, sequence_no)")

    op.execute("""
        CREATE TABLE content.chapter_knowledge_point (
            chapter_id bigint NOT NULL REFERENCES content.chapter(id) ON DELETE CASCADE,
            kp_id bigint NOT NULL REFERENCES knowledge.knowledge_point(id) ON DELETE CASCADE,
            teaching_role text NOT NULL CHECK (teaching_role IN ('core','example','extension','exercise')),
            review_status text NOT NULL DEFAULT 'pending' CHECK (review_status IN ('pending','approved','rejected')),
            reviewed_by text,
            PRIMARY KEY (chapter_id, kp_id, teaching_role),
            CHECK (review_status <> 'approved' OR reviewed_by IS NOT NULL)
        )
    """)
    op.execute("CREATE INDEX idx_content_chapter_kp_lookup ON content.chapter_knowledge_point(kp_id, review_status)")

    op.execute("""
        CREATE OR REPLACE FUNCTION content.confidentiality_rank(level text)
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
        CREATE OR REPLACE FUNCTION content.validate_chapter()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            v_parent_version_id bigint;
            v_version_source_asset_version_id bigint;
            v_version_confidentiality text;
            v_source_asset_version_id bigint;
            v_source_confidentiality text;
            v_cursor_parent_id bigint;
        BEGIN
            SELECT pv.source_asset_version_id, pv.confidentiality
              INTO v_version_source_asset_version_id, v_version_confidentiality
              FROM content.product_version pv
             WHERE pv.id = NEW.product_version_id;

            SELECT f.asset_version_id, a.confidentiality
              INTO v_source_asset_version_id, v_source_confidentiality
              FROM knowledge.fragment f
              JOIN knowledge.asset_version av ON av.id = f.asset_version_id
              JOIN knowledge.asset a ON a.id = av.asset_id
             WHERE f.id = NEW.source_fragment_id;

            IF v_source_asset_version_id IS DISTINCT FROM v_version_source_asset_version_id THEN
                RAISE EXCEPTION 'chapter source fragment must belong to product version source asset version';
            END IF;

            IF content.confidentiality_rank(NEW.confidentiality) < content.confidentiality_rank(v_version_confidentiality)
               OR content.confidentiality_rank(NEW.confidentiality) < content.confidentiality_rank(v_source_confidentiality) THEN
                RAISE EXCEPTION 'chapter confidentiality cannot be lower than source material';
            END IF;

            IF NEW.parent_id IS NOT NULL THEN
                SELECT c.product_version_id INTO v_parent_version_id
                  FROM content.chapter c
                 WHERE c.id = NEW.parent_id;

                IF v_parent_version_id IS DISTINCT FROM NEW.product_version_id THEN
                    RAISE EXCEPTION 'chapter parent must belong to the same product version';
                END IF;

                v_cursor_parent_id := NEW.parent_id;
                WHILE v_cursor_parent_id IS NOT NULL LOOP
                    IF v_cursor_parent_id = NEW.id THEN
                        RAISE EXCEPTION 'chapter tree cannot contain cycles';
                    END IF;
                    SELECT c.parent_id INTO v_cursor_parent_id
                      FROM content.chapter c
                     WHERE c.id = v_cursor_parent_id;
                END LOOP;
            END IF;

            RETURN NEW;
        END;
        $$;
    """)
    op.execute("""
        CREATE TRIGGER trg_content_chapter_validate
        BEFORE INSERT OR UPDATE ON content.chapter
        FOR EACH ROW EXECUTE FUNCTION content.validate_chapter()
    """)

    op.execute("""
        CREATE OR REPLACE FUNCTION content.prevent_published_version_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF OLD.status = 'published' AND (
                OLD.product_id IS DISTINCT FROM NEW.product_id OR
                OLD.version_no IS DISTINCT FROM NEW.version_no OR
                OLD.source_asset_version_id IS DISTINCT FROM NEW.source_asset_version_id OR
                OLD.title IS DISTINCT FROM NEW.title OR
                OLD.summary IS DISTINCT FROM NEW.summary OR
                OLD.confidentiality IS DISTINCT FROM NEW.confidentiality
            ) THEN
                RAISE EXCEPTION 'published product versions are immutable; create a new version';
            END IF;
            RETURN NEW;
        END;
        $$;
    """)
    op.execute("""
        CREATE TRIGGER trg_content_product_version_immutable
        BEFORE UPDATE ON content.product_version
        FOR EACH ROW EXECUTE FUNCTION content.prevent_published_version_mutation()
    """)

    op.execute("""
        CREATE OR REPLACE FUNCTION content.validate_product_version_publish()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF NEW.status = 'published' AND EXISTS (
                SELECT 1
                  FROM content.chapter c
                 WHERE c.product_version_id = NEW.id
                   AND (c.review_status <> 'approved' OR c.status <> 'published')
            ) THEN
                RAISE EXCEPTION 'cannot publish product version with unpublished or unapproved chapters';
            END IF;
            RETURN NEW;
        END;
        $$;
    """)
    op.execute("""
        CREATE TRIGGER trg_content_product_version_publish
        BEFORE INSERT OR UPDATE ON content.product_version
        FOR EACH ROW EXECUTE FUNCTION content.validate_product_version_publish()
    """)

    op.execute("""
        CREATE OR REPLACE FUNCTION content.prevent_published_chapter_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            version_status text;
        BEGIN
            IF TG_OP = 'DELETE' THEN
                SELECT status INTO version_status FROM content.product_version WHERE id = OLD.product_version_id;
                IF version_status = 'published' THEN
                    RAISE EXCEPTION 'published product version chapters are immutable; create a new version';
                END IF;
                RETURN OLD;
            END IF;

            SELECT status INTO version_status FROM content.product_version WHERE id = NEW.product_version_id;
            IF version_status = 'published' THEN
                RAISE EXCEPTION 'published product version chapters are immutable; create a new version';
            END IF;
            RETURN NEW;
        END;
        $$;
    """)
    op.execute("""
        CREATE TRIGGER trg_content_chapter_immutable
        BEFORE INSERT OR UPDATE OR DELETE ON content.chapter
        FOR EACH ROW EXECUTE FUNCTION content.prevent_published_chapter_mutation()
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_content_chapter_immutable ON content.chapter")
    op.execute("DROP FUNCTION IF EXISTS content.prevent_published_chapter_mutation()")
    op.execute("DROP TRIGGER IF EXISTS trg_content_product_version_publish ON content.product_version")
    op.execute("DROP FUNCTION IF EXISTS content.validate_product_version_publish()")
    op.execute("DROP TRIGGER IF EXISTS trg_content_product_version_immutable ON content.product_version")
    op.execute("DROP FUNCTION IF EXISTS content.prevent_published_version_mutation()")
    op.execute("DROP TRIGGER IF EXISTS trg_content_chapter_validate ON content.chapter")
    op.execute("DROP FUNCTION IF EXISTS content.validate_chapter()")
    op.execute("DROP FUNCTION IF EXISTS content.confidentiality_rank(text)")
    op.execute("DROP INDEX IF EXISTS content.idx_content_chapter_kp_lookup")
    op.execute("DROP TABLE IF EXISTS content.chapter_knowledge_point")
    op.execute("DROP INDEX IF EXISTS content.idx_content_chapter_version_order")
    op.execute("DROP INDEX IF EXISTS content.idx_content_chapter_parent")
    op.execute("DROP TABLE IF EXISTS content.chapter")
    op.execute("DROP TABLE IF EXISTS content.product_version")
    op.execute("DROP TABLE IF EXISTS content.product")
    op.execute("DROP SCHEMA IF EXISTS content")
