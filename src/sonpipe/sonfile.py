"""A thin, testable wrapper around a CED ``sonpy`` ``SonFile``.

This module isolates every call into ``sonpy`` so that:

* the rest of sonpipe deals in plain integers, numpy arrays and dicts, and
* tests can inject a fake ``sonpy`` implementation (see ``tests/fakesonpy.py``)
  and run on machines where CED's sonpy binaries are not available.

Channel numbering
-----------------
``sonpy`` addresses channels with a 0-based index, but Spike2 (and NDR-matlab)
refer to channels by their 1-based "channel number" as shown in the Spike2
Sampling Configuration.  sonpipe speaks the Spike2 convention on its public
surface: a channel *number* ``n`` maps to the sonpy *index* ``n - 1``.
"""

import math
import os

import numpy as np

from . import channels, debuglog
from .errors import SonpipeError


def _resolve_son_module(root, importer):
    """Return the sonpy module object that actually exposes ``SonFile``.

    CED packages sonpy inconsistently across platforms and versions:

    * some wheels expose the API at the top level (``sonpy.__init__`` does
      ``from .sonpy import *``), so ``sonpy.SonFile`` works;
    * some wheels ship an empty ``__init__`` and the API lives in the compiled
      submodule ``sonpy.sonpy``;
    * older references used a ``sonpy.lib`` submodule.

    ``root`` is the imported top-level ``sonpy`` package and ``importer`` is a
    callable like ``importlib.import_module``. Returns the module exposing
    ``SonFile``, or ``None`` if none of the known layouts do.
    """
    if hasattr(root, "SonFile"):
        return root
    for sub in ("lib", "sonpy"):
        mod = getattr(root, sub, None)
        if mod is None:
            try:
                mod = importer("sonpy." + sub)
            except Exception:
                mod = None
        if mod is not None and hasattr(mod, "SonFile"):
            return mod
    return None


def load_sonpy():
    """Import and return the sonpy module that exposes ``SonFile``.

    ``sonpy`` is CED's GPLv3-licensed package and is not vendored with sonpipe.
    """
    import importlib

    try:
        root = importlib.import_module("sonpy")
    except Exception as exc:  # pragma: no cover - exercised only without sonpy
        raise SonpipeError(
            "The 'sonpy' package (Cambridge Electronic Design) is required but "
            "could not be imported.\n"
            "Install it with:  pip install sonpy\n"
            "sonpy is CED's GPLv3-licensed software, fetched from PyPI on "
            "install; it is intentionally not bundled with sonpipe.\n"
            f"(import error: {exc})"
        )

    module = _resolve_son_module(root, importlib.import_module)
    if module is None:
        raise SonpipeError(
            "sonpy is installed but no module exposing 'SonFile' was found "
            "(checked sonpy, sonpy.lib, sonpy.sonpy). This is an unexpected "
            "sonpy version/layout."
        )
    return module


def _call(method, index):
    """Call a sonpy accessor that may want the channel positionally or as ``chan=``."""
    try:
        return method(index)
    except TypeError:
        return method(chan=index)


class SmrxFile:
    """Read metadata and data from a single ``.smrx`` / ``.smr`` file."""

    def __init__(self, path, sonlib=None):
        if sonlib is None:
            sonlib = load_sonpy()
        self._son = sonlib
        # Expand a leading ~ (callers such as MATLAB pass it through literally,
        # and neither the shell nor Python expands it inside a quoted argument).
        self.path = os.path.expanduser(os.fspath(path))
        if not os.path.exists(self.path):
            raise SonpipeError("File not found: {}".format(self.path))

        # sonpy opens in read-only mode when the second argument is True.
        debuglog.log("open", path=self.path)
        self.f = debuglog.call("SonFile", sonlib.SonFile, self.path, True)
        self._check_open_error()

        self.timebase = float(debuglog.call("GetTimeBase", self.f.GetTimeBase))
        self.max_channels = int(debuglog.call("MaxChannels", self.f.MaxChannels))

    # -- close / teardown --------------------------------------------------

    def close(self):
        """Release the sonpy file handle while the interpreter is still healthy.

        sonpy's ``SonFile`` closes its file in its C++ destructor. If we leave
        that to interpreter shutdown, the destructor can run in a torn-down
        state and fail an internal assertion (abort()/SIGABRT) *after* a read
        has already succeeded -- a crash with no bad data but an alarming
        report. Closing explicitly here, at a well-defined point, both makes
        that step visible in the breadcrumb log and avoids the shutdown-order
        assertion. Safe to call more than once.
        """
        f = getattr(self, "f", None)
        if f is None:
            return
        self.f = None
        closer = getattr(f, "Close", None) or getattr(f, "close", None)
        if callable(closer):
            debuglog.call("Close", closer)
        else:
            # No explicit close method; drop the last reference now (rather than
            # at interpreter shutdown) so the destructor runs while healthy.
            debuglog.log("del SonFile")
            del f

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False

    # -- open / error handling ---------------------------------------------

    def _check_open_error(self):
        """Raise if sonpy reports the file could not be opened."""
        getter = getattr(self.f, "GetOpenError", None)
        if getter is None:
            return
        try:
            err = getter()
        except Exception:
            return
        # sonpy returns 0 (or an enum whose int() is 0) on success.
        try:
            code = int(err)
        except (TypeError, ValueError):
            code = 0 if err is None else 1
        if code != 0:
            raise SonpipeError(
                "sonpy could not open '{}' (open error code {}). "
                "Is it a valid Spike2 .smrx/.smr file?".format(self.path, code)
            )

    # -- channel discovery -------------------------------------------------

    def index_for_number(self, number):
        """Convert a Spike2 1-based channel *number* to a sonpy 0-based *index*."""
        index = int(number) - 1
        if index < 0 or index >= self.max_channels:
            raise SonpipeError(
                "Channel number {} is out of range (file has {} channel "
                "slots).".format(number, self.max_channels)
            )
        return index

    def kind(self, index):
        """Return the integer channel-type ``kind`` for a sonpy channel *index*."""
        return int(debuglog.call("ChannelType", self.f.ChannelType, index))

    def channel_numbers(self):
        """Return the Spike2 channel numbers of every non-Off channel."""
        numbers = []
        for index in range(self.max_channels):
            if self.kind(index) != channels.OFF:
                numbers.append(index + 1)
        return numbers

    def _text(self, method_name, index):
        method = getattr(self.f, method_name, None)
        if method is None:
            return ""
        try:
            value = debuglog.call(
                "{}[{}]".format(method_name, index), lambda: _call(method, index))
        except Exception:
            return ""
        if value is None:
            return ""
        return str(value).strip()

    def _num(self, method_name, index, default=None):
        method = getattr(self.f, method_name, None)
        if method is None:
            return default
        try:
            return float(debuglog.call(
                "{}[{}]".format(method_name, index), lambda: _call(method, index)))
        except Exception:
            return default

    def channel_info(self, number):
        """Return a metadata dict for the given Spike2 channel *number*.

        Returns ``None`` if the channel slot is Off (unused).
        """
        index = self.index_for_number(number)
        kind = self.kind(index)
        if kind == channels.OFF:
            return None

        max_ticks = self._num("ChannelMaxTime", index, default=0.0)
        max_ticks = 0 if max_ticks is None else int(max_ticks)

        info = {
            "number": number,
            "index": index,
            "kind": kind,
            "kind_name": channels.kind_name(kind),
            "ndr_type": channels.ndr_type(kind),
            "title": self._text("GetChannelTitle", index),
            "units": self._text("GetChannelUnits", index),
            "comment": self._text("GetChannelComment", index),
            "max_time_ticks": max_ticks,
            "max_time": max_ticks * self.timebase,
            # The following keys are always present (null for non-waveform
            # channels) so that consumers such as MATLAB's jsondecode receive a
            # uniform struct array rather than a ragged cell array.
            "sampleinterval": None,
            "samplerate": None,
            "divide": None,
            "ideal_rate": None,
            "scale": None,
            "offset": None,
            "num_samples": None,
        }

        if kind in channels.WAVEFORM_KINDS:
            divide = int(debuglog.call("ChannelDivide", self.f.ChannelDivide, index))
            info["divide"] = divide
            sample_interval = divide * self.timebase
            info["sampleinterval"] = sample_interval
            info["samplerate"] = (1.0 / sample_interval) if sample_interval > 0 else None
            info["ideal_rate"] = self._num("GetIdealRate", index)
            info["scale"] = self._num("GetChannelScale", index, default=1.0)
            info["offset"] = self._num("GetChannelOffset", index, default=0.0)
            info["num_samples"] = (max_ticks // divide) if divide > 0 else 0

        return info

    def all_channel_info(self):
        """Return metadata dicts for every non-Off channel, ordered by number."""
        out = []
        for number in self.channel_numbers():
            info = self.channel_info(number)
            if info is not None:
                out.append(info)
        return out

    def file_info(self):
        """Return file-level metadata (timebase, duration, channel count)."""
        max_time_ticks = self._file_max_ticks()
        info = {
            "path": self.path,
            "timebase": self.timebase,
            "max_channels": self.max_channels,
            "max_time_ticks": max_time_ticks,
            "max_time": max_time_ticks * self.timebase,
        }
        for name, key in (("GetFileVersion", "version"), ("AppID", "app_id")):
            method = getattr(self.f, name, None)
            if method is not None:
                try:
                    info[key] = debuglog.call(name, method)
                except Exception:
                    pass
        return info

    def _file_max_ticks(self):
        getter = getattr(self.f, "GetMaxTime", None)
        if getter is not None:
            try:
                return int(debuglog.call("GetMaxTime", getter))
            except Exception:
                pass
        # Fall back to the largest per-channel max time.
        longest = 0
        for index in range(self.max_channels):
            if self.kind(index) == channels.OFF:
                continue
            ticks = self._num("ChannelMaxTime", index, default=0.0) or 0.0
            longest = max(longest, int(ticks))
        return longest

    # -- time <-> tick <-> sample helpers ----------------------------------

    def seconds_to_ticks(self, seconds):
        """Round a time in seconds to the nearest integer clock tick."""
        return int(round(seconds / self.timebase))

    def _wave_tick_range(self, index, start, count, t0, t1):
        """Resolve a read request into ``(tfrom_ticks, tupto_ticks, nmax)``.

        Either sample-based (``start``/``count``) or time-based (``t0``/``t1``)
        arguments may be given.  Sample-based reads assume the waveform's first
        sample sits at tick 0, which is the common Spike2 case.
        """
        divide = int(debuglog.call("ChannelDivide", self.f.ChannelDivide, index))
        if divide <= 0:
            divide = 1
        max_ticks = int(self._num("ChannelMaxTime", index, default=0.0) or 0)

        if start is not None or count is not None:
            start = 0 if start is None else int(start)
            if start < 0:
                start = 0
            tfrom = start * divide
            if count is None:
                tupto = max_ticks + 1
                nmax = max(0, (max_ticks - tfrom) // divide + 1)
            else:
                count = int(count)
                tupto = (start + count) * divide
                nmax = count
        else:
            # Time-based.
            tfrom = 0 if (t0 is None or t0 < 0) else self.seconds_to_ticks(t0)
            if t1 is None or math.isinf(t1):
                tupto = max_ticks + 1
            else:
                tupto = self.seconds_to_ticks(t1) + 1
            span = max(0, tupto - tfrom)
            nmax = span // divide + 2

        if tupto > max_ticks + 1:
            tupto = max_ticks + 1
        return tfrom, tupto, int(nmax)

    def _event_tick_range(self, t0, t1):
        max_ticks = self._file_max_ticks()
        tfrom = 0 if (t0 is None or t0 < 0) else self.seconds_to_ticks(t0)
        if t1 is None or math.isinf(t1):
            tupto = max_ticks + 1
        else:
            tupto = self.seconds_to_ticks(t1) + 1
        return int(tfrom), int(tupto)

    # -- reads -------------------------------------------------------------

    def read_waveform(self, number, start=None, count=None, t0=None, t1=None,
                      scaled=True):
        """Read waveform samples for a channel and return a numpy array.

        For ``Adc`` channels the raw 16-bit integers are converted to real
        units with ``value = adc * scale / 6553.6 + offset`` when ``scaled`` is
        true; otherwise the raw ``int16`` values are returned.  ``RealWave``
        channels are already in real units.
        """
        index = self.index_for_number(number)
        kind = self.kind(index)
        if kind not in channels.WAVEFORM_KINDS:
            raise SonpipeError(
                "Channel {} is {} (kind {}), not a waveform channel.".format(
                    number, channels.kind_name(kind), kind
                )
            )
        tfrom, tupto, nmax = self._wave_tick_range(index, start, count, t0, t1)
        debuglog.log("read_waveform", number=number, index=index, kind=kind,
                     start=start, count=count, t0=t0, t1=t1,
                     tfrom=tfrom, tupto=tupto, nmax=nmax)
        if nmax <= 0:
            return np.zeros(0, dtype=np.float64 if scaled else _wave_raw_dtype(kind))

        if kind == channels.ADC:
            raw = np.asarray(debuglog.call(
                "ReadInts", self.f.ReadInts, index, nmax, tfrom, tupto))
            if scaled:
                scale = self._num("GetChannelScale", index, default=1.0)
                offset = self._num("GetChannelOffset", index, default=0.0)
                return raw.astype(np.float64) * (scale / 6553.6) + offset
            return raw.astype(np.int16)
        else:  # REAL_WAVE
            raw = np.asarray(debuglog.call(
                "ReadFloats", self.f.ReadFloats, index, nmax, tfrom, tupto))
            return raw.astype(np.float64 if scaled else np.float32)

    def read_events(self, number, t0=None, t1=None, chunk=1_000_000):
        """Read event times (seconds) for an event or marker channel.

        Reads in ticks and converts to seconds using the file time base.  The
        read is chunked so channels with more than ``chunk`` events are not
        truncated.
        """
        index = self.index_for_number(number)
        kind = self.kind(index)
        tfrom, tupto = self._event_tick_range(t0, t1)
        debuglog.log("read_events", number=number, index=index, kind=kind,
                     t0=t0, t1=t1, tfrom=tfrom, tupto=tupto)

        reader = self._event_reader_for(kind)
        pieces = []
        cursor = tfrom
        while cursor < tupto:
            ticks = np.asarray(reader(index, chunk, cursor, tupto), dtype=np.int64)
            if ticks.size == 0:
                break
            pieces.append(ticks)
            if ticks.size < chunk:
                break
            cursor = int(ticks[-1]) + 1
        if not pieces:
            return np.zeros(0, dtype=np.float64)
        return np.concatenate(pieces).astype(np.float64) * self.timebase

    def _event_reader_for(self, kind):
        """Return a callable ``(index, nmax, tfrom, tupto) -> tick array``.

        For pure event channels this is ``ReadEvents``.  Marker channels do not
        have a plain-event reader, so we pull markers and take their ticks.
        """
        if kind in channels.EVENT_KINDS:
            return lambda i, n, a, b: debuglog.call(
                "ReadEvents", self.f.ReadEvents, i, n, a, b)

        marker_method = self._marker_method(kind)
        marker_name = getattr(marker_method, "__name__", "ReadMarkers")

        def read_marker_ticks(i, n, a, b):
            markers = debuglog.call(marker_name, marker_method, i, n, a, b)
            return _marker_ticks(markers)

        return read_marker_ticks

    def _marker_method(self, kind):
        name = {
            channels.MARKER: "ReadMarkers",
            channels.ADC_MARK: "ReadWaveMarks",
            channels.REAL_MARK: "ReadRealMarks",
            channels.TEXT_MARK: "ReadTextMarks",
        }.get(kind)
        method = getattr(self.f, name, None) if name else None
        if method is None:
            # Fall back to generic ReadMarkers if the specific reader is absent.
            method = getattr(self.f, "ReadMarkers", None)
        if method is None:
            raise SonpipeError(
                "sonpy provides no marker reader for kind {}.".format(kind)
            )
        return method

    def read_markers(self, number, t0=None, t1=None, chunk=1_000_000):
        """Read markers for a marker channel as a list of dicts.

        Each entry has ``time`` (seconds) and ``code`` (list of up to four
        marker code bytes).  Text markers additionally carry ``text``.
        """
        index = self.index_for_number(number)
        kind = self.kind(index)
        if kind not in channels.MARKER_KINDS:
            raise SonpipeError(
                "Channel {} is {} (kind {}), not a marker channel.".format(
                    number, channels.kind_name(kind), kind
                )
            )
        tfrom, tupto = self._event_tick_range(t0, t1)
        marker_method = self._marker_method(kind)
        marker_name = getattr(marker_method, "__name__", "ReadMarkers")
        debuglog.log("read_markers", number=number, index=index, kind=kind,
                     t0=t0, t1=t1, tfrom=tfrom, tupto=tupto)

        out = []
        cursor = tfrom
        while cursor < tupto:
            markers = debuglog.call(marker_name, marker_method, index, chunk, cursor, tupto)
            markers = list(markers) if markers is not None else []
            if not markers:
                break
            for m in markers:
                out.append(_marker_to_dict(m, self.timebase))
            if len(markers) < chunk:
                break
            last_tick = _marker_tick(markers[-1])
            if last_tick is None:
                break
            cursor = int(last_tick) + 1
        return out


def _wave_raw_dtype(kind):
    return np.int16 if kind == channels.ADC else np.float32


def _marker_tick(marker):
    for attr in ("Tick", "tick", "Time", "time"):
        if hasattr(marker, attr):
            try:
                return int(getattr(marker, attr))
            except Exception:
                pass
    return None


def _marker_ticks(markers):
    if markers is None:
        return np.zeros(0, dtype=np.int64)
    ticks = [_marker_tick(m) for m in markers]
    ticks = [t for t in ticks if t is not None]
    return np.asarray(ticks, dtype=np.int64)


def _marker_code(marker):
    for attr in ("Code", "code"):
        if hasattr(marker, attr):
            value = getattr(marker, attr)
            try:
                return [int(c) for c in value]
            except TypeError:
                try:
                    return [int(value)]
                except Exception:
                    return []
    # Some sonpy versions expose Code1..Code4.
    codes = []
    for i in range(1, 5):
        attr = "Code{}".format(i)
        if hasattr(marker, attr):
            try:
                codes.append(int(getattr(marker, attr)))
            except Exception:
                pass
    return codes


def _marker_to_dict(marker, timebase):
    tick = _marker_tick(marker)
    entry = {
        "tick": tick,
        "time": (tick * timebase) if tick is not None else None,
        "code": _marker_code(marker),
    }
    for attr in ("Text", "text"):
        if hasattr(marker, attr):
            text = getattr(marker, attr)
            if text is not None:
                entry["text"] = str(text)
            break
    return entry
