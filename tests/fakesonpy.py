"""A minimal fake of the CED ``sonpy.lib`` module for testing.

It reproduces the parts of the ``sonpy`` API that :class:`sonpipe.SmrxFile`
relies on, so the package can be exercised on machines without CED's
proprietary binaries.  It is *not* a real SON file reader -- it serves synthetic
in-memory data whose shape matches what real sonpy returns.

The channel layout of the default fake file (mirrors a small Spike2 file):

===============  =====  =========================================
sonpy index      kind   contents
===============  =====  =========================================
0 (Spike2 #1)    Adc    ramp waveform 0,1,2,... (int16), 10 kHz
1 (Spike2 #2)    Off    unused slot
2 (Spike2 #3)    RealWave  sine-ish float waveform, 10 kHz
3 (Spike2 #4)    EventFall event ticks every 100 ticks
4 (Spike2 #5)    Marker    markers every 250 ticks
5 (Spike2 #6)    TextMark  text markers
===============  =====  =========================================
"""

import numpy as np


class DataType:
    """Integer-valued stand-in for sonpy's ``DataType`` enum."""

    Off = 0
    Adc = 1
    EventFall = 2
    EventRise = 3
    EventBoth = 4
    Marker = 5
    AdcMark = 6
    RealMark = 7
    TextMark = 8
    RealWave = 9


class _Marker:
    def __init__(self, tick, code=(0, 0, 0, 0), text=None):
        self.Tick = int(tick)
        self.Code = list(code)
        if text is not None:
            self.Text = text


# The synthetic file: per-channel description.
TIMEBASE = 1e-6            # 1 microsecond per tick
DIVIDE = 100              # 100 ticks per sample -> 10 kHz
N_SAMPLES = 1000         # waveform length in samples
MAX_TICKS = N_SAMPLES * DIVIDE

_ADC_SCALE = 2.0          # real = adc * scale/6553.6 + offset
_ADC_OFFSET = 0.5


class SonFile:
    """Fake ``SonFile`` serving the synthetic layout described above."""

    def __init__(self, path, read_only=True):
        self.path = path
        self.read_only = read_only
        self._open_error = 0
        # Waveform sample data.
        self._adc = (np.arange(N_SAMPLES) % 2000 - 1000).astype(np.int16)
        t = np.arange(N_SAMPLES) / (1.0 / (DIVIDE * TIMEBASE))
        self._realwave = np.sin(2 * np.pi * 5 * t).astype(np.float32)
        # Event / marker tick tables.
        self._event_ticks = np.arange(0, MAX_TICKS, 100, dtype=np.int64)
        self._marker_ticks = np.arange(0, MAX_TICKS, 250, dtype=np.int64)
        self._text_ticks = np.arange(0, MAX_TICKS, 400, dtype=np.int64)

    # -- file-level ---------------------------------------------------------

    def GetOpenError(self):
        return self._open_error

    def GetTimeBase(self):
        return TIMEBASE

    def MaxChannels(self):
        return 6

    def GetMaxTime(self):
        return MAX_TICKS

    def GetFileVersion(self):
        return 9

    # -- per-channel metadata ----------------------------------------------

    def ChannelType(self, chan):
        return {
            0: DataType.Adc,
            1: DataType.Off,
            2: DataType.RealWave,
            3: DataType.EventFall,
            4: DataType.Marker,
            5: DataType.TextMark,
        }[chan]

    def ChannelDivide(self, chan):
        if chan in (0, 2):
            return DIVIDE
        return 0

    def ChannelMaxTime(self, chan):
        return MAX_TICKS

    def GetIdealRate(self, chan):
        return 1.0 / (DIVIDE * TIMEBASE)

    def GetChannelScale(self, chan):
        return _ADC_SCALE

    def GetChannelOffset(self, chan):
        return _ADC_OFFSET

    def GetChannelTitle(self, chan):
        return {0: "Ramp", 2: "Sine", 3: "Trig", 4: "Mark", 5: "Notes"}.get(chan, "")

    def GetChannelUnits(self, chan):
        return {0: "V", 2: "mV"}.get(chan, "")

    def GetChannelComment(self, chan):
        return ""

    # -- reads --------------------------------------------------------------

    def _wave_slice(self, data, nMax, tFrom, tUpto, divide):
        # Sample i sits at tick i*divide; select those in [tFrom, tUpto).
        first = max(0, (tFrom + divide - 1) // divide) if tFrom > 0 else 0
        last = min(len(data), (tUpto + divide - 1) // divide)
        sel = data[first:last]
        if nMax is not None and nMax >= 0:
            sel = sel[:nMax]
        return sel

    def ReadInts(self, chan, nMax, tFrom, tUpto):
        return self._wave_slice(self._adc, nMax, tFrom, tUpto, DIVIDE)

    def ReadFloats(self, chan, nMax, tFrom, tUpto):
        return self._wave_slice(self._realwave, nMax, tFrom, tUpto, DIVIDE)

    def ReadEvents(self, chan, nMax, tFrom, tUpto):
        ticks = self._event_ticks
        sel = ticks[(ticks >= tFrom) & (ticks < tUpto)]
        return sel[:nMax]

    def ReadMarkers(self, chan, nMax, tFrom, tUpto):
        ticks = self._marker_ticks
        sel = ticks[(ticks >= tFrom) & (ticks < tUpto)][:nMax]
        return [_Marker(t, code=(int(t) % 256, 0, 0, 0)) for t in sel]

    def ReadTextMarks(self, chan, nMax, tFrom, tUpto):
        ticks = self._text_ticks
        sel = ticks[(ticks >= tFrom) & (ticks < tUpto)][:nMax]
        return [_Marker(t, code=(1, 0, 0, 0), text="note{}".format(int(t)))
                for t in sel]
