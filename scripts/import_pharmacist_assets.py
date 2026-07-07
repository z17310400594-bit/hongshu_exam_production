"""Import prepared pharmacist PDFs as V2 knowledge assets.

This script writes only the asset layer:

- knowledge.asset
- knowledge.asset_version
- MinIO object storage

It intentionally does NOT create content chapters, fragments, knowledge-point
mappings, or structured questions. Those require a later parsing/review step.

Run:
    py scripts/import_pharmacist_assets.py --dry-run
    py scripts/import_pharmacist_assets.py --apply
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine

try:
    import fitz  # type: ignore[import-untyped]
except Exception as exc:  # pragma: no cover - local dependency guard
    raise SystemExit("PyMuPDF/fitz is required to extract PDF text before import.") from exc

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.config import settings  # noqa: E402
from api.services.assets import get_minio_client, upload_asset_version  # noqa: E402


DEFAULT_PACKAGE_DIR = ROOT / ".tmp" / "pharmacist_import_package"
DEFAULT_COLLECTION_CODE = "coll_internal"
DEFAULT_STATUS = "draft"
DEFAULT_REVIEW_STATUS = "pending"

OWNER_BY_CATEGORY = {
    "教材": "org_teaching_materials",
    "题库": "org_teaching_aids",
    "考点": "org_teaching_aids",
    "考霸秘籍": "org_teaching_aids",
}


@dataclass(frozen=True)
class ImportResult:
    source_category: str
    subject_code: str
    material_type: str
    asset_code: str
    asset_id: int | str
    asset_version_id: int | str
    upload_status: str
    object_key: str
    content_sha256: str
    notes: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import prepared pharmacist PDFs as V2 assets.")
    parser.add_argument("--package-dir", type=Path, default=DEFAULT_PACKAGE_DIR)
    parser.add_argument("--manifest", type=Path, default=None)
    parser.add_argument("--collection-code", default=DEFAULT_COLLECTION_CODE)
    parser.add_argument("--asset-status", default=DEFAULT_STATUS, choices=["draft", "reviewed", "published", "deprecated"])
    parser.add_argument("--version-review-status", default=DEFAULT_REVIEW_STATUS, choices=["pending", "approved", "rejected"])
    parser.add_argument("--reviewed-by", default=None)
    parser.add_argument("--dry-run", action="store_true", help="Plan only; do not write DB/MinIO.")
    parser.add_argument("--apply", action="store_true", help="Actually write DB/MinIO.")
    parser.add_argument("--report", type=Path, default=None)
    return parser.parse_args()


def load_manifest(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def make_asset_code(row: dict[str, str]) -> str:
    stem = Path(row["normalized_file_name"]).stem
    ascii_part = "_".join(
        part
        for part in [
            "pharm",
            str(row.get("year") or "2026"),
            row.get("subject_code") or "unknown_subject",
            row.get("material_type") or "material",
            (row.get("file_sha256") or "")[:12],
        ]
        if part
    )
    ascii_part = re.sub(r"[^a-zA-Z0-9_]+", "_", ascii_part).strip("_").lower()
    return ascii_part or re.sub(r"[^a-zA-Z0-9_]+", "_", stem).strip("_").lower()


def make_title(row: dict[str, str]) -> str:
    return " - ".join(
        part
        for part in [
            row.get("cert_name") or "执业药师",
            row.get("track"),
            row.get("subject_name"),
            row.get("material_type"),
            row.get("version_label"),
        ]
        if part
    )


def extract_pdf_text(path: Path) -> str:
    doc = fitz.open(str(path))
    parts: list[str] = []
    for index, page in enumerate(doc, start=1):
        text_value = page.get_text().strip()
        if text_value:
            parts.append(f"[[page:{index}]]\n{text_value}")
    return "\n\n".join(parts)


def ensure_asset(
    conn: Connection,
    *,
    code: str,
    row: dict[str, str],
    collection_code: str,
    asset_status: str,
) -> int:
    owner_org_code = OWNER_BY_CATEGORY.get(row.get("source_category") or "", "org_teaching_aids")
    allowed_use = [item.strip() for item in (row.get("allowed_use") or "retrieval,generation").split(",") if item.strip()]
    inserted = conn.execute(
        text(
            """
            WITH refs AS (
                SELECT c.id AS collection_id, o.id AS owner_org_id
                  FROM knowledge.collection c
                  JOIN iam.organization_unit o ON o.code = :owner_org_code
                 WHERE c.code = :collection_code
            )
            INSERT INTO knowledge.asset (
                code, asset_type, title, collection_id, owner_org_id,
                confidentiality, copyright_owner, allowed_use, status
            )
            SELECT :code, :asset_type, :title, collection_id, owner_org_id,
                   :confidentiality, :copyright_owner, :allowed_use, :status
              FROM refs
            ON CONFLICT (code) DO UPDATE SET
                title = EXCLUDED.title,
                asset_type = EXCLUDED.asset_type,
                confidentiality = EXCLUDED.confidentiality,
                copyright_owner = EXCLUDED.copyright_owner,
                allowed_use = EXCLUDED.allowed_use,
                status = EXCLUDED.status,
                updated_at = now()
            RETURNING id
            """
        ),
        {
            "code": code,
            "asset_type": row["asset_type"],
            "title": make_title(row),
            "collection_code": collection_code,
            "owner_org_code": owner_org_code,
            "confidentiality": row.get("confidentiality") or "internal",
            "copyright_owner": row.get("copyright_owner") or None,
            "allowed_use": allowed_use,
            "status": asset_status,
        },
    ).fetchone()
    if inserted is None:
        raise ValueError(f"Cannot resolve collection/org refs for asset {code}")
    return int(inserted.id)


def asset_has_version(conn: Connection, *, asset_id: int, version_no: int) -> tuple[int, str, str] | None:
    row = conn.execute(
        text(
            """
            SELECT id, object_key, content_sha256
              FROM knowledge.asset_version
             WHERE asset_id = :asset_id
               AND version_no = :version_no
            """
        ),
        {"asset_id": asset_id, "version_no": version_no},
    ).fetchone()
    if row is None:
        return None
    return int(row.id), str(row.object_key or ""), str(row.content_sha256 or "")


def import_assets(args: argparse.Namespace, rows: list[dict[str, str]]) -> list[ImportResult]:
    engine: Engine = create_engine(settings.database_url)
    client = get_minio_client()
    results: list[ImportResult] = []

    for row in rows:
        file_path = Path(row["output_path"])
        asset_code = make_asset_code(row)
        version_no = 1

        if args.dry_run:
            results.append(
                ImportResult(
                    source_category=row["source_category"],
                    subject_code=row["subject_code"],
                    material_type=row["material_type"],
                    asset_code=asset_code,
                    asset_id="dry-run",
                    asset_version_id="dry-run",
                    upload_status="planned",
                    object_key="",
                    content_sha256=row.get("file_sha256", ""),
                    notes=str(file_path),
                )
            )
            continue

        if not file_path.exists():
            raise FileNotFoundError(file_path)

        extracted_text = extract_pdf_text(file_path)
        content = file_path.read_bytes()

        with engine.begin() as conn:
            asset_id = ensure_asset(
                conn,
                code=asset_code,
                row=row,
                collection_code=args.collection_code,
                asset_status=args.asset_status,
            )
            existing_version = asset_has_version(conn, asset_id=asset_id, version_no=version_no)

        if existing_version is not None:
            version_id, object_key, digest = existing_version
            results.append(
                ImportResult(
                    source_category=row["source_category"],
                    subject_code=row["subject_code"],
                    material_type=row["material_type"],
                    asset_code=asset_code,
                    asset_id=asset_id,
                    asset_version_id=version_id,
                    upload_status="exists",
                    object_key=object_key,
                    content_sha256=digest,
                    notes="asset version already exists",
                )
            )
            continue

        uploaded = upload_asset_version(
            engine,
            client=client,
            bucket=settings.minio_bucket,
            asset_code=asset_code,
            version_no=version_no,
            content=content,
            mime_type="application/pdf",
            extracted_text=extracted_text,
            review_status=args.version_review_status,
            reviewed_by=args.reviewed_by,
        )
        results.append(
            ImportResult(
                source_category=row["source_category"],
                subject_code=row["subject_code"],
                material_type=row["material_type"],
                asset_code=asset_code,
                asset_id=asset_id,
                asset_version_id=uploaded.asset_version_id,
                upload_status=uploaded.status,
                object_key=uploaded.object_key,
                content_sha256=uploaded.content_sha256,
                notes=f"pages/text imported from {file_path.name}",
            )
        )

    return results


def write_report(path: Path, results: list[ImportResult]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(ImportResult.__dataclass_fields__))
        writer.writeheader()
        for result in results:
            writer.writerow(result.__dict__)


def main() -> int:
    args = parse_args()
    if args.dry_run and args.apply:
        raise SystemExit("Choose only one of --dry-run or --apply")
    if not args.dry_run and not args.apply:
        raise SystemExit("Pass --dry-run to preview or --apply to import")

    manifest = args.manifest or args.package_dir / "manifest.csv"
    report = args.report or args.package_dir / ("asset_import_dry_run.csv" if args.dry_run else "asset_import_report.csv")
    rows = load_manifest(manifest)
    results = import_assets(args, rows)
    write_report(report, results)

    created = sum(1 for result in results if result.upload_status == "created")
    exists = sum(1 for result in results if result.upload_status == "exists")
    planned = sum(1 for result in results if result.upload_status == "planned")
    print(f"rows={len(results)} planned={planned} created={created} exists={exists}")
    print(f"report={report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
