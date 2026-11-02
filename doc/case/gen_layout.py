"""瞬迹整机外壳 · 布局概念图（1:1 比例 SVG）。

EGO1 板框是**待实测参数**（EGO_W / EGO_H），其余尺寸均为实测/图纸值。
改参数后重跑本脚本即可更新图纸。
"""
from pathlib import Path

OUT = Path(__file__).resolve().parent / "layout_concept.svg"

# ---------------- 参数 ----------------
EGO_W, EGO_H = 150.0, 100.0     # ← EGO1 板框（待实测确认）
FE_W, FE_H = 96.0, 96.0         # FE-16（已确认）
MARGIN = 6.0                    # 板与内壁间隙
WALL = 2.5
GAP_RIBBON = 24.0               # EGO1↔FE-16 之间：2×18 排线走线
HARNESS = 48.0                  # FE-16 前方：DUT 线束回路区

INNER_W = max(EGO_W, FE_W) + 2 * MARGIN
INNER_H = EGO_H + GAP_RIBBON + FE_H + HARNESS + 2 * MARGIN
OUT_W = INNER_W + 2 * WALL
OUT_H = INNER_H + 2 * WALL

S = 2.2
PAD, TOP = 40, 40
W, H = OUT_W * S + 2 * PAD, OUT_H * S + 2 * TOP


def X(v):
    return PAD + v * S


def Y(v):
    return TOP + v * S


egoX = WALL + MARGIN + (INNER_W - 2 * MARGIN - EGO_W) / 2
egoY = WALL + MARGIN
feX = WALL + MARGIN + (INNER_W - 2 * MARGIN - FE_W) / 2
feY = egoY + EGO_H + GAP_RIBBON

p = []
p.append(f'<rect width="{W:.0f}" height="{H:.0f}" fill="#0e1319"/>')
p.append(f'<text x="26" y="27" class="h1">瞬迹 · 整机外壳布局（概念图 · mm）</text>')

# 外壳
p.append(f'<rect x="{X(0):.1f}" y="{Y(0):.1f}" width="{OUT_W*S:.1f}" height="{OUT_H*S:.1f}" class="outer"/>')
p.append(f'<rect x="{X(WALL):.1f}" y="{Y(WALL):.1f}" width="{INNER_W*S:.1f}" height="{INNER_H*S:.1f}" class="cavity"/>')

# EGO1
p.append(f'<rect x="{X(egoX):.1f}" y="{Y(egoY):.1f}" width="{EGO_W*S:.1f}" height="{EGO_H*S:.1f}" class="boardEgo"/>')
cx, cy = X(egoX + EGO_W / 2), Y(egoY + EGO_H / 2)
p.append(f'<text x="{cx:.1f}" y="{cy-4:.1f}" class="lbl">EGO1（待实测）</text>')
p.append(f'<text x="{cx:.1f}" y="{cy+10:.1f}" class="sub">Artix-7 XC7A35T · Type-C 供电 · UART</text>')

# FE-16
p.append(f'<rect x="{X(feX):.1f}" y="{Y(feY):.1f}" width="{FE_W*S:.1f}" height="{FE_H*S:.1f}" class="boardFe"/>')
cx2, cy2 = X(feX + FE_W / 2), Y(feY + FE_H / 2)
p.append(f'<text x="{cx2:.1f}" y="{cy2-4:.1f}" class="lbl">FE-16  96 × 96</text>')
p.append(f'<text x="{cx2:.1f}" y="{cy2+10:.1f}" class="sub">16 通道前端 · A/B/回读 三点观测</text>')

# FE-16 接口
j5x0, j5x1 = feX + 26.4, feX + 69.58
p.append(f'<rect x="{X(j5x0):.1f}" y="{Y(feY-2.4):.1f}" width="{(j5x1-j5x0)*S:.1f}" height="{2.4*S:.1f}" class="conn"/>')
p.append(f'<text x="{X((j5x0+j5x1)/2):.1f}" y="{Y(feY-4.5):.1f}" class="sub">J5 2×18</text>')
p.append(f'<rect x="{X(feX-2.4):.1f}" y="{Y(feY+22):.1f}" width="{2.4*S:.1f}" height="{22.86*S:.1f}" class="conn"/>')
p.append(f'<rect x="{X(feX+FE_W):.1f}" y="{Y(feY+22):.1f}" width="{2.4*S:.1f}" height="{22.86*S:.1f}" class="conn"/>')
p.append(f'<text x="{X(feX-5):.1f}" y="{Y(feY+34):.1f}" class="sub" text-anchor="end">JA</text>')
p.append(f'<text x="{X(feX+FE_W+5):.1f}" y="{Y(feY+34):.1f}" class="sub" text-anchor="start">JB</text>')

# 2×18 排线
p.append(f'<path d="M {X(j5x0+6):.1f} {Y(feY):.1f} '
         f'C {X(j5x0+6):.1f} {Y(feY-GAP_RIBBON*0.5):.1f}, '
         f'{X(egoX+EGO_W*0.42):.1f} {Y(egoY+EGO_H+3):.1f}, '
         f'{X(egoX+EGO_W*0.42):.1f} {Y(egoY+EGO_H):.1f}" class="ribbon"/>')
p.append(f'<text x="{X(egoX+EGO_W*0.70):.1f}" y="{Y(egoY+EGO_H+GAP_RIBBON*0.55):.1f}" '
         f'class="sub">2×18 排线 · EGO1 J5 → FE-16 J5</text>')

# DUT 线束回路
hy = feY + FE_H + HARNESS * 0.55
p.append(f'<path d="M {X(feX-1):.1f} {Y(feY+33):.1f} '
         f'C {X(feX-6):.1f} {Y(hy+14):.1f}, {X(feX+14):.1f} {Y(hy):.1f}, {X(feX+FE_W/2):.1f} {Y(hy):.1f} '
         f'S {X(feX+FE_W-14):.1f} {Y(hy+14):.1f}, {X(feX+FE_W+1):.1f} {Y(feY+33):.1f}" class="dut"/>')
p.append(f'<text x="{X(feX+FE_W/2):.1f}" y="{Y(hy+7):.1f}" class="sub">DUT 线束回路（1:1 / 拔线 / 交叉 / 短接）</text>')

# 前侧开口
p.append(f'<rect x="{X(WALL):.1f}" y="{Y(OUT_H-WALL):.1f}" width="{INNER_W*S:.1f}" height="{WALL*S:.1f}" class="cut"/>')
p.append(f'<text x="{X(OUT_W/2):.1f}" y="{Y(OUT_H+4):.1f}" class="dim">前侧开口：DUT 线束引出 + 拍摄取景</text>')

# 尺寸
p.append(f'<line x1="{X(0):.1f}" y1="{Y(OUT_H)+8:.1f}" x2="{X(OUT_W):.1f}" y2="{Y(OUT_H)+8:.1f}" class="dimline"/>')
p.append(f'<text x="{X(OUT_W/2):.1f}" y="{Y(OUT_H)+14:.1f}" class="dim">外框宽 {OUT_W:.1f}</text>')
p.append(f'<line x1="{X(OUT_W)+8:.1f}" y1="{Y(0):.1f}" x2="{X(OUT_W)+8:.1f}" y2="{Y(OUT_H):.1f}" class="dimline"/>')
p.append(f'<text x="{X(OUT_W)+15:.1f}" y="{Y(OUT_H/2):.1f}" class="dim">外框深 {OUT_H:.1f}</text>')

svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W:.0f}" height="{H:.0f}" viewBox="0 0 {W:.0f} {H:.0f}">
<style>
 .h1 {{ font:600 15px "Segoe UI","Microsoft YaHei",sans-serif; fill:#dbe3ec; }}
 .lbl {{ font:600 13px "Segoe UI","Microsoft YaHei",sans-serif; fill:#e6edf5; text-anchor:middle; }}
 .sub {{ font:11px "Segoe UI","Microsoft YaHei",sans-serif; fill:#8fa3ba; text-anchor:middle; }}
 .dim {{ font:11px Consolas,monospace; fill:#9fb0c4; text-anchor:middle; }}
 .outer {{ fill:none; stroke:#6b7a8f; stroke-width:2; }}
 .cavity {{ fill:#121821; stroke:#2a3646; stroke-width:1; stroke-dasharray:5 3; }}
 .boardEgo {{ fill:#1b2f4d; stroke:#4f8fd0; stroke-width:1.6; stroke-dasharray:7 4; }}
 .boardFe {{ fill:#1d4d33; stroke:#3fa06a; stroke-width:1.6; }}
 .conn {{ fill:#3a4757; stroke:#8695a8; stroke-width:1; }}
 .ribbon {{ fill:none; stroke:#c98a4b; stroke-width:7; opacity:.75; }}
 .dut {{ fill:none; stroke:#d9534f; stroke-width:5; opacity:.8; stroke-dasharray:10 5; }}
 .cut {{ fill:#0b0f14; stroke:#e06c75; stroke-width:1.4; stroke-dasharray:6 3; }}
 .dimline {{ stroke:#55627a; stroke-width:1; }}
</style>
{chr(10).join(p)}
</svg>
'''
OUT.write_text(svg, encoding="utf-8")
print(f"wrote {OUT}")
print(f"内腔 {INNER_W:.1f} × {INNER_H:.1f}   外框 {OUT_W:.1f} × {OUT_H:.1f}")
