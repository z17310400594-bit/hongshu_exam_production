"""Import cleaned Xi Yao 1 Markdown files into V2 knowledge tables.

This is a DB-only ingestion path for parser validation. It deliberately avoids
MinIO so cleaned Markdown can be tested without changing the existing PDF asset
pipeline.

Run:
    py scripts/import_xi_yao_1_cleaned_markdown.py --dry-run
    py scripts/import_xi_yao_1_cleaned_markdown.py --apply
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.config import settings  # noqa: E402


DEFAULT_SOURCE_DIR = Path("C:/Users/Administrator/Desktop/" + "\u897f\u836f1")
DEFAULT_COLLECTION_CODE = "coll_internal"
DEFAULT_OWNER_ORG_CODE = "org_teaching_materials"
DEFAULT_REVIEWER = "xi_yao_1_cleaned_markdown_import"
DEFAULT_REPORT = ROOT / ".tmp" / "xi_yao_1_cleaned_import_report.csv"
KP_CODE = "xi_yao_1_cleaned_general"

MATERIALS = {
    "textbook": {
        "file": "2026\u897f\u836f\u4e00\u6559\u6750.cleaned.md",
        "asset_type": "textbook",
        "title": "2026\u897f\u836f\u4e00\u6559\u6750\uff08\u6e05\u6d17\u7248\uff09",
    },
    "handout": {
        "file": "2026\u897f\u836f\u4e00\u8bb2\u4e49.cleaned.md",
        "asset_type": "handout",
        "title": "2026\u897f\u836f\u4e00\u8bb2\u4e49\uff08\u6e05\u6d17\u7248\uff09",
    },
    "exam_2022": {
        "file": "2022\u897f\u836f\u4e00\u771f\u9898 \uff08\u56de\u5fc6\u5b8c\u6574\u7248\uff09.cleaned.md",
        "asset_type": "paper",
        "title": "2022\u897f\u836f\u4e00\u771f\u9898\uff08\u6e05\u6d17\u7248\uff09",
    },
    "exam_2023": {
        "file": "2023\u897f\u836f\u4e00\u771f\u9898.cleaned.md",
        "asset_type": "paper",
        "title": "2023\u897f\u836f\u4e00\u771f\u9898\uff08\u6e05\u6d17\u7248\uff09",
    },
    "exam_2024": {
        "file": "2024\u897f\u836f\u4e00\u771f\u9898.cleaned.md",
        "asset_type": "paper",
        "title": "2024\u897f\u836f\u4e00\u771f\u9898\uff08\u6e05\u6d17\u7248\uff09",
    },
    "exam_2025": {
        "file": "2025\u897f\u836f\u5b66\u4e00\u771f\u9898\uff08\u56de\u5fc6\u7248\uff09.cleaned.md",
        "asset_type": "paper",
        "title": "2025\u897f\u836f\u5b66\u4e00\u771f\u9898\uff08\u6e05\u6d17\u7248\uff09",
    },
}


@dataclass(frozen=True)
class ChunkPlan:
    material_key: str
    asset_code: str
    title: str
    asset_type: str
    content_sha256: str
    source_path: Path
    fragment_code: str
    sequence_no: int
    heading: str
    content: str
    page_from: int | None
    page_to: int | None


@dataclass(frozen=True)
class ImportResult:
    material_key: str
    asset_code: str
    fragment_code: str
    sequence_no: int
    page_from: int | None
    page_to: int | None
    char_count: int
    status: str
    heading: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import cleaned Xi Yao 1 Markdown into V2 knowledge tables.")
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--cleaned-dir", type=Path, default=None)
    parser.add_argument("--collection-code", default=DEFAULT_COLLECTION_CODE)
    parser.add_argument("--owner-org-code", default=DEFAULT_OWNER_ORG_CODE)
    parser.add_argument("--reviewed-by", default=DEFAULT_REVIEWER)
    parser.add_argument("--chunk-size", type=int, default=1600)
    parser.add_argument("--overlap", type=int, default=120)
    parser.add_argument("--min-chars", type=int, default=120)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--only", nargs="*", choices=sorted(MATERIALS), default=None)
    return parser.parse_args()


def latest_cleaned_dir(source_dir: Path) -> Path:
    candidates = [path for path in source_dir.glob("\u6e05\u6d17\u540e_*") if path.is_dir()]
    if not candidates:
        raise SystemExit(f"no cleaned dir found under {source_dir}; run clean_xi_yao_1_pdfs.py first")
    return max(candidates, key=lambda path: path.stat().st_mtime)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_text(value: str) -> str:
    value = value.replace("\u3000", " ")
    value = re.sub(r"\r\n?", "\n", value)
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def iter_page_blocks(markdown: str) -> list[tuple[int | None, str]]:
    blocks: list[tuple[int | None, str]] = []
    current_page: int | None = None
    current: list[str] = []
    for line in markdown.splitlines():
        match = re.fullmatch(r"\[\[page:(\d+)\]\]", line.strip())
        if match:
            if current:
                blocks.append((current_page, normalize_text("\n".join(current))))
            current_page = int(match.group(1))
            current = []
            continue
        if line.startswith("# "):
            continue
        current.append(line)
    if current:
        blocks.append((current_page, normalize_text("\n".join(current))))
    return [(page, text_value) for page, text_value in blocks if text_value]


def split_text(text_value: str, *, chunk_size: int, overlap: int, min_chars: int) -> list[str]:
    text_value = normalize_text(text_value)
    if len(text_value) <= chunk_size:
        return [text_value] if len(text_value) >= min_chars else []

    chunks: list[str] = []
    cursor = 0
    while cursor < len(text_value):
        end = min(cursor + chunk_size, len(text_value))
        if end < len(text_value):
            boundaries = [
                text_value.rfind("\n\n", cursor, end),
                text_value.rfind("\n", cursor, end),
                text_value.rfind("\u3002", cursor, end),
                text_value.rfind("\uff1b", cursor, end),
            ]
            boundary = max(boundaries)
            if boundary > cursor + min_chars:
                end = boundary + 1
        chunk = text_value[cursor:end].strip()
        if len(chunk) >= min_chars:
            chunks.append(chunk)
        if end >= len(text_value):
            break
        cursor = max(end - overlap, cursor + min_chars)
    return chunks


def guess_heading(content: str) -> str:
    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue
        if len(line) <= 60:
            return line
        return line[:60]
    return ""


def build_plans(args: argparse.Namespace) -> list[ChunkPlan]:
    cleaned_dir = args.cleaned_dir or latest_cleaned_dir(args.source_dir)
    keys = args.only or list(MATERIALS)
    plans: list[ChunkPlan] = []
    for key in keys:
        meta = MATERIALS[key]
        source_path = cleaned_dir / str(meta["file"])
        if not source_path.exists():
            print(f"skip missing: {source_path}")
            continue
        content = source_path.read_text(encoding="utf-8")
        digest = file_sha256(source_path)
        asset_code = f"xi_yao_1_cleaned_{key}_{digest[:12]}"
        sequence_no = 0
        for page_no, page_text in iter_page_blocks(content):
            for chunk in split_text(page_text, chunk_size=args.chunk_size, overlap=args.overlap, min_chars=args.min_chars):
                sequence_no += 1
                plans.append(
                    ChunkPlan(
                        material_key=key,
                        asset_code=asset_code,
                        title=str(meta["title"]),
                        asset_type=str(meta["asset_type"]),
                        content_sha256=digest,
                        source_path=source_path,
                        fragment_code=f"cleaned_{sequence_no:04d}",
                        sequence_no=sequence_no,
                        heading=guess_heading(chunk),
                        content=chunk,
                        page_from=page_no,
                        page_to=page_no,
                    )
                )
    return plans


def ensure_refs(conn: Connection, *, collection_code: str, owner_org_code: str) -> tuple[int, int]:
    row = conn.execute(
        text(
            """
            SELECT c.id AS collection_id, o.id AS owner_org_id
              FROM knowledge.collection c
              JOIN iam.organization_unit o ON o.code = :owner_org_code
             WHERE c.code = :collection_code
            """
        ),
        {"collection_code": collection_code, "owner_org_code": owner_org_code},
    ).fetchone()
    if row is None:
        raise RuntimeError(f"missing collection/org refs: {collection_code}, {owner_org_code}")
    return int(row.collection_id), int(row.owner_org_id)


def ensure_kp(conn: Connection, *, reviewed_by: str) -> int:
    row = conn.execute(
        text(
            """
            INSERT INTO knowledge.knowledge_point (
                code, name, domain_code, cognitive_level, description, status
            )
            VALUES (
                :code, :name, 'pharmacist', 'understand',
                :description, 'active'
            )
            ON CONFLICT (code) DO UPDATE SET
                name = EXCLUDED.name,
                domain_code = EXCLUDED.domain_code,
                cognitive_level = EXCLUDED.cognitive_level,
                description = EXCLUDED.description,
                status = 'active',
                merged_into_kp_id = NULL
            RETURNING id
            """
        ),
        {
            "code": KP_CODE,
            "name": "\u897f\u836f\u4e00\u6e05\u6d17\u8d44\u6599\u901a\u7528\u8003\u70b9",
            "description": "\u6e05\u6d17\u540e\u6559\u6750\u3001\u8bb2\u4e49\u3001\u771f\u9898\u7247\u6bb5\u7684MVP\u901a\u7528\u6302\u8f7d\u70b9\u3002",
        },
    ).fetchone()
    if row is None:
        raise RuntimeError(f"failed to ensure KP {KP_CODE}")

    kp_id = int(row.id)
    for scope_type, scope_code in [
        ("certificate", "pharmacist_licensed"),
        ("exam_subject", "pharmacist_west_1"),
    ]:
        conn.execute(
            text(
                """
                INSERT INTO knowledge.knowledge_point_scope (kp_id, scope_type, scope_code)
                VALUES (:kp_id, :scope_type, :scope_code)
                ON CONFLICT (kp_id, scope_type, scope_code) DO NOTHING
                """
            ),
            {"kp_id": kp_id, "scope_type": scope_type, "scope_code": scope_code},
        )
    return kp_id


def apply_plans(args: argparse.Namespace, plans: list[ChunkPlan]) -> list[ImportResult]:
    engine = create_engine(settings.database_url)
    results: list[ImportResult] = []
    grouped: dict[str, list[ChunkPlan]] = {}
    for plan in plans:
        grouped.setdefault(plan.asset_code, []).append(plan)

    with engine.begin() as conn:
        collection_id, owner_org_id = ensure_refs(conn, collection_code=args.collection_code, owner_org_code=args.owner_org_code)
        kp_id = ensure_kp(conn, reviewed_by=args.reviewed_by)

        for asset_code, asset_plans in grouped.items():
            first = asset_plans[0]
            asset_row = conn.execute(
                text(
                    """
                    INSERT INTO knowledge.asset (
                        code, asset_type, title, collection_id, owner_org_id,
                        confidentiality, copyright_owner, allowed_use, status
                    )
                    VALUES (
                        :code, :asset_type, :title, :collection_id, :owner_org_id,
                        'internal', NULL, ARRAY['retrieval','generation']::text[], 'published'
                    )
                    ON CONFLICT (code) DO UPDATE SET
                        title = EXCLUDED.title,
                        asset_type = EXCLUDED.asset_type,
                        status = 'published',
                        allowed_use = EXCLUDED.allowed_use,
                        updated_at = now()
                    RETURNING id
                    """
                ),
                {
                    "code": first.asset_code,
                    "asset_type": first.asset_type,
                    "title": first.title,
                    "collection_id": collection_id,
                    "owner_org_id": owner_org_id,
                },
            ).fetchone()
            if asset_row is None:
                raise RuntimeError(f"failed to upsert asset {asset_code}")
            asset_id = int(asset_row.id)
            extracted_text = first.source_path.read_text(encoding="utf-8")
            version_row = conn.execute(
                text(
                    """
                    INSERT INTO knowledge.asset_version (
                        asset_id, version_no, object_key, mime_type, extracted_text,
                        content_sha256, review_status, reviewed_by, reviewed_at
                    )
                    VALUES (
                        :asset_id, 1, NULL, 'text/markdown', :extracted_text,
                        :content_sha256, 'approved', :reviewed_by, now()
                    )
                    ON CONFLICT (asset_id, version_no) DO UPDATE SET
                        reviewed_by = EXCLUDED.reviewed_by
                    RETURNING id
                    """
                ),
                {
                    "asset_id": asset_id,
                    "extracted_text": extracted_text,
                    "content_sha256": first.content_sha256,
                    "reviewed_by": args.reviewed_by,
                },
            ).fetchone()
            if version_row is None:
                raise RuntimeError(f"failed to upsert asset version {asset_code}")
            asset_version_id = int(version_row.id)

            for plan in asset_plans:
                fragment_row = conn.execute(
                    text(
                        """
                        INSERT INTO knowledge.fragment (
                            asset_version_id, fragment_code, fragment_type, sequence_no,
                            heading, content, page_from, page_to
                        )
                        VALUES (
                            :asset_version_id, :fragment_code, 'section', :sequence_no,
                            :heading, :content, :page_from, :page_to
                        )
                        ON CONFLICT (asset_version_id, fragment_code) DO UPDATE SET
                            sequence_no = EXCLUDED.sequence_no,
                            heading = EXCLUDED.heading,
                            content = EXCLUDED.content,
                            page_from = EXCLUDED.page_from,
                            page_to = EXCLUDED.page_to
                        RETURNING id
                        """
                    ),
                    {
                        "asset_version_id": asset_version_id,
                        "fragment_code": plan.fragment_code,
                        "sequence_no": plan.sequence_no,
                        "heading": plan.heading,
                        "content": plan.content,
                        "page_from": plan.page_from,
                        "page_to": plan.page_to,
                    },
                ).fetchone()
                if fragment_row is None:
                    raise RuntimeError(f"failed to upsert fragment {asset_code}/{plan.fragment_code}")
                conn.execute(
                    text(
                        """
                        INSERT INTO knowledge.fragment_knowledge_point (
                            fragment_id, kp_id, relation_role, confidence,
                            review_status, reviewed_by
                        )
                        VALUES (
                            :fragment_id, :kp_id, 'evidence', 0.700,
                            'approved', :reviewed_by
                        )
                        ON CONFLICT (fragment_id, kp_id, relation_role) DO UPDATE SET
                            confidence = EXCLUDED.confidence,
                            review_status = 'approved',
                            reviewed_by = EXCLUDED.reviewed_by
                        """
                    ),
                    {"fragment_id": int(fragment_row.id), "kp_id": kp_id, "reviewed_by": args.reviewed_by},
                )
                results.append(
                    ImportResult(
                        material_key=plan.material_key,
                        asset_code=plan.asset_code,
                        fragment_code=plan.fragment_code,
                        sequence_no=plan.sequence_no,
                        page_from=plan.page_from,
                        page_to=plan.page_to,
                        char_count=len(plan.content),
                        status="upserted",
                        heading=plan.heading,
                    )
                )
    return results


def dry_run_results(plans: list[ChunkPlan]) -> list[ImportResult]:
    return [
        ImportResult(
            material_key=plan.material_key,
            asset_code=plan.asset_code,
            fragment_code=plan.fragment_code,
            sequence_no=plan.sequence_no,
            page_from=plan.page_from,
            page_to=plan.page_to,
            char_count=len(plan.content),
            status="planned",
            heading=plan.heading,
        )
        for plan in plans
    ]


def write_report(path: Path, rows: list[ImportResult]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(ImportResult.__dataclass_fields__))
        writer.writeheader()
        for row in rows:
            writer.writerow(row.__dict__)


def main() -> int:
    args = parse_args()
    if args.dry_run and args.apply:
        raise SystemExit("Choose only one of --dry-run or --apply")
    if not args.dry_run and not args.apply:
        raise SystemExit("Pass --dry-run to preview or --apply to write DB rows")
    if args.overlap >= args.chunk_size:
        raise SystemExit("--overlap must be smaller than --chunk-size")

    plans = build_plans(args)
    results = dry_run_results(plans) if args.dry_run else apply_plans(args, plans)
    write_report(args.report, results)

    assets = len({row.asset_code for row in results})
    print(f"assets={assets} fragments={len(results)} mode={'dry-run' if args.dry_run else 'apply'}")
    print(f"report={args.report}")
    for asset_code in sorted({row.asset_code for row in results}):
        count = sum(1 for row in results if row.asset_code == asset_code)
        print(f"{asset_code}: fragments={count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
