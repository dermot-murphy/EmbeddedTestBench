"""Command/reply with events arriving in between.

Traces to: BLE-FR-002, BLE-FR-060 .. BLE-FR-062, SWE4-UT-BLESESSION.
"""

from __future__ import annotations

import pytest

from benchtools.core.errors import TransportTimeoutError
from benchtools.core.transport.mock import MockTransport
from benchtools.instruments.nordic_dongle.constants import DongleError
from benchtools.instruments.nordic_dongle.session import DongleCommandError, DongleSession


class ScriptedDongle:
    """A responder returning canned lines, so a session can be driven exactly."""

    def __init__(self, script=None, stream=None):
        self.script = dict(script or {})
        self.stream = list(stream or [])
        self.written = []

    def respond(self, message: bytes):
        line = message.decode().strip()
        self.written.append(line)
        reply = self.script.get(line, "ok")
        if reply is None:
            return None
        return (reply + "\n").encode()

    def poll(self) -> bytes:
        if not self.stream:
            return b""
        return (self.stream.pop(0) + "\n").encode()


@pytest.fixture
def scripted():
    return ScriptedDongle()


@pytest.fixture
def session(scripted):
    transport = MockTransport(responder=scripted)
    transport.open()
    instance = DongleSession(transport, timeout=2.0)
    instance.start()
    yield instance
    instance.close()
    transport.close()


class TestCommands:
    def test_a_command_is_sent_and_its_reply_returned(self, session, scripted):
        reply = session.execute("ver")
        assert scripted.written == ["ver"]
        assert reply.ok

    def test_arguments_are_joined(self, session, scripted):
        session.execute("scan", "start", 3000, "name=SENS")
        assert scripted.written[-1] == "scan start 3000 name=SENS"

    def test_fields_are_parsed(self, session, scripted):
        scripted.script["time"] = "ok t=42 hz=1000000"
        assert session.execute("time").fields["t"] == "42"

    def test_a_refusal_raises_with_the_reason(self, session, scripted):
        scripted.script["connect"] = "err 5 no sensor selected"
        with pytest.raises(DongleCommandError) as caught:
            session.execute("connect")
        assert caught.value.error is DongleError.NO_SENSOR
        assert "no sensor selected" in str(caught.value)

    def test_a_refusal_can_be_tolerated(self, session, scripted):
        scripted.script["disconnect"] = "err 6 not connected"
        reply = session.execute("disconnect", allow_error=True)
        assert reply.ok is False and reply.error is DongleError.NOT_CONNECTED

    def test_a_silent_dongle_times_out_with_advice(self, session, scripted):
        scripted.script["ver"] = None
        with pytest.raises(TransportTimeoutError, match="did not answer"):
            session.execute("ver", timeout=0.05)


class TestEventsAroundCommands:
    def test_an_event_before_the_reply_is_not_mistaken_for_it(self, session, scripted):
        """The reply is the line that says ok, whatever arrived first."""
        scripted.script["list"] = "+sensor t=1 idx=0 addr=E4:1C:7B:02:9A:11 name=SENS-0A1B2C\nok sensors=1"
        reply = session.execute("list")
        assert reply.ok and reply.fields["sensors"] == "1"
        assert [event.name for event in session.take_events()] == ["sensor"]

    def test_events_are_queued_not_dropped(self, session, scripted):
        scripted.stream = ["+adv t=1000 addr=A", "+adv t=2000 addr=A"]
        session.collect(0.2)
        assert session.pending_events == 0     # collect takes them
        scripted.stream = ["+adv t=3000 addr=A"]
        session.collect(0.1)

    def test_an_event_that_arrives_before_a_command_survives_it(self, session, scripted):
        scripted.stream = ["+adv t=1000 addr=A"]
        session.collect(0.05, stop=lambda event: True)
        session.execute("ver")
        # The event was taken by collect, and the command did not disturb it.
        assert session.pending_events == 0

    def test_non_protocol_lines_are_ignored(self, session, scripted):
        scripted.script["ver"] = "SEGGER J-Link banner\nok"
        assert session.execute("ver").ok

    def test_host_time_is_recorded_on_every_event(self, session, scripted):
        scripted.stream = ["+adv t=1000 addr=A"]
        events = session.collect(0.2)
        assert events and events[0].host_time is not None
        assert events[0].timestamp_us == 1000


class TestCollectAndWait:
    def test_collect_stops_early_when_asked(self, session, scripted):
        scripted.stream = ["+adv t=%d addr=A" % (index * 1000) for index in range(100)]
        events = session.collect(5.0, stop=lambda event: event.integer("t") >= 3000)
        assert len(events) == 4
        assert len(scripted.stream) > 0        # it did not read them all

    def test_wait_for_event_returns_a_queued_one(self, session, scripted):
        scripted.stream = ["+conn t=1 state=ready interval_us=30000"]
        event = session.wait_for_event("conn", timeout=0.5)
        assert event.integer("interval_us") == 30000

    def test_wait_for_event_applies_the_match(self, session, scripted):
        scripted.stream = [
            "+conn t=1 state=linked",
            "+conn t=2 state=ready interval_us=30000",
        ]
        event = session.wait_for_event(
            "conn", timeout=0.5, match=lambda item: item.get("state") == "ready"
        )
        assert event.timestamp_us == 2

    def test_waiting_for_an_event_that_never_comes(self, session):
        with pytest.raises(TransportTimeoutError, match="no '\\+conn' event"):
            session.wait_for_event("conn", timeout=0.05)

    def test_take_events_can_filter_by_name(self, session, scripted):
        """Taking the advertising reports must leave the notifications alone."""
        scripted.stream = ["+adv t=1 addr=A", "+rx t=2 data=ff", "+adv t=3 addr=A"]
        collected = session.collect(0.3, stop=lambda event: event.integer("t") >= 3)
        for event in collected:
            session._events.append(event)       # put them back, in order
        assert [event.timestamp_us for event in session.take_events("adv")] == [1, 3]
        assert [event.name for event in session.take_events()] == ["rx"]

    def test_drop_notices_are_counted(self, session, scripted):
        """The dongle telling us it lost lines is the only way to know."""
        scripted.stream = ["+drop t=5 count=3"]
        session.collect(0.2)
        assert session.dropped_notices == 3


class TestLogging:
    def test_both_directions_are_logged(self, session, scripted, tmp_path):
        path = tmp_path / "session.log"
        session.log_to(str(path))
        scripted.script["ver"] = "ok Nordic PCA10059 proto=1.0"
        session.execute("ver")
        session.stop_log()

        text = path.read_text()
        assert "> ver" in text
        assert "< ok Nordic PCA10059 proto=1.0" in text
        assert "session opened" in text and "session closed" in text

    def test_the_log_is_flushed_per_line(self, session, scripted, tmp_path):
        """A session that then hangs must still have a complete log."""
        path = tmp_path / "session.log"
        session.log_to(str(path))
        session.execute("ver")
        assert "> ver" in path.read_text()      # still open

    def test_a_note_can_be_written(self, session, tmp_path):
        path = tmp_path / "session.log"
        session.log_to(str(path))
        session.note("starting the profile")
        assert "starting the profile" in path.read_text()

    def test_the_log_path_is_reported(self, session, tmp_path):
        path = str(tmp_path / "session.log")
        assert session.log_to(path) == path
        assert session.log_path == path
        session.stop_log()
        assert session.log_path is None

    def test_stopping_twice_is_harmless(self, session, tmp_path):
        session.log_to(str(tmp_path / "session.log"))
        session.stop_log()
        session.stop_log()

    def test_events_reach_the_log_too(self, session, scripted, tmp_path):
        path = tmp_path / "session.log"
        session.log_to(str(path))
        scripted.stream = ["+adv t=1000 addr=E4:1C:7B:02:9A:11 rssi=-62"]
        session.collect(0.2)
        assert "+adv t=1000" in path.read_text()
