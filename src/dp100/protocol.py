"""Pure-Python DP100 frame protocol. No hardware access here — fully unit-testable.

Frame layout (both directions)::

    +------+------+-----+----------+-----------+--------+--------+
    | addr | func | seq | data_len | data ...  | crc_lo | crc_hi |
    +------+------+-----+----------+-----------+--------+--------+

* ``addr``  0xFB host -> device, 0xFA device -> host
* ``func``  0x30 BASIC_INFO (live readings), 0x35 BASIC_SET (setpoints)
* ``crc``   CRC-16/MODBUS over ``addr .. data``, little-endian
* transported as a 64-byte USB HID report (no report id)

See ``docs/PROTOCOL.md`` for the field tables.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import NamedTuple

VID = 0x2E3C
PID = 0xAF01

ADDR_TX = 0xFB
ADDR_RX = 0xFA
FUNC_INFO = 0x30
FUNC_SET = 0x35
REPORT_LEN = 64

OUT_MODE_NAMES = {0: "CC", 1: "CV", 2: "PROT"}


def crc16_modbus(data: bytes) -> int:
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc


def build_frame(func: int, data: bytes = b"", seq: int = 0) -> bytes:
    """Host -> device frame, without HID padding."""
    if len(data) > 255:
        raise ValueError("data too long")
    head = bytes([ADDR_TX, func & 0xFF, seq & 0xFF, len(data)]) + data
    return head + struct.pack("<H", crc16_modbus(head))


class Frame(NamedTuple):
    addr: int
    func: int
    seq: int
    data: bytes


def parse_frame(buf: bytes) -> Frame | None:
    """Parse a received report. Returns None on garbage or CRC mismatch.

    Tolerates a leading 0x00 report-id byte that some HID stacks prepend.
    """
    buf = bytes(buf)
    if len(buf) >= 7 and buf[0] == 0 and buf[1] in (ADDR_TX, ADDR_RX):
        buf = buf[1:]
    if len(buf) < 6 or buf[0] not in (ADDR_TX, ADDR_RX):
        return None
    n = buf[3]
    if len(buf) < 6 + n:
        return None
    rx_crc = struct.unpack_from("<H", buf, 4 + n)[0]
    if rx_crc != crc16_modbus(buf[: 4 + n]):
        return None
    return Frame(buf[0], buf[1], buf[2], buf[4 : 4 + n])


@dataclass(frozen=True)
class BasicInfo:
    """Decoded BASIC_INFO (0x30) reply."""

    vin_v: float
    vout_v: float
    iout_a: float
    vo_max_v: float
    temp1_c: float
    temp2_c: float
    dc5v_v: float
    out_mode_raw: int
    work_st: int

    @property
    def power_w(self) -> float:
        return self.vout_v * self.iout_a

    def out_mode(self, output_on: bool | None = None) -> str:
        """Mode string. When the output is known to be off the chip still reports 2 (PROT);
        pass ``output_on=False`` to get ``"OFF"`` instead."""
        if output_on is False:
            return "OFF"
        return OUT_MODE_NAMES.get(self.out_mode_raw, str(self.out_mode_raw))

    def as_dict(self, output_on: bool | None = None) -> dict:
        d = self.__dict__.copy()
        d["power_w"] = self.power_w
        d["out_mode"] = self.out_mode(output_on)
        if output_on is not None:
            d["output_on"] = int(output_on)
        return d

    @classmethod
    def decode(cls, data: bytes) -> BasicInfo:
        if len(data) < 16:
            raise ValueError(f"BASIC_INFO payload too short ({len(data)} B): {data.hex()}")
        vin, vout, iout, vo_max, t1, t2, dc5v = struct.unpack_from("<7H", data)
        return cls(vin / 1000, vout / 1000, iout / 1000, vo_max / 1000,
                   t1 / 10, t2 / 10, dc5v / 1000, data[14], data[15])


@dataclass(frozen=True)
class BasicSet:
    """Decoded BASIC_SET (0x35) reply / encoded write request."""

    index: int
    state: int
    vo_set_v: float
    io_set_a: float
    ovp_v: float
    ocp_a: float

    @property
    def output_on(self) -> bool:
        return self.state != 0

    def as_dict(self) -> dict:
        return self.__dict__.copy()

    @classmethod
    def decode(cls, data: bytes) -> BasicSet:
        if len(data) < 10:
            raise ValueError(f"BASIC_SET payload too short ({len(data)} B): {data.hex()}")
        vo, io, ovp, ocp = struct.unpack_from("<4H", data, 2)
        return cls(data[0], data[1], vo / 1000, io / 1000, ovp / 1000, ocp / 1000)

    def encode(self) -> bytes:
        """Payload for a BASIC_SET write (``index | 0x20`` marks it as a write)."""
        return bytes([(self.index & 0x1F) | 0x20, 1 if self.state else 0]) + struct.pack(
            "<4H",
            round(self.vo_set_v * 1000),
            round(self.io_set_a * 1000),
            round(self.ovp_v * 1000),
            round(self.ocp_a * 1000),
        )


BASIC_SET_READ_PAYLOAD = b"\x80"
BASIC_SET_WRITE_ACK = b"\x01"
