"""Tests for the opt-in breadcrumb logging (sonpipe.debuglog)."""

import importlib
import os
import signal
import subprocess
import sys

import pytest

import fakesonpy
from sonpipe import debuglog


@pytest.fixture(autouse=True)
def _fresh_debuglog(monkeypatch):
    # debuglog caches the resolved path; reset it for each test.
    monkeypatch.setattr(debuglog, "_state", {"resolved": False, "path": None})
    monkeypatch.delenv("SONPIPE_LOG", raising=False)
    yield


@pytest.mark.parametrize("value", ["", "0", "false", "off", "NO"])
def test_disabled_values_yield_no_path(monkeypatch, value):
    monkeypatch.setenv("SONPIPE_LOG", value)
    monkeypatch.setattr(debuglog, "_state", {"resolved": False, "path": None})
    assert debuglog.logfile_path() is None
    assert debuglog.enabled() is False


def test_explicit_path_is_used_and_expanded(tmp_path, monkeypatch):
    target = tmp_path / "sub" / "sonpipe.log"
    monkeypatch.setenv("SONPIPE_LOG", str(target))
    monkeypatch.setattr(debuglog, "_state", {"resolved": False, "path": None})
    assert debuglog.logfile_path() == str(target)
    assert debuglog.enabled() is True


def test_log_writes_line_with_fields(tmp_path, monkeypatch):
    target = tmp_path / "sonpipe.log"
    monkeypatch.setenv("SONPIPE_LOG", str(target))
    monkeypatch.setattr(debuglog, "_state", {"resolved": False, "path": None})
    debuglog.log("read_waveform", number=1, nmax=50)
    text = target.read_text()
    assert "read_waveform" in text
    assert "number=1" in text
    assert "nmax=50" in text


def test_log_is_noop_when_disabled(tmp_path, monkeypatch):
    # No SONPIPE_LOG set -> nothing is written anywhere.
    debuglog.log("should_not_appear", x=1)
    assert not any(p.name.endswith(".log") for p in tmp_path.iterdir())


def test_call_passes_through_and_logs_both_ends(tmp_path, monkeypatch):
    target = tmp_path / "sonpipe.log"
    monkeypatch.setenv("SONPIPE_LOG", str(target))
    monkeypatch.setattr(debuglog, "_state", {"resolved": False, "path": None})
    result = debuglog.call("Widget", lambda a, b: a + b, 2, 3)
    assert result == 5
    text = target.read_text()
    assert "-> Widget" in text
    assert "<- Widget" in text
    assert "args=2,3" in text


def test_call_is_transparent_when_disabled():
    # With logging off, call() is a plain passthrough (and touches no disk).
    assert debuglog.call("Widget", lambda a, b: a * b, 4, 5) == 20


def test_breadcrumb_survives_an_abort(tmp_path):
    """The '-> name' line must be flushed *before* the call, so it survives an
    uncatchable abort() -- the exact scenario sonpy's assert triggers."""
    logpath = tmp_path / "sonpipe.log"
    driver = (
        "import os, signal, sys\n"
        "sys.path[:0] = [{tests!r}, {src!r}]\n"
        "os.environ['SONPIPE_LOG'] = {log!r}\n"
        "from sonpipe import debuglog\n"
        "def boom():\n"
        "    os.kill(os.getpid(), signal.SIGABRT)\n"
        "debuglog.call('ReadInts', boom)\n"
    ).format(
        tests=os.path.join(os.path.dirname(__file__)),
        src=os.path.join(os.path.dirname(os.path.dirname(__file__)), "src"),
        log=str(logpath),
    )
    proc = subprocess.run([sys.executable, "-c", driver],
                          capture_output=True, text=True)
    # Killed by SIGABRT (negative signal number on POSIX).
    assert proc.returncode == -signal.SIGABRT
    lines = logpath.read_text().strip().splitlines()
    # The last surviving line is the pre-call breadcrumb naming the crash site,
    # and there is no matching '<- ReadInts' completion line.
    assert lines[-1].split("pid=")[1].split(" ", 1)[1].startswith("-> ReadInts")
    assert not any("<- ReadInts" in ln for ln in lines)


def test_importable_alongside_fakesonpy():
    # Guard against import cycles between sonfile and debuglog.
    importlib.reload(fakesonpy)
    from sonpipe import sonfile  # noqa: F401
