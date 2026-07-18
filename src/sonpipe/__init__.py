"""sonpipe - a CLI bridge for reading CED Spike2 .smrx / .smr files via sonpy.

sonpipe extracts data from 64-bit ``.smrx`` (and legacy 32-bit ``.smr``) files
produced by the Cambridge Electronic Design (CED) Spike2 acquisition system and
streams it, as raw binary bytes, to standard output.  This lets a host
environment such as MATLAB drive data ingestion in chunks and reinterpret the
byte stream directly (e.g. with ``typecast``) without any text-parsing overhead.

The reader, :mod:`sonpy`, is CED's GPLv3-licensed interface to the SON64
library and is fetched automatically by ``pip install sonpipe``.  It is
intentionally *not* vendored in this repository, so sonpipe's own MIT
distribution stays free of GPL copyleft.

The command-line tools mirror the reading functions found in the NDR-matlab
``ndr.format.ced`` package:

===========================  ==============================================
sonpipe sub-command          NDR-matlab equivalent
===========================  ==============================================
``sonpipe header``           ``ndr.format.ced.read_SOMSMR_header``
``sonpipe sampleinterval``   ``ndr.format.ced.read_SOMSMR_sampleinterval``
``sonpipe read``             ``ndr.format.ced.read_SOMSMR_datafile``
===========================  ==============================================
"""

from .channels import (
    ADC,
    ADC_MARK,
    EVENT_BOTH,
    EVENT_FALL,
    EVENT_RISE,
    KIND_NAMES,
    MARKER,
    OFF,
    REAL_MARK,
    REAL_WAVE,
    TEXT_MARK,
    kind_name,
    ndr_type,
)
from .errors import SonpipeError
from .sonfile import SmrxFile

__version__ = "0.1.0"

__all__ = [
    "SmrxFile",
    "SonpipeError",
    "kind_name",
    "ndr_type",
    "KIND_NAMES",
    "OFF",
    "ADC",
    "EVENT_FALL",
    "EVENT_RISE",
    "EVENT_BOTH",
    "MARKER",
    "ADC_MARK",
    "REAL_MARK",
    "TEXT_MARK",
    "REAL_WAVE",
    "__version__",
]
