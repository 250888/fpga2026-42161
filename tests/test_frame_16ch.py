# 16 路拓扑帧黄金向量（2026-10-24 审查 B1/W11 补齐）
#
# 背景：2026-10-22 的 16 路扩展只在 Python 侧测过 payload 构造，线级 TB 只到 4 路。
# 本文件把 48B 帧的两个关键形态锁死，并与 sim/tb_uart_packet_tx16.v 的 384'h
# 黄金帧双向对齐（DUT 发的、Python 造的必须逐字节相同）。
#
# 矩阵取 1:1 双射（A_i ↔ B_i），byte k = matrix[8k+7:8k] 行 major：
#   行 0-7  -> 01 00 02 00 04 00 08 00 10 00 20 00 40 00 80 00
#   行 8-15 -> 00 01 00 02 00 04 00 08 00 10 00 20 00 40 00 80
from __future__ import annotations

from xunji import protocol as P

N_CH = 16

# 上电未学习：cls = NO_REF(5)
GOLDEN_NO_REF = (
    "55aa010126000000"
    "01000200040008001000200040008000"
    "00010002000400080010002000400080"
    "0000000005000a02"
)
# 学习后参考一致：cls = PASS(0)
GOLDEN_PASS = (
    "55aa010126000000"
    "01000200040008001000200040008000"
    "00010002000400080010002000400080"
    "000000000000fffd"
)


def _identity() -> int:
    """1:1 双射矩阵：bit(i*16+i)。"""
    m = 0
    for i in range(N_CH):
        m |= 1 << (i * N_CH + i)
    return m


def test_identity_matrix_layout() -> None:
    """行 major、byte k = matrix[8k+7:8k]。"""
    m = _identity()
    raw = m.to_bytes(N_CH * N_CH // 8, "little")
    assert raw.hex() == (
        "01000200040008001000200040008000"
        "00010002000400080010002000400080"
    )


def test_16ch_no_ref_frame() -> None:
    """上电未学习：cls=5、Len=38、整帧 48B。"""
    frame = P.build_frame(1, 1, 0, P.matrix_payload(_identity(), N_CH, 0, 0,
                                                   P.CLASS_NO_REF, 0))
    assert len(frame) == 48
    assert frame.hex() == GOLDEN_NO_REF


def test_16ch_pass_frame() -> None:
    """学习后参考一致：cls=0。"""
    frame = P.build_frame(1, 1, 0, P.matrix_payload(_identity(), N_CH, 0, 0,
                                                   P.CLASS_PASS, 0))
    assert len(frame) == 48
    assert frame.hex() == GOLDEN_PASS


def test_16ch_roundtrip() -> None:
    """造帧 → parse_frame → parse_matrix_payload 应回到原矩阵。"""
    m = _identity()
    payload = P.matrix_payload(m, N_CH, 0x0003, 0x0000, P.CLASS_OPEN, 0x5A)
    assert len(payload) == 38
    ver, ftype, seq, pl = P.parse_frame(
        P.build_frame(1, 1, 7, payload))
    assert (ver, ftype, seq) == (1, 1, 7)
    d = P.parse_matrix_payload(pl, N_CH)
    assert d["matrix"] == m
    assert d["open_flags"] == 0x0003
    assert d["cls"] == P.CLASS_OPEN
    assert d["ts0"] == 0x5A


def test_16ch_pairs_from_matrix() -> None:
    """矩阵 -> (A_i, B_j) 连接对，语义：i=A 行、j=B 列、bit=1=导通。"""
    m = _identity()
    pairs = [(a, b) for a in range(N_CH) for b in range(N_CH)
             if (m >> (a * N_CH + b)) & 1]
    assert len(pairs) == 16
    assert pairs[0] == (0, 0) and pairs[-1] == (15, 15)
