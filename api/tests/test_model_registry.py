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
        "assessment.exam_event",
        "assessment.exam_phase",
        "assessment.paper",
        "assessment.question",
        "assessment.question_knowledge_point",
        "assessment.subject_score_rule",
        "content.chapter",
        "content.chapter_knowledge_point",
        "content.product",
        "content.product_version",
        "generation.citation",
        "generation.output",
        "generation.run",
        "iam.organization_unit",
        "ingestion.import_batch",
        "ingestion.validation_error",
        "knowledge.asset",
        "knowledge.asset_version",
        "knowledge.collection",
        "knowledge.collection_acl",
        "knowledge.fragment",
        "knowledge.fragment_knowledge_point",
        "knowledge.knowledge_point",
        "knowledge.knowledge_point_relation",
        "knowledge.knowledge_point_scope",
        "policy.clause",
        "policy.document",
        "policy.document_version",
        "policy.eligibility_rule",
        "policy.eligibility_rule_evidence",
    }.issubset(Base.metadata.tables)
