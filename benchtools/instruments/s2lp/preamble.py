"""Measuring a transmitter's preamble length from PQI.

PQI (LINK_QUALIF2) is the S2-LP's preamble quality indicator. Measured on the
kit (#87, #89) against the Kepler sensor, with the PQI check enabled
(QI.PQI_TH > 0): a 64-bit preamble read 63, a 256-bit preamble read 255. PQI
tracks the preamble the receiver heard, one count per bit after the first, up
to the register's full scale of 255. With the check disabled - QI.PQI_TH = 0,
the reset value - PQI reads 0 whatever was sent.

So PQI is a test of the transmitter's preamble length, with two limits:

* **A frame caught part-way reads low.** The receiver hears only the preamble
  after it started listening. The *maximum* over several frames is the
  measurement; any single frame is a lower bound.
* **255 is a ceiling.** A preamble of 256 bits or more reads 255, so 127
  pairs (254 bits) is the longest that can be told apart from a longer one.

The sensor configures its preamble in bit-pairs (``WR PREAMBLE-LENGTH``), so
the expected PQI for *pairs* is ``2 * pairs - 1``.

Traces to: S2LP-FR-049, S2LP-DD-PREAMBLE.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

__all__ = [
    "PQI_CEILING",
    "PreambleMeasurement",
    "PreambleCheck",
    "expected_pqi",
    "check_preamble",
]

#: LINK_QUALIF2 is 8 bits wide; a preamble of 256 bits or more reads this.
PQI_CEILING = 255

#: Longest preamble, in bit-pairs, whose PQI is below the ceiling.
LONGEST_MEASURABLE_PAIRS = PQI_CEILING // 2


def expected_pqi(pairs: int) -> int:
    """The PQI a preamble of *pairs* bit-pairs should read, at most 255."""
    return min(2 * int(pairs) - 1, PQI_CEILING)


@dataclass
class PreambleMeasurement:
    """PQI readings from one transmitter.

    :param source: Who sent the frames, for example a sensor ID.
    :param pqi: Every frame's PQI, in arrival order.
    """

    source: str
    pqi: List[int] = field(default_factory=list)

    @property
    def frames(self) -> int:
        """Frames heard from this source."""
        return len(self.pqi)

    @property
    def max_pqi(self) -> Optional[int]:
        """The measurement: the best-heard frame."""
        return max(self.pqi) if self.pqi else None

    @property
    def saturated(self) -> bool:
        """True when the best frame read the ceiling, so the preamble may be longer."""
        return self.max_pqi == PQI_CEILING

    @property
    def preamble_bits(self) -> Optional[int]:
        """Preamble bits the best frame showed: PQI + 1. A lower bound when saturated."""
        return None if self.max_pqi is None else self.max_pqi + 1

    @property
    def preamble_pairs(self) -> Optional[float]:
        """:attr:`preamble_bits` in bit-pairs, the unit the sensor is set in."""
        return None if self.preamble_bits is None else self.preamble_bits / 2.0

    def as_dict(self) -> Dict[str, Any]:
        """The measurement as plain data, for JSON and the runner."""
        return {
            "source": self.source,
            "frames": self.frames,
            "pqi": list(self.pqi),
            "max_pqi": self.max_pqi,
            "preamble_bits": self.preamble_bits,
            "preamble_pairs": self.preamble_pairs,
            "saturated": self.saturated,
        }


@dataclass
class PreambleCheck:
    """A measurement compared with the preamble the transmitter was set to."""

    measurement: PreambleMeasurement
    expected_pairs: int
    tolerance_pairs: int
    verdict: str
    reason: str

    @property
    def passed(self) -> bool:
        """True only for a pass; unmeasurable is not a pass."""
        return self.verdict == "pass"

    def as_dict(self) -> Dict[str, Any]:
        """The check and its measurement as plain data, for JSON and the runner."""
        result = self.measurement.as_dict()
        result.update({
            "expected_pairs": self.expected_pairs,
            "expected_pqi": expected_pqi(self.expected_pairs),
            "tolerance_pairs": self.tolerance_pairs,
            "verdict": self.verdict,
            "passed": self.passed,
            "reason": self.reason,
        })
        return result


def check_preamble(measurement: PreambleMeasurement, expected_pairs: int,
                   tolerance_pairs: int = 2) -> PreambleCheck:
    """Compare a measurement with the preamble the transmitter was set to.

    :param tolerance_pairs: How many bit-pairs the best frame may fall short
        by, for a receiver that locked on a little late.
    :returns: A check whose verdict is ``"pass"``, ``"fail"``, or
        ``"unmeasurable"``. It is unmeasurable when the expected preamble is
        at or beyond PQI's ceiling, or when no frame was heard. A test must
        not count unmeasurable as a pass.
    """
    expected = expected_pqi(expected_pairs)
    best = measurement.max_pqi

    def result(verdict: str, reason: str) -> PreambleCheck:
        return PreambleCheck(measurement, int(expected_pairs), int(tolerance_pairs),
                             verdict, reason)

    if best is None:
        return result("unmeasurable", "no frame was heard from %s" % measurement.source)
    if expected >= PQI_CEILING:
        return result("unmeasurable",
                      "%d pairs is %d bits, at or past PQI's ceiling of %d; lengths above "
                      "%d pairs cannot be told apart"
                      % (expected_pairs, 2 * expected_pairs, PQI_CEILING,
                         LONGEST_MEASURABLE_PAIRS))
    low = expected - 2 * int(tolerance_pairs)
    if best > expected:
        return result("fail", "best PQI %d is above the %d expected for %d pairs: the "
                      "preamble is longer than set" % (best, expected, expected_pairs))
    if best < low:
        return result("fail", "best PQI %d is below %d (%d pairs, less %d pairs tolerance) "
                      "over %d frame(s): the preamble is shorter than set, or every frame "
                      "was caught late" % (best, low, expected_pairs, tolerance_pairs,
                                            measurement.frames))
    return result("pass", "best PQI %d for %d pairs (expected %d, lowest accepted %d)"
                  % (best, expected_pairs, expected, low))
