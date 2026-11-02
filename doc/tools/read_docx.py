#!/usr/bin/env python3
"""提取docx全文（含表格）用于审查 V1.2"""
from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph
from docx.oxml.ns import qn

path = r"d:\UserFolders\Desktop\嵌赛FPGA\瞬迹_完整可行技术路线_EGO1开发板版_V1.2.docx"
doc = Document(path)

def iter_block_items(parent):
    for child in parent.element.body.iterchildren():
        if child.tag == qn('w:p'):
            yield Paragraph(child, parent)
        elif child.tag == qn('w:tbl'):
            yield Table(child, parent)

out = []
for block in iter_block_items(doc):
    if isinstance(block, Paragraph):
        t = block.text.strip()
        if t:
            style = block.style.name if block.style else ""
            prefix = f"[{style}] " if "Heading" in style or "标题" in style else ""
            out.append(prefix + t)
    else:
        out.append("──表格开始──")
        for row in block.rows:
            cells = [c.text.strip().replace("\n", " ") for c in row.cells]
            out.append(" | ".join(cells))
        out.append("──表格结束──")

text = "\n".join(out)
print(text)
print(f"\n=== 统计: {len(text)}字符, {len(out)}行 ===")
