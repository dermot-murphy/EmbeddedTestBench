"""Command-line front end for the TDS3014B driver.

Run ``python -m tek3014b --help`` for usage. Every sub-command accepts
``--resource sim://`` so the whole tool can be exercised, and demonstrated,
without an instrument on the bench.

Traces to: SWE1-FR-100, SWE3-DD-CLI.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from typing import Dict, List, Optional, Sequence

from . import __version__
from .constants import EdgeDirection, ImageFormat, MeasurementType
from .errors import Tek3014BError
from .scope import Tek3014B

_LOG = logging.getLogger("tek3014b")

_EXIT_OK = 0
_EXIT_ERROR = 1
_EXIT_USAGE = 2


# ---------------------------------------------------------------------------
# Argument helpers
# ---------------------------------------------------------------------------
def _parse_channels(text: str) -> List[int]:
    """Parse ``"1,2,4"`` into ``[1, 2, 4]``."""
    channels = []
    for token in text.split(","):
        token = token.strip()
        if not token:
            continue
        try:
            channels.append(int(token))
        except ValueError:
            raise argparse.ArgumentTypeError("%r is not a channel number" % token)
    if not channels:
        raise argparse.ArgumentTypeError("no channels given")
    return channels


def _per_channel(text: Optional[str], channels: Sequence[int], name: str) -> Dict[int, float]:
    """Expand a scalar or comma list into a per-channel mapping.

    ``"1.0"`` applies to every channel; ``"1.0,2.0"`` applies positionally.
    """
    if text is None:
        return {}
    values = [token.strip() for token in str(text).split(",") if token.strip()]
    try:
        numbers = [float(value) for value in values]
    except ValueError:
        raise SystemExit("%s: %r is not a number or a comma-separated list" % (name, text))
    if len(numbers) == 1:
        return {channel: numbers[0] for channel in channels}
    if len(numbers) != len(channels):
        raise SystemExit(
            "%s: expected 1 value or %d values (one per channel), got %d"
            % (name, len(channels), len(numbers))
        )
    return dict(zip(channels, numbers))


def _apply_setup(scope: Tek3014B, args: argparse.Namespace, channels: Sequence[int]) -> None:
    """Apply the vertical, horizontal and trigger settings from *args*."""
    volts = _per_channel(args.vdiv, channels, "--vdiv")
    positions = _per_channel(args.position, channels, "--position")
    offsets = _per_channel(args.offset, channels, "--offset")

    for channel in channels:
        scope.configure_channel(
            channel,
            enabled=True,
            volts_per_div=volts.get(channel),
            position_div=positions.get(channel),
            offset_v=offsets.get(channel),
            coupling=args.coupling,
            bandwidth=args.bandwidth,
        )

    if args.tdiv is not None:
        scope.set_time_per_div(args.tdiv)
    if args.record_length is not None:
        scope.set_record_length(args.record_length)

    if args.trigger_source is not None or args.trigger_level is not None:
        scope.configure_edge_trigger(
            source=args.trigger_source if args.trigger_source is not None else channels[0],
            level=args.trigger_level if args.trigger_level is not None else 0.0,
            slope=args.trigger_slope,
            mode=args.trigger_mode,
        )


def _emit(payload: dict, path: Optional[str]) -> None:
    """Print *payload* as JSON, and also write it to *path* when given."""
    text = json.dumps(payload, indent=2, sort_keys=True, default=str)
    print(text)
    if path:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text + "\n")
        _LOG.info("wrote %s", path)


# ---------------------------------------------------------------------------
# Sub-commands
# ---------------------------------------------------------------------------
def _cmd_idn(scope: Tek3014B, args: argparse.Namespace) -> int:
    _emit(
        {
            "identity": scope.identity(),
            "model": scope.model,
            "transport": scope.transport.description,
            "enabled_channels": scope.enabled_channels(),
            "time_per_div_s": scope.get_time_per_div(),
            "record_length": scope.get_record_length(),
        },
        args.json,
    )
    return _EXIT_OK


def _cmd_screenshot(scope: Tek3014B, args: argparse.Namespace) -> int:
    path = scope.screenshot(
        args.output,
        image_format=args.format,
        palette=args.palette,
        layout=args.layout,
    )
    _emit({"screenshot": path, "format": str(args.format)}, args.json)
    return _EXIT_OK


def _cmd_capture(scope: Tek3014B, args: argparse.Namespace) -> int:
    channels = args.channels
    _apply_setup(scope, args, channels)
    waveforms = scope.capture_single(channels, timeout=args.timeout, width=args.width)

    result = {
        "channels": {},
        "points": len(waveforms[channels[0]]),
        "sample_interval_s": waveforms[channels[0]].sample_interval,
    }
    for channel, waveform in sorted(waveforms.items()):
        result["channels"][str(channel)] = {
            "min_v": waveform.minimum,
            "max_v": waveform.maximum,
            "peak_to_peak_v": waveform.peak_to_peak,
            "mean_v": waveform.mean,
            "clipped_samples": waveform.clipped_sample_count,
        }

    if args.csv:
        result["csv"] = scope.save_csv(waveforms, args.csv)
    if args.plot:
        from .plotting import plot_waveforms
        result["plot"] = plot_waveforms(waveforms, args.plot, title=args.title)
    if args.screenshot:
        result["screenshot"] = scope.screenshot(args.screenshot)

    _emit(result, args.json)
    return _EXIT_OK


def _cmd_spread(scope: Tek3014B, args: argparse.Namespace) -> int:
    channels = args.channels
    if len(channels) < 2:
        raise SystemExit("spread: at least two channels are required")
    _apply_setup(scope, args, channels)

    waveforms, spread = scope.measure_channel_spread(
        channels,
        direction=args.direction,
        percent=args.percent,
        absolute_threshold=args.threshold,
        edge_index=args.edge_index,
        reference=args.reference,
        timeout=args.timeout,
    )

    result = spread.as_dict()
    result["spread_ns"] = spread.spread * 1e9
    result["clipped_samples"] = {
        str(channel): waveform.clipped_sample_count for channel, waveform in sorted(waveforms.items())
    }

    if args.csv:
        result["csv"] = scope.save_csv(waveforms, args.csv)
    if args.plot:
        from .plotting import plot_waveforms
        result["plot"] = plot_waveforms(waveforms, args.plot, title=args.title, spread=spread)
    if args.screenshot:
        result["screenshot"] = scope.screenshot(args.screenshot)

    _emit(result, args.json)
    return _EXIT_OK


def _cmd_period(scope: Tek3014B, args: argparse.Namespace) -> int:
    channel = args.channels[0]
    _apply_setup(scope, args, [channel])
    waveforms, period = scope.measure_period_host(channel, timeout=args.timeout)

    result = period.as_dict()
    result["mean_ns"] = period.mean * 1e9
    result["instrument_period_s"] = None
    try:
        result["instrument_period_s"] = scope.measure_period(channel)
    except Tek3014BError as exc:
        _LOG.warning("instrument-side period measurement unavailable: %s", exc)

    if args.csv:
        result["csv"] = scope.save_csv(waveforms, args.csv)
    if args.plot:
        from .plotting import plot_waveforms
        result["plot"] = plot_waveforms(waveforms, args.plot, title=args.title)

    _emit(result, args.json)
    return _EXIT_OK


def _cmd_measure(scope: Tek3014B, args: argparse.Namespace) -> int:
    channel = args.channels[0]
    _apply_setup(scope, args, args.channels)
    if args.type:
        value = scope.measure(
            args.type,
            source1=channel,
            source2=args.source2,
            edge1=args.edge1,
            edge2=args.edge2,
        )
        result = {"type": str(args.type), "source": channel, "value": value,
                  "units": scope.measure_units()}
    else:
        result = {"source": channel, "measurements": scope.measure_summary(channel)}
    _emit(result, args.json)
    return _EXIT_OK


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    """Construct the argument parser."""
    parser = argparse.ArgumentParser(
        prog="tek3014b",
        description=(
            "Control a Tektronix TDS3014B oscilloscope over Ethernet. "
            "No VISA installation is required: a bare IP address uses the "
            "built-in VXI-11 transport."
        ),
        epilog="Use --resource sim:// to run against the built-in simulator.",
    )
    parser.add_argument("--version", action="version", version="tek3014b %s" % __version__)
    parser.add_argument(
        "-r", "--resource", default="sim://",
        help="instrument address: an IP/host name, a VISA-style resource string, "
             "or sim:// for the simulator (default: %(default)s)",
    )
    parser.add_argument(
        "-b", "--backend", default="auto",
        choices=("auto", "vxi11", "socket", "visa", "sim"),
        help="transport backend (default: %(default)s)",
    )
    parser.add_argument("-t", "--timeout", type=float, default=10.0,
                        help="I/O and acquisition timeout in seconds (default: %(default)s)")
    parser.add_argument("-v", "--verbose", action="count", default=0,
                        help="increase logging (repeat for debug)")
    parser.add_argument("--json", metavar="PATH", help="also write the result as JSON to PATH")
    parser.add_argument("--no-error-check", action="store_true",
                        help="skip querying the instrument's event queue after each setup step")

    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_setup_options(sub, default_channels="1"):
        sub.add_argument("-c", "--channels", type=_parse_channels, default=_parse_channels(default_channels),
                         help="channels to use, e.g. 1,2,3,4 (default: %s)" % default_channels)
        sub.add_argument("--vdiv", help="volts/division: one value, or one per channel")
        sub.add_argument("--position", help="vertical position in divisions: one value, or one per channel")
        sub.add_argument("--offset", help="vertical offset in volts: one value, or one per channel")
        sub.add_argument("--coupling", choices=("AC", "DC", "GND"), help="input coupling")
        sub.add_argument("--bandwidth", choices=("TWENTY", "ONEFIFTY", "FULL"), help="bandwidth limit")
        sub.add_argument("--tdiv", type=float, help="time per division in seconds, e.g. 200e-9")
        sub.add_argument("--record-length", type=int, choices=(500, 10000), help="record length in points")
        sub.add_argument("--trigger-source", type=int, help="trigger source channel")
        sub.add_argument("--trigger-level", type=float, help="trigger level in volts")
        sub.add_argument("--trigger-slope", default="RISE", choices=("RISE", "FALL"), help="trigger slope")
        sub.add_argument("--trigger-mode", default="NORMAL", choices=("AUTO", "NORMAL"), help="trigger mode")
        sub.add_argument("--title", default="Tektronix TDS3014B capture", help="plot title")

    identify = subparsers.add_parser("idn", help="identify the instrument and report its state")
    identify.set_defaults(handler=_cmd_idn)

    shot = subparsers.add_parser("screenshot", help="capture the instrument screen to an image file")
    shot.add_argument("output", help="destination image path")
    shot.add_argument("--format", default=ImageFormat.PNG,
                      type=ImageFormat.coerce, help="hardcopy format (default: PNG)")
    shot.add_argument("--palette", default="COLOR", choices=("COLOR", "INKSAVER", "BLACKANDWHITE"))
    shot.add_argument("--layout", default="LANDSCAPE", choices=("LANDSCAPE", "PORTRAIT"))
    shot.set_defaults(handler=_cmd_screenshot)

    capture = subparsers.add_parser("capture", help="trigger once and transfer the waveform records")
    add_setup_options(capture, "1")
    capture.add_argument("--width", type=int, default=1, choices=(1, 2), help="bytes per point")
    capture.add_argument("--csv", help="write the records to this CSV file")
    capture.add_argument("--plot", help="render the records to this image file")
    capture.add_argument("--screenshot", help="also save the instrument screen here")
    capture.set_defaults(handler=_cmd_capture)

    spread = subparsers.add_parser(
        "spread",
        help="measure the timing spread of several channels switching",
        description="Capture all the given channels from one acquisition and "
                    "report how far apart in time they cross their thresholds.",
    )
    add_setup_options(spread, "1,2,3,4")
    spread.add_argument("--direction", default=EdgeDirection.RISE, type=EdgeDirection.coerce,
                        help="RISE for going high, FALL for going low (default: RISE)")
    spread.add_argument("--percent", type=float, default=50.0,
                        help="threshold as a percentage of each channel's amplitude (default: %(default)s)")
    spread.add_argument("--threshold", type=float,
                        help="absolute threshold in volts, applied to every channel")
    spread.add_argument("--edge-index", type=int, default=0,
                        help="which edge after the trigger to use (default: %(default)s)")
    spread.add_argument("--reference", type=int, help="channel to report skews against")
    spread.add_argument("--csv", help="write the records to this CSV file")
    spread.add_argument("--plot", help="render the records, with edges marked, to this image file")
    spread.add_argument("--screenshot", help="also save the instrument screen here")
    spread.set_defaults(handler=_cmd_spread)

    period = subparsers.add_parser("period", help="measure period statistics over a captured record")
    add_setup_options(period, "1")
    period.add_argument("--csv", help="write the record to this CSV file")
    period.add_argument("--plot", help="render the record to this image file")
    period.set_defaults(handler=_cmd_period)

    measure = subparsers.add_parser("measure", help="take instrument-side measurements")
    add_setup_options(measure, "1")
    measure.add_argument("--type", type=MeasurementType.coerce,
                         help="measurement type; omit for a summary of the common ones")
    measure.add_argument("--source2", type=int, help="second source, for DELAY and PHASE")
    measure.add_argument("--edge1", default="RISE", choices=("RISE", "FALL"))
    measure.add_argument("--edge2", default="RISE", choices=("RISE", "FALL"))
    measure.set_defaults(handler=_cmd_measure)

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Entry point. Returns a process exit status."""
    parser = build_parser()
    args = parser.parse_args(argv)

    level = logging.WARNING
    if args.verbose == 1:
        level = logging.INFO
    elif args.verbose >= 2:
        level = logging.DEBUG
    logging.basicConfig(level=level, format="%(levelname)-8s %(name)s: %(message)s")

    try:
        scope = Tek3014B.connect(
            args.resource,
            backend=args.backend,
            timeout=args.timeout,
            auto_check_errors=not args.no_error_check,
        )
    except Tek3014BError as exc:
        print("error: could not connect to %s: %s" % (args.resource, exc), file=sys.stderr)
        return _EXIT_ERROR

    try:
        return args.handler(scope, args)
    except Tek3014BError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return _EXIT_ERROR
    except SystemExit as exc:
        print("error: %s" % exc, file=sys.stderr)
        return _EXIT_USAGE
    finally:
        scope.close()


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
