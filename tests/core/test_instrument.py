"""The generic instrument lifecycle.

Extracted from the SCPI base because a debug probe, a BLE dongle and a legacy
meter share the lifecycle and share nothing else. The runner relies only on this
contract, so anything satisfying it is usable on a bench.

Traces to: CORE-FR-012 .. CORE-FR-016, SWE4-UT-INSTRUMENT.
"""

from __future__ import annotations

import pytest

from benchtools.core.errors import InstrumentError
from benchtools.core.instrument import Instrument, InstrumentIdentity


class FakeInstrument(Instrument):
    """A minimal non-SCPI instrument, as a new driver would be."""

    MODEL_NAME = "Fake Widget"

    def __init__(self, events=(), **kwargs):
        super().__init__(**kwargs)
        self._events = list(events)
        self._open_count = 0
        self._close_count = 0
        self._post_open_count = 0
        self._is_open = False
        self.identity_reads = 0

    def _open(self):
        self._open_count += 1
        self._is_open = True

    def _close(self):
        self._close_count += 1
        self._is_open = False

    @property
    def is_open(self):
        return self._is_open

    def _post_open(self):
        self._post_open_count += 1

    def _read_identity(self):
        self.identity_reads += 1
        return InstrumentIdentity(
            raw="ACME WIDGET v2 sn:12345",
            manufacturer="ACME", model="WIDGET", serial_number="12345", firmware="v2",
        )

    def read_event_queue(self):
        events, self._events = self._events, []
        return events


class TestIdentity:
    def test_fields_can_be_given_directly(self):
        """A probe reports a serial number and firmware, not an *IDN? string."""
        identity = InstrumentIdentity(raw="raw", model="J-Link V11", serial_number="80101")
        assert identity.model == "J-Link V11" and identity.serial_number == "80101"

    def test_from_idn_parses_four_fields(self):
        identity = InstrumentIdentity.from_idn("A,B,C,D")
        assert (identity.manufacturer, identity.model) == ("A", "B")
        assert (identity.serial_number, identity.firmware) == ("C", "D")

    def test_from_idn_tolerates_missing_fields(self):
        assert InstrumentIdentity.from_idn("A,B").firmware == ""

    def test_str_is_the_raw_text(self):
        assert str(InstrumentIdentity(raw="anything")) == "anything"


class TestLifecycle:
    def test_initialise_opens_then_runs_the_hook(self):
        instrument = FakeInstrument()
        instrument.initialise()
        assert instrument._open_count == 1
        assert instrument._post_open_count == 1
        assert instrument.is_open

    def test_close_releases(self):
        instrument = FakeInstrument()
        instrument.initialise()
        instrument.close()
        assert instrument._close_count == 1 and not instrument.is_open

    def test_close_never_raises(self):
        class Awkward(FakeInstrument):
            def _close(self):
                raise RuntimeError("the USB cable was pulled")

        instrument = Awkward()
        instrument.initialise()
        instrument.close()          # must not propagate

    def test_context_manager_initialises_once(self):
        instrument = FakeInstrument()
        with instrument:
            assert instrument._open_count == 1
            with instrument:
                pass                # already initialised
        assert instrument._open_count == 1

    def test_context_manager_closes_on_an_exception(self):
        instrument = FakeInstrument()
        with pytest.raises(ValueError):
            with instrument:
                raise ValueError("boom")
        assert instrument._close_count == 1


class TestIdentityCaching:
    def test_identity_is_cached(self):
        instrument = FakeInstrument()
        instrument.identify()
        instrument.identify()
        assert instrument.identity_reads == 1

    def test_refresh_re_reads(self):
        instrument = FakeInstrument()
        instrument.identify()
        instrument.identify(refresh=True)
        assert instrument.identity_reads == 2

    def test_identity_returns_the_raw_string(self):
        assert FakeInstrument().identity() == "ACME WIDGET v2 sn:12345"

    def test_convenience_properties(self):
        instrument = FakeInstrument()
        assert instrument.manufacturer == "ACME"
        assert instrument.model == "WIDGET"
        assert instrument.serial_number == "12345"
        assert instrument.firmware == "v2"

    def test_unknown_model_falls_back(self):
        class Anonymous(FakeInstrument):
            def _read_identity(self):
                return InstrumentIdentity(raw="?")

        assert Anonymous().model == "unknown"


class TestErrorChecking:
    def test_no_error_queue_by_default(self):
        class Plain(Instrument):
            def _open(self):
                pass

            def _close(self):
                pass

            @property
            def is_open(self):
                return True

            def _read_identity(self):
                return InstrumentIdentity(raw="x")

        Plain().check_errors()          # must not raise

    def test_reported_events_raise(self):
        instrument = FakeInstrument(events=[(-113, "Undefined header")])
        with pytest.raises(InstrumentError, match="Fake Widget") as info:
            instrument.check_errors()
        assert info.value.events[0][0] == -113

    def test_after_configuration_respects_the_flag(self):
        instrument = FakeInstrument(events=[(-1, "x")], auto_check_errors=False)
        instrument._after_configuration()          # must not raise
        instrument.auto_check_errors = True
        instrument._events = [(-1, "x")]
        with pytest.raises(InstrumentError):
            instrument._after_configuration()


class TestSubclassContract:
    def test_unimplemented_hooks_raise(self):
        class Incomplete(Instrument):
            pass

        with pytest.raises(NotImplementedError):
            Incomplete()._open()
        with pytest.raises(NotImplementedError):
            Incomplete()._read_identity()

    def test_scpi_instrument_is_an_instrument(self):
        from benchtools.core.scpi import ScpiInstrument

        assert issubclass(ScpiInstrument, Instrument)

    def test_the_probe_is_an_instrument_but_not_scpi(self):
        """The split exists so a non-SCPI driver is still a bench instrument."""
        from benchtools.core.scpi import ScpiInstrument
        from benchtools.instruments.jlink import JLinkProbe

        assert issubclass(JLinkProbe, Instrument)
        assert not issubclass(JLinkProbe, ScpiInstrument)
