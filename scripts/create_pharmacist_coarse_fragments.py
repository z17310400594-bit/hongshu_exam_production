"""Create coarse MVP fragments for imported 2026 pharmacist assets.

This is intentionally not chapter parsing. It turns each extracted PDF text into
medium-sized, reviewable fragments so the existing generation/citation pipeline
can use the material before detailed chapter/KP mapping exists.

Run:
    py scripts/create_pharmacist_coarse_fragments.py --dry-run
    py scripts/create_pharmacist_coarse_fragments.py --apply --approve-for-generation
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.config import settings  # noqa: E402

DEFAULT_ASSET_PREFIX = "pharm_2026_%"
DEFAULT_KP_CODE = "pharm_2026_general"
DEFAULT_REVIEWER = "pharmacist_coarse_fragment_script"
DEFAULT_REPORT = ROOT / ".tmp" / "pharmacist_import_package" / "coarse_fragment_report.csv"

NOISE_PATTERNS = (
    "版权所有",
    "版权",
    "责任编辑",
    "图书在版编目",
    "isbn",
    "目录",
    "目 录",
    "contents",
    "仅供",
)


@dataclass(frozen=True)
class FragmentPlan:
    asset_code: str
    asset_title: str
    asset_version_id: int
    fragment_code: str
    sequence_no: int
    heading: str
    content: str


@dataclass(frozen=True)
class FragmentResult:
    asset_code: str
    fragment_code: str
    sequence_no: int
    char_count: int
    status: str
    notes: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create coarse pharmacist fragments from extracted asset text.")
    parser.add_argument("--asset-prefix", default=DEFAULT_ASSET_PREFIX)
    parser.add_argument("--kp-code", default=DEFAULT_KP_CODE)
    parser.add_argument("--chunk-size", type=int, default=4200)
    parser.add_argument("--overlap", type=int, default=250)
    parser.add_argument("--min-chars", type=int, default=900)
    parser.add_argument("--max-fragments-per-asset", type=int, default=40)
    parser.add_argument("--reviewed-by", default=DEFAULT_REVIEWER)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument(
        "--approve-for-generation",
        action="store_true",
        help="Set imported pharmacist assets to published and versions to approved for generation MVP.",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--apply", action="store_true")
    return parser.parse_args()


def normalize_text(value: str) -> str:
    value = value.replace("\u3000", " ")
    value = re.sub(r"\r\n?", "\n", value)
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def is_noisy_chunk(chunk: str, min_chars: int) -> bool:
    compact = re.sub(r"\s+", "", chunk).lower()
    if len(compact) < min_chars:
        return True
    if compact.count(".") + compact.count("_") > len(compact) * 0.08:
        return True
    if sum(1 for pattern in NOISE_PATTERNS if pattern in compact) >= 2:
        return True
    if compact.startswith("目录") and len(compact) < min_chars * 3:
        return True
    return False


def chunk_text(text_value: str, *, chunk_size: int, overlap: int, min_chars: int, max_chunks: int) -> list[str]:
    normalized = normalize_text(text_value)
    if not normalized:
        return []

    chunks: list[str] = []
    cursor = 0
    while cursor < len(normalized) and len(chunks) < max_chunks:
        end = min(cursor + chunk_size, len(normalized))
        if end < len(normalized):
            boundary = max(normalized.rfind("\n\n", cursor, end), normalized.rfind("。", cursor, end))
            if boundary > cursor + min_chars:
                end = boundary + 1
        chunk = normalized[cursor:end].strip()
        if not is_noisy_chunk(chunk, min_chars):
            chunks.append(chunk)
        if end >= len(normalized):
            break
        cursor = max(end - overlap, cursor + min_chars)
    return chunks


def load_asset_versions(conn: Connection, asset_prefix: str) -> list[dict[str, object]]:
    rows = conn.execute(
        text(
            """
            SELECT
                a.id AS asset_id,
                a.code AS asset_code,
                a.title AS asset_title,
                av.id AS asset_version_id,
                av.extracted_text
              FROM knowledge.asset a
              JOIN knowledge.asset_version av ON av.asset_id = a.id
             WHERE a.code LIKE :asset_prefix
               AND av.version_no = 1
               AND coalesce(av.extracted_text, '') <> ''
             ORDER BY a.code
            """
        ),
        {"asset_prefix": asset_prefix},
    ).fetchall()
    return [dict(row._mapping) for row in rows]


def build_plans(engine: Engine, args: argparse.Namespace) -> list[FragmentPlan]:
    with engine.connect() as conn:
        rows = load_asset_versions(conn, args.asset_prefix)

    plans: list[FragmentPlan] = []
    for row in rows:
        chunks = chunk_text(
            str(row["extracted_text"]),
            chunk_size=args.chunk_size,
            overlap=args.overlap,
            min_chars=args.min_chars,
            max_chunks=args.max_fragments_per_asset,
        )
        for index, chunk in enumerate(chunks, start=1):
            plans.append(
                FragmentPlan(
                    asset_code=str(row["asset_code"]),
                    asset_title=str(row["asset_title"]),
                    asset_version_id=int(row["asset_version_id"]),
                    fragment_code=f"coarse_{index:04d}",
                    sequence_no=index,
                    heading=f"{row['asset_title']}｜粗切片 {index:04d}",
                    content=chunk,
                )
            )
    return plans


def ensure_general_kp(conn: Connection, *, kp_code: str) -> int:
    row = conn.execute(
        text(
            """
            INSERT INTO knowledge.knowledge_point (
                code, name, domain_code, cognitive_level, description, status
            )
            VALUES (
                :code, '执业药师通用备考资料', 'pharmacist',
                'understand', 'MVP 粗切片通用知识点，用于章节解析完成前的随机取材生成。', 'active'
            )
            ON CONFLICT (code) DO UPDATE SET
                name = EXCLUDED.name,
                domain_code = EXCLUDED.domain_code,
                description = EXCLUDED.description,
                status = 'active',
                merged_into_kp_id = NULL
            RETURNING id
            """
        ),
        {"code": kp_code},
    ).fetchone()
    if row is None:
        raise RuntimeError(f"Failed to ensure knowledge point {kp_code}")
    return int(row.id)


def approve_assets_for_generation(conn: Connection, *, asset_prefix: str, reviewed_by: str) -> None:
    conn.execute(
        text(
            """
            UPDATE knowledge.asset
               SET status = 'published',
                   updated_at = now()
             WHERE code LIKE :asset_prefix
            """
        ),
        {"asset_prefix": asset_prefix},
    )
    conn.execute(
        text(
            """
            UPDATE knowledge.asset_version av
               SET review_status = 'approved',
                   reviewed_by = :reviewed_by,
                   reviewed_at = now()
              FROM knowledge.asset a
             WHERE a.id = av.asset_id
               AND a.code LIKE :asset_prefix
            """
        ),
        {"asset_prefix": asset_prefix, "reviewed_by": reviewed_by},
    )


def apply_plans(engine: Engine, plans: list[FragmentPlan], args: argparse.Namespace) -> list[FragmentResult]:
    results: list[FragmentResult] = []
    with engine.begin() as conn:
        kp_id = ensure_general_kp(conn, kp_code=args.kp_code)
        if args.approve_for_generation:
            approve_assets_for_generation(conn, asset_prefix=args.asset_prefix, reviewed_by=args.reviewed_by)

        for plan in plans:
            fragment_row = conn.execute(
                text(
                    """
                    INSERT INTO knowledge.fragment (
                        asset_version_id, fragment_code, fragment_type,
                        sequence_no, heading, content
                    )
                    VALUES (
                        :asset_version_id, :fragment_code, 'section',
                        :sequence_no, :heading, :content
                    )
                    ON CONFLICT (asset_version_id, fragment_code) DO UPDATE SET
                        sequence_no = EXCLUDED.sequence_no,
                        heading = EXCLUDED.heading,
                        content = EXCLUDED.content
                    RETURNING id
                    """
                ),
                {
                    "asset_version_id": plan.asset_version_id,
                    "fragment_code": plan.fragment_code,
                    "sequence_no": plan.sequence_no,
                    "heading": plan.heading,
                    "content": plan.content,
                },
            ).fetchone()
            if fragment_row is None:
                raise RuntimeError(f"Failed to upsert fragment {plan.asset_code}/{plan.fragment_code}")

            conn.execute(
                text(
                    """
                    INSERT INTO knowledge.fragment_knowledge_point (
                        fragment_id, kp_id, relation_role, confidence,
                        review_status, reviewed_by
                    )
                    VALUES (
                        :fragment_id, :kp_id, 'evidence', 0.600,
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
                FragmentResult(
                    asset_code=plan.asset_code,
                    fragment_code=plan.fragment_code,
                    sequence_no=plan.sequence_no,
                    char_count=len(plan.content),
                    status="upserted",
                    notes=plan.heading,
                )
            )
    return results


def write_report(path: Path, rows: list[FragmentResult]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(FragmentResult.__dataclass_fields__))
        writer.writeheader()
        for row in rows:
            writer.writerow(row.__dict__)


def main() -> int:
    args = parse_args()
    if args.dry_run and args.apply:
        raise SystemExit("Choose only one of --dry-run or --apply")
    if not args.dry_run and not args.apply:
        raise SystemExit("Pass --dry-run to preview or --apply to write fragments")
    if args.overlap >= args.chunk_size:
        raise SystemExit("--overlap must be smaller than --chunk-size")

    engine = create_engine(settings.database_url)
    plans = build_plans(engine, args)
    if args.dry_run:
        results = [
            FragmentResult(
                asset_code=plan.asset_code,
                fragment_code=plan.fragment_code,
                sequence_no=plan.sequence_no,
                char_count=len(plan.content),
                status="planned",
                notes=plan.heading,
            )
            for plan in plans
        ]
    else:
        results = apply_plans(engine, plans, args)
    write_report(args.report, results)

    asset_count = len({row.asset_code for row in results})
    print(f"assets={asset_count} fragments={len(results)} mode={'dry-run' if args.dry_run else 'apply'}")
    print(f"report={args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
