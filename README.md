# dp100-cli

Command-line tool and Python library for the **ALIENTEK DP100** (ATK-MDP100) USB
digital power supply. Read live voltage / current / temperature, change setpoints,
switch the output, and log samples to CSV — from a terminal or a script.

```
$ dp100 info
Vout  11.997 V  Iout  0.354 A  P   4.247 W  [CV]  Vin 32.22 V  T 38.2/38.7 C
$ dp100 get
output ON   Vset 12.000 V  Iset 5.000 A  OVP 30.50 V  OCP 5.05 A  (preset 0)
```

Talks to the device directly over USB HID (via [hidapi](https://github.com/libusb/hidapi));
no vendor software or driver required.

## Install

```bash
pipx install dp100-cli        # recommended: isolated, gives you the `dp100` command
# or
pip install dp100-cli
```

Requires Python 3.9+. `hidapi` ships binary wheels for CPython 3.9–3.13; on a
brand-new interpreter without a wheel, point pipx at an older one, e.g.
`pipx install --python python3.12 dp100-cli`. On **Linux** add a udev rule so you can open the device
without root (see [`contrib/99-dp100.rules`](contrib/99-dp100.rules)):

```bash
sudo cp contrib/99-dp100.rules /etc/udev/rules.d/ && sudo udevadm control --reload-rules
```

## Usage

```bash
dp100 info                      # live readings
dp100 get                       # current setpoints
dp100 set --v 12 --i 2.5        # change only the fields you pass (read-merge-write)
dp100 set --ovp 15 --ocp 3      # protection thresholds
dp100 set --v 7.4 --on          # set and enable in one go
dp100 on                        # enable output
dp100 off                       # disable output
dp100 watch --hz 10             # sample continuously, Ctrl-C to stop
dp100 watch --hz 10 --csv --seconds 30 > log.csv
dp100 --json info               # every command can emit JSON
dp100 raw 35 80                 # send a raw function code, print the reply
```

`set` refuses a voltage above OVP or a current above OCP instead of tripping the
supply's protection. While the output is off the unit reports mode `PROT`; the CLI
shows `OFF` in that case.

## As a library

```python
from dp100 import DP100

with DP100() as psu:
    print(psu.info())                       # dict of live readings
    psu.apply(v=7.4, i=2.0)                 # change setpoints, output state untouched
    psu.output(True)
    print(psu.read_info().power_w)
```

`dp100.protocol` (frame building/parsing, CRC, payload dataclasses) has no hardware
dependency and can be reused in other transports.

## Protocol

Documented in [`docs/PROTOCOL.md`](docs/PROTOCOL.md): 64-byte HID reports,
`[addr, func, seq, len, data…, CRC-16/MODBUS]`, function `0x30` for live readings and
`0x35` to read/write setpoints.

## Claude Code skill

The repo ships a [Claude Code](https://claude.com/claude-code) skill at
[`.claude/skills/dp100/SKILL.md`](.claude/skills/dp100/SKILL.md): open the repo in
Claude Code and it knows the commands, the safety rules (never enables the output
unless asked) and the troubleshooting steps. Copy the folder into any other project's
`.claude/skills/` to use it there.

## Platform notes

* Verified on macOS 15 (Apple Silicon) with a real unit.
* Linux and Windows use the same hidapi code path but have not been exercised on
  hardware yet — reports welcome.
* The DP100 USB-A port does not supply 5 V while the unit is in USB device mode;
  this tool only uses the USB-C data connection.

## Development

```bash
git clone https://github.com/AndySze/dp100-cli && cd dp100-cli
python -m venv .venv && .venv/bin/pip install -e '.[dev]'
.venv/bin/pytest            # protocol + CLI tests run without hardware
.venv/bin/ruff check .
```

## Credits

The frame format and function codes were learned by reading the ESP32 host
implementation in [DP100_ESP32_WebApp](https://github.com/BrokenClient/DP100_ESP32_WebApp)
(GPL-3.0), which in turn builds on [DP100-WebApp](https://github.com/codingjoe/DP100-WebApp).
This project is an independent, from-scratch Python implementation of that wire
protocol; no code from either project is included, so it is offered under MIT.

## License

MIT — see [LICENSE](LICENSE).
