"""A simulated dongle, and the sensors it can hear.

The model is deliberately exact rather than lifelike. Advertising events are
placed on a virtual microsecond clock at the sensor's nominal interval plus a
repeating pattern of advertising delays, so a test can assert that a 100 ms
sensor reads as 100 ms and that the jitter is the 0-10 ms the Bluetooth
specification requires - not merely that the figure is "about right".

The virtual clock advances only when the host reads, so a two minute profile
capture runs in milliseconds and still produces the intervals a two minute
capture would. That is what makes it possible to assert on exact figures in a
unit test rather than on tolerances wide enough to hide a scaling error.

What is modelled: the command set, the sensor table, advertising with
configurable interval and deliberate dropouts, connection and UART over BLE
with a fixed round-trip latency, and the drop counters that tell a host its
stream was lossy.

Traces to: BLE-FR-080, BLE-DD-SIM.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .constants import AddressType, DongleError

__all__ = ["SimulatedSensor", "SimulatedDongle", "DEFAULT_SENSORS"]


@dataclass
class SimulatedSensor:
    """A sensor the simulated dongle can hear.

    :param interval_us: Nominal advertising interval.
    :param delay_pattern_us: Advertising delays applied in rotation. The
        specification adds a random 0-10 ms to every interval; a fixed rotation
        reproduces that spread deterministically.
    :param miss_every: Drop one advertising event in this many, to model a
        sensor that skips beacons. 0 for a sensor that never misses.
    :param responses: Replies to UART commands, as text.
    :param latency_us: Round trip from write to notification.
    """

    address: str
    name: str = ""
    address_type: AddressType = AddressType.RANDOM_STATIC
    rssi: int = -60
    interval_us: int = 100_000
    delay_pattern_us: Tuple[int, ...] = (0, 3_000, 7_000, 10_000)
    miss_every: int = 0
    payload: bytes = b"\x02\x01\x06"
    responses: Dict[str, str] = field(default_factory=dict)
    latency_us: int = 12_500
    #: Commands that take longer than the usual round trip, in microseconds.
    #: A sensor that measures something before answering is the case where the
    #: latency figure is about the firmware rather than about the link.
    latency_overrides: Dict[str, int] = field(default_factory=dict)
    connectable: bool = True

    def advertising_payload(self) -> bytes:
        """The advertising data, with the local name appended when there is one."""
        if not self.name:
            return self.payload
        encoded = self.name.encode("utf-8")
        return self.payload + bytes([len(encoded) + 1, 0x09]) + encoded


#: The default population: a sensor under test, a second one to make selection
#: mean something, and an unnamed device to prove filtering works.
DEFAULT_SENSORS: Tuple[SimulatedSensor, ...] = (
    SimulatedSensor(
        address="E4:1C:7B:02:9A:11",
        name="SENS-0A1B2C",
        rssi=-62,
        interval_us=100_000,
        responses={
            # The bench's sensor console takes "rd <what>". The bare forms are
            # kept alongside because the driver's own tests use them, and a
            # console that accepts both is the usual case anyway.
            "rd version": "1.4.2",
            "rd id": "SENS-0A1B2C",
            "version": "1.4.2",
            "id": "SENS-0A1B2C",
            "temp": "23.5",
            "battery": "97",
            "measure": "OK 1024",
        },
        latency_overrides={"measure": 95_000},
    ),
    SimulatedSensor(
        address="C9:3A:51:0F:22:04",
        name="SENS-0B2C3D",
        rssi=-78,
        interval_us=250_000,
        miss_every=5,
        responses={
            "rd version": "1.3.9",
            "rd id": "SENS-0B2C3D",
            "version": "1.3.9",
            "id": "SENS-0B2C3D",
        },
    ),
    SimulatedSensor(
        address="F1:22:33:44:55:66",
        name="",
        rssi=-91,
        interval_us=500_000,
        connectable=False,
    ),
)


class SimulatedDongle:
    """An in-process model of the dongle firmware.

    Satisfies :class:`~benchtools.core.simulator.Streamer`: it answers commands
    through :meth:`respond` and produces advertising events through
    :meth:`poll`.

    :param sensors: The population it can hear.
    :param drop_every: Drop one outgoing event in this many, to model a USB
        queue that could not keep up. 0 never drops.
    """

    #: What ``ver`` reports, in the same shape the firmware uses.
    IDENTITY = "Nordic PCA10059"

    #: The build the simulated dongle is running. A test that exercises the
    #: update path changes these, as flashing a real dongle would.
    DEFAULT_FIRMWARE_VERSION = "1.1.0"
    DEFAULT_FIRMWARE_BUILT = "2026-09-13T12:00:00Z"
    DEFAULT_PROTOCOL = "1.1"

    def __init__(
        self,
        sensors: Optional[Tuple[SimulatedSensor, ...]] = None,
        drop_every: int = 0,
    ) -> None:
        # Copied, not shared. DEFAULT_SENSORS is a module-level tuple of
        # dataclasses holding mutable dicts: a test that changed one sensor's
        # replies would change them for every simulator built afterwards, and
        # the tests it broke would be somewhere else entirely.
        self.sensors: List[SimulatedSensor] = [
            copy.deepcopy(sensor)
            for sensor in (sensors if sensors is not None else DEFAULT_SENSORS)
        ]
        self.drop_every = int(drop_every)

        self.clock_us = 1_000_000              # a dongle that has been up a second
        self.command_log: List[str] = []
        self.dropped = 0

        self.firmware_version = self.DEFAULT_FIRMWARE_VERSION
        self.firmware_built = self.DEFAULT_FIRMWARE_BUILT
        self.protocol = self.DEFAULT_PROTOCOL
        #: True once ``dfu`` has been accepted: the dongle is in its bootloader
        #: and answers nothing until it is flashed and restarted.
        self.in_bootloader = False
        self.dfu_requests = 0

        self._scanning = False
        self._scan_until_us: Optional[int] = None
        self._scan_filter: Dict[str, str] = {}
        self._found: List[SimulatedSensor] = []
        self._selected: Optional[SimulatedSensor] = None
        self._connected: Optional[SimulatedSensor] = None
        self._profiling = False
        self._profile_address: Optional[str] = None
        self._profile_received = 0
        self._profile_reported = 0
        self._emitted = 0

        #: Next advertising event per sensor, in virtual microseconds.
        self._next_us: Dict[str, int] = {}
        self._delay_index: Dict[str, int] = {}
        self._beacon_index: Dict[str, int] = {}
        self._queue: List[str] = []

    # ------------------------------------------------------------------
    # The link
    # ------------------------------------------------------------------
    def respond(self, message: bytes) -> Optional[bytes]:
        """Answer one command line, prefixed by any queued events."""
        line = message.decode("utf-8", errors="replace").strip()
        if not line:
            return None
        self.command_log.append(line)

        if self.in_bootloader:
            # A dongle in its bootloader does not speak this protocol at all.
            # Returning nothing is what the host sees: a timeout.
            return None

        lines = self._flush_queue()
        lines.extend(self._dispatch(line))
        return ("\n".join(lines) + "\n").encode("utf-8")

    def poll(self) -> bytes:
        """Produce whatever the dongle would have sent by now.

        Advances the virtual clock to the next scheduled advertising event, so
        a capture proceeds as fast as the host reads.
        """
        if self._queue:
            return ("\n".join(self._flush_queue()) + "\n").encode("utf-8")
        if not (self._scanning or self._profiling):
            return b""

        produced = self._advance()
        if not produced:
            return b""
        return ("\n".join(produced) + "\n").encode("utf-8")

    # ------------------------------------------------------------------
    def _flush_queue(self) -> List[str]:
        queued, self._queue = self._queue, []
        return queued

    def _emit(self, line: str) -> Optional[str]:
        """Apply the drop model to one outgoing event line."""
        self._emitted += 1
        if self.drop_every and (self._emitted % self.drop_every == 0):
            self.dropped += 1
            return None
        return line

    def _advance(self) -> List[str]:
        """Advance to the next advertising event and report it."""
        candidates = [
            (self._schedule_for(sensor), sensor)
            for sensor in self.sensors
            if self._hears(sensor)
        ]
        if not candidates:
            return []

        when_us, sensor = min(candidates, key=lambda item: item[0])

        # The firmware stops scanning when its own timeout expires and says so.
        # Modelling that here is what lets a three second scan be simulated in
        # milliseconds: the host waits for the event, not for the wall clock.
        if self._scan_until_us is not None and when_us >= self._scan_until_us:
            self.clock_us = self._scan_until_us
            self._scanning = False
            self._scan_until_us = None
            return ["+scan t=%d state=stopped" % self.clock_us]

        self.clock_us = when_us
        self._schedule_next(sensor)

        lines: List[str] = []
        index = self._beacon_index.get(sensor.address, 0)
        self._beacon_index[sensor.address] = index + 1

        # A sensor that skips beacons: the event is scheduled and then not sent,
        # which is exactly what a real dropout looks like from the host.
        if sensor.miss_every and ((index + 1) % sensor.miss_every == 0):
            return lines

        self._remember(sensor)

        if self._profiling and self._wants(sensor):
            self._profile_received += 1
            line = self._emit(self._advertising_line(sensor, when_us))
            if line is None:
                lines.append(
                    "+drop t=%d count=%d" % (when_us, self.dropped)
                )
            else:
                self._profile_reported += 1
                lines.append(line)
        return lines

    def _schedule_for(self, sensor: SimulatedSensor) -> int:
        """When this sensor next advertises, in virtual microseconds.

        A schedule left in the past - because the clock jumped forward when a
        scan timed out - is rolled forward rather than replayed. Time does not
        run backwards on a dongle, and a negative interval would poison every
        statistic derived from it.
        """
        when = self._next_us.get(sensor.address)
        # Strictly in the past, not "not in the future": an event scheduled for
        # the current instant is due now. Rolling it forward instead loses one
        # beacon every time two sensors coincide, which is exactly when a real
        # scanner would hear the quieter one.
        if when is None or when < self.clock_us:
            when = self.clock_us + sensor.interval_us
            self._next_us[sensor.address] = when
        return when

    def _schedule_next(self, sensor: SimulatedSensor) -> None:
        index = self._delay_index.get(sensor.address, 0)
        delay = sensor.delay_pattern_us[index % len(sensor.delay_pattern_us)] if sensor.delay_pattern_us else 0
        self._delay_index[sensor.address] = index + 1
        self._next_us[sensor.address] = self.clock_us + sensor.interval_us + delay

    def _hears(self, sensor: SimulatedSensor) -> bool:
        """Whether the scan filter admits *sensor*."""
        if self._connected is not None:
            return False                       # the radio is on the connection
        name = self._scan_filter.get("name")
        if name and name not in sensor.name:
            return False
        address = self._scan_filter.get("addr")
        if address and address.upper().split("/")[0] != sensor.address.upper():
            return False
        minimum = self._scan_filter.get("rssi")
        if minimum and sensor.rssi < int(minimum):
            return False
        return True

    def _wants(self, sensor: SimulatedSensor) -> bool:
        if self._profile_address is None:
            return True
        return self._profile_address.upper().split("/")[0] == sensor.address.upper()

    def _remember(self, sensor: SimulatedSensor) -> None:
        if sensor not in self._found:
            self._found.append(sensor)

    def _advertising_line(self, sensor: SimulatedSensor, when_us: int) -> str:
        # Channels rotate 37, 38, 39 as a real scanner would see successive
        # events on whichever channel it was listening to.
        channel = 37 + (self._beacon_index.get(sensor.address, 1) - 1) % 3
        return (
            "+adv t=%d addr=%s type=%d rssi=%d pdu=0 ch=%d name=%s data=%s"
            % (
                when_us,
                sensor.address,
                int(sensor.address_type),
                sensor.rssi,
                channel,
                sensor.name,
                sensor.advertising_payload().hex(),
            )
        )

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------
    def _dispatch(self, line: str) -> List[str]:
        tokens = line.split()
        command = tokens[0]
        arguments = tokens[1:]

        handler = getattr(self, "_cmd_" + command, None)
        if handler is None:
            return [self._error(DongleError.UNKNOWN, "unknown command")]
        return handler(arguments)

    @staticmethod
    def _error(code: DongleError, text: str) -> str:
        return "err %d %s" % (int(code), text)

    def _cmd_ver(self, arguments: List[str]) -> List[str]:
        return [
            "ok %s fw=%s built=%s proto=%s uptime_us=%d dropped=%d"
            % (
                self.IDENTITY,
                self.firmware_version,
                self.firmware_built,
                self.protocol,
                self.clock_us,
                self.dropped,
            )
        ]

    def _cmd_dfu(self, arguments: List[str]) -> List[str]:
        """Answer, then go quiet: the link comes back as the bootloader's."""
        self.dfu_requests += 1
        self.in_bootloader = True
        return ["ok dfu=1 fw=%s" % self.firmware_version]

    def _cmd_time(self, arguments: List[str]) -> List[str]:
        return ["ok t=%d hz=1000000" % self.clock_us]

    def _cmd_scan(self, arguments: List[str]) -> List[str]:
        if not arguments:
            return [self._error(DongleError.ARGS, "wrong number of arguments")]
        if arguments[0] == "stop":
            self._scanning = False
            self._scan_until_us = None
            return ["ok scanning=0 sensors=%d" % len(self._found)]
        if arguments[0] != "start" or len(arguments) < 2:
            return [self._error(DongleError.VALUE, "bad argument value")]

        self._found = []
        self._scan_filter = {}
        for token in arguments[2:]:
            key, _, value = token.partition("=")
            self._scan_filter[key] = value
        self._scanning = True
        duration_ms = int(arguments[1]) if arguments[1].isdigit() else 0
        self._scan_until_us = (self.clock_us + duration_ms * 1000) if duration_ms else None
        return ["ok scanning=1 ms=%s" % arguments[1]]

    def _cmd_list(self, arguments: List[str]) -> List[str]:
        lines = []
        for index, sensor in enumerate(self._found):
            lines.append(
                "+sensor t=%d idx=%d addr=%s type=%d rssi=%d seen=1 name=%s"
                % (
                    self.clock_us,
                    index,
                    sensor.address,
                    int(sensor.address_type),
                    sensor.rssi,
                    sensor.name,
                )
            )
        lines.append("ok sensors=%d" % len(self._found))
        return lines

    def _cmd_select(self, arguments: List[str]) -> List[str]:
        target = arguments[0]
        sensor = None
        if target.isdigit():
            index = int(target)
            if index < len(self._found):
                sensor = self._found[index]
        else:
            wanted = target.upper().split("/")[0]
            for candidate in self.sensors:
                if candidate.address.upper() == wanted:
                    sensor = candidate
                    break
        if sensor is None:
            return [self._error(DongleError.VALUE, "bad argument value")]

        self._selected = sensor
        return [
            "ok addr=%s type=%d name=%s known=1"
            % (sensor.address, int(sensor.address_type), sensor.name)
        ]

    def _cmd_selected(self, arguments: List[str]) -> List[str]:
        if self._selected is None:
            return [self._error(DongleError.NO_SENSOR, "no sensor selected")]
        return [
            "ok addr=%s type=%d name=%s connected=%d"
            % (
                self._selected.address,
                int(self._selected.address_type),
                self._selected.name,
                1 if self._connected is not None else 0,
            )
        ]

    def _cmd_connect(self, arguments: List[str]) -> List[str]:
        sensor = self._selected
        if arguments:
            wanted = arguments[0].upper().split("/")[0]
            sensor = next(
                (item for item in self.sensors if item.address.upper() == wanted), None
            )
        if sensor is None:
            return [self._error(DongleError.NO_SENSOR, "no sensor selected")]
        if self._connected is not None:
            return [self._error(DongleError.STATE, "not valid in this state")]
        if not sensor.connectable:
            return [self._error(DongleError.BLE, "the BLE stack refused the request")]

        self._scanning = False
        self._connected = sensor
        self.clock_us += 30_000
        self._queue.append(
            "+conn t=%d addr=%s state=linked interval_us=30000"
            % (self.clock_us, sensor.address)
        )
        self.clock_us += 5_000
        self._queue.append(
            "+conn t=%d state=ready interval_us=30000" % self.clock_us
        )
        return ["ok connecting=1 addr=%s" % sensor.address]

    def _cmd_disconnect(self, arguments: List[str]) -> List[str]:
        if self._connected is None:
            return [self._error(DongleError.NOT_CONNECTED, "not connected")]
        self._connected = None
        self.clock_us += 1_000
        self._queue.append("+disc t=%d reason=0x16" % self.clock_us)
        return ["ok"]

    def _cmd_uart(self, arguments: List[str]) -> List[str]:
        if self._connected is None:
            return [self._error(DongleError.NOT_CONNECTED, "not connected")]
        try:
            payload = bytes.fromhex(arguments[0])
        except ValueError:
            return [self._error(DongleError.VALUE, "bad argument value")]
        self.clock_us += 500
        return ["ok len=%d t=%d" % (len(payload), self.clock_us)]

    def _cmd_cmd(self, arguments: List[str]) -> List[str]:
        if self._connected is None:
            return [self._error(DongleError.NOT_CONNECTED, "not connected")]
        try:
            payload = bytes.fromhex(arguments[0])
        except ValueError:
            return [self._error(DongleError.VALUE, "bad argument value")]

        sensor = self._connected
        request = payload.decode("utf-8", errors="replace").strip()
        reply = sensor.responses.get(request)
        if reply is None:
            reply = "ERR unknown command"

        transmitted_us = self.clock_us
        self.clock_us += sensor.latency_overrides.get(request, sensor.latency_us)
        received_us = self.clock_us
        encoded = reply.encode("utf-8")

        self._queue.append(
            "+rx t=%d len=%d data=%s" % (received_us, len(encoded), encoded.hex())
        )
        return [
            "ok t_tx=%d t_rx=%d dt_us=%d interval_us=30000 len=%d data=%s"
            % (
                transmitted_us,
                received_us,
                received_us - transmitted_us,
                len(encoded),
                encoded.hex(),
            )
        ]

    def _cmd_adv(self, arguments: List[str]) -> List[str]:
        if not arguments:
            return [self._error(DongleError.ARGS, "wrong number of arguments")]
        if arguments[0] == "stats":
            return [
                "ok received=%d reported=%d dropped=%d profiling=%d"
                % (
                    self._profile_received,
                    self._profile_reported,
                    self.dropped,
                    1 if self._profiling else 0,
                )
            ]
        if arguments[0] == "stop":
            self._profiling = False
            return [
                "ok profiling=0 received=%d reported=%d"
                % (self._profile_received, self._profile_reported)
            ]
        if arguments[0] != "start":
            return [self._error(DongleError.VALUE, "bad argument value")]

        address = arguments[1] if len(arguments) > 1 else None
        if address is None:
            if self._selected is None:
                return [self._error(DongleError.NO_SENSOR, "no sensor selected")]
            address = self._selected.address

        self._profile_address = address
        self._profile_received = 0
        self._profile_reported = 0
        self._profiling = True
        return [
            "ok profiling=1 addr=%s scanning=%d"
            % (address, 1 if self._scanning else 0)
        ]

    def apply_update(self, version: str, built: str) -> None:
        """Flash a new build and restart, as a DFU does.

        This is what a test's flasher calls instead of running ``nrfutil``.
        """
        self.firmware_version = version
        self.firmware_built = built
        self.in_bootloader = False
        self._cmd_reset([])

    def _cmd_reset(self, arguments: List[str]) -> List[str]:
        self._scanning = False
        self._scan_until_us = None
        self._profiling = False
        self._connected = None
        self._selected = None
        self._found = []
        self._next_us = {}
        self._delay_index = {}
        self._beacon_index = {}
        return ["ok resetting=1"]
