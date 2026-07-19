"""Command-line interface for sonpipe.

Sub-commands
------------
``header``          Print JSON metadata for the file and all channels.
``sampleinterval``  Print JSON sample-interval info for one channel.
``read``            Stream channel data.  Waveforms and events are written as
                    raw little-endian binary by default (for fast ingestion by
                    MATLAB's ``typecast``); markers are written as JSON.

Design notes
------------
Metadata commands (``header``, ``sampleinterval``) emit JSON on stdout because
they are called rarely and their volume is tiny.  The performance-critical
``read`` command emits *raw bytes only* on stdout so a host such as MATLAB can
capture the pipe and reinterpret it with ``typecast`` -- no number-to-text and
back conversion.  Anything informational is written to stderr so it never
pollutes the binary stream.
"""

import argparse
import json
import math
import sys

import numpy as np

from . import __version__, channels, debuglog
from .errors import SonpipeError
from .sonfile import SmrxFile

_DTYPES = {
    "double": "<f8",
    "single": "<f4",
    "int16": "<i2",
    "int32": "<i4",
    "int64": "<i8",
}

# The command-line bridge streams data through a pipe, which is comparatively
# slow for very large reads.  Warn (but do not refuse) past this many bytes so
# users are nudged toward chunked reads (--start/--count or --t0/--t1).
WARN_BYTES = 50 * 1024 * 1024


def _itemsize(dtype):
    return np.dtype(_DTYPES[dtype]).itemsize


def _warn_size(nbytes, args, label):
    if getattr(args, "no_size_warning", False):
        return
    if nbytes is not None and nbytes > WARN_BYTES:
        sys.stderr.write(
            "sonpipe: warning: reading ~{:.1f} MB of {} (> {} MB). The "
            "command-line bridge can be slow for large reads; consider reading "
            "in smaller blocks with --start/--count or --t0/--t1 (suppress this "
            "warning with --no-size-warning).\n".format(
                nbytes / 1048576.0, label, WARN_BYTES // 1048576
            )
        )


def _open(path):
    return SmrxFile(path)


def _dump_json(obj, pretty):
    if pretty:
        json.dump(obj, sys.stdout, indent=2, sort_keys=False)
    else:
        json.dump(obj, sys.stdout, separators=(",", ":"))
    sys.stdout.write("\n")
    # Flush before the caller closes the file, so the payload is delivered even
    # if sonpy aborts while its handle is being released.
    sys.stdout.flush()


# --------------------------------------------------------------------------
# sub-command handlers
# --------------------------------------------------------------------------

def cmd_header(args):
    with _open(args.file) as smrx:
        out = {
            "fileinfo": smrx.file_info(),
            "channelinfo": smrx.all_channel_info(),
        }
        _dump_json(out, args.pretty)
        return 0


def cmd_sampleinterval(args):
    with _open(args.file) as smrx:
        info = smrx.channel_info(args.channel)
        if info is None:
            raise SonpipeError("Channel {} is not recorded in the file.".format(args.channel))
        sample_interval = info.get("sampleinterval")
        out = {
            "channel": args.channel,
            "kind": info["kind"],
            "kind_name": info["kind_name"],
            "sampleinterval": sample_interval,
            "samplerate": info.get("samplerate"),
            "total_samples": info.get("num_samples"),
            "total_time": info.get("max_time"),
        }
        _dump_json(out, args.pretty)
        return 0


def _write_binary(arr, dtype, endian):
    np_dtype = np.dtype(_DTYPES[dtype])
    if endian == "big":
        np_dtype = np_dtype.newbyteorder(">")
    elif endian == "native":
        np_dtype = np_dtype.newbyteorder("=")
    # else little (the explicit default already encoded in _DTYPES)
    buf = np.ascontiguousarray(arr.astype(np_dtype, copy=False))
    sys.stdout.buffer.write(buf.tobytes())
    sys.stdout.buffer.flush()
    return buf.size


def cmd_read(args):
    with _open(args.file) as smrx:
        info = smrx.channel_info(args.channel)
        if info is None:
            raise SonpipeError("Channel {} is not recorded in the file.".format(args.channel))
        kind = info["kind"]

        if kind in channels.WAVEFORM_KINDS:
            return _read_waveform(smrx, args, info)
        if kind in channels.EVENT_KINDS:
            return _read_events(smrx, args, info)
        if kind in channels.MARKER_KINDS:
            return _read_markers(smrx, args, info)
        raise SonpipeError("Unsupported channel kind {} ({}).".format(kind, info["kind_name"]))


def _estimate_wave_samples(args, info):
    """Best-effort estimate of how many samples a waveform read will return."""
    if args.count is not None:
        return max(0, args.count)
    samplerate = info.get("samplerate")
    num_samples = info.get("num_samples") or 0
    start = args.start or 0
    if args.t0 is not None or args.t1 is not None:
        if not samplerate:
            return None
        t0 = args.t0 or 0.0
        if args.t1 is None or math.isinf(args.t1):
            return max(0, num_samples)
        return max(0, int((args.t1 - t0) * samplerate))
    return max(0, num_samples - start)


def _read_waveform(smrx, args, info):
    scaled = not args.raw
    dtype = args.dtype if args.dtype is not None else ("int16" if args.raw else "double")

    if not args.json:
        est_samples = _estimate_wave_samples(args, info)
        if est_samples is not None:
            _warn_size(est_samples * _itemsize(dtype), args, "waveform samples")

    data = smrx.read_waveform(
        args.channel,
        start=args.start,
        count=args.count,
        t0=args.t0,
        t1=args.t1,
        scaled=scaled,
    )
    if args.json:
        _dump_json({
            "channel": args.channel,
            "kind": info["kind"],
            "samplerate": info.get("samplerate"),
            "count": int(data.size),
            "data": data.tolist(),
        }, args.pretty)
        return 0

    n = _write_binary(data, dtype, args.endian)
    sys.stderr.write("sonpipe: wrote {} samples ({}) for channel {}\n".format(
        n, dtype, args.channel))
    sys.stderr.flush()  # sentinel must reach disk before the file handle closes
    return 0


def _read_events(smrx, args, info):
    times = smrx.read_events(args.channel, t0=args.t0, t1=args.t1)
    dtype = args.dtype or "double"
    _warn_size(times.size * _itemsize(dtype), args, "event times")
    if args.json:
        _dump_json({
            "channel": args.channel,
            "kind": info["kind"],
            "count": int(times.size),
            "times": times.tolist(),
        }, args.pretty)
        return 0
    n = _write_binary(times, dtype, args.endian)
    sys.stderr.write("sonpipe: wrote {} event times ({}) for channel {}\n".format(
        n, dtype, args.channel))
    sys.stderr.flush()  # sentinel must reach disk before the file handle closes
    return 0


def _read_markers(smrx, args, info):
    markers = smrx.read_markers(args.channel, t0=args.t0, t1=args.t1)
    # Rough size estimate: time + 4 code bytes + optional text per marker.
    _warn_size(len(markers) * 48, args, "markers")
    # Markers are heterogeneous (times + code bytes + optional text); JSON only.
    _dump_json({
        "channel": args.channel,
        "kind": info["kind"],
        "kind_name": info["kind_name"],
        "count": len(markers),
        "markers": markers,
    }, args.pretty)
    return 0


def cmd_channels(args):
    """Convenience listing: one line per channel (human/script friendly)."""
    with _open(args.file) as smrx:
        for info in smrx.all_channel_info():
            sr = info.get("samplerate")
            sr_str = "{:.4f} Hz".format(sr) if sr else "-"
            sys.stdout.write("{number}\t{kind_name}\t{ndr_type}\t{sr}\t{title}\n".format(
                number=info["number"],
                kind_name=info["kind_name"],
                ndr_type=info["ndr_type"],
                sr=sr_str,
                title=info.get("title", ""),
            ))
        sys.stdout.flush()
        return 0


# --------------------------------------------------------------------------
# argument parsing
# --------------------------------------------------------------------------

def build_parser():
    parser = argparse.ArgumentParser(
        prog="sonpipe",
        description=(
            "Stream data from CED Spike2 .smrx/.smr files as raw binary "
            "(via sonpy) for fast ingestion by MATLAB and other tools."
        ),
    )
    parser.add_argument("--version", action="version",
                        version="sonpipe {}".format(__version__))
    sub = parser.add_subparsers(dest="command", required=True)

    p_header = sub.add_parser(
        "header", help="print JSON metadata for the file and every channel")
    p_header.add_argument("file", help="path to a .smrx or .smr file")
    p_header.add_argument("--pretty", action="store_true",
                          help="pretty-print the JSON output")
    p_header.set_defaults(func=cmd_header)

    p_si = sub.add_parser(
        "sampleinterval",
        help="print JSON sample-interval / sample-rate info for one channel")
    p_si.add_argument("file", help="path to a .smrx or .smr file")
    p_si.add_argument("-c", "--channel", type=int, required=True,
                      help="Spike2 channel number (1-based)")
    p_si.add_argument("--pretty", action="store_true")
    p_si.set_defaults(func=cmd_sampleinterval)

    p_read = sub.add_parser(
        "read",
        help="stream channel data (raw binary for waveforms/events, JSON for markers)")
    p_read.add_argument("file", help="path to a .smrx or .smr file")
    p_read.add_argument("-c", "--channel", type=int, required=True,
                        help="Spike2 channel number (1-based)")
    # Sample-based chunking (waveforms).
    p_read.add_argument("--start", type=int, default=None,
                        help="first sample index (0-based) for waveform reads")
    p_read.add_argument("--count", type=int, default=None,
                        help="number of samples to read for waveform reads")
    # Time-based windowing (all channel types).
    p_read.add_argument("--t0", type=float, default=None,
                        help="start time in seconds (default: start of file)")
    p_read.add_argument("--t1", type=float, default=None,
                        help="end time in seconds (default: end of file)")
    p_read.add_argument("--raw", action="store_true",
                        help="for Adc waveforms, emit raw int16 ADC values "
                             "instead of scaled real units")
    p_read.add_argument("--dtype", choices=sorted(_DTYPES), default=None,
                        help="binary output dtype (default: double for scaled "
                             "waveforms/events, int16 for --raw)")
    p_read.add_argument("--endian", choices=("little", "big", "native"),
                        default="little",
                        help="byte order of the binary output (default: little)")
    p_read.add_argument("--json", action="store_true",
                        help="emit JSON instead of raw binary (debugging)")
    p_read.add_argument("--no-size-warning", action="store_true",
                        help="suppress the >50 MB slow-read warning")
    p_read.add_argument("--pretty", action="store_true")
    p_read.set_defaults(func=cmd_read)

    p_ch = sub.add_parser(
        "channels", help="print a tab-separated one-line-per-channel listing")
    p_ch.add_argument("file", help="path to a .smrx or .smr file")
    p_ch.set_defaults(func=cmd_channels)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if debuglog.enabled():
        shown = argv if argv is not None else sys.argv[1:]
        debuglog.log("main", command=getattr(args, "command", None),
                     argv=" ".join(str(a) for a in shown))
    try:
        rc = args.func(args)
        # A clean-finish breadcrumb: if the log ends here, the command completed
        # normally and any abort happened during interpreter shutdown; if the log
        # instead ends on a dangling '-> <sonpy call>', that call is the crash.
        debuglog.log("done", command=getattr(args, "command", None), rc=rc)
        return rc
    except SonpipeError as exc:
        sys.stderr.write("sonpipe: error: {}\n".format(exc))
        return 2
    except BrokenPipeError:  # pragma: no cover - consumer closed the pipe early
        return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
