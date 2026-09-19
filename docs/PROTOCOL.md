# DP100 USB HID protocol

Reverse-engineered notes for the ALIENTEK **ATK-MDP100** (DP100) digital power supply.
Verified against a real unit on macOS (hidapi) on 2026-09-19. The protocol knowledge
was originally derived from the ESP-IDF implementation in
[DP100_ESP32_WebApp](https://github.com/BrokenClient/DP100_ESP32_WebApp) (`main/dp100_usb.c`).

## USB identity

| | |
|---|---|
| VID / PID | `0x2E3C` / `0xAF01` |
| Vendor / product string | `ALIENTEK` / `ATK-MDP100` |
| Class | USB HID, 64-byte IN/OUT reports, no report id |

The device is **not** a CDC serial port; talk to it with hidapi (or raw interrupt
transfers on the HID endpoints).

## Frame

Every request and reply is one frame inside one 64-byte report (zero-padded):

| offset | size | field | notes |
|---|---|---|---|
| 0 | 1 | `addr` | `0xFB` host→device, `0xFA` device→host |
| 1 | 1 | `func` | function code |
| 2 | 1 | `seq` | sequence, echoed; `0` is fine |
| 3 | 1 | `data_len` | N |
| 4 | N | `data` | payload |
| 4+N | 2 | `crc` | CRC-16/MODBUS over bytes `0 .. 4+N-1`, **little-endian** |

CRC-16/MODBUS: init `0xFFFF`, poly `0xA001` (reflected), no final XOR.
Check value for `"123456789"` is `0x4B37`.

Some HID stacks (macOS, Windows) require a leading `0x00` report-id byte on write and
may return one on read; parsers should tolerate a leading zero.

## Function `0x30` — BASIC_INFO (live readings)

Request: `data_len = 0` (some older firmware wants a single `0x00` byte instead).

Reply payload, 16 bytes, little-endian:

| offset | type | field | unit |
|---|---|---|---|
| 0 | u16 | `vin` | mV |
| 2 | u16 | `vout` | mV |
| 4 | u16 | `iout` | mA |
| 6 | u16 | `vo_max` | mV (hardware max output) |
| 8 | u16 | `temp1` | 0.1 °C |
| 10 | u16 | `temp2` | 0.1 °C |
| 12 | u16 | `dc5v` | mV (USB 5 V rail) |
| 14 | u8 | `out_mode` | `0` CC, `1` CV, `2` PROT |
| 15 | u8 | `work_st` | |

`out_mode` reads `2` whenever the output is disabled; read BASIC_SET to know whether
the output is actually on.

Captured example (output off): `02 7e 00 00 00 00 30 75 7c 01 7f 01 b7 13 02 00`
→ Vin 32.258 V, Vout 0, Iout 0, Vo_max 30.0 V, T 38.0 / 38.3 °C, 5V rail 5.047 V.

## Function `0x35` — BASIC_SET (setpoints)

### Read

Request payload: `80`.

Reply payload, 10 bytes:

| offset | type | field | unit |
|---|---|---|---|
| 0 | u8 | `index` | preset slot |
| 1 | u8 | `state` | `0` output off, `1` on |
| 2 | u16 | `vo_set` | mV |
| 4 | u16 | `io_set` | mA |
| 6 | u16 | `ovp_set` | mV |
| 8 | u16 | `ocp_set` | mA |

Captured example: `00 00 e0 2e 88 13 24 77 ba 13`
→ preset 0, off, 12.000 V, 5.000 A, OVP 30.50 V, OCP 5.05 A.

### Write

Request payload, 10 bytes, same layout as the read reply except byte 0 is
`index | 0x20`. Reply payload is a single `01` on success.

The write replaces **all** fields, so a client that wants to change only the
voltage must read first, merge, then write. Allow ~100 ms after a write before
reading the setpoints back.
