"""Prepare pharmacist source files for V2 import.

This script does NOT write to the database. It turns a local folder dump into a
reviewable import package:

- files/: normalized file copies
- manifest.csv: asset/content/question-bank import metadata
- needs_review.csv: files that need a human decision before import
- README.md: run summary and next-step guidance

Default input folders match the current Windows desktop layout:

    C:/Users/Administrator/Desktop/教材
    C:/Users/Administrator/Desktop/题库
    C:/Users/Administrator/Desktop/考点
    C:/Users/Administrator/Desktop/考霸秘籍

Run:
    py scripts/prepare_pharmacist_files.py --dry-run
    py scripts/prepare_pharmacist_files.py
    py scripts/prepare_pharmacist_files.py --source 教材=C:/path/to/教材 --source 题库=C:/path/to/题库
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import re
import shutil
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

try:
    import fitz  # type: ignore[import-untyped]
except Exception:  # pragma: no cover - optional local dependency
    fitz = None


CERT_CODE = "pharmacist_licensed"
CERT_NAME = "执业药师"
DEFAULT_YEAR = 2026
DEFAULT_CONFIDENTIALITY = "internal"
DEFAULT_COPYRIGHT_OWNER = "待确认"
DEFAULT_ALLOWED_USE = "retrieval,generation"

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT / ".tmp" / "pharmacist_import_package"

DEFAULT_SOURCES = {
    "教材": Path(r"C:\Users\Administrator\Desktop\教材"),
    "题库": Path(r"C:\Users\Administrator\Desktop\题库"),
    "考点": Path(r"C:\Users\Administrator\Desktop\考点"),
    "考霸秘籍": Path(r"C:\Users\Administrator\Desktop\考霸秘籍"),
}

SUBJECTS = {
    "law": ("pharmacist_law", "药事管理与法规", "通用"),
    "west_1": ("pharmacist_west_1", "药学专业知识（一）", "西药"),
    "west_2": ("pharmacist_west_2", "药学专业知识（二）", "西药"),
    "west_syn": ("pharmacist_west_syn", "药学综合知识与技能", "西药"),
    "tcm_1": ("pharmacist_tcm_1", "中药学专业知识（一）", "中药"),
    "tcm_2": ("pharmacist_tcm_2", "中药学专业知识（二）", "中药"),
    "tcm_syn": ("pharmacist_tcm_syn", "中药学综合知识与技能", "中药"),
}

MATERIAL_BY_CATEGORY = {
    "教材": {
        "material_type": "textbook",
        "asset_type": "textbook",
        "product_type": "textbook",
        "paper_type": "",
    },
    "题库": {
        "material_type": "question_bank",
        "asset_type": "paper",
        "product_type": "",
        "paper_type": "chapter_test",
    },
    "考点": {
        "material_type": "key_points",
        "asset_type": "handout",
        "product_type": "handout",
        "paper_type": "",
    },
    "考霸秘籍": {
        "material_type": "secret_manual",
        "asset_type": "manual",
        "product_type": "teaching_aid",
        "paper_type": "",
    },
}


@dataclass(frozen=True)
class ManifestRow:
    source_path: str
    normalized_file_name: str
    output_path: str
    cert_code: str
    cert_name: str
    year: int
    track: str
    subject_code: str
    subject_name: str
    source_category: str
    material_type: str
    asset_type: str
    product_type: str
    paper_type: str
    confidentiality: str
    copyright_owner: str
    allowed_use: str
    version_label: str
    review_status: str
    file_sha256: str
    size_bytes: int
    page_count: int | str
    first3_text_chars: int | str
    parse_status: str
    notes: str


@dataclass(frozen=True)
class ReviewRow:
    source_path: str
    issue_code: str
    issue_detail: str
    suggested_action: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare 执业药师 files for V2 import.")
    parser.add_argument(
        "--source",
        action="append",
        default=[],
        metavar="CATEGORY=PATH",
        help="Override/add a source folder. Category should be 教材, 题库, 考点, or 考霸秘籍.",
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--year", type=int, default=DEFAULT_YEAR)
    parser.add_argument("--cert-code", default=CERT_CODE)
    parser.add_argument("--cert-name", default=CERT_NAME)
    parser.add_argument("--confidentiality", default=DEFAULT_CONFIDENTIALITY)
    parser.add_argument("--copyright-owner", default=DEFAULT_COPYRIGHT_OWNER)
    parser.add_argument("--allowed-use", default=DEFAULT_ALLOWED_USE)
    parser.add_argument("--dry-run", action="store_true", help="Only print the plan; do not create files.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing normalized copies.")
    return parser.parse_args()


def parse_sources(values: list[str]) -> dict[str, Path]:
    if not values:
        return DEFAULT_SOURCES.copy()

    sources: dict[str, Path] = {}
    for value in values:
        if "=" not in value:
            raise SystemExit(f"--source must be CATEGORY=PATH, got: {value}")
        category, raw_path = value.split("=", 1)
        category = category.strip()
        if category not in MATERIAL_BY_CATEGORY:
            raise SystemExit(f"Unsupported category {category!r}; expected one of {sorted(MATERIAL_BY_CATEGORY)}")
        sources[category] = Path(raw_path.strip())
    return sources


def iter_pdfs(sources: dict[str, Path]) -> Iterable[tuple[str, Path, Path]]:
    for category, root in sources.items():
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.pdf")):
            if path.is_file():
                yield category, root, path


def detect_subject(category: str, path: Path) -> tuple[str, str, str, list[ReviewRow]]:
    text = normalize_text(" ".join(path.parts[-4:]))
    reviews: list[ReviewRow] = []

    subject_key = ""
    if "法规" in text:
        subject_key = "law"
    elif "中药综合" in text or "中药综" in text:
        subject_key = "tcm_syn"
    elif "中药二" in text or "中药（二）" in text or "中药(二)" in text:
        subject_key = "tcm_2"
    elif "中药一" in text or "中药（一）" in text or "中药(一)" in text:
        subject_key = "tcm_1"
    elif "药综" in text or "药学综合" in text:
        subject_key = "west_syn"
    elif "西药二" in text or "西药（二）" in text or "西药(二)" in text or re.search(r"(^|[^中])药二", text):
        subject_key = "west_2"
    elif "西药一" in text or "西药（一）" in text or "西药(一)" in text or re.search(r"(^|[^中])药一", text):
        subject_key = "west_1"

    if not subject_key:
        reviews.append(
            ReviewRow(
                source_path=str(path),
                issue_code="SUBJECT_UNMATCHED",
                issue_detail="Cannot infer subject from folder/file name.",
                suggested_action="Rename file or add manifest override with subject_code.",
            )
        )
        return "", "", "", reviews

    subject_code, subject_name, track = SUBJECTS[subject_key]
    return subject_code, subject_name, track, reviews


def normalize_text(value: str) -> str:
    return (
        value.replace("（", "(")
        .replace("）", ")")
        .replace("Ⅰ", "一")
        .replace("Ⅱ", "二")
        .replace("Ⅲ", "三")
    )


def safe_slug(value: str) -> str:
    value = value.strip()
    value = re.sub(r"[\\/:*?\"<>|]+", "_", value)
    value = re.sub(r"\s+", "_", value)
    value = value.replace("（", "").replace("）", "")
    value = value.replace("(", "").replace(")", "")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_pdf(path: Path) -> tuple[int | str, int | str, str, str]:
    if fitz is None:
        return "", "", "not_checked", "PyMuPDF is not installed; page/text inspection skipped."
    try:
        doc = fitz.open(str(path))
        page_count = len(doc)
        text_chars = 0
        for index in range(min(3, page_count)):
            text_chars += len(doc[index].get_text().strip())
        if text_chars <= 50:
            return page_count, text_chars, "needs_ocr_or_review", "First 3 pages have very little extractable text."
        return page_count, text_chars, "text_extractable", ""
    except Exception as exc:  # pragma: no cover - depends on local PDF quality
        return "", "", "pdf_error", f"{type(exc).__name__}: {exc}"


def version_label(path: Path, year: int) -> str:
    text = normalize_text(str(path))
    match = re.search(r"(20\d{2})", text)
    source_year = match.group(1) if match else str(year)
    date_match = re.search(r"(\d{1,2})[._-](\d{1,2})", text)
    if date_match:
        month = int(date_match.group(1))
        day = int(date_match.group(2))
        return f"{source_year}-{month:02d}-{day:02d}"
    return source_year


def build_row(
    *,
    category: str,
    source_root: Path,
    path: Path,
    args: argparse.Namespace,
) -> tuple[ManifestRow, list[ReviewRow]]:
    metadata = MATERIAL_BY_CATEGORY[category]
    subject_code, subject_name, track, reviews = detect_subject(category, path)
    page_count, first3_text_chars, parse_status, parse_note = inspect_pdf(path)
    digest = sha256_file(path)
    version = version_label(path, args.year)
    ext = path.suffix.lower()

    if parse_status in {"needs_ocr_or_review", "pdf_error"}:
        reviews.append(
            ReviewRow(
                source_path=str(path),
                issue_code=parse_status.upper(),
                issue_detail=parse_note,
                suggested_action="Check PDF text extraction before automatic fragment/question parsing.",
            )
        )

    if category == "题库":
        reviews.append(
            ReviewRow(
                source_path=str(path),
                issue_code="QUESTION_PARSE_REVIEW_REQUIRED",
                issue_detail="Question PDF can be stored as an asset, but structured question rows require parser/human verification.",
                suggested_action="After asset import, run a question parser or provide question CSV with question_no/type/options/answer/analysis/kp.",
            )
        )

    normalized_file_name = "_".join(
        safe_slug(part)
        for part in [
            str(args.year),
            args.cert_name,
            track or "待分类",
            subject_name or "待识别科目",
            metadata["material_type"],
            f"v{safe_slug(version)}",
            args.confidentiality,
        ]
        if part
    ) + ext
    output_path = args.output_dir / "files" / normalized_file_name

    rel_note = f"source_relative={path.relative_to(source_root)}"
    notes = "; ".join(part for part in [rel_note, parse_note] if part)

    row = ManifestRow(
        source_path=str(path),
        normalized_file_name=normalized_file_name,
        output_path=str(output_path),
        cert_code=args.cert_code,
        cert_name=args.cert_name,
        year=args.year,
        track=track,
        subject_code=subject_code,
        subject_name=subject_name,
        source_category=category,
        material_type=metadata["material_type"],
        asset_type=metadata["asset_type"],
        product_type=metadata["product_type"],
        paper_type=metadata["paper_type"],
        confidentiality=args.confidentiality,
        copyright_owner=args.copyright_owner,
        allowed_use=args.allowed_use,
        version_label=version,
        review_status="pending",
        file_sha256=digest,
        size_bytes=path.stat().st_size,
        page_count=page_count,
        first3_text_chars=first3_text_chars,
        parse_status=parse_status,
        notes=notes,
    )
    return row, reviews


def write_csv(path: Path, rows: list[object], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))


def write_readme(path: Path, rows: list[ManifestRow], reviews: list[ReviewRow], sources: dict[str, Path]) -> None:
    by_category: dict[str, int] = {}
    by_subject: dict[str, int] = {}
    for row in rows:
        by_category[row.source_category] = by_category.get(row.source_category, 0) + 1
        key = row.subject_name or "待识别科目"
        by_subject[key] = by_subject.get(key, 0) + 1

    lines = [
        "# 执业药师文件预处理包",
        "",
        f"Generated at: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "## 输入目录",
        "",
    ]
    for category, source in sources.items():
        lines.append(f"- {category}: `{source}`")

    lines.extend(
        [
            "",
            "## 输出",
            "",
            "- `files/`: 标准命名后的 PDF 副本",
            "- `manifest.csv`: 入库清单",
            "- `needs_review.csv`: 需要人工确认的问题",
            "",
            "## 统计",
            "",
            f"- 文件总数: {len(rows)}",
            f"- 需复核项: {len(reviews)}",
            "",
            "### 按来源分类",
            "",
        ]
    )
    for category, count in sorted(by_category.items()):
        lines.append(f"- {category}: {count}")

    lines.extend(["", "### 按科目分类", ""])
    for subject, count in sorted(by_subject.items()):
        lines.append(f"- {subject}: {count}")

    lines.extend(
        [
            "",
            "## 下一步建议",
            "",
            "1. 先人工检查 `needs_review.csv`。",
            "2. 先选择 `药学专业知识（一）` 做一条试点链路。",
            "3. 题库 PDF 不建议直接结构化入题表；先用 parser/CSV 校验题号、题型、选项、答案、解析、知识点。",
            "4. 确认版权/授权后，再把 `review_status` 从 `pending` 改为 `approved`。",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    sources = parse_sources(args.source)
    pdfs = list(iter_pdfs(sources))
    if not pdfs:
        print("No PDF files found in configured sources.", file=sys.stderr)
        return 2

    rows: list[ManifestRow] = []
    reviews: list[ReviewRow] = []
    for category, source_root, path in pdfs:
        row, row_reviews = build_row(category=category, source_root=source_root, path=path, args=args)
        rows.append(row)
        reviews.extend(row_reviews)

    print(f"Found {len(rows)} PDF files.")
    print(f"Review items: {len(reviews)}.")
    print(f"Output dir: {args.output_dir}")

    if args.dry_run:
        for row in rows:
            print(f"[DRY] {row.source_category} | {row.subject_name or '待识别科目'} | {row.normalized_file_name}")
        return 0

    args.output_dir.mkdir(parents=True, exist_ok=True)
    files_dir = args.output_dir / "files"
    files_dir.mkdir(parents=True, exist_ok=True)

    for row in rows:
        source = Path(row.source_path)
        target = Path(row.output_path)
        if target.exists() and not args.overwrite:
            reviews.append(
                ReviewRow(
                    source_path=str(source),
                    issue_code="OUTPUT_EXISTS",
                    issue_detail=f"Target file already exists: {target}",
                    suggested_action="Use --overwrite or clean the output directory.",
                )
            )
            continue
        shutil.copy2(source, target)

    write_csv(args.output_dir / "manifest.csv", rows, list(ManifestRow.__dataclass_fields__))
    write_csv(args.output_dir / "needs_review.csv", reviews, list(ReviewRow.__dataclass_fields__))
    write_readme(args.output_dir / "README.md", rows, reviews, sources)

    print("Wrote:")
    print(f"- {args.output_dir / 'manifest.csv'}")
    print(f"- {args.output_dir / 'needs_review.csv'}")
    print(f"- {args.output_dir / 'README.md'}")
    print(f"- {files_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
