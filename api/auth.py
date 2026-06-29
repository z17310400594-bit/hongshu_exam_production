"""Minimal authorization service — checks collection ACLs.

WP02 scope: organization-level access only.  WP03+ will extend with user/role.
"""

from sqlalchemy import text
from sqlalchemy.engine import Engine


class AuthorizationError(Exception):
    """Raised when a principal is denied access to a resource."""

    def __init__(self, status_code: int = 403, detail: str = "Forbidden"):
        self.status_code = status_code
        self.detail = detail


def check_collection_access(
    engine: Engine,
    principal_type: str,
    principal_code: str,
    collection_code: str,
    required_permission: str = "read",
) -> None:
    """Raise AuthorizationError if the principal lacks the required permission.

    Warning: the error message MUST NOT contain the collection name, title,
    confidentiality level, or internal IDs — only the fact that access was denied.
    """
    with engine.connect() as conn:
        result = conn.execute(
            text("""
                SELECT 1
                  FROM knowledge.collection_acl acl
                  JOIN knowledge.collection c ON c.id = acl.collection_id
                 WHERE c.code = :coll_code
                   AND acl.principal_type = :ptype
                   AND acl.principal_code = :pcode
                   AND acl.permission = :perm
                 LIMIT 1
            """),
            {
                "coll_code": collection_code,
                "ptype": principal_type,
                "pcode": principal_code,
                "perm": required_permission,
            },
        ).fetchone()

    if result is None:
        raise AuthorizationError(
            status_code=403,
            detail="Access denied",
        )
