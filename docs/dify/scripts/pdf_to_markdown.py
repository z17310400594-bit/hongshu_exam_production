"""
pdf_to_markdown.py — PDF → #章 ##知识点 Markdown 转换

输入: PDF（如 2026年执业药师-法规.pdf）
输出:
  1. Markdown/*.md — 按章组织的 # ## 格式文件（供脚本 B 切分用）
  2. chapter_index.json — 章节索引（供 CODE_1 使用）

层级映射:
  PDF 原文           →  Markdown
  第X章 章名          →  # 第X章 章名
  第Y节 节名          →  (合并到文件标题，# 章 - 节)
  一、知识点名         →  ## 一、知识点名
  （一）子点           →  ### （一）子点
  1. / ① / (1)       →  保留原文
"""

import fitz
import re
import os
import json
from pathlib import Path
from collections import OrderedDict


def extract_text_from_pdf(pdf_path: str, skip_pages: int = 0) -> str:
    """提取 PDF 全文，可选跳过前 N 页（目录）"""
    doc = fitz.open(pdf_path)
    full_text = []
    for i in range(skip_pages, doc.page_count):
        text = doc[i].get_text()
        full_text.append(text)
    doc.close()
    return "\n".join(full_text)


def clean_pdf_text(text: str) -> str:
    """清洗 PDF 产物: 去页码、合并被切断的句子"""
    lines = text.split("\n")
    cleaned = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            cleaned.append("")
            continue

        # 去掉独立页码 (纯数字行，1-3 位数)
        if re.match(r'^\d{1,3}$', stripped):
            continue

        cleaned.append(stripped)

    # ── 合并断行: 只合并明确被 PDF 切断的句子 ──
    # 规则简洁: 上行不以 。！？：— 结尾 + 本行不是序号/标题开头 → 合并
    merged = []
    buffer = ""
    for i, line in enumerate(cleaned):
        if not line:
            if buffer:
                merged.append(buffer)
                buffer = ""
            merged.append("")
            continue

        # 层级标题/序号行 → 独立
        if re.match(r'^(第[一二三四五六七八九十百]+[章节]|[一二三四五六七八九十]+、|（[一二三四五六七八九十]+）|\d+[.、)）])', line):
            if buffer:
                merged.append(buffer)
                buffer = ""
            merged.append(line)
            continue

        prev_ends = buffer.endswith(('。', '！', '？', '：', '—')) if buffer else True

        if buffer and prev_ends:
            merged.append(buffer)
            buffer = line
        elif buffer:
            buffer += line  # 续接，不加空格（可能是 PDF 切开的词语）
        else:
            buffer = line

    if buffer:
        merged.append(buffer)

    return "\n".join(merged)


def detect_hierarchy(text: str) -> list[dict]:
    """
    检测 PDF 文本层级，返回结构化列表。
    每个元素: {level: 1|2|3, type: "chapter"|"section"|"point", number: str, title: str, content: list}
    """
    lines = text.split("\n")
    blocks = []
    current_block = {"type": "preamble", "content": [], "start_line": 0}

    i = 0
    while i < len(lines):
        stripped = lines[i].strip()

        # 跳过空行
        if not stripped:
            current_block["content"].append("")
            i += 1
            continue

        # ── 第X章 → level 1 ──
        ch_match = re.match(r'^第([一二三四五六七八九十百]+)章\s*(.*)$', stripped)
        if ch_match:
            ch_num = ch_match.group(1)
            ch_title = ch_match.group(2).strip()

            # 标题可能在下一行（如 "第一章\n执业药师与公众健康"）
            if not ch_title and i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                # 不是层级标记、不是页码
                if next_line and not re.match(r'^(第|一、|二、|三、|（|目录|\d+$)', next_line):
                    ch_title = next_line
                    i += 1  # 消费下一行

            if current_block.get("type") != "preamble" or current_block["content"]:
                blocks.append(current_block)
            current_block = {
                "level": 1,
                "type": "chapter",
                "number": ch_num,
                "title": ch_title,
                "content": [],
                "start_line": i,
            }
            i += 1
            continue

        # ── 第Y节 → level 2 ──
        sec_match = re.match(r'^第([一二三四五六七八九十百]+)节\s*(.*)$', stripped)
        if sec_match:
            sec_num = sec_match.group(1)
            sec_title = sec_match.group(2).strip()

            if not sec_title and i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if next_line and not re.match(r'^(第|一、|二、|三、|（|\d+$)', next_line):
                    sec_title = next_line
                    i += 1

            if current_block.get("type") != "preamble" or current_block["content"]:
                blocks.append(current_block)
            current_block = {
                "level": 2,
                "type": "section",
                "number": sec_num,
                "title": sec_title,
                "content": [],
                "start_line": i,
            }
            i += 1
            continue

        # ── 一、二、三、... → level 3 (知识点，将来变成 ##) ──
        point_match = re.match(r'^([一二三四五六七八九十]+)、\s*(.*)$', stripped)
        if point_match:
            if current_block.get("type") != "preamble" or current_block["content"]:
                blocks.append(current_block)
            current_block = {
                "level": 3,
                "type": "point",
                "number": point_match.group(1),
                "title": point_match.group(2).strip(),
                "content": [],
                "start_line": i,
            }
            i += 1
            continue

        # ── （一）（二） → level 4 (子点，保留为 ###) ──
        sub_match = re.match(r'^（([一二三四五六七八九十]+)）\s*(.*)$', stripped)
        if sub_match:
            if current_block.get("type") == "point":
                current_block["content"].append("### （" + sub_match.group(1) + "）" + (sub_match.group(2) or ""))
            else:
                current_block["content"].append(stripped)
            i += 1
            continue

        # ── 普通内容 ──
        current_block["content"].append(stripped)
        i += 1

    if current_block["content"] or current_block.get("type") != "preamble":
        blocks.append(current_block)

    return blocks


def blocks_to_markdown(blocks: list[dict], exam_name: str, output_dir: str) -> dict:
    """
    将层级块转为 Markdown 文件 + chapter_index。

    输出结构:
      output_dir/
        {章序号}_{章名}.md          # 完整章文件（供人工审查）
        upload/
          {章名}__{知识点}.txt      # 切分后的知识点文件（上传 Dify）
      chapter_index.json
    """
    os.makedirs(output_dir, exist_ok=True)
    upload_dir = os.path.join(output_dir, "upload")
    os.makedirs(upload_dir, exist_ok=True)

    index = {"exam": exam_name, "chapters": []}
    current_chapter = None
    current_section = None
    chapter_topics = []

    md_file = None
    chapter_num = 0

    for block in blocks:
        if block["type"] == "chapter":
            # 关闭上一个 chapter 文件
            if md_file:
                md_file.close()

            chapter_num += 1
            ch_title = block["title"] if block["title"] else f"第{block['number']}章"
            safe_ch = re.sub(r'[\\/:*?"<>|]', '-', ch_title)
            filename = f"第{chapter_num:02d}章_{safe_ch}.md"
            filepath = os.path.join(output_dir, filename)

            md_file = open(filepath, "w", encoding="utf-8")
            current_chapter = {
                "name": ch_title,
                "number": block["number"],
            }
            current_section = None
            chapter_topics = []

            md_file.write(f"# 第{block['number']}章 {ch_title}\n\n")
            if block["content"]:
                md_file.write("\n".join(block["content"]) + "\n\n")

        elif block["type"] == "section":
            sec_title = block["title"] if block["title"] else ""
            safe_sec = re.sub(r'[\\/:*?"<>|]', '-', sec_title)
            current_section = {"name": sec_title, "number": block["number"]}

            if md_file:
                if sec_title:
                    md_file.write(f"## 第{block['number']}节 {sec_title}\n\n")
                else:
                    md_file.write(f"## 第{block['number']}节\n\n")
                if block["content"]:
                    md_file.write("\n".join(block["content"]) + "\n\n")

        elif block["type"] == "point":
            pt_title = block["title"] if block["title"] else f"{block['number']}、"
            # 知识点 → ## 级别（脚本 B 的切分边界）
            safe_pt = re.sub(r'[\\/:*?"<>|]', '-', pt_title)
            safe_ch_name = re.sub(r'[\\/:*?"<>|]', '-', current_chapter["name"]) if current_chapter else "未知"

            # 写入章文件
            if md_file:
                md_file.write(f"## {block['number']}、{pt_title}\n\n")
                if block["content"]:
                    md_file.write("\n".join(block["content"]) + "\n\n")

            # 同时写入独立的 upload/*.txt（压缩多余空行）
            upload_filename = f"{safe_ch_name}__{block['number']}、{safe_pt}.txt"
            upload_path = os.path.join(upload_dir, upload_filename)

            # 压缩 content: 连续空行 → 单个空行，首尾去空
            compact_content = []
            prev_empty = False
            for cl in block["content"]:
                if not cl.strip():
                    if not prev_empty:
                        compact_content.append("")
                    prev_empty = True
                else:
                    compact_content.append(cl)
                    prev_empty = False
            # 去尾空行
            while compact_content and not compact_content[-1]:
                compact_content.pop()

            with open(upload_path, "w", encoding="utf-8") as f:
                f.write(f"# {current_chapter['name'] if current_chapter else ''}\n")
                if current_section:
                    f.write(f"## 第{current_section['number']}节 {current_section['name']}\n")
                f.write(f"## {block['number']}、{pt_title}\n\n")
                f.write("\n".join(compact_content))

            chapter_topics.append(pt_title)

        else:
            # preamble 或其他
            if md_file and block["content"]:
                md_file.write("\n".join(block["content"]) + "\n\n")

    # 关闭最后一个文件
    if md_file:
        md_file.close()

    # 构建 chapter_index (简化版 - 每个章一个条目)
    index_chapters = OrderedDict()
    current_ch_key = None
    for block in blocks:
        if block["type"] == "chapter":
            ch_title = block["title"] if block["title"] else f"第{block['number']}章"
            ch_key = re.sub(r'[\\/:*?"<>|]', '-', ch_title)
            if ch_key not in index_chapters:
                index_chapters[ch_key] = {"name": ch_title, "file": ch_key, "topics": []}
            current_ch_key = ch_key
        elif block["type"] == "point":
            pt_title = block["title"] if block["title"] else f"{block['number']}、"
            if current_ch_key and current_ch_key in index_chapters:
                if pt_title not in index_chapters[current_ch_key]["topics"]:
                    index_chapters[current_ch_key]["topics"].append(pt_title)

    index["chapters"] = list(index_chapters.values())

    # 写 chapter_index.json
    index_path = os.path.join(output_dir, "chapter_index.json")
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    total_topics = sum(len(c["topics"]) for c in index["chapters"])
    print(f"章节数: {len(index['chapters'])}")
    print(f"知识点总数: {total_topics}")
    print(f"Markdown 文件: {output_dir}/")
    print(f"上传文件: {upload_dir}/")
    print(f"索引文件: {index_path}")

    return index


def main(pdf_path: str, exam_name: str, output_dir: str, toc_pages: int = 2):
    print(f"读取 PDF: {pdf_path}")
    text = extract_text_from_pdf(pdf_path, skip_pages=toc_pages)
    print(f"跳过前 {toc_pages} 页目录, 提取文本: {len(text)} 字符")

    print("清洗文本...")
    text = clean_pdf_text(text)
    print(f"清洗后: {len(text)} 字符")

    print("检测层级...")
    blocks = detect_hierarchy(text)
    print(f"检测到 {len(blocks)} 个块")

    chapter_blocks = [b for b in blocks if b["type"] == "chapter"]
    section_blocks = [b for b in blocks if b["type"] == "section"]
    point_blocks = [b for b in blocks if b["type"] == "point"]
    print(f"  章: {len(chapter_blocks)}, 节: {len(section_blocks)}, 知识点: {len(point_blocks)}")

    print("生成 Markdown + upload + chapter_index...")
    index = blocks_to_markdown(blocks, exam_name, output_dir)

    print("\nDone!")
    return index


if __name__ == "__main__":
    import sys

    # 默认路径
    PDF_PATH = r"C:\Users\Administrator\Desktop\2026执业药师基础讲义pdf文件\2026年执业药师-法规.pdf"
    OUTPUT_DIR = r"C:\Users\Administrator\Desktop\法规教材_output"
    EXAM_NAME = "执业药师"

    if len(sys.argv) > 1:
        PDF_PATH = sys.argv[1]
    if len(sys.argv) > 2:
        OUTPUT_DIR = sys.argv[2]

    main(PDF_PATH, EXAM_NAME, OUTPUT_DIR)
