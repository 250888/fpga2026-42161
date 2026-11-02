# -*- coding: utf-8 -*-
"""生成作品报告用的框图（纯 SVG 手写 + PyMuPDF 转 PNG，无需 matplotlib）。

输出：
    doc/figs/fig2-1_system.svg / .png     系统整体框图
    doc/figs/fig2-7_software.svg / .png   软件分层框图

用法：python scripts/make_diagrams.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "doc", "figs")
os.makedirs(OUT, exist_ok=True)

FONT = "Microsoft YaHei, SimHei, Noto Sans CJK SC, sans-serif"
INK = "#1a1a1a"
GREY = "#5a5a5a"
LINE = "#333333"

# 配色
C_FPGA = "#1f4e79"      # 深蓝 —— FPGA
C_FPGA_BG = "#eef3f9"
C_FE = "#1f6f3f"        # 深绿 —— 前端板
C_FE_BG = "#eff7f1"
C_DUT = "#8b2e2e"       # 暗红 —— 被测对象
C_DUT_BG = "#fbeeee"
C_PC = "#5b3f8c"        # 紫 —— 主机
C_PC_BG = "#f4f0fa"
C_4066 = "#9a6b00"      # 棕黄 —— 故障源
C_4066_BG = "#fff7e6"
C_CONTRACT = "#b8860b"
C_CONTRACT_BG = "#fff8e1"


def esc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def rect(x, y, w, h, fill="#ffffff", stroke=LINE, sw=1.6, rx=8, dash=None):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" ry="{rx}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{d}/>')


def text(x, y, lines, size=15, fill=INK, anchor="middle", weight="normal", lh=1.45):
    """多行文本，y 为第一行基线。"""
    if isinstance(lines, str):
        lines = lines.split("\n")
    out = [f'<text x="{x}" y="{y}" font-family="{FONT}" font-size="{size}" '
           f'fill="{fill}" text-anchor="{anchor}" font-weight="{weight}">']
    for i, ln in enumerate(lines):
        dy = 0 if i == 0 else size * lh
        out.append(f'<tspan x="{x}" dy="{dy}">{esc(ln)}</tspan>')
    out.append("</text>")
    return "".join(out)


def vcenter_text(x, cy, lines, size=15, **kw):
    """以 cy 为视觉中心放多行文本。"""
    if isinstance(lines, str):
        lines = lines.split("\n")
    n = len(lines)
    lh = size * kw.pop("lh", 1.45)
    total = (n - 1) * lh
    y0 = cy - total / 2 + size * 0.35
    return text(x, y0, lines, size=size, **kw)


def box_text(x, y, w, h, lines, size=15, fill=INK, weight="normal", **kw):
    return vcenter_text(x + w / 2, y + h / 2, lines, size=size, fill=fill,
                        weight=weight, **kw)


ARROW_DEFS = f'''
<defs>
  <marker id="a" markerWidth="10" markerHeight="10" refX="8" refY="3.2"
          orient="auto" markerUnits="strokeWidth">
    <path d="M0,0 L8,3.2 L0,6.4 z" fill="{LINE}"/>
  </marker>
  <marker id="ab" markerWidth="10" markerHeight="10" refX="8" refY="3.2"
          orient="auto" markerUnits="strokeWidth">
    <path d="M0,0 L8,3.2 L0,6.4 z" fill="{C_FPGA}"/>
  </marker>
  <marker id="ar" markerWidth="10" markerHeight="10" refX="8" refY="3.2"
          orient="auto" markerUnits="strokeWidth">
    <path d="M0,0 L8,3.2 L0,6.4 z" fill="{C_DUT}"/>
  </marker>
  <marker id="ap" markerWidth="10" markerHeight="10" refX="8" refY="3.2"
          orient="auto" markerUnits="strokeWidth">
    <path d="M0,0 L8,3.2 L0,6.4 z" fill="{C_PC}"/>
  </marker>
  <marker id="a4" markerWidth="10" markerHeight="10" refX="8" refY="3.2"
          orient="auto" markerUnits="strokeWidth">
    <path d="M0,0 L8,3.2 L0,6.4 z" fill="{C_4066}"/>
  </marker>
  <marker id="s" markerWidth="10" markerHeight="10" refX="1" refY="3.2"
          orient="auto" markerUnits="strokeWidth">
    <path d="M8,0 L0,3.2 L8,6.4 z" fill="{LINE}"/>
  </marker>
</defs>
'''


def arrow(x1, y1, x2, y2, color=LINE, sw=2.0, marker="a", start_marker=None,
          dash=None):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    sm = f' marker-start="url(#{start_marker})"' if start_marker else ""
    return (f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" '
            f'stroke-width="{sw}"{d} marker-end="url(#{marker})"{sm} '
            f'stroke-linecap="round"/>')


def _text_width(s, size):
    """按字符类型估算文字宽度：中日韩全角约 1.0 em，其余约 0.56 em。"""
    n = 0.0
    for ch in s:
        n += 1.0 if ord(ch) > 0x2E80 else 0.56
    return n * size


def label(x, y, s, size=13, fill=GREY, anchor="middle", weight="normal"):
    """带白色底衬的连线标注。"""
    w = _text_width(s, size) + 14
    if anchor == "middle":
        rx = x - w / 2
    elif anchor == "start":
        rx = x - 6
    else:
        rx = x - w + 6
    return (f'<rect x="{rx}" y="{y - size * 0.95}" width="{w}" '
            f'height="{size * 1.55}" rx="4" fill="#ffffff" opacity="0.92"/>'
            + text(x, y, s, size=size, fill=fill, anchor=anchor, weight=weight))


# ===========================================================================
# 图 2-1 系统整体框图
# ===========================================================================
def fig_system():
    W, H = 1760, 900
    p = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
         f'viewBox="0 0 {W} {H}">', ARROW_DEFS,
         rect(0, 0, W, H, fill="#ffffff", stroke="none", sw=0)]

    # ---- 列标题
    for cx, name, col in [(190, "被测对象", C_DUT), (620, "FE-16 前端板", C_FE),
                          (1140, "EGO1 主控", C_FPGA), (1605, "PC 端", C_PC)]:
        p.append(text(cx, 112, name, size=17, fill=col, weight="bold"))

    # ---- 被测线束
    p.append(rect(60, 140, 260, 470, fill=C_DUT_BG, stroke=C_DUT, sw=2.0))
    p.append(box_text(60, 140, 260, 470,
                      ["被测线束", "16 路", "", "JA ──→ JB", "A0–A15   B0–B15", "",
                       "（含 CD4066 串入）"], size=19, fill=C_DUT))

    # ---- FE-16 外壳
    p.append(rect(360, 130, 520, 490, fill=C_FE_BG, stroke=C_FE, sw=2.4, rx=14))

    # A 端激励
    p.append(rect(383, 200, 228, 236, fill="#ffffff", stroke=C_FE, sw=1.8))
    p.append(box_text(383, 200, 228, 236,
                      ["A 端激励", "", "LVC07 ×3", "（开漏，非反相）", "↓", "RS 330 Ω ×16",
                       "", "→ A 节点"], size=15, fill=C_FE, weight="bold"))
    # B 端回采
    p.append(rect(629, 200, 228, 236, fill="#ffffff", stroke=C_FE, sw=1.8))
    p.append(box_text(629, 200, 228, 236,
                      ["B 端回采", "", "← B 节点", "", "RP 4.7 kΩ ×16", "↑",
                       "LVC14 ×3", "（施密特反相）"], size=15, fill=C_FE, weight="bold"))
    # 底部说明
    p.append(rect(383, 462, 474, 132, fill="#ffffff", stroke=C_FE, sw=1.4))
    p.append(box_text(383, 462, 474, 132,
                      ["RU 10 kΩ ×16 输入上拉  ·  去耦 100 nF ×6",
                       "RCT1 电流断点  ·  JP1/EXT1 外部供电口（默认不插）",
                       "TP1–TP50 测试点（A / B / b_raw / 3V3 / GND）"],
                      size=14, fill="#2b2b2b"))

    # ---- EGO1 外壳
    p.append(rect(880, 130, 520, 490, fill=C_FPGA_BG, stroke=C_FPGA, sw=2.6, rx=14))
    p.append(text(1140, 168, "Artix-7 XC7A35T · 100 MHz 单时钟",
                  size=14, fill=C_FPGA))

    inner = [
        (188, ["开漏驱动控制器 drive_controller", "按 scan_idx 逐路拉低 a_ctrl_n（其余全 1）"]),
        (272, ["拓扑扫描状态机 topology_scanner",
               "IDLE→DRIVE→SETTLE→SAMPLE→DECIDE→RELEASE"]),
        (356, ["16×16 连接矩阵 + 位掩码", "conn_matrix[256] / stuck[16] / open[16]"]),
        (440, ["学习门 learn_gate    ·    比较器 golden_compare",
               "M_ref 锁存          ·     PASS/OPEN/MISWIRE/BRIDGE/ANOMALY"]),
        (524, ["UART 帧发送器 uart_packet_tx", "触发沿锁存矩阵快照 → 48 B 定长帧"]),
    ]
    for y, lines in inner:
        p.append(rect(902, y, 476, 68, fill="#ffffff", stroke=C_FPGA, sw=1.5))
        p.append(box_text(902, y, 476, 68, lines, size=14, fill="#12314f"))

    # ---- 主机上位机
    p.append(rect(1520, 140, 170, 470, fill=C_PC_BG, stroke=C_PC, sw=2.0))
    p.append(box_text(1520, 140, 170, 470,
                      ["主机上位机", "", "Python", "CLI", "read/sim/lint", "",
                       "浏览器", "单文件", "HTML"], size=17, fill=C_PC, weight="bold"))

    # ---- CD4066 故障源
    p.append(rect(60, 700, 260, 140, fill=C_4066_BG, stroke=C_4066, sw=2.0))
    p.append(box_text(60, 700, 260, 140,
                      ["CD4066 故障源", "4 × CD4066（32 路开关）", "Arduino Nano 控制"],
                      size=15, fill=C_4066, weight="bold"))

    # ---- 连线
    # 线束 ↔ FE
    p.append(arrow(320, 300, 360, 300, color=C_FPGA, sw=2.2, marker="ab"))
    p.append(arrow(360, 430, 320, 430, color=C_DUT, sw=2.2, marker="ar"))
    p.append(label(340, 288, "A 激励", size=12, fill=C_FPGA))
    p.append(label(340, 418, "B 回采", size=12, fill=C_DUT))
    # FE ↔ FPGA
    p.append(arrow(880, 240, 832, 240, color=C_FPGA, sw=2.4, marker="ab"))
    p.append(label(856, 224, "a_ctrl_n[15:0]", size=12, fill=C_FPGA))
    p.append(arrow(832, 520, 880, 520, color=C_FPGA, sw=2.4, marker="ab"))
    p.append(label(856, 540, "b_raw[15:0]", size=12, fill=C_FPGA))
    # FPGA → PC
    p.append(arrow(1400, 320, 1520, 320, color=C_PC, sw=2.4, marker="ap"))
    p.append(label(1460, 296, "UART 48 B 帧", size=11, fill=C_PC))
    p.append(label(1460, 352, "115200 bps", size=11, fill=C_PC))
    # CD4066 → 线束
    p.append(arrow(190, 700, 190, 612, color=C_4066, sw=2.2, marker="a4",
                   dash="7,6"))
    p.append(label(190, 682, "串入线束", size=12, fill=C_4066))

    p.append(text(60, 878,
                  "说明：FPGA 逐路开漏拉低 A 端，B 端经上拉与施密特反相器回采，"
                  "仅用 32 根信号线完成 16×16 全连接矩阵重建；"
                  "CD4066 串入线束用于注入 μs 级瞬态开路。",
                  size=13, fill=GREY, anchor="start"))
    p.append("</svg>")

    svg = "\n".join(p)
    path = os.path.join(OUT, "fig2-1_system.svg")
    with open(path, "w", encoding="utf-8") as f:
        f.write(svg)
    print("SVG:", path)
    return path, "fig2-1_system.png"


# ===========================================================================
# 图 2-7 软件分层框图
# ===========================================================================
def fig_software():
    W, H = 1640, 900
    p = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
         f'viewBox="0 0 {W} {H}">', ARROW_DEFS,
         rect(0, 0, W, H, fill="#ffffff", stroke="none", sw=0)]

    # ---- 第一层 RTL
    p.append(rect(40, 84, 1560, 232, fill=C_FPGA_BG, stroke=C_FPGA, sw=2.2, rx=12))
    p.append(text(64, 118, "第一层  FPGA RTL（Verilog-2001 · 100 MHz 单时钟 · clock-enable 节拍）",
                  size=17, fill=C_FPGA, anchor="start", weight="bold"))
    rtl = [
        ("drive_controller", "开漏驱动"),
        ("topology_scanner", "扫描状态机"),
        ("glitch_filter\ninput_sync", "三级滤波"),
        ("matrix_degree\ngolden_compare", "度统计与分类"),
        ("learn_gate", "参考矩阵锁存"),
        ("uart_packet_tx", "48 B 帧组帧"),
    ]
    bw, gap = 232, 24
    for i, (name, desc) in enumerate(rtl):
        x = 64 + i * (bw + gap)
        p.append(rect(x, 146, bw, 148, fill="#ffffff", stroke=C_FPGA, sw=1.5))
        p.append(vcenter_text(x + bw / 2, 186, name.split("\n"), size=15,
                              fill="#12314f", weight="bold"))
        p.append(text(x + bw / 2, 268, desc, size=13, fill=C_FE))

    # ---- 契约层
    p.append(rect(200, 344, 1240, 96, fill=C_CONTRACT_BG, stroke=C_CONTRACT,
                  sw=2.6, rx=10))
    p.append(vcenter_text(820, 374,
                          "唯一契约：48 字节定长帧  "
                          "SOF 55AA | Ver | Type | Len | Seq | Payload(38 B) | CRC-16/CCITT-FALSE",
                          size=16, fill="#7a5a00", weight="bold"))
    p.append(text(820, 418, "两侧各自持有独立的黄金帧回归用例，任何一侧单方面改动都会被回归拦截",
                  size=14, fill="#7a5a00"))

    # ---- 第二层 Python
    p.append(rect(40, 470, 1560, 178, fill=C_FE_BG, stroke=C_FE, sw=2.2, rx=12))
    p.append(text(64, 504, "第二层  主机 Python 包 xunji（uv 管理 · pytest 84 项回归 · lint 0）",
                  size=17, fill=C_FE, anchor="start", weight="bold"))
    py = [
        ("protocol.py", "帧编解码 / CRC16"),
        ("cli.py · read", "SOF 搜索 · 定长切帧\nCRC 校验 · 矩阵展开"),
        ("cli.py · sim", "驱动 iverilog\n跑 6 个 testbench"),
        ("cli.py · lint", "RTL 风格检查"),
    ]
    pw, pgap = 360, 24
    for i, (name, desc) in enumerate(py):
        x = 64 + i * (pw + pgap)
        p.append(rect(x, 528, pw, 100, fill="#ffffff", stroke=C_FE, sw=1.5))
        p.append(text(x + pw / 2, 566, name, size=16, fill="#14472a", weight="bold"))
        p.append(vcenter_text(x + pw / 2, 604, desc.split("\n"), size=13, fill=GREY))

    # ---- 第三层 浏览器
    p.append(rect(40, 688, 1560, 168, fill=C_PC_BG, stroke=C_PC, sw=2.2, rx=12))
    p.append(text(64, 722,
                  "第三层  浏览器上位机（单文件 HTML · 零安装 · Web Serial 直连 · 断线看门狗）",
                  size=17, fill=C_PC, anchor="start", weight="bold"))
    web = [
        ("串口适配层", "Web Serial / 自动重连"),
        ("16 路状态灯 + 矩阵网格", "非对角高亮"),
        ("判定码面板", "cls / open / stuck"),
        ("实时连接数 + µs 面板", "历史条 / 瞬态捕获"),
    ]
    ww = 360
    for i, (name, desc) in enumerate(web):
        x = 64 + i * (ww + 24)
        p.append(rect(x, 744, ww, 92, fill="#ffffff", stroke=C_PC, sw=1.5))
        p.append(text(x + ww / 2, 778, name, size=15, fill="#3b2765", weight="bold"))
        p.append(text(x + ww / 2, 812, desc, size=13, fill=GREY))

    # ---- 层间箭头
    p.append(arrow(820, 316, 820, 344, color=C_CONTRACT, sw=2.4, marker="a"))
    p.append(arrow(820, 440, 820, 470, color=C_CONTRACT, sw=2.4, marker="a"))
    p.append(arrow(820, 648, 820, 688, color=C_PC, sw=2.2, marker="ap"))

    p.append(label(944, 332, "48 B 帧（UART 115200）", size=13, fill="#7a5a00"))
    p.append(label(944, 458, "解码后结构化字段", size=13, fill="#7a5a00"))
    p.append(label(944, 670, "事件回调 / DOM 更新", size=13, fill=C_PC))

    p.append(text(40, 884,
                  "说明：RTL 与主机之间只通过冻结的 48 字节帧结构耦合，"
                  "彼此可独立开发与回归；上位机为零依赖单文件，现场免安装。",
                  size=13, fill=GREY, anchor="start"))
    p.append("</svg>")

    svg = "\n".join(p)
    path = os.path.join(OUT, "fig2-7_software.svg")
    with open(path, "w", encoding="utf-8") as f:
        f.write(svg)
    print("SVG:", path)
    return path, "fig2-7_software.png"


def svg_to_png(svg_path, png_name, dpi=200):
    import pymupdf
    doc = pymupdf.open(svg_path)
    page = doc[0]
    pix = page.get_pixmap(dpi=dpi)
    out = os.path.join(OUT, png_name)
    pix.save(out)
    doc.close()
    print(f"PNG: {out}  {pix.width}x{pix.height}")
    return out


if __name__ == "__main__":
    a = fig_system()
    b = fig_software()
    svg_to_png(a[0], a[1])
    svg_to_png(b[0], b[1])
    print("输出目录:", OUT)
