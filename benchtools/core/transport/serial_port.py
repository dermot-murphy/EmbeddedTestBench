"""Transport over a serial port.

Three quite different instruments arrive through this one door: a USB CDC
device that enumerates as a serial port (the BLE dongle), a real RS-232
instrument behind a USB converter (the multimeter to come), and a serial port
published over TCP by a terminal server. They differ only in the resource
string, which is why this transport delegates to ``pyserial``'s URL handler
rather than opening a device node itself::

    serial://COM5                 a Windows port
    serial://COM5:115200          with the line rate
    serial:///dev/ttyACM0         a POSIX device
    serial://socket://host:4001   a port published by ser2net, for a container
    serial://loop://              pyserial's loopback, for tests

``pyserial`` is an optional extra. It is imported when the link is opened, not
when this module is imported, so the package still installs and runs without it
and a missing install produces a diagnostic naming the extra rather than an
``ImportError`` from an unrelated import (CORE-NFR-003).

**Why not a reader thread.** Unlike a pipe, a serial port on Windows *can* be
read with a timeout, and pyserial's ``read`` already blocks only as long as it
is told to. A thread would add a hand-off and buy nothing.

Traces to: CORE-FR-017, CORE-FR-061, CORE-ARC-003, CORE-DD-SERIAL.
"""

from __future__ import annotations

from typing import Optional, Tuple

from ..errors import ConnectionFailedError, TransportError, TransportTimeoutError
from .base import Transport

__all__ = ["SerialTransport", "DEFAULT_BAUDRATE"]


#: Line rate used when the resource does not name one. A USB CDC port ignores
#: it entirely; a real RS-232 instrument does not, and 115200 is the usual
#: setting on the converters this bench uses.
DEFAULT_BAUDRATE = 115200


class SerialTransport(Transport):
    """Talk to an instrument over a serial port.

    :param port: Port name or pyserial URL. ``COM5``, ``/dev/ttyACM0``,
        ``socket://host:4001``, ``loop://``.
    :param resource: Alias for *port*, so the transport can be selected by a
        ``serial://`` resource string. May carry a trailing ``:<baudrate>``.
    :param baudrate: Line rate. Overridden by one given in *resource*.
    :param timeout: Default I/O timeout in seconds.
    :param terminator: Line terminator.
    :param bytesize: Data bits.
    :param parity: ``"N"``, ``"E"``, ``"O"``, ``"M"`` or ``"S"``.
    :param stopbits: Stop bits, 1, 1.5 or 2.
    :param rtscts: Hardware flow control.
    :param xonxoff: Software flow control.
    :param dsrdtr: DSR/DTR flow control.
    :param dtr: Drive the DTR line to this state after opening, or leave it
        alone when ``None``. Some instruments take their interface power from
        the handshake lines rather than using them for flow control; the TTi
        1604's opto-isolated interface is one, and is simply absent until DTR
        is asserted.
    :param rts: Drive the RTS line to this state after opening, or leave it
        alone when ``None``.
    """

    def __init__(
        self,
        port: Optional[str] = None,
        resource: Optional[str] = None,
        baudrate: int = DEFAULT_BAUDRATE,
        timeout: float = 10.0,
        terminator: bytes = b"\n",
        bytesize: int = 8,
        parity: str = "N",
        stopbits: float = 1,
        rtscts: bool = False,
        xonxoff: bool = False,
        dsrdtr: bool = False,
        dtr: Optional[bool] = None,
        rts: Optional[bool] = None,
    ) -> None:
        super().__init__(timeout=timeout, terminator=terminator)
        target = port if port is not None else resource
        if not target:
            raise ValueError("a serial port is required")
        self._port, self._baudrate = self._split_baudrate(str(target), int(baudrate))
        self._bytesize = int(bytesize)
        self._parity = str(parity).upper()[:1] or "N"
        self._stopbits = stopbits
        self._rtscts = bool(rtscts)
        self._xonxoff = bool(xonxoff)
        self._dsrdtr = bool(dsrdtr)
        self._dtr = dtr
        self._rts = rts
        self._serial = None

    # ------------------------------------------------------------------
    @staticmethod
    def _split_baudrate(target: str, default: int) -> Tuple[str, int]:
        """Separate a trailing ``:<baudrate>`` from the port name.

        Only a trailing group of digits counts, so ``socket://host:4001`` keeps
        its port number and ``COM5:115200`` gives up its line rate.
        """
        head, separator, tail = target.rpartition(":")
        if separator and tail.isdigit() and "://" not in tail:
            if "://" in head and head.rpartition("/")[2].count(".") == 0 and not head.endswith("/"):
                # socket://host:4001 - the number is a TCP port, not a rate.
                return target, default
            if head:
                return head, int(tail)
        return target, default

    @property
    def port(self) -> str:
        """The port this transport opens."""
        return self._port

    @property
    def baudrate(self) -> int:
        """The configured line rate."""
        return self._baudrate

    @property
    def description(self) -> str:
        return "serial %s" % self._port

    # ------------------------------------------------------------------
    def _open_link(self) -> None:
        try:
            import serial                               # noqa: F401  (optional extra)
        except ImportError as exc:                      # pragma: no cover - env dependent
            raise ConnectionFailedError(
                "the serial transport needs pyserial, which is not installed. "
                "Install it with: pip install benchtools[serial]"
            ) from exc

        try:
            self._serial = serial.serial_for_url(
                self._port,
                baudrate=self._baudrate,
                bytesize=self._bytesize,
                parity=self._parity,
                stopbits=self._stopbits,
                rtscts=self._rtscts,
                xonxoff=self._xonxoff,
                dsrdtr=self._dsrdtr,
                timeout=self._timeout,
                write_timeout=self._timeout,
                do_not_open=True,
            )
            self._serial.open()
        except Exception as exc:                        # serial.SerialException et al
            self._serial = None
            raise ConnectionFailedError(
                "cannot open %s: %s. Check the device is plugged in, that the "
                "name is right (COM5 on Windows, /dev/ttyACM0 on Linux), and "
                "that nothing else has the port open."
                % (self._port, exc)
            ) from exc

        # Set the handshake lines before anything is read. Where they power an
        # opto-isolated interface rather than carrying flow control, the device
        # is mute until they are right, and that presents as a dead port.
        for line, state in (("dtr", self._dtr), ("rts", self._rts)):
            if state is None:
                continue
            try:
                setattr(self._serial, line, bool(state))
            except (AttributeError, OSError, ValueError):  # pragma: no cover - URL handlers
                # Not every pyserial URL handler exposes the modem lines.
                # serial.SerialException is an OSError, so this covers a real
                # port refusing the change as well as a handler without it.
                self._logger.debug("cannot set %s on %s", line, self._port, exc_info=True)

        # Discard whatever the device said before anyone was listening: a boot
        # banner read as the answer to the first command is a confusing failure.
        try:
            self._serial.reset_input_buffer()
            self._serial.reset_output_buffer()
        except Exception:                               # pragma: no cover - URL handlers
            pass

    def discard_input(self) -> int:
        """Drop everything received and not yet read, including the OS buffer.

        An instrument that streams readings fills the operating system's
        receive buffer while nobody is reading; without this, the next read
        returns a reading that may be minutes old (CORE-FR-061).
        """
        dropped = super().discard_input()
        if self._serial is not None:
            try:
                dropped += int(self._serial.in_waiting or 0)
            except Exception:  # pylint: disable=broad-exception-caught  # pragma: no cover
                pass
            try:
                self._serial.reset_input_buffer()
            except Exception:  # pylint: disable=broad-exception-caught  # pragma: no cover
                self._logger.debug("could not reset the input buffer of %s", self._port,
                           exc_info=True)
        return dropped

    def _close_link(self) -> None:
        port, self._serial = self._serial, None
        if port is None:
            return
        try:
            port.close()
        except Exception:                               # pragma: no cover - defensive
            self._logger.debug("error closing %s", self._port, exc_info=True)

    def _send(self, data: bytes) -> None:
        if self._serial is None:
            raise TransportError("%s is not open" % self.description)
        try:
            self._serial.write(data)
            self._serial.flush()
        except Exception as exc:
            # A write timeout is a different fault from a broken port: the port
            # is fine and the far end is not taking the data - flow control
            # asserted, or a device that stopped reading. Reporting both as a
            # connection failure sends the reader looking at the cable.
            # SerialTimeoutException on a real port; queue.Full from
            # pyserial's own loopback and socket handlers, which raise the
            # timeout their internal queue raises.
            if type(exc).__name__ in ("SerialTimeoutException", "Full"):
                raise TransportTimeoutError(
                    "%s accepted no more data within %.3f s after %d byte(s). "
                    "The far end is not reading: check flow control (rtscts) "
                    "and that the device is running."
                    % (self.description, self._timeout, len(data))
                ) from exc
            raise ConnectionFailedError(
                "write to %s failed: %s" % (self._port, exc)
            ) from exc

    def _recv_chunk(self, max_bytes: int) -> Tuple[bytes, bool]:
        if self._serial is None:
            raise TransportError("%s is not open" % self.description)
        try:
            # Only when it has changed. pyserial reconfigures the port on every
            # assignment, and on Windows that loses bytes: a GPD-3303D on an
            # FTDI adapter dropped about one reply in five until this was
            # guarded.
            if self._serial.timeout != self._timeout:
                self._serial.timeout = self._timeout
            first = self._serial.read(1)
            if not first:
                raise TransportTimeoutError(
                    "no data from %s within %.3f s" % (self.description, self._timeout)
                )
            waiting = 0
            try:
                waiting = self._serial.in_waiting
            except Exception:                           # pragma: no cover - URL handlers
                waiting = 0
            extra = b""
            if waiting:
                extra = self._serial.read(min(waiting, max_bytes - 1))
            return first + extra, False
        except TransportTimeoutError:
            raise
        except Exception as exc:
            raise ConnectionFailedError(
                "read from %s failed: %s" % (self._port, exc)
            ) from exc
