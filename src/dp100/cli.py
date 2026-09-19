"""``dp100`` command-line entry point."""

from __future__ import annotations

import argparse
import json
import sys
import time
from importlib import resources
from pathlib import Path

from . import __version__
from .device import DP100, DP100Error


def fmt_info(s: dict) -> str:
    return (
        f"Vout {s['vout_v']:7.3f} V  Iout {s['iout_a']:6.3f} A  P {s['power_w']:7.3f} W  "
        f"[{s['out_mode']}]  Vin {s['vin_v']:.2f} V  T {s['temp1_c']:.1f}/{s['temp2_c']:.1f} C"
    )


def fmt_set(s: dict) -> str:
    return (
        f"output {'ON ' if s['state'] else 'OFF'}  Vset {s['vo_set_v']:.3f} V  Iset {s['io_set_a']:.3f} A  "
        f"OVP {s['ovp_v']:.2f} V  OCP {s['ocp_a']:.2f} A  (preset {s['index']})"
    )


def _sleep_until(t: float) -> None:
    # Split sleep + final spin: time.sleep() overshoots badly on some macOS setups.
    while (rem := t - time.monotonic()) > 0:
        time.sleep(rem / 2 if rem > 0.004 else 0)


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="dp100", description="ALIENTEK DP100 power supply CLI")
    ap.add_argument("--version", action="version", version=f"dp100-cli {__version__}")
    ap.add_argument("--json", action="store_true", help="machine-readable JSON output")
    ap.add_argument("--timeout", type=int, default=300, help="per-request timeout in ms (default 300)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("info", help="live Vout / Iout / power / temperature")
    sub.add_parser("get", help="current setpoints")

    p = sub.add_parser("set", help="change setpoints (only the fields given)")
    p.add_argument("--v", type=float, help="output voltage, V")
    p.add_argument("--i", type=float, help="current limit, A")
    p.add_argument("--ovp", type=float, help="over-voltage protection, V")
    p.add_argument("--ocp", type=float, help="over-current protection, A")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--on", action="store_true", help="also enable the output")
    g.add_argument("--off", action="store_true", help="also disable the output")

    sub.add_parser("on", help="enable the output")
    sub.add_parser("off", help="disable the output")

    w = sub.add_parser("watch", help="sample continuously")
    w.add_argument("--hz", type=float, default=5, help="sample rate (default 5)")
    w.add_argument("--seconds", type=float, default=0, help="stop after N s (0 = until Ctrl-C)")
    w.add_argument("--csv", action="store_true", help="CSV: t_s,vout_v,iout_a,power_w,mode")

    k = sub.add_parser("skill", help="Claude Code skill: print or install SKILL.md")
    k.add_argument("action", choices=["show", "install"], nargs="?", default="show")
    k.add_argument("--global", dest="user_wide", action="store_true",
                   help="install to ~/.claude/skills (default: ./.claude/skills of the current project)")
    k.add_argument("--force", action="store_true", help="overwrite an existing SKILL.md")

    r = sub.add_parser("raw", help="send a raw function code, print the reply")
    r.add_argument("func", type=lambda x: int(x, 16), help="function code, hex (30 / 35)")
    r.add_argument("data", nargs="?", default="", help="payload, hex")
    return ap


def skill_text() -> str:
    return resources.files("dp100").joinpath("skill/SKILL.md").read_text(encoding="utf-8")


def skill_cmd(a) -> int:
    if a.action == "show":
        print(skill_text(), end="")
        return 0
    base = Path.home() / ".claude" if a.user_wide else Path.cwd() / ".claude"
    dst = base / "skills" / "dp100" / "SKILL.md"
    if dst.exists() and not a.force:
        print(f"dp100: {dst} exists (use --force to overwrite)", file=sys.stderr)
        return 1
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(skill_text(), encoding="utf-8")
    print(f"installed {dst}")
    return 0


def main(argv=None) -> int:
    ap = build_parser()
    a = ap.parse_args(argv)
    if a.cmd == "skill":
        return skill_cmd(a)

    def out(d: dict, f) -> None:
        print(json.dumps(d) if a.json else f(d))

    try:
        with DP100(timeout_ms=a.timeout) as dev:
            if a.cmd == "info":
                out(dev.info(), fmt_info)
            elif a.cmd == "get":
                out(dev.get_set(), fmt_set)
            elif a.cmd == "set":
                state = 1 if a.on else 0 if a.off else None
                out(dev.apply(state=state, v=a.v, i=a.i, ovp=a.ovp, ocp=a.ocp), fmt_set)
            elif a.cmd in ("on", "off"):
                out(dev.output(a.cmd == "on"), fmt_set)
            elif a.cmd == "watch":
                period = 1.0 / a.hz
                output_on = dev.read_set().output_on
                t0 = time.monotonic()
                if a.csv:
                    print("t_s,vout_v,iout_a,power_w,mode")
                try:
                    while True:
                        t = time.monotonic() - t0
                        s = dev.read_info().as_dict(output_on)
                        if a.csv:
                            print(f"{t:.3f},{s['vout_v']:.3f},{s['iout_a']:.3f},{s['power_w']:.3f},{s['out_mode']}")
                        else:
                            print(f"{t:7.2f}s  {fmt_info(s)}")
                        sys.stdout.flush()
                        if a.seconds and t >= a.seconds:
                            break
                        _sleep_until(t0 + t + period)
                except KeyboardInterrupt:
                    pass
            elif a.cmd == "raw":
                fr = dev.transact(a.func, bytes.fromhex(a.data))
                print(
                    f"addr=0x{fr.addr:02x} func=0x{fr.func:02x} seq={fr.seq} "
                    f"data[{len(fr.data)}]={fr.data.hex()}"
                )
    except (DP100Error, ValueError) as e:
        print(f"dp100: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
