"""FE-16 生成物机检。

期望表独立硬编码（直接从 V1.9 TABLE 3/13/14 与 74xx14/07 标准脚位推导），
不 import 生成器的 fe16_design —— 两条独立链路互为交叉验证。
"""
from __future__ import annotations

import json
import math
import re
from collections import Counter
from pathlib import Path

import pytest

PCB_PATH = Path(__file__).resolve().parents[1] / "pcb" / "frontend16" / "xunji_fe16.kicad_pcb"
SCH_PATH = PCB_PATH.with_suffix(".kicad_sch")

# ---------------------------------------------------------------------------
# 独立期望表（V1.9）
# ---------------------------------------------------------------------------
BOARD_W, BOARD_H = 96.0, 96.0

# 74xx07/14 家族标准脚位：槽位 → (输入脚, 输出脚)
CH_SLOT = {0: (1, 2), 1: (3, 4), 2: (5, 6),
           3: (9, 8), 4: (11, 10), 5: (13, 12)}
PIN_GND, PIN_VCC = 7, 14
N_CH = 16


def _expected() -> dict[tuple[str, str], str | None]:
    """(ref, pin) → 期望网络；None = 必须无网络（NC）。"""
    exp: dict[tuple[str, str], str | None] = {}

    def E(ref: str, pin, net: str | None) -> None:
        exp[(ref, str(pin))] = net

    # J5（V1.9 TABLE 3）
    for i in range(N_CH):
        E("J5", i + 1, f"ACTRL{i}")
        E("J5", 17 + i, f"BRW{i}")
    E("J5", 33, "GND")
    E("J5", 34, "GND")
    E("J5", 35, "VIN_J5")
    E("J5", 36, "VIN_J5")

    # A/B 口（TABLE 14：1..16 信号，17..20 NC/KEY）
    for i in range(N_CH):
        E("JA", i + 1, f"A{i}")
        E("JB", i + 1, f"B{i}")
    for p in range(17, 21):
        E("JA", p, None)
        E("JB", p, None)

    # 16 通道信号链
    for ch in range(N_CH):
        in_p, out_p = CH_SLOT[ch % 6]
        u07 = f"U{ch // 6 + 1}"        # U1..U3
        u14 = f"U{ch // 6 + 4}"        # U4..U6
        # A 路
        E("J5", ch + 1, f"ACTRL{ch}")
        E(u07, in_p, f"ACTRL{ch}")
        E(f"RU{ch + 1}", 1, f"ACTRL{ch}")
        E(f"RU{ch + 1}", 2, "VCC3V3")
        E(u07, out_p, f"ADRV{ch}")
        E(f"RS{ch + 1}", 1, f"ADRV{ch}")
        E(f"RS{ch + 1}", 2, f"A{ch}")
        E("JA", ch + 1, f"A{ch}")
        E(f"TP{ch + 1}", 1, f"A{ch}")
        # B 路
        E(f"RP{ch + 1}", 1, f"B{ch}")
        E(f"RP{ch + 1}", 2, "VCC3V3")
        E(u14, in_p, f"B{ch}")
        E("JB", ch + 1, f"B{ch}")
        E(f"TP{17 + ch}", 1, f"B{ch}")
        E(u14, out_p, f"BRW{ch}")
        E("J5", 17 + ch, f"BRW{ch}")
        E(f"TP{33 + ch}", 1, f"BRW{ch}")

    # 六颗 IC 电源脚
    for i in range(1, 7):
        E(f"U{i}", PIN_GND, "GND")
        E(f"U{i}", PIN_VCC, "VCC3V3")

    # 未用通道（V1.9 §9：U3 输入固定高、U6 输入固定 GND；输出悬空）
    for slot in (4, 5):
        in_p, out_p = CH_SLOT[slot]
        E("U3", in_p, "VCC3V3")
        E("U3", out_p, None)
        E("U6", in_p, "GND")
        E("U6", out_p, None)

    # 去耦 + 总旁路
    for c in range(1, 8):
        E(f"C{c}", 1, "VCC3V3")
        E(f"C{c}", 2, "GND")

    # 电源断点/备用入口（D15）
    E("RCT1", 1, "VIN_J5")
    E("RCT1", 2, "VCC3V3")
    E("JP1", 1, "VCC3V3")
    E("JP1", 2, "VIN_EXT")
    E("EXT1", 1, "VIN_EXT")
    E("EXT1", 2, "GND")

    # 电源测试点
    E("TP49", 1, "VCC3V3")
    E("TP50", 1, "GND")
    E("TP51", 1, "VIN_J5")
    return exp


EXPECTED = _expected()

# ---------------------------------------------------------------------------
# mini s-expression 解析
# ---------------------------------------------------------------------------
_TOKEN = re.compile(r'\(|\)|"(?:[^"\\]|\\.)*"|[^\s()]+')


def parse_sexpr(text: str):
    stack: list[list] = [[]]
    for tok in _TOKEN.findall(text):
        if tok == "(":
            stack.append([])
        elif tok == ")":
            done = stack.pop()
            stack[-1].append(done)
        elif tok.startswith('"'):
            stack[-1].append(json.loads(tok))
        else:
            stack[-1].append(tok)
    root = stack[0]
    assert len(root) == 1, "s-expression 根节点数异常"
    return root[0]


def kids(node, key):
    return [x for x in node if isinstance(x, list) and x and x[0] == key]


def kid(node, key):
    k = kids(node, key)
    return k[0] if k else None


def _rot(lx: float, ly: float, fx: float, fy: float, deg: float):
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    return (fx + lx * c + ly * s, fy - lx * s + ly * c)


def load_pcb():
    root = parse_sexpr(PCB_PATH.read_text(encoding="utf-8"))
    assert root[0] == "kicad_pcb"
    fps: dict[str, dict[str, tuple[str | None, tuple[float, float]]]] = {}
    for fp in kids(root, "footprint"):
        at = kid(fp, "at")
        fx, fy = float(at[1]), float(at[2])
        frot = float(at[3]) if len(at) > 3 else 0.0
        ref = None
        for prop in kids(fp, "property"):
            if prop[1] == "Reference":
                ref = prop[2]
        assert ref, "footprint 缺 Reference"
        pads = {}
        for pad in kids(fp, "pad"):
            num = pad[1]
            if num == "":
                continue
            pat = kid(pad, "at")
            lx, ly = float(pat[1]), float(pat[2])
            netn = kid(pad, "net")
            net = netn[2] if netn else None
            pads[num] = (net, _rot(lx, ly, fx, fy, frot))
        fps[ref] = pads
    # segment/via 只带 net 代号，经顶层 (net code name) 映射回网名
    netmap = {str(n[1]): n[2] for n in kids(root, "net") if len(n) >= 3}

    def _netname(node):
        code = str(kid(node, "net")[1])
        return netmap.get(code, code)

    segs = []
    for s in kids(root, "segment"):
        st, en = kid(s, "start"), kid(s, "end")
        segs.append({
            "a": (float(st[1]), float(st[2])),
            "b": (float(en[1]), float(en[2])),
            "w": float(kid(s, "width")[1]),
            "layer": kid(s, "layer")[1],
            "net": _netname(s),
        })
    vias = [{"p": (float(kid(v, "at")[1]), float(kid(v, "at")[2])),
             "net": _netname(v)} for v in kids(root, "via")]
    edges = [(kid(g, "start"), kid(g, "end")) for g in kids(root, "gr_line")
             if kid(g, "layer") and kid(g, "layer")[1] == "Edge.Cuts"]
    return fps, segs, vias, edges


@pytest.fixture(scope="module")
def pcb():
    if not PCB_PATH.exists():
        pytest.fail(f"缺少生成物 {PCB_PATH}（先跑 gen_frontend16.py）")
    return load_pcb()

# ---------------------------------------------------------------------------
# 网表断言
# ---------------------------------------------------------------------------
def test_all_expected_pins_connected(pcb):
    fps = pcb[0]
    bad = []
    for (ref, pin), net in EXPECTED.items():
        if ref not in fps:
            bad.append(f"{ref} 整个缺失")
            continue
        if pin not in fps[ref]:
            bad.append(f"{ref}.{pin} 焊盘缺失")
            continue
        got = fps[ref][pin][0]
        if got != net:
            bad.append(f"{ref}.{pin}: 期望 {net} 实际 {got}")
    assert not bad, "网表偏差:\n" + "\n".join(bad[:40])


def test_no_unexpected_pin_nets(pcb):
    """生成的有网焊盘必须全部出现在期望表里（防多连/串网）。"""
    fps = pcb[0]
    extra = []
    for ref, pads in fps.items():
        for pin, (net, _xy) in pads.items():
            if net is None:
                continue
            key = (ref, pin)
            if key not in EXPECTED:
                extra.append(f"{ref}.{pin}={net}（期望表无此焊盘）")
            elif EXPECTED[key] != net:
                extra.append(f"{ref}.{pin}: 期望 {EXPECTED[key]} 实际 {net}")
    assert not extra, "意外连接:\n" + "\n".join(extra[:40])


def test_nc_pins_have_no_net(pcb):
    fps = pcb[0]
    for key, net in EXPECTED.items():
        if net is None:
            ref, pin = key
            got = fps[ref][pin][0]
            assert got is None, f"NC 焊盘 {ref}.{pin} 不该有网络，实际 {got}"


def test_ref_inventory(pcb):
    fps = pcb[0]
    cnt = Counter(re.match(r"[A-Za-z]+", r).group() for r in fps)
    assert cnt["RS"] == 16 and cnt["RU"] == 16 and cnt["RP"] == 16
    assert cnt["U"] == 6 and cnt["C"] == 7 and cnt["TP"] == 51
    assert {"J5", "JA", "JB"} <= set(fps) and cnt["H"] == 4
    assert cnt["RCT"] == 1 and cnt["JP"] == 1 and cnt["EXT"] == 1
    assert len(fps) == 122, f"位号总数 {len(fps)} != 122"


def test_board_outline(pcb):
    _f, _s, _v, edges = pcb
    assert len(edges) == 4, f"Edge.Cuts 应 4 段，实际 {len(edges)}"
    xs, ys = [], []
    for st, en in edges:
        xs += [float(st[1]), float(en[1])]
        ys += [float(st[2]), float(en[2])]
    assert abs(max(xs) - min(xs) - BOARD_W) < 0.01
    assert abs(max(ys) - min(ys) - BOARD_H) < 0.01


def test_placement_zones(pcb):
    """布局语义：接口/IC 分区不能错（J5 顶、JA 左、JB 右、U1-3 左半…）。"""
    fps = pcb[0]
    centers = {}
    for ref, pads in fps.items():
        if pads:
            xs = [xy[0] for _n, xy in pads.values()]
            ys = [xy[1] for _n, xy in pads.values()]
            centers[ref] = (sum(xs) / len(xs), sum(ys) / len(ys))
    # 安装孔是 NPTH 无铜焊盘（被跳过），直接读 footprint 原点
    root = parse_sexpr(PCB_PATH.read_text(encoding="utf-8"))
    for fp in kids(root, "footprint"):
        ref = next((p[2] for p in kids(fp, "property") if p[1] == "Reference"), None)
        if ref and ref.startswith("H") and ref not in centers:
            at = kid(fp, "at")
            centers[ref] = (float(at[1]), float(at[2]))
    assert centers["J5"][1] < 16, "J5 应在顶边"
    assert 0.35 * BOARD_W < centers["J5"][0] < 0.65 * BOARD_W, "J5 应在顶部中央"
    assert centers["JA"][0] < 15, "A 口应在左边"
    assert centers["JB"][0] > BOARD_W - 15, "B 口应在右边"
    for u in ("U1", "U2", "U3"):
        assert centers[u][0] < BOARD_W / 2, f"{u} 应在左半板（A 侧）"
    for u in ("U4", "U5", "U6"):
        assert centers[u][0] > BOARD_W / 2, f"{u} 应在右半板（B 侧）"
    # 安装孔在四角
    for h in ("H1", "H2", "H3", "H4"):
        x, y = centers[h]
        assert (x < 10 and y < 10) or (x > BOARD_W - 10 and y < 10) \
            or (x < 10 and y > BOARD_H - 10) \
            or (x > BOARD_W - 10 and y > BOARD_H - 10), f"{h} 不在板角"


def test_no_pad_overlap(pcb):
    """异网焊盘铜边距 ≥0.2mm（按 pad 实际 size 矩形分离距；C4/TP 压叠回归防护）。"""
    root = parse_sexpr(PCB_PATH.read_text(encoding="utf-8"))
    pads = []
    for fp in kids(root, "footprint"):
        at = kid(fp, "at")
        fx, fy = float(at[1]), float(at[2])
        frot = float(at[3]) if len(at) > 3 else 0.0
        ref = next((p[2] for p in kids(fp, "property") if p[1] == "Reference"), "?")
        for pad in kids(fp, "pad"):
            pat = kid(pad, "at")
            lx, ly = float(pat[1]), float(pat[2])
            size = kid(pad, "size")
            w, h = float(size[1]), float(size[2])
            netn = kid(pad, "net")
            net = netn[2] if netn else None
            a = math.radians(frot)
            cx = fx + lx * math.cos(a) + ly * math.sin(a)
            cy = fy - lx * math.sin(a) + ly * math.cos(a)
            if frot % 180 == 90:
                w, h = h, w
            pads.append((ref, pad[1], net, cx, cy, w, h))
    worst = []
    for i in range(len(pads)):
        r1, n1, net1, x1, y1, w1, h1 = pads[i]
        if not net1:
            continue
        for j in range(i + 1, len(pads)):
            r2, n2, net2, x2, y2, w2, h2 = pads[j]
            if not net2 or net2 == net1:
                continue
            dx = max(0.0, abs(x1 - x2) - (w1 + w2) / 2)
            dy = max(0.0, abs(y1 - y2) - (h1 + h2) / 2)
            d = math.hypot(dx, dy)
            if d < 0.2:
                worst.append((d, f"{r1}.{n1}({net1})", f"{r2}.{n2}({net2})"))
    worst.sort()
    assert not worst, f"铜边距 <0.2mm 的异网焊盘对: {worst[:8]}"



def _seg_point_dist(a, b, p) -> float:
    ax, ay = a
    bx, by = b
    px, py = p
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def _seg_seg_dist(s1, s2) -> float:
    # 线段相交=0（粗略用端点到线段最小值即可满足正交布线检查）
    return min(_seg_point_dist(s1["a"], s1["b"], s2["a"]),
               _seg_point_dist(s1["a"], s1["b"], s2["b"]),
               _seg_point_dist(s2["a"], s2["b"], s1["a"]),
               _seg_point_dist(s2["a"], s2["b"], s1["b"]))


def test_routing_nonempty(pcb):
    _f, segs, _v, _e = pcb
    assert segs, "尚无走线（fe16_router 未接入或 route_all 返回空）"


def test_routing_connected(pcb):
    """每个信号网的全部焊盘必须经走线几何连通。"""
    fps, segs, vias, _e = pcb
    if not segs:
        pytest.skip("无走线")
    # 收集每个 net 的分量（union-find on 端点/pad）
    from collections import defaultdict
    nets: dict[str, list] = defaultdict(lambda: {"pads": [], "segs": [], "vias": []})
    for ref, pads in fps.items():
        for pin, (net, xy) in pads.items():
            if net:
                nets[net]["pads"].append((f"{ref}.{pin}", xy))
    for s in segs:
        nets[s["net"]]["segs"].append(s)
    for v in vias:
        nets[v["net"]]["vias"].append(v)

    problems = []
    for net, data in sorted(nets.items()):
        if not data["segs"]:
            if len(data["pads"]) > 1:
                problems.append(f"{net}: 无走线但有 {len(data['pads'])} 焊盘")
            continue
        # 节点 = 焊盘 + 线端点 + via；union
        nodes: list[tuple] = [xy for _n, xy in data["pads"]]
        owner = list(range(len(nodes)))
        pad_names = [n for n, _x in data["pads"]]

        def find(i):
            while owner[i] != i:
                owner[i] = owner[owner[i]]
                i = owner[i]
            return i

        def union(i, j):
            ri, rj = find(i), find(j)
            if ri != rj:
                owner[rj] = ri

        def add_node(xy, tol=0.05):
            for i, q in enumerate(nodes):
                if math.hypot(xy[0] - q[0], xy[1] - q[1]) <= tol:
                    return i
            nodes.append(xy)
            owner.append(len(owner))
            return len(nodes) - 1

        for s in data["segs"]:
            union(add_node(s["a"]), add_node(s["b"]))
        for v in data["vias"]:
            add_node(v["p"])
        # 焊盘 ↔ 端点：端点落在焊盘覆盖范围
        pad_idx = {}
        for i, (name, xy) in enumerate(data["pads"]):
            pad_idx[name] = i
        for si, s in enumerate(data["segs"]):
            for end in (s["a"], s["b"]):
                for i, (_n, pxy) in enumerate(data["pads"]):
                    if math.hypot(end[0] - pxy[0], end[1] - pxy[1]) <= 0.95:
                        # 端点近焊盘中心 → 视为接到该焊盘（找该端点所在分量并入）
                        ni = add_node(end)
                        union(ni, i)
        # 线端点之间共享
        # （add_node 已按容差合并）
        roots = {find(i) for i in range(len(nodes))}
        # 允许：个别孤立焊盘以外全连通 → 每 net 分量数应为 1
        if len(roots) > 1:
            groups: dict[int, list] = defaultdict(list)
            for i in range(len(nodes)):
                groups[find(i)].append(i)
            desc = "; ".join(
                ",".join(pad_names[i] for i in g if i < len(pad_names))[:60]
                for g in groups.values())
            problems.append(f"{net}: {len(roots)} 个分量 [{desc}]")
    assert not problems, "连通性失败:\n" + "\n".join(problems[:30])


def test_clearance(pcb):
    """同层异网走线间距 ≥ 0.2mm（粗查；权威判定 kicad-cli DRC）。"""
    _f, segs, _v, _e = pcb
    if not segs:
        pytest.skip("无走线")
    bad = []
    for i in range(len(segs)):
        s1 = segs[i]
        for j in range(i + 1, len(segs)):
            s2 = segs[j]
            if s1["layer"] != s2["layer"] or s1["net"] == s2["net"]:
                continue
            d = _seg_seg_dist(s1, s2) - (s1["w"] + s2["w"]) / 2
            if d < 0.2:
                bad.append(f"{s1['net']}↔{s2['net']} @{s1['layer']} 间距 {d:.3f}")
    assert not bad, "间距违规:\n" + "\n".join(bad[:20])


def test_segments_inside_board(pcb):
    _f, segs, _v, _e = pcb
    if not segs:
        pytest.skip("无走线")
    out = []
    for s in segs:
        for x, y in (s["a"], s["b"]):
            if not (0.0 <= x <= BOARD_W and 0.0 <= y <= BOARD_H):
                out.append(f"{s['net']} 端点 ({x},{y}) 出板")
    assert not out, "\n".join(out[:10])


# ---------------------------------------------------------------------------
# 原理图 ↔ PCB 一致性
# ---------------------------------------------------------------------------
def test_sch_pcb_consistency(pcb):
    fps = pcb[0]
    assert SCH_PATH.exists(), "缺少原理图"
    root = parse_sexpr(SCH_PATH.read_text(encoding="utf-8"))
    assert root[0] == "kicad_sch"
    inst_refs = set()
    for sym in kids(root, "symbol"):
        for prop in kids(sym, "property"):
            if prop[1] == "Reference" and not prop[2].startswith("#"):
                inst_refs.add(prop[2])
    # 安装孔只在 PCB（KiCad 惯例，不上原理图）
    pcb_refs = {r for r in fps if not (r.startswith("H") and r[1:].isdigit())}
    assert inst_refs == pcb_refs, (
        f"原理图/PCB 位号不一致: sch-pcb={sorted(inst_refs - pcb_refs)[:10]} "
        f"pcb-sch={sorted(pcb_refs - inst_refs)[:10]}")
    labels = {g[1] for g in kids(root, "global_label")}
    pcb_nets = {n for pads in fps.values() for n, _xy in pads.values() if n}
    # 原理图 label 集合应覆盖 PCB 全部网络（NC 网络无 label 属正常）
    missing = pcb_nets - labels
    assert not missing, f"原理图缺网络 label: {sorted(missing)[:10]}"
