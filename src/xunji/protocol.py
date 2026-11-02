# UART 二进制帧协议 — 冻结自 V1.9 §17（不可无依据变更）。
#
# 帧布局：SOF(55 AA) | Version(1) | Type(1) | Length(2,LE) | Sequence(2,LE) | Payload | CRC(2,LE)
# 除 SOF 外多字节数值一律小端；CRC 覆盖 Version..Payload（不含 SOF 与 CRC 自身）。
# CRC-16/CCITT-FALSE：poly=0x1021, init=0xFFFF, refin=false, refout=false, xorout=0x0000。
from __future__ import annotations

SOF = b"\x55\xaa"

# 帧类型：§17 只固定格式、未枚举 Type 表；Type=1 定为拓扑矩阵帧
# （决策记录：doc/superpowers/plans/2026-10-11-uart-frame-v19.md）
TYPE_MATRIX = 0x01

# 拓扑矩阵帧 payload（2026-10-22 扩展，决策记录
# doc/superpowers/specs/2026-10-22-topology-frame-16ch.md）：
#   MAT[N*N/8] + open(2,LE) + stuck(2,LE) + cls(1) + ts0(1)
#   byte k = matrix[8k+7 : 8k]（行 major，row0 的 b0..b7 在 byte0）；
#   cls: 0 PASS / 1 OPEN / 2 MISWIRE / 3 BRIDGE / 4 ANOMALY / 5 NO_REF（未学习）。
MATRIX_PAYLOAD_TAIL = 6
CLASS_PASS = 0
CLASS_OPEN = 1
CLASS_MISWIRE = 2
CLASS_BRIDGE = 3
CLASS_ANOMALY = 4
CLASS_NO_REF = 5


def matrix_bytes(n_ch: int) -> int:
    """N_CH×N_CH 矩阵的行优先字节数（4 路 2B、16 路 32B）。"""
    if n_ch not in (4, 16):
        raise ValueError(f"只支持 N_CH=4/16，收到 {n_ch}")
    return n_ch * n_ch // 8


def matrix_payload(matrix: int, n_ch: int, open_flags: int, stuck_low_mask: int,
                   cls: int, ts0: int) -> bytes:
    """构造拓扑矩阵帧 payload（长度 = N*N/8 + 6）。"""
    nbytes = matrix_bytes(n_ch)
    if not 0 <= matrix < (1 << (n_ch * n_ch)):
        raise ValueError(f"矩阵超出 {n_ch}×{n_ch} 位宽")
    return (
        matrix.to_bytes(nbytes, "little")
        + (open_flags & 0xFFFF).to_bytes(2, "little")
        + (stuck_low_mask & 0xFFFF).to_bytes(2, "little")
        + bytes((cls & 0xFF, ts0 & 0xFF))
    )


def parse_matrix_payload(payload: bytes, n_ch: int) -> dict[str, int]:
    """解析拓扑矩阵帧 payload；长度不符直接拒绝。"""
    nbytes = matrix_bytes(n_ch)
    if len(payload) != nbytes + MATRIX_PAYLOAD_TAIL:
        raise ValueError(
            f"payload 长度 {len(payload)} != {nbytes + MATRIX_PAYLOAD_TAIL}")
    matrix = int.from_bytes(payload[:nbytes], "little")
    tail = payload[nbytes:]
    return {
        "matrix": matrix,
        "open_flags": int.from_bytes(tail[0:2], "little"),
        "stuck_low_mask": int.from_bytes(tail[2:4], "little"),
        "cls": tail[4],
        "ts0": tail[5],
    }

# CRC-16/CCITT-FALSE 参数（与 RTL 端 uart_packet/上位机必须一致）
_CRC_POLY = 0x1021
_CRC_INIT = 0xFFFF
_MAX_PAYLOAD = 65535
_MIN_FRAME = 2 + 1 + 1 + 2 + 2 + 0 + 2  # SOF..CRC 最短帧


def crc16_ccitt_false(data: bytes) -> int:
    """按 V1.9 冻结参数计算 CRC-16/CCITT-FALSE。"""
    crc = _CRC_INIT
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ _CRC_POLY) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc


def build_frame(version: int, frame_type: int, sequence: int, payload: bytes) -> bytes:
    """构造完整帧。Length 字段承载 payload 长度，单帧 payload 上限 65535 B（V1.9 §17）。"""
    if len(payload) > _MAX_PAYLOAD:
        raise ValueError(f"payload 超过 {_MAX_PAYLOAD} 字节，必须分块")
    body = (
        bytes((version, frame_type))
        + len(payload).to_bytes(2, "little")
        + sequence.to_bytes(2, "little")
        + payload
    )
    crc = crc16_ccitt_false(body).to_bytes(2, "little")
    return SOF + body + crc


def parse_frame(frame: bytes) -> tuple[int, int, int, bytes]:
    """解析单帧，返回 (version, type, sequence, payload)；SOF/CRC/长度任一不符即拒绝。"""
    if len(frame) < _MIN_FRAME:
        raise ValueError(f"帧过短：{len(frame)} 字节")
    if frame[:2] != SOF:
        raise ValueError("SOF 错误，期望 55 AA")
    body = frame[2:-2]
    expected_crc = crc16_ccitt_false(body)
    actual_crc = int.from_bytes(frame[-2:], "little")
    if actual_crc != expected_crc:
        raise ValueError(f"CRC 错误：期望 {expected_crc:#06x}，实际 {actual_crc:#06x}")
    length = int.from_bytes(frame[4:6], "little")
    if len(body[6:]) != length:
        raise ValueError(f"Length 字段 {length} 与实际 payload {len(body[6:])} 不符")
    version, frame_type = body[0], body[1]
    sequence = int.from_bytes(body[4:6], "little")
    return version, frame_type, sequence, body[6:]
