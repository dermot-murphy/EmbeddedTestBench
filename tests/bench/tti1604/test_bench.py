"""The TTi 1604 driver against a real meter.

Run only when named, with the meter's port in the environment::

    BENCHTOOLS_TTI1604=/dev/ttyUSB0 python -m pytest tests/bench/tti1604 -v

With nothing but the meter connected (inputs open), every test that needs no
reference runs: the link, the stream, function and range selection, the
frequency gate, the echo. Name a reference for what is wired - one at a time;
see README.md - and the matching measurement test runs against it. The current
test runs only when ``BENCHTOOLS_TTI1604_DCI`` is set, because selecting a
current function puts the meter's shunt across its input.

Every test leaves the meter on DC volts, auto-ranging, so the tests may run in
any order and a failure does not strand the meter on a current range.

A markdown record of what the meter did is written at the end
(``BENCHTOOLS_TTI1604_REPORT``, default ``tti1604_bench_findings.md``), for the
bench confirmation items DMM-OPEN-01 to -08.

Traces to: DMM-FR-001 .. DMM-FR-033, DMM-FR-080, SWE4-UT-DMMBENCH.
"""

from __future__ import annotations

import math

import pytest

from benchtools.core.errors import TransportTimeoutError
from benchtools.instruments.tti1604 import Tti1604

from .conftest import DC_AMPS, DC_VOLTS, HERTZ, OHMS, REFERENCES, reference, simulator_of

pytestmark = pytest.mark.bench


@pytest.fixture(autouse=True)
def home(meter):
    """Start and finish every test on DC volts, auto-ranging."""
    yield
    try:
        meter.select_volts()
        meter.select_dc()
        meter.select_auto_range()
    except Exception:  # pylint: disable=broad-exception-caught  # pragma: no cover
        pass


def clock(meter: Tti1604) -> float:
    """The driver's clock: real time on a port, virtual on the simulator."""
    return meter._clock()


def _compare(value, expected: float, tolerance: float) -> None:
    assert value is not None, "the meter showed no number (overrange or frozen)"
    assert math.isclose(value, expected, rel_tol=tolerance, abs_tol=1e-9), (
        "measured %g, reference %g, tolerance %g%%" % (value, expected, tolerance * 100))


# ---------------------------------------------------------------------------
# The link
# ---------------------------------------------------------------------------
class TestTheLink:
    def test_the_meter_answers_and_reads(self, meter, findings):
        """DMM-FR-001 .. -006, DMM-FR-027: echo, remote mode, a reading."""
        assert meter.is_remote
        state = meter.current_state()
        findings.record("Connected", "remote mode acknowledged; front panel on %s, %s "
                        "range, %s" % (state.function, state.range_label,
                                       "auto" if state.flags["auto_range"] else "manual"),
                        "#115, DMM-FR-027")

    def test_keys_are_acknowledged_promptly(self, meter, findings):
        """DMM-FR-024. Resends on a quiet bench point at the DTR/RTS levels."""
        started = clock(meter)
        for _ in range(4):                    # Auto/Man four times: back where it was
            meter.press("auto")
        elapsed = clock(meter) - started
        findings.record("Key echo", "4 presses of Auto/Man took %.2f s" % elapsed,
                        "DMM-OPEN-07")
        assert elapsed < 4 * 0.3, "keys needed resending: check the converter's DTR/RTS levels"


# ---------------------------------------------------------------------------
# The stream
# ---------------------------------------------------------------------------
class TestTheStream:
    def test_every_frame_decodes(self, meter, findings):
        """DMM-FR-010, -028: 25 readings, ten seconds, none garbled."""
        before = meter.resynchronised_bytes
        readings = meter.read_many(25)
        dropped = meter.resynchronised_bytes - before
        findings.record("Frame decoding", "25 consecutive frames decoded; %d false "
                        "start(s) passed over" % dropped, "DMM-FR-028")
        assert all(reading.value is not None or reading.overrange for reading in readings)
        assert dropped <= 2, "a clean link should not need to resynchronise mid-stream"

    def test_the_reading_rate_is_two_and_a_half_per_second(self, meter, findings):
        meter.read()
        started = clock(meter)
        meter.read_many(10)
        interval = (clock(meter) - started) / 10
        findings.record("Reading rate", "mean %.3f s between readings on DC volts "
                        "(manual: 0.4 s)" % interval, "DMM-FR-031")
        assert 0.3 <= interval <= 0.55

    def test_the_raw_stream(self, meter, findings):
        """DMM-OPEN-01 and -03: what is on the line, byte for byte."""
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
        """DMM-FR-029: each confirmed from the readings. No current, no ohms."""
        timings = []
        steps = (
            ("ac_volts", meter.select_ac),
            ("ac_millivolts", meter.select_millivolts),
            ("dc_millivolts", meter.select_dc),
            ("dc_volts", meter.select_volts),
            ("ac_volts", meter.select_ac),
            ("frequency", meter.select_hertz),
            ("ac_volts", meter.select_volts),
            ("dc_volts", meter.select_dc),
        )
        for expected, step in steps:
            started = clock(meter)
            reading = step()
            timings.append("%s %.1f s" % (expected, clock(meter) - started))
            assert reading.function == expected
        findings.record("Function changes", "; ".join(timings), "DMM-FR-029")

    def test_every_dc_voltage_range(self, meter, findings):
        """DMM-FR-030: lock each range by full scale, then auto again."""
        seen = []
        for full_scale in (4, 40, 400, 1000):
            reading = meter.set_range(full_scale)
            assert not reading.flags["auto_range"]
            seen.append(reading.range_label)
        assert meter.select_auto_range().flags["auto_range"]
        findings.record("DC volts ranges", "locked in turn: %s; auto restored"
                        % ", ".join(seen), "DMM-FR-030")

    def test_the_frequency_gate(self, meter, findings):
        """DMM-FR-032, -033, DMM-OPEN-06: about 30 s, most of it the 10 s gate."""
        meter.select_volts()
        meter.select_ac()
        meter.select_hertz()
        started = clock(meter)
        slow = meter.set_range(4000)
        took = clock(meter) - started
        fast = meter.set_range(40000)
        findings.record("Frequency gate", "Down: gate flag %s, %s range, %.1f s to "
                        "confirm; Up: gate flag %s, %s range"
                        % (slow.status["gate_ten_seconds"], slow.range_label, took,
                           fast.status["gate_ten_seconds"], fast.range_label),
                        "DMM-OPEN-06")
        assert slow.status["gate_ten_seconds"] and not fast.status["gate_ten_seconds"]


# ---------------------------------------------------------------------------
# Against references, when they are wired
# ---------------------------------------------------------------------------
class TestAgainstReferences:
    def test_dc_voltage(self, meter, findings, tolerance):
        expected = reference(DC_VOLTS)
        if expected is None:
            pytest.skip("no DC voltage reference: set %s" % DC_VOLTS)
        meter.select_volts()
        meter.select_dc()
        reading = meter.measure()
        findings.record("DC volts", "%s on the %s range (display %s); reference %g V"
                        % (reading, reading.range_label, reading.text, expected),
                        "DMM-FR-015")
        _compare(reading.value, expected, tolerance)

    def test_resistance(self, meter, findings, tolerance):
        """DMM-FR-016 and DMM-OPEN-08: the derived multiplier, on a real display."""
        expected = reference(OHMS)
        if expected is None:
            pytest.skip("no resistor named: set %s" % OHMS)
        meter.select_ohms()
        reading = meter.measure()
        findings.record("Resistance", "%s on the %s range, display `%s`; reference %g ohm%s"
                        % (reading, reading.range_label, reading.text, expected,
                           "; " + reading.problem if reading.problem else ""),
                        "DMM-OPEN-08")
        _compare(reading.value, expected, tolerance)

    def test_dc_current(self, meter, findings, tolerance):
        """Only with consent: the shunt goes across the input."""
        expected = reference(DC_AMPS)
        if expected is None:
            pytest.skip("no current reference: set %s, with the leads in the mA and "
                        "COM sockets and in series with the load" % DC_AMPS)
        if abs(expected) > 0.4:
            meter.select_amps()
        else:
            meter.select_milliamps()
        meter.select_dc()
        reading = meter.measure()
        findings.record("DC current", "%s on the %s range; reference %g A"
                        % (reading, reading.range_label, expected), "DMM-FR-015")
        _compare(reading.value, expected, tolerance)

    def test_frequency(self, meter, findings, tolerance):
        expected = reference(HERTZ)
        if expected is None:
            pytest.skip("no frequency reference: set %s, with a signal of at least "
                        "2,000 counts on an AC volts range" % HERTZ)
        meter.select_volts()
        meter.select_ac()
        meter.select_hertz()
        reading = meter.measure()
        findings.record("Frequency", "%s on the %s range; reference %g Hz"
                        % (reading, reading.range_label, expected), "DMM-FR-017")
        _compare(reading.value, expected, tolerance)

    def test_an_open_input_on_ohms_is_an_overrange(self, meter, findings):
        """DMM-FR-018. Needs the input open: skipped when anything is named."""
        if any(reference(name) is not None for name in REFERENCES):
            pytest.skip("a reference is wired, so the input is not open")
        simulator = simulator_of(meter)
        if simulator is not None:
            simulator.set_value(math.inf)             # nothing connected
        meter.select_ohms()
        reading = meter.measure()
        if simulator is not None:
            simulator.set_value(1.0)
        findings.record("Open input on ohms", "display `%s`, overrange %s"
                        % (reading.text, reading.overrange), "DMM-FR-018")
        assert reading.overrange and reading.value is None


# ---------------------------------------------------------------------------
# Handing the meter back
# ---------------------------------------------------------------------------
class TestHandingBack:  # pylint: disable=too-few-public-methods
    def test_local_then_remote(self, meter, findings):
        """DMM-FR-007: readings stop in local mode and resume in remote."""
        meter.local()
        transport = meter.transport
        previous = transport.timeout
        transport.timeout = 1.5
        transport.discard_input()
        quiet = False
        try:
            # A frame already in flight when Local was pressed may still
            # arrive; after that the line must go quiet.
            for _ in range(3):
                try:
                    transport.read_available()
                except TransportTimeoutError:
                    quiet = True
                    break
        finally:
            transport.timeout = previous
        meter.remote()
        assert quiet, "the meter kept sending in local mode"
        assert meter.read() is not None
        findings.record("Local and remote", "readings stopped in local mode and "
                        "resumed in remote", "DMM-FR-007")
