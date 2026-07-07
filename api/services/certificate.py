"""Certificate lookup service — exact match, alias normalization, old-ID mapping."""


from sqlalchemy import text
from sqlalchemy.engine import Engine


def normalize_alias(raw: str) -> str:
    """Normalize a user-supplied alias (e.g. '一建' → 'cls1_constructor').

    WP03: delegates to the certificate_alias table via lookup_by_alias().
    Raw input is lowercased and stripped first.
    """
    return raw.strip().lower()


def lookup_by_code(engine: Engine, code: str) -> dict | None:
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT id, code, name, category_code FROM core.certificate WHERE code = :c"),
            {"c": code},
        ).fetchone()
    return dict(row._mapping) if row else None


def lookup_by_name(engine: Engine, name: str) -> dict | None:
    """Exact name match — no fuzzy search."""
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT id, code, name, category_code FROM core.certificate WHERE name = :n"),
            {"n": name},
        ).fetchone()
    return dict(row._mapping) if row else None


def lookup_by_alias(engine: Engine, raw_alias: str) -> dict | None:
    """Search raw alias against alias column first, then fallback to normalized."""
    trimmed = raw_alias.strip()
    with engine.connect() as conn:
        row = conn.execute(
            text('''SELECT c.id, c.code, c.name, c.category_code
                      FROM core.certificate c
                      JOIN core.certificate_alias a ON a.certificate_id = c.id
                     WHERE a.alias = :r'''),
            {'r': trimmed},
        ).fetchone()
        if row:
            return dict(row._mapping)
    return lookup_by_normalized_alias(engine, normalize_alias(raw_alias))


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
    return dict(rows[0]._mapping)


class OldCertMapping:
    """Draft mapping: legacy cert_id → (status, v2_code | None, reason)."""

    def __init__(self):
        self._entries: dict[str, dict] = {}

    def add(self, old_id: str, status: str, v2_code: str | None = None, reason: str = ""):
        assert status in ("mapped", "rejected", "needs_review"), f"bad status: {status}"
        self._entries[old_id] = {"old_id": old_id, "status": status, "v2_code": v2_code, "reason": reason}

    def get(self, old_id: str) -> dict:
        return self._entries.get(old_id, {"old_id": old_id, "status": "needs_review", "v2_code": None, "reason": "not yet classified"})

    def all(self) -> list[dict]:
        return list(self._entries.values())


def build_old_cert_mapping(engine: Engine) -> OldCertMapping:
    """Build mapping from legacy cert_ids found in certificate_alias.

    Any legacy alias that resolves to a certificate is 'mapped';
    aliases in the legacy table with no V2 counterpart are 'needs_review'.
    """
    mapping = OldCertMapping()
    with engine.connect() as conn:
        rows = conn.execute(
            text("""
                SELECT a.normalized_alias AS old_id, c.code AS v2_code, c.name AS v2_name
                  FROM core.certificate_alias a
                  JOIN core.certificate c ON c.id = a.certificate_id
                 WHERE a.alias_type = 'common'
            """)
        ).fetchall()
        for row in rows:
            mapping.add(row.old_id, "mapped", row.v2_code, f"→ {row.v2_name}")
    return mapping


def list_certificates(engine: Engine) -> list[dict]:
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT id, code, name, category_code, status FROM core.certificate ORDER BY code")
        ).fetchall()
    return [dict(r._mapping) for r in rows]
