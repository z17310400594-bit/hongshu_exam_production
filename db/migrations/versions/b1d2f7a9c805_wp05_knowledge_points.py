"""wp05_knowledge_points

Revision ID: b1d2f7a9c805
Revises: 8fb1d4ac20f4
Create Date: 2026-06-29 20:30:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "b1d2f7a9c805"
down_revision: str | None = "8fb1d4ac20f4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE knowledge.knowledge_point (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            code text NOT NULL UNIQUE,
            name text NOT NULL,
            parent_id bigint REFERENCES knowledge.knowledge_point(id),
            domain_code text NOT NULL,
            cognitive_level text CHECK (
                cognitive_level IS NULL OR
                cognitive_level IN ('remember','understand','apply','analyze','evaluate','create')
            ),
            description text,
            status text NOT NULL DEFAULT 'active' CHECK (status IN ('active','deprecated','merged')),
            merged_into_kp_id bigint REFERENCES knowledge.knowledge_point(id),
            CHECK (parent_id IS NULL OR parent_id <> id),
            CHECK (merged_into_kp_id IS NULL OR merged_into_kp_id <> id),
            CHECK ((status = 'merged') = (merged_into_kp_id IS NOT NULL))
        )
    """)
    op.execute("CREATE INDEX idx_knowledge_point_parent ON knowledge.knowledge_point(parent_id)")

    op.execute("""
        CREATE TABLE knowledge.knowledge_point_relation (
            from_kp_id bigint NOT NULL REFERENCES knowledge.knowledge_point(id) ON DELETE CASCADE,
            to_kp_id bigint NOT NULL REFERENCES knowledge.knowledge_point(id) ON DELETE CASCADE,
            relation_type text NOT NULL CHECK (relation_type IN ('prerequisite','related','contains','similar')),
            PRIMARY KEY (from_kp_id, to_kp_id, relation_type),
            CHECK (from_kp_id <> to_kp_id)
        )
    """)
    op.execute("CREATE INDEX idx_knowledge_point_relation_to ON knowledge.knowledge_point_relation(to_kp_id)")

    op.execute("""
        CREATE TABLE knowledge.knowledge_point_scope (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            kp_id bigint NOT NULL REFERENCES knowledge.knowledge_point(id) ON DELETE CASCADE,
            scope_type text NOT NULL CHECK (scope_type IN ('certificate','exam_subject','curriculum','asset_type')),
            scope_code text NOT NULL,
            UNIQUE (kp_id, scope_type, scope_code)
        )
    """)
    op.execute("""
        CREATE INDEX idx_knowledge_point_scope_lookup
        ON knowledge.knowledge_point_scope(scope_type, scope_code)
    """)

    op.execute("""
        CREATE TABLE knowledge.fragment_knowledge_point (
            fragment_id bigint NOT NULL REFERENCES knowledge.fragment(id) ON DELETE CASCADE,
            kp_id bigint NOT NULL REFERENCES knowledge.knowledge_point(id) ON DELETE CASCADE,
            relation_role text NOT NULL CHECK (relation_role IN ('definition','evidence','explanation','example','exercise')),
            confidence numeric(4,3) NOT NULL DEFAULT 1 CHECK (confidence BETWEEN 0 AND 1),
            review_status text NOT NULL DEFAULT 'pending' CHECK (review_status IN ('pending','approved','rejected')),
            reviewed_by text,
            PRIMARY KEY (fragment_id, kp_id, relation_role),
            CHECK (review_status <> 'approved' OR reviewed_by IS NOT NULL)
        )
    """)
    op.execute("""
        CREATE INDEX idx_fragment_knowledge_point_kp_review
        ON knowledge.fragment_knowledge_point(kp_id, review_status)
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS knowledge.idx_fragment_knowledge_point_kp_review")
    op.execute("DROP TABLE IF EXISTS knowledge.fragment_knowledge_point")
    op.execute("DROP INDEX IF EXISTS knowledge.idx_knowledge_point_scope_lookup")
    op.execute("DROP TABLE IF EXISTS knowledge.knowledge_point_scope")
    op.execute("DROP INDEX IF EXISTS knowledge.idx_knowledge_point_relation_to")
    op.execute("DROP TABLE IF EXISTS knowledge.knowledge_point_relation")
    op.execute("DROP INDEX IF EXISTS knowledge.idx_knowledge_point_parent")
    op.execute("DROP TABLE IF EXISTS knowledge.knowledge_point")
