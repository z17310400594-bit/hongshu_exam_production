"""FastAPI dependencies — identity extraction and authorization."""

from typing import Annotated

from fastapi import Depends, Header

from api.auth import AuthorizationError, check_collection_access
from api.main import sync_engine


async def get_current_principal(
    x_org_code: Annotated[str | None, Header(alias="X-Org-Code", include_in_schema=False)] = None,
) -> dict:
    """Extract caller identity from the X-Org-Code request header."""
    if not x_org_code:
        raise AuthorizationError(status_code=401, detail="Missing X-Org-Code header")
    return {"principal_type": "org", "principal_code": x_org_code}


def require_collection_read(collection_code: str):
    """FastAPI dependency factory: check collection ACL for the current principal.

    Usage:
        @app.get("/collections/{code}")
        async def get_collection(code: str, _=Depends(require_collection_read(code))):
            ...
    """

    async def _check(principal: Annotated[dict, Depends(get_current_principal)]):
        check_collection_access(
            sync_engine,
            principal_type=principal["principal_type"],
            principal_code=principal["principal_code"],
            collection_code=collection_code,
            required_permission="read",
        )

    return Depends(_check)
