"""Integration tests against the *real* CED sonpy and a real Spike2 file.

Unlike the rest of the suite (which uses a synthetic fake sonpy), these exercise
the actual sonpy binding end-to-end -- both the :class:`SmrxFile` wrapper and the
CLI (as a subprocess, so the raw-binary pipe is exercised too).

They run when BOTH of the following hold:

* the ``sonpy`` package (CED, GPLv3) is importable, and
* a real Spike2 file is available -- by default the repository's
  ``example/spike2data.smrx``, or whatever ``SONPIPE_TEST_FILE`` points at.

Otherwise they are skipped. In CI they run on a Python for which CED ships a
sonpy wheel (Python 3.14 covers Linux, Windows, and macOS Intel/Apple Silicon).
"""

import json
import os
import subprocess
import sys

import numpy as np
import pytest

from sonpipe import channels
from sonpipe.sonfile import SmrxFile

pytestmark = pytest.mark.integration

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
_DEFAULT_FILE = os.path.join(_REPO, "example", "spike2data.smrx")
_FILE = os.environ.get("SONPIPE_TEST_FILE") or (
    _DEFAULT_FILE if os.path.exists(_DEFAULT_FILE) else None
)

try:
    import sonpy  # noqa: F401
    _HAVE_SONPY = True
except Exception:
    _HAVE_SONPY = False


@pytest.fixture
def real_file():
    if not _FILE:
        pytest.skip("no real Spike2 file (set SONPIPE_TEST_FILE or add example/spike2data.smrx)")
    if not os.path.exists(_FILE):
        pytest.skip("test file does not exist: {}".format(_FILE))
    if not _HAVE_SONPY:
        pytest.skip("CED sonpy is not installed (pip install sonpy)")
    return _FILE


def _first_waveform(smrx):
    for info in smrx.all_channel_info():
        if info["kind"] in channels.WAVEFORM_KINDS:
            return info
    return None


# -- SmrxFile wrapper --------------------------------------------------------

def test_header_has_valid_channels(real_file):
    smrx = SmrxFile(real_file)
    infos = smrx.all_channel_info()
    assert len(infos) > 0
    for info in infos:
        assert info["kind"] in channels.KIND_NAMES
        assert info["number"] >= 1
        assert info["ndr_type"] in ("analog_in", "event", "mark", "text")


def test_file_info(real_file):
    smrx = SmrxFile(real_file)
    fi = smrx.file_info()
    assert fi["timebase"] > 0
    assert fi["max_time_ticks"] >= 0


def test_waveform_read(real_file):
    smrx = SmrxFile(real_file)
    wf = _first_waveform(smrx)
    if wf is None:
        pytest.skip("no waveform channels in the test file")
    ch = wf["number"]

    assert wf["sampleinterval"] > 0
    assert abs(wf["samplerate"] * wf["sampleinterval"] - 1.0) < 1e-6

    full = smrx.read_waveform(ch)
    assert full.dtype == np.float64
    assert full.size > 0
    assert np.all(np.isfinite(full))

    # A count-limited read from the same origin is a prefix of a longer read.
    n = min(100, full.size)
    head = smrx.read_waveform(ch, start=0, count=n)
    assert head.size == n
    np.testing.assert_allclose(head, full[:n])

    # Raw (unscaled) reads come back as int16 for Adc channels.
    if wf["kind"] == channels.ADC:
        raw = smrx.read_waveform(ch, start=0, count=n, scaled=False)
        assert raw.dtype == np.int16
        assert raw.size == n


def test_event_or_marker_read(real_file):
    smrx = SmrxFile(real_file)
    for info in smrx.all_channel_info():
        if info["kind"] in channels.EVENT_KINDS:
            times = smrx.read_events(info["number"])
            assert times.dtype == np.float64
            assert np.all(np.diff(times) >= 0)  # non-decreasing
            return
        if info["kind"] in channels.MARKER_KINDS:
            markers = smrx.read_markers(info["number"])
            for m in markers:
                assert "time" in m
            return
    pytest.skip("no event or marker channels in the test file")


# -- CLI end-to-end (subprocess, exercises the raw-binary pipe) ---------------

def _cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "sonpipe", *args],
        check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    ).stdout


def test_cli_header_and_binary_read(real_file):
    doc = json.loads(_cli("header", real_file))
    assert "fileinfo" in doc and "channelinfo" in doc
    waves = [c for c in doc["channelinfo"] if c["kind"] in (channels.ADC, channels.REAL_WAVE)]
    if not waves:
        pytest.skip("no waveform channels in the test file")
    ch = str(waves[0]["number"])

    raw = _cli("read", real_file, "-c", ch, "--start", "0", "--count", "100")
    data = np.frombuffer(raw, dtype="<f8")
    assert 0 < data.size <= 100
    assert np.all(np.isfinite(data))
