"""A simulated Kepler sensor (Sensoteq Kappa X), as the bench's sensor 5C1712.

One model, read by every simulated instrument that touches the sensor: the
dongle hears its replies over BLE, the probe reads its RTT log, and the S2-LP
kit receives its frames (#122). A command that changes the sensor -
``WR PREAMBLE-LENGTH``, ``ECURESET HARD`` - therefore changes what the others
see, as it does on the bench.

Where each reply format comes from (#121):

- ``ACK RD VERSION = V11.00.0000-95-gc051f3665``, ``ACK RD SHA = c051f3665``,
  ``ACK RD ID = 0x5C1712``, ``ACK RD BATTERY = 2789mV``,
  ``ACK RD TEMPERATURE = 21187mC``, ``ACK ECURESET HARD``: captured from
  5C1712 running V11.00.0000-95 in the 2026-10-04 qualification
  (``docs/aspice/qualification/2026-10-04``). That firmware echoes the command
  as it was sent and writes the unit straight after the number.
- ``ACK WR ALIVE-PERIOD 10 Secs``: the reply ``kepler_battery.yaml`` and
  ``kepler_temperature.yaml`` check for, and in Kepler bench traces of the
  same firmware generation.
- ``MCU Temperature: 21000mC``: the RTT line, from the same qualification
  (``qs01.events.jsonl``).
- The ranges of ``WR ALIVE-PERIOD`` (10-900 s, default 600) and
  ``WR PREAMBLE-LENGTH`` (32-1023, default 32), and the ``OUT OF RANGE``
  refusal: the sensor firmware's parameter table, ``api_param_cfg.h``.

Open items, assumed rather than captured, and marked so in BLE-DD-KEPLERSIM:

- ``ACK RD BATTERY-LOADED = <n>mV`` and ``ACK WR PREAMBLE-LENGTH <n> Pairs``
  are taken from later firmware (V11.01), which lowercases the echo and puts a
  space before the unit, and written in the V11.00 style.
- The loaded battery reads 20 mV below the unloaded one, and the MCU 3.5 C
  above the machine temperature (seen as 2.5-4.75 C on 5C1712).
- An unknown command answers ``NACK Invalid Command``.
- ``SESSION SWDL`` answers ``ACK SESSION SWDL``; the firmware's handler
  (``app_cmd.c``) replies ``ACK``, and the exact text was not captured. The
  sensor then enters its bootloader (#244).

**Its radio (#122).** The sensor transmits VERSION and ALIVE frames on 433 MHz,
on the air clock the simulated bench keeps (:mod:`.world`). Where each part
comes from:

- The frame layouts - header, field offsets, encodings - are the ones the
  Kepler plugin's decoder reads (RF_CAP 6, type version 1). The header bytes
  (product 3, RF_CAP 6, HW and FW capability 4), the PCB code 3 and the
  vibration figures of an ALIVE frame are copied from frames 5C1712 sent:
  VERSION in the 2026-10-04 qualification (``qs07_rx_only.events.jsonl``),
  ALIVE in ``docs/aspice/qualification/2026-10-25/293_kepler_frame_gap``.
- Three copies of every transmission, repeat 0 to 2, ``frames_per_packet`` 3:
  as captured. The copies were 31 to 229 ms apart (#293); here, 100 ms.
- The "SI updated" status bit set in the first copy of an ALIVE only: V11.00
  and V11.01 (#95).
- The VERSION frame about 8 s after ``ECURESET HARD`` (#85), carrying reset
  reason 4. ``WR PREAMBLE-LENGTH`` is stored and applied when the radio next
  initialises, after a reset: the reason ``kepler_preamble.yaml`` resets.
- The radio settings a receiver must match to hear the sensor
  (:data:`KEPLER_433_TRANSMITTER`): those of ``s2lp_kepler_433_rx.regs``, set
  up to the sensor firmware's values and captured on the kit on 2026-09-27.

Open items in the radio, assumed rather than captured:

- The frame's version field is ``RD VERSION`` alone, the owner's rule for V11
  (2026-10-07). The V11.00.0000-95 build captured on 2026-10-04 appends a
  space and the SHA; :attr:`KeplerSensorModel.frame_version_with_sha` sends
  that instead.
- The first ALIVE comes one alive period after a reset, and a new
  ``WR ALIVE-PERIOD`` starts a new period from when it is written.
- The battery and temperature on the air are rounded to the nearest 20 mV and
  0.1 C.
- The frame's ``ticks`` count one per frame sent.

Traces to: BLE-DD-KEPLERSIM.
"""

from __future__ import annotations

import re
import struct
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple

__all__ = [
    "KEPLER_433_TRANSMITTER",
    "KEPLER_5C1712_ADDRESS",
    "KEPLER_5C1712_ID",
    "KEPLER_5C1712_NAME",
    "KEPLER_5C1712_DFU_ADDRESS",
    "KEPLER_5C1712_DFU_NAME",
    "KeplerSensorModel",
    "RadioSettings",
    "Transmission",
]

#: The bench's sensor under test, as the specifications name it.
KEPLER_5C1712_ID = 0x5C1712
KEPLER_5C1712_ADDRESS = "D1:8D:3B:4C:19:96"
#: The name V11.00.0000 advertises: the firmware tag, cut to 23 characters by
#: that generation's advertising payload.
KEPLER_5C1712_NAME = "KAPPA_5C1712_V11.00.00"
#: 5C1712 in its bootloader: the application's address + 1, and the name the
#: V2.00.0000 bootloader gives itself when the application enters it, with the
#: V4X PCB code (bl_board.c) (#244).
KEPLER_5C1712_DFU_ADDRESS = "D1:8D:3B:4C:19:97"
KEPLER_5C1712_DFU_NAME = "KAPPA_5C1712-0FDFU"

#: RESETREAS.SREQ: the reset reason a ``ECURESET HARD`` leaves.
RESET_REASON_SOFT = 4

_WRITE = re.compile(r"^WR\s+(ALIVE-PERIOD|PREAMBLE-LENGTH)\s+(\S+)$", re.IGNORECASE)


@dataclass(frozen=True)
class RadioSettings:
    """What a receiver must be set to, to hear a transmitter.

    :param registers: S2-LP register name, mask and value: the receiver hears
        only if ``register & mask == value`` for each.
    :param sync_word: The transmitter's sync word. The receiver hears it as its
        primary sync word (SYNC3..0) or, with ``PCKTCTRL1.SECOND_SYNC_SEL``, its
        secondary (PCKT_FLT_GOALS3..0); both are stored least significant
        byte first.
    """

    registers: Tuple[Tuple[str, int, int], ...]
    sync_word: int


#: The sensor's 433 MHz transmitter: 433.425 MHz, 2-FSK at 100 kbps, basic
#: packets of variable length with an address byte and CRC-16, sync word
#: 0xB19C0CA7 (sensor to gateway). The values are those of
#: ``s2lp_kepler_433_rx.regs``, which was set up to the sensor firmware's.
#: Deviation and channel filter are not compared: a near miss in either still
#: receives on a real radio, and how near is not modelled.
KEPLER_433_TRANSMITTER = RadioSettings(
    registers=(
        ("SYNT3", 0x1F, 0x12),      # band select and SYNT[27:24]
        ("SYNT2", 0xFF, 0x2A),
        ("SYNT1", 0xFF, 0xC9),
        ("SYNT0", 0xFF, 0xF3),
        ("MOD4", 0xFF, 0x06),       # data rate mantissa
        ("MOD3", 0xFF, 0x25),
        ("MOD2", 0xFF, 0x09),       # 2-FSK, data rate exponent 9
        ("PCKTCTRL4", 0x08, 0x08),  # one address byte
        ("PCKTCTRL3", 0xC0, 0x00),  # basic packets
        ("PCKTCTRL2", 0x01, 0x01),  # variable length
        ("PCKTCTRL1", 0xE0, 0x40),  # CRC-16 0x8005
    ),
    sync_word=0xB19C0CA7,
)


@dataclass(frozen=True)
class Transmission:
    """One copy of one frame on the air."""

    at_s: float
    payload: bytes
    preamble_pairs: int
    settings: RadioSettings
    source: str


#: PL_TYPE of the frames the model sends.
_VERSION, _ALIVE = 2, 3
#: The header 5C1712 sends after its ID: product 3 (Kappa GEN2), RF_CAP 6,
#: type version 1 with HW capability 4, FW capability 4.
_HEADER = bytes([0x03, 0x06, 0x0C, 0x04])
#: Copies of each transmission, and the gap between them.
COPIES = 3
COPY_GAP_S = 0.1
#: From ``ECURESET HARD`` to the VERSION frame (#85).
VERSION_DELAY_S = 8.0
#: An ALIVE frame's vibration figures, bytes 14 to 32, as 5C1712 sent them
#: (si_scale, then RMS acceleration, velocity and peak-to-peak, X Y Z).
_ALIVE_VIBRATION = bytes.fromhex("00 008D 0051 0058 0093 007A 005F 0316 021A 0254")
#: ALIVE_STATUS: phase 2, "SI updated" (bit 0) in the first copy only (#95).
_ALIVE_STATUS = 0x08
_SI_UPDATED = 0x01


@dataclass
class KeplerSensorModel:  # pylint: disable=too-many-instance-attributes
    """What a Kepler sensor reports, and the state its commands change.

    :param supply: Reads the volts the sensor is powered from, or None when
        nothing simulated feeds it; the battery then reads *battery_mv*. On the
        simulated bench it is the simulated supply's channel 2, which is how
        ``kepler_battery.yaml`` wires 5C1712.
    """

    sensor_id: int = KEPLER_5C1712_ID
    version: str = "V11.00.0000-95-gc051f3665"
    sha: str = "c051f3665"
    battery_mv: int = 3300
    loaded_drop_mv: int = 20
    temperature_mc: int = 21187
    mcu_above_machine_mc: int = 3500
    alive_period_s: int = 600
    preamble_length: int = 32
    reset_reason: int = 1
    resets: int = 0
    #: In its bootloader, after ``SESSION SWDL``, advertising for an update.
    in_bootloader: bool = False
    supply: Optional[Callable[[], Optional[float]]] = None
    #: Reads the air clock, in seconds; 0 without one.
    clock: Optional[Callable[[], float]] = None
    #: The PCB code the VERSION frame carries: 3, V4X.
    pcb_code: int = 3
    #: Send the version as the captured V11.00.0000-95 build did, with a space
    #: and the SHA after it, rather than by the V11 rule.
    frame_version_with_sha: bool = False
    #: Whether the sensor transmits at all.
    transmitting: bool = True
    #: The radio it transmits with.
    radio: RadioSettings = KEPLER_433_TRANSMITTER
    #: The preamble the radio is sending: :attr:`preamble_length` as it was at
    #: the last reset.
    radio_preamble_length: int = 32
    ticks: int = 0
    _next_alive_at: Optional[float] = field(default=None, repr=False)
    _next_version_at: Optional[float] = field(default=None, repr=False)
    _copies: List[Tuple[float, int, int]] = field(default_factory=list, repr=False)

    #: Accepted ranges, from the sensor firmware's parameter table.
    ALIVE_PERIOD_RANGE = (10, 900)
    PREAMBLE_LENGTH_RANGE = (32, 1023)

    # ------------------------------------------------------------------
    def battery_now_mv(self) -> int:
        """The battery as the sensor measures it: its supply, when it has one."""
        volts = self.supply() if self.supply is not None else None
        if volts is None:
            return int(self.battery_mv)
        return int(round(volts * 1000.0))

    def mcu_temperature_mc(self) -> int:
        """The MCU die temperature, which RTT reports and BLE does not."""
        return int(self.temperature_mc + self.mcu_above_machine_mc)

    def rtt_line(self) -> str:
        """One line of the sensor's RTT log, as it writes it once a second."""
        return "MCU Temperature: %dmC" % self.mcu_temperature_mc()

    def reset(self) -> None:
        """A software reset: what ``ECURESET HARD`` does after it answers.

        The radio takes the stored preamble length, a VERSION frame follows
        after :data:`VERSION_DELAY_S`, and the alive period starts again.
        """
        self.resets += 1
        self.reset_reason = RESET_REASON_SOFT
        self.radio_preamble_length = self.preamble_length
        now = self._now()
        self._copies = []
        self._next_version_at = now + VERSION_DELAY_S
        self._next_alive_at = now + self.alive_period_s

    # ------------------------------------------------------------------
    # The radio
    # ------------------------------------------------------------------
    def _now(self) -> float:
        return float(self.clock()) if self.clock is not None else 0.0

    def next_transmission_at(self) -> Optional[float]:
        """When the sensor next puts a frame on the air, or None if it will not."""
        if not self.transmitting or self.in_bootloader:
            return None
        if self._copies:
            return self._copies[0][0]
        if self._next_alive_at is None:
            # Running since before the bench looked: an ALIVE is due within a period.
            self._next_alive_at = self._now() + self.alive_period_s
        due = [at for at in (self._next_version_at, self._next_alive_at) if at is not None]
        return min(due)

    def transmit(self) -> Transmission:
        """The next copy of the next frame, at :meth:`next_transmission_at`.

        The frame's readings are taken when it is sent.
        """
        at = self.next_transmission_at()
        if at is None:
            raise RuntimeError("the sensor is not transmitting")
        if not self._copies:
            if self._next_version_at is not None and self._next_version_at <= at:
                kind, self._next_version_at = _VERSION, None
            else:
                kind = _ALIVE
                self._next_alive_at = at + self.alive_period_s
            self._copies = [(at + COPY_GAP_S * repeat, kind, repeat) for repeat in range(COPIES)]
        sent_at, kind, repeat = self._copies.pop(0)
        self.ticks = (self.ticks + 1) & 0xFFFF
        payload = self.version_frame(repeat) if kind == _VERSION else self.alive_frame(repeat)
        return Transmission(sent_at, payload, self.radio_preamble_length, self.radio,
                            "%06X" % self.sensor_id)

    def _header(self, pl_type: int, repeat: int) -> bytes:
        frame_count = ((repeat + 1) << 4) | COPIES
        return (struct.pack(">I", self.sensor_id)[1:] + _HEADER
                + bytes([pl_type, frame_count]))

    def _battery_byte(self, millivolts: int) -> int:
        return max(0, min(255, int(round(millivolts / 20.0))))

    def _temperature_tenths(self) -> int:
        return int(round(self.temperature_mc / 100.0))

    def version_frame(self, repeat: int = 0) -> bytes:
        """A VERSION frame: 83 bytes, as the plugin's decoder lays them out."""
        version = self.version + (" " + self.sha if self.frame_version_with_sha else "")
        return (self._header(_VERSION, repeat)
                + self.sha.encode("ascii")[:7].ljust(7, b"\x00")
                # 53 bytes of text the decoder reads, then 4 the sensor leaves 0.
                + version.encode("ascii")[:53].ljust(57, b"\x00")
                + struct.pack(">I", self.reset_reason)
                + bytes([self._battery_byte(self.battery_now_mv() - self.loaded_drop_mv),
                         self.pcb_code & 0xFF])
                + struct.pack(">hH", self._temperature_tenths(), self.ticks))

    def alive_frame(self, repeat: int = 0) -> bytes:
        """An ALIVE frame: 35 bytes, as the plugin's decoder lays them out."""
        status = _ALIVE_STATUS | (_SI_UPDATED if repeat == 0 else 0)
        return (self._header(_ALIVE, repeat)
                + struct.pack(">hBH", self._temperature_tenths(),
                              self._battery_byte(self.battery_now_mv()), self.ticks)
                + _ALIVE_VIBRATION + bytes([0, status]))

    # ------------------------------------------------------------------
    def respond(self, request: str) -> str:
        """The sensor's reply to one BLE console command."""
        text = " ".join(request.split())
        word = text.upper()
        readings = {
            "RD VERSION": self.version,
            "RD SHA": self.sha,
            "RD ID": "0x%06X" % self.sensor_id,
            "RD BATTERY": "%dmV" % self.battery_now_mv(),
            "RD BATTERY-LOADED": "%dmV" % (self.battery_now_mv() - self.loaded_drop_mv),
            "RD TEMPERATURE": "%dmC" % self.temperature_mc,
        }
        if word in readings:
            return "ACK %s = %s" % (text, readings[word])
        if word in ("ECURESET HARD", "SESSION SWDL"):
            return "ACK %s" % text
        match = _WRITE.match(text)
        if match:
            return self._write(text, match.group(1).upper(), match.group(2))
        return "NACK Invalid Command"

    def _write(self, text: str, parameter: str, value: str) -> str:
        if not value.isdigit():
            return "NACK %s INVALID VALUE" % text
        number = int(value)
        if parameter == "ALIVE-PERIOD":
            low, high = self.ALIVE_PERIOD_RANGE
            unit = "Secs"
        else:
            low, high = self.PREAMBLE_LENGTH_RANGE
            unit = "Pairs"
        if not low <= number <= high:
            return "NACK %s OUT OF RANGE" % text
        if parameter == "ALIVE-PERIOD":
            self.alive_period_s = number
            self._next_alive_at = self._now() + number
        else:
            self.preamble_length = number
        return "ACK %s %s" % (text, unit)
