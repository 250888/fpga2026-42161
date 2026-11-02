"""FE-16 A* 栅格布线器。

0.5mm 栅格、双层（F.Cu/B.Cu）、via 自动跨层；线宽统一 0.25mm
（全板最大电流 <50mA，0.25mm/1oz 载流裕量 >10 倍，V1.9 未强制线宽）。

流程：读入已放置元件的 .kicad_pcb → pad 膨胀为障碍 → 按 net 顺序
Prim 逐点 A* → 输出 segments/vias。
"""
from __future__ import annotations

import heapq
import json
import math
import re
from pathlib import Path

PITCH = 0.5
OX = OY = 0.25                 # 格心 = 0.25 + 0.5k
CLEAR = 0.2                    # 铜间距（KiCad 板级最小值）
TRACK_W = 0.25
VIA_COST = 10.0                # 换层惩罚（格）——降罚鼓励跨层分流
BEND_COST = 1.6                # 拐弯惩罚（格）
BOARD_W, BOARD_H = 96.0, 96.0
NX = int((BOARD_W - 0.5) / PITCH) + 1    # 格心 0.25..95.75 → 192
NY = int((BOARD_H - 0.5) / PITCH) + 1    # 192

_TOKEN = re.compile(r'\(|\)|"(?:[^"\\]|\\.)*"|[^\s()]+')


def _parse(text: str):
    stack: list[list] = [[]]
    for tok in _TOKEN.findall(text):
        if tok == "(":
            stack.append([])
        elif tok == ")":
            d = stack.pop()
            stack[-1].append(d)
        elif tok.startswith('"'):
            stack[-1].append(json.loads(tok))
        else:
            stack[-1].append(tok)
    return stack[0][0]


def _kids(node, key):
    return [x for x in node if isinstance(x, list) and x and x[0] == key]


def _kid(node, key):
    k = _kids(node, key)
    return k[0] if k else None


def gx(x: float) -> int:
    return round((x - OX) / PITCH)


def gy(y: float) -> int:
    return round((y - OY) / PITCH)


def xy(ix: int, iy: int) -> tuple[float, float]:
    return (OX + ix * PITCH, OY + iy * PITCH)


def _rot(lx, ly, fx, fy, deg):
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    return (fx + lx * c + ly * s, fy - lx * s + ly * c)


class Board:
    def __init__(self):
        # occ[layer][ix][iy] = None | "OBS" | net 名
        self.occ: list[list[list[str | None]]] = [
            [[None] * NY for _ in range(NX)] for _ in range(2)]
        self.pads: dict[str, list[dict]] = {}    # net → [pad dict]
        self.net_pads: dict[str, list] = {}

    def mark(self, ix: int, iy: int, layer: int, val: str | None) -> None:
        if not (0 <= ix < NX and 0 <= iy < NY):
            return
        cur = self.occ[layer][ix][iy]
        if cur is None:
            self.occ[layer][ix][iy] = val if val else "OBS"
        elif val is not None and cur != val and cur != "OBS":
            self.occ[layer][ix][iy] = "OBS"

    def mark_pad(self, cx: float, cy: float, w: float, h: float,
                 layers: list[int], net: str | None, inflate: float) -> None:
        val = net if net else "OBS"
        x0, x1 = gx(cx - w / 2 - inflate), gx(cx + w / 2 + inflate)
        y0, y1 = gy(cy - h / 2 - inflate), gy(cy + h / 2 + inflate)
        for ix in range(x0, x1 + 1):
            for iy in range(y0, y1 + 1):
                for L in layers:
                    self.mark(ix, iy, L, val)


def load_board(pcb_path: Path) -> tuple[Board, list[tuple[str, str]]]:
    root = _parse(pcb_path.read_text(encoding="utf-8"))
    b = Board()
    infl = TRACK_W / 2 + CLEAR
    order: list[tuple[str, str]] = []          # (net, 语义) 留作扩展
    for fp in _kids(root, "footprint"):
        at = _kid(fp, "at")
        fx, fy = float(at[1]), float(at[2])
        frot = float(at[3]) if len(at) > 3 else 0.0
        for pad in _kids(fp, "pad"):
            kind = pad[2]                      # smd / thru_hole / np_thru_hole
            pat = _kid(pad, "at")
            lx, ly = float(pat[1]), float(pat[2])
            size = _kid(pad, "size")
            w, h = float(size[1]), float(size[2])
            netn = _kid(pad, "net")
            net = netn[2] if netn else None
            cx, cy = _rot(lx, ly, fx, fy, frot)
            if frot % 180 == 90:               # 旋转 90° 时矩形对调
                w, h = h, w
            layers = [0, 1] if kind in ("thru_hole", "np_thru_hole") else [0]
            b.mark_pad(cx, cy, w, h, layers, net, infl)
            if net:
                b.pads.setdefault(net, []).append(
                    {"c": (cx, cy), "wh": (w, h), "layers": layers})
    return b, order


# ---------------------------------------------------------------------------
# A*
# ---------------------------------------------------------------------------
DIRS = [(1, 0), (-1, 0), (0, 1), (0, -1)]


def _h(ix: int, iy: int, goal: tuple[int, int]) -> int:
    return abs(ix - goal[0]) + abs(iy - goal[1])


def astar(b: Board, starts: set[tuple[int, int, int]],
          goal: tuple[int, int, int], net: str) -> list[tuple[int, int, int]] | None:
    """4邻 + via 的 A*，状态含方向（拐弯惩罚）。返回格路径。"""
    gix, giy, gL = goal
    heap: list[tuple[float, float, int, int, int, int]] = []
    best: dict[tuple[int, int, int, int], float] = {}
    parent: dict[tuple[int, int, int, int], tuple[int, int, int, int]] = {}
    for sx, sy, sL in starts:
        for d in range(5):
            key = (sx, sy, sL, d)
            best[key] = 0.0
            heapq.heappush(heap, (_h(sx, sy, (gix, giy)) + VIA_COST, 0.0,
                                  sx, sy, sL, d))
    found_key = None
    while heap:
        f, g, ix, iy, L, d = heapq.heappop(heap)
        key = (ix, iy, L, d)
        if g > best.get(key, 1e18):
            continue
        if (ix, iy, L) == goal:
            found_key = key
            break
        # 邻域
        for nd, (dx, dy) in enumerate(DIRS):
            nx, ny = ix + dx, iy + dy
            if not (1 <= nx < NX - 1 and 1 <= ny < NY - 1):
                continue
            occ = b.occ[L][nx][ny]
            if occ is not None and occ != net:
                continue
            ng = g + 1.0 + (0.0 if d in (nd, 4) else BEND_COST)
            nkey = (nx, ny, L, nd)
            if ng < best.get(nkey, 1e18):
                best[nkey] = ng
                parent[nkey] = key
                heapq.heappush(heap, (ng + _h(nx, ny, (gix, giy)), ng,
                                      nx, ny, L, nd))
        # 换层
        nL = L ^ 1
        ok = True
        for ddx in (-1, 0, 1):
            for ddy in (-1, 0, 1):
                o = b.occ[nL][ix + ddx][iy + ddy]
                if o is not None and o != net:
                    ok = False
                    break
            if not ok:
                break
        if ok:
            ng = g + VIA_COST
            nkey = (ix, iy, nL, d)
            if ng < best.get(nkey, 1e18):
                best[nkey] = ng
                parent[nkey] = key
                heapq.heappush(heap, (ng + _h(ix, iy, (gix, giy)), ng,
                                      ix, iy, nL, d))
    if found_key is None:
        return None
    path = []
    k = found_key
    while k in parent:
        path.append((k[0], k[1], k[2]))
        k = parent[k]
    path.append((k[0], k[1], k[2]))
    path.reverse()
    return path


# ---------------------------------------------------------------------------
# net 布线（Prim 逐点连接）
# ---------------------------------------------------------------------------
def route_net(b: Board, net: str, seq: list[str],
              segs: list[dict], vias: list[dict]) -> str | None:
    pads = b.pads[net]
    if len(pads) < 2:
        return None

    def pad_cells(p):
        cx, cy = p["c"]
        return (gx(cx), gy(cy), p["layers"])

    cells = [pad_cells(p) for p in pads]
    # 增量续布：本 net 已有走线（跨轮保留的半成品/成功段）都算已连通
    connected: set[tuple[int, int, int]] = set()
    for s in segs:
        if s["net"] != net:
            continue
        L = 0 if s["layer"] == "F.Cu" else 1
        x1, y1 = s["a"]
        x2, y2 = s["b"]
        ix1, iy1, ix2, iy2 = gx(x1), gy(y1), gx(x2), gy(y2)
        steps = max(abs(ix2 - ix1), abs(iy2 - iy1), 1)
        for k in range(steps + 1):
            ix = round(ix1 + (ix2 - ix1) * k / steps)
            iy = round(iy1 + (iy2 - iy1) * k / steps)
            connected.add((ix, iy, L))
    for v in vias:
        if v["net"] == net:
            connected.add((gx(v["p"][0]), gy(v["p"][1]), 0))
            connected.add((gx(v["p"][0]), gy(v["p"][1]), 1))

    remaining = [i for i, c in enumerate(cells)
                 if not any((c[0], c[1], L) in connected for L in c[2])]
    if not remaining:
        return None
    if not connected:
        # 全新 net：起点 = 中位数 pad
        cx0 = sorted(c[0] for c in cells)[len(cells) // 2]
        cy0 = sorted(c[1] for c in cells)[len(cells) // 2]
        start_pad = min(range(len(pads)),
                        key=lambda i: abs(cells[i][0] - cx0) + abs(cells[i][1] - cy0))
        for L in cells[start_pad][2]:
            connected.add((cells[start_pad][0], cells[start_pad][1], L))
        remaining = [i for i in remaining if i != start_pad]
    stuck: set[int] = set()
    first_err = None
    while True:
        # 最近可达候选（卡死的 target 跳过，先连通其余 pad 最大化半成品）
        cand = [i for i in remaining if i not in stuck]
        if not cand:
            if remaining:
                ti = remaining[0]
                tx, ty, _tLs = cells[ti]
                return first_err or f"{net}: 无法连接 pad {ti}（格 {tx},{ty}）"
            return None

        def d2t(i):
            ix, iy, _L = cells[i]
            return min(abs(ix - c[0]) + abs(iy - c[1]) for c in connected)
        cand.sort(key=d2t)
        ti = cand[0]
        tx, ty, tLs = cells[ti]
        goal = (tx, ty, tLs[0])
        path = astar(b, connected, goal, net)
        if path is None:
            stuck.add(ti)
            if first_err is None:
                first_err = f"{net}: 无法连接 pad {ti}（格 {tx},{ty}）"
            continue
        remaining.remove(ti)
        # 落盘 + 占格
        for (ix, iy, L) in path:
            b.occ[L][ix][iy] = net
            connected.add((ix, iy, L))
        # path → 精确坐标：首/末格若恰为本 net 的 pad 格则吸附到 pad 中心
        pts: list[tuple[float, float, int]] = [
            (*xy(ix, iy), L) for (ix, iy, L) in path]
        sL = path[0][2]
        for p in pads:
            if ((gx(p["c"][0]), gy(p["c"][1])) == (path[0][0], path[0][1])
                    and sL in p["layers"]):
                pts[0] = (p["c"][0], p["c"][1], sL)
                break
        pts[-1] = (pads[ti]["c"][0], pads[ti]["c"][1], pts[-1][2])
        _emit(pts, net, seq, segs, vias)
    return None


def _emit(pts, net, seq, segs, vias) -> None:
    # 连续同层段合并；层变点出 via
    i = 0
    while i < len(pts) - 1:
        x1, y1, L1 = pts[i]
        x2, y2, L2 = pts[i + 1]
        if L1 != L2:
            vias.append({"p": (x1, y1), "net": net,
                         "uuid": f"{net}:v{len(vias)}"})
            i += 1
            continue
        # 同层：向后合并共线同向
        j = i + 1
        while j < len(pts) - 1 and pts[j][2] == L1 and pts[j + 1][2] == L1:
            ax, ay = pts[i][0], pts[i][1]
            bx, by = pts[j][0], pts[j][1]
            cx, cy = pts[j + 1][0], pts[j + 1][1]
            cross = (bx - ax) * (cy - by) - (by - ay) * (cx - bx)
            if abs(cross) > 1e-6:
                break
            j += 1
        x2, y2 = pts[j][0], pts[j][1]
        if math.hypot(x2 - x1, y2 - y1) > 1e-6:
            segs.append({"a": (x1, y1), "b": (x2, y2), "w": TRACK_W,
                         "layer": "F.Cu" if L1 == 0 else "B.Cu",
                         "net": net, "uuid": f"{net}:s{len(segs)}"})
        i = j


def _wipe_net(b: Board, segs: list[dict], vias: list[dict], net: str) -> None:
    """清掉某 net 的全部半成品（走线/via/占格），并重建其 pad 安全区。"""
    segs[:] = [s for s in segs if s["net"] != net]
    vias[:] = [v for v in vias if v["net"] != net]
    for L in (0, 1):
        occ = b.occ[L]
        for ix in range(NX):
            row = occ[ix]
            for iy in range(NY):
                if row[iy] == net:
                    row[iy] = None
    infl = TRACK_W / 2 + CLEAR
    for p in b.pads[net]:
        cx, cy = p["c"]
        w, h = p["wh"]
        b.mark_pad(cx, cy, w, h, p["layers"], net, infl)


def route_from_pcb(pcb_path: Path, max_rounds: int = 8) -> tuple[list[dict], list[dict]]:
    b0, _ = load_board(pcb_path)
    power = ("VCC3V3", "GND")
    rest = [n for n in b0.pads if n not in power]

    def bbox(net):
        ps = b0.pads[net]
        xs = [p["c"][0] for p in ps]
        ys = [p["c"][1] for p in ps]
        return (max(xs) - min(xs)) + (max(ys) - min(ys))

    # 先难后易：电源树 → 长信号 → 短信号
    rest.sort(key=bbox, reverse=True)
    order = [n for n in power if n in b0.pads] + rest

    errors: list[str] = []
    b, _ = load_board(pcb_path)
    segs: list[dict] = []
    vias: list[dict] = []
    pending = order
    for rnd in range(max_rounds):
        failed: list[str] = []
        for net in pending:
            err = route_net(b, net, [], segs, vias)
            if err:
                failed.append(net)
        if not failed:
            print(f"router: {len(segs)} segments, {len(vias)} vias (round {rnd + 1})")
            return segs, vias
        errors = failed
        print(f"round {rnd + 1}: {len(failed)} nets failed -> wipe 后干净重布")
        # 成功者的线永久保留；失败者的半成品是毒占位，清掉后整 net 重来
        for net in failed:
            _wipe_net(b, segs, vias, net)
        pending = failed
    raise RuntimeError(f"布线失败（{max_rounds} 轮未收敛）: {', '.join(errors)}")


if __name__ == "__main__":
    import sys
    s, v = route_from_pcb(Path(sys.argv[1]))
    print(f"OK {len(s)} segments {len(v)} vias")
