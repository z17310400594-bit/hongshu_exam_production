"""Clean Xi Yao 1 PDFs with the parser selected by the 2026-07-04 eval.

Decision basis:
- Use pymupdf4llm as the main parser: it passed textbook, handout, and paper
  samples quickly and preserves Markdown tables well enough for MVP ingestion.
- Keep docling as a future fallback/reference for textbook chapters only; it was
  slower and failed the 2025 paper sample in the local eval.

The script writes cleaned Markdown next to the source PDFs and never modifies
the originals.

Run:
    py scripts/clean_xi_yao_1_pdfs.py --only textbook handout
    py scripts/clean_xi_yao_1_pdfs.py
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import pymupdf4llm  # type: ignore[import-untyped]
except Exception as exc:  # pragma: no cover - local dependency guard
    raise SystemExit("pymupdf4llm is required. Install it before running this parser-cleaning script.") from exc


DEFAULT_SOURCE_DIR = Path("C:/Users/Administrator/Desktop/" + "\u897f\u836f1")

SOURCE_FILES = {
    "textbook": "2026\u897f\u836f\u4e00\u6559\u6750.pdf",
    "handout": "2026\u897f\u836f\u4e00\u8bb2\u4e49.pdf",
    "exam_2022": "2022\u897f\u836f\u4e00\u771f\u9898 \uff08\u56de\u5fc6\u5b8c\u6574\u7248\uff09.pdf",
    "exam_2023": "2023\u897f\u836f\u4e00\u771f\u9898.pdf",
    "exam_2024": "2024\u897f\u836f\u4e00\u771f\u9898.pdf",
    "exam_2025": "2025\u897f\u836f\u5b66\u4e00\u771f\u9898\uff08\u56de\u5fc6\u7248\uff09.pdf",
}


@dataclass(frozen=True)
class CleanStats:
    source_file: str
    output_file: str
    parser: str
    page_count: int
    original_lines: int
    kept_lines: int
    removed_boundary_lines: int
    table_lines: int
    heading_lines: int
    repeated_boundary_lines: list[str]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Clean Xi Yao 1 PDFs into parser-selected Markdown.")
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--top-lines", type=int, default=3)
    parser.add_argument("--bottom-lines", type=int, default=3)
    parser.add_argument("--min-repeat", type=int, default=3)
    parser.add_argument("--min-repeat-ratio", type=float, default=0.06)
    parser.add_argument("--table-strategy", default="lines_strict")
    parser.add_argument("--only", nargs="*", choices=sorted(SOURCE_FILES), default=None)
    return parser.parse_args()


def parse_with_pymupdf4llm(path: Path, *, table_strategy: str) -> list[dict[str, Any]]:
    pages = pymupdf4llm.to_markdown(
        str(path),
        page_chunks=True,
        page_separators=False,
        ignore_images=True,
        ignore_graphics=True,
        show_progress=False,
        table_strategy=table_strategy,
    )
    if not isinstance(pages, list):
        raise RuntimeError(f"pymupdf4llm returned unexpected result for {path}")
    return pages


def normalize_boundary_line(value: str) -> str:
    value = value.replace("\u3000", " ")
    value = re.sub(r"\s+", " ", value).strip()
    return value


def normalize_markdown_text(value: str) -> str:
    value = value.replace("\u3000", " ")
    value = re.sub(r"\r\n?", "\n", value)
    value = re.sub(r"[ \t]+$", "", value, flags=re.MULTILINE)
    value = re.sub(r"\n{4,}", "\n\n\n", value)
    return value.strip()


def split_nonempty_lines(text_value: str) -> list[str]:
    return [line.rstrip() for line in text_value.splitlines() if line.strip()]


def repeated_boundary_lines(
    pages: list[dict[str, Any]],
    *,
    top_lines: int,
    bottom_lines: int,
    min_repeat: int,
    min_repeat_ratio: float,
) -> set[str]:
    counter: Counter[str] = Counter()
    for page in pages:
        lines = split_nonempty_lines(str(page.get("text") or ""))
        boundary = lines[:top_lines] + (lines[-bottom_lines:] if bottom_lines else [])
        seen = {normalize_boundary_line(line) for line in boundary if normalize_boundary_line(line)}
        counter.update(seen)

    threshold = max(min_repeat, int(len(pages) * min_repeat_ratio))
    repeated: set[str] = set()
    for line, count in counter.items():
        if count < threshold:
            continue
        if _is_structural_markdown(line):
            continue
        if len(line) <= 100 or _looks_like_page_artifact(line):
            repeated.add(line)
    return repeated


def clean_page_text(
    text_value: str,
    *,
    repeated_lines: set[str],
    top_lines: int,
    bottom_lines: int,
) -> tuple[str, int]:
    lines = text_value.splitlines()
    nonempty_positions = [index for index, line in enumerate(lines) if line.strip()]
    top_positions = set(nonempty_positions[:top_lines])
    bottom_positions = set(nonempty_positions[-bottom_lines:]) if bottom_lines else set()

    output: list[str] = []
    removed = 0
    for index, line in enumerate(lines):
        normalized = normalize_boundary_line(line)
        if _looks_like_page_artifact(normalized):
            removed += 1
            continue
        is_boundary = index in top_positions or index in bottom_positions
        if is_boundary and normalized in repeated_lines and not _is_structural_markdown(normalized):
            removed += 1
            continue
        output.append(line.rstrip())

    return normalize_markdown_text("\n".join(output)), removed


def _looks_like_page_artifact(line: str) -> bool:
    if not line:
        return False
    if re.fullmatch(r"[-\s]*\d{1,4}[-\s]*", line):
        return True
    if re.fullmatch(r"\[\[page:\d+\]\]", line):
        return True
    return False


def _is_structural_markdown(line: str) -> bool:
    return line.startswith("#") or line.startswith("|") or re.fullmatch(r"\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?", line) is not None


def render_clean_markdown(path: Path, pages: list[dict[str, Any]], args: argparse.Namespace) -> tuple[str, CleanStats]:
    repeated = repeated_boundary_lines(
        pages,
        top_lines=args.top_lines,
        bottom_lines=args.bottom_lines,
        min_repeat=args.min_repeat,
        min_repeat_ratio=args.min_repeat_ratio,
    )

    rendered: list[str] = [f"# {path.stem}", ""]
    original_lines = 0
    kept_lines = 0
    removed = 0
    for fallback_page_no, page in enumerate(pages, start=1):
        metadata = page.get("metadata") or {}
        page_no = int(metadata.get("page_number") or fallback_page_no)
        raw_text = str(page.get("text") or "")
        page_text, page_removed = clean_page_text(
            raw_text,
            repeated_lines=repeated,
            top_lines=args.top_lines,
            bottom_lines=args.bottom_lines,
        )
        original_lines += len(split_nonempty_lines(raw_text))
        kept_lines += len(split_nonempty_lines(page_text))
        removed += page_removed

        rendered.append(f"[[page:{page_no}]]")
        if page_text:
            rendered.append(page_text)
        rendered.append("")

    markdown = "\n".join(rendered).strip() + "\n"
    stats = CleanStats(
        source_file=str(path),
        output_file="",
        parser="pymupdf4llm",
        page_count=len(pages),
        original_lines=original_lines,
        kept_lines=kept_lines,
        removed_boundary_lines=removed,
        table_lines=sum(1 for line in markdown.splitlines() if line.lstrip().startswith("|")),
        heading_lines=sum(1 for line in markdown.splitlines() if line.lstrip().startswith("#")),
        repeated_boundary_lines=sorted(repeated)[:80],
    )
    return markdown, stats


def clean_file(path: Path, output_dir: Path, args: argparse.Namespace) -> CleanStats:
    pages = parse_with_pymupdf4llm(path, table_strategy=args.table_strategy)
    markdown, stats = render_clean_markdown(path, pages, args)
    output_path = output_dir / f"{path.stem}.cleaned.md"
    output_path.write_text(markdown, encoding="utf-8")
    return CleanStats(**{**asdict(stats), "output_file": str(output_path)})


def main() -> int:
    args = parse_args()
    if not args.source_dir.exists():
        raise SystemExit(f"source dir not found: {args.source_dir}")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = args.output_dir or args.source_dir / f"\u6e05\u6d17\u540e_pymupdf4llm_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)

    keys = args.only or list(SOURCE_FILES)
    stats: list[CleanStats] = []
    for key in keys:
        source = args.source_dir / SOURCE_FILES[key]
        if not source.exists():
            print(f"skip missing: {source}")
            continue
        stats.append(clean_file(source, output_dir, args))

    stats_path = output_dir / "clean_stats.json"
    stats_path.write_text(json.dumps([asdict(row) for row in stats], ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"output_dir={output_dir}")
    print(f"files={len(stats)} parser=pymupdf4llm")
    print(f"stats={stats_path}")
    for row in stats:
        print(
            f"{Path(row.source_file).name}: pages={row.page_count} "
            f"kept={row.kept_lines}/{row.original_lines} removed={row.removed_boundary_lines} "
            f"tables={row.table_lines} headings={row.heading_lines}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
