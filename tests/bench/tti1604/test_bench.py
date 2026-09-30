"""The TTi 1604 driver against a real meter.

Run only when named, with the meter's port in the environment::

    BENCHTOOLS_TTI1604=/dev/ttyUSB1 pytest tests/bench/tti1604 -v

With nothing but the meter connected (inputs open), every test that needs no
reference runs: the link, the stream, function and range selection, the
frequency gate, the echo. Name a reference for what is wired - one at a time;
see README.md - and the matching measurement test runs against it. The current
tests run only when ``BENCHTOOLS_TTI1604_DCI`` is set, because selecting a
current function puts the meter's shunt across its input (DMM-NFR-002).

Every test leaves the meter on DC volts, auto-ranging, so the tests may run in
any order and a failure does not strand the meter on a current range.

A markdown record of what the meter did is written at the end
(``BENCHTOOLS_TTI1604_REPORT``, default ``tti1604_bench_findings.md``), for the
bench confirmation items DMM-OPEN-01 to -07.

Traces to: DMM-FR-001 .. DMM-FR-033, DMM-FR-070, DMM-FR-080, DMM-NFR-002, SWE4-UT-DMMBENCH.
"""

from __future__ import annotations

import math

import pytest

from benchtools.core.errors import MeasurementError, TransportTimeoutError
from benchtools.instruments.tti1604 import Function, Key, Tti1604

from .conftest import DC_AMPS, DC_VOLTS, HERTZ, OHMS, reference

pytestmark = pytest.mark.bench

#: Functions safe to select with the input open or across a low-voltage
#: reference: no current function, and no resistance (which drives a test
#: current into whatever is connected) unless a resistor is named.
_SAFE_TOUR = (
    Function.AC_VOLTS,
    Function.DC_MILLIVOLTS,
    Function.AC_MILLIVOLTS,
    Function.FREQUENCY,
    Function.DC_VOLTS,
)


@pytest.fixture(autouse=True)
def home(meter):
    """Start and finish every test on DC volts, auto-ranging."""
    yield
    try:
        meter.select_function(Function.DC_VOLTS)
        meter.set_auto_range()
    except Exception:                                   # pragma: no cover - bench only
        pass


def clock(meter: Tti1604) -> float:
    """The driver's clock: real time on a port, virtual on the simulator."""
    return meter._clock()


# ---------------------------------------------------------------------------
# The link
# ---------------------------------------------------------------------------
class TestTheLink:
    def test_the_meter_answers_and_reads(self, meter, findings):
        """DMM-FR-001, -004, -005: echo, remote mode, a reading."""
        identity = meter.identify()
        assert identity.model == "1604"
        state = meter.current_state()
        findings.record("Connected", "remote mode acknowledged; front panel on %s, %s "
                        "range, %s" % (state.function, state.range_label,
                                       "auto" if state.auto_range else "manual"),
                        "DMM-FR-004")

    def test_keys_are_acknowledged_first_time(self, meter, findings):
        """DMM-FR-002. Resends on a quiet bench point at the DTR/RTS levels."""
        attempts = []
        started = clock(meter)
        for _ in range(4):                    # Auto/Man four times: back where it was
            attempts.append(meter.press(Key.AUTO))
        elapsed = clock(meter) - started
        findings.record("Key echo", "4 presses of Auto/Man took %.2f s; attempts per "
                        "key %s" % (elapsed, attempts), "DMM-OPEN-07")
        assert max(attempts) <= 2, (
            "keys needed %s attempts: the link is marginal - check the converter's "
            "DTR and RTS levels (DMM-OPEN-07)" % attempts)


# ---------------------------------------------------------------------------
# The stream
# ---------------------------------------------------------------------------
class TestTheStream:
    def test_every_frame_decodes(self, meter, findings):
        """DMM-FR-010, -011: 25 readings, ten seconds, none garbled."""
        before = meter.resynchronised_bytes
        readings = meter.read_many(25)
        dropped = meter.resynchronised_bytes - before
        findings.record("Frame decoding", "25 consecutive frames decoded; %d byte(s) "
                        "dropped while resynchronising" % dropped, "DMM-FR-011")
        assert all(reading.numeric or reading.overload for reading in readings)
        assert dropped <= 10, "a clean link should not need to resynchronise mid-stream"

    def test_the_reading_rate_is_two_and_a_half_per_second(self, meter, findings):
        readings = meter.read_many(11)
        interval = (readings[-1].received_at - readings[0].received_at) / 10
        findings.record("Reading rate", "mean %.3f s between readings on DC volts "
                        "(manual: 0.4 s)" % interval, "AD-25")
        assert 0.3 <= interval <= 0.55

    def test_the_raw_stream(self, meter, findings):
        """DMM-OPEN-01 and -06: what is on the line, byte for byte."""
        transport = meter.transport
        previous = transport.timeout
        transport.timeout = 0.5
        data = bytearray()
        transport.discard_input()
        deadline = clock(meter) + 2.0
        try:
            while clock(meter) < deadline:
                try:
                    data += transport.read_available()
                except TransportTimeoutError:
                    pass
        finally:
            transport.timeout = previous
        starts = [index for index, value in enumerate(data) if value == 0x0D]
        gaps = sorted({later - earlier for earlier, later in zip(starts, starts[1:])})
        nul_after = sum(1 for index in starts
                        if index + 10 < len(data) and data[index + 10] == 0x00)
        findings.record(
            "Raw stream", "%d bytes in 2 s; distances between carriage returns %s; "
            "a NUL after %d of %d frames. First 40 bytes: `%s`"
            % (len(data), gaps, nul_after, len(starts), bytes(data[:40]).hex()),
            "DMM-OPEN-01")
        assert len(starts) >= 3


# ---------------------------------------------------------------------------
# Function and range
# ---------------------------------------------------------------------------
class TestFunctionAndRange:
    def test_a_tour_of_the_safe_functions(self, meter, findings):
        """DMM-FR-020, AD-24: each confirmed from the readings."""
        timings = []
        for function in _SAFE_TOUR:
            started = clock(meter)
            reading = meter.select_function(function)
            timings.append("%s %.1f s" % (function, clock(meter) - started))
            assert reading.function == function
        findings.record("Function changes", "; ".join(timings), "AD-24")

    def test_every_dc_voltage_range(self, meter, findings):
        """DMM-FR-022: lock each range by full scale, then auto again."""
        seen = []
        for full_scale in (4, 40, 400, 1000):
            reading = meter.set_range(full_scale)
            assert not reading.auto_range
            seen.append(reading.range_label)
        assert meter.set_auto_range().auto_range
        findings.record("DC volts ranges", "locked in turn: %s; auto restored"
                        % ", ".join(seen), "DMM-FR-022")

    def test_the_frequency_gate(self, meter, findings):
        """DMM-FR-023, D-41, DMM-OPEN-04: about 30 s, most of it the 10 s gate."""
        meter.select_function(Function.FREQUENCY)
        started = clock(meter)
        slow = meter.set_range(4000)
        took = clock(meter) - started
        fast = meter.set_range(40000)
        findings.record("Frequency gate", "Down: gate flag %s, %s range, %.1f s to "
                        "confirm; Up: gate flag %s, %s range"
                        % (slow.gate_10s, slow.range_label, took,
                           fast.gate_10s, fast.range_label), "DMM-OPEN-04")
        assert slow.gate_10s and not fast.gate_10s


# ---------------------------------------------------------------------------
# Against references, when they are wired
# ---------------------------------------------------------------------------
def _compare(value: float, expected: float, tolerance: float) -> None:
    assert math.isclose(value, expected, rel_tol=tolerance, abs_tol=1e-9), (
        "measured %g, reference %g, tolerance %g%%" % (value, expected, tolerance * 100))


class TestAgainstReferences:
    def test_dc_voltage(self, meter, findings, tolerance):
        expected = reference(DC_VOLTS)
        if expected is None:
            pytest.skip("no DC voltage reference: set %s" % DC_VOLTS)
        value = meter.measure_dc_voltage()
        reading = meter.last_reading
        findings.record("DC volts", "%g V on the %s range (display %s); reference %g V"
                        % (value, reading.range_label, reading.display, expected),
                        "DMM-FR-033")
        _compare(value, expected, tolerance)

    def test_resistance(self, meter, findings, tolerance):
        """DMM-FR-012 and DMM-OPEN-02: the derived multiplier, on a real display."""
        expected = reference(OHMS)
        if expected is None:
            pytest.skip("no resistor named: set %s" % OHMS)
        value = meter.measure_resistance()
        reading = meter.last_reading
        findings.record("Resistance", "%g ohm on the %s range, display `%s`; reference "
                        "%g ohm" % (value, reading.range_label, reading.display, expected),
                        "DMM-OPEN-02")
        _compare(value, expected, tolerance)

    def test_dc_current(self, meter, findings, tolerance):
        """Only with consent: the mA socket's shunt goes across the input."""
        expected = reference(DC_AMPS)
        if expected is None:
            pytest.skip("no current reference: set %s, with the leads in the mA and "
                        "COM sockets and in series with the load" % DC_AMPS)
        socket = "10A" if abs(expected) > 0.4 else "mA"
        value = meter.measure_dc_current(socket=socket)
        reading = meter.last_reading
        findings.record("DC current", "%g A on the %s range (%s socket); reference %g A"
                        % (value, reading.range_label, socket, expected), "DMM-FR-033")
        _compare(value, expected, tolerance)

    def test_frequency(self, meter, findings, tolerance):
        expected = reference(HERTZ)
        if expected is None:
            pytest.skip("no frequency reference: set %s, with a signal of at least "
                        "2,000 counts on an AC volts range" % HERTZ)
        value = meter.measure_frequency()
        findings.record("Frequency", "%g Hz on the %s range; reference %g Hz"
                        % (value, meter.last_reading.range_label, expected), "DMM-FR-023")
        _compare(value, expected, tolerance)

    def test_an_open_input_on_ohms_is_an_overload_not_a_number(self, meter, findings):
        """DMM-FR-031. Needs the input open: skipped when anything is named."""
        if any(reference(name) is not None for name in (DC_VOLTS, OHMS, DC_AMPS, HERTZ)):
            pytest.skip("a reference is wired, so the input is not open")
        with pytest.raises(MeasurementError, match="OFL"):
            meter.measure_resistance()
        findings.record("Open input on ohms", "OFL raised as MeasurementError",
                        "DMM-FR-014, -031")


# ---------------------------------------------------------------------------
# Handing the meter back
# ---------------------------------------------------------------------------
class TestHandingBack:
    def test_local_then_remote(self, meter, findings):
        """DMM-FR-006: readings stop in local mode and resume in remote."""
        meter.local()
        transport = meter.transport
        previous = transport.timeout
        transport.timeout = 1.5
        transport.discard_input()
        quiet = False
        try:
            # A frame already in flight when Local was pressed may still arrive;
            # after that the line must go quiet.
            for _ in range(3):
                try:
                    transport.read_available()
                except TransportTimeoutError:
                    quiet = True
                    break
        finally:
            transport.timeout = previous
        assert quiet, "the meter kept sending in local mode"
        meter.remote()
        assert meter.read().numeric or meter.last_reading.overload
        findings.record("Local and remote", "readings stopped in local mode and "
                        "resumed in remote", "DMM-FR-006")
