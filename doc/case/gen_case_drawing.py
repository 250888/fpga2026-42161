"""从 build_case 的真实参数生成带尺寸的俯视开孔图（SVG），用于核对孔位。"""
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("bc", HERE / "build_case.py")
bc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bc)

OUT = HERE / "case_drawing.svg"
S = 3.6
PAD, TOP = 60, 50
W = bc.CASE_W * S + 2 * PAD
H = bc.CASE_D * S + 2 * TOP


def X(v):
    return PAD + v * S


def Y(v):
    return TOP + v * S


def R(x0, y0, x1, y1, cls, dash=""):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return (f'<rect x="{X(x0):.1f}" y="{Y(y0):.1f}" width="{(x1-x0)*S:.1f}" '
            f'height="{(y1-y0)*S:.1f}" class="{cls}"{d}/>')


def C(x, y, d, cls):
    return (f'<circle cx="{X(x):.1f}" cy="{Y(y):.1f}" r="{d*S/2:.1f}" '
            f'class="{cls}"/>')


def T(x, y, s, cls, anchor="middle", dy=0):
    return (f'<text x="{X(x):.1f}" y="{Y(y)+dy:.1f}" class="{cls}" '
            f'text-anchor="{anchor}">{s}</text>')


def L(x0, y0, x1, y1, cls):
    return (f'<line x1="{X(x0):.1f}" y1="{Y(y0):.1f}" x2="{X(x1):.1f}" '
            f'y2="{Y(y1):.1f}" class="{cls}"/>')


p = [f'<rect width="{W:.0f}" height="{H:.0f}" fill="#0e1319"/>',
     f'<text x="24" y="28" class="h1">FE-16 + EGO1 整机外壳 · 俯视开孔图（mm，1:1 比例）</text>']

# 外壳 / 内腔
p.append(R(0, 0, bc.CASE_W, bc.CASE_D, "outer"))
p.append(R(bc.WALL, bc.WALL, bc.CASE_W - bc.WALL, bc.CASE_D - bc.WALL, "cavity", "5 4"))

# 后侧线缆槽隔墙
p.append(R(bc.WALL, bc.DUCT_D, bc.CASE_W - bc.WALL,
           bc.DUCT_D + bc.DUCT_WALL, "duct"))
# J5 过线口
p.append(R(bc.FE_X + 20, bc.DUCT_D - 1, bc.FE_X + 76,
           bc.DUCT_D + bc.DUCT_WALL + 1, "cut"))

# EGO1 舱位 + 围边
p.append(R(bc.EGO_X, bc.EGO_Y, bc.EGO_X + bc.EGO_W, bc.EGO_Y + bc.EGO_H,
           "ego", "6 4"))
p.append(R(bc.EGO_X - bc.RIM_W, bc.EGO_Y - bc.RIM_W,
           bc.EGO_X + bc.EGO_W + bc.RIM_W, bc.EGO_Y + bc.EGO_H + bc.RIM_W, "rim"))
p.append(T(bc.EGO_X + bc.EGO_W / 2, bc.EGO_Y + bc.EGO_H / 2 - 3,
           f"EGO1 舱位 {bc.EGO_W:.0f}×{bc.EGO_H:.0f}", "lbl"))
p.append(T(bc.EGO_X + bc.EGO_W / 2, bc.EGO_Y + bc.EGO_H / 2 + 6,
           "围边内腔 151×101（单边 0.5 间隙）", "sub"))

# FE-16 板轮廓
p.append(R(bc.FE_X, bc.FE_Y, bc.FE_X + bc.FE_W, bc.FE_Y + bc.FE_H, "fe", "6 4"))
p.append(T(bc.FE_X + bc.FE_W / 2, bc.FE_Y + bc.FE_H / 2 - 14,
           "FE-16 96×96", "lbl"))

# FE-16 四个 M3 柱（外径 7 / 底孔 2.6）
for (mx, my) in bc.FE_MH:
    cx, cy = bc.FE_X + mx, bc.FE_Y + my
    p.append(C(cx, cy, 7.0, "standoff"))
    p.append(C(cx, cy, 2.6, "pilot"))
    p.append(T(cx, cy - 6.6, f"({mx},{my})", "dim"))

# FE-16 接口
j5x0, j5x1 = bc.FE_X + bc.FE_J5[0], bc.FE_X + bc.FE_J5[2]
j5y0, j5y1 = bc.FE_Y + bc.FE_J5[1], bc.FE_Y + bc.FE_J5[3]
p.append(R(j5x0, j5y0, j5x1, j5y1, "conn"))
p.append(T((j5x0 + j5x1) / 2, j5y0 - 1.5, "J5 2×18（朝后）", "sub"))
ja = bc.FE_JA
p.append(R(bc.FE_X + ja[0], bc.FE_Y + ja[1], bc.FE_X + ja[2], bc.FE_Y + ja[3], "conn"))
p.append(T(bc.FE_X + ja[0] - 4, bc.FE_Y + 33, "JA", "sub", "end"))
jb = bc.FE_JB
p.append(R(bc.FE_X + jb[0], bc.FE_Y + jb[1], bc.FE_X + jb[2], bc.FE_Y + jb[3], "conn"))
p.append(T(bc.FE_X + jb[2] + 4, bc.FE_Y + 33, "JB", "sub", "start"))

# FE-16 测试点行（朝前）
for (yy, name) in ((bc.FE_TPA, "TP1-16 (A)"), (bc.FE_TPB, "TP17-32 (B)")):
    y = bc.FE_Y + yy
    p.append(L(bc.FE_X + 18, y, bc.FE_X + 78, y, "tprow"))
    p.append(T(bc.FE_X + bc.FE_W / 2, y - 1.6, name, "sub"))

# 前壁开口 + 绑扎孔 + 过线槽
p.append(R(bc.FRONT_X0, bc.CASE_D - bc.WALL, bc.FRONT_X1, bc.CASE_D, "open"))
p.append(T((bc.FRONT_X0 + bc.FRONT_X1) / 2, bc.CASE_D - bc.WALL + 4.6,
           "前侧贯通开口（线束/模块线/USB）", "openlbl"))
for xx in (60, 150, 240):
    p.append(R(xx, bc.CASE_D - bc.WALL, xx + 4, bc.CASE_D, "tie"))
    p.append(T(xx + 2, bc.CASE_D + 4.5, "绑扎孔", "dim"))

# 左侧通风
for i in range(4):
    yy = bc.EGO_Y + 20 + i * 22
    if yy + 8 < bc.CASE_D - bc.WALL - 6:
        p.append(R(0, yy, bc.WALL, yy + 8, "vent"))

# 脚垫
for (px, py) in [(12, 12), (bc.CASE_W - 12, 12),
                 (12, bc.CASE_D - 12), (bc.CASE_W - 12, bc.CASE_D - 12)]:
    p.append(C(px, py, 8.0, "foot"))

# 尺寸线
p.append(L(0, bc.CASE_D + 12, bc.CASE_W, bc.CASE_D + 12, "dimline"))
p.append(T(bc.CASE_W / 2, bc.CASE_D + 16, f"总宽 {bc.CASE_W:.0f}", "dim"))
p.append(L(bc.CASE_W + 12, 0, bc.CASE_W + 12, bc.CASE_D, "dimline"))
p.append(T(bc.CASE_W + 17, bc.CASE_D / 2, f"总深 {bc.CASE_D:.0f}", "dim"))
# FE 柱距
sx0, sx1 = bc.FE_X + 4, bc.FE_X + 92
sy0, sy1 = bc.FE_Y + 4, bc.FE_Y + 92
p.append(L(sx0, bc.CASE_D - 20, sx1, bc.CASE_D - 20, "dimline"))
p.append(T((sx0 + sx1) / 2, bc.CASE_D - 24, "88.0", "dim"))
p.append(L(bc.CASE_W - 6, sy0, bc.CASE_W - 6, sy1, "dimline"))
p.append(T(bc.CASE_W - 11, (sy0 + sy1) / 2, "88.0", "dim", "end"))

# 图例
lg = [("outer", "外壳外框"), ("cavity", "内腔"), ("standoff/pilot", "M3 柱 / 底孔 2.6"),
      ("open", "开口"), ("tie", "绑扎孔"), ("vent", "通风")]
for i, (c, t) in enumerate(lg):
    y = TOP + bc.CASE_D * S + 34 + i * 16
    p.append(f'<rect x="{PAD}" y="{y}" width="14" height="10" class="{c}"/>')
    p.append(f'<text x="{PAD+20}" y="{y+9}" class="lg">{t}</text>')

H = TOP + bc.CASE_D * S + 34 + len(lg) * 16 + 20

svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W:.0f}" height="{H:.0f}"
     viewBox="0 0 {W:.0f} {H:.0f}">
<style>
 .h1 {{ font:600 15px "Segoe UI","Microsoft YaHei",sans-serif; fill:#dbe3ec; }}
 .lbl {{ font:600 13px "Segoe UI","Microsoft YaHei",sans-serif; fill:#e6edf5; }}
 .sub {{ font:11px "Segoe UI","Microsoft YaHei",sans-serif; fill:#8fa3ba; }}
 .dim {{ font:11px Consolas,monospace; fill:#c9a86b; }}
 .lg  {{ font:12px "Segoe UI","Microsoft YaHei",sans-serif; fill:#9fb0c4; text-anchor:start; }}
 .openlbl {{ font:11px "Segoe UI","Microsoft YaHei",sans-serif; fill:#e06c75; }}
 .outer {{ fill:none; stroke:#8695a8; stroke-width:2; }}
 .cavity {{ fill:#121821; stroke:#2a3646; stroke-width:1; }}
 .duct {{ fill:#3a4757; stroke:#8695a8; stroke-width:1; }}
 .cut, .open {{ fill:#0b0f14; stroke:#e06c75; stroke-width:1.6; stroke-dasharray:6 3; }}
 .tie {{ fill:#d9534f; }}
 .vent {{ fill:#0b0f14; stroke:#55627a; stroke-width:1; }}
 .ego {{ fill:#1b2f4d; stroke:#4f8fd0; stroke-width:1.4; }}
 .rim {{ fill:none; stroke:#4f8fd0; stroke-width:2.4; }}
 .fe {{ fill:#1d4d33; stroke:#3fa06a; stroke-width:1.4; }}
 .standoff {{ fill:#4a5566; stroke:#9fb0c4; stroke-width:1.4; }}
 .pilot {{ fill:#0b0f14; }}
 .conn {{ fill:#3a4757; stroke:#8695a8; stroke-width:1; }}
 .tprow {{ stroke:#c98a4b; stroke-width:3; }}
 .foot {{ fill:none; stroke:#55627a; stroke-width:1.2; stroke-dasharray:3 3; }}
 .dimline {{ stroke:#c9a86b; stroke-width:1; }}
</style>
{chr(10).join(p)}
</svg>
'''
OUT.write_text(svg, encoding="utf-8")
print("wrote", OUT, f"({bc.CASE_W:.0f} x {bc.CASE_D:.0f})")
