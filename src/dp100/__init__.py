"""dp100 — control the ALIENTEK DP100 USB digital power supply.

>>> from dp100 import DP100
>>> with DP100() as psu:
...     print(psu.info()["vout_v"])
...     psu.apply(v=12.0, i=2.0, state=1)
"""

from .device import DP100, DP100Error, DP100NotFound, DP100Timeout
from .protocol import (
    FUNC_INFO,
    FUNC_SET,
    PID,
    VID,
    BasicInfo,
    BasicSet,
    build_frame,
    crc16_modbus,
    parse_frame,
)

__version__ = "0.1.0"
__all__ = [
    "DP100", "DP100Error", "DP100NotFound", "DP100Timeout",
    "BasicInfo", "BasicSet", "build_frame", "parse_frame", "crc16_modbus",
    "VID", "PID", "FUNC_INFO", "FUNC_SET", "__version__",
]
