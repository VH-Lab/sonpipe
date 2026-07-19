# sonpipe

A lightweight command-line **bridge** for reading Cambridge Electronic Design
(CED) Spike2 data files. `sonpipe` extracts data from Spike2 files with CED's
[`sonpy`](https://pypi.org/project/sonpy/) library (GPLv3) and streams it as
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

2. **Licensing via pip.** CED's `sonpy` is licensed under the GPL v3. sonpipe
   does **not** vendor it; instead `pip install sonpipe` declares `sonpy` as a
   dependency, so pip fetches the official build from PyPI. Keeping it a runtime
   dependency (rather than bundling) leaves sonpipe's own MIT distribution free
   of GPL copyleft. (On Apple Silicon, CED's current wheel is x86_64-only — see
   the Apple Silicon note under Installation.)

3. **No text-parsing overhead.** Waveforms and event times are written as raw
   little-endian binary, not JSON/CSV text. MATLAB captures the byte stream and
   reinterprets it directly (`typecast` / `fread`) with no number→text→number
   round-trips.

4. **Controlled chunking.** The host drives ingestion, requesting blocks by
   sample index (`--start`/`--count`) or time window (`--t0`/`--t1`), keeping
   memory usage low and predictable even for multi-gigabyte recordings.

---

## Installation

### Recommended: the install script

The install scripts set up sonpipe in an **isolated virtual environment** and
put the `sonpipe` command on your PATH, so it never collides with other Python
packages. From a checkout of this repo:

```bash
# Linux / macOS
./install.sh
```
```powershell
# Windows (PowerShell)
./install.ps1 -AddToPath
```

On Linux/macOS this creates a venv at `~/.local/share/sonpipe/venv` and links
the command at `~/.local/bin/sonpipe`. On Windows the venv lives under
`%LOCALAPPDATA%\sonpipe`. Both print the exact `sonpipe.executable(...)` line to
paste into MATLAB. Run `./install.sh --help` for options (custom prefix, Python,
installing from PyPI, etc.).

**Updating.** After a `git pull`, re-run `./install.sh` (or `./update.sh`) — it
reuses the existing environment and upgrades the sonpipe package in place, which
is fast and doesn't re-download `sonpy`. Use `./install.sh --recreate` to force
a clean rebuild.

> **Python version.** CED ships `sonpy` wheels for **Python 3.14 on Linux and
> macOS** (and Python 3.9–3.14 on Windows). The installer prefers a
> `python3.14` interpreter; if `sonpy` cannot be imported it tells you to
> install 3.14 and re-run with `--python "$(command -v python3.14)"`.
>
> **Apple Silicon.** CED's macOS `sonpy` is x86_64-only (despite its
> `universal2` label) **and** is linked against the official **python.org**
> framework build — so it will not load under Homebrew or `uv` Python. On an
> Apple Silicon Mac:
>
> 1. Install **Python 3.14 from [python.org](https://www.python.org/downloads/macos/)**
>    (the universal2 installer).
> 2. Run `./install.sh` — it detects Apple Silicon, finds that framework Python
>    automatically, builds an **x86_64** venv under Rosetta 2, and installs the
>    `sonpipe` command as an `arch -x86_64` wrapper so it runs correctly even
>    when launched from MATLAB.
>
> Everything else (the CLI logic, the MATLAB package, and the fake-sonpy test
> suites) runs natively on arm64.

### Manual: pip

```bash
pip install sonpipe          # once published to PyPI
pip install .                # from a checkout
sonpipe --version
```

This also installs `sonpy` (from CED, via PyPI) and `numpy`. For an isolated,
PATH-managed command you can alternatively use `pipx install sonpipe`.

> **Note on the `sonpy` license.** `sonpy` is CED software licensed under the
> **GPL v3** and distributed by CED as prebuilt binaries (the underlying SON64
> C source is not published). It is fetched by pip at install time and is
> intentionally not bundled in this repository, so sonpipe's own MIT
> distribution stays free of GPL copyleft. GPL places no restrictions on *use*
> (reading your own files); obligations attach only to redistribution.

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

## Troubleshooting: diagnosing a hard crash

CED's `sonpy` is a compiled C++ library. On some files/channels it fails an
internal **assertion** and calls `abort()` (`SIGABRT`) instead of raising a
Python error. `abort()` cannot be caught with `try`/`except` — it terminates
the whole reader process immediately — so there is no Python traceback, and the
host may otherwise see only truncated or empty output.

Two mechanisms help you catch and locate such a crash:

1. **The MATLAB layer detects it.** A successful `read` prints a completion
   sentinel (`sonpipe: wrote N …`) to stderr as its final act. The MATLAB
   `invoke_binary` helper requires that sentinel and checks that `N` matches the
   bytes captured; if the reader died mid-stream (even when an intermediate
   `arch -x86_64` wrapper masks the non-zero exit status), you get a
   `sonpipe:crash` / `sonpipe:truncated` error naming the exact command instead
   of silently short data.

2. **Breadcrumb logging pinpoints *where* it crashed.** Set the `SONPIPE_LOG`
   environment variable and re-run the command that crashes. sonpipe writes one
   line immediately before and after every call into `sonpy`, flushed to disk so
   it survives the `abort()`. The **last line** in the log is then the `sonpy`
   call — with its exact arguments — that triggered the crash.

   ```bash
   # shell
   SONPIPE_LOG=1 sonpipe read recording.smrx -c 21 --t0 100 --t1 110 > /dev/null
   #   -> logs to ~/.local/var/log/sonpipe-<uid>.log
   SONPIPE_LOG=/tmp/sonpipe.log sonpipe read …      # or an explicit path
   ```
   ```matlab
   % MATLAB: turn on for the session, re-run the failing read, then turn off
   setenv('SONPIPE_LOG', '1');
   ... % the call that crashes
   setenv('SONPIPE_LOG', '');
   ```

   Accepted values: `1`/`true`/`on` → default path
   `~/.local/var/log/sonpipe-<uid>.log`; any other value → that path
   (`~` is expanded); unset/`0`/`false`/`off` → disabled (zero overhead).

   Every call into sonpy is logged — `SonFile` (open), the metadata accessors
   (`ChannelType`, `ChannelDivide`, `ChannelMaxTime`, `GetChannelScale`, …), the
   reads (`ReadInts` / `ReadFloats` / `ReadEvents` / marker reads), and the
   `Close`/teardown — plus a `done` line when the command finishes cleanly.
   Reading the **last line** tells you where it died:

   * ends on a dangling `-> ReadInts args=…` (no matching `<- ReadInts`) — that
     sonpy read aborted; the `read_waveform`/`read_events`/`read_markers`
     context line just above shows the resolved `tfrom/tupto/nmax`, so you can
     see the exact arguments sonpipe passed;
   * ends on a dangling `-> Close` / `del SonFile` — sonpy aborted while
     releasing the file handle (a teardown-order assertion);
   * ends on `done command=… rc=0` — the command completed and the data is
     valid; any crash report came from interpreter shutdown *after* the result
     was delivered.

   To avoid the teardown-order case, sonpipe now closes the sonpy file handle
   explicitly at the end of each command (while the interpreter is still
   healthy) rather than leaving it to garbage collection at shutdown. This makes
   the release step visible in the log and, in practice, prevents a class of
   post-read `abort()`s.

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

To additionally validate the **real** `sonpy` binding, there is an integration
suite that runs the actual CED sonpy end-to-end (both the `SmrxFile` wrapper and
the CLI as a subprocess) against the checked-in `example/spike2data.smrx`. It is
skipped unless `sonpy` is importable; point `SONPIPE_TEST_FILE` at another file
to use your own:

```bash
pip install sonpy                 # real CED sonpy (Python 3.14 on Linux/macOS)
pytest -m integration             # uses example/spike2data.smrx by default
```

In CI, the integration suite runs on **Linux, Windows, and macOS Apple Silicon**
using Python 3.14. On the macOS runner it exercises the x86_64 `sonpy` under
Rosetta 2 (`arch -x86_64`), since CED ships no native arm64 build.

### Continuous integration

Continuous integration (see `.github/workflows/`) mirrors the matbox style used
by NDR-matlab and runs on **Linux, Windows, and macOS Apple Silicon**. The
macOS runner covers both architectures: the CLI and MATLAB suites run natively
on arm64, while the real-`sonpy` suite runs x86_64 under Rosetta 2:

* **CLI tests** build the Python package (`compileall` + `python -m build`) and
  run the pytest suite.
* **MATLAB tests** run the `matlab.unittest` suite (which drives the CLI via a
  fake). matlab-actions provides MathWorks licensing for free on public repos;
  no secret is needed.

The workflows trigger on pushes to `main`, pull requests targeting `main`, and
manual dispatch.

---

## Repository layout

```
sonpipe/
├── src/sonpipe/            # Python package (CLI + sonpy wrapper)
├── tests/                  # Python tests (fake sonpy + real-sonpy integration)
├── matlab/+sonpipe/        # MATLAB client package (imitates ndr.format.ced.*)
├── test/+sonpipe/+unittest/# MATLAB unit tests + fake CLI
├── example/spike2data.smrx # a real 64-bit Spike2 file used by integration tests
└── .github/workflows/      # cross-platform CI (CLI, MATLAB, real-sonpy)
```

---

## License

sonpipe is released under the MIT License (see `LICENSE`). It depends on, but
does not include, CED's `sonpy` library, which is licensed separately under the
GPL v3.
