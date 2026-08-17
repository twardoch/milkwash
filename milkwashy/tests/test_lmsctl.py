# this_file: milkwashy/tests/test_lmsctl.py
"""Residency invariant: never load a model while another is resident.

`lms` is faked here — a fake proves the state machine, not the real CLI, so a
live bounded sweep is run separately (see WORK.md).
"""

from __future__ import annotations

import json
import subprocess

import pytest

from milkwashy import lmsctl


class FakeLms:
    """Minimal `lms` stand-in tracking residency and recording the call order."""

    server_port: int | None = 1234

    def __init__(self, *, unload_broken: bool = False, all_broken: bool = False):
        self.resident: list[str] = []
        self.calls: list[list[str]] = []
        self.unload_broken = unload_broken
        self.all_broken = all_broken
        # residency observed immediately before each `load`
        self.resident_at_load: list[list[str]] = []

    def __call__(self, args, **kwargs):
        assert args[0] == "lms"
        cmd = args[1:]
        self.calls.append(cmd)
        out, rc = "", 0
        if cmd[:2] == ["ps", "--json"]:
            out = json.dumps([{"identifier": i, "type": "llm"} for i in self.resident])
        elif cmd[0] == "load":
            self.resident_at_load.append(list(self.resident))
            self.resident.append(cmd[1])
        elif cmd[0] == "unload" and cmd[1] == "--all":
            if self.all_broken:
                rc = 1
            else:
                self.resident.clear()
        elif cmd[0] == "unload":
            if self.unload_broken:
                rc = 1
            elif cmd[1] in self.resident:
                self.resident.remove(cmd[1])
        elif cmd[:2] == ["server", "status"]:
            # the real `lms` writes this to stderr
            msg = (
                f"The server is running on port {self.server_port}."
                if self.server_port is not None
                else "The server is not running."
            )
            return subprocess.CompletedProcess(args, 0, "", msg + "\n")
        elif cmd[:2] == ["server", "start"]:
            self.server_port = int(cmd[cmd.index("--port") + 1]) if "--port" in cmd else 1235
        return subprocess.CompletedProcess(args, rc, out, "")


@pytest.fixture
def fake(monkeypatch):
    f = FakeLms()
    monkeypatch.setattr(subprocess, "run", f)
    monkeypatch.setattr(lmsctl.time, "sleep", lambda _s: None)
    return f


def test_loaded_when_nothing_resident_then_empty(fake):
    assert lmsctl.loaded() == []


def test_loaded_reports_ps_identifier_field(fake):
    fake.resident = ["model-a"]
    assert lmsctl.loaded() == ["model-a"]


def test_load_exclusive_when_other_model_resident_then_unloads_first(fake):
    fake.resident = ["stale-model"]
    assert lmsctl.load_exclusive("model-b") is True
    assert fake.resident_at_load == [[]], "load must see an empty residency list"
    assert fake.resident == ["model-b"]


def test_load_exclusive_escalates_to_unload_all_when_targeted_unload_fails(monkeypatch):
    f = FakeLms(unload_broken=True)
    f.resident = ["stuck"]
    monkeypatch.setattr(subprocess, "run", f)
    monkeypatch.setattr(lmsctl.time, "sleep", lambda _s: None)
    assert lmsctl.load_exclusive("next-model") is True
    assert ["unload", "--all"] in f.calls
    assert f.resident_at_load == [[]]


def test_ensure_none_loaded_raises_when_residency_unprovable(monkeypatch):
    f = FakeLms(unload_broken=True, all_broken=True)
    f.resident = ["wedged"]
    monkeypatch.setattr(subprocess, "run", f)
    monkeypatch.setattr(lmsctl.time, "sleep", lambda _s: None)
    with pytest.raises(lmsctl.LmsResidencyError, match="wedged"):
        lmsctl.ensure_none_loaded()


def test_load_exclusive_aborts_rather_than_stacking(monkeypatch):
    """A wedged model must block the next load, not be loaded on top of."""
    f = FakeLms(unload_broken=True, all_broken=True)
    f.resident = ["wedged"]
    monkeypatch.setattr(subprocess, "run", f)
    monkeypatch.setattr(lmsctl.time, "sleep", lambda _s: None)
    with pytest.raises(lmsctl.LmsResidencyError):
        lmsctl.load_exclusive("next-model")
    assert f.resident_at_load == [], "no load may be attempted"


def test_unload_verified_leaves_nothing_resident(fake):
    lmsctl.load_exclusive("model-a")
    lmsctl.unload_verified("model-a")
    assert fake.resident == []


def test_sequential_models_never_share_residency(fake):
    for key in ("m1", "m2", "m3"):
        lmsctl.load_exclusive(key)
        lmsctl.unload_verified(key)
    assert fake.resident_at_load == [[], [], []], "each load saw an empty machine"


def test_load_failure_still_leaves_machine_clean(monkeypatch):
    f = FakeLms()

    def failing(args, **kwargs):
        if args[1] == "load":
            f.calls.append(args[1:])
            return subprocess.CompletedProcess(args, 1, "", "no model_type")
        return f(args, **kwargs)

    monkeypatch.setattr(subprocess, "run", failing)
    monkeypatch.setattr(lmsctl.time, "sleep", lambda _s: None)
    assert lmsctl.load_exclusive("broken-model") is False
    assert f.resident == []


def test_run_closes_stdin(monkeypatch):
    """`lms unload` can prompt; an inherited stdin would block until timeout."""
    seen = {}

    def spy(args, **kwargs):
        seen.update(kwargs)
        return subprocess.CompletedProcess(args, 0, "[]", "")

    monkeypatch.setattr(subprocess, "run", spy)
    lmsctl.loaded()
    assert seen["stdin"] is subprocess.DEVNULL


def test_server_port_read_from_stderr(fake):
    assert lmsctl.server_port() == 1234
    fake.server_port = None
    assert lmsctl.server_port() is None
    assert lmsctl.server_status() is False


def test_ensure_server_starts_on_the_requested_port(fake, monkeypatch):
    """`lms server start` with no --port reuses the last port, silently."""
    monkeypatch.setattr(lmsctl, "_api_answers", lambda _u, **_k: True)
    fake.server_port = None
    lmsctl.ensure_server(port=1234, base_url="http://127.0.0.1:1234/v1")
    assert ["server", "start", "--port", "1234"] in fake.calls
    assert fake.server_port == 1234


def test_ensure_server_when_running_on_other_port_then_raises(fake):
    """A server on 1235 while inference targets 1234 fails every model."""
    fake.server_port = 1235
    with pytest.raises(lmsctl.LmsError, match="1235"):
        lmsctl.ensure_server(port=1234, base_url="http://127.0.0.1:1234/v1")


def test_ensure_server_when_api_does_not_answer_then_raises(fake, monkeypatch):
    """A wedged socket accepts TCP but never replies; catch it up front."""
    monkeypatch.setattr(lmsctl, "_api_answers", lambda _u, **_k: False)
    with pytest.raises(lmsctl.LmsError, match="does not answer"):
        lmsctl.ensure_server(port=1234, base_url="http://127.0.0.1:1234/v1")


def test_ensure_server_when_port_held_then_names_the_remedy(fake):
    def wedged(args, **kwargs):
        if args[1:3] == ["server", "start"]:
            fake.calls.append(args[1:])
            return subprocess.CompletedProcess(
                args, 1, "", "Error: listen EADDRINUSE: address already in use 127.0.0.1:1234"
            )
        return fake(args, **kwargs)

    fake.server_port = None
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(subprocess, "run", wedged)
        with pytest.raises(lmsctl.LmsError, match="Restart LM Studio"):
            lmsctl.ensure_server(port=1234)


def test_missing_lms_cli_raises_lms_error(monkeypatch):
    def missing(args, **kwargs):
        raise FileNotFoundError(args[0])

    monkeypatch.setattr(subprocess, "run", missing)
    with pytest.raises(lmsctl.LmsError, match="not found"):
        lmsctl.loaded()
