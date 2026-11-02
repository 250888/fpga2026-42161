# tests/test_top.py — 顶层双 wrapper / 极性单点 / 端口与 XDC 一致（V1.9 P048–P050）
#
# 红线（AGENTS.md §6）：生产 Top `b_conn=b_sync`（导通=1），反相只许在 loopback wrapper；
# 核心模块只能使用 b_conn，不得读取 b_raw，也不得在核心内反相。
from pathlib import Path
import re

REPO = Path(__file__).resolve().parents[1]
RTL = REPO / "rtl"
SIM = REPO / "sim"
CONSTRS = REPO / "constrs" / "ego1.xdc"
SCRIPTS = REPO / "scripts"
CLI = REPO / "src" / "xunji" / "cli.py"

HW = RTL / "xunji_top_hw.v"
LB = RTL / "xunji_top_loopback.v"
CORE = RTL / "xunji_core.v"


def _t(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _code(p: Path) -> str:
    """去掉注释后的源码：注释里允许讨论极性，判定只看真实代码。"""
    src = _t(p)
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return re.sub(r"//[^\n]*", "", src)


def _module_ports(path: Path) -> set[str]:
    """取模块头里的端口名（bus 取基名）。"""
    src = _t(path)
    i = src.find("module ")
    assert i >= 0, f"{path} 不是 Verilog 源"
    head = src[i:src.find(";", i)]          # 模块头（参数 + 端口）到第一个分号
    return set(re.findall(r"(?:input|output|inout)\s+(?:wire|reg)?\s*(?:\[[^\]]*\])?\s*(\w+)",
                          head))


def _xdc_ports() -> set[str]:
    names = set()
    for raw in _t(CONSTRS).splitlines():
        line = raw.split("#", 1)[0]
        for m in re.finditer(r"\[get_ports\s+(?:\{([^}]*)\}|([^\]\s]+))\]", line):
            n = (m.group(1) or m.group(2)).strip()
            names.add(re.sub(r"\[\*?\d*\]$", "", n))
    return names


def test_生产Top不反相():
    src = _code(HW)
    assert re.search(r"assign\s+b_conn\s*=\s*b_sync\s*;", src), \
        "xunji_top_hw 必须固定 b_conn = b_sync（V1.9 P048）"
    assert not re.search(r"~\s*b_sync", src), "xunji_top_hw 内不得出现反相"


def test_loopback反相():
    src = _code(LB)
    assert re.search(r"assign\s+b_conn\s*=\s*~\s*b_sync\s*;", src), \
        "xunji_top_loopback 必须 b_conn = ~b_sync（V1.9 P049）"


def test_核心不处理极性():
    for f in (CORE, RTL / "topology_scanner.v"):
        src = _code(f)
        hit = re.search(r"~\s*b_(conn|filtered|sync)", src)
        assert not hit, f"{f.name} 内出现极性反相（{hit.group(0) if hit else ''}）——极性只能在 wrapper"


def test_同步器带CDC属性():
    for name in ("input_sync.v", "xj_rst_sync.v"):
        src = _t(RTL / name)
        assert "ASYNC_REG" in src, f"{name} 缺 ASYNC_REG"
        assert "SHREG_EXTRACT" in src, f"{name} 缺 SHREG_EXTRACT"


def test_两wrapper端口集合一致():
    hw, lb = _module_ports(HW), _module_ports(LB)
    assert hw == lb, f"端口不一致：仅 hw={sorted(hw - lb)} / 仅 lb={sorted(lb - hw)}"


def test_端口与XDC完全对应():
    """无未约束端口（否则 Vivado UCIO-1/NSTD-1 DRC）、无指向不存在端口的约束。"""
    ports = _module_ports(HW)
    xdc = _xdc_ports()
    assert ports == xdc, (f"仅顶层有: {sorted(ports - xdc)} / 仅XDC有: {sorted(xdc - ports)}")


def test_管线顶层名与模块真实存在():
    rtl_modules = set()
    for f in RTL.glob("*.v"):
        rtl_modules |= set(re.findall(r"\bmodule\s+(\w+)", _t(f)))
    sim_modules = set()
    for f in SIM.glob("*.v"):
        sim_modules |= set(re.findall(r"\bmodule\s+(\w+)", _t(f)))

    proj = _t(SCRIPTS / "create_project.tcl")
    synth_top = re.search(r"set_property\s+top\s+(\w+)\s+\[current_fileset\]", proj)
    sim_top = re.search(r"set_property\s+top\s+(\w+)\s+\[get_filesets sim_1\]", proj)
    assert synth_top and sim_top, "create_project.tcl 缺顶层设置"
    assert synth_top.group(1) == "xunji_top_hw", f"合成顶层应为生产 Top: {synth_top.group(1)}"
    assert sim_top.group(1) == "tb_xunji_loopback", f"仿真顶层: {sim_top.group(1)}"
    assert synth_top.group(1) in rtl_modules, "合成顶层模块未在 rtl/ 中定义"
    assert sim_top.group(1) in sim_modules, "仿真顶层模块未在 sim/ 中定义"

    sim_tcl = _t(SCRIPTS / "simulate.tcl")
    m = re.search(r"set_property\s+top\s+(\w+)\s+\[get_filesets sim_1\]", sim_tcl)
    assert m and m.group(1) == sim_top.group(1), "simulate.tcl 与 create_project.tcl 仿真顶层不一致"

    bit = re.search(r"impl_1\s+(\S+\.bit)", _t(SCRIPTS / "build.tcl"))
    assert bit and bit.group(1) == f"{synth_top.group(1)}.bit", \
        f"build.tcl 比特流名未跟随顶层: {bit.group(1) if bit else None}"


def test_cli引用双wrapper与仿真顶层():
    cli = _t(CLI)
    assert "xunji_top_hw" in cli, "cli lint 未覆盖生产顶层 xunji_top_hw"
    assert "xunji_top_loopback" in cli, "cli lint 未覆盖 loopback 顶层"
    assert "tb_xunji_loopback" in cli, "cli sim/xsim 顶层名未跟随改名"
    assert "xj_top" not in cli, "cli 仍引用已废弃的 xj_top"


def test_脚本不再引用xj_top():
    for f in list(SCRIPTS.glob("*.tcl")) + [SCRIPTS / "lint.vlt"]:
        assert "xj_top" not in _t(f), f"{f.name} 仍引用已废弃的 xj_top"
    # 豁免文件名必须跟上改名后的核心文件
    assert "xunji_core" in _t(SCRIPTS / "lint.vlt"), "lint.vlt 豁免未覆盖 xunji_core.v"
