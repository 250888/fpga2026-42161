# uart_packet_tx 帧协议对齐 V1.9 §17 红线（计划：doc/superpowers/plans/2026-10-11-uart-frame-v19.md）
#
# 三道锁：① RTL 源码红线（55 AA/CRC-16 在场、A5 5A/CRC8 禁绝）② TB 黄金帧与
# protocol.build_frame 双向一致（跨语言锁定）③ cli sim/xsim 覆盖两个仿真顶层。
from pathlib import Path
import re

from xunji.protocol import build_frame

REPO = Path(__file__).resolve().parents[1]
RTL = REPO / "rtl" / "uart_packet_tx.v"
SIM_TB = REPO / "sim" / "tb_uart_packet_tx.v"
CLI = REPO / "src" / "xunji" / "cli.py"

# TB 激励：matrix=16'h2804、open=0、stuck=0、cls=0、timestamp[7:0]=8'hBE
# （payload 定义见 tests/test_matrix_payload.py 与 specs/2026-10-22-topology-frame-16ch.md）
PAYLOAD = bytes([0x04, 0x28, 0x00, 0x00, 0x00, 0x00, 0x00, 0xBE])
GOLDEN0 = bytes.fromhex("55AA01010800000004280000000000BEE338")
GOLDEN1 = bytes.fromhex("55AA01010800010004280000000000BEA657")


def _code(p: Path) -> str:
    src = p.read_text(encoding="utf-8")
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return re.sub(r"//[^\n]*", "", src)


def _tb_localparam_hex(name: str) -> bytes:
    """从 TB 提取 localparam [8*FRAME_LEN-1:0] NAME = 144'h...（18 字节黄金帧字面量）。"""
    src = SIM_TB.read_text(encoding="utf-8")
    m = re.search(rf"{name}\s*=\s*144'h([0-9A-Fa-f]{{36}})", src)
    assert m, f"sim/tb_uart_packet_tx.v 缺少 localparam {name}（144'h 黄金帧）"
    return bytes.fromhex(m.group(1))


class TestRtlSourceRedlines:
    """旧帧（A5 5A/CRC8）不得回潮，§17 头与 CRC-16 参数必须在场。"""

    def test_SOF为55AA次序且无A55A(self):
        src = _code(RTL).upper()
        i55, iaa = src.find("8'H55"), src.find("8'HAA")
        assert 0 <= i55 < iaa, "RTL 缺少 SOF 55 AA 或发送次序颠倒（V1.9 §17）"
        # 负向用边界：避免 18'hA5xx 之类宽字面量误命中
        assert not re.search(r"(?<![0-9])8'ha5\b", _code(RTL), re.I), "残留旧帧头 A5"
        assert not re.search(r"(?<![0-9])8'h5a\b", _code(RTL), re.I), "残留旧帧头 5A"

    def test_CRC16参数在场且旧CRC8清除(self):
        src = _code(RTL).upper()
        assert "16'H1021" in src, "缺 CRC-16/CCITT-FALSE poly=0x1021"
        assert "16'HFFFF" in src, "缺 CRC-16/CCITT-FALSE init=0xFFFF"
        assert "8'H07" not in src and "CRC8" not in src, "旧 CRC-8 残留"

    def test_CRC小端先发低字节(self):
        src = _code(RTL)
        lo = src.find("crc_r[7:0]")
        hi = src.find("crc_r[15:8]")
        assert lo >= 0 and hi >= 0, "CRC 必须以 crc_r 低字节在前发送（小端）"
        assert lo < hi, "CRC 高字节先发违反小端约定"


class TestTbGoldenLock:
    """TB 字面量黄金帧必须与 protocol.build_frame 逐字节一致（跨语言双向锁）。"""

    def test_TB黄金帧0与Python协议一致(self):
        assert _tb_localparam_hex("GOLDEN0") == build_frame(1, 1, 0, PAYLOAD) == GOLDEN0

    def test_TB黄金帧1序列递增(self):
        assert _tb_localparam_hex("GOLDEN1") == build_frame(1, 1, 1, PAYLOAD) == GOLDEN1

    def test_黄金帧总长18且长度字段为8(self):
        assert len(GOLDEN0) == 18, "4 路拓扑帧总长应为 18 B（payload 8 B）"
        assert int.from_bytes(GOLDEN0[4:6], "little") == 8, "Length 字段应等于 payload 8 B"


class TestCliSimTops:
    def test_cli的SIM_TOPS恰含sim目录全部仿真顶层(self):
        # 不能只查子串：字符串可能只出现在注释里（评审 minor-2）。
        # 清单自维护：必须在 cli 里登记 sim/ 下每一个 tb_*.v，且不得有幽灵条目。
        cli = CLI.read_text(encoding="utf-8")
        m = re.search(r"SIM_TOPS\s*=\s*\(([^)]*)\)", cli)
        assert m, "cli 缺少 SIM_TOPS 元组"
        registered = set(re.findall(r'"(tb_\w+)"', m.group(1)))
        present = {p.stem for p in (REPO / "sim").glob("tb_*.v")}
        assert registered == present, (
            f"SIM_TOPS 与实际 TB 不一致：仅登记 {sorted(registered - present)} / "
            f"未登记 {sorted(present - registered)}")


class TestTypeConstant:
    def test_TYPE_MATRIX与帧Type字节一致(self):
        from xunji.protocol import TYPE_MATRIX  # 常量尚不存在时本测试红，属任务1范围
        assert TYPE_MATRIX == GOLDEN0[3] == 1
