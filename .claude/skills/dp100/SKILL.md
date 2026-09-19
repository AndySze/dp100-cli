---
name: dp100
description: Control an ALIENTEK DP100 (ATK-MDP100) USB bench power supply with the `dp100` CLI or the `dp100` Python library — read live voltage/current/power/temperature, read or change setpoints, enable/disable the output, log samples to CSV. Use whenever the user mentions DP100, a bench/lab power supply, powering a device under test, measuring current draw, or switching the supply output.
---

# DP100 power supply

`dp100` talks to the supply directly over USB HID (hidapi); no vendor app needed.
Install with `pipx install dp100-cli` (or `pipx install --python python3.12 dp100-cli`
if the default interpreter has no hidapi wheel yet). Protocol details: `docs/PROTOCOL.md`.

## Commands

```bash
dp100 info                      # live Vout / Iout / P / mode / Vin / temperature
dp100 get                       # setpoints: output on/off, Vset, Iset, OVP, OCP
dp100 set --v 12 --i 2.5        # change only the fields given (read-merge-write)
dp100 set --ovp 15 --ocp 3      # protection thresholds
dp100 set --v 7.4 --on          # set and enable in one go
dp100 on                        # enable output
dp100 off                       # disable output
dp100 watch --hz 10             # sample continuously, Ctrl-C to stop
dp100 watch --hz 10 --csv --seconds 30 > log.csv   # columns: t_s,vout_v,iout_a,power_w,mode
dp100 --json info               # any command can emit JSON for scripts
dp100 raw 35 80                 # raw function code, prints the reply hex
```

Library:

```python
from dp100 import DP100
with DP100() as psu:
    psu.info()                 # dict of live readings
    psu.apply(v=7.4, i=2.0)    # setpoints only, output state untouched
    psu.output(True)
```

## Rules

1. **`on` and `set --on` energise a real load.** Only do it when the user explicitly
   asks to turn the output on. `off` is always safe.
2. **Read before you write.** Writes replace all setpoints; the CLI merges for you,
   but check `get` first so the voltage you set is below OVP (the CLI refuses
   otherwise and writes nothing).
3. **Change voltage with the output off** when the step is large: `off` → `set --v` → `on`.
4. While the output is off the chip reports mode `PROT`; the CLI shows `OFF`. That is
   not a protection trip. CC / CV / PROT only mean something with the output on.

## Troubleshooting

- `no DP100 found`: check the USB-C data cable and that the unit is powered. It is an
  HID device, not a serial port, so it never appears under `/dev/tty*`.
  macOS: `ioreg -p IOUSB -l -w0 | grep ATK-MDP100`. Linux: install
  `contrib/99-dp100.rules` so non-root users can open it.
- `no reply`: retry with `--timeout 800`; if it persists, replug the USB cable.
- `dp100: command not found`: `pipx install --python python3.12 dp100-cli`.
