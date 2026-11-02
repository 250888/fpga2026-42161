"""瞬迹 · 整机外壳（CadQuery 参数化）

设计依据（对外部动态故障模块的三个要求）：
  1. FE-16 朝向固定为「J5 朝后 / JA 左 / JB 右 / A·B 测试点朝前」
     - J5 排线走后侧 22mm 线缆槽 → 通到 EGO1
     - JA、JB 的线从板两侧绕到**前方**，全部从**前侧大开口**出去
     - A/B 测试点（TP1-16 / TP17-32）在板的前缘 → 动态模块感测线
       和示波器探头都从**上方（上盖窗口）或前侧**接入
  2. 洞洞板（CD4066 动态故障模块）**放壳外**，只留走线通道
     - 前侧开口 26mm 高、贯通左右，供：EGO1 控制信号出线
       + 模块感测线回板 + DUT 线束
  3. JA 左侧 16mm 通道、JB 右侧 15mm 通道，让线束在壳内拐到前方

运行：  E:\\d\\cad\\venv\\Scripts\\python.exe doc\\case\\build_case.py
输出：  doc/case/out/*.step, *.stl
"""

from pathlib import Path
import cadquery as cq

OUT = Path(__file__).resolve().parent / "out"
OUT.mkdir(parents=True, exist_ok=True)

# ============================== 参数 ==============================
# ---- 电路板 ----
EGO_W, EGO_H = 150.0, 100.0     # ← EGO1 板框（待实测；照片标定估 155×115）
FE_W, FE_H = 96.0, 96.0         # FE-16（实测）
FE_T = 1.6
FE_MH = [(4, 4), (92, 4), (4, 92), (92, 92)]   # FE-16 安装孔（板坐标）
FE_JA = (7.73, 22.0, 10.27, 44.86)             # JA 占位（板坐标）
FE_JB = (83.19, 22.0, 85.73, 44.86)            # JB 占位
FE_J5 = (26.4, 6.5, 69.58, 9.04)               # J5 占位
FE_TPA = 77.0                                  # TP1-16 行 y
FE_TPB = 83.0                                  # TP17-32 行 y

# ---- 外壳 ----
WALL = 3.0
FLOOR = 3.0
CASE_H = 42.0
BOARD_Z = 7.0                   # 板底高度（留 4mm 给背面焊点；柱高 4mm，M3×6 吃牙 3.7mm）
RIM_CLR = 0.5                   # EGO1 围边单边间隙（板 150×100 → 内腔 151×101）
DUCT_D = 22.0                   # 后侧线缆槽深
DUCT_WALL = 2.0
EDGE_L = 8.0                    # EGO1 左边距
BAY_GAP = 16.0                  # EGO1↔FE 间隙 = JA 走线通道
EDGE_R = 18.0                   # FE 右边距 = JB 转向前空间
FRONT_AREA = 44.0               # FE 前方 DUT 线束回路区
RIM_W, RIM_H = 2.5, 5.0
LC = 0.35                       # 上盖凸缘间隙

# ---- 上盖 ----
LID_T = 3.0
LID_BORDER = 10.0
ACRYLIC_T = 2.0
LID_LIP = 2.0

# ---- 推导 ----
BAY_D = max(EGO_H, FE_H + FRONT_AREA)
CASE_W = EDGE_L + EGO_W + BAY_GAP + FE_W + EDGE_R
CASE_D = DUCT_D + DUCT_WALL + 8.0 + BAY_D + 8.0

EGO_X, EGO_Y = EDGE_L, DUCT_D + DUCT_WALL + 8.0
FE_X, FE_Y = EDGE_L + EGO_W + BAY_GAP, EGO_Y

# 前侧/侧面走线开口（z 从板面上方 11mm 起，线在板上方过、再垂落到 TP）
OPEN_Z0, OPEN_Z1 = FLOOR + 8.0, FLOOR + 34.0
FRONT_X0, FRONT_X1 = EDGE_L + 26.0, CASE_W - 20.0


def box(x0, y0, z0, x1, y1, z1):
    return (cq.Workplane("XY").box(x1 - x0, y1 - y0, z1 - z0)
            .translate(((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2)))


def cyl(x, y, z0, z1, d):
    return cq.Workplane("XY").circle(d / 2).extrude(z1 - z0).translate((x, y, z0))


# ============================== 底壳 ==============================
def make_base():
    outer = box(0, 0, 0, CASE_W, CASE_D, CASE_H)
    cavity = box(WALL, WALL, FLOOR, CASE_W - WALL, CASE_D - WALL, CASE_H + 1)
    b = outer.cut(cavity)

    # ---- 后侧线缆槽（隔墙 + J5 过线口）----
    duct_face = DUCT_D + DUCT_WALL
    b = b.union(box(WALL, DUCT_D, FLOOR, CASE_W - WALL, duct_face, FLOOR + 28))
    b = b.cut(box(FE_X + 20, DUCT_D - 1, FLOOR + 6,
                  FE_X + 76, duct_face + 1, FLOOR + 28))   # FE J5 出线口

    # ---- EGO1 定位围边（不依赖安装孔，留 0.5mm 单边间隙）----
    x0, y0 = EGO_X - RIM_W, EGO_Y - RIM_W
    x1, y1 = EGO_X + EGO_W + RIM_W, EGO_Y + EGO_H + RIM_W
    rim = box(x0, y0, FLOOR, x1, y1, FLOOR + RIM_H)
    rim = rim.cut(box(EGO_X - RIM_CLR, EGO_Y - RIM_CLR, FLOOR - 1,
                      EGO_X + EGO_W + RIM_CLR, EGO_Y + EGO_H + RIM_CLR,
                      FLOOR + RIM_H + 1))
    b = b.union(rim)

    # ---- FE-16 四柱 ----
    for (mx, my) in FE_MH:
        cx, cy = FE_X + mx, FE_Y + my
        b = b.union(cyl(cx, cy, FLOOR, BOARD_Z, 7.0))
        # 底孔只在柱体内，绝不打穿外壳底面
        b = b.cut(cyl(cx, cy, FLOOR + 0.5, BOARD_Z + 0.2, 2.6))

    # ---- 前侧贯通大开口（DUT 线束 / 模块感测线 / EGO1 控制线）----
    b = b.cut(box(FRONT_X0, CASE_D - WALL - 1, OPEN_Z0,
                  FRONT_X1, CASE_D - WALL + 1, OPEN_Z1))

    # ---- 右侧 JB 拐弯防挤（不开口，靠 15mm 内部通道转向）----
    # 通风：左侧、前侧
    for i in range(4):
        yy = EGO_Y + 20 + i * 22
        if yy + 8 < CASE_D - WALL - 6:
            b = b.cut(box(-1, yy, FLOOR + 6, WALL + 1, yy + 8, FLOOR + 20))
    for i in range(2):
        xx = 30 + i * 70
        b = b.cut(box(xx, CASE_D - WALL - 1, FLOOR + 4,
                      xx + 40, CASE_D - WALL + 1, FLOOR + 6))  # 扎带过线槽

    # ---- 前壁外侧绑扎孔：洞洞板（CD4066 + Arduino Nano）贴壁固定 ----
    # 洞洞板在壳外，靠扎带/魔术贴挂在前壁；这些孔穿过 z 4.5..10 的实体壁带
    for xx in (60, 150, 240):
        b = b.cut(box(xx, CASE_D - WALL - 1, FLOOR + 1.5,
                      xx + 4.0, CASE_D - WALL + 1, FLOOR + 7.0))

    # ---- 底面脚垫槽 ----
    for (px, py) in [(12, 12), (CASE_W - 12, 12),
                     (12, CASE_D - 12), (CASE_W - 12, CASE_D - 12)]:
        b = b.cut(cyl(px, py, -1, 1.2, 8.0))
    return b


# ============================== 上盖 ==============================
def make_lid():
    plate = box(0, 0, 0, CASE_W, CASE_D, LID_T)
    lip = box(WALL + LC, WALL + LC, -LID_LIP,
              CASE_W - WALL - LC, CASE_D - WALL - LC, 0.01)
    lid = plate.union(lip)
    # 亚克力沉台：从内侧挖 ACRYLIC_T+0.2 深，范围 = LID_BORDER → 形成承边
    lid = lid.cut(box(LID_BORDER, LID_BORDER, -ACRYLIC_T - 0.2,
                      CASE_W - LID_BORDER, CASE_D - LID_BORDER, 0.05))
    # 观察窗：比沉台小 4mm → 内侧留 4mm 承边托住亚克力，外侧挡住不掉
    lid = lid.cut(box(LID_BORDER + 4, LID_BORDER + 4, -LID_LIP - 1,
                      CASE_W - LID_BORDER - 4, CASE_D - LID_BORDER - 4,
                      LID_T + 1))
    return lid


if __name__ == "__main__":
    base, lid = make_base(), make_lid()
    for name, shp in (("base", base), ("lid", lid)):
        cq.exporters.export(shp, str(OUT / f"xunji_case_{name}.step"))
        cq.exporters.export(shp, str(OUT / f"xunji_case_{name}.stl"),
                            tolerance=0.15, angularTolerance=0.2)
    asm = base.union(lid.translate((0, 0, CASE_H)))
    cq.exporters.export(asm, str(OUT / "xunji_case_asm.step"))
    cq.exporters.export(asm, str(OUT / "xunji_case_asm.stl"),
                        tolerance=0.15, angularTolerance=0.2)

    print(f"外框 {CASE_W:.1f} × {CASE_D:.1f} × {CASE_H + LID_T:.1f} mm")
    print(f"EGO1 舱位 x{EGO_X}..{EGO_X+EGO_W}  y{EGO_Y}..{EGO_Y+EGO_H}")
    print(f"FE-16 舱位 x{FE_X}..{FE_X+FE_W}  y{FE_Y}..{FE_Y+FE_H}")
    print(f"前侧开口 x{FRONT_X0}..{FRONT_X1}  z{OPEN_Z0}..{OPEN_Z1}")
    print(f"JA 走线通道 {BAY_GAP:.0f}mm   JB 转向空间 {EDGE_R-3:.0f}mm")
