"""
执业药师讲义 PDF 预处理脚本
功能：PDF 文本提取 → 清洗 → 按规则切分 → 生成带 metadata 的 chunk
输出：每本书一个 .jsonl 文件 + 一个合并的 .csv 用于 Dify 批量导入

用法：
  python preprocess_kb_pdfs.py

配置见下方 CONFIG 区，按需修改 PDF_DIR 和 OUTPUT_DIR。
"""

import fitz  # pymupdf
import json
import os
import re
import csv
import unicodedata
from pathlib import Path

# ═══════════════════════════════════════════════════════════════
# 配置区
# ═══════════════════════════════════════════════════════════════

PDF_DIR = r"C:\Users\Administrator\Desktop\2026执业药师基础讲义pdf文件"
OUTPUT_DIR = os.path.join(PDF_DIR, "output_chunks")

# 每本书的结构类型: 'A' = 条目表格式, 'B' = 知识点叙述式
BOOK_CONFIG = {
    "2026年执业药师-法规.pdf":      {"type": "B", "subject": "药事管理与法规", "exam_chapter_prefix": ""},
    "2026年执业药师-西药（一）.pdf": {"type": "B", "subject": "西药学",         "exam_chapter_prefix": ""},
    "2026年执业药师-西药（二）.pdf": {"type": "B", "subject": "西药学",         "exam_chapter_prefix": ""},
    "2026年执业药师-药综.pdf":      {"type": "B", "subject": "药学综合",       "exam_chapter_prefix": ""},
    "2026年执业药师-中药（一）.pdf": {"type": "A", "subject": "中药学",         "exam_chapter_prefix": ""},
    "2026年执业药师-中药（二）.pdf": {"type": "A", "subject": "中药学",         "exam_chapter_prefix": ""},
    "2026年执业药师-中药综.pdf":    {"type": "A", "subject": "中药学",         "exam_chapter_prefix": ""},
}

# 输出格式: 'jsonl' = 每行一个 JSON, 'csv' = Dify 导入格式
OUTPUT_FORMAT = "jsonl"  # 改 "csv" 则生成 Dify 可直接导入的 CSV

# ═══════════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════════

def clean_text_light(text: str) -> str:
    """轻量清洗：只去页码和乱码，保留原始换行（Type A 用）"""
    text = re.sub(r'\n(\d{1,3})\n', '\n', text)
    text = re.sub(r'^\d{1,3}\n', '', text, flags=re.MULTILINE)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = text.replace('', '•').replace('', '§')
    return text.strip()


def clean_text_full(text: str) -> str:
    """完整清洗：去页码 + 合并 PDF 表格短行（Type B 用）"""
    text = clean_text_light(text)
    text = re.sub(r'(?<=[^\n])\n(?=[^\n]{1,3}\n)', '', text)
    return text.strip()


def extract_chapter_number(text: str) -> str:
    """从文本开头提取章节编号"""
    m = re.match(r'第([一二三四五六七八九十百零〇\d]+)章', text)
    return m.group(1) if m else ""


def extract_section_number(text: str) -> str:
    """从文本开头提取节编号"""
    m = re.match(r'第([一二三四五六七八九十百零〇\d]+)节', text)
    return m.group(1) if m else ""


# ═══════════════════════════════════════════════════════════════
# A 类处理器：条目表格式（中药二/中药一/中药综）
# ═══════════════════════════════════════════════════════════════

def process_type_a(full_text: str, book_name: str, config: dict) -> list[dict]:
    """
    中药类书籍：PDF 目录页把所有章标题挤在前几页，不能按章节拆分。
    改为直接在全文中搜索「一、基本药物」区域，从附近标题推断章/节归属。
    """
    chunks = []
    chunk_id = 0

    # 构建章节目录索引：扫描所有「第X章 XXX」「第X节 XXX」标题位置
    chapter_index = []  # [(start_pos, ch_num, ch_title), ...]
    for m in re.finditer(r'第([一二三四五六七八九十百零\d]+)章\s*(\S+)', full_text):
        chapter_index.append((m.start(), m.group(1), m.group(2).strip()))

    section_index = []  # [(start_pos, sec_num, sec_title), ...]
    for m in re.finditer(r'第([一二三四五六七八九十百零\d]+)节\s*(\S+)', full_text):
        section_index.append((m.start(), m.group(1), m.group(2).strip()))

    # 找所有「一、基本药物」区域
    # PDF 提取后表头行被拼接：一、基本药物药物\n性能特点功效主治\n...
    # 所以用 .*?\n 吞掉同一行剩余的表格头文字
    drug_regions = list(re.finditer(
        r'(?:一、定义.*?)?(?:二、分类.*?)?(?:三、使用注意.*?)?一、基本药物.*?\n(.+?)(?=二、配伍|第[一二三四五六七八九十]+[章节]|$)',
        full_text, re.DOTALL
    ))

    if not drug_regions:
        # 放宽模式
        drug_regions = list(re.finditer(
            r'一、基本药物.*?\n(.+?)(?=二、配伍|$)',
            full_text, re.DOTALL
        ))

    print(f"  [DEBUG] drug_regions: {len(drug_regions)}, full_text len: {len(full_text)}")

    for region in drug_regions:
        region_start = region.start()
        region_text = region.group(0)

        # 推断当前区域的章/节归属
        ch_num, ch_title = "", ""
        for pos, num, title in reversed(chapter_index):
            if pos < region_start:
                ch_num, ch_title = num, title
                break

        sec_num, sec_title = "", ""
        for pos, num, title in reversed(section_index):
            if pos < region_start:
                sec_num, sec_title = num, title
                break

        # 提取章节头信息（定义/分类/使用注意）
        overview = _extract_type_a_overview(region_text)
        if overview:
            chunk_id += 1
            chunks.append({
                "chunk_id": f"{book_name.replace('.pdf','')}_{chunk_id:04d}",
                "content": overview["content"],
                "metadata": {
                    "subject": config["subject"],
                    "exam_type": "执业药师",
                    "book": book_name,
                    "chapter": ch_num,
                    "section": sec_num,
                    "exam_chapter": f"第{ch_num}章 {ch_title}",
                    "topic": overview.get("topic", ""),
                    "chunk_type": "chapter_overview",
                    "source": book_name,
                }
            })

        # 提取药物条目
        drug_entries = _extract_drug_entries(region_text)
        if not drug_entries:
            print(f"  [DEBUG] region at {region_start}: overview={overview is not None}, drug_entries=0, len(region_text)={len(region_text)}")
        for drug in drug_entries:
            chunk_id += 1
            chunks.append({
                "chunk_id": f"{book_name.replace('.pdf','')}_{chunk_id:04d}",
                "content": drug["content"],
                "metadata": {
                    "subject": config["subject"],
                    "exam_type": "执业药师",
                    "book": book_name,
                    "chapter": ch_num,
                    "section": sec_num,
                    "exam_chapter": f"第{ch_num}章 {ch_title}",
                    "exam_section": f"第{sec_num}节 {sec_title}",
                    "drug": drug.get("drug_name", ""),
                    "chunk_type": "drug_entry",
                    "source": book_name,
                    "keywords": drug.get("keywords", []),
                }
            })

        # 提取配伍使用（从紧跟着的区域末尾）
        drug_pairs = _extract_drug_pairs(region_text)
        for pair in drug_pairs:
            chunk_id += 1
            chunks.append({
                "chunk_id": f"{book_name.replace('.pdf','')}_{chunk_id:04d}",
                "content": pair["content"],
                "metadata": {
                    "subject": config["subject"],
                    "exam_type": "执业药师",
                    "book": book_name,
                    "chapter": ch_num,
                    "section": sec_num,
                    "exam_chapter": f"第{ch_num}章 {ch_title}",
                    "chunk_type": "drug_pair",
                    "source": book_name,
                    "keywords": pair.get("keywords", []),
                }
            })

    return chunks


def _extract_type_a_overview(sec_text: str) -> dict | None:
    """提取章节头信息：定义、分类、使用注意"""
    # 先合并 PDF 短行
    merged = _join_pdf_lines(sec_text)

    overview_parts = []
    # 匹配「一、定义」「二、分类」「三、使用注意」等
    patterns = [
        r'(一、定义.*?)(?=二、分类|三、|一、基本|$)',
        r'(二、分类.*?)(?=三、使用|一、基本|$)',
        r'(三、使用注意.*?)(?=第一节|第二节|第[一二三四五六七八九十]+节|一、基本药物|二、配伍|$)',
    ]
    for pat in patterns:
        m = re.search(pat, merged, re.DOTALL)
        if m:
            part = m.group(1).strip()
            if len(part) > 20:
                overview_parts.append(part)

    if overview_parts:
        topic = ""
        topic_m = re.search(r'(第[一二三四五六七八九十]+章\s*\S+)', merged)
        if topic_m:
            topic = topic_m.group(1)
        return {"content": "\n\n".join(overview_parts), "topic": topic}
    return None


def _join_pdf_lines(text: str) -> str:
    """
    合并 PDF 表格提取产生的短行。
    PDF 表格每列独立提取导致大量短行（< 20 字），需要合并为连续段落。
    规则：非空短行拼接到上一行末尾（用空格分隔），遇到空行则分段。
    """
    lines = text.split('\n')
    merged = []
    buf = ""

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if buf:
                merged.append(buf)
                buf = ""
            continue

        # 独立数字行（页码）→ 跳过
        if re.match(r'^\d{1,4}$', stripped):
            continue

        # 短行（< 15 字且不以标点结尾）→ 拼接到 buffer
        if len(stripped) < 15 and not re.search(r'[。？！，、；：）\)]$', stripped):
            buf += stripped
        else:
            if buf:
                merged.append(buf + stripped)
                buf = ""
            else:
                merged.append(stripped)

    if buf:
        merged.append(buf)

    return '\n'.join(merged)


def _extract_drug_entries(sec_text: str) -> list[dict]:
    """
    从节文本中提取药物条目。
    PDF 原格式中药名独占一行（2-4 字），后面跟性能特点/功效/主治。
    不做行合并，直接用原始行边界检测。
    """
    entries = []

    # 找「一、基本药物」或「基本药物」后的内容
    drug_section_match = re.search(
        r'(?:一、基本药物|基本药物).*?\n(.+?)(?=二、配伍|三、[^使]|第[一二三四五六七八九十]+节|$)',
        sec_text, re.DOTALL
    )
    if not drug_section_match:
        return entries

    raw_text = drug_section_match.group(1)

    # 去表头行
    raw_text = re.sub(r'^\s*药物\s*性能特点\s*功效\s*主治\s*$', '', raw_text, flags=re.MULTILINE)
    raw_text = re.sub(r'^\s*性能特点\s*功效\s*主治\s*$', '', raw_text, flags=re.MULTILINE)

    # 不可为药名的词汇
    STOP_WORDS = {
        '使用注意', '基本药物', '配伍使用', '不宜久', '掌握用', '了解其',
        '第一部分', '第二部分', '第三部分', '第四部分',
        '常用单味药', '常用中成药', '性能特点', '功效主治',
    }

    lines = raw_text.split('\n')
    # 第一遍：找出所有药名候选行（独占一行的 2-5 个纯 CJK + 可能的数字编号）
    drug_positions = []  # [(line_index, drug_name), ...]
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        # 药名特征：2-5 个 CJK 字符，可带括号编号
        if (2 <= len(stripped) <= 6
                and re.match(r'^[一-鿿（）\(\)\d]*$', stripped)
                and stripped not in STOP_WORDS
                and not re.match(r'^\d+$', stripped)
                and not re.match(r'^第[一二三四五六七八九十]', stripped)
                and not re.match(r'^[一二三四五六七八九十]、', stripped)):
            drug_positions.append((i, stripped))

    if len(drug_positions) < 2:
        return entries

    # 第二遍：按药名边界切分
    for idx in range(len(drug_positions)):
        start_line, drug_name = drug_positions[idx]
        if idx + 1 < len(drug_positions):
            end_line = drug_positions[idx + 1][0]
        else:
            end_line = len(lines)

        # 收集该药物的所有行（从药名行的下一行到下一个药名行）
        drug_lines = []
        for j in range(start_line + 1, end_line):
            line = lines[j].strip()
            if line and line not in STOP_WORDS:
                drug_lines.append(line)

        if len(drug_lines) < 2:
            continue  # 太短，可能误识别

        drug_content = '\n'.join(drug_lines)
        content = f"【药物】{drug_name}\n{drug_content}"

        entries.append({
            "drug_name": drug_name,
            "content": content.strip(),
            "keywords": [drug_name],
        })

    return entries


def _extract_drug_pairs(sec_text: str) -> list[dict]:
    """提取配伍使用条目"""
    pairs = []
    merged = _join_pdf_lines(sec_text)
    pair_match = re.search(r'(二、配伍使用.*?)(?=三、|第[一二三四五六七八九十]+章|第[一二三四五六七八九十]+节|$)', merged, re.DOTALL)
    if pair_match:
        pair_text = pair_match.group(1)
        for m in re.finditer(r'([一-鿿]+配[一-鿿]+[：:].+?)(?=[一-鿿]+配|\Z)', pair_text, re.DOTALL):
            content = m.group(1).strip()
            if len(content) > 20:
                name_part = content[:content.index('配')] + '配' + content[content.index('配')+1:content.index('：')]
                pairs.append({
                    "content": content,
                    "keywords": name_part.replace('配', ' ').split(),
                })
    return pairs


# ═══════════════════════════════════════════════════════════════
# B 类处理器：知识点叙述式（法规/西药一/西药二/药综）
# ═══════════════════════════════════════════════════════════════

def process_type_b(full_text: str, book_name: str, config: dict) -> list[dict]:
    """
    法规/西药类书籍：按章→节→编号知识点切分。
    每个「一、」「二、」等编号条目自成一个 chunk。
    """
    chunks = []
    chunk_id = 0

    # 按「第X章」切分
    chapter_pattern = r'(第[一二三四五六七八九十百零\d]+章\s*.+?)(?=第[一二三四五六七八九十百零\d]+章\s*|$)'
    chapters = re.findall(chapter_pattern, full_text, re.DOTALL)

    if not chapters:
        chapters = [full_text]

    for ch_text in chapters:
        ch_num = extract_chapter_number(ch_text)
        ch_title = ch_text.split('\n')[0].strip()

        # 按「第X节」切分
        section_pattern = r'(第[一二三四五六七八九十百零\d]+节\s*.+?)(?=第[一二三四五六七八九十百零\d]+节\s*|$)'
        sections = re.findall(section_pattern, ch_text, re.DOTALL)

        if not sections:
            sections = [ch_text]

        for sec_text in sections:
            sec_num = extract_section_number(sec_text)
            sec_title = sec_text.split('\n')[0].strip()

            # 按中文编号「一、」「二、」切分知识点
            items = _split_by_numbered_items(sec_text)

            for item_text in items:
                if len(item_text.strip()) < 30:
                    continue  # 跳过太短的片段

                # 提取编号标题
                title_match = re.match(r'([一二三四五六七八九十]+)[、，．.](.+)', item_text)
                item_title = title_match.group(2).strip() if title_match else ""
                item_num = title_match.group(1) if title_match else ""

                chunk_id += 1
                chunks.append({
                    "chunk_id": f"{book_name.replace('.pdf','')}_{chunk_id:04d}",
                    "content": item_text.strip(),
                    "metadata": {
                        "subject": config["subject"],
                        "exam_type": "执业药师",
                        "book": book_name,
                        "chapter": ch_num,
                        "section": sec_num,
                        "exam_chapter": ch_title,
                        "topic": sec_title,
                        "sub_topic": item_title,
                        "item_number": item_num,
                        "chunk_type": "key_point",
                        "source": book_name,
                        "keywords": _extract_keywords(item_text),
                    }
                })

    return chunks


def _split_by_numbered_items(text: str) -> list[str]:
    """按中文编号（一、二、三、…）或括号编号（（一）（二）…）切分"""
    # 先在（一）（二）处切分
    items = re.split(r'\n(?=（[一二三四五六七八九十]+）)', text)
    # 对每个结果再在一、二、三处切分
    result = []
    for item in items:
        sub = re.split(r'\n(?=[一二三四五六七八九十]+[、，．.])', item)
        result.extend(sub)
    return [r for r in result if r.strip()]


def _extract_keywords(text: str) -> list[str]:
    """从知识文本中提取关键词"""
    keywords = []
    # 提取引号中的术语
    quoted = re.findall(r'[「「]([^」」]+)[」」]', text)
    keywords.extend(quoted[:5])
    # 提取英文缩写
    abbr = re.findall(r'[A-Z]{2,6}', text)
    keywords.extend(abbr[:3])
    return list(set(keywords))[:8]


# ═══════════════════════════════════════════════════════════════
# 主流程
# ═══════════════════════════════════════════════════════════════

def process_book(pdf_path: str) -> list[dict]:
    """处理单本 PDF，返回 chunk 列表"""
    book_name = os.path.basename(pdf_path)
    # Unicode 规范化：确保文件名与 BOOK_CONFIG 的 key 匹配（Windows 路径可能有 NFC/NFD 差异）
    book_name = unicodedata.normalize('NFC', book_name)
    config = BOOK_CONFIG.get(book_name)

    # 如果精确匹配失败，尝试规范化后再匹配
    if not config:
        normalized_keys = {unicodedata.normalize('NFC', k): v for k, v in BOOK_CONFIG.items()}
        config = normalized_keys.get(book_name)

    if not config:
        print(f"  [WARN] {book_name}: 未在 BOOK_CONFIG 中配置，跳过")
        return []

    print(f"  [INFO] 提取文本...")
    doc = fitz.open(pdf_path)
    full_text = ""
    for page in doc:
        full_text += page.get_text() + "\n"
    doc.close()

    print(f"  [INFO] 清洗文本...")
    if config["type"] == "A":
        full_text = clean_text_light(full_text)
    else:
        full_text = clean_text_full(full_text)

    print(f"  [INFO] 按类型 '{config['type']}' 切分...")
    if config["type"] == "A":
        chunks = process_type_a(full_text, book_name, config)
    else:
        chunks = process_type_b(full_text, book_name, config)

    return chunks


def save_output(chunks: list[dict], book_name: str):
    """保存切分结果"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    safe_name = book_name.replace(".pdf", "").replace("（", "(").replace("）", ")")

    if OUTPUT_FORMAT == "jsonl":
        path = os.path.join(OUTPUT_DIR, f"{safe_name}.jsonl")
        with open(path, "w", encoding="utf-8") as f:
            for chunk in chunks:
                f.write(json.dumps(chunk, ensure_ascii=False) + "\n")
        print(f"  [OK] -> {path} ({len(chunks)} chunks)")

    elif OUTPUT_FORMAT == "csv":
        path = os.path.join(OUTPUT_DIR, f"{safe_name}.csv")
        fieldnames = ["chunk_id", "content", "subject", "exam_type", "book",
                      "chapter", "section", "topic", "sub_topic", "chunk_type",
                      "source", "keywords"]
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for chunk in chunks:
                row = {
                    "chunk_id": chunk["chunk_id"],
                    "content": chunk["content"],
                    "subject": chunk["metadata"].get("subject", ""),
                    "exam_type": chunk["metadata"].get("exam_type", ""),
                    "book": chunk["metadata"].get("book", ""),
                    "chapter": chunk["metadata"].get("chapter", ""),
                    "section": chunk["metadata"].get("section", ""),
                    "topic": chunk["metadata"].get("topic", ""),
                    "sub_topic": chunk["metadata"].get("sub_topic", ""),
                    "chunk_type": chunk["metadata"].get("chunk_type", ""),
                    "source": chunk["metadata"].get("source", ""),
                    "keywords": ",".join(chunk["metadata"].get("keywords", [])),
                }
                writer.writerow(row)
        print(f"  [OK] -> {path} ({len(chunks)} chunks)")


def main():
    print("=" * 60)
    print("执业药师讲义 PDF 预处理")
    print(f"PDF 目录: {PDF_DIR}")
    print(f"输出目录: {OUTPUT_DIR}")
    print(f"输出格式: {OUTPUT_FORMAT}")
    print("=" * 60)

    # 扫描 PDF
    pdf_files = sorted([
        f for f in os.listdir(PDF_DIR)
        if f.endswith(".pdf")
    ])

    if not pdf_files:
        print("[ERROR] PDF 目录下未找到 PDF 文件")
        return

    print(f"\n找到 {len(pdf_files)} 个 PDF 文件:\n")
    for f in pdf_files:
        config = BOOK_CONFIG.get(f, {})
        print(f"  {f}  -> 类型: {config.get('type', '?')}, 科目: {config.get('subject', '?')}")

    # 逐本处理
    total_chunks = 0
    for pdf_file in pdf_files:
        pdf_path = os.path.join(PDF_DIR, pdf_file)
        print(f"\n处理: {pdf_file}")
        try:
            chunks = process_book(pdf_path)
            save_output(chunks, pdf_file)
            total_chunks += len(chunks)
        except Exception as e:
            print(f"  [ERROR] {e}")
            import traceback
            traceback.print_exc()

    # 汇总
    print(f"\n{'=' * 60}")
    print(f"处理完成: 共 {total_chunks} 个 chunk")
    print(f"输出目录: {OUTPUT_DIR}")
    print(f"{'=' * 60}")

    # 生成合并索引（方便 Dify 批量导入时对照）
    index_path = os.path.join(OUTPUT_DIR, "_chunk_index.json")
    index = {
        "total_chunks": total_chunks,
        "books": {},
    }
    for output_file in sorted(os.listdir(OUTPUT_DIR)):
        if output_file.endswith(".jsonl"):
            count = sum(1 for _ in open(os.path.join(OUTPUT_DIR, output_file), encoding="utf-8"))
            index["books"][output_file] = count
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    print(f"索引文件: {index_path}")


if __name__ == "__main__":
    main()
