# -*- coding: utf-8 -*-
# 按 docx 段落索引区间抽取章节，连同章节范围内出现的表格，写成 UTF-8 文本
import re
from docx import Document

DOCX = r"D:\UserFolders\Desktop\嵌赛FPGA\瞬迹_完整可行技术路线_EGO1开发板版_V1.9.docx"
OUT = r"D:\UserFolders\Desktop\嵌赛FPGA\scripts\v19_sections.txt"

doc = Document(DOCX)

# 段落正文
paras = []
for i, p in enumerate(doc.paragraphs):
    style = p.style.name if p.style else ""
    paras.append((i, style, p.text))

# 表格按文档顺序无法直接对齐段落，全部导出，标注行数
tables = []
for ti, table in enumerate(doc.tables):
    rows = []
    for row in table.rows:
        cells = [c.text.replace("\n", " / ").strip() for c in row.cells]
        rows.append(" | ".join(cells))
    tables.append((ti, len(table.rows), len(table.columns), rows))

SECTIONS = {
    "4.3": (32, 33),
    "21": (116, 128),
    "26": (154, 155),
    "27": (158, 165),
}

with open(OUT, "w", encoding="utf-8") as f:
    for name, (lo, hi) in SECTIONS.items():
        f.write(f"\n{'='*90}\n### 章节 {name}  (P{lo:03d}-P{hi:03d})\n{'='*90}\n")
        for i, style, text in paras:
            if lo <= i <= hi and (text.strip() or "Heading" in style):
                f.write(f"[P{i:03d}|{style}] {text}\n")
        # 附属表格：全部表格列在文末，便于按需查
    f.write(f"\n{'='*90}\n### 附：全部 {len(tables)} 张表\n{'='*90}\n")
    for ti, nr, nc, rows in tables:
        f.write(f"\n--- TABLE {ti} ({nr}x{nc}) ---\n")
        for r in rows:
            f.write(f"  {r}\n")

print("written:", OUT)
