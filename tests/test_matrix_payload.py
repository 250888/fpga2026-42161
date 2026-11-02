# tests/test_matrix_payload.py — 拓扑矩阵帧 payload 定义（16 路扩展，2026-10-22 决策）
#
# 背景：V1.9 §17 只冻结帧结构（SOF 55AA / Ver / Type / Len(2B) / Seq(2B) / Payload / CRC16），
# payload 语义是工程侧决策，原 4 字节（mat_lo/mat_hi/open/ts0）无法承载 16 路 256 bit 矩阵。
# 本次扩展（决策记录 doc/superpowers/specs/2026-10-22-topology-frame-16ch.md）：
#   Payload = MAT[N*N/8] + open(2,LE) + stuck(2,LE) + cls(1) + ts0(1)
#   byte k = matrix[8k+7 : 8k]（行 major，row0 的 b0..b7 在 byte0）；
#   cls: 0 PASS / 1 OPEN / 2 MISWIRE / 3 BRIDGE / 4 ANOMALY / 5 NO_REF（未学习）。
from xunji.protocol import (
    MATRIX_PAYLOAD_TAIL,
    CLASS_PASS,
    CLASS_NO_REF,
    build_frame,
    matrix_payload,
    parse_matrix_payload,
)


def test_payload长度随通道数():
    assert MATRIX_PAYLOAD_TAIL == 6
    assert len(matrix_payload(0x2804, 4, 0, 0, CLASS_PASS, 0xBE)) == 4 + 6 - 2  # 2+6=8
    assert len(matrix_payload(0, 16, 0, 0, CLASS_NO_REF, 0)) == 32 + 6


def test_4路黄金帧():
    """与 uart_packet_tx.v TB 双向锁定（18 字节帧）。"""
    p = matrix_payload(0x2804, 4, 0, 0, CLASS_PASS, 0xBE)
    assert p.hex() == "04280000000000be"
    assert build_frame(1, 1, 0, p).hex() == "55aa01010800000004280000000000bee338"
    assert build_frame(1, 1, 1, p).hex() == "55aa01010800010004280000000000bea657"


def test_4路往返解析():
    p = matrix_payload(0x2804, 4, 0b0101, 0b0010, 2, 0xBE)
    got = parse_matrix_payload(p, 4)
    assert got["matrix"] == 0x2804
    assert got["open_flags"] == 0b0101
    assert got["stuck_low_mask"] == 0b0010
    assert got["cls"] == 2
    assert got["ts0"] == 0xBE


def test_16路往返解析():
    matrix = (1 << 256) - 1
    p = matrix_payload(matrix, 16, 0xFFFF, 0x8001, 4, 0x5A)
    assert len(p) == 38
    got = parse_matrix_payload(p, 16)
    assert got["matrix"] == matrix
    assert got["open_flags"] == 0xFFFF
    assert got["stuck_low_mask"] == 0x8001
    assert got["cls"] == 4
    assert got["ts0"] == 0x5A


def test_分类枚举与RTL一致():
    from xunji.protocol import (CLASS_PASS, CLASS_OPEN, CLASS_MISWIRE,
                                CLASS_BRIDGE, CLASS_ANOMALY, CLASS_NO_REF)
    assert (CLASS_PASS, CLASS_OPEN, CLASS_MISWIRE, CLASS_BRIDGE,
            CLASS_ANOMALY, CLASS_NO_REF) == (0, 1, 2, 3, 4, 5)
