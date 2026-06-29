"""wp11_import_validation

Revision ID: c6f1a2b9d304
Revises: b7e2d4c8f901
Create Date: 2026-06-30 03:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "c6f1a2b9d304"
down_revision: str | None = "b7e2d4c8f901"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS ingestion")

    op.execute("""
        CREATE TABLE ingestion.import_batch (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            filename text NOT NULL,
            content_sha256 text NOT NULL UNIQUE CHECK (content_sha256 ~ '^[0-9a-f]{64}$'),
            imported_by text NOT NULL,
            status text NOT NULL DEFAULT 'uploaded' CHECK (status IN ('uploaded','validating','failed','committed')),
            total_rows integer NOT NULL DEFAULT 0 CHECK (total_rows >= 0),
            success_rows integer NOT NULL DEFAULT 0 CHECK (success_rows >= 0),
            failed_rows integer NOT NULL DEFAULT 0 CHECK (failed_rows >= 0),
            imported_at timestamptz NOT NULL DEFAULT now(),
            CHECK (success_rows + failed_rows <= total_rows)
        )
    """)
    op.execute("CREATE INDEX idx_ingestion_import_batch_status ON ingestion.import_batch(status)")

    op.execute("""
        CREATE TABLE ingestion.validation_error (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            batch_id bigint NOT NULL REFERENCES ingestion.import_batch(id) ON DELETE CASCADE,
            row_number integer CHECK (row_number IS NULL OR row_number > 0),
            row_key text NOT NULL,
            field_name text NOT NULL,
            error_code text NOT NULL CHECK (error_code ~ '^[A-Z0-9_]+$'),
            error_message text NOT NULL,
            severity text NOT NULL DEFAULT 'P1' CHECK (severity IN ('P0','P1','P2','P3')),
            UNIQUE (batch_id, row_key, field_name, error_code)
        )
    """)
    op.execute("CREATE INDEX idx_ingestion_validation_error_batch ON ingestion.validation_error(batch_id, severity)")

    op.execute("""
        CREATE OR REPLACE FUNCTION ingestion.mark_batch_failed_for_blocking_error()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF NEW.severity IN ('P0','P1') THEN
                UPDATE ingestion.import_batch
                   SET status = 'failed'
                 WHERE id = NEW.batch_id
                   AND status <> 'failed';
            END IF;
            RETURN NEW;
        END;
        $$;
    """)
    op.execute("""
        CREATE TRIGGER trg_ingestion_validation_error_blocking
        AFTER INSERT OR UPDATE ON ingestion.validation_error
        FOR EACH ROW EXECUTE FUNCTION ingestion.mark_batch_failed_for_blocking_error()
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_ingestion_validation_error_blocking ON ingestion.validation_error")
    op.execute("DROP FUNCTION IF EXISTS ingestion.mark_batch_failed_for_blocking_error()")
    op.execute("DROP INDEX IF EXISTS ingestion.idx_ingestion_validation_error_batch")
    op.execute("DROP TABLE IF EXISTS ingestion.validation_error")
    op.execute("DROP INDEX IF EXISTS ingestion.idx_ingestion_import_batch_status")
    op.execute("DROP TABLE IF EXISTS ingestion.import_batch")
    op.execute("DROP SCHEMA IF EXISTS ingestion")
