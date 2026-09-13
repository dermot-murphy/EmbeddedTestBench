# SWE.3 — Software Detailed Design

| Field | Value |
|---|---|
| Document ID | BENCHTOOLS-SWE3-001 |
| Version | 2.0 |
| Date | 2026-09-13 |
| Process reference | Automotive SPICE V4.0, SWE.3 Software Detailed Design and Unit Construction |

Each section is a design unit, named `<ELEMENT>-DD-<NAME>` and referenced from the
module docstring of the implementing source file.

---

# CORE — `benchtools.core`

## CORE-DD-ERR — `errors.py`

Single exception hierarchy, rooted at `BenchToolsError`, so a caller can guard a
whole measurement sequence across any number of instruments and the runner with
one `except`.

```
BenchToolsError
├── TransportError
│   ├── ConnectionFailedError
│   ├── TransportTimeoutError
│   ├── ProtocolError
│   ├── UnsupportedTransportError
│   └── Vxi11Error            (carries the VXI-11 error code)
├── InstrumentError           (carries the parsed event queue)
├── ConfigurationError        (also a ValueError)
├── MeasurementError
├── AcquisitionTimeoutError
├── OptionalDependencyError
└── BenchError
    ├── SpecError             (malformed test specification)
    ├── BenchConfigError      (malformed bench configuration)
    └── StepError
```

`ConfigurationError` also derives from `ValueError`, because it is raised for
argument validation and should read naturally to callers already handling it.

## CORE-DD-ENUMS — `enums.py`

`ScpiEnum` is a `str` enum whose value is the literal SCPI argument. `coerce()`
accepts a member, a member name or a mnemonic, case-insensitively, and otherwise
raises with the valid values listed. Only cross-instrument enumerations live here
(`EdgeDirection`, `Slope`); model-specific ones belong in that instrument's
`constants` module.

## CORE-DD-VALIDATE — `validation.py`

`validate_range`, `validate_channel`, `validate_channels`, `validate_choice`.
Messages name the setting, the offending value, the permitted range and the unit.
`validate_channels` rejects duplicates rather than collapsing them: a duplicate
almost always means the caller built the list wrongly, and quietly returning
fewer channels than asked for would hide that.

## CORE-DD-TRANSPORT — `transport/base.py`

Abstract link providing buffered framing. Subclasses implement `_open_link`,
`_close_link`, `_send(data)` and `_recv_chunk(max_bytes) -> (data, end)`.

| Method | Framing rule | Used for |
|---|---|---|
| `read_message()` | To the terminator, or to end-of-message | Ordinary SCPI query responses |
| `read_exactly(n)` | Exactly *n* bytes, terminator-transparent | IEEE 488.2 block payloads |
| `read_raw()` | Everything to end-of-message | Images and other unframed transfers |

Design points:

- `write()` discards unread buffered bytes first. Without this, a stale response
  would be returned as the answer to the next query — a failure mode producing
  plausible wrong data rather than an error.
- `read_message()` breaks out of the fill loop as soon as a terminator is visible,
  so an already-buffered response costs no extra round trip.
- `MAX_RESPONSE_BYTES` (64 MiB) bounds a runaway read if an instrument never
  asserts end-of-message.
- Context-manager support guarantees the link is released on an exception path.

## CORE-DD-VXI11 — `transport/vxi11.py`

Pure-standard-library VXI-11 client, in three layers: an XDR codec
(`_Packer`/`_Unpacker`, RFC 4506), ONC-RPC with record marking (RFC 5531), and
the VXI-11 core channel procedures. Notable behaviour:

- `query_portmapper` tries TCP first, then UDP, and raises naming both failures.
- `_open_link` probes each configured device name and, if all are refused, lists
  every name with the error each returned — so the user is told what to override.
- `_send` chunks writes to the negotiated `maxRecvSize`, setting END only on the
  final chunk; the size is clamped to `[512, 1 MiB]` and defaulted if zero.
- `_check` maps VXI-11 error 15 to `TransportTimeoutError` and error 4 to
  `ConnectionFailedError`, rather than surfacing raw numbers.
- `read_stb` uses `device_readstb`, which works while the instrument is busy.

Protocol detail and the VISA analysis are in the VISA determination report.

## CORE-DD-SOCKET — `transport/socket_raw.py`

Raw TCP transport, for instruments that expose a SCPI socket. `_recv_chunk`
reports `end=True` only on a closed stream, so framing falls to the terminator.
`read_raw` uses an inter-byte idle gap, the only way to bound an unframed transfer
on a stream socket; this is documented as heuristic and is the main technical
argument for preferring VXI-11 where both exist.

## CORE-DD-VISA — `transport/visa_backend.py`

Optional PyVISA transport. `pyvisa` is imported inside `_open_link`, so importing
the package never requires it. `_recv_chunk` derives the END flag from the VISA
status code, which is what lets the base class's framing work unchanged.

## CORE-DD-MOCK — `transport/mock.py`

Loopback transport accepting any `Responder` — anything with
`respond(bytes) -> bytes | None`. It has no knowledge of which instrument is
simulated. Responses are returned in small chunks so that framing and
reassembly are exercised rather than bypassed. The description is derived from
the responder's `*IDN?` model field, so it is meaningful for any instrument.

## CORE-DD-FACTORY — `transport/factory.py`

`parse_resource()` is separated from `open_transport()` so parsing is testable
without opening a connection. Backends and URL schemes live in registries
(`register_backend`), so a new link type is added from its own module. The
significant rule: a bare host or a `TCPIP::…::INSTR` string resolves to the
**built-in VXI-11** transport; VISA is opt-in.

`open_transport` accepts a `responder_factory`, called when the resource selects
the simulator. This is how an instrument driver supplies *its own* simulator
without this module knowing about any instrument.

## CORE-DD-SCPI — `scpi.py`

`ScpiInstrument`, the base every driver subclasses.

| Group | Members |
|---|---|
| 488.2 blocks | `parse_ieee_block`, `format_ieee_block` |
| Identity | `InstrumentIdentity`, `identify`, `identity`, `manufacturer`, `model`, `firmware` |
| Lifecycle | `connect`, `initialise`, `close`, context manager |
| Primitives | `_write`, `_query`, `_query_float`, `_query_int`, `_query_bool`, `_query_fields` |
| Status | `reset`, `clear_status`, `operation_complete`, `event_status`, `self_test_passed` |
| Errors | `read_event_queue`, `check_errors`, `_after_configuration` |
| Escape hatch | `write_raw`, `query_raw` |

Two extension points, because instrument families genuinely differ:

- **`read_event_queue`** defaults to polling `SYSTem:ERRor?` until it reports 0
  (SCPI-1999), bounded at 64 iterations so a stuck queue cannot hang the caller.
  Tektronix instruments override it with `ALLEv?`.
- **`initialise`** clears status; a subclass extends it for whatever response
  formatting its queries need. It deliberately does not `*RST`: silently
  discarding an operator's front-panel setup would be a surprising side effect of
  connecting.

`SIMULATOR_CLASS` is the class attribute a driver sets to declare its own
simulator, which is what inverts the transport-to-instrument dependency.
`connect()` takes `transport_kwargs` for link options and forwards any remaining
keywords to the driver's constructor, so a driver with extra parameters (such as
a capability envelope) needs no override.

## CORE-DD-SIM — `simulator.py`

`SimulatedInstrument` holds the shared harness: compound message splitting on `;`
with a leading `:` reset, handler dispatch by name (`scpi_slug` maps `CH1:SCALE?`
to `_cmd_CH1_SCALE_Q`), the 488.2 mandated queries, an event queue, and binary
replies via `set_binary_reply`. `Responder` is the runtime-checkable protocol the
mock transport accepts.

Adding a command to a simulator is adding a method. `_unknown_command` is the hook
for pattern-matched families (such as `CH<n>:<setting>`), falling through to the
base, which records the header in the event queue exactly as an instrument does —
so a driver that misspells a command fails a test rather than passing silently.
The base class is concrete and usable on its own, which is what makes a bare
`sim://` resource meaningful.

---

# ANA — `benchtools.analysis`

## ANA-DD-WAVEFORM — `waveform.py`

- `decode_curve(payload, width, signed)` decodes big-endian 1- or 2-byte codes
  using `array`, byte-swapping only on a little-endian host.
- `WaveformPreamble` is frozen; `time_at(i)` and `volts_at(raw)` implement the
  manual's scaling relations. `start_index` makes a partial transfer report
  absolute record times.
- `Waveform` carries the record plus statistics and `clipped_sample_count`.
- **Four constructors, and why:**

  | Constructor | Input | Notes |
  |---|---|---|
  | `from_codes` | decoded codes | the common core |
  | `from_payload` | de-framed binary payload | used by drivers; does **not** parse a block header |
  | `from_block` | complete block with header | parses, then delegates |
  | `from_ascii` | comma-separated text | for ASCII encodings |

  The `from_payload`/`from_block` split is safety-critical: binary sample data can
  contain `0x23` (`#`), which a second pass of the block parser would misread as a
  header. `parse_ieee_block` is re-exported from `core.scpi`, where it is shared
  with the drivers that send and receive blocks.
- `waveforms_to_csv` exports several channels with one shared time column, and
  rejects records of differing length.

## ANA-DD-MEASURE — `measure.py`

- `estimate_levels` builds a histogram and takes the most populated bin in each
  half as the base and top level — the same idea as an instrument's own high/low
  algorithm, and far more robust than min/max on a signal with overshoot. Falls
  back to min/max when the histogram is not credibly bimodal, and warns when the
  record is clipped, because every threshold derived from it is then wrong.
- `find_crossings` is a single forward pass with an arm/disarm state machine
  implementing the hysteresis band. Each accepted crossing is interpolated:
  `t = t[i-1] + (threshold - v[i-1]) / (v[i] - v[i-1]) * (t[i] - t[i-1])`.
- `measure_period` differences consecutive same-polarity crossings and returns a
  `PeriodResult` exposing mean, min, max, standard deviation, peak-to-peak jitter
  and frequency.
- `measure_channel_spread` is the headline unit: per channel resolve the threshold
  (from that channel's own amplitude by default), find the requested edge, record
  the crossing; then report per-channel times, skews relative to a reference
  (default: the earliest channel), the earliest and latest channel, the spread and
  the standard deviation. `require_all` decides whether a channel with no such
  edge is an error or is excluded.

`SpreadResult` stores the crossings and derives everything else as properties, so
there is one source of truth and the summary cannot disagree with the data.

## ANA-DD-PLOT — `plotting.py`

`matplotlib` is imported inside `plot_waveforms` and the `Agg` backend selected,
so no display is needed on a test rig. Channel colours mirror the oscilloscope
front panel; the time axis auto-scales to an engineering prefix. Given a
`SpreadResult`, each channel's crossing is marked and the spread annotated — which
is what turns a skew number into reviewable evidence.

---

# INST — `benchtools.instruments`

## INST-DD-GENERIC — `generic.py`

`GenericScpiInstrument` adds nothing to `ScpiInstrument` beyond a model name. It
covers the part of every instrument that is always the same — prove it is
reachable, find out what it is, read its errors, send raw SCPI — and is what the
runner uses for a bench entry with no dedicated driver. Because it adds nothing,
it also demonstrates that the core is genuinely instrument-agnostic.

## SCOPE-DD-CONST — `tek3014b/constants.py`

TDS3000-family enumerations and `ModelLimits`, the capability envelope
(channel count, volts/div range, position range, time/div range, record lengths,
average counts, bandwidth options). `TDS3014B_LIMITS` is the default instance;
supporting another family member is constructing a different one and passing it to
`Tek3014B(limits=...)` or `connect(..., limits=...)`.

## SCOPE-DD-SCOPE — `tek3014b/scope.py`

The oscilloscope's SCPI vocabulary. Everything not specific to the instrument
comes from `ScpiInstrument`; this module contributes:

| Group | Members |
|---|---|
| Overrides | `initialise` (adds `HEADER OFF;:VERBOSE OFF`), `read_event_queue` (`ALLEv?`) |
| Vertical | `enable_channel`, `configure_channel`, `apply_setup`, `get_channel_setup`, `set/get_volts_per_div`, `set/get_position` |
| Horizontal | `set_time_per_div`, `set_horizontal_delay`, `set_record_length` |
| Trigger | `configure_edge_trigger`, `set/get_trigger_level`, `trigger_state`, `force_trigger` |
| Acquisition | `run`, `stop`, `single`, `is_busy`, `wait_for_acquisition` |
| Capture | `_read_preamble`, `_read_curve_payload`, `capture`, `capture_single` |
| Instrument measurement | `measure`, `measure_period`, `measure_delay`, `measure_summary` |
| Host analysis | `measure_channel_spread`, `measure_period_host` |
| Screen | `screenshot` |

Implementation notes:

- `_read_preamble` fetches all seven preamble fields in one compound query,
  turning seven round trips into one.
- `_read_curve_payload` consumes the block header via `read_exactly` and then
  exactly the declared byte count, returning the payload **already de-framed**.
- `capture` validates first, sends one `DATA:*` setup message, then loops the
  channels, warning for any whose record is clipped.
- `wait_for_acquisition` polls `BUSY?` to a deadline and, on timeout, includes the
  trigger state in the exception message.
- `screenshot` forces the hardcopy port to the command interface, optionally
  verifies the format and falls back to `BMPCOLOR`, raises the transport timeout
  for the transfer and restores it in a `finally`.
- `measure` raises when the instrument returns its 9.9E37 sentinel, rather than
  handing the caller a number that is not a measurement.

## SCOPE-DD-SIM — `tek3014b/simulator.py`

`SimulatedTDS3014B` subclasses `SimulatedInstrument`, adding the TDS3000 command
set, instrument state and `ChannelSignal` — an analytic description of each input
(frequency, amplitude, baseline, duty, rise and fall time, delay). `curve_codes`
digitises it through the same preamble the driver uses to undo the scaling,
including clipping at the digitiser rail. Measurements are computed from the model
parameters, **not** from the sampled record, so host-side analysis is validated
against an independent reference. `make_png` produces a genuinely valid PNG.

## SCOPE-DD-CLI — `tek3014b/cli.py`

Sub-commands `idn`, `capture`, `spread`, `period`, `measure`, `screenshot`,
emitting JSON so the tool composes into a harness. `--resource` defaults to
`sim://`. Per-channel options accept one value for all channels or one per
channel. A negative value must be passed with `=` (`--position=-4,-3`), standard
`argparse` behaviour, documented in the README.

---

# RUN — `benchtools.runner`

## RUN-DD-SPEC — `spec.py`

The specification model: `TestSpec` → `TestCase` → `Step` → `Expectation`, all
frozen dataclasses built by `from_mapping` classmethods that validate as they go
and raise `SpecError` naming what to fix. `load_mapping` reads JSON with the
standard library and YAML when `pyyaml` is present. `TestSpec.instruments_used`
collects the aliases referenced anywhere, so the runner can verify the bench
before starting. `TestSpec` and `TestCase` set `__test__ = False`: their names
would otherwise make pytest try to collect them.

## RUN-DD-LIMITS — `limits.py`

`Limit` supports `minimum`, `maximum`, `equals` with `tolerance` or
`tolerance_percent`, in any consistent combination, validated at construction.
`from_mapping` accepts `min`/`max`/`nominal` aliases because that is what reads
naturally in YAML, and ignores unknown keys because an expectation carries
name/unit/scale alongside them. `check()` returns a `LimitOutcome` carrying the
rendered limit text and, on failure, by how much the value missed. A `None` or NaN
value fails rather than passing.

## RUN-DD-RESOLVE — `resolve.py`

Driver methods return whatever suits them: a float, a dataclass, a dict keyed by
channel, a tuple of records and a result object. `resolve_path` addresses into
that with a dotted path, trying each element as a mapping key (by string then by
int, because YAML gives keys as text while a channel-keyed dict uses ints), then a
sequence index, then an attribute, then a zero-argument method. This is the price
of AD-08 and is confined to this module.

## RUN-DD-BENCH — `bench.py`

`InstrumentConfig` and `BenchConfig` model the bench; `Bench` holds the live
instruments. Drivers are selected from a registry by name (`register_driver`), so
a specification names data rather than code. Instruments connect on first use, so
a suite touching one instrument does not require the whole bench powered up, and
`close()` releases whatever was opened even after a failure. `require()` fails
fast when the bench lacks an alias the specification uses. `is_simulated` is true
when `--simulate` was given *or* every configured resource is a simulator, which
is what lets every report disclose it.

## RUN-DD-RESULTS — `results.py`

`Status` (PASS/FAIL/ERROR/SKIP) with a `severity` ordering and a `worst()`
aggregator, so roll-up from measurement to step to case to run is one rule applied
at each level. `MeasurementRecord`, `StepRecord`, `CaseRecord` and `RunRecord` are
plain data with `as_dict()`; `RunRecord.requirements_verified` groups cases by
requirement and reports the worst outcome of each. Report writers read only these,
so a new format needs no change to the engine.

## RUN-DD-RUNNER — `runner.py`

`BenchRunner` resolves each step's `do:` to a bound method on a bench instrument —
rejecting private names, and on an unknown name listing what is available — calls
it, extracts the declared measurements and checks them. A `BenchToolsError`, a
`TypeError` from wrong arguments, or any other exception becomes an **error**; a
measurement outside its limit becomes a **failure**. Setup failures abort the
suite; teardown runs in a `finally`. `BUILTIN_ACTIONS` holds actions not bound to
an instrument (currently `sleep`, so a settling time is stated explicitly rather
than hidden in a driver).

## RUN-DD-REPORT — `report.py`

`write_json` (lossless), `format_markdown`/`write_markdown` (verdict, then
requirements, then problems, then all measurements; simulation disclosed), and
`write_junit` (a limit failure is `<failure>`, an execution error is `<error>`, the
requirement is the classname). `summary_line` gives a one-line console or commit
status.

## RUN-DD-CLI — `cli.py` and `benchtools/cli.py`

`benchtools run` takes one or more specifications, a `--bench` or `--simulate`,
and report destinations; with several specifications the report paths are suffixed
so they do not overwrite. Exit status is 0 pass, 1 failure or error, 2 usage.
`benchtools/cli.py` dispatches `run`, `scope`, `drivers` and `backends` by name
rather than nesting argparse parsers, so each tool keeps its own complete
`--help`.
