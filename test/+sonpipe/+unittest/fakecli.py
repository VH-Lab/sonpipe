#!/usr/bin/env python3
"""A stand-in for the ``sonpipe`` command-line tool, for MATLAB unit tests.

It runs the *real* sonpipe CLI code, but injects the test fake sonpy module in
place of CED's proprietary ``sonpy``.  That way the MATLAB ``+sonpipe`` wrappers
can be exercised end-to-end (argument construction, JSON decoding, binary
typecast, channel dispatch, time-vector math) on any machine, without the CED
binaries and without a Python/MATLAB in-process bridge.

The file served is synthetic: contents are ignored and the channel layout comes
from ``tests/fakesonpy.py`` (Spike2 #1 Adc, #3 RealWave, #4 EventFall,
#5 Marker, #6 TextMark).
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
# .../repo/test/+sonpipe/+unittest/fakecli.py  ->  repo is three levels up.
_REPO = os.path.abspath(os.path.join(_HERE, os.pardir, os.pardir, os.pardir))

sys.path.insert(0, os.path.join(_REPO, "src"))     # the sonpipe package
sys.path.insert(0, os.path.join(_REPO, "tests"))   # fakesonpy

import fakesonpy  # noqa: E402
from sonpipe import cli, sonfile  # noqa: E402

# Force the CLI to use the fake reader instead of importing CED's sonpy.
sonfile.load_sonpy = lambda: fakesonpy


if __name__ == "__main__":
    sys.exit(cli.main())
