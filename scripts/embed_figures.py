# -*- coding: utf-8 -*-
"""把已生成的图片嵌入作品报告，替换正文里的【图 x-x …】占位符。

能填的：2-1 / 2-3 / 2-4 / 2-5 / 2-6 / 2-7
仍空缺的：2-2（硬件连接示意）、3-1/3-2/3-3（实物照）、3-4/3-5（PCB 照）、3-6（上位机截图）
        —— 这些需要实拍照片，保留占位并标注【待插入】。

用法：python scripts/embed_figures.py
"""
import os
import re
import sys

from docx import Document
from docx.shared import Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DOCX = (sys.argv[1] if len(sys.argv) > 1
        else os.path.join(ROOT, "doc", "瞬迹_作品报告.docx"))
FIGS = os.path.join(ROOT, "doc", "figs")
CASE = os.path.join(ROOT, "doc", "case", "out")

# 图号 -> [(图片路径, 宽度英寸, 图注)]；多张图则依次插入
PLAN = {
    "2-1": [
        (os.path.join(FIGS, "fig2-1_system.png"), 6.2,
         "图 2-1  系统整体框图（EGO1 主控 / FE-16 前端板 / CD4066 故障源 / 主机上位机）"),
    ],
    "2-3": [
        (os.path.join(CASE, "preview_xunji_case_asm.png"), 5.6,
         "图 2-3  外壳装配设计渲染图（自主设计 · 计划生产，本阶段未打印装配）"),
    ],
    "2-4": [
        (os.path.join(ROOT, "doc", "case", "case_drawing.png"), 5.4,
         "图 2-4  外壳工程图（底壳 / 上盖 / 装配体）"),
    ],
    "2-5": [
        (os.path.join(FIGS, "fig2-5_schematic.png"), 5.2,
         "图 2-5  FE-16 前端板原理图（KiCad Eeschema 导出）"),
    ],
    "2-6": [
        (os.path.join(FIGS, "fig2-6a_pcb_top.png"), 3.3,
         "图 2-6a  FE-16 PCB 版图 · 顶层"),
        (os.path.join(FIGS, "fig2-6b_pcb_bottom.png"), 3.3,
         "图 2-6b  FE-16 PCB 版图 · 底层"),
    ],
    "2-7": [
        (os.path.join(FIGS, "fig2-7_software.png"), 6.2,
         "图 2-7  软件分层框图（RTL / Python CLI / 浏览器上位机）"),
    ],
    "3-3": [
        (os.path.join(CASE, "render_asm.png"), 5.4,
         "图 3-3  外壳设计渲染图（底壳 / 上盖 / 装配体；计划生产，本阶段未打印）"),
    ],
}

PENDING = ["2-2", "3-1", "3-2", "3-4", "3-5", "3-6"]


def clear_runs(p):
    for r in list(p.runs):
        r._element.getparent().remove(r._element)


def insert_paragraph_after(paragraph, text=None, style=None):
    from docx.oxml import OxmlElement
    from docx.text.paragraph import Paragraph
    new_p = OxmlElement("w:p")
    paragraph._p.addnext(new_p)
    para = Paragraph(new_p, paragraph._parent)
    if style is not None:
        para.style = style
    if text:
        para.add_run(text)
    return para


def main():
    doc = Document(DOCX)
    normal = doc.styles["Normal"]
    filled, pending = [], []

    for p in list(doc.paragraphs):
        t = p.text.strip()
        m = re.match(r"^【图\s*([0-9]+-[0-9]+[ab]?)", t)
        if not m:
            continue
        key = m.group(1)

        if key in PLAN:
            items = PLAN[key]
            clear_runs(p)
            p.style = normal
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            anchor = p
            for i, (img, width, caption) in enumerate(items):
                if not os.path.exists(img):
                    print("  缺少图片:", img)
                    continue
                if i == 0:
                    target = p
                else:
                    target = insert_paragraph_after(anchor, style=normal)
                    target.alignment = WD_ALIGN_PARAGRAPH.CENTER
                run = target.add_run()
                run.add_picture(img, width=Inches(width))
                cap = insert_paragraph_after(target, style=normal)
                cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
                cap.add_run(caption)
                anchor = cap          # 链式：下一张图接在图注之后
            filled.append(key)
        else:
            clear_runs(p)
            p.style = normal
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            r = p.add_run(f"【待插入：{t.strip('【】')}】")
            r.bold = True
            pending.append(key)

    doc.save(DOCX)
    print("已填图:", filled)
    print("仍待插:", pending)
    print("保存:", DOCX)


if __name__ == "__main__":
    main()
