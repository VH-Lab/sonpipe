"""Optional integration tests against the *real* CED sonpy and a real file.

These are skipped unless BOTH of the following hold:

* the ``sonpy`` package (proprietary CED) is importable, and
* the ``SONPIPE_TEST_FILE`` environment variable points at a real ``.smr`` or
  ``.smrx`` file.

A convenient fixture is NDR-matlab's ``example_data/example.smr``:

    SONPIPE_TEST_FILE=/path/to/NDR-matlab/example_data/example.smr pytest -m integration

Unlike the rest of the suite (which uses a synthetic fake sonpy), these tests
validate the actual sonpy binding end-to-end.
"""

import os

import numpy as np
import pytest

from sonpipe import channels
from sonpipe.sonfile import SmrxFile

pytestmark = pytest.mark.integration

_FILE = os.environ.get("SONPIPE_TEST_FILE")

try:
    import sonpy  # noqa: F401
    _HAVE_SONPY = True
except Exception:
    _HAVE_SONPY = False


@pytest.fixture
def real_file():
    if not _FILE:
        pytest.skip("set SONPIPE_TEST_FILE to a real .smr/.smrx file to run integration tests")
    if not os.path.exists(_FILE):
        pytest.skip("SONPIPE_TEST_FILE does not exist: {}".format(_FILE))
    if not _HAVE_SONPY:
        pytest.skip("CED sonpy is not installed (pip install sonpy)")
    return _FILE


def test_header_has_channels(real_file):
    smrx = SmrxFile(real_file)
    infos = smrx.all_channel_info()
    assert len(infos) > 0
    for info in infos:
        assert info["kind"] in channels.KIND_NAMES
        assert info["number"] >= 1


def test_waveform_read_and_chunking(real_file):
    smrx = SmrxFile(real_file)
    waveforms = [c for c in smrx.all_channel_info()
                 if c["kind"] in channels.WAVEFORM_KINDS]
    if not waveforms:
        pytest.skip("no waveform channels in the test file")
    ch = waveforms[0]["number"]

    si = smrx.channel_info(ch)["sampleinterval"]
    assert si is not None and si > 0

    full = smrx.read_waveform(ch, start=0, count=500, scaled=True)
    assert full.dtype == np.float64
    assert np.all(np.isfinite(full))

    # A sample sub-block must match the corresponding slice of a larger read.
    chunk = smrx.read_waveform(ch, start=100, count=50, scaled=True)
    assert chunk.size == 50
    np.testing.assert_allclose(chunk, full[100:150])


def test_sampleinterval_matches_header(real_file):
    smrx = SmrxFile(real_file)
    for info in smrx.all_channel_info():
        if info["kind"] in channels.WAVEFORM_KINDS:
            assert info["samplerate"] > 0
            assert abs(info["samplerate"] * info["sampleinterval"] - 1.0) < 1e-6
