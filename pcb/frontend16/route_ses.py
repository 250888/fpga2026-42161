"""Freerouting SES 会话文件 → xunji_fe16.kicad_pcb 走线回填。

管线：gen_frontend16（无走线 pcb）→ gen_dsn → freerouting → SES
     → 本脚本解析 wire/via → gen.build_pcb(segs, vias) 重写 pcb。

单位：SES (resolution um 10) → 坐标为数据库单位（0.1 μm），
     回填 ÷10000 → mm；SES/DSN y 向上，KiCad y 向下 → y = BOARD_H - y。
"""
from __future__ import annotations

import sys
from pathlib import Path

from fe16_design import BOARD_H
from fe16_router import _kids, _kid, _parse
from gen_frontend16 import PCB_OUT, build_pcb

SESES = Path(__file__).with_name("xunji_fe16.ses")
DBU_PER_MM = 10000.0  # resolution um 10：1 mm = 1000 μm × 10 dbu


def _xy(x, y) -> tuple[float, float]:
    return float(x) / DBU_PER_MM, BOARD_H - float(y) / DBU_PER_MM


def parse_ses(ses_path: Path) -> tuple[list[dict], list[dict]]:
    root = _parse(ses_path.read_text(encoding="utf-8"))
    if root[0] != "session":
        raise ValueError(f"不是 SES 文件: {root[0]}")
    segs: list[dict] = []
    vias: list[dict] = []
    # net 名集合（回填时对齐 PCB 网表）
    pcb_nets = set()
    for nd in _kids(_parse(PCB_OUT.read_text(encoding="utf-8")), "net"):
        if len(nd) >= 3 and str(nd[1]).isdigit():
            pcb_nets.add(str(nd[2]))

    routes = _kids(root, "routes")
    if not routes:
        raise ValueError("SES 缺少 routes 段")
    # 标准为 network_out；兼容 network
    nouts = _kids(routes[0], "network_out") or _kids(routes[0], "network")

    for nw in nouts:
        for net in _kids(nw, "net"):
            name = str(net[1])
            if name not in pcb_nets:
                raise ValueError(f"SES net 不在 PCB 网表: {name!r}")
            _collect(name, net, segs, vias)
        _collect(str(nw[1]), nw, segs, vias) if len(nw) > 1 and isinstance(nw[1], str) and not _kids(nw, "net") else None
    if not segs:
        raise ValueError("SES 未解析出任何走线（结构不符）")
    return segs, vias


def _collect(name: str, node, segs: list[dict], vias: list[dict]) -> None:
    for w in _kids(node, "wire"):
        path = _kid(w, "path")
        if not path or len(path) < 5:
            continue
        layer = {"top": "F.Cu", "bottom": "B.Cu",
                 "front": "F.Cu", "back": "B.Cu"}.get(str(path[1]), str(path[1]))
        width = float(path[2]) / DBU_PER_MM
        coords = list(path[3:])
        pts = [_xy(coords[i], coords[i + 1])
               for i in range(0, len(coords) - 1, 2)]
        for k in range(len(pts) - 1):
            if pts[k] != pts[k + 1]:
                segs.append({"a": pts[k], "b": pts[k + 1], "w": width,
                             "layer": layer, "net": name,
                             "uuid": f"{name}:s{len(segs)}"})
    for v in _kids(node, "via"):
        # (via "NAME" x y) 裸坐标，或 (via NAME (at x y))
        at = _kid(v, "at")
        if at and len(at) >= 3:
            vias.append({"p": _xy(at[1], at[2]), "net": name,
                         "uuid": f"{name}:v{len(vias)}"})
        elif len(v) >= 4:
            try:
                vias.append({"p": _xy(v[2], v[3]), "net": name,
                             "uuid": f"{name}:v{len(vias)}"})
            except (TypeError, ValueError):
                continue


def main() -> None:
    ses = Path(sys.argv[1]) if len(sys.argv) > 1 else SESES
    segs, vias = parse_ses(ses)
    # Freerouting 在拥塞走廊会自行 neck-down（SES 实测 0.1874/0.15/0.125），
    # 低于 0.25 工艺线宽 → 回填时统一抬回 0.25，净距是否被挤爆由 DRC 复验
    necked = sum(1 for s in segs if s["w"] < 0.25)
    for s in segs:
        s["w"] = 0.25
    PCB_OUT.write_text(build_pcb(segs, vias), encoding="utf-8")
    layers = {s["layer"] for s in segs}
    nets = {s["net"] for s in segs} | {v["net"] for v in vias}
    print(f"SES -> PCB: {len(segs)} segments ({sorted(layers)}), "
          f"{len(vias)} vias, {len(nets)} nets, widened {necked} necked paths")


if __name__ == "__main__":
    main()
