# sonpipe

A lightweight command-line **bridge** for reading Cambridge Electronic Design
(CED) Spike2 data files. `sonpipe` extracts data from proprietary Spike2 files
with CED's [`sonpy`](https://pypi.org/project/sonpy/) library and streams it as
**raw binary bytes** to standard output, so a host environment such as MATLAB
can ingest it in chunks — quickly, predictably, and cross-platform.

It supports **both** Spike2 file formats transparently:

* **32-bit `.smr`** (legacy "son32")
* **64-bit `.smrx`** ("son64")

The command-line tools imitate the reading functions of the
[`ndr.format.ced`](https://github.com/VH-Lab/NDR-matlab) package in NDR-matlab,
and a companion MATLAB package (`+sonpipe`) provides drop-in analogues of those
functions that call the CLI for you.

---

## Why a CLI bridge?

1. **Interpreter isolation.** Python runs in its own process, invoked by a
   system call. It never shares MATLAB's memory space, so there are no version
   locks, environment conflicts, or interpreter crashes inside your workspace.

2. **Licensing via pip.** CED's `sonpy` is proprietary. sonpipe does **not**
   bundle or redistribute it; instead `pip install sonpipe` declares `sonpy` as
   a dependency, so pip fetches the official, authorized CED binaries directly
   — including native builds for Apple Silicon.

3. **No text-parsing overhead.** Waveforms and event times are written as raw
   little-endian binary, not JSON/CSV text. MATLAB captures the byte stream and
   reinterprets it directly (`typecast` / `fread`) with no number→text→number
   round-trips.

4. **Controlled chunking.** The host drives ingestion, requesting blocks by
   sample index (`--start`/`--count`) or time window (`--t0`/`--t1`), keeping
   memory usage low and predictable even for multi-gigabyte recordings.

---

## Installation

```bash
pip install sonpipe
```

This also installs `sonpy` (from CED, via PyPI) and `numpy`. Verify:

```bash
sonpipe --version
```

> **Note on the CED license.** `sonpy` is proprietary CED software. It is
> fetched by pip at install time and is intentionally not included in this
> repository.

---

## Command-line usage

`sonpipe` has four sub-commands. Metadata commands emit JSON; `read` emits raw
binary (except for markers, which are JSON).

| Sub-command              | NDR-matlab analogue                          |
| ------------------------ | -------------------------------------------- |
| `sonpipe header`         | `ndr.format.ced.read_SOMSMR_header`          |
| `sonpipe sampleinterval` | `ndr.format.ced.read_SOMSMR_sampleinterval`  |
| `sonpipe read`           | `ndr.format.ced.read_SOMSMR_datafile`        |
| `sonpipe channels`       | (convenience listing)                        |

### header — file and channel metadata (JSON)

```bash
sonpipe header recording.smrx --pretty
```

Channels are reported by their **Spike2 channel number** (1-based). The `kind`
field is the CED data-type code (see table below), which matches both `sonpy`'s
`DataType` enum and NDR-matlab's `channelinfo.kind`.

### sampleinterval — timing for one channel (JSON)

```bash
sonpipe sampleinterval recording.smrx -c 21
# {"channel":21,"sampleinterval":4e-05,"samplerate":25000.0,"total_samples":...,"total_time":...}
```

### read — stream channel data

Waveform, by sample block (raw little-endian `double`, scaled to real units):

```bash
sonpipe read recording.smrx -c 21 --start 0 --count 500000 > block0.bin
```

Waveform, by time window; raw unscaled 16-bit ADC values:

```bash
sonpipe read recording.smrx -c 21 --t0 0 --t1 10 --raw > adc.bin
```

Event channel (event times in seconds, as `double`):

```bash
sonpipe read recording.smrx -c 24 > events.bin
```

Marker / TextMark channel (JSON — times, code bytes, optional text):

```bash
sonpipe read recording.smrx -c 30
```

Useful `read` flags: `--raw` (int16 ADC values), `--dtype`
{double,single,int16,int32,int64}, `--endian` {little,big,native}, `--json`
(debugging), `--no-size-warning`.

> **Large reads.** Because the pipe can be slow for very large transfers,
> sonpipe prints a warning to stderr when a read exceeds **50 MB**. Read in
> smaller blocks, or pass `--no-size-warning` to silence it.

### channels — quick tab-separated listing

```bash
sonpipe channels recording.smrx
# 21   Adc   analog_in   25000.0000 Hz   Vm
```

### Channel kinds

| kind  | name     | ndr_type  | read as                       |
| ----- | -------- | --------- | ----------------------------- |
| 1     | Adc      | analog_in | binary waveform (int16→real)  |
| 2/3/4 | Event\*  | event     | binary event times (double)   |
| 5     | Marker   | mark      | JSON (time + code bytes)      |
| 6     | AdcMark  | mark      | JSON (WaveMark)               |
| 7     | RealMark | mark      | JSON                          |
| 8     | TextMark | text      | JSON (time + text)            |
| 9     | RealWave | analog_in | binary waveform (float)       |

---

## MATLAB usage

The `matlab/+sonpipe` package provides drop-in analogues of the
`ndr.format.ced.*` functions, backed by the CLI.

**Setup**

1. `pip install sonpipe`
2. Add the folder that *contains* `+sonpipe` to the MATLAB path:
   ```matlab
   addpath('/path/to/sonpipe/matlab')
   ```
3. If the `sonpipe` command is not on the system PATH, tell MATLAB where it is:
   ```matlab
   sonpipe.executable('/full/path/to/sonpipe')   % or 'python3 -m sonpipe'
   ```

**Example**

```matlab
f = '/data/recording.smrx';          % or a legacy .smr file

h  = sonpipe.read_SOMSMR_header(f);   % file + channel header
sr = 1 / sonpipe.read_SOMSMR_sampleinterval(f, h, 21);

% Read waveform channel 21 from t = 0 to t = 100 s
[data, total_samples, total_time, ~, t] = ...
    sonpipe.read_SOMSMR_datafile(f, h, 21, 0, 100);

plot(t, data); xlabel('Time (s)'); ylabel(h.channelinfo(1).units);
```

Because these mirror `ndr.format.ced.*`, existing code often ports by swapping
the package prefix (`ndr.format.ced` → `sonpipe`).

Helpers: `sonpipe.channels(f)` (NDR-style channel struct array),
`sonpipe.channelinfo(h, n)` (one channel's header entry), `sonpipe.executable`
(locate/set the CLI command).

---

## Development, testing, and CI

**Python (CLI) tests** use a fake `sonpy` shim, so they run anywhere:

```bash
pip install -e . --no-deps
pip install numpy pytest
pytest -q
```

**MATLAB tests** live in `test/+sonpipe/+unittest` and drive a fake CLI
(`fakecli.py`, which runs the real sonpipe code against synthetic data), so
they too need no CED binaries — only Python + numpy:

```matlab
addpath('matlab'); addpath('test');
results = runtests('sonpipe.unittest');
```

### Where do the test files come from?

The default suites use **no real Spike2 files**. `tests/fakesonpy.py` is a
pure-Python stand-in for CED's `sonpy` that serves synthetic in-memory channels
(a ramp waveform, a sine `RealWave`, events, markers, text markers); the MATLAB
tests drive `fakecli.py`, which runs the real sonpipe code against that same
fake. This keeps the suites deterministic and lets them run everywhere —
including Linux, where CED's `sonpy` does not install cleanly.

To additionally validate the **real** `sonpy` binding, there is an optional,
skipped-by-default integration suite. Point it at any real file (for example,
NDR-matlab's `example_data/example.smr`) with `sonpy` installed:

```bash
SONPIPE_TEST_FILE=/path/to/example.smr pytest -m integration
```

### Continuous integration

Continuous integration (see `.github/workflows/`) mirrors the matbox style used
by NDR-matlab. Both the CLI and MATLAB suites are built ("compiled") and run on
**Linux, Windows, macOS Intel, and macOS Apple Silicon**. The workflows trigger
on pushes to `main`, pull requests targeting `main`, and manual dispatch.

---

## Repository layout

```
sonpipe/
├── src/sonpipe/            # Python package (CLI + sonpy wrapper)
├── tests/                  # Python tests + fake sonpy
├── matlab/+sonpipe/        # MATLAB client package (imitates ndr.format.ced.*)
├── test/+sonpipe/+unittest/# MATLAB unit tests + fake CLI
└── .github/workflows/      # cross-platform CI (CLI + MATLAB)
```

---

## License

sonpipe is released under the MIT License (see `LICENSE`). It depends on, but
does not include, CED's proprietary `sonpy` library, which carries its own
license.
