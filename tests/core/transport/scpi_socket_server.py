"""A loopback SCPI-over-TCP server, standing in for a raw-socket instrument.

The TDS3014B has no raw socket, but later scopes on the same command set do,
so the socket transport needs the same level of test as the VXI-11 one.

Traces to: SWE4-UT-SOCKET.
"""

from __future__ import annotations

import socket
import threading
from typing import Optional

from benchtools.instruments.tek3014b.simulator import SimulatedTDS3014B


class ScpiSocketServer:
    """Serves one simulated instrument over a line-oriented TCP socket."""

    def __init__(self, simulator: Optional[SimulatedTDS3014B] = None) -> None:
        self.simulator = simulator or SimulatedTDS3014B()
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.bind(("127.0.0.1", 0))
        self._socket.listen(4)
        self._socket.settimeout(0.1)
        self.port = self._socket.getsockname()[1]
        self._running = True
        self._thread = threading.Thread(target=self._accept_loop, daemon=True)
        self._thread.start()

    def _accept_loop(self) -> None:
        while self._running:
            try:
                connection, _ = self._socket.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            connection.settimeout(5.0)
            threading.Thread(target=self._serve, args=(connection,), daemon=True).start()

    def _serve(self, connection: socket.socket) -> None:
        buffer = bytearray()
        with connection:
            while self._running:
                try:
                    chunk = connection.recv(4096)
                except socket.timeout:
                    continue
                except OSError:
                    return
                if not chunk:
                    return
                buffer.extend(chunk)
                while b"\n" in buffer:
                    line, _, rest = bytes(buffer).partition(b"\n")
                    buffer = bytearray(rest)
                    reply = self.simulator.respond(line.strip())
                    if reply:
                        try:
                            connection.sendall(reply)
                        except OSError:
                            return

    def close(self) -> None:
        """Stop serving and release the listening socket."""
        self._running = False
        try:
            self._socket.close()
        except OSError:
            pass
        self._thread.join(timeout=2.0)

    def __enter__(self) -> "ScpiSocketServer":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.close()
        return False
