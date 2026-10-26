"""The synthetic device's viewer panel: the last value each sender gave.

Traces to: SWE4-UT-PLUGINS (the synthetic test plugin).
"""

from __future__ import annotations

from typing import Any, Dict


class SyntheticPanel:
    """Keeps each sender's latest READING."""

    def __init__(self) -> None:
        self.latest: Dict[str, int] = {}

    def feed(self, frame: Dict[str, Any]) -> None:
        """One received frame, as the viewer's radio view holds it."""
        decoded = frame.get("decoded") or {}
        if decoded.get("type") == "READING":
            self.latest[str(decoded["sensor_id"])] = int(decoded["value"])

    def view(self, sensor: str = "") -> Dict[str, Any]:
        """The latest value of *sensor*, or of every sender."""
        if sensor:
            return {"sensor": sensor, "value": self.latest.get(sensor)}
        return {"latest": dict(self.latest)}
