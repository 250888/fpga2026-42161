"""瞬迹 FE-16 16路前端板 —— 设计数据唯一事实源。

全部内容由 V1.9 推导（§9 / §9.1 / TABLE 3 / TABLE 13 / TABLE 14），
生成器与机检都从这里取数；机检 tests/test_frontend_pcb.py 另行独立
硬编码期望表，与本模块互为交叉验证。

坐标系：KiCad 毫米，原点左上，x 向右，y 向下。
"""
from __future__ import annotations

N_CH = 16
BOARD_W, BOARD_H = 96.0, 96.0    # ≤10×10cm：嘉立创免费券板框上限

# ---------------------------------------------------------------------------
# 通道 → IC → 引脚（LVC07 与 LVC14 同为 74xx14/xx07 家族标准脚位）
#   每颗 6 通道：槽位 slot 0..5，(输入脚, 输出脚)
# ---------------------------------------------------------------------------
SLOT_PINS = {
    0: (1, 2), 1: (3, 4), 2: (5, 6),
    3: (9, 8), 4: (11, 10), 5: (13, 12),
}
PIN_GND, PIN_VCC = 7, 14
UNUSED_SLOTS = (4, 5)          # 仅 U3(U6) 的槽 4/5 未用

def channel_ic(ch: int, lvc07: bool) -> tuple[str, int]:
    """ch → (IC位号, slot)。LVC07: U1..U3；LVC14: U4..U6。"""
    base = 1 if lvc07 else 4
    return f"U{ch // 6 + base}", ch % 6

def channel_pins(ch: int) -> tuple[int, int]:
    """ch → (输入脚, 输出脚)。"""
    return SLOT_PINS[ch % 6]

# ---------------------------------------------------------------------------
# 网表：net_name -> frozenset{(ref, pin)}
# ---------------------------------------------------------------------------
POWER_NETS = ("GND", "VCC3V3", "VIN_J5", "VIN_EXT")

def build_netlist() -> dict[str, frozenset[tuple[str, str]]]:
    nl: dict[str, set[tuple[str, str]]] = {}

    def add(net: str, ref: str, pin) -> None:
        nl.setdefault(net, set()).add((ref, str(pin)))

    # J5：1..16=ACTRL0..15, 17..32=BRW0..15, 33/34=GND, 35/36=VIN_J5（TABLE 3）
    for ch in range(N_CH):
        add(f"ACTRL{ch}", "J5", ch + 1)
        add(f"BRW{ch}", "J5", 17 + ch)
    add("GND", "J5", 33)
    add("GND", "J5", 34)
    add("VIN_J5", "J5", 35)
    add("VIN_J5", "J5", 36)

    # A/B 口：1..16=信号；17..20=NC/KEY 故意不连网（TABLE 14 / §9.1）
    for ch in range(N_CH):
        add(f"A{ch}", "JA", ch + 1)
        add(f"B{ch}", "JB", ch + 1)

    for ch in range(N_CH):
        in_p, out_p = channel_pins(ch)
        u07, _ = channel_ic(ch, lvc07=True)
        u14, _ = channel_ic(ch, lvc07=False)
        # A 路：J5 → LVC07 输入（ACTRL 网）+ 安全上拉 → 开漏出 → 串阻 → A口
        add(f"ACTRL{ch}", u07, in_p)
        add(f"ACTRL{ch}", f"RU{ch + 1}", 1)
        add("VCC3V3", f"RU{ch + 1}", 2)
        add(f"ADRV{ch}", u07, out_p)
        add(f"ADRV{ch}", f"RS{ch + 1}", 1)
        add(f"A{ch}", f"RS{ch + 1}", 2)
        add(f"A{ch}", f"TP{ch + 1}", 1)
        # B 路：B口 → 上拉 Rp → LVC14 输入 → 整形反相出 → J5
        add(f"B{ch}", f"RP{ch + 1}", 1)
        add("VCC3V3", f"RP{ch + 1}", 2)
        add(f"B{ch}", u14, in_p)
        add(f"B{ch}", f"TP{17 + ch}", 1)
        add(f"BRW{ch}", u14, out_p)
        add(f"BRW{ch}", f"TP{33 + ch}", 1)

    # 六颗 IC 电源脚
    for i in range(1, 7):
        add("GND", f"U{i}", PIN_GND)
        add("VCC3V3", f"U{i}", PIN_VCC)

    # 未用通道：U3 输入固定高、U6 输入固定 GND；输出悬空（§9 / D8）
    for ref, net_in in (("U3", "VCC3V3"), ("U6", "GND")):
        for slot in UNUSED_SLOTS:
            in_p, _ = SLOT_PINS[slot]
            add(net_in, ref, in_p)

    # 去耦 C1..C6 每 IC 一颗 + C7 总旁路 10μF
    for c in ("C1", "C2", "C3", "C4", "C5", "C6", "C7"):
        add("VCC3V3", c, 1)
        add("GND", c, 2)

    # 电源断点 RCT1（0Ω）+ 备用入口互斥跳线 JP1 + EXT 焊盘（D15）
    add("VIN_J5", "RCT1", 1)
    add("VCC3V3", "RCT1", 2)
    add("VCC3V3", "JP1", 1)
    add("VIN_EXT", "JP1", 2)
    add("VIN_EXT", "EXT1", 1)
    add("GND", "EXT1", 2)

    # 电源测试点（TP49..51）
    add("VCC3V3", "TP49", 1)
    add("GND", "TP50", 1)
    add("VIN_J5", "TP51", 1)

    return {k: frozenset(v) for k, v in nl.items()}

# 位号清单（BOM 生成用）
REFS = (
    ["J5", "JA", "JB"]
    + [f"U{i}" for i in range(1, 7)]
    + [f"RS{i}" for i in range(1, 17)]   # A端串联 330Ω
    + [f"RU{i}" for i in range(1, 17)]   # LVC07 输入安全上拉 10k
    + [f"RP{i}" for i in range(1, 17)]   # B端上拉 Rp 4.7k（可替换）
    + [f"C{i}" for i in range(1, 8)]     # C1..6=100nF, C7=10μF
    + [f"TP{i}" for i in range(1, 52)]   # TP1..16=A, 17..32=B, 33..48=b_raw, 49..51=电源
    + ["RCT1", "JP1", "EXT1"]
    + [f"H{i}" for i in range(1, 5)]     # 安装孔
)

# BOM：位号 → (值, 封装, 描述)
def bom_rows() -> list[tuple[str, str, str, str]]:
    """返回 (位号, 值, 封装, 描述) 列表。"""
    rows = []
    for i in range(1, 17):
        rows.append((f"RS{i}", "330", "R_Axial_P2.54mm_Vertical", "A端串联保护(直插立式)"))
        rows.append((f"RU{i}", "10k", "R_Axial_P2.54mm_Vertical", "LVC07输入安全上拉(直插立式)"))
        rows.append((f"RP{i}", "4.7k", "R_Axial_P2.54mm_Vertical", "B端上拉Rp可替换(直插立式)"))
    for i in range(1, 7):
        rows.append((f"C{i}", "100nF", "C_0805_2012Metric", f"U{i}去耦"))
    rows.append(("C7", "10uF", "C_0805_2012Metric", "J5入口总旁路"))
    rows.append(("RCT1", "0", "R_Axial_P2.54mm_Vertical", "整板电流断点(测流取下,直插立式)"))
    rows.append(("JP1", "HDR-1x2", "PinHeader_1x02_P2.54mm", "EXT供电选择,与RCT1互斥"))
    rows.append(("EXT1", "HDR-1x2", "PinHeader_1x02_P2.54mm", "外部3.3V入口(仅3V3,禁5V)"))
    for i in range(1, 7):
        rows.append((f"U{i}", "SN74LVC07A" if i <= 3 else "SN74LVC14A",
                     "SOIC-14_3.9x8.7mm_P1.27mm",
                     "6路开漏缓冲" if i <= 3 else "6路施密特反相"))
    rows.append(("J5", "IDC-2x18", "IDC-Header_2x18_P2.54mm", "J5转接36Pin"))
    rows.append(("JA", "IDC-2x10", "IDC-Header_2x10_P2.54mm", "A端DUT 20Pin"))
    rows.append(("JB", "IDC-2x10", "IDC-Header_2x10_P2.54mm", "B端DUT 20Pin"))
    rows += [(f"TP{i}", "TestPoint", "TestPoint_THTPad_1.7mm", "")
             for i in range(1, 52)]
    rows += [(f"H{i}", "MountingHole", "MountingHole_3.2mm", "") for i in range(1, 5)]
    return rows

# ---------------------------------------------------------------------------
# 封装几何（焊盘局部坐标，mm；pad 尺寸 = (w, h)）
# ---------------------------------------------------------------------------
PAD_SOIC14 = (1.5, 0.6)
def pads_soic14() -> dict[int, tuple[float, float]]:
    out = {}
    for k in range(7):                       # 左排 pin1..7 上→下
        y = -3.81 + k * 1.27
        out[k + 1] = (-2.475, y)
        out[14 - k] = (2.475, y)             # 右排 pin14..8 上→下
    return out

PAD_0805 = (1.1, 1.4)
def pads_0805() -> dict[int, tuple[float, float]]:
    return {1: (-0.95, 0.0), 2: (0.95, 0.0)}

# 直插立式电阻（2026-10-24：队友购入直插电阻，49 颗电阻改直插；电容保持 0805）
PAD_THT_R = (1.6, 1.6)      # 盘径
DRILL_THT_R = 0.8           # 孔径（兼容 0.5mm 直插电阻引脚）
R_PITCH = 2.54              # 立式安装两孔距（引脚弯 90°，电阻体竖立）
def pads_tht_r() -> dict[int, tuple[float, float]]:
    """立式：两孔上下排（local y 方向），body 竖立在两孔之间。"""
    return {1: (0.0, 0.0), 2: (0.0, R_PITCH)}

PAD_IDC_HOLE, DRILL_IDC = (1.4, 1.4), 1.0    # 通孔焊盘(环宽0.2), 钻1.0；1.4 使 2.54 针缝格化后可过线
def pads_idc(n_pairs: int) -> dict[int, tuple[float, float]]:
    """2×N 列对式针序：pin1/pin2 同列相对，3/4 次列……（IDC 排线蛇形一致）。"""
    out = {}
    for p in range(1, 2 * n_pairs + 1):
        col, row = (p - 1) // 2, (p - 1) % 2
        out[p] = (col * 2.54, row * 2.54)
    return out

PAD_TP, DRILL_TP = (1.4, 1.4), 1.0           # 测试环（环宽0.2，与 IDC 统一）
PAD_MH, DRILL_MH = (3.2, 3.2), 3.2           # 安装孔 NPTH

# ---------------------------------------------------------------------------
# 布局锚点（mm，KiCad 坐标：原点左上、y 向下）
# ---------------------------------------------------------------------------
J5_ORIGIN = (26.4, 6.5)       # J5 pin1；列→x右，排1 y=6.5，排2 y=9.04（居中 x 26.4..69.58）
JA_ORIGIN = (10.27, 22.0)     # A口 pin1；rot=-90：列→y下，排1 x=10.27，排2 x=7.73
JB_ORIGIN = (85.73, 22.0)     # B口 pin1；rot=-90：排1 x=85.73，排2 x=83.19（=96-10.27 镜像）
IDC_ROT_Y = -90.0

# IC 锚点（body 中心；rot=0：pin1 左上）——以 x=48 中轴镜像对称
IC_POS = {
    "U1": (36.0, 30.0), "U2": (36.0, 62.0), "U3": (44.0, 67.0),
    "U4": (60.0, 30.0), "U5": (60.0, 62.0), "U6": (52.0, 67.0),
}

# 电源区（J5 右侧顶角：VIN_J5 引脚旁）
RCT_POS = (77.0, 6.5)         # 电流断点
JP1_POS = (84.0, 6.5)         # EXT 互斥跳线
EXT_POS = (84.0, 13.5)        # 外部电源焊盘
C7_POS = (77.0, 10.5)         # 10μF 总旁路

MH_POS = [(4.0, 4.0), (BOARD_W - 4.0, 4.0), (4.0, BOARD_H - 4.0),
          (BOARD_W - 4.0, BOARD_H - 4.0)]

# ---------------------------------------------------------------------------
# 旋转换算：KiCad footprint (at x y rot)，rot 为 CCW 角（y 向下画布）
#   绝对 = origin + [[cos, sin], [-sin, cos]] · 局部
# ---------------------------------------------------------------------------
import math
def rot_pad(local: tuple[float, float], origin: tuple[float, float],
            deg: float) -> tuple[float, float]:
    a = math.radians(deg)
    lx, ly = local
    c, s = math.cos(a), math.sin(a)
    return (origin[0] + lx * c + ly * s, origin[1] - lx * s + ly * c)

def idc_pin_pos(n_pairs: int, pin: int, origin: tuple[float, float],
                deg: float) -> tuple[float, float]:
    return rot_pad(pads_idc(n_pairs)[pin], origin, deg)
