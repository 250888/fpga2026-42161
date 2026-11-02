# -*- coding: utf-8 -*-
"""生成《瞬迹》AMD 赛道海报：中文一页 + 英文一页（16:9，13.333×7.5 英寸）。

版面沿用官方模板的三栏骨架（背景 / 架构 / 结果）+ 深色区块标题条 + 细线分隔，
但用基本图元重建，避免模板原位改字的溢位与高亮残留。

用法：python scripts/make_poster.py
输出：doc/瞬迹_海报_中英_20261103.pptx
"""
import os
import sys

from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "doc", "瞬迹_海报_中英_20261103.pptx")
FIGS = os.path.join(ROOT, "doc", "figs")
CASE = os.path.join(ROOT, "doc", "case", "out")
STRIP = os.path.join(FIGS, "_poster_strip.png")
LOGO = r"C:\Users\clocker\Downloads\校标.jpeg"
AMD_PNG = os.path.join(ROOT, "build", "tpl_media", "image1.png")

INK = "1A1A1A"
GREY = "6E6E6E"
BLUE = "1F4E79"
BAND = "262626"
ACC = "B03A2E"

W, H = 13.333, 7.5
COL_A, COL_B, COL_C = 0.35, 4.48, 8.62
WD_A, WD_B, WD_C = 3.95, 3.95, 4.42
TOP = 1.74
BAND_H = 0.40


def build_strip():
    from PIL import Image
    panels = [os.path.join(FIGS, "fig2-6a_pcb_top.png"),
              os.path.join(FIGS, "fig2-6b_pcb_bottom.png"),
              os.path.join(CASE, "preview_xunji_case_asm.png")]
    Hh = 560
    imgs = []
    for p in panels:
        im = Image.open(p).convert("RGB")
        w = max(1, int(im.width * Hh / im.height))
        imgs.append(im.resize((w, Hh), Image.LANCZOS))
    Wt = sum(i.width for i in imgs) + 18 * (len(imgs) + 1)
    canvas = Image.new("RGB", (Wt, Hh + 36), (255, 255, 255))
    x = 18
    for im in imgs:
        canvas.paste(im, (x, 18))
        x += im.width + 18
    canvas.save(STRIP, "PNG")


def tb(slide, x, y, w, h, text, font, size, bold=False, color=INK,
       align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, spacing=1.14, space_after=0):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = Inches(0.02)
    tf.margin_top = tf.margin_bottom = 0
    for i, line in enumerate(str(text).split("\n")):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.line_spacing = spacing
        p.space_after = Pt(space_after)
        r = p.add_run()
        r.text = line
        r.font.name = font
        r.font.size = Pt(size)
        r.font.bold = bold
        r.font.color.rgb = RGBColor.from_string(color)
    return box


def rect(slide, x, y, w, h, fill=None, line=None, lw=1.0, rounded=False):
    shp = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE if rounded else MSO_SHAPE.RECTANGLE,
        Inches(x), Inches(y), Inches(w), Inches(h))
    if rounded:
        try:
            shp.adjustments[0] = 0.06
        except Exception:
            pass
    if fill:
        shp.fill.solid()
        shp.fill.fore_color.rgb = RGBColor.from_string(fill)
    else:
        shp.fill.background()
    if line:
        shp.line.color.rgb = RGBColor.from_string(line)
        shp.line.width = Pt(lw)
    else:
        shp.line.fill.background()
    shp.text_frame.word_wrap = True
    return shp


def band(slide, x, y, w, text, font, size=16):
    s = rect(slide, x, y, w, BAND_H, fill=BAND)
    tf = s.text_frame
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    tf.margin_left = tf.margin_right = Inches(0.06)
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.LEFT
    r = p.add_run()
    r.text = text
    r.font.name = font
    r.font.size = Pt(size)
    r.font.bold = True
    r.font.color.rgb = RGBColor.from_string("FFFFFF")
    return s


def hline(slide, x1, x2, y, color="BFBFBF", lw=1.0):
    from pptx.enum.shapes import MSO_CONNECTOR
    ln = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y),
                                    Inches(x2), Inches(y))
    ln.line.color.rgb = RGBColor.from_string(color)
    ln.line.width = Pt(lw)


def pic(slide, path, x, y, w=None, h=None):
    kw = {}
    if w: kw["width"] = Inches(w)
    if h: kw["height"] = Inches(h)
    return slide.shapes.add_picture(path, Inches(x), Inches(y), **kw)


def results_table(slide, x, y, w, rows, font, size=9.5, col_w=(0.95, 1.25, 2.15)):
    shp = slide.shapes.add_table(len(rows), 3, Inches(x), Inches(y),
                                 Inches(sum(col_w)), Inches(0.30 * len(rows)))
    tbl = shp.table
    for i, cw in enumerate(col_w):
        tbl.columns[i].width = Inches(cw)
    for r, row in enumerate(rows):
        tbl.rows[r].height = Inches(0.30)
        for c, val in enumerate(row):
            cell = tbl.cell(r, c)
            cell.text = ""
            cell.margin_left = cell.margin_right = Inches(0.05)
            cell.margin_top = cell.margin_bottom = Inches(0.01)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            cell.fill.solid()
            cell.fill.fore_color.rgb = RGBColor.from_string(
                "EDEFF2" if r == 0 else ("FFFFFF" if r % 2 else "F7F8FA"))
            p = cell.text_frame.paragraphs[0]
            run = p.add_run()
            run.text = str(val)
            run.font.name = font
            run.font.size = Pt(size)
            run.font.bold = (r == 0) or (c == 1 and r > 0)
            run.font.color.rgb = RGBColor.from_string(INK)
    return shp


def build_slide(prs, d):
    s = prs.slides.add_slide(prs.slide_layouts[6])

    # ---- 顶部
    tb(s, 0.32, 0.10, 5.0, 0.26, d["copyright"], d["latin"], 10, color=GREY)
    if os.path.exists(AMD_PNG):
        pic(s, AMD_PNG, 11.72, 0.09, w=1.30)      # AMD wordmark（母版图，4.19:1）
    hline(s, 0.32, 13.01, 1.50, "C9C9C9", 1.2)

    # ---- 标题
    tb(s, 0.32, 0.40, 7.10, 1.02, d["title"], d["font"], 20.5, bold=True,
       color="111111", spacing=1.06)

    # ---- 队伍信息
    tb(s, 7.50, 0.36, 2.70, 0.32, d["members"], d["font"], 13, bold=True, color=INK)
    tb(s, 7.50, 0.69, 2.70, 0.70, d["school"], d["font"], 11, bold=True, color=BLUE,
       spacing=1.06)
    if os.path.exists(LOGO):
        pic(s, LOGO, 10.28, 0.38, h=0.60)

    # ---- 三栏区块标题
    band(s, COL_A, TOP, WD_A, d["sec1"], d["font"])
    band(s, COL_B, TOP, WD_B, d["sec2"], d["font"])
    band(s, COL_C, TOP, WD_C, d["sec3"], d["font"])

    y = TOP + BAND_H + 0.16

    # ===== 栏 A：背景 =====
    tb(s, COL_A, y, WD_A, 3.10, d["body1"], d["font"], 10, color=INK, spacing=1.18,
       space_after=2)
    if os.path.exists(STRIP):
        p = pic(s, STRIP, COL_A, 5.30, w=WD_A)
        tb(s, COL_A, 5.30 + p.height / 914400 + 0.05, WD_A, 0.30, d["cap_strip"],
           d["font"], 9.5, bold=True, color=INK, align=PP_ALIGN.CENTER)

    # ===== 栏 B：架构 =====
    p = pic(s, os.path.join(FIGS, "fig2-1_system.png"), COL_B, y, w=WD_B)
    yy = y + p.height / 914400 + 0.03
    tb(s, COL_B, yy, WD_B, 0.26, d["cap_sys"], d["font"], 10, bold=True,
       color=INK, align=PP_ALIGN.CENTER)

    b1 = rect(s, COL_B, 4.72, WD_B, 1.18, fill="F5F7FA", line="C9D2DC", rounded=True)
    tb(s, COL_B + 0.08, 4.78, WD_B - 0.16, 1.06, d["box1"], d["font"], 9.2,
       color=INK, spacing=1.14)
    b2 = rect(s, COL_B, 6.02, WD_B, 1.12, fill="F5F7FA", line="C9D2DC", rounded=True)
    tb(s, COL_B + 0.08, 6.08, WD_B - 0.16, 1.00, d["box2"], d["font"], 9.2,
       color=INK, spacing=1.14)

    # ===== 栏 C：结果 =====
    tb(s, COL_C, y - 0.02, WD_C, 0.28, d["res_intro"], d["font"], 10, bold=True,
       color=ACC)
    results_table(s, COL_C, y + 0.30, WD_C, d["table"], d["font"], 9.2,
                  col_w=d["colw"])
    tb(s, COL_C, 4.52, WD_C, 1.30, d["body2"], d["font"], 9.6, color=INK, spacing=1.16)

    hl = rect(s, COL_C, 5.90, WD_C, 1.22, fill="FDF3F1", line="E0B4AC", rounded=True)
    tb(s, COL_C + 0.10, 5.97, WD_C - 0.20, 1.10, d["highlight"], d["font"], 9.6,
       color="7B241C", spacing=1.18)

    return s


CN = {
    "font": "微软雅黑", "latin": "Calibri",
    "copyright": "© 2026 AMD FPGA Innovation Design Contest",
    "title": "瞬迹 —— 基于 FPGA 的线束拓扑重建\n与 μs 级瞬态开路诊断装置",
    "members": "王鑫婷　　季佳越",
    "school": "中国地质大学（武汉）\nChina University of Geosciences (Wuhan)",
    "sec1": "背景与方案", "sec2": "系统架构与创新点", "sec3": "测试结果与性能",
    "body1": ("线束装配错误与端子松动是整机故障的重要来源。传统人工通断表需逐根核对，"
              "效率低，且无法捕获瞬态断线。\n"
              "本作品用同一套硬件回答两个问题：\n"
              "「线怎么接」——16×16 静态拓扑重建；\n"
              "「线什么时候断」——μs 级瞬态捕获。\n"
              "硬件：EGO1（Artix-7 XC7A35T，100 MHz）＋自研 FE-16 前端板。\n"
              "信号链：a_ctrl_n → LVC07 开漏 → RS 330 Ω → JA → 被测线束 → JB → "
              "RP 4.7 kΩ 上拉 → LVC14 施密特反相 → b_raw → FPGA。\n"
              "规格：16 通道 · 单轮扫描 112 μs · 48 B 定长帧 · 240 fps · 115200 bps · "
              "帧内可捕获 μs 级瞬态。"),
    "cap_strip": "自研 FE-16 前端板与整机（PCB 顶/底 + 外壳设计）",
    "cap_sys": "系统框图",
    "box1": ("双端有源扫描拓扑（创新点 1）\n"
             "① 32 根信号线完成 16×16 全连接矩阵\n"
             "② 开漏激励天然无多路竞争，串阻限流约 10 mA\n"
             "③ 施密特反相抑制长线束慢边沿抖动"),
    "box2": ("三层滤波与帧一致性（创新点 2、3）\n"
             "① 5 μs 空闲稳定窗 + 101 拍多数表决 + 8 拍去毛刺\n"
             "② 帧矩阵在发送触发沿锁存，保证 CRC 与负载同源"),
    "res_intro": "学习—比对，五级分类并定位到具体线号",
    "table": [
        ["制造故障", "系统判定", "定位结果"],
        ["16 路 1:1", "PASS", "16 条连接，全部对角"],
        ["拔 1 根", "OPEN", "open=0x0020 → ch5"],
        ["交叉 2 根", "MISWIRE", "矩阵出现 A2→B7、A7→B2"],
        ["短接 2 根", "BRIDGE", "18 条连接，A1↔B4 交叉出现"],
        ["交叉+断路", "ANOMALY", "拒绝硬套类型，符合不夸大原则"],
    ],
    "colw": (0.92, 1.05, 2.45),
    "body2": ("动态能力：CD4066 + Arduino Nano 串入线束，按需在 μs 量级断开指定通道，"
              "FPGA 以 100 MHz 采样捕获帧内瞬态开路，实现「线什么时候断」的黑匣子式记录。\n"
              "上位机：单文件 HTML 零安装直连，实时显示 16 路状态、连接矩阵与判定码，"
              "支持证据 hex 落盘。"),
    "highlight": ("资源与时序（XC7A35T-1CSG324C）\n"
                  "LUT 2119（10.19%） · FF 1564（3.76%）\n"
                  "BRAM 0 · DSP 0 · WNS +1.408 ns\n"
                  "回归：iverilog 6/6 · pytest 84 项全通过"),
}

EN = {
    "font": "Calibri", "latin": "Calibri",
    "copyright": "© 2026 AMD FPGA Innovation Design Contest",
    "title": "XunJi — FPGA-based Harness Topology Reconstruction\nand μs-level Transient Open-Circuit Diagnosis",
    "members": "Wang Xinting　　Ji Jiayue",
    "school": "China University of Geosciences (Wuhan)",
    "sec1": "INTRODUCTION", "sec2": "SYSTEM ARCHITECTURE & INNOVATION",
    "sec3": "RESULTS & PERFORMANCE",
    "body1": ("Mis-assembly and loose terminals are major sources of equipment failure. "
              "Manual continuity checks are slow and cannot capture transient opens.\n"
              "One platform answers two questions:\n"
              "\"how is the harness wired\" — 16×16 static topology reconstruction;\n"
              "\"when does a wire open\" — μs-level transient capture.\n"
              "Hardware: EGO1 (Artix-7 XC7A35T, 100 MHz) + self-designed FE-16 front-end board.\n"
              "Signal chain: a_ctrl_n → LVC07 open-drain → RS 330 Ω → JA → harness under test → "
              "JB → RP 4.7 kΩ pull-up → LVC14 Schmitt inverter → b_raw → FPGA.\n"
              "Spec: 16 channels · 112 μs per scan · 48 B fixed frame · 240 fps · 115200 bps · "
              "in-frame μs transient capture."),
    "cap_strip": "Self-designed FE-16 front-end board and assembly (PCB top/bottom + case)",
    "cap_sys": "System Architecture",
    "box1": ("Dual-ended active scanning topology (innovation 1)\n"
             "1. 32 signal lines build a full 16×16 connection matrix\n"
             "2. Open-drain drive: no contention; series resistor limits current to ~10 mA\n"
             "3. Schmitt inverter rejects slow-edge jitter on long harnesses"),
    "box2": ("Three-stage filtering and frame consistency (innovation 2, 3)\n"
             "1. 5 μs idle settle + 101-sample majority vote + 8-sample deglitch\n"
             "2. Matrix latched at the TX trigger edge: CRC and payload always agree"),
    "res_intro": "Learn-and-compare: five-class verdict, located to the exact wire",
    "table": [
        ["Injected fault", "Verdict", "Localisation"],
        ["16-ch 1:1 wiring", "PASS", "16 connections, all diagonal"],
        ["pull one wire", "OPEN", "open=0x0020 → ch5"],
        ["swap two wires", "MISWIRE", "matrix shows A2→B7, A7→B2"],
        ["short two wires", "BRIDGE", "18 connections, A1↔B4 appears"],
        ["swap + open", "ANOMALY", "refuses to over-claim a single class"],
    ],
    "colw": (1.02, 0.95, 2.45),
    "body2": ("Dynamic capability: CD4066 + Arduino Nano are inserted in-series with the harness; "
              "any channel can be opened for microseconds on demand, and the FPGA captures the "
              "in-frame transient at 100 MHz — a black-box record of \"when a wire opens\".\n"
              "Host tool: single-file HTML, zero install, real-time 16-channel status, connection "
              "matrix and verdict code, with hex evidence export."),
    "highlight": ("Resources & timing (XC7A35T-1CSG324C)\n"
                  "LUT 2119 (10.19%) · FF 1564 (3.76%)\n"
                  "BRAM 0 · DSP 0 · WNS +1.408 ns\n"
                  "Regression: iverilog 6/6 · pytest 84 passed"),
}


def main():
    build_strip()
    prs = Presentation()
    prs.slide_width = Inches(W)
    prs.slide_height = Inches(H)
    build_slide(prs, CN)
    build_slide(prs, EN)
    prs.save(OUT)
    print("已保存:", OUT, "页数:", len(prs.slides))


if __name__ == "__main__":
    main()
