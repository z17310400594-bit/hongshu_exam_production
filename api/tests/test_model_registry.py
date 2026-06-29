"""Model registry tests.

These catch false-green Alembic checks where a migration imports model modules
manually but the package-level registry is empty in a fresh Python process.
"""

from api.models import Base


def test_api_models_import_registers_all_current_tables():
    assert {
        "core.certificate",
        "core.certificate_alias",
        "core.exam_subject",
        "iam.organization_unit",
        "knowledge.asset",
        "knowledge.asset_version",
        "knowledge.collection",
        "knowledge.collection_acl",
        "knowledge.fragment",
    }.issubset(Base.metadata.tables)
