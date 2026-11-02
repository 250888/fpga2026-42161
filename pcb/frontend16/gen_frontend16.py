"""FE-16 生成器：从 fe16_design 生成 .kicad_pcb / .kicad_sch / BOM.csv。

用法：python gen_frontend16.py   （或 uv run python ...）
KiCad 8 格式（pcb version 20240108 / sch version 20231120），
本机装什么版本 KiCad 都能开；立创 EDA 专业版可导入。
"""
from __future__ import annotations

import csv
import math
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fe16_design import (  # noqa: E402
    BOARD_H, BOARD_W, DRILL_IDC, DRILL_MH, DRILL_TP, IC_POS, IDC_ROT_Y,
    JA_ORIGIN, JB_ORIGIN, J5_ORIGIN, MH_POS, PAD_0805, PAD_IDC_HOLE, PAD_MH,
    PAD_SOIC14, PAD_TP, PIN_GND, PIN_VCC, RCT_POS, JP1_POS, EXT_POS, C7_POS,
    PAD_THT_R, DRILL_THT_R, pads_tht_r,
    bom_rows, build_netlist, pads_idc, pads_soic14, pads_0805, rot_pad,
    UNUSED_SLOTS, SLOT_PINS,
)

HERE = Path(__file__).resolve().parent
PCB_OUT = HERE / "xunji_fe16.kicad_pcb"
SCH_OUT = HERE / "xunji_fe16.kicad_sch"
BOM_OUT = HERE / "BOM_fe16.csv"

_NS = uuid.UUID("a3f1c2d4-0e6b-4f8a-9c3d-7b2e5f91a640")
def U(tag: str) -> str:
    return str(uuid.uuid5(_NS, tag))

# ---------------------------------------------------------------------------
# 网络编号
# ---------------------------------------------------------------------------
NETLIST = build_netlist()
NETS = [""] + sorted(NETLIST)
NET_ID = {n: i for i, n in enumerate(NETS)}
PAD_NET: dict[tuple[str, str], str] = {
    (ref, pin): net for net, pads in NETLIST.items() for ref, pin in pads
}

# ---------------------------------------------------------------------------
# s-expression
# ---------------------------------------------------------------------------
# KiCad 官方词法：字符串值一律带引号，keyword/enum 值必须裸词（demo 对照表）。
_KW = {
    "yes", "no",
    "signal", "power", "user",
    "smd", "thru_hole", "np_thru_hole", "through_hole",
    "circle", "rect", "roundrect", "oval", "trapezoid",
    "line", "default", "solid", "none", "background",
    "passive", "input", "output", "open_collector", "open_emitter",
    "tri_state", "bidirectional", "power_in", "power_out", "free",
    "unspecified", "clock", "inverted", "inverted_clock",
    "edge_clock_high", "non_logic",
    "left", "right", "top", "bottom", "center",
    "exclude_from_pos_files", "exclude_from_bom",
}

def sx(node, _key: bool = False) -> str:
    if isinstance(node, str):
        if _key or node in _KW:
            return node
        return '"' + node.replace("\\", "\\\\").replace('"', '\\"') + '"'
    if isinstance(node, (int, float)):
        return (f"{node:g}" if isinstance(node, float) else str(node))
    inner = [sx(node[0], True)] if node else []
    inner += [sx(x) for x in node[1:]]
    return "(" + " ".join(inner) + ")"

def _num(v: float) -> float:
    return round(v, 4)

# ---------------------------------------------------------------------------
# 通用 property / pad 片段
# ---------------------------------------------------------------------------
def _prop(name: str, val: str, x: float, y: float, layer: str, tag: str,
          size: float = 0.8, hide: bool = False, angle: float = 0.0) -> list:
    eff: list = ["effects", ["font", ["size", size, size], ["thickness", 0.15]]]
    if hide:
        eff.append(["hide", "yes"])
    return ["property", name, val,
            ["at", _num(x), _num(y), _num(angle)], ["layer", layer],
            ["uuid", U(tag)], eff]

def _pad(num, kind: str, shape: str, lx: float, ly: float, size_wh,
         layers: list[str], frot: float, net: str | None,
         tag: str, drill=None, rratio=None) -> list:
    node: list = ["pad", str(num), kind, shape,
                  ["at", _num(lx), _num(ly), _num(frot)],
                  ["size", _num(size_wh[0]), _num(size_wh[1])],
                  *([["drill", _num(drill)]] if drill else []),
                  ["layers", *layers],
                  ["uuid", U(tag)]]
    if rratio is not None:
        node.insert(-1, ["roundrect_rratio", rratio])
    if net:
        node.insert(-1, ["net", NET_ID[net], net])
    return node

def _fp_header(name: str, ref: str, value: str, x: float, y: float,
               rot: float, tag: str, attr: str, descr: str = "",
               ref_y: float = -2.0, ref_rot: float = 0.0) -> list:
    head: list = ["footprint", f"fe16:{name}", ["layer", "F.Cu"],
                  ["uuid", U(tag)], ["at", _num(x), _num(y), _num(rot)]]
    if descr:
        head.append(["descr", descr])
    head.append(_prop("Reference", ref, 0, ref_y, "F.SilkS", tag + ":ref", 0.8,
                      angle=ref_rot))
    head.append(_prop("Value", value, 0, 2.0, "F.Fab", tag + ":val", 0.8))
    head.append(["attr", attr])
    return head

def _line(x1, y1, x2, y2, layer, tag, w=0.12) -> list:
    return ["fp_line", ["start", _num(x1), _num(y1)], ["end", _num(x2), _num(y2)],
            ["stroke", ["width", w], ["type", "solid"]],
            ["layer", layer], ["uuid", U(tag)]]

def _text(s, x, y, layer, tag, size=0.8, rot=0.0) -> list:
    return ["fp_text", "user", s, ["at", _num(x), _num(y), _num(rot)],
            ["layer", layer], ["uuid", U(tag)],
            ["effects", ["font", ["size", size, size], ["thickness", 0.12]]]]

def _gr_text(s, x, y, tag, size=0.8, rot=0.0, layer="F.SilkS") -> list:
    """板级丝印文字（非封装内）。ASCII，避免贴片厂字体渲染成方块。"""
    return ["gr_text", s, ["at", _num(x), _num(y), _num(rot)],
            ["layer", layer], ["uuid", U(tag)],
            ["effects", ["font", ["size", size, size], ["thickness", 0.12]]]]

# ---------------------------------------------------------------------------
# 封装构建
# ---------------------------------------------------------------------------
def fp_0805(ref: str, value: str, x: float, y: float, rot: float,
            kind: str = "R") -> list:
    net1 = PAD_NET.get((ref, "1")); net2 = PAD_NET.get((ref, "2"))
    w, h = PAD_0805
    # ref 避让：rot±90 时文本随封装旋转成竖排会扫到自己 pad → 反旋 90 保持
    # 横排；C2/C3/C5/C6 下移 2mm 避开 U2/U3/U5/U6 底丝印线（silk_overlap）
    rr = rot if abs(rot) % 180 == 90 else 0.0
    ry = 2.0 if ref in {"C2", "C3", "C5", "C6"} else -2.0
    # 封装名必须随 kind 变（C_0805 / R_0805）。两者 pad 几何相同，但若电容
    # 沿用 R_0805，BOM/贴片坐标里的 Device/Footprint 会把 C1..C7 标成电阻，
    # 贴片厂按器件类型贴装就会贴错件。
    fp = _fp_header(f"{kind}_0805_2012Metric", ref, value, x, y, rot, ref, "smd",
                    ref_y=ry, ref_rot=rr)
    fp += [_line(-1.6, -0.75, -1.6, 0.75, "F.SilkS", ref + ":s1"),
           _line(1.6, -0.75, 1.6, 0.75, "F.SilkS", ref + ":s2"),
           _line(-1.7, -1.0, 1.7, -1.0, "F.CrtYd", ref + ":c1", 0.05),
           _line(1.7, -1.0, 1.7, 1.0, "F.CrtYd", ref + ":c2", 0.05),
           _line(1.7, 1.0, -1.7, 1.0, "F.CrtYd", ref + ":c3", 0.05),
           _line(-1.7, 1.0, -1.7, -1.0, "F.CrtYd", ref + ":c4", 0.05)]
    for p, (lx, ly) in pads_0805().items():
        fp.append(_pad(p, "smd", "roundrect", lx, ly, (w, h),
                       ["F.Cu", "F.Mask", "F.Paste"], rot,
                       PAD_NET.get((ref, str(p))), f"{ref}:p{p}", rratio=0.25))
    return fp

def fp_r0805(ref: str, value: str, x: float, y: float, rot: float) -> list:
    return fp_0805(ref, value, x, y, rot, kind="R")

def fp_c0805(ref: str, value: str, x: float, y: float, rot: float) -> list:
    return fp_0805(ref, value, x, y, rot, kind="C")

def fp_tht_r(ref: str, value: str, x: float, y: float, rot: float) -> list:
    """直插立式电阻：两孔上下排、孔距 2.54mm，电阻体竖立在两孔之间。

    引脚弯 90°，本体立起来，2D 占位约 2.8×5.4mm。孔 0.8 / 盘 1.6，
    兼容 0.5mm 直插电阻引脚。rot=0 时 pad1 在上（y 小）、pad2 在下（y+2.54）。
    """
    fp = _fp_header("R_Axial_P2.54mm_Vertical", ref, value, x, y, rot, ref,
                    "through_hole", "直插立式电阻 2.54mm", ref_y=-2.2,
                    ref_rot=0.0)
    # 丝印：竖立电阻体外框（两孔外侧各一横线 + 侧边）；F.CrtYd 矩形
    fp += [_line(-1.3, -1.3, 1.3, -1.3, "F.SilkS", ref + ":s1"),
           _line(-1.3, 3.84, 1.3, 3.84, "F.SilkS", ref + ":s2"),
           _line(-1.4, -1.4, 1.4, -1.4, "F.CrtYd", ref + ":c1", 0.05),
           _line(1.4, -1.4, 1.4, 3.94, "F.CrtYd", ref + ":c2", 0.05),
           _line(1.4, 3.94, -1.4, 3.94, "F.CrtYd", ref + ":c3", 0.05),
           _line(-1.4, 3.94, -1.4, -1.4, "F.CrtYd", ref + ":c4", 0.05)]
    for p, (lx, ly) in pads_tht_r().items():
        fp.append(_pad(p, "thru_hole", "circle", lx, ly, PAD_THT_R,
                       ["*.Cu", "*.Mask"], rot,
                       PAD_NET.get((ref, str(p))), f"{ref}:p{p}",
                       drill=DRILL_THT_R))
    return fp

def fp_soic14(ref: str, value: str, x: float, y: float, rot: float) -> list:
    fp = _fp_header("SOIC-14_3.9x8.7mm_P1.27mm", ref, value, x, y, rot, ref,
                    "smd", "SOIC-14")
    # 丝印 body 轮廓 + pin1 圆点
    fp += [_line(-2.0, -4.5, 2.0, -4.5, "F.SilkS", ref + ":s1"),
           _line(-2.0, 4.5, 2.0, 4.5, "F.SilkS", ref + ":s2"),
           _line(-3.3, -4.7, -3.3, 4.7, "F.CrtYd", ref + ":c1", 0.05),
           _line(-3.3, 4.7, 3.3, 4.7, "F.CrtYd", ref + ":c2", 0.05),
           _line(3.3, 4.7, 3.3, -4.7, "F.CrtYd", ref + ":c3", 0.05),
           _line(3.3, -4.7, -3.3, -4.7, "F.CrtYd", ref + ":c4", 0.05),
           ["fp_circle", ["center", -3.6, -4.445], ["end", -3.3, -4.445],
            ["stroke", ["width", 0.12], ["type", "solid"]],
            ["fill", "none"], ["layer", "F.SilkS"], ["uuid", U(ref + ":dot")]],
           _text("1A", -1.0, -3.81, "F.Fab", ref + ":t1", 0.5),
           _text("7", -1.0, 3.81, "F.Fab", ref + ":t7", 0.5)]
    pw, ph = PAD_SOIC14
    for p, (lx, ly) in pads_soic14().items():
        fp.append(_pad(p, "smd", "roundrect", lx, ly, (pw, ph),
                       ["F.Cu", "F.Mask", "F.Paste"], rot,
                       PAD_NET.get((ref, str(p))), f"{ref}:p{p}", rratio=0.25))
    return fp

def fp_idc(ref: str, npairs: int, x: float, y: float, rot: float) -> list:
    name = f"IDC-Header_2x{npairs}_P2.54mm"
    # 竖排封装（JA/JB rot±90）ref 跟随旋转：水平 ref 会横穿自己的外框丝印
    rr = rot if abs(rot) % 180 == 90 else 0.0
    fp = _fp_header(name, ref, f"IDC-2x{npairs}", x, y, rot, ref,
                    "through_hole", "IDC 简牛/双排针 2.54mm", ref_rot=rr)
    L = (npairs - 1) * 2.54
    # 外壳丝印（牛角座外框，排针同孔兼容）+ 键槽缺口 + pin1 三角
    fp += [_line(-2.7, -2.7, L + 2.7, -2.7, "F.SilkS", ref + ":b1"),
           _line(L + 2.7, -2.7, L + 2.7, 5.24, "F.SilkS", ref + ":b2"),
           _line(L + 2.7, 5.24, -2.7, 5.24, "F.SilkS", ref + ":b3"),
           _line(-2.7, 5.24, -2.7, -2.7, "F.SilkS", ref + ":b4"),
           _line(L / 2 - 1.27, -2.7, L / 2 - 1.27, -1.4, "F.SilkS", ref + ":k1"),
           _line(L / 2 + 1.27, -2.7, L / 2 + 1.27, -1.4, "F.SilkS", ref + ":k2"),
           ["fp_poly", ["pts", ["xy", -2.7, -3.4], ["xy", -1.2, -2.7],
             ["xy", -2.7, -2.0]],
            ["stroke", ["width", 0.1], ["type", "solid"]],
            ["fill", "solid"], ["layer", "F.SilkS"], ["uuid", U(ref + ":p1tri")]],
           _text("1", -3.6, -1.27, "F.SilkS", ref + ":t1", 0.8)]
    sw, sh = PAD_IDC_HOLE
    for p, (lx, ly) in pads_idc(npairs).items():
        shape = "rect" if p == 1 else "circle"
        fp.append(_pad(p, "thru_hole", shape, lx, ly, (sw, sh),
                       ["*.Cu", "*.Mask"], rot,
                       PAD_NET.get((ref, str(p))), f"{ref}:p{p}", drill=DRILL_IDC))
    return fp

def fp_tp(ref: str, x: float, y: float) -> list:
    # TP33-48 pitch 2.1mm < 横排 4 字符宽 ≈3.2mm → 相邻 ref 互叠；
    # 改竖排（local −2.8 + 90°）：文本宽 0.8 横跨 pitch，纵向 spans 17.6..20.8
    # 距 pad 顶 21.05 间隙 0.25
    # TP1..16 ref 下置（+2）：上置会探进 C3/C6 焊盘与丝印（silk_over_copper×4）
    n = int(ref[2:])
    if 33 <= n <= 48:
        ry, rr = -2.8, 90.0
    elif n <= 16:
        ry, rr = 2.0, 0.0
    else:
        ry, rr = -2.0, 0.0
    fp = _fp_header("TestPoint_THTPad_1.7mm", ref, "TestPoint", x, y, 0.0,
                    ref, "through_hole", ref_y=ry, ref_rot=rr)
    fp.append(_pad(1, "thru_hole", "circle", 0, 0, PAD_TP,
                   ["*.Cu", "*.Mask"], 0.0,
                   PAD_NET.get((ref, "1")), ref + ":p1", drill=DRILL_TP))
    return fp

def fp_hdr2(ref: str, value: str, x: float, y: float, rot: float) -> list:
    fp = _fp_header("PinHeader_1x02_P2.54mm", ref, value, x, y, rot, ref,
                    "through_hole")
    fp += [_line(-1.27, -1.27, 3.81, -1.27, "F.SilkS", ref + ":b1"),
           _line(3.81, -1.27, 3.81, 3.81, "F.SilkS", ref + ":b2"),
           _line(3.81, 3.81, -1.27, 3.81, "F.SilkS", ref + ":b3"),
           _line(-1.27, 3.81, -1.27, -1.27, "F.SilkS", ref + ":b4")]
    for p, (lx, ly) in pads_idc(1).items():
        shape = "rect" if p == 1 else "circle"
        fp.append(_pad(p, "thru_hole", shape, lx, ly, (1.7, 1.7),
                       ["*.Cu", "*.Mask"], rot,
                       PAD_NET.get((ref, str(p))), f"{ref}:p{p}", drill=1.0))
    return fp

def fp_mh(ref: str, x: float, y: float, rot: float = 0.0) -> list:
    return ["footprint", "fe16:MountingHole_3.2mm", ["layer", "F.Cu"],
            ["uuid", U(ref)], ["at", _num(x), _num(y), 0],
            ["attr", "exclude_from_pos_files", "exclude_from_bom"],
            _prop("Reference", ref, 0, -3.0, "F.SilkS", ref + ":ref", 0.8, hide=True),
            _prop("Value", "MountingHole", 0, 3.0, "F.Fab", ref + ":val", 0.8, hide=True),
            ["fp_circle", ["center", 0, 0], ["end", 3.0, 0],
             ["stroke", ["width", 0.05], ["type", "solid"]],
             ["fill", "none"], ["layer", "F.CrtYd"], ["uuid", U(ref + ":cy")]],
            ["pad", "", "np_thru_hole", "circle", ["at", 0, 0, 0],
             ["size", PAD_MH[0], PAD_MH[1]], ["drill", DRILL_MH],
             ["layers", "*.Cu", "*.Mask"], ["uuid", U(ref + ":p")]]]

# ---------------------------------------------------------------------------
# 放置
# ---------------------------------------------------------------------------
def placements() -> dict[str, tuple[str, float, float, float]]:
    P: dict[str, tuple[str, float, float, float]] = {}
    P["J5"] = ("idc18", *J5_ORIGIN, 0.0)
    P["JA"] = ("idc10", *JA_ORIGIN, IDC_ROT_Y)
    P["JB"] = ("idc10", *JB_ORIGIN, IDC_ROT_Y)
    for r, (px, py) in IC_POS.items():
        P[r] = ("soic", px, py, 0.0)
    # 直插立式电阻（2026-10-24：队友购直插，49 颗电阻改立式，孔距 2.54 竖向）
    # 每列 8 个。RS：U输出→JA，放左侧（U 与 JA 之间）。
    # RU：J5→U输入，放 U 右侧中央空区——原先放最左会导致 ACTRL 横穿 RS 列造成
    #     拥塞（Freerouting 漏布 ACTRL4/8/11）；移到中央后不再交叉。
    # RP：JB→U输入，放右侧。中央列 yp=5 避开底部 U3/U6（y≈62）。
    def tht_col(prefix: str, start: int, x: float, y0: float = 22.0,
                yp: float = 6.0) -> None:
        for i in range(8):
            P[f"{prefix}{start + i}"] = ("r", x, y0 + i * yp, 0.0)
    tht_col("RS", 1, 16.0)
    tht_col("RS", 9, 23.0)
    tht_col("RU", 1, 41.0, yp=5.0)   # 列左移让开底部 U6；yp 保持 5 防间距违规
    tht_col("RU", 9, 47.0, yp=5.0)
    tht_col("RP", 1, 68.0)           # RP 左移让开 JB，给 B 端留通道
    tht_col("RP", 9, 74.0)
    P["C1"] = ("c", 36.0, 23.5, 0.0)
    P["C2"] = ("c", 36.0, 68.5, 0.0)
    P["C3"] = ("c", 44.0, 74.0, 0.0)
    P["C4"] = ("c", 60.0, 23.5, 0.0)   # 让开 TP33-48 行（铜边距冲突）
    P["C5"] = ("c", 60.0, 68.5, 0.0)
    P["C6"] = ("c", 52.0, 74.0, 0.0)
    P["C7"] = ("c", *C7_POS, 0.0)
    P["RCT1"] = ("r", 91.0, 20.0, 0.0)   # 直插立式；移至右上空区（避开 RP 列/JB）
    P["JP1"] = ("hdr", *JP1_POS, 0.0)
    P["EXT1"] = ("hdr", *EXT_POS, 0.0)
    for i in range(16):                       # TPA1..16 底排（y=77）
        P[f"TP{i + 1}"] = ("tp", 18.0 + i * 4.0, 77.0, 0.0)   # 4.0 pitch: blob 缝 3-4 格防横线封死
    for i in range(16):                       # TPB17..32 底排第二行（y=83）右移靠近 B 端（2.9mm 间距防违规）
        P[f"TP{17 + i}"] = ("tp", 36.0 + i * 2.9, 83.0, 0.0)
    for i in range(16):                       # TPR33..48 J5 正下横排（y=17）
        P[f"TP{33 + i}"] = ("tp", 32.0 + i * 2.1, 17.0, 0.0)
    P["TP49"] = ("tp", 16.0, 17.0, 0.0)
    P["TP50"] = ("tp", 21.0, 17.0, 0.0)
    P["TP51"] = ("tp", 26.0, 17.0, 0.0)
    for i, (mx, my) in enumerate(MH_POS, start=1):
        P[f"H{i}"] = ("mh", mx, my, 0.0)
    return P

REF_VALUE = {ref: val for ref, val, _f, _d in bom_rows()}
BUILDERS = {
    "idc18": lambda ref, x, y, r: fp_idc(ref, 18, x, y, r),
    "idc10": lambda ref, x, y, r: fp_idc(ref, 10, x, y, r),
    "soic": lambda ref, x, y, r: fp_soic14(ref, REF_VALUE[ref], x, y, r),
    "r": lambda ref, x, y, r: fp_tht_r(ref, REF_VALUE[ref], x, y, r),
    "c": lambda ref, x, y, r: fp_c0805(ref, REF_VALUE[ref], x, y, r),
    "tp": lambda ref, x, y, r: fp_tp(ref, x, y),
    "hdr": lambda ref, x, y, r: fp_hdr2(ref, REF_VALUE[ref], x, y, r),
    "mh": lambda ref, x, y, r: fp_mh(ref, x, y),
}

# ---------------------------------------------------------------------------
# PCB
# ---------------------------------------------------------------------------
def build_pcb(segments=(), vias=()) -> str:
    root: list = ["kicad_pcb", ["version", 20240108],
                  ["generator", "gen_frontend16"],
                  ["generator_version", "8.0"],
                  ["general", ["thickness", 1.6]],
                  ["paper", "A4"],
                  ["layers",
                   [0, "F.Cu", "signal"], [31, "B.Cu", "signal"],
                   [36, "B.SilkS", "user", "B.Silkscreen"],
                   [37, "F.SilkS", "user", "F.Silkscreen"],
                   [38, "B.Mask", "user"], [39, "F.Mask", "user"],
                   [34, "B.Paste", "user"], [35, "F.Paste", "user"],
                   [44, "Edge.Cuts", "user"], [46, "B.CrtYd", "user"],
                   [47, "F.CrtYd", "user"], [48, "B.Fab", "user"],
                   [49, "F.Fab", "user"]],
                  ["setup", ["pad_to_mask_clearance", 0],
                   ["allow_soldermask_bridges_in_footprints", "no"]]]
    for i, n in enumerate(NETS):
        root.append(["net", i, n])
    for ref, (kind, x, y, r) in placements().items():
        root.append(BUILDERS[kind](ref, x, y, r))
    # 供电区丝印说明（10-15 补）：
    #   JP1 XOR RCT1 —— 两条供电通路互斥，同时接会并联两路电源（竖排，贴电源区右缘）
    #   +3V3 / GND   —— EXT1 竖排两脚：上=3.3V 入口、下=地（与各自引脚同高）
    #   3V3 ONLY     —— 禁止往 EXT1 灌 5V
    for _i, (_s, _x, _y, _r) in enumerate((
            ("JP1 XOR RCT1", 89.6, 10.0, 90.0),
            ("+3V3", 80.8, 13.5, 0.0),
            ("GND", 80.8, 16.04, 0.0),
            ("3V3 ONLY", 84.0, 18.4, 0.0))):
        root.append(_gr_text(_s, _x, _y, f"silk_pwr{_i}", rot=_r))
    # 板框
    m = 0.0
    corners = [(m, m), (BOARD_W, m), (BOARD_W, BOARD_H), (m, BOARD_H)]
    for i in range(4):
        x1, y1 = corners[i]
        x2, y2 = corners[(i + 1) % 4]
        root.append(["gr_line", ["start", _num(x1), _num(y1)],
                     ["end", _num(x2), _num(y2)],
                     ["stroke", ["width", 0.1], ["type", "solid"]],
                     ["layer", "Edge.Cuts"], ["uuid", U(f"edge{i}")]])
    for s in segments:
        root.append(["segment", ["start", _num(s["a"][0]), _num(s["a"][1])],
                     ["end", _num(s["b"][0]), _num(s["b"][1])],
                     ["width", _num(s.get("w", 0.25))],
                     ["layer", s["layer"]],
                     ["net", NET_ID[s["net"]]], ["uuid", U(s["uuid"])]])
    for v in vias:
        root.append(["via", ["at", _num(v["p"][0]), _num(v["p"][1])],
                     ["size", 0.6], ["drill", 0.3],
                     ["layers", "F.Cu", "B.Cu"],
                     ["net", NET_ID[v["net"]]], ["uuid", U(v["uuid"])]])
    return "\n".join(_pretty(root)) + "\n"

def _pretty(node, ind=0) -> list[str]:
    s = sx(node)
    if len(s) < 110 and "\n" not in s:
        return ["  " * ind + s]
    out = ["  " * ind + "(" + (node[0] if node else "")]
    head = node[0] if node and isinstance(node[0], str) else ""
    parts = []
    line = "  " * ind + "("
    first = True
    for x in node:
        piece = sx(x, first)
        if first:
            line += piece
            first = False
        else:
            if len(line) + len(piece) + 1 > 110:
                parts.append(line)
                line = "  " * (ind + 1) + piece
            else:
                line += " " + piece
    parts.append(line + ")")
    del out
    return parts

# ---------------------------------------------------------------------------
# 原理图
# ---------------------------------------------------------------------------
def _lib_r() -> list:
    return ["symbol", "fe16:R",
            ["pin_numbers", ["hide", "yes"]] if False else ["pin_numbers"],
            ["pin_names", ["offset", 0]],
            ["exclude_from_sim", "no"], ["in_bom", "yes"], ["on_board", "yes"],
            _prop("Reference", "R", 2.032, 0, "F.Fab", "lib:R:ref", 1.27),
            _prop("Value", "R", 0, 0, "F.Fab", "lib:R:val", 1.27),
            _prop("Footprint", "", 0, 0, "F.Fab", "lib:R:fp", 1.27, hide=True),
            ["symbol", "R_0_1",
             ["rectangle", ["start", -1.016, -2.54], ["end", 1.016, 2.54],
              ["stroke", ["width", 0.254], ["type", "default"]],
              ["fill", ["type", "none"]]]],
            ["symbol", "R_1_1",
             _pin("1", "passive", -3.81, 0, 0, 2.792),
             _pin("2", "passive", 3.81, 0, 180, 2.792)]]

def _lib_c() -> list:
    """电容符号 fe16:C（两片平行极板；0805 瓷片无极性，不画极性标记）。

    原先电容复用 fe16:R，导出到 EasyEDA/贴片文件后 C1..C7 的器件类型变成
    电阻，故独立建符号。
    """
    return ["symbol", "fe16:C",
            ["pin_numbers"],
            ["pin_names", ["offset", 0]],
            ["exclude_from_sim", "no"], ["in_bom", "yes"], ["on_board", "yes"],
            _prop("Reference", "C", 2.032, 0, "F.Fab", "lib:C:ref", 1.27),
            _prop("Value", "C", 0, 0, "F.Fab", "lib:C:val", 1.27),
            _prop("Footprint", "", 0, 0, "F.Fab", "lib:C:fp", 1.27, hide=True),
            ["symbol", "C_0_1",
             ["polyline", ["pts", ["xy", -0.508, -1.27], ["xy", -0.508, 1.27]],
              ["stroke", ["width", 0.3048], ["type", "default"]],
              ["fill", ["type", "none"]]],
             ["polyline", ["pts", ["xy", 0.508, -1.27], ["xy", 0.508, 1.27]],
              ["stroke", ["width", 0.3048], ["type", "default"]],
              ["fill", ["type", "none"]]]],
            ["symbol", "C_1_1",
             _pin("1", "passive", -3.81, 0, 0, 3.302),
             _pin("2", "passive", 3.81, 0, 180, 3.302)]]

def _lib_hdr2() -> list:
    """2 脚排针符号 fe16:HDR-1x2（JP1/EXT1 用；原先复用 fe16:R）。"""
    return ["symbol", "fe16:HDR-1x2",
            ["pin_names", ["offset", 0.254]],
            ["exclude_from_sim", "no"], ["in_bom", "yes"], ["on_board", "yes"],
            _prop("Reference", "J", 0, 5.08, "F.Fab", "lib:HDR:ref", 1.27),
            _prop("Value", "HDR-1x2", 0, -5.08, "F.Fab", "lib:HDR:val", 1.27),
            _prop("Footprint", "", 0, 0, "F.Fab", "lib:HDR:fp", 1.27, hide=True),
            ["symbol", "HDR1x2_0_1",
             ["rectangle", ["start", -1.27, -1.27], ["end", 1.27, 1.27],
              ["stroke", ["width", 0.254], ["type", "default"]],
              ["fill", ["type", "background"]]]],
            ["symbol", "HDR1x2_1_1",
             _pin("1", "passive", -3.81, 0, 0, 2.54),
             _pin("2", "passive", 3.81, 0, 180, 2.54)]]

def _pin(num, etype, x, y, ang, length, name="~") -> list:
    return ["pin", etype, "line", ["at", x, y, ang], ["length", length],
            ["name", name, ["effects", ["font", ["size", 1.27, 1.27]]]],
            ["number", str(num), ["effects", ["font", ["size", 1.27, 1.27]]]]]

def _lib_ic(kind: str) -> list:
    """kind: '07' 开漏 / '14' 施密特反相。符号脚位按功能排（非物理位置）。"""
    name = f"fe16:LVC{kind}"
    pins_left = []   # 输入 1,3,5,9,11,13
    pins_right = []  # 输出 2,4,6,8,10,12
    order_l = [1, 3, 5, 9, 11, 13]
    order_r = [2, 4, 6, 8, 10, 12]
    # KiCad 符号库 y 轴向上（渲染 y = Y - ly）：正 y 渲染在上，
    # 故 pin1/VCC 取正 y、GND 取负 y，与数据手册惯例一致
    y0 = 7.62
    for i, p in enumerate(order_l):
        pins_left.append(_pin(p, "input", -10.16, y0 - i * 3.048, 0, 5.08,
                              f"{p // 2 + 1}A" if p % 2 else ""))
    etype = "open_collector" if kind == "07" else "output"
    for i, p in enumerate(order_r):
        pins_right.append(_pin(p, etype, 10.16, y0 - i * 3.048, 180, 5.08,
                               ""))
    pins_top = [_pin(PIN_VCC, "power_in", 0, 12.7, 270, 5.08, "VCC")]
    pins_bot = [_pin(PIN_GND, "power_in", 0, -12.7, 90, 5.08, "GND")]
    return ["symbol", name,
            ["pin_names", ["offset", 0.254]],
            ["exclude_from_sim", "no"], ["in_bom", "yes"], ["on_board", "yes"],
            _prop("Reference", "U", 0, 15.24, "F.Fab", f"lib:{name}:ref", 1.27),
            _prop("Value", f"74LVC{kind}A", 0, -15.24, "F.Fab", f"lib:{name}:val", 1.27),
            _prop("Footprint", "", 0, 0, "F.Fab", f"lib:{name}:fp", 1.27, hide=True),
            ["symbol", f"LVC{kind}_0_1",
             ["rectangle", ["start", -7.62, -11.43], ["end", 7.62, 11.43],
              ["stroke", ["width", 0.254], ["type", "default"]],
              ["fill", ["type", "background"]]]],
            ["symbol", f"LVC{kind}_1_1", *pins_left, *pins_right,
             *pins_top, *pins_bot]]

def _lib_conn(name: str, npins: int) -> list:
    # y 轴向上：pin1 取正 y 渲染在最上（与 _pin_abs 的取负配套）。
    # 奇数脚左列、偶数脚右列：符号同一行 = pads_idc 列对式（IDC 排线蛇形）
    # 的同一物理列，逐针对线时符号行与实物列一一对应
    half = npins // 2
    pins = []
    # name 用默认 "~"（隐藏）：连接器只显示 number，避免体内数字与标签叠字
    for i in range(half):
        pins.append(_pin(2 * i + 1, "passive", -10.16,
                         half * 1.27 - 1.27 - i * 2.54,
                         0, 5.08))
    for i in range(half):
        pins.append(_pin(2 * i + 2, "passive", 10.16,
                         half * 1.27 - 1.27 - i * 2.54, 180, 5.08))
    h = half * 2.54
    return ["symbol", name,
            ["pin_names", ["offset", 0.254]],
            ["exclude_from_sim", "no"], ["in_bom", "yes"], ["on_board", "yes"],
            _prop("Reference", "J", 0, h / 2 + 2.54, "F.Fab", f"lib:{name}:ref", 1.27),
            _prop("Value", name.split(":")[1], 0, -h / 2 - 2.54, "F.Fab", f"lib:{name}:val", 1.27),
            _prop("Footprint", "", 0, 0, "F.Fab", f"lib:{name}:fp", 1.27, hide=True),
            ["symbol", f"{name.split(':')[1]}_0_1",
             ["rectangle", ["start", -7.62, -h / 2 - 1.27],
              ["end", 7.62, h / 2 + 1.27],
              ["stroke", ["width", 0.254], ["type", "default"]],
              ["fill", ["type", "background"]]]],
            ["symbol", f"{name.split(':')[1]}_1_1", *pins]]

def _lib_tp() -> list:
    return ["symbol", "fe16:TestPoint",
            ["pin_names", ["offset", 0.254]],
            ["exclude_from_sim", "no"], ["in_bom", "no"], ["on_board", "yes"],
            _prop("Reference", "TP", 0, 2.54, "F.Fab", "lib:tp:ref", 1.27),
            _prop("Value", "TestPoint", 0, 5.08, "F.Fab", "lib:tp:val", 1.27),
            _prop("Footprint", "", 0, 0, "F.Fab", "lib:tp:fp", 1.27, hide=True),
            ["symbol", "TestPoint_0_1",
             ["polyline", ["pts", ["xy", 0, 0], ["xy", 0, -1.27], ["xy", 1.27, -1.27],
               ["xy", 1.27, -2.54], ["xy", 0, -2.54]]],
             ["stroke", ["width", 0.254], ["type", "default"]],
             ["fill", ["type", "none"]]],
            ["symbol", "TestPoint_1_1",
             _pin(1, "passive", 0, 0, 270, 0, "1")]]
    # 上面 polyline 括号修正：
    # （结构错误会在 parse 时炸，见下方简单修正版）

def _lib_tp_ok() -> list:
    return ["symbol", "fe16:TestPoint",
            ["pin_names", ["offset", 0.254]],
            ["exclude_from_sim", "no"], ["in_bom", "no"], ["on_board", "yes"],
            _prop("Reference", "TP", 0, 2.54, "F.Fab", "lib:tp:ref", 1.27),
            _prop("Value", "TestPoint", 0, 5.08, "F.Fab", "lib:tp:val", 1.27),
            _prop("Footprint", "", 0, 0, "F.Fab", "lib:tp:fp", 1.27, hide=True),
            ["symbol", "TestPoint_0_1",
             ["polyline",
              ["pts", ["xy", 0, 0], ["xy", 0, -1.27], ["xy", 1.27, -1.27],
               ["xy", 1.27, -2.54], ["xy", 0, -2.54]],
              ["stroke", ["width", 0.254], ["type", "default"]],
              ["fill", ["type", "none"]]]],
            ["symbol", "TestPoint_1_1",
             _pin(1, "passive", 0, 0, 270, 0, "1")]]

def _lib_pwr_flag() -> list:
    return ["symbol", "power:PWR_FLAG",
            ["power"], ["pin_numbers", ["hide", "yes"]],
            ["pin_names", ["offset", 0]], ["exclude_from_sim", "no"],
            ["in_bom", "no"], ["on_board", "yes"],
            _prop("Reference", "#FLG", 0, 1.905, "F.Fab", "lib:flg:ref", 1.27, True),
            _prop("Value", "PWR_FLAG", 0, 3.81, "F.Fab", "lib:flg:val", 1.27),
            _prop("Footprint", "", 0, 0, "F.Fab", "lib:flg:fp", 1.27, hide=True),
            ["symbol", "PWR_FLAG_0_1",
             ["polyline",
              ["pts", ["xy", 0, 0], ["xy", 0, 1.27], ["xy", -1.016, 1.905],
               ["xy", 0, 2.54], ["xy", 1.016, 1.905], ["xy", 0, 1.27]],
              ["stroke", ["width", 0], ["type", "default"]],
              ["fill", ["type", "none"]]]],
            ["symbol", "PWR_FLAG_1_1",
             _pin(1, "power_out", 0, 0, 90, 0, "pwr")]]

# 原理图符号 pin 位置：lib pin (at lx ly ang) 相对实例 (at X Y R)
def _pin_abs(lx, ly, ang, X, Y, R) -> tuple[float, float, float]:
    # KiCad 符号局部坐标 y 轴向上、画布 y 向下（kicad-cli ERC 实测：
    # lib y=+12.7 渲染于实例 Y-12.7）→ 先取负再旋转，引脚角同步镜像
    a = math.radians(R)
    c, s = math.cos(a), math.sin(a)
    fx, fy = lx, -ly
    return (X + fx * c + fy * s, Y - fx * s + fy * c, (-ang + R) % 360)

def build_sch() -> str:
    # 实例位置（宽松网格；连线全靠 global label，布局只影响可读性）
    inst: dict[str, tuple[float, float, float]] = {}
    inst["J5"] = (77.47, 33.02, 0.0)          # 顶中
    inst["JA"] = (25.4, 60.96, 0.0)
    inst["JB"] = (157.48, 60.96, 0.0)
    for i, r in enumerate(("U1", "U2", "U3")):
        inst[r] = (76.2, 99.06 + i * 40.64, 0.0)
    for i, r in enumerate(("U4", "U5", "U6")):
        inst[r] = (177.8, 99.06 + i * 40.64, 0.0)
    # 无源竖列
    for ch in range(16):
        inst[f"RU{ch + 1}"] = (38.1, 45.72 + ch * 7.62, 0.0)
        inst[f"RS{ch + 1}"] = (50.8, 45.72 + ch * 7.62, 0.0)
        inst[f"RP{ch + 1}"] = (129.54, 45.72 + ch * 7.62, 0.0)
    for i in range(1, 8):
        inst[f"C{i}"] = (101.6, 45.72 + (i - 1) * 7.62, 0.0)
    inst["RCT1"] = (129.54, 177.8, 0.0)
    inst["JP1"] = (129.54, 190.5, 0.0)
    inst["EXT1"] = (129.54, 203.2, 0.0)
    for i in range(1, 52):
        col, row = (i - 1) // 17, (i - 1) % 17
        inst[f"TP{i}"] = (215.9 + col * 20.32, 33.02 + row * 7.62, 0.0)
    # PWR_FLAG 挂四个电源网
    flags = {"VCC3V3": (114.3, 177.8), "GND": (114.3, 190.5),
             "VIN_J5": (114.3, 203.2), "VIN_EXT": (114.3, 215.9)}

    root: list = ["kicad_sch", ["version", 20231120],
                  ["generator", "gen_frontend16"],
                  ["generator_version", "8.0"],
                  ["uuid", U("schroot")], ["paper", "A3"],
                  ["title_block", ["title", "XunJi FE-16 16路前端"],
                   ["rev", "1.0"], ["company", "瞬狙"]]]
    lib_syms: list = ["lib_symbols", _lib_r(), _lib_c(), _lib_hdr2(),
                      _lib_ic("07"), _lib_ic("14"),
                      _lib_conn("fe16:IDC-2x18", 36),
                      _lib_conn("fe16:IDC-2x10", 20),
                      _lib_tp_ok(), _lib_pwr_flag()]
    root.append(lib_syms)

    def glabel(net: str, x: float, y: float, ang: float, tag: str) -> list:
        return ["global_label", net,
                ["shape", "bidirectional"],
                ["at", _num(x), _num(y), _num(ang)],
                ["fields_autoplaced", "yes"],
                ["effects", ["font", ["size", 1.27, 1.27]],
                 ["justify", "left"]],
                ["uuid", U(tag)],
                ["property", "Intersheetrefs", "${INTERSHEET_REFS}",
                 ["at", _num(x), _num(y), 0],
                 ["effects", ["font", ["size", 1.27, 1.27]], ["hide", "yes"]]]]

    def noconnect(x, y, tag) -> list:
        return ["no_connect", ["at", _num(x), _num(y)], ["uuid", U(tag)]]

    # 实例符号 + 每 pin 贴 label / NC / 不贴
    def place(ref: str, lib_id: str, pins: dict[str, tuple], n_pins: int) -> None:
        X, Y, R = inst[ref]
        node: list = ["symbol", ["lib_id", lib_id], ["at", _num(X), _num(Y), _num(R)],
                      ["unit", 1], ["exclude_from_sim", "no"],
                      ["in_bom", "yes"], ["on_board", "yes"], ["dnp", "no"],
                      ["uuid", U(ref + ":inst")],
                      _prop("Reference", ref, X, Y - 5.08, "F.Fab", ref + ":sref", 1.27),
                      _prop("Value", pins["__val__"], X, Y + 5.08, "F.Fab", ref + ":sval", 1.27),
                      _prop("Footprint", "", X, Y, "F.Fab", ref + ":sfp", 1.27, True)]
        for p in range(1, n_pins + 1):
            node.append(["pin", str(p), ["uuid", U(f"{ref}:pin{p}")]])
        root.append(node)
        # 按网表贴 label
        for p in range(1, n_pins + 1):
            net = PAD_NET.get((ref, str(p)))
            lx, ly, ang = pins[str(p)]
            ax, ay, _a = _pin_abs(lx, ly, ang, X, Y, R)
            if net is None:
                root.append(noconnect(ax, ay, f"{ref}:nc{p}"))
            else:
                root.append(glabel(net, ax, ay, _a, f"{ref}:gl{p}"))

    # 各符号 pin 的 lib 局部坐标表
    def r_pins():
        return {"__val__": "", "1": (-3.81, 0, 0), "2": (3.81, 0, 180)}
    def ic_pins(kind):
        # 与 _lib_ic 的 y 同步取负（y 轴向上，标签必须贴渲染后的引脚）
        d = {"__val__": f"74LVC{kind}A"}
        order_l = [1, 3, 5, 9, 11, 13]
        order_r = [2, 4, 6, 8, 10, 12]
        for i, p in enumerate(order_l):
            d[str(p)] = (-10.16, 7.62 - i * 3.048, 0)
        for i, p in enumerate(order_r):
            d[str(p)] = (10.16, 7.62 - i * 3.048, 180)
        d[str(PIN_VCC)] = (0, 12.7, 270)
        d[str(PIN_GND)] = (0, -12.7, 90)
        return d
    def conn_pins(npins):
        # 与 _lib_conn 同构：奇左偶右，同 y 为同一物理列
        d = {"__val__": ""}
        half = npins // 2
        for i in range(half):
            y = half * 1.27 - 1.27 - i * 2.54
            d[str(2 * i + 1)] = (-10.16, y, 0)
            d[str(2 * i + 2)] = (10.16, y, 180)
        return d
    def tp_pins():
        return {"__val__": "TestPoint", "1": (0, 0, 270)}

    place("J5", "fe16:IDC-2x18", conn_pins(36), 36)
    place("JA", "fe16:IDC-2x10", conn_pins(20), 20)
    place("JB", "fe16:IDC-2x10", conn_pins(20), 20)
    for r in ("U1", "U2", "U3"):
        place(r, "fe16:LVC07", ic_pins("07"), 14)
    for r in ("U4", "U5", "U6"):
        place(r, "fe16:LVC14", ic_pins("14"), 14)
    for ch in range(16):
        for pre, val in (("RU", "10k"), ("RS", "330"), ("RP", "4.7k")):
            ref = f"{pre}{ch + 1}"
            pins = r_pins(); pins["__val__"] = val
            place(ref, "fe16:R", pins, 2)
    for i in range(1, 8):
        ref = f"C{i}"
        pins = r_pins(); pins["__val__"] = "100nF" if i <= 6 else "10uF"
        place(ref, "fe16:C", pins, 2)   # 电容用 fe16:C（原先复用 R 符号，导出后器件类型变电阻）
    pins = r_pins(); pins["__val__"] = "0"
    place("RCT1", "fe16:R", pins, 2)    # RCT1 是 0Ω 电阻，保持 R 符号
    for ref in ("JP1", "EXT1"):
        pins = r_pins(); pins["__val__"] = "HDR-1x2"
        place(ref, "fe16:HDR-1x2", pins, 2)   # 排针用排针符号（原先复用 R 符号）
    for i in range(1, 52):
        place(f"TP{i}", "fe16:TestPoint", tp_pins(), 1)
    # PWR_FLAG
    for net, (x, y) in flags.items():
        root.append(["symbol", ["lib_id", "power:PWR_FLAG"], ["at", x, y, 0],
                     ["unit", 1], ["exclude_from_sim", "no"], ["in_bom", "no"],
                     ["on_board", "yes"], ["dnp", "no"], ["uuid", U(f"flg:{net}")],
                     _prop("Reference", "#FLG01", x, y - 1.905, "F.Fab", f"flg:{net}:r", 1.27, True),
                     _prop("Value", "PWR_FLAG", x, y + 3.81, "F.Fab", f"flg:{net}:v", 1.27),
                     _prop("Footprint", "", x, y, "F.Fab", f"flg:{net}:f", 1.27, True),
                     ["pin", "1", ["uuid", U(f"flg:{net}:pin")]]])
        root.append(glabel(net, x, y, 90, f"flg:{net}:gl"))
    # 页脚
    root.append(["sheet_instances", ["path", "/", ["page", "1"]]])

    def _strip_sym(node):
        # 8 格式 symbol property 不收 layer/uuid（kicad-cli 实测拒收）；pin uuid 保留
        if not isinstance(node, list):
            return node
        out = []
        for x in node:
            if isinstance(x, list) and x and x[0] == "property":
                out.append([y for y in x
                            if not (isinstance(y, list) and y
                                    and y[0] in ("layer", "uuid"))])
            else:
                out.append(_strip_sym(x))
        return out

    root = [_strip_sym(n) if isinstance(n, list) and n
            and n[0] in ("symbol", "lib_symbols") else n for n in root]
    return "\n".join(_pretty(root)) + "\n"

# ---------------------------------------------------------------------------
# BOM
# ---------------------------------------------------------------------------
def build_bom() -> str:
    import io
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Reference", "Value", "Footprint", "Description", "Qty"])
    rows = bom_rows()
    by_val: dict[tuple[str, str], list[str]] = {}
    for ref, val, fp, desc in rows:
        by_val.setdefault((val, fp, desc), []).append(ref)
    for (val, fp, desc), refs in by_val.items():
        w.writerow([" ".join(refs), val, fp, desc, len(refs)])
    return buf.getvalue()

def main() -> None:
    # 纯生成：无走线 PCB + 原理图 + BOM（布线由 freeroute 管线独立完成）
    PCB_OUT.write_text(build_pcb([], []), encoding="utf-8")
    SCH_OUT.write_text(build_sch(), encoding="utf-8")
    BOM_OUT.write_text(build_bom(), encoding="utf-8")
    print(f"WROTE {PCB_OUT.name} / {SCH_OUT.name} / {BOM_OUT.name}")

if __name__ == "__main__":
    main()
