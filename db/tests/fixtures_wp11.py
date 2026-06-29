"""WP11 fixtures — import validation batches."""

from __future__ import annotations

VALID_HASH = "a" * 64
INVALID_HASH = "b" * 64
WARN_HASH = "c" * 64


VALID_FIXTURE = {
    "filename": "valid/certificate.csv",
    "content_sha256": VALID_HASH,
    "imported_by": "org_teaching_materials",
    "total_rows": 2,
    "validation_errors": [],
}

INVALID_FIXTURE = {
    "filename": "invalid/duplicate_alias.csv",
    "content_sha256": INVALID_HASH,
    "imported_by": "org_teaching_materials",
    "total_rows": 3,
    "validation_errors": [
        {
            "row_number": 2,
            "row_key": "一建",
            "field_name": "normalized_alias",
            "error_code": "UQ_CERTIFICATE_ALIAS",
            "error_message": "normalized alias must be unique",
            "severity": "P1",
        },
        {
            "row_number": 3,
            "row_key": "BAD_RULE",
            "field_name": "evidence_code",
            "error_code": "FK_RULE_EVIDENCE",
            "error_message": "rule evidence target not found",
            "severity": "P0",
        },
    ],
}

WARN_FIXTURE = {
    "filename": "invalid/needs_review.csv",
    "content_sha256": WARN_HASH,
    "imported_by": "org_teaching_materials",
    "total_rows": 1,
    "validation_errors": [
        {
            "row_number": 1,
            "row_key": "UNCERTAIN_CERT",
            "field_name": "exam_authority",
            "error_code": "NEEDS_BUSINESS_REVIEW",
            "error_message": "exam authority needs business confirmation",
            "severity": "P2",
        }
    ],
}
