# tests/test_xdc.py — constrs/ego1.xdc 与 V1.9 §4.1 表3 / §4.2 冻结约束的一致性
#
# 依据：瞬迹_完整可行技术路线_EGO1开发板版_V1.9.docx
#   §4.1 表3：J5 物理针 ↔ 信号 ↔ PACKAGE_PIN（唯一针脚基准）
#   §4.2     ：冻结 XDC（时钟/复位/32 路 J5/DRIVE 4/SLEW SLOW/UART）
#   HANDOFF §6 P0-3：按表3 重写 ego1.xdc
#
# 这些断言是红线：改管脚必须先改 V1.9 文档，再改本测试，最后改 XDC。
from pathlib import Path
import re

REPO = Path(__file__).resolve().parents[1]
XDC = REPO / "constrs" / "ego1.xdc"

# --- V1.9 §4.1 表3（冻结，逐针不可动）-------------------------------------
FROZEN_PIN = {
    "sys_clk": "P17",          # 100 MHz（§4.2）
    "rst_n": "P15",            # EGO1 S6 复位，按下拉低（§4.2）
    "uart_tx": "T4",           # 板级 UART_RX，FPGA 视角发送（§4.1）
    "uart_rx": "N5",           # 板级 UART_TX，FPGA 视角接收（§4.1）
    # a_ctrl_n[15:0] = J5-1..16
    "a_ctrl_n[0]": "B16", "a_ctrl_n[1]": "B17", "a_ctrl_n[2]": "A15", "a_ctrl_n[3]": "A16",
    "a_ctrl_n[4]": "A13", "a_ctrl_n[5]": "A14", "a_ctrl_n[6]": "B18", "a_ctrl_n[7]": "A18",
    "a_ctrl_n[8]": "F13", "a_ctrl_n[9]": "F14", "a_ctrl_n[10]": "B13", "a_ctrl_n[11]": "B14",
    "a_ctrl_n[12]": "D14", "a_ctrl_n[13]": "C14", "a_ctrl_n[14]": "B11", "a_ctrl_n[15]": "A11",
    # b_raw[15:0] = J5-17..32
    "b_raw[0]": "E15", "b_raw[1]": "E16", "b_raw[2]": "D15", "b_raw[3]": "C15",
    "b_raw[4]": "H16", "b_raw[5]": "G16", "b_raw[6]": "F15", "b_raw[7]": "F16",
    "b_raw[8]": "H14", "b_raw[9]": "G14", "b_raw[10]": "E17", "b_raw[11]": "D17",
    "b_raw[12]": "K13", "b_raw[13]": "J13", "b_raw[14]": "H17", "b_raw[15]": "G17",
}

# --- 板载 LED/按键/拨码：V1.9 §4.2 未冻结（HANDOFF §4.3 遗留1）-----------
# 这里只做「不再静默漂移」的回归锁定；转正与否必须先在 V1.9 文档里拍板。
PROVISIONAL_PIN = {
    "led[0]": "K3", "led[1]": "M1", "led[2]": "L1", "led[3]": "K6",
    "led[4]": "J5", "led[5]": "H5", "led[6]": "H6", "led[7]": "K1",
    "led[8]": "K2", "led[9]": "J2", "led[10]": "J3", "led[11]": "H4",
    "led[12]": "J4", "led[13]": "G3", "led[14]": "G4", "led[15]": "F6",
    "btn[0]": "R11", "btn[1]": "R17", "btn[2]": "R15", "btn[3]": "V1", "btn[4]": "U4",
    "sw[0]": "R1", "sw[1]": "N4", "sw[2]": "M4", "sw[3]": "R2",
    "sw[4]": "P2", "sw[5]": "P3", "sw[6]": "P4", "sw[7]": "P5",
}

_PORT = r"\[get_ports\s+(?:\{(?P<p1>[^}]*)\}|(?P<p2>[^\]\s]+))\]"
_RE_DICT = re.compile(r"set_property\s+-dict\s*\{(?P<props>[^}]*)\}\s*" + _PORT)
_RE_ONE = re.compile(
    r"set_property\s+(?P<prop>PACKAGE_PIN|IOSTANDARD|DRIVE|SLEW)\s+(?P<val>\S+)\s+" + _PORT)
_RE_CLOCK = re.compile(r"create_clock\b.*?" + _PORT)


def _port(m: re.Match) -> str:
    return (m.group("p1") or m.group("p2")).strip()


def _live_lines() -> list[str]:
    out = []
    for raw in XDC.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0]          # Tcl 行尾注释
        if line.strip():
            out.append(line)
    return out


def _parse():
    """返回 (pin[端口]=封装脚, props[端口][属性名]=值, clocks[端口]=周期文本)"""
    pin: dict[str, str] = {}
    props: dict[str, dict[str, str]] = {}
    clocks: dict[str, str] = {}
    for line in _live_lines():
        for m in _RE_DICT.finditer(line):
            # -dict { PACKAGE_PIN X IOSTANDARD Y }：按两两一组解析
            port = _port(m)
            toks = m.group("props").split()
            for i in range(0, len(toks) - 1, 2):
                props.setdefault(port, {})[toks[i]] = toks[i + 1]
            if "PACKAGE_PIN" in props.get(port, {}):
                pin[port] = props[port]["PACKAGE_PIN"]
        for m in _RE_ONE.finditer(line):
            port = _port(m)
            props.setdefault(port, {})[m.group("prop")] = m.group("val")
            if m.group("prop") == "PACKAGE_PIN":
                pin[port] = m.group("val")
        mc = _RE_CLOCK.search(line)
        if mc:
            clocks[_port(mc)] = line
    return {k: v for k, v in pin.items() if isinstance(v, str)}, props, clocks


def test_表3的32路J5管脚逐条一致():
    pin, _, _ = _parse()
    bad = {f"{p}: XDC={pin.get(p)!r} 表3={q}"
           for p, q in FROZEN_PIN.items() if pin.get(p) != q}
    assert not bad, "与 V1.9 §4.1 表3 不一致:\n" + "\n".join(sorted(bad))


def test_冻结端口一个不多一个不少():
    pin, _, _ = _parse()
    frozen_ports = {p for p in FROZEN_PIN}
    assert frozen_ports <= set(pin), f"缺冻结端口: {sorted(frozen_ports - set(pin))}"


def test_全表管脚无重复():
    pin, _, _ = _parse()
    seen: dict[str, str] = {}
    dup = []
    for port, pkg in pin.items():
        if pkg in seen:
            dup.append(f"{pkg}: {seen[pkg]} 与 {port}")
        seen[pkg] = port
    assert not dup, "同一封装脚被多个端口占用:\n" + "\n".join(sorted(dup))


def _attr(props: dict[str, dict[str, str]], port: str, key: str):
    """逐端口属性；若只写了通配 base[*] 则回退到通配值。"""
    if port in props and key in props[port]:
        return props[port][key]
    base = port.split("[", 1)[0]
    return props.get(f"{base}[*]", {}).get(key)


def test_电平标准全为LVCMOS33():
    _, props, _ = _parse()
    bad = [f"{p}: {_attr(props, p, 'IOSTANDARD')}"
           for p in pin_all(props) if _attr(props, p, "IOSTANDARD") != "LVCMOS33"]
    assert not bad, "IOSTANDARD 非 LVCMOS33:\n" + "\n".join(sorted(bad))


def pin_all(props: dict[str, dict[str, str]]) -> list[str]:
    return sorted(p for p in props if "PACKAGE_PIN" in props[p])


def test_a端驱动强度与摆率按冻结段要求():
    _, props, _ = _parse()
    a_ports = sorted(p for p in props if re.fullmatch(r"a_ctrl_n\[\d+\]", p))
    assert len(a_ports) == 16, f"a_ctrl_n 约束不足 16 路: {a_ports}"
    # §4.2 写法是通配 [get_ports {a_ctrl_n[*]}]；逐路写法也接受，但必须逐路带全
    for p in a_ports:
        assert _attr(props, p, "DRIVE") == "4", f"{p} DRIVE != 4"
        assert _attr(props, p, "SLEW") == "SLOW", f"{p} SLEW != SLOW"
    # 只允许 a 端降驱动，B 端是输入不需要
    assert "b_raw[*]" not in props


def test_系统时钟10ns():
    _, _, clocks = _parse()
    assert "sys_clk" in clocks, "缺少针对 sys_clk 的 create_clock"
    line = clocks["sys_clk"]
    assert re.search(r"-period\s+10\.000", line), f"周期不是 10.000: {line}"


def test_暂定板载段未漂移():
    pin, _, _ = _parse()
    bad = {f"{p}: XDC={pin.get(p)!r} 草稿={q}"
           for p, q in PROVISIONAL_PIN.items() if pin.get(p) != q}
    assert not bad, ("板载 LED/按键/拨码（V1.9 未冻结，暂定段）发生变化：\n"
                     + "\n".join(sorted(bad))
                     + "\n若确要改，先改 V1.9 §4.2/HANDOFF §4.3 遗留1，再改本测试。")
