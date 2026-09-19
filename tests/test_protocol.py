"""Protocol round-trip tests using replies captured from a real DP100 (no hardware needed)."""

from dp100.protocol import (
    ADDR_RX,
    FUNC_INFO,
    FUNC_SET,
    BasicInfo,
    BasicSet,
    build_frame,
    crc16_modbus,
    parse_frame,
)

# Captured 2026-09-19 from an ATK-MDP100 (output off, Vset 12 V, Iset 5 A, OVP 30.5 V, OCP 5.05 A)
INFO_PAYLOAD = bytes.fromhex("027e0000000030757c017f01b7130200")
SET_PAYLOAD = bytes.fromhex("0000e02e88132477ba13")


def frame_from_device(func: int, payload: bytes) -> bytes:
    head = bytes([ADDR_RX, func, 0, len(payload)]) + payload
    return head + crc16_modbus(head).to_bytes(2, "little")


def test_crc16_modbus_known_vector():
    # Standard MODBUS check value for "123456789"
    assert crc16_modbus(b"123456789") == 0x4B37


def test_build_frame_layout():
    f = build_frame(FUNC_SET, b"\x80")
    assert f[:4] == bytes([0xFB, 0x35, 0x00, 0x01])
    assert f[4] == 0x80
    assert len(f) == 7
    assert parse_frame(f).data == b"\x80"


def test_parse_rejects_bad_crc():
    f = bytearray(build_frame(FUNC_INFO))
    f[-1] ^= 0xFF
    assert parse_frame(bytes(f)) is None


def test_parse_tolerates_report_id_prefix():
    raw = frame_from_device(FUNC_INFO, INFO_PAYLOAD)
    assert parse_frame(b"\x00" + raw) == parse_frame(raw)


def test_parse_rejects_garbage():
    assert parse_frame(b"") is None
    assert parse_frame(b"\x00" * 64) is None
    assert parse_frame(b"\x12\x34\x56") is None


def test_decode_basic_info_captured():
    fr = parse_frame(frame_from_device(FUNC_INFO, INFO_PAYLOAD).ljust(64, b"\x00"))
    info = BasicInfo.decode(fr.data)
    assert info.vin_v == 32.258
    assert info.vout_v == 0.0
    assert info.iout_a == 0.0
    assert info.vo_max_v == 30.0
    assert info.temp1_c == 38.0
    assert info.temp2_c == 38.3
    assert info.dc5v_v == 5.047
    assert info.out_mode_raw == 2
    assert info.out_mode() == "PROT"
    assert info.out_mode(output_on=False) == "OFF"
    assert info.power_w == 0.0


def test_decode_basic_set_captured():
    fr = parse_frame(frame_from_device(FUNC_SET, SET_PAYLOAD))
    s = BasicSet.decode(fr.data)
    assert (s.index, s.state) == (0, 0)
    assert s.vo_set_v == 12.0
    assert s.io_set_a == 5.0
    assert s.ovp_v == 30.5
    assert s.ocp_a == 5.05
    assert not s.output_on


def test_basic_set_encode_roundtrip():
    s = BasicSet(index=0, state=1, vo_set_v=7.4, io_set_a=2.5, ovp_v=15.0, ocp_a=3.0)
    enc = s.encode()
    assert enc[0] == 0x20  # index 0 | write flag
    assert enc[1] == 1
    back = BasicSet.decode(bytes([0, 1]) + enc[2:])
    assert back == BasicSet(0, 1, 7.4, 2.5, 15.0, 3.0)
