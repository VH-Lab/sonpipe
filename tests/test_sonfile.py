"""Tests for the SmrxFile wrapper and channel mappings."""

import types

import numpy as np
import pytest

import fakesonpy
from sonpipe import channels
from sonpipe.errors import SonpipeError
from sonpipe.sonfile import SmrxFile


def open_file(path):
    return SmrxFile(path, sonlib=fakesonpy)


def test_resolve_son_module_top_level():
    # Layout: sonpy.SonFile at the top level (e.g. CED Windows wheels).
    from sonpipe.sonfile import _resolve_son_module
    root = types.SimpleNamespace(SonFile=object)
    assert _resolve_son_module(root, lambda name: None) is root


def test_resolve_son_module_lib_submodule():
    from sonpipe.sonfile import _resolve_son_module
    lib = types.SimpleNamespace(SonFile=object)
    root = types.SimpleNamespace(lib=lib)
    assert _resolve_son_module(root, lambda name: None) is lib


def test_resolve_son_module_compiled_submodule():
    # Layout: empty sonpy/__init__.py, API in the compiled sonpy.sonpy (Linux).
    from sonpipe.sonfile import _resolve_son_module
    compiled = types.SimpleNamespace(SonFile=object)
    root = types.SimpleNamespace()  # no SonFile, no attributes

    def importer(name):
        assert name == "sonpy.sonpy"
        return compiled

    assert _resolve_son_module(root, importer) is compiled


def test_resolve_son_module_not_found():
    from sonpipe.sonfile import _resolve_son_module
    root = types.SimpleNamespace()
    assert _resolve_son_module(root, lambda name: (_ for _ in ()).throw(ImportError())) is None


def test_channel_kind_codes_match_sonpy_enum():
    assert channels.ADC == int(fakesonpy.DataType.Adc)
    assert channels.REAL_WAVE == int(fakesonpy.DataType.RealWave)
    assert channels.TEXT_MARK == int(fakesonpy.DataType.TextMark)


def test_ndr_type_mapping():
    assert channels.ndr_type(channels.ADC) == "analog_in"
    assert channels.ndr_type(channels.REAL_WAVE) == "analog_in"
    assert channels.ndr_type(channels.EVENT_FALL) == "event"
    assert channels.ndr_type(channels.MARKER) == "mark"
    assert channels.ndr_type(channels.REAL_MARK) == "mark"
    assert channels.ndr_type(channels.TEXT_MARK) == "text"


def test_missing_file_raises():
    with pytest.raises(SonpipeError):
        open_file("/no/such/file.smrx")


def test_leading_tilde_is_expanded(tmp_path, monkeypatch):
    # HOME (Unix) / USERPROFILE (Windows) drive os.path.expanduser.
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    (tmp_path / "ex.smrx").write_bytes(b"")
    smrx = open_file("~/ex.smrx")
    assert smrx.path == str(tmp_path / "ex.smrx")


def test_channel_numbers_skip_off(smrx_path):
    smrx = open_file(smrx_path)
    # slot index 1 (Spike2 #2) is Off and must be omitted.
    assert smrx.channel_numbers() == [1, 3, 4, 5, 6]


def test_number_to_index_offset(smrx_path):
    smrx = open_file(smrx_path)
    # Spike2 channel number 1 -> sonpy index 0.
    assert smrx.index_for_number(1) == 0
    assert smrx.index_for_number(6) == 5
    with pytest.raises(SonpipeError):
        smrx.index_for_number(999)


def test_adc_channel_info(smrx_path):
    smrx = open_file(smrx_path)
    info = smrx.channel_info(1)  # Spike2 #1 -> Adc
    assert info["kind"] == channels.ADC
    assert info["ndr_type"] == "analog_in"
    assert info["title"] == "Ramp"
    assert info["units"] == "V"
    assert info["sampleinterval"] == pytest.approx(fakesonpy.DIVIDE * fakesonpy.TIMEBASE)
    assert info["samplerate"] == pytest.approx(10000.0)
    assert info["num_samples"] == fakesonpy.N_SAMPLES


def test_off_channel_info_is_none(smrx_path):
    smrx = open_file(smrx_path)
    assert smrx.channel_info(2) is None  # Spike2 #2 is Off


def test_event_channel_info_has_nan_interval(smrx_path):
    smrx = open_file(smrx_path)
    info = smrx.channel_info(4)  # EventFall
    assert info["kind"] == channels.EVENT_FALL
    assert info["sampleinterval"] is None
    assert info["samplerate"] is None


def test_file_info(smrx_path):
    smrx = open_file(smrx_path)
    fi = smrx.file_info()
    assert fi["timebase"] == pytest.approx(fakesonpy.TIMEBASE)
    assert fi["max_time_ticks"] == fakesonpy.MAX_TICKS
    assert fi["max_time"] == pytest.approx(fakesonpy.MAX_TICKS * fakesonpy.TIMEBASE)


# -- waveform reads ---------------------------------------------------------

def test_read_full_adc_scaled(smrx_path):
    smrx = open_file(smrx_path)
    data = smrx.read_waveform(1)
    assert data.dtype == np.float64
    assert data.size == fakesonpy.N_SAMPLES
    # First raw sample is -1000; scaled = -1000*scale/6553.6 + offset.
    expected0 = -1000 * (2.0 / 6553.6) + 0.5
    assert data[0] == pytest.approx(expected0)


def test_read_adc_raw_is_int16(smrx_path):
    smrx = open_file(smrx_path)
    data = smrx.read_waveform(1, scaled=False)
    assert data.dtype == np.int16
    assert data[0] == -1000


def test_read_adc_chunk_start_count(smrx_path):
    smrx = open_file(smrx_path)
    full = smrx.read_waveform(1, scaled=False)
    chunk = smrx.read_waveform(1, start=100, count=50, scaled=False)
    assert chunk.size == 50
    np.testing.assert_array_equal(chunk, full[100:150])


def test_read_adc_chunks_tile_full(smrx_path):
    smrx = open_file(smrx_path)
    full = smrx.read_waveform(1, scaled=False)
    pieces = []
    for start in range(0, fakesonpy.N_SAMPLES, 250):
        pieces.append(smrx.read_waveform(1, start=start, count=250, scaled=False))
    joined = np.concatenate(pieces)
    np.testing.assert_array_equal(joined, full)


def test_read_realwave(smrx_path):
    smrx = open_file(smrx_path)
    data = smrx.read_waveform(3)  # RealWave
    assert data.dtype == np.float64
    assert data.size == fakesonpy.N_SAMPLES


def test_read_waveform_time_window(smrx_path):
    smrx = open_file(smrx_path)
    # 0 to 0.005 s at 10 kHz -> ~50 samples.
    data = smrx.read_waveform(1, t0=0.0, t1=0.005, scaled=False)
    assert 49 <= data.size <= 52


def test_read_waveform_on_event_channel_errors(smrx_path):
    smrx = open_file(smrx_path)
    with pytest.raises(SonpipeError):
        smrx.read_waveform(4)


# -- event / marker reads ---------------------------------------------------

def test_read_events_returns_seconds(smrx_path):
    smrx = open_file(smrx_path)
    times = smrx.read_events(4)
    assert times.dtype == np.float64
    # Events every 100 ticks at 1 us/tick -> every 1e-4 s.
    assert times[0] == pytest.approx(0.0)
    assert times[1] == pytest.approx(1e-4)


def test_read_events_time_window(smrx_path):
    smrx = open_file(smrx_path)
    times = smrx.read_events(4, t0=0.0, t1=0.001)
    assert np.all(times <= 0.001 + 1e-12)


def test_read_events_chunked_no_truncation(smrx_path):
    smrx = open_file(smrx_path)
    full = smrx.read_events(4)
    chunked = smrx.read_events(4, chunk=7)  # tiny chunk forces the read loop
    np.testing.assert_allclose(full, chunked)


def test_read_markers(smrx_path):
    smrx = open_file(smrx_path)
    markers = smrx.read_markers(5)  # Spike2 #5 -> generic Marker
    assert len(markers) > 0
    first = markers[0]
    assert first["time"] == pytest.approx(0.0)
    assert first["code"]  # marker code bytes present


def test_read_text_markers(smrx_path):
    smrx = open_file(smrx_path)
    markers = smrx.read_markers(6)  # Spike2 #6 -> TextMark
    assert len(markers) > 0
    assert "text" in markers[0]
    assert markers[0]["text"].startswith("note")


def test_read_markers_on_waveform_errors(smrx_path):
    smrx = open_file(smrx_path)
    with pytest.raises(SonpipeError):
        smrx.read_markers(1)
