"""
batch_convert.py — 批量转换所有药师 PDF

用法: python batch_convert.py
输出: 桌面/{教材名}_output/
"""

import os
import sys

# 添加脚本目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pdf_to_markdown import main as convert_one

PDF_DIR = r"C:\Users\Administrator\Desktop\2026执业药师基础讲义pdf文件"
OUTPUT_BASE = r"C:\Users\Administrator\Desktop"

# PDF 文件名 → (考试名, TOC页数)
PDFS = [
    ("2026年执业药师-法规.pdf", "执业药师-法规", 2),
    ("2026年执业药师-中药（一）.pdf", "执业药师-中药一", 2),
    ("2026年执业药师-中药（二）.pdf", "执业药师-中药二", 2),
    ("2026年执业药师-中药综.pdf", "执业药师-中药综", 2),
    ("2026年执业药师-西药（一）.pdf", "执业药师-西药一", 2),
    ("2026年执业药师-西药（二）.pdf", "执业药师-西药二", 2),
    ("2026年执业药师-药综.pdf", "执业药师-药综", 2),
]

for filename, exam_name, toc_pages in PDFS:
    pdf_path = os.path.join(PDF_DIR, filename)
    output_dir = os.path.join(OUTPUT_BASE, f"{exam_name}_output")

    if not os.path.exists(pdf_path):
        print(f"SKIP (not found): {pdf_path}")
        continue

    print(f"\n{'='*60}")
    print(f"Processing: {exam_name}")
    print(f"{'='*60}")

    convert_one(pdf_path, exam_name, output_dir, toc_pages=toc_pages)

print("\n\nAll done!")
