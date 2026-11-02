"""从 FE-16 设计数据生成 Specctra DSN（Freerouting 输入）。

语法对照 freerouting 仓库 fixtures/Issue107-*_kicad.dsn（KiCad 官方导出）
与 Cadence SPECCTRA Design Language Reference v10。

坐标：KiCad mm（y 向下）→ DSN μm、y 向上（dsn_y = BOARD_H - y）。
(resolution um 10) → 坐标/padstack 数值单位均为 μm。
"""
from __future__ import annotations

from pathlib import Path

from fe16_design import (BOARD_H, BOARD_W, build_netlist, pads_0805,
                         pads_idc, pads_soic14, pads_tht_r)
from gen_frontend16 import placements

DSN_OUT = Path(__file__).with_name("xunji_fe16.dsn")

VIA_NAME = "Via[0-1]_600:300_um"   # 结构声明的过孔（直径600/钻300 μm）


def um(v: float) -> int:
    return round(v * 1000)


def dsn_y(y: float) -> int:
    return round((BOARD_H - y) * 1000)


# 封装类型 → (padstack 名, pin→局部坐标(mm, y 向下))
def _kind_pads(kind: str) -> tuple[str, dict[int, tuple[float, float]]]:
    if kind == "idc18":
        return "PS_IDC14", pads_idc(18)
    if kind == "idc10":
        return "PS_IDC14", pads_idc(10)
    if kind == "r":
        return "PS_RTH", pads_tht_r()      # 电阻：直插立式（2026-10-24）
    if kind == "c":
        return "PS_R0805", pads_0805()     # 电容：保持 0805 贴片
    if kind == "soic":
        return "PS_SOIC14", pads_soic14()
    if kind == "tp":
        return "PS_TP14", {1: (0.0, 0.0)}
    if kind == "hdr":
        return "PS_HDR17", pads_idc(1)
    if kind == "mh":
        return "PS_MH32", {1: (0.0, 0.0)}
    raise ValueError(kind)


def padstacks() -> str:
    # 通孔：F.Cu/B.Cu 双层圆盘（fixture 的 THT pad 即此形，无 hole 字段）
    # SMD：仅 F.Cu 矩形（对角两顶点，相对 padstack 原点）
    # MH：NPTH 无铜环，当 3200 μm 铜盘保守避让
    # pin1 方盘（KiCad IDC/Hdr pin1 = rect，方角比圆多伸 √2-1 倍半径）：
    # 若按圆建模，Freerouting 的 0.27 净距会贴圆走，方角插进走线造成短路
    # （实测 ACTRL2×J5 pin1 shorting_items）→ pin1 单独用方 padstack
    return f"""  (padstack PS_IDC14
    (shape (circle F.Cu 1400))
    (shape (circle B.Cu 1400))
    (attach off))
  (padstack PS_IDC14_P1
    (shape (rect F.Cu -700 -700 700 700))
    (shape (rect B.Cu -700 -700 700 700))
    (attach off))
  (padstack PS_TP14
    (shape (circle F.Cu 1400))
    (shape (circle B.Cu 1400))
    (attach off))
  (padstack PS_HDR17
    (shape (circle F.Cu 1700))
    (shape (circle B.Cu 1700))
    (attach off))
  (padstack PS_HDR17_P1
    (shape (rect F.Cu -850 -850 850 850))
    (shape (rect B.Cu -850 -850 850 850))
    (attach off))
  (padstack PS_MH32
    (shape (circle F.Cu 3200))
    (shape (circle B.Cu 3200))
    (attach off))
  (padstack PS_R0805
    (shape (rect F.Cu -550 -700 550 700))
    (attach off))
  (padstack PS_RTH
    (shape (circle F.Cu 1600))
    (shape (circle B.Cu 1600))
    (attach off))
  (padstack PS_SOIC14
    (shape (rect F.Cu -750 -300 750 300))
    (attach off))
  (padstack "{VIA_NAME}"
    (shape (circle F.Cu 600))
    (shape (circle B.Cu 600))
    (attach off))"""


def build_dsn() -> str:
    P = placements()
    netlist = build_netlist()

    # library：每元件一个 image（Specctra 关联法），pin 局部 y 翻转向上
    images = []
    for ref in sorted(P):
        kind, _x, _y, _rot = P[ref]
        ps_name, pads = _kind_pads(kind)
        pins = []
        for pin in sorted(pads):
            lx, ly = pads[pin]
            # pin1 方盘映射到方 padstack（与 KiCad fp_idc/fp_hdr2 的 rect 一致）
            ps = ps_name
            if pin == 1 and ps_name in ("PS_IDC14", "PS_HDR17"):
                ps = ps_name + "_P1"
            pins.append(f"    (pin {ps} {pin} {um(lx)} {round(-ly * 1000)})")
        images.append(f"  (image {ref}\n" + "\n".join(pins) + ")")

    # placement：(place REF X Y front ROTATION)，rotation 与 KiCad 同号
    places = []
    for ref in sorted(P):
        kind, x, y, rot = P[ref]
        r = round(rot) % 360
        places.append(f"  (component {ref}\n"
                      f"    (place {ref} {um(x)} {dsn_y(y)} front {r}))")

    # network：pins 用 REF-PIN 连字符连接
    nets = []
    for name in sorted(netlist):
        conns = [f"{ref}-{pin}" for ref, pin in sorted(netlist[name])]
        nets.append(f"    (net {name}\n      (pins {' '.join(conns)}))")

    # class：0.25mm 线宽 netclass 声明。
    # 间距取 0.27mm（> KiCad 0.2mm 要求 + 0.0626mm neck-down 补偿余量）：
    # Freerouting 允许 neck-down 收窄走线，但按 0.27 规划的边距在回填强制
    # 0.25mm 后仍 ≥0.2074mm；若按 0.2001 规划，收窄段抬宽后会击穿 0.2mm
    # （实测 10 条 clearance 违规）。
    cls = (f"    (class main {' '.join(sorted(netlist))}\n"
           f"      (rule (width 250) (clearance 270)))")

    # 板框 path：宽 0 + 闭合矩形 (0,H) (W,H) (W,0) (0,0) (0,H)（μm，y 向上）
    bw, bh = um(BOARD_W), um(BOARD_H)
    return f"""(pcb fe16
  (parser
    (string_quote ")
    (space_in_quoted_tokens on)
    (host_cad "gen_dsn")
    (host_version "1.0"))
  (resolution um 10)
  (unit um)
  (structure
    (layer F.Cu (type signal))
    (layer B.Cu (type signal))
    (boundary (path pcb 0 0 {bh} {bw} {bh} {bw} 0 0 0 0 {bh}))
    (via "{VIA_NAME}")
    (rule
      (width 250)
      (clearance 270)))
  (placement
{chr(10).join(places)})
  (library
{padstacks()}
{chr(10).join(images)})
  (network
{chr(10).join(nets)}
{cls})
)
"""


def main() -> None:
    DSN_OUT.write_text(build_dsn(), encoding="utf-8")
    print(f"WROTE {DSN_OUT.name} ({DSN_OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
