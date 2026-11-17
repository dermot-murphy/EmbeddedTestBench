"""The synthetic device's viewer panel: the last value each sender gave.

It has one tab on the RF page, ``latest``; an action, ``clear``; and one
section of the report, a table of the latest values (#303).

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

    def view(self, sensor: str = "", tab: str = "latest") -> Dict[str, Any]:
        """The latest value of *sensor*, or of every sender."""
        if tab != "latest":
            raise ValueError("no tab %r" % tab)
        if sensor:
            return {"sensor": sensor, "value": self.latest.get(sensor)}
        return {"latest": dict(self.latest)}

    def action(self, name: str, sensor: str = "") -> Dict[str, Any]:
        """``clear``: forget *sensor*'s value, or every sender's."""
        if name != "clear":
            raise ValueError("no action %r" % name)
        if sensor:
            self.latest.pop(sensor, None)
        else:
            self.latest.clear()
        return {"ok": True, "cleared": sensor or "all"}

    def report(self, sensor: str = "") -> Dict[str, Any]:
        """One section: the latest value of each sender, or of *sensor*."""
        rows = [[sender, value] for sender, value in sorted(self.latest.items())
                if not sensor or sender == sensor]
        return {"sensor": sensor or (rows[0][0] if rows else ""), "sections": [
            {"title": "Synthetic readings", "blocks": [
                {"table": {"headers": ["Sender", "Value"], "rows": rows, "numeric": [1]}}
                if rows else {"note": "No READING frames."}]}]}
