"""CED Spike2 channel-type codes and their mappings.

The integer codes below are shared by three worlds and, conveniently, agree:

* the CED ``sonpy`` ``DataType`` enum (``int(sonpy.lib.DataType.Adc) == 1``),
* the legacy sigTOOL/SON library ``kind`` numbers used by NDR-matlab's
  ``ndr.format.ced`` functions, and
* the values sonpipe emits in its ``header`` output.

Because they agree, code that consumes sonpipe's ``kind`` field behaves exactly
like the existing NDR-matlab reader, which switches on the same numbers.
"""

# --- DataType / kind codes -------------------------------------------------
OFF = 0          # channel slot is unused
ADC = 1          # integer waveform (analog, regularly sampled)
EVENT_FALL = 2   # event on a positive-to-negative transition
EVENT_RISE = 3   # event on a negative-to-positive transition
EVENT_BOTH = 4   # event on either transition ("level")
MARKER = 5       # generic marker (4 code bytes per event)
ADC_MARK = 6     # WaveMark: a marker with an attached short waveform (spike)
REAL_MARK = 7    # marker with attached real-valued data
TEXT_MARK = 8    # marker with attached text
REAL_WAVE = 9    # single-precision floating-point waveform

KIND_NAMES = {
    OFF: "Off",
    ADC: "Adc",
    EVENT_FALL: "EventFall",
    EVENT_RISE: "EventRise",
    EVENT_BOTH: "EventBoth",
    MARKER: "Marker",
    ADC_MARK: "AdcMark",
    REAL_MARK: "RealMark",
    TEXT_MARK: "TextMark",
    REAL_WAVE: "RealWave",
}

# Groupings by how the data is read.
WAVEFORM_KINDS = frozenset({ADC, REAL_WAVE})
EVENT_KINDS = frozenset({EVENT_FALL, EVENT_RISE, EVENT_BOTH})
MARKER_KINDS = frozenset({MARKER, ADC_MARK, REAL_MARK, TEXT_MARK})


def kind_name(kind):
    """Return the human-readable name for a channel ``kind`` code."""
    return KIND_NAMES.get(int(kind), "Unknown")


def ndr_type(kind):
    """Map a CED ``kind`` code to an NDR reader channel type.

    Mirrors ``ndr.reader.ced_smr.cedsmrheader2readerchanneltype`` so the names
    line up with the rest of the NDR ecosystem:

    ================  ===============
    kind              ndr_type
    ================  ===============
    Adc, RealWave     ``analog_in``
    Event*            ``event``
    Marker, AdcMark,  ``mark``
    RealMark
    TextMark          ``text``
    ================  ===============
    """
    kind = int(kind)
    if kind in WAVEFORM_KINDS:
        return "analog_in"
    if kind in EVENT_KINDS:
        return "event"
    if kind in (MARKER, ADC_MARK, REAL_MARK):
        return "mark"
    if kind == TEXT_MARK:
        return "text"
    return "unknown"
