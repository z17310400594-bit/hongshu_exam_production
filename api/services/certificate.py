"""Certificate lookup service — exact match only, no LIMIT 1 guesswork."""

from sqlalchemy import text
from sqlalchemy.engine import Engine


class AmbiguousAliasError(Exception):
    """Raised when a normalized alias maps to more than one certificate."""


def lookup_by_code(engine: Engine, code: str) -> dict | None:
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT id, code, name, category_code FROM core.certificate WHERE code = :c"),
            {"c": code},
        ).fetchone()
    return row._mapping if row else None


def lookup_by_normalized_alias(engine: Engine, normalized: str) -> dict | None:
    with engine.connect() as conn:
        rows = conn.execute(
            text("""
                SELECT c.id, c.code, c.name, c.category_code
                  FROM core.certificate c
                  JOIN core.certificate_alias a ON a.certificate_id = c.id
                 WHERE a.normalized_alias = :n
            """),
            {"n": normalized},
        ).fetchall()
    if not rows:
        return None
    if len(rows) > 1:
        raise AmbiguousAliasError(f"normalized_alias '{normalized}' matches {len(rows)} certificates")
    return rows[0]._mapping


def list_certificates(engine: Engine) -> list[dict]:
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT id, code, name, category_code, status FROM core.certificate ORDER BY code")
        ).fetchall()
    return [r._mapping for r in rows]
