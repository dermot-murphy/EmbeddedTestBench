"""RTT reading, writing, expecting and logging.

Traces to: JLINK-FR-050 .. JLINK-FR-055, SWE4-UT-RTT.
"""

from __future__ import annotations

import threading
import time

import pytest

from benchtools.core.errors import ConfigurationError
from benchtools.instruments.jlink import ProbeLimits, RttTimeout
from benchtools.instruments.jlink.rtt import RttClient, SimulatedRttBackend

from .conftest import END_LOCATION


@pytest.fixture
def client(simulator):
    simulator.connected = True
    simulator.breakpoints[1] = {"location": END_LOCATION, "enabled": True}
    instance = RttClient(SimulatedRttBackend(simulator))
    instance.start()
    yield instance, simulator
    instance.stop()


class TestReading:
    def test_lines_arrive_when_the_target_runs(self, client):
        instance, simulator = client
        simulator.resume()
        assert instance.read_lines() == [
            "sensor: start", "sensor: done mv=1234", "sensor: count=7",
        ]

    def test_reads_consume(self, client):
        instance, simulator = client
        simulator.resume()
        assert instance.read_lines()
        assert instance.read_lines() == []

    def test_read_returns_text(self, client):
        instance, simulator = client
        simulator.resume()
        assert "sensor: start\n" in instance.read()

    def test_read_line_waits(self, client):
        instance, simulator = client
        simulator.resume()
        assert instance.read_line(timeout=1.0) == "sensor: start"

    def test_read_line_returns_none_on_timeout(self, client):
        instance, _ = client
        assert instance.read_line(timeout=0.1) is None

    def test_history_survives_consuming_reads(self, client):
        """A test that consumes lines as it goes still needs the transcript."""
        instance, simulator = client
        simulator.resume()
        instance.read_lines()
        simulator.resume()
        instance.read_lines()
        assert len(instance.history) == 7
        assert instance.history[0] == "sensor: start"

    def test_pending_count(self, client):
        instance, simulator = client
        simulator.resume()
        assert instance.pending_count == 3


class TestWritingAndExpecting:
    def test_command_and_reply(self, client):
        instance, _ = client
        assert instance.command("version", r"(\d+\.\d+\.\d+)").group(1) == "1.4.2"

    def test_write_reaches_the_target(self, client):
        instance, simulator = client
        instance.write("status")
        instance.read_lines()
        assert "status" in simulator.rtt_in

    def test_expect_finds_a_pattern(self, client):
        instance, simulator = client
        simulator.resume()
        assert instance.expect(r"mv=(\d+)").group(1) == "1234"

    def test_expect_timeout_reports_what_arrived(self, client):
        """"Timed out" alone never tells you why."""
        instance, simulator = client
        simulator.resume()
        with pytest.raises(RttTimeout) as info:
            instance.expect("never-appears", timeout=0.2)
        assert "sensor: start" in str(info.value)
        assert "never-appears" in str(info.value)

    def test_command_discards_older_lines(self, client):
        instance, simulator = client
        simulator.resume()                       # noise before the command
        assert instance.command("version", r"1\.4\.2")


class TestLogging:
    def test_log_file_is_written_and_flushed(self, simulator, tmp_path):
        """Flushed per write, so the log survives the run that crashed."""
        simulator.connected = True
        simulator.breakpoints[1] = {"location": END_LOCATION, "enabled": True}
        path = tmp_path / "rtt.log"
        instance = RttClient(SimulatedRttBackend(simulator))
        instance.start(log_path=str(path))
        try:
            simulator.resume()
            instance.read_lines()
            assert "sensor: done mv=1234" in path.read_text()
        finally:
            instance.stop()
        assert "# RTT channel 0" in path.read_text()

    def test_log_path_is_reported(self, simulator, tmp_path):
        path = tmp_path / "deep" / "rtt.log"
        instance = RttClient(SimulatedRttBackend(simulator))
        instance.start(log_path=str(path))
        try:
            assert instance.log_path == str(path)
            assert path.exists()
        finally:
            instance.stop()


class TestLifecycle:
    def test_start_and_stop_are_idempotent(self, simulator):
        instance = RttClient(SimulatedRttBackend(simulator))
        instance.start()
        instance.start()
        assert instance.is_running
        instance.stop()
        instance.stop()
        assert not instance.is_running

    def test_context_manager(self, simulator):
        with RttClient(SimulatedRttBackend(simulator)) as instance:
            assert instance.is_running
        assert not instance.is_running

    def test_without_the_background_thread(self, simulator):
        """Reads pump synchronously, so collection still works."""
        simulator.connected = True
        simulator.breakpoints[1] = {"location": END_LOCATION, "enabled": True}
        instance = RttClient(SimulatedRttBackend(simulator))
        instance.start(background=False)
        try:
            simulator.resume()
            assert instance.read_lines()
        finally:
            instance.stop()


class _OverlapDetectingBackend:
    """A backend whose poll is slow enough to overlap, and notices when it does.

    Stands in for any backend whose poll is not safe to enter twice - the
    simulator's drain is check-then-pop - without depending on the scheduler to
    produce the race by chance (D-42).
    """

    def __init__(self) -> None:
        self.inside = 0
        self.overlaps = 0
        self._count_lock = threading.Lock()

    def rtt_open(self, *args, **kwargs) -> None:
        """Nothing to open."""

    def rtt_close(self) -> None:
        """Nothing to close."""

    def rtt_poll(self) -> bytes:
        with self._count_lock:
            self.inside += 1
            if self.inside > 1:
                self.overlaps += 1
        time.sleep(0.002)
        with self._count_lock:
            self.inside -= 1
        return b"line\n"


class TestConcurrency:  # pylint: disable=too-few-public-methods
    def test_the_backend_is_never_polled_twice_at_once(self):
        """The reader thread and a caller's read both pump; only one may poll.

        Before D-42 the poll was taken outside the client's lock, and on
        Python 3.9 CI the simulator's drain raised ``IndexError: pop from an
        empty deque`` when the two met.
        """
        backend = _OverlapDetectingBackend()
        instance = RttClient(backend)
        workers = [
            threading.Thread(target=lambda: [instance.read_lines() for _ in range(25)])
            for _ in range(4)
        ]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join()
        assert backend.overlaps == 0


class TestThroughTheProbe:
    def test_probe_rtt_helpers(self, probe):
        probe.rtt_start()
        try:
            probe.run_to(END_LOCATION)
            assert any("mv=1234" in line for line in probe.rtt_read_lines())
            assert probe.rtt_command("version", r"1\.4\.2")
        finally:
            probe.rtt_stop()

    def test_probe_rtt_log(self, probe, tmp_path):
        path = tmp_path / "probe.log"
        probe.rtt_start(log_path=str(path))
        try:
            probe.run_to(END_LOCATION)
            probe.rtt_read_lines()
            assert probe.rtt_log
        finally:
            probe.rtt_stop()
        assert "sensor" in path.read_text()

    def test_rtt_expect_through_the_probe(self, probe):
        probe.rtt_start()
        try:
            probe.run_to(END_LOCATION)
            assert probe.rtt_expect(r"count=(\d+)").group(1) == "7"
        finally:
            probe.rtt_stop()

    def test_channel_beyond_the_limit_is_rejected(self, probe):
        probe._limits = ProbeLimits(max_rtt_channels=2)
        with pytest.raises(ConfigurationError, match="RTT channels"):
            probe.rtt_start(channel=5)
