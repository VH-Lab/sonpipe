"""End-to-end tests of the sonpipe CLI (with the fake sonpy)."""

import json

import numpy as np
import pytest

import fakesonpy
from sonpipe import cli


def run(capsysbinary, argv):
    """Run the CLI, returning (exit_code, stdout_bytes, stderr_text)."""
    code = cli.main(argv)
    captured = capsysbinary.readouterr()
    return code, captured.out, captured.err.decode() if isinstance(captured.err, bytes) else captured.err


def test_header_json(capsysbinary, smrx_path):
    code, out, _ = run(capsysbinary, ["header", smrx_path])
    assert code == 0
    doc = json.loads(out.decode())
    assert doc["fileinfo"]["timebase"] == pytest.approx(fakesonpy.TIMEBASE)
    numbers = [c["number"] for c in doc["channelinfo"]]
    assert numbers == [1, 3, 4, 5, 6]  # Off slot #2 excluded
    adc = doc["channelinfo"][0]
    assert adc["kind"] == 1
    assert adc["kind_name"] == "Adc"
    assert adc["ndr_type"] == "analog_in"


def test_sampleinterval_json(capsysbinary, smrx_path):
    code, out, _ = run(capsysbinary, ["sampleinterval", smrx_path, "-c", "1"])
    assert code == 0
    doc = json.loads(out.decode())
    assert doc["channel"] == 1
    assert doc["samplerate"] == pytest.approx(10000.0)
    assert doc["total_samples"] == fakesonpy.N_SAMPLES


def test_sampleinterval_off_channel_errors(capsysbinary, smrx_path):
    code, out, err = run(capsysbinary, ["sampleinterval", smrx_path, "-c", "2"])
    assert code == 2
    assert "not recorded" in err


def test_read_waveform_binary_double(capsysbinary, smrx_path):
    code, out, err = run(capsysbinary, ["read", smrx_path, "-c", "1"])
    assert code == 0
    data = np.frombuffer(out, dtype="<f8")
    assert data.size == fakesonpy.N_SAMPLES
    expected0 = -1000 * (2.0 / 6553.6) + 0.5
    assert data[0] == pytest.approx(expected0)
    assert "wrote 1000 samples" in err


def test_read_waveform_raw_int16(capsysbinary, smrx_path):
    code, out, _ = run(capsysbinary, ["read", smrx_path, "-c", "1", "--raw"])
    assert code == 0
    data = np.frombuffer(out, dtype="<i2")
    assert data.size == fakesonpy.N_SAMPLES
    assert data[0] == -1000


def test_read_waveform_chunk(capsysbinary, smrx_path):
    code, out, _ = run(capsysbinary, [
        "read", smrx_path, "-c", "1", "--start", "100", "--count", "50", "--raw"])
    assert code == 0
    data = np.frombuffer(out, dtype="<i2")
    assert data.size == 50


def test_read_chunks_reconstruct_full(capsysbinary, smrx_path):
    pieces = []
    for start in range(0, fakesonpy.N_SAMPLES, 300):
        _, out, _ = run(capsysbinary, [
            "read", smrx_path, "-c", "1", "--start", str(start),
            "--count", "300", "--raw"])
        pieces.append(np.frombuffer(out, dtype="<i2"))
    joined = np.concatenate(pieces)
    _, full_out, _ = run(capsysbinary, ["read", smrx_path, "-c", "1", "--raw"])
    full = np.frombuffer(full_out, dtype="<i2")
    np.testing.assert_array_equal(joined, full)


def test_read_waveform_big_endian(capsysbinary, smrx_path):
    code, out, _ = run(capsysbinary, [
        "read", smrx_path, "-c", "1", "--raw", "--endian", "big"])
    data = np.frombuffer(out, dtype=">i2")
    assert data[0] == -1000


def test_read_waveform_json(capsysbinary, smrx_path):
    code, out, _ = run(capsysbinary, [
        "read", smrx_path, "-c", "1", "--count", "5", "--json", "--raw"])
    doc = json.loads(out.decode())
    assert doc["count"] == 5
    assert len(doc["data"]) == 5


def test_read_events_binary(capsysbinary, smrx_path):
    code, out, err = run(capsysbinary, ["read", smrx_path, "-c", "4"])
    assert code == 0
    times = np.frombuffer(out, dtype="<f8")
    assert times[0] == pytest.approx(0.0)
    assert times[1] == pytest.approx(1e-4)
    assert "event times" in err


def test_read_markers_json(capsysbinary, smrx_path):
    code, out, _ = run(capsysbinary, ["read", smrx_path, "-c", "6"])
    assert code == 0
    doc = json.loads(out.decode())
    assert doc["kind_name"] == "TextMark"
    assert doc["count"] > 0
    assert "text" in doc["markers"][0]


def test_large_read_warns(capsysbinary, smrx_path, monkeypatch):
    # Lower the threshold so the modest fake file trips it.
    from sonpipe import cli as climod
    monkeypatch.setattr(climod, "WARN_BYTES", 100)
    code, out, err = run(capsysbinary, ["read", smrx_path, "-c", "1"])
    assert code == 0
    assert "warning" in err.lower()
    assert "MB" in err


def test_large_read_warning_suppressed(capsysbinary, smrx_path, monkeypatch):
    from sonpipe import cli as climod
    monkeypatch.setattr(climod, "WARN_BYTES", 100)
    code, out, err = run(capsysbinary, [
        "read", smrx_path, "-c", "1", "--no-size-warning"])
    assert code == 0
    assert "warning" not in err.lower()


def test_channels_listing(capsysbinary, smrx_path):
    code, out, _ = run(capsysbinary, ["channels", smrx_path])
    assert code == 0
    lines = out.decode().strip().splitlines()
    assert len(lines) == 5  # 5 non-Off channels
    assert lines[0].startswith("1\tAdc\tanalog_in")
