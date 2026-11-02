# UART 二进制协议测试 — 规格冻结自 V1.9 §17：
# SOF 55 AA(2B) + Version(1B) + Type(1B) + Length(2B) + Sequence(2B) + Payload + CRC(2B)
# 除 SOF 外多字节小端；CRC-16/CCITT-FALSE: poly=0x1021, init=0xFFFF, refin/refout=false, xorout=0
import pytest

from xunji.protocol import (
    SOF,
    build_frame,
    crc16_ccitt_false,
    parse_frame,
)


class TestCrc16CcittFalse:
    def test_公开校验值_123456789(self):
        # CRC-16/CCITT-FALSE 的公开 check value：ASCII "123456789" -> 0x29B1
        assert crc16_ccitt_false(b"123456789") == 0x29B1

    def test_空输入等于初始值(self):
        # 无数据时 CRC 保持 init=0xFFFF
        assert crc16_ccitt_false(b"") == 0xFFFF


class TestBuildFrame:
    def test_帧头与字段布局(self):
        frame = build_frame(version=1, frame_type=2, sequence=3, payload=b"\x01\x02")
        assert frame[:2] == SOF == b"\x55\xaa"
        assert frame[2] == 1  # Version
        assert frame[3] == 2  # Type
        assert int.from_bytes(frame[4:6], "little") == 2  # Length = payload 长度
        assert int.from_bytes(frame[6:8], "little") == 3  # Sequence
        assert frame[8:10] == b"\x01\x02"  # Payload

    def test_crc覆盖_从version到payload_小端存放(self):
        frame = build_frame(1, 2, 3, b"\x01\x02")
        expected_crc = crc16_ccitt_false(frame[2:-2])
        assert int.from_bytes(frame[-2:], "little") == expected_crc

    def test_空payload合法(self):
        frame = build_frame(1, 2, 0, b"")
        version, ftype, seq, payload = parse_frame(frame)
        assert payload == b""

    def test_payload超过65535字节拒绝(self):
        with pytest.raises(ValueError):
            build_frame(1, 2, 0, b"\x00" * 65536)


class TestParseFrame:
    def test_往返一致(self):
        payload = bytes(range(64))
        frame = build_frame(7, 0x10, 0x1234, payload)
        assert parse_frame(frame) == (7, 0x10, 0x1234, payload)

    def test_SOF错误拒绝(self):
        frame = bytearray(build_frame(1, 2, 3, b"x"))
        frame[0] = 0x54
        with pytest.raises(ValueError):
            parse_frame(bytes(frame))

    def test_CRC损坏拒绝(self):
        frame = bytearray(build_frame(1, 2, 3, b"hello"))
        frame[-1] ^= 0xFF
        with pytest.raises(ValueError):
            parse_frame(bytes(frame))

    def test_负载截断拒绝(self):
        frame = bytearray(build_frame(1, 2, 3, b"hello"))
        del frame[9]  # payload 去掉一个字节但 Length 字段不变
        with pytest.raises(ValueError):
            parse_frame(bytes(frame))

    def test_帧过短拒绝(self):
        with pytest.raises(ValueError):
            parse_frame(b"\x55\xaa\x01")
