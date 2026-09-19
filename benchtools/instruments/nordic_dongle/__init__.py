"""Nordic nRF52840 dongle: scan, select, UART over BLE, advertising profile.

The dongle runs the firmware in ``firmware/nordic_dongle`` and appears as a
serial port. It is a bench instrument like any other::

    from benchtools.instruments.nordic_dongle import NordicDongle

    with NordicDongle.connect("COM5", log_path="ble.log") as dongle:
        sensors = dongle.scan(3.0, name="SENS")
        dongle.select(sensors[0])

        profile = dongle.measure_advertising_profile(10.0, expected_interval=0.1)
        print(profile.mean_interval_s, profile.missed_events, profile.is_complete)

        dongle.open_link()
        timing = dongle.measure_response_time("version", repeat=10)
        print(timing.milliseconds, timing.is_trustworthy)

The dongle's firmware is part of the instrument, so the driver can tell whether
it is the build you think it is - and refresh it if not::

    with NordicDongle.connect("COM5", firmware="firmware/nordic_dongle/_build",
                              update_firmware=True) as dongle:
        print(dongle.firmware_version, dongle.firmware_built)

``sim://`` drives a deterministic model instead, so every one of those calls is
testable with no dongle, no sensor and no radio.

Traces to: BLE-ARC-001.
"""

from .constants import (
    COMMANDS,
    DEFAULT_BAUDRATE,
    DEFAULT_COMMAND_TIMEOUT,
    DEFAULT_SCAN_MS,
    DONGLE_LIMITS,
    EVENTS,
    PROTOCOL_VERSION,
    AddressType,
    DongleError,
    DongleLimits,
    ScanFilter,
)
from .dongle import NordicDongle, Sensor
from .script import (
    CommandScript,
    ScriptRun,
    ScriptStep,
    ScriptTest,
    StepResult,
    load_script,
    parse_script,
)
from .firmware import (
    MANIFEST_NAME,
    FirmwareBuild,
    FirmwareStatus,
    FirmwareUpdateError,
    parse_build_date,
)
from .latency import LatencySource, ResponseSample, ResponseTiming
from .profile import ADV_DELAY_MAX_S, COALESCE_WINDOW_S, AdvertisingEvent, AdvertisingProfile
from .protocol import (
    DongleProtocolError,
    Event,
    Reply,
    format_address,
    normalise_address,
    parse_line,
)
from .session import DongleCommandError, DongleSession
from .simulator import DEFAULT_SENSORS, SimulatedDongle, SimulatedSensor

__all__ = [
    "NordicDongle",
    "Sensor",
    "CommandScript",
    "ScriptRun",
    "ScriptStep",
    "ScriptTest",
    "StepResult",
    "load_script",
    "parse_script",
    "FirmwareBuild",
    "FirmwareStatus",
    "FirmwareUpdateError",
    "MANIFEST_NAME",
    "parse_build_date",
    "AdvertisingEvent",
    "AdvertisingProfile",
    "COALESCE_WINDOW_S",
    "ADV_DELAY_MAX_S",
    "ResponseTiming",
    "ResponseSample",
    "LatencySource",
    "DongleSession",
    "DongleCommandError",
    "DongleProtocolError",
    "SimulatedDongle",
    "SimulatedSensor",
    "DEFAULT_SENSORS",
    "Event",
    "Reply",
    "parse_line",
    "format_address",
    "normalise_address",
    "AddressType",
    "DongleError",
    "DongleLimits",
    "DONGLE_LIMITS",
    "ScanFilter",
    "COMMANDS",
    "EVENTS",
    "PROTOCOL_VERSION",
    "DEFAULT_BAUDRATE",
    "DEFAULT_SCAN_MS",
    "DEFAULT_COMMAND_TIMEOUT",
]
