# -*- coding: utf-8 -*-
"""把最终定稿的两张海报 PDF 合成一份两页 PPTX（提交系统要求 PPTx 格式）。

每页把 PDF 里嵌的原图（3840x2160）整页铺满，视觉与 PDF 完全一致。
用法：python scripts/make_poster_from_pdf.py
输出：doc/瞬迹_海报_中英_终版.pptx
"""
import io
import os
import sys

import pymupdf
from PIL import Image
from pptx import Presentation
from pptx.util import Inches

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "doc", "瞬迹_海报_中英_终版.pptx")
PAGES = [
    (os.path.join(ROOT, "doc", "瞬迹_海报_中文版_含校徽.pdf"), "中文版"),
    (os.path.join(ROOT, "doc", "XUNJI_Poster_English_含校徽.pdf"), "English"),
]
W_IN, H_IN = 13.333, 7.5


def page_image(pdf_path):
    """取出 PDF 第一页里嵌入的主图，返回 PIL Image。"""
    doc = pymupdf.open(pdf_path)
    page = doc[0]
    imgs = page.get_images(full=True)
    if not imgs:
        raise SystemExit(f"{pdf_path} 里没有嵌入图")
    xref = imgs[0][0]
    raw = doc.extract_image(xref)
    im = Image.open(io.BytesIO(raw["image"]))
    if im.mode != "RGB":
        im = im.convert("RGB")
    print(f"  {os.path.basename(pdf_path)}: {im.size[0]}x{im.size[1]} "
          f"{len(raw['image'])/1048576:.2f} MB ({raw['ext']})")
    doc.close()
    return im


def main():
    prs = Presentation()
    prs.slide_width = Inches(W_IN)
    prs.slide_height = Inches(H_IN)
    blank = prs.slide_layouts[6]

    tmpdir = os.path.join(ROOT, "build")
    os.makedirs(tmpdir, exist_ok=True)

    for i, (pdf, label) in enumerate(PAGES, 1):
        if not os.path.exists(pdf):
            raise SystemExit(f"缺少 {pdf}")
        print(f"第 {i} 页（{label}）：")
        im = page_image(pdf)
        # 存为高质量 JPEG 供 pptx 使用（PNG 会更大）
        jpg = os.path.join(tmpdir, f"_poster_page{i}.jpg")
        im.save(jpg, "JPEG", quality=95, subsampling=0)
        s = prs.slides.add_slide(blank)
        s.shapes.add_picture(jpg, 0, 0,
                             width=prs.slide_width, height=prs.slide_height)

    prs.save(OUT)
    print("已生成:", OUT)
    print("大小: %.2f MB  页数: %d"
          % (os.path.getsize(OUT) / 1048576, len(prs.slides)))
    for j in (os.path.join(tmpdir, "_poster_page1.jpg"),
              os.path.join(tmpdir, "_poster_page2.jpg")):
        if os.path.exists(j):
            os.remove(j)


if __name__ == "__main__":
    main()
