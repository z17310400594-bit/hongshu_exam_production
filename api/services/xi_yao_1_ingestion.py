"""Lightweight Xi Yao 1 PDF ingestion for the condensed handout MVP."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

DEFAULT_SOURCE_DIR = Path(r"C:\Users\Administrator\Desktop\西药1")

SOURCE_FILES = {
    "textbook": "2026西药一教材.pdf",
    "handout": "2026西药一讲义.pdf",
    "exam_2022": "2022西药一真题 （回忆完整版）.pdf",
    "exam_2023": "2023西药一真题.pdf",
    "exam_2024": "2024西药一真题.pdf",
    "exam_2025": "2025西药学一真题（回忆版）.pdf",
}

CHAPTERS = {
    "chapter_01": {
        "title": "第一章 药品与药品质量体系",
        "keywords": ["药品", "药物", "药品名称", "质量", "药典", "稳定性", "贮藏"],
    },
    "chapter_03": {
        "title": "第三章 药物的体内过程",
        "keywords": ["吸收", "分布", "代谢", "排泄", "半衰期", "生物利用度", "生物等效性", "清除率", "表观分布容积"],
    },
}


def build_evidence_pack(source_dir: Path, *, chapter_code: str, max_fragments_per_source: int = 10) -> dict[str, Any]:
    if chapter_code not in CHAPTERS:
        raise ValueError(f"unsupported chapter: {chapter_code}")
    chapter = CHAPTERS[chapter_code]
    documents = load_documents(source_dir)
    textbook_fragments = _select_fragments(documents.get("textbook", []), chapter["keywords"], max_fragments_per_source)
    handout_fragments = _select_fragments(documents.get("handout", []), chapter["keywords"], max_fragments_per_source)
    exam_evidence = _select_exam_evidence(documents, chapter["keywords"], limit=8)
    return {
        "subjectCode": "xi_yao_1",
        "chapterCode": chapter_code,
        "chapterTitle": chapter["title"],
        "textbookFragments": textbook_fragments,
        "handoutFragments": handout_fragments,
        "examEvidence": exam_evidence,
        "constraints": [
            "只基于证据包生成。",
            "不得编造真题年份、题号、页码。",
            "不得写今年必考、押题、稳过。",
            "依据不足的内容写入 reviewWarnings。",
        ],
    }


def load_documents(source_dir: Path = DEFAULT_SOURCE_DIR) -> dict[str, list[dict[str, Any]]]:
    return {
        source_type: extract_pdf_fragments(source_dir / filename, source_type=source_type)
        for source_type, filename in SOURCE_FILES.items()
        if (source_dir / filename).exists()
    }


def extract_pdf_fragments(path: Path, *, source_type: str) -> list[dict[str, Any]]:
    try:
        import fitz  # type: ignore[import-untyped]
    except ImportError as exc:
        raise RuntimeError("PyMuPDF/fitz is required to extract PDF text.") from exc

    file_hash = _sha256(path)
    fragments: list[dict[str, Any]] = []
    doc = fitz.open(str(path))
    try:
        for page_index, page in enumerate(doc, start=1):
            text_value = _compact_text(page.get_text("text") or "")
            if not text_value:
                continue
            for index, chunk in enumerate(_split_text(text_value, max_chars=900), start=1):
                fragments.append(
                    {
                        "sourceType": source_type,
                        "sourceTitle": path.stem,
                        "page": f"p{page_index}",
                        "heading": _guess_heading(chunk),
                        "content": chunk,
                        "hash": file_hash,
                        "fragmentCode": f"{path.stem}_p{page_index}_{index}",
                    }
                )
    finally:
        doc.close()
    return fragments


def _select_fragments(fragments: list[dict[str, Any]], keywords: list[str], limit: int) -> list[dict[str, Any]]:
    scored = sorted(
        ((sum(fragment["content"].count(keyword) for keyword in keywords), fragment) for fragment in fragments),
        key=lambda item: item[0],
        reverse=True,
    )
    return [
        {
            "sourceTitle": item["sourceTitle"],
            "page": item["page"],
            "heading": item["heading"],
            "content": item["content"],
        }
        for score, item in scored
        if score > 0
    ][:limit]


def _select_exam_evidence(documents: dict[str, list[dict[str, Any]]], keywords: list[str], *, limit: int) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for source_type, fragments in documents.items():
        if not source_type.startswith("exam_"):
            continue
        year = int(source_type.removeprefix("exam_"))
        for fragment in _select_fragments(fragments, keywords, limit=limit):
            evidence.append(
                {
                    "year": year,
                    "questionNo": _guess_question_no(fragment["content"]),
                    "summary": _clip(fragment["content"], 120),
                    "analysisSummary": _clip(fragment["content"], 220),
                }
            )
    return evidence[:limit]


def _split_text(text_value: str, *, max_chars: int) -> list[str]:
    chunks: list[str] = []
    current = ""
    for part in re.split(r"(?<=[。！？；])", text_value):
        if len(current) + len(part) > max_chars and current:
            chunks.append(current.strip())
            current = part
        else:
            current += part
    if current.strip():
        chunks.append(current.strip())
    return chunks


def _compact_text(text_value: str) -> str:
    return re.sub(r"\s+", " ", text_value).strip()


def _guess_heading(text_value: str) -> str:
    return _clip(text_value, 32)


def _guess_question_no(text_value: str) -> str | None:
    match = re.search(r"(?:第)?([0-9]{1,3})\s*[\.、题]", text_value)
    return f"Q{match.group(1)}" if match else None


def _clip(text_value: str, max_chars: int) -> str:
    compact = _compact_text(text_value)
    return compact[:max_chars]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
