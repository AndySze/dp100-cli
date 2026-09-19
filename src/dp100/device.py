"""hidapi transport + high-level DP100 API."""

from __future__ import annotations

import sys
import time

from .protocol import (
    BASIC_SET_READ_PAYLOAD,
    BASIC_SET_WRITE_ACK,
    FUNC_INFO,
    FUNC_SET,
    PID,
    REPORT_LEN,
    VID,
    BasicInfo,
    BasicSet,
    Frame,
    build_frame,
    parse_frame,
)


class DP100Error(RuntimeError):
    pass


class DP100NotFound(DP100Error):
    pass


class DP100Timeout(DP100Error):
    pass


def enumerate_devices() -> list:
    import hid

    return hid.enumerate(VID, PID)


class DP100:
    """One open DP100. Use as a context manager or call ``close()``.

    Every call is a request/response transaction; the device does not stream.
    """

    def __init__(self, path: bytes | None = None, timeout_ms: int = 300, retries: int = 3):
        import hid  # imported lazily so the protocol module stays importable without hidapi

        if path is None:
            devs = enumerate_devices()
            if not devs:
                raise DP100NotFound(
                    f"no DP100 found (VID 0x{VID:04X} / PID 0x{PID:04X}); "
                    "check the USB cable and that the unit is on"
                )
            path = devs[0]["path"]
        self._dev = hid.device()
        self._dev.open_path(path)
        self.timeout_ms = timeout_ms
        self.retries = retries

    # ---- lifecycle ----
    def close(self) -> None:
        self._dev.close()

    def __enter__(self) -> DP100:
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # ---- transport ----
    def transact(self, func: int, data: bytes = b"") -> Frame:
        frame = build_frame(func, data)
        report = frame.ljust(REPORT_LEN, b"\x00")
        if sys.platform != "linux":
            # macOS / Windows hidapi expect a leading report-id byte (0x00 = none).
            report = b"\x00" + report
        for _ in range(self.retries):
            self._dev.write(report)
            deadline = time.monotonic() + self.timeout_ms / 1000
            while time.monotonic() < deadline:
                rx = self._dev.read(REPORT_LEN, timeout_ms=self.timeout_ms)
                if not rx:
                    break
                parsed = parse_frame(bytes(rx))
                if parsed and parsed.func == func:
                    return parsed
        raise DP100Timeout(f"no reply to function 0x{func:02x}")

    # ---- high level ----
    def read_info(self) -> BasicInfo:
        return BasicInfo.decode(self.transact(FUNC_INFO).data)

    def read_set(self) -> BasicSet:
        return BasicSet.decode(self.transact(FUNC_SET, BASIC_SET_READ_PAYLOAD).data)

    def write_set(self, s: BasicSet) -> None:
        ack = self.transact(FUNC_SET, s.encode()).data
        if ack != BASIC_SET_WRITE_ACK:
            raise DP100Error(f"write not acknowledged: {ack.hex()}")
        time.sleep(0.1)  # device needs ~100 ms before the new setpoint reads back

    def info(self, with_state: bool = True) -> dict:
        """Live readings as a dict. ``with_state`` also reads the setpoints so that
        ``out_mode`` reports ``OFF`` while the output is disabled."""
        on = self.read_set().output_on if with_state else None
        return self.read_info().as_dict(on)

    def get_set(self) -> dict:
        return self.read_set().as_dict()

    def apply(
        self,
        state: int | None = None,
        v: float | None = None,
        i: float | None = None,
        ovp: float | None = None,
        ocp: float | None = None,
    ) -> dict:
        """Read-merge-write: only the fields given are changed.

        Refuses a voltage above OVP or a current above OCP (the device would
        otherwise trip protection immediately).
        """
        cur = self.read_set()
        new = BasicSet(
            index=cur.index,
            state=cur.state if state is None else int(bool(state)),
            vo_set_v=cur.vo_set_v if v is None else v,
            io_set_a=cur.io_set_a if i is None else i,
            ovp_v=cur.ovp_v if ovp is None else ovp,
            ocp_a=cur.ocp_a if ocp is None else ocp,
        )
        if new.vo_set_v > new.ovp_v:
            raise ValueError(f"voltage setpoint {new.vo_set_v} V exceeds OVP {new.ovp_v} V")
        if new.io_set_a > new.ocp_a:
            raise ValueError(f"current setpoint {new.io_set_a} A exceeds OCP {new.ocp_a} A")
        self.write_set(new)
        return self.read_set().as_dict()

    def output(self, on: bool) -> dict:
        return self.apply(state=1 if on else 0)
