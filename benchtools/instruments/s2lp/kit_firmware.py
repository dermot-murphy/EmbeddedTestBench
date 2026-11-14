"""The host side of the ETB S2-LP kit firmware's line protocol (#84).

The kit can run either of two firmwares: ST's CLI firmware, which the rest of
this package drives, or the ETB kit firmware in ``firmware/s2lp_kit``. The
second exists because ST's re-arms the radio from the host, one frame at a time,
and is deaf for the round trip; the ETB firmware re-arms inside the radio's
interrupt, reads the registers the host asked for after each frame, and
numbers every record so a lost one shows as a gap.

:class:`~.s2lp.S2lpDevkit` asks which firmware the board runs when it connects
(:func:`probe`). ``id`` is the ETB firmware's identification; ST's command
interpreter answers it with ``no such command``, which costs nothing. On the
ETB firmware the driver then talks through :class:`KitSession` instead of
:class:`~.session.S2lpSession`: registers, strobes, shutdown and receiving
work; ST's own commands (its radio library calls, transmit, the board EEPROM)
are refused with a message naming the firmware.

The protocol, one command per line, each answered by one line::

    id                      ok etb-s2lp-kit V1.00.0000 proto=1 silicon=c1
    rd <addr> <count>       ok <hex>
    wr <addr> <hex>         ok
    cmd <code>              ok <MC_STATE1><MC_STATE0>
    sdn <0|1>               ok
    rx start [<addr>,...]   ok
    rx stop                 (records still queued, then)
                            ok frames=<n> rejects=<n> overflows=<n> deaf_max_us=<n>
    stat                    ok running=<0|1> ... queued=<n> uart_overruns=<n>

and, unasked, while receiving::

    f <seq> <time_us> <length> <registers hex or -> <payload hex>
    r <seq> <time_us> <irq status hex>

Traces to: S2LP-FR-098, S2LP-FR-099, S2LP-FR-100, S2LP-DD-KITHOST.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Callable, Deque, Dict, List, Optional, Sequence, Tuple

from ...core.errors import InstrumentError, ProtocolError, TransportTimeoutError
from .registers import BY_ADDRESS
from .session import S2lpSession

__all__ = [
    "KIT_FIRMWARE_NAME",
    "KIT_PROTOCOL",
    "KitIdentity",
    "KitRecord",
    "KitSession",
    "SimulatedKitFirmware",
    "parse_identity",
    "parse_record",
    "probe",
]

#: The name the ETB kit firmware gives in its ``id`` answer.
KIT_FIRMWARE_NAME = "etb-s2lp-kit"

#: The line protocol version this driver speaks.
KIT_PROTOCOL = 1

#: Seconds :func:`probe` waits for an answer to ``id``. ST's firmware answers
#: ``no such command`` at once, so this is reached only by a board that says
#: nothing at all.
PROBE_TIMEOUT = 1.0

#: Seconds to wait for ``rx stop``: the firmware sends every queued record
#: first, up to 16 lines of about 300 characters at 115200 baud.
STOP_TIMEOUT = 5.0

#: Most registers the firmware reads after each frame.
MAX_REGISTERS = 8

#: Largest payload the firmware reports, in bytes.
MAX_PAYLOAD = 128

#: Longest command line the firmware accepts, without its line end.
LINE_MAX = 300

_ID_PREFIX = "ok " + KIT_FIRMWARE_NAME + " "


@dataclass
class KitIdentity:
    """What the firmware's ``id`` answer says."""

    name: str
    version: str
    protocol: int
    silicon: int
    raw: str


@dataclass
class KitRecord:  # pylint: disable=too-many-instance-attributes
    """One record the firmware sent while receiving.

    :param kind: ``"f"`` for a frame received intact, ``"r"`` for a reception
        the radio discarded (CRC, a filter, a FIFO error).
    :param seq: The record's number since ``rx start``. Every record is
        numbered, sent or dropped, so a gap is a record the board lost.
    :param time_us: The board's microsecond timer when the radio's interrupt
        was taken, modulo 2^32.
    :param length: The payload length the radio reported.
    :param registers: The registers read after the frame, in the order asked.
    :param payload: The frame's payload.
    :param irq: A rejection's IRQ status.
    """

    kind: str
    seq: int
    time_us: int
    length: int = 0
    registers: bytes = b""
    payload: bytes = b""
    irq: int = 0
    raw: str = ""


def parse_identity(line: str) -> Optional[KitIdentity]:
    """The ETB firmware's ``id`` answer, or ``None`` if *line* is not one."""
    if not line.startswith(_ID_PREFIX):
        return None
    words = line.split()
    fields = dict(word.split("=", 1) for word in words[3:] if "=" in word)
    try:
        return KitIdentity(name=words[1], version=words[2] if len(words) > 2 else "",
                           protocol=int(fields.get("proto", "0")),
                           silicon=int(fields.get("silicon", "0"), 16), raw=line)
    except ValueError:
        return None


def parse_record(line: str) -> Optional[KitRecord]:
    """A record line as a :class:`KitRecord`, or ``None`` if it is not one.

    A line that starts like a record but does not parse is not a record:
    ``None``, so the caller keeps it as an unclaimed line rather than guess.
    """
    words = line.split(" ")
    try:
        if words[0] == "f" and len(words) in (5, 6):
            payload = bytes.fromhex(words[5]) if len(words) == 6 else b""
            registers = b"" if words[4] == "-" else bytes.fromhex(words[4])
            return KitRecord(kind="f", seq=int(words[1]), time_us=int(words[2]),
                             length=int(words[3]), registers=registers,
                             payload=payload, raw=line)
        if words[0] == "r" and len(words) == 4:
            return KitRecord(kind="r", seq=int(words[1]), time_us=int(words[2]),
                             irq=int(words[3], 16), raw=line)
    except ValueError:
        return None
    return None


def probe(session: S2lpSession, timeout: float = PROBE_TIMEOUT) -> Optional[KitIdentity]:
    """Ask the board for the ETB firmware's ``id``; its identity, or ``None``.

    ``None`` means the board is not running the ETB firmware: ST's answers
    ``no such command``, and its prompt is read and dropped so the next
    command starts clean.
    """
    session.note("asking which firmware the board runs")
    session.write_line("id")
    deadline = time.monotonic() + float(timeout)
    while time.monotonic() < deadline:
        line = session.read_line()
        if line is None:
            continue
        identity = parse_identity(line)
        if identity is not None:
            return identity
        if line.strip().lower() == "no such command" or line.startswith("err"):
            break
    session.drain()
    return None


class KitSession(S2lpSession):
    """Commands to the ETB kit firmware, its records, and the same raw log.

    A :class:`~.session.S2lpSession` for the logging, line reading and command
    count, with the ETB protocol in place of ST's. ST's commands are refused:
    :meth:`execute`, :meth:`send` and :meth:`read_reply` raise
    :class:`~benchtools.core.errors.InstrumentError` naming the firmware, so a
    method of the driver that needs ST's firmware says so rather than hang.

    Writes keep the transport's receive buffer: records arrive unasked while
    receiving, and a write that dropped them would lose frames.
    """

    def __init__(self, previous: S2lpSession, identity: KitIdentity) -> None:
        super().__init__(previous.transport, timeout=previous.timeout)
        self.identity = identity
        self.adopt_log(previous)
        self.commands_sent = previous.commands_sent
        #: Records read while waiting for an answer, oldest first.
        self.records: Deque[KitRecord] = deque()
        #: Whether ``rx start`` has been answered and ``rx stop`` not sent.
        self.receiving = False
        #: The counters ``rx stop`` last answered with.
        self.last_counters: Dict[str, int] = {}

    # ------------------------------------------------------------------
    # ST's commands: refused
    # ------------------------------------------------------------------
    def _refuse(self, name: str) -> InstrumentError:
        return InstrumentError(
            "%s needs ST's CLI firmware; this kit runs %s %s, which provides "
            "registers, strobes, shutdown and receiving only"
            % (name or "that", self.identity.name, self.identity.version))

    def send(self, name: str, *arguments) -> str:
        raise self._refuse(name)

    def execute(self, name: str, *arguments, timeout: Optional[float] = None):
        raise self._refuse(name)

    def read_reply(self, timeout: Optional[float] = None, command: str = "", expect: str = "",
                   cancel: Optional[Callable[[], bool]] = None):
        raise self._refuse(command)

    # ------------------------------------------------------------------
    # The ETB protocol
    # ------------------------------------------------------------------
    def ask(self, line: str, timeout: Optional[float] = None) -> str:
        """Send one command line, and return its answer after ``ok``.

        Records that arrive first are kept in :attr:`records`.

        :raises ProtocolError: when the firmware answers ``err``.
        :raises TransportTimeoutError: when it does not answer in time.
        """
        if len(line) > LINE_MAX:
            raise ProtocolError("%r is longer than the firmware's %d characters"
                                % (line[:40] + "...", LINE_MAX))
        self.write_line(line)
        limit = self.timeout if timeout is None else float(timeout)
        deadline = time.monotonic() + limit
        while time.monotonic() < deadline:
            text = self.read_line()
            if text is None:
                continue
            record = parse_record(text)
            if record is not None:
                self.records.append(record)
            elif text == "ok" or text.startswith("ok "):
                return text[3:]
            elif text.startswith("err"):
                raise ProtocolError("the kit firmware refused %r: %s" % (line, text[4:]))
            else:
                self.unclaimed.append(text)
        raise TransportTimeoutError("the kit firmware did not answer %r within %.3f s"
                                    % (line, limit))

    def read(self, address: int, count: int) -> List[int]:
        """*count* registers from *address*, in reads of up to 128."""
        values: List[int] = []
        for start in range(address, address + count, MAX_PAYLOAD):
            wanted = min(MAX_PAYLOAD, address + count - start)
            chunk = bytes.fromhex(self.ask("rd %02x %d" % (start, wanted)))
            if len(chunk) != wanted:
                raise ProtocolError("asked for %d register(s) from 0x%02X and got %d"
                                    % (wanted, start, len(chunk)))
            values += chunk
        return values

    def write(self, address: int, values: Sequence[int]) -> None:
        """Write consecutive registers from *address*, in writes of up to 128."""
        data = bytes(values)
        for offset in range(0, len(data), MAX_PAYLOAD):
            self.ask("wr %02x %s" % (address + offset, data[offset:offset + MAX_PAYLOAD].hex()))

    def command(self, code: int) -> int:
        """Send a command strobe; the radio's MC_STATE1/MC_STATE0 after it."""
        return int(self.ask("cmd %02x" % code), 16)

    def shutdown(self, held: bool) -> None:
        """Hold the radio in shutdown, or release it."""
        self.ask("sdn %d" % (1 if held else 0))

    def stat(self) -> Dict[str, int]:
        """The firmware's counters, from ``stat``."""
        return _counters(self.ask("stat"))

    def rx_start(self, addresses: Sequence[int]) -> None:
        """Start receiving, reading *addresses* after each frame."""
        if len(addresses) > MAX_REGISTERS:
            raise ProtocolError("the firmware reads at most %d registers per frame, not %d"
                                % (MAX_REGISTERS, len(addresses)))
        self.records.clear()
        line = "rx start"
        if addresses:
            line += " " + ",".join("%02x" % address for address in addresses)
        self.ask(line)
        self.receiving = True

    def rx_stop(self) -> Tuple[List[KitRecord], Dict[str, int]]:
        """Stop receiving: the records not yet taken, and the firmware's counters.

        :attr:`receiving` is cleared only once the board has answered, so a
        stop that timed out is tried again by :meth:`stop` (#348 review).
        """
        counters = _counters(self.ask("rx stop", timeout=max(self.timeout, STOP_TIMEOUT)))
        self.receiving = False
        self.last_counters = counters
        left = list(self.records)
        self.records.clear()
        return left, counters

    def next_record(self, timeout: Optional[float],
                    cancel: Optional[Callable[[], bool]] = None) -> Optional[KitRecord]:
        """The next record, or ``None`` when *timeout* runs out or *cancel* says so."""
        if self.records:
            return self.records.popleft()
        deadline = None if timeout is None else time.monotonic() + float(timeout)
        while deadline is None or time.monotonic() < deadline:
            if cancel is not None and cancel():
                return None
            text = self.read_line()
            if text is None:
                continue
            record = parse_record(text)
            if record is not None:
                return record
            self.unclaimed.append(text)
        return None

    def stop(self, wait: float = 2.0) -> list:
        """End a receive, if one is running. Nothing is returned: no ST replies."""
        if self.receiving:
            self.rx_stop()
        return []


def _counters(text: str) -> Dict[str, int]:
    """``name=value`` pairs as integers."""
    counters: Dict[str, int] = {}
    for word in text.split():
        name, _, value = word.partition("=")
        if value:
            counters[name] = int(value)
    return counters


# ----------------------------------------------------------------------
# A simulated kit running the ETB firmware, for tests
# ----------------------------------------------------------------------
@dataclass
class _Queued:
    kind: str
    payload: bytes = b""
    irq: int = 0
    registers: Dict[int, int] = field(default_factory=dict)
    dropped: bool = False


class SimulatedKitFirmware:  # pylint: disable=too-many-instance-attributes
    """The ETB kit firmware's protocol, answered in process.

    Frames are queued with :meth:`queue_frame` and :meth:`queue_reject`, and
    sent one per poll while receiving; those still queued at ``rx stop`` are
    sent before its answer, as the board's ring is. A queued record marked ``dropped``
    takes a sequence number and is not sent, as one the board's ring could
    not hold. Registers start at their documented reset values; the ones a
    frame sets (RSSI, PQI, ...) are given with the frame.
    """

    def __init__(self, version: str = "V1.00.0000", silicon: int = 0xC1) -> None:
        self.version = version
        self.silicon = silicon
        self.registers: Dict[int, int] = {address: entry.reset
                                          for address, entry in BY_ADDRESS.items()}
        self.registers[0xF0] = 0x03            # DEVICE_INFO1: S2-LP part number
        self.registers[0xF1] = silicon
        self.command_log: List[str] = []
        self.running = False
        self.shutdown = False
        self.addresses: List[int] = []
        self.inbound: List[_Queued] = []
        self._seq = 0
        self._time_us = 1000
        self.frames = 0
        self.rejects = 0
        self.overflows = 0

    def queue_frame(self, payload: bytes, registers: Optional[Dict[int, int]] = None,
                    dropped: bool = False) -> None:
        """Have a frame arrive while receiving."""
        self.inbound.append(_Queued("f", payload=bytes(payload),
                                    registers=dict(registers or {}), dropped=dropped))

    def queue_reject(self, irq: int = 0x02) -> None:
        """Have the radio discard a reception while receiving."""
        self.inbound.append(_Queued("r", irq=irq))

    def respond(self, message: bytes) -> Optional[bytes]:
        """Answer one command line, as the firmware does."""
        text = message.decode("ascii", errors="replace").strip()
        if not text:
            return None
        self.command_log.append(text)
        words = text.split()
        handler = getattr(self, "_do_" + words[0], None)
        if handler is None:
            return b"err unknown command\r\n"
        if self.running and words[0] in ("rd", "wr", "cmd", "sdn"):
            return b"err receiving\r\n"
        try:
            return (handler(words[1:]) + "\r\n").encode("ascii")
        except (IndexError, ValueError):
            return b"err bad argument\r\n"

    def poll(self) -> Optional[bytes]:
        """The next record, while receiving."""
        while self.running and self.inbound:
            line = self._next_line()
            if line:
                return (line + "\r\n").encode("ascii")
        return None

    def _next_line(self) -> str:
        record = self.inbound.pop(0)
        seq, self._seq = self._seq, self._seq + 1
        self._time_us = (self._time_us + 25000) & 0xFFFFFFFF
        if record.dropped:
            self.overflows += 1
            return ""
        if record.kind == "r":
            self.rejects += 1
            return "r %d %d %08x" % (seq, self._time_us, record.irq)
        self.frames += 1
        self.registers.update(record.registers)
        values = bytes(self.registers.get(address, 0) for address in self.addresses)
        return "f %d %d %d %s %s" % (seq, self._time_us, len(record.payload),
                                     values.hex() if self.addresses else "-",
                                     record.payload.hex())

    def _counters(self) -> str:
        return "frames=%d rejects=%d overflows=%d deaf_max_us=%d" % (
            self.frames, self.rejects, self.overflows, 0)

    def _do_id(self, _words: List[str]) -> str:
        return "ok %s %s proto=%d silicon=%02x" % (KIT_FIRMWARE_NAME, self.version,
                                                   KIT_PROTOCOL, self.silicon)

    def _do_rd(self, words: List[str]) -> str:
        address, count = int(words[0], 16), int(words[1])
        if not 1 <= count <= MAX_PAYLOAD:
            raise ValueError(count)
        return "ok " + bytes(self.registers.get((address + index) & 0xFF, 0)
                             for index in range(count)).hex()

    def _do_wr(self, words: List[str]) -> str:
        address, data = int(words[0], 16), bytes.fromhex(words[1])
        for index, value in enumerate(data):
            self.registers[(address + index) & 0xFF] = value
        return "ok"

    def _do_cmd(self, words: List[str]) -> str:
        int(words[0], 16)
        return "ok 0000"

    def _do_sdn(self, words: List[str]) -> str:
        if words[0] not in ("0", "1"):
            raise ValueError(words[0])
        self.shutdown = words[0] == "1"
        if not self.shutdown:
            for address, entry in BY_ADDRESS.items():
                if entry.writable:
                    self.registers[address] = entry.reset
        return "ok"

    def _do_rx(self, words: List[str]) -> str:
        if words[0] == "start" and len(words) <= 2:
            addresses = [int(word, 16) for word in words[1].split(",")] if len(words) == 2 else []
            if len(addresses) > MAX_REGISTERS:
                raise ValueError(addresses)
            self.addresses = addresses
            self._seq = self.frames = self.rejects = self.overflows = 0
            self.running = True
            return "ok"
        if words[0] == "stop" and len(words) == 1:
            # What is still inbound counts as queued on the board: sent first.
            lines = [line for line in (self._next_line() for _ in list(self.inbound)) if line]
            self.running = False
            return "\r\n".join(lines + ["ok " + self._counters()])
        raise ValueError(words)

    def _do_stat(self, _words: List[str]) -> str:
        return "ok running=%d %s queued=0 uart_overruns=0" % (int(self.running),
                                                              self._counters())
