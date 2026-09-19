"""CLI tests against a fake device (no hardware)."""

import json

import pytest

from dp100 import cli
from dp100.device import DP100
from dp100.protocol import BasicInfo, BasicSet


class FakeDP100:
    def __init__(self, *_, **__):
        self.set = BasicSet(0, 0, 12.0, 5.0, 30.5, 5.05)
        self.written = []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass

    def read_info(self):
        return BasicInfo(32.0, 12.0 if self.set.state else 0.0, 0.3 if self.set.state else 0.0,
                         30.0, 38.0, 38.3, 5.05, 1 if self.set.state else 2, 0)

    def read_set(self):
        return self.set

    def write_set(self, s):
        self.written.append(s)
        self.set = s

    def info(self, with_state=True):
        return self.read_info().as_dict(self.set.output_on if with_state else None)

    def get_set(self):
        return self.set.as_dict()

    # reuse the real read-merge-write logic against the fake transport
    apply = DP100.apply
    output = DP100.output


@pytest.fixture
def fake(monkeypatch):
    inst = FakeDP100()
    monkeypatch.setattr(cli, "DP100", lambda *a, **k: inst)
    return inst


def test_info_off_shows_off(fake, capsys):
    assert cli.main(["--json", "info"]) == 0
    d = json.loads(capsys.readouterr().out)
    assert d["out_mode"] == "OFF" and d["output_on"] == 0


def test_set_merges_and_writes(fake, capsys):
    assert cli.main(["--json", "set", "--v", "7.4"]) == 0
    d = json.loads(capsys.readouterr().out)
    assert d["vo_set_v"] == 7.4 and d["io_set_a"] == 5.0 and d["state"] == 0
    assert len(fake.written) == 1


def test_set_rejects_over_ovp(fake, capsys):
    assert cli.main(["set", "--v", "31"]) == 1
    assert "exceeds OVP" in capsys.readouterr().err
    assert fake.written == []


def test_on_then_info_cv(fake, capsys):
    assert cli.main(["on"]) == 0
    assert cli.main(["--json", "info"]) == 0
    out = capsys.readouterr().out.strip().splitlines()[-1]
    assert json.loads(out)["out_mode"] == "CV"
