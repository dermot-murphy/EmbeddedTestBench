"""The bench: which instruments exist, where they are, and how to reach them.

Separating the bench from the test specification is what makes a specification
portable. The same suite runs on the real rig, on a second rig with different
addresses, or entirely against simulators, by pointing the runner at a different
bench configuration - with no change to the test.

Example (YAML)::

    name: EMC bench 2
    instruments:
      scope:
        driver: tek3014b
        resource: 192.168.1.50
        timeout: 10.0
      psu:
        driver: generic
        resource: 192.168.1.60

Drivers are named, not imported by the specification, so a test file cannot
reach arbitrary code. New drivers are added with :func:`register_driver`.

Traces to: RUN-FR-001 .. RUN-FR-005, RUN-FR-037, RUN-DD-BENCH.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, Optional, Type

from ..core.errors import BenchConfigError, BenchToolsError
from ..core.instrument import Instrument
from ..instruments.generic import GenericScpiInstrument
from ..instruments.jlink import JLinkProbe
from ..instruments.gpd2303s import Gpd2303S
from ..instruments.nordic_dongle import NordicDongle
from ..instruments.s2lp import S2lpDevkit
from ..instruments.tek3014b import Tek3014B

__all__ = [
    "InstrumentConfig",
    "BenchConfig",
    "Bench",
    "register_driver",
    "registered_drivers",
]

_LOG = logging.getLogger(__name__)

#: Driver name to class. Extended with :func:`register_driver`.
_DRIVERS: Dict[str, Type[Instrument]] = {}


def register_driver(name: str, driver: Type[Instrument]) -> None:
    """Register an instrument driver under the name a bench config uses."""
    _DRIVERS[name.lower()] = driver


def registered_drivers() -> tuple:
    """Return the registered driver names."""
    return tuple(sorted(_DRIVERS))


register_driver("tek3014b", Tek3014B)
register_driver("tds3014b", Tek3014B)
register_driver("generic", GenericScpiInstrument)
register_driver("scpi", GenericScpiInstrument)
register_driver("jlink", JLinkProbe)
register_driver("segger", JLinkProbe)
register_driver("ble-dongle", NordicDongle)
register_driver("nordic", NordicDongle)
register_driver("gpd2303s", Gpd2303S)
register_driver("gwinstek-psu", Gpd2303S)
register_driver("s2lp", S2lpDevkit)
register_driver("s2lp-devkit", S2lpDevkit)


@dataclass(frozen=True)
class InstrumentConfig:
    """How to reach one instrument.

    :param alias: Name the test specification refers to it by.
    :param driver: Registered driver name.
    :param resource: Address or resource string; ``sim://`` for a simulator.
    :param timeout: I/O timeout in seconds.
    :param options: Extra keyword arguments for the driver's ``connect``.
    """

    alias: str
    driver: str
    resource: str
    timeout: float = 10.0
    options: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, alias: str, data) -> "InstrumentConfig":
        if isinstance(data, str):          # shorthand: alias: "tek3014b@1.2.3.4"
            driver, separator, resource = data.partition("@")
            if not separator:
                raise BenchConfigError(
                    "instrument %r shorthand must be '<driver>@<resource>', got %r"
                    % (alias, data)
                )
            return cls(alias=alias, driver=driver.strip(), resource=resource.strip())
        if not isinstance(data, dict):
            raise BenchConfigError(
                "instrument %r must be a mapping or a '<driver>@<resource>' string" % alias
            )
        driver = data.get("driver")
        if not driver:
            raise BenchConfigError("instrument %r has no driver" % alias)
        if str(driver).lower() not in _DRIVERS:
            raise BenchConfigError(
                "instrument %r names unknown driver %r; registered drivers are %s"
                % (alias, driver, ", ".join(registered_drivers()))
            )
        resource = data.get("resource", "sim://")
        options = dict(data.get("options", {}) or {})
        try:
            timeout = float(data.get("timeout", 10.0))
        except (TypeError, ValueError) as exc:
            raise BenchConfigError("instrument %r has a non-numeric timeout" % alias) from exc
        return cls(
            alias=alias,
            driver=str(driver).lower(),
            resource=str(resource),
            timeout=timeout,
            options=options,
        )


@dataclass(frozen=True)
class BenchConfig:
    """A named collection of instruments."""

    name: str
    instruments: Dict[str, InstrumentConfig]
    description: str = ""
    source: str = ""

    @classmethod
    def from_mapping(cls, data, source: str = "") -> "BenchConfig":
        if not isinstance(data, dict):
            raise BenchConfigError("bench configuration must be a mapping")
        instruments = data.get("instruments")
        if not instruments:
            raise BenchConfigError("bench configuration lists no instruments")
        if not isinstance(instruments, dict):
            raise BenchConfigError("'instruments' must be a mapping of alias to definition")
        return cls(
            name=str(data.get("name", "bench")),
            description=str(data.get("description", "")),
            instruments={
                alias: InstrumentConfig.from_mapping(alias, definition)
                for alias, definition in instruments.items()
            },
            source=source,
        )

    @classmethod
    def simulated(cls, aliases, driver: str = "tek3014b") -> "BenchConfig":
        """Build a bench where every named instrument is a simulator.

        Used by ``--simulate`` and by the test suite, so a specification can be
        exercised with no hardware and no separate configuration file.

        :param aliases: Either a sequence of alias names, all given *driver*, or a
            mapping of alias to driver name. The mapping form is what a
            specification's ``instruments`` block provides, and is the only way a
            suite spanning different instrument types can be simulated without a
            bench file.
        :param driver: Driver for aliases with none declared.
        """
        if isinstance(aliases, dict):
            wanted = {str(alias): str(name or driver) for alias, name in aliases.items()}
        else:
            wanted = {str(alias): driver for alias in aliases}
        unknown = sorted(name for name in wanted.values() if name.lower() not in _DRIVERS)
        if unknown:
            raise BenchConfigError(
                "cannot simulate unknown driver(s) %s; registered drivers are %s"
                % (", ".join(unknown), ", ".join(registered_drivers()))
            )
        return cls(
            name="simulated bench",
            description="every instrument replaced by its simulator",
            instruments={
                alias: InstrumentConfig(alias=alias, driver=name.lower(), resource="sim://")
                for alias, name in wanted.items()
            },
        )


def load_bench(path: str) -> BenchConfig:
    """Load a bench configuration from a JSON or YAML file."""
    from .spec import load_mapping

    return BenchConfig.from_mapping(load_mapping(path), source=path)


class Bench:
    """Live instruments for a run, connected on first use.

    Instruments are connected lazily so that a suite touching one instrument
    does not require every instrument on the bench to be powered up. Whatever
    was opened is closed on exit, including after a failure.

    :param config: The bench configuration.
    :param simulate: Ignore configured resources and use each driver's
        simulator, for a dry run of a specification.
    """

    def __init__(self, config: BenchConfig, simulate: bool = False) -> None:
        self.config = config
        self.simulate = bool(simulate)
        self._open: Dict[str, Instrument] = {}

    # ------------------------------------------------------------------
    def require(self, aliases) -> None:
        """Raise if the bench does not define every alias in *aliases*."""
        missing = [alias for alias in aliases if alias not in self.config.instruments]
        if missing:
            raise BenchConfigError(
                "the specification uses instrument(s) %s, which the bench %r does "
                "not define; it provides %s"
                % (
                    ", ".join(repr(item) for item in missing),
                    self.config.name,
                    ", ".join(sorted(self.config.instruments)) or "none",
                )
            )

    def check_drivers(self, declared) -> None:
        """Raise if the bench provides a different *kind* of instrument.

        A specification that declares ``probe: jlink`` pointed at a bench whose
        ``probe`` is an oscilloscope should say so here, rather than failing four
        steps later on a missing method.

        Driver *classes* are compared rather than names, because several names
        map to one driver (``jlink`` and ``segger``, ``tek3014b`` and ``tds3014b``).
        """
        for alias, wanted in (declared or {}).items():
            configured = self.config.instruments.get(alias)
            if configured is None:
                continue                      # require() reports a missing alias
            expected = _DRIVERS.get(str(wanted).lower())
            actual = _DRIVERS.get(configured.driver)
            if expected is None:
                raise BenchConfigError(
                    "the specification wants instrument %r to be driver %r, which "
                    "is not registered; registered drivers are %s"
                    % (alias, wanted, ", ".join(registered_drivers()))
                )
            if actual is not expected:
                raise BenchConfigError(
                    "the specification wants instrument %r to be a %s, but bench "
                    "%r provides a %s"
                    % (alias, expected.__name__, self.config.name,
                       actual.__name__ if actual else configured.driver)
                )

    def get(self, alias: str) -> Instrument:
        """Return the instrument registered as *alias*, connecting if needed."""
        if alias in self._open:
            return self._open[alias]
        if alias not in self.config.instruments:
            raise BenchConfigError(
                "no instrument called %r on bench %r; it provides %s"
                % (alias, self.config.name, ", ".join(sorted(self.config.instruments)) or "none")
            )
        definition = self.config.instruments[alias]
        driver = _DRIVERS[definition.driver]
        resource = "sim://" if self.simulate else definition.resource
        _LOG.info("connecting %s (%s) at %s", alias, definition.driver, resource)
        instrument = driver.connect(
            resource,
            timeout=definition.timeout,
            **definition.options,
        )
        self._open[alias] = instrument
        return instrument

    @property
    def is_simulated(self) -> bool:
        """``True`` when no instrument on this bench is real hardware.

        True either because ``--simulate`` was given, or because every
        configured resource already points at a simulator. Both cases must be
        disclosed in a report: otherwise simulated numbers read as hardware
        measurements.
        """
        if self.simulate:
            return True
        resources = [item.resource.strip().lower() for item in self.config.instruments.values()]
        return bool(resources) and all(
            resource.startswith(("sim://", "mock://")) or resource in ("sim", "mock")
            for resource in resources
        )

    @property
    def connected(self) -> Dict[str, Instrument]:
        """Instruments connected so far."""
        return dict(self._open)

    def describe_instruments(self) -> Dict[str, Dict[str, str]]:
        """What each open instrument says it is, for the run record.

        Identification is asked of the instrument, not taken from the bench
        configuration: the configuration says what was *meant* to be there, and
        the point of this is to record what actually answered - including which
        firmware it was running, which for a programmable instrument decides
        whether its numbers mean what they appear to mean.
        """
        described: Dict[str, Dict[str, str]] = {}
        for alias, instrument in self._open.items():
            configured = self.config.instruments.get(alias)
            entry = {
                "driver": type(instrument).__name__,
                "resource": configured.resource if configured else "",
            }
            try:
                identity = instrument.identify()
                entry.update(
                    {
                        "manufacturer": identity.manufacturer,
                        "model": identity.model,
                        "serial_number": identity.serial_number,
                        "firmware": identity.firmware,
                        "identity": identity.raw,
                    }
                )
            except BenchToolsError as exc:
                # An instrument that will not say what it is still belongs in
                # the record, with the reason it would not.
                entry["identity_error"] = str(exc)
            described[alias] = entry
        return described

    def close(self) -> None:
        """Close every connected instrument, reporting but not raising errors."""
        for alias, instrument in list(self._open.items()):
            try:
                instrument.close()
            except Exception:  # pragma: no cover - defensive
                _LOG.warning("error closing %s", alias, exc_info=True)
            finally:
                self._open.pop(alias, None)

    def __enter__(self) -> "Bench":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.close()
        return False

    def __iter__(self) -> Iterator[str]:
        return iter(sorted(self.config.instruments))
