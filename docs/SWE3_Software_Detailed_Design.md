# SWE.3 — Software Detailed Design

| Field | Value |
|---|---|
| Document ID | TEK3014B-SWE3-001 |
| Version | 1.0 |
| Date | 2026-09-12 |
| Process reference | Automotive SPICE V4.0, SWE.3 Software Detailed Design and Unit Construction |

Each section below is a design unit. Units are named `SWE3-DD-<NAME>` and are referenced
from the module docstring of the implementing source file.

---

## SWE3-DD-CONST — `tek3014b/constants.py`

Single definition point for the SCPI vocabulary and the instrument capability envelope.

- `_ScpiEnum` — base `str` enum whose value is the literal SCPI argument. Provides
  `coerce()`, accepting a member, a member name, or a mnemonic, case-insensitively, so
  every public API can take `"rise"`, `"RISE"` or `Slope.RISE` interchangeably and reject
  anything else with a message listing the valid values.
- Enumerations: `Coupling`, `Bandwidth`, `Slope`, `TriggerMode`, `TriggerSource`,
  `TriggerState`, `AcquisitionMode`, `StopAfter`, `DataEncoding`, `MeasurementType`,
  `EdgeDirection`, `DelayDirection`, `ImageFormat`, `HardcopyPalette`, `HardcopyLayout`.
- `ModelLimits` — frozen dataclass holding the capability envelope (channel count,
  volts/div range, position range, time/div range, record lengths, average counts,
  available bandwidth limits). `TDS3014B_LIMITS` is the default instance. Supporting a
  different TDS3000-family model is a matter of constructing a different instance
  (SWE1-NFR-008).
- `INVALID_MEASUREMENT = 9.9e37` — the instrument's invalid-data sentinel.
- `DEFAULT_VXI11_DEVICE_NAMES` — the probe order for `create_link`.

---

## SWE3-DD-ERR — `tek3014b/errors.py`

Exception hierarchy, all rooted at `Tek3014BError` so a caller can guard a whole sequence
with one `except` without swallowing unrelated programming errors.

```
Tek3014BError
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
└── OptionalDependencyError
```

`ConfigurationError` deliberately also derives from `ValueError`, because it is raised for
argument validation and should read naturally to callers already handling `ValueError`.

---

## SWE3-DD-TRANSPORT — `tek3014b/transport/base.py`

Abstract link providing buffered framing. Subclasses implement four primitives:
`_open_link`, `_close_link`, `_send(data)` and `_recv_chunk(max_bytes) -> (data, end)`.

| Method | Framing rule | Used for |
|---|---|---|
| `read_message()` | Up to the terminator, or to end-of-message | Ordinary SCPI query responses |
| `read_exactly(n)` | Exactly *n* bytes, terminator-transparent | IEEE 488.2 block payloads |
| `read_raw()` | Everything to end-of-message | Hardcopy images (no length prefix) |

Design points:

- `write()` discards any unread buffered bytes before sending. Without this, a stale
  response would be returned as the answer to the next query — a failure mode that
  produces plausible-looking wrong data rather than an error.
- `read_message()` breaks out of the fill loop as soon as a terminator is visible, so a
  response already fully buffered costs no extra round trip; leftover bytes after the
  terminator are retained for the next read.
- `MAX_RESPONSE_BYTES` (64 MiB) bounds a runaway read if an instrument never asserts END.
- `_fill()` raises `TransportTimeoutError` when a chunk yields neither data nor END.
- Context-manager support guarantees the link is released on an exception path.

---

## SWE3-DD-VXI11 — `tek3014b/transport/vxi11.py`

Pure-standard-library VXI-11 client. Three layers:

1. **XDR codec** — `_Packer` / `_Unpacker`. Big-endian 32-bit scalars; opaque and string
   length-prefixed and padded to a 4-byte boundary. `_Unpacker` raises `ProtocolError` on
   a truncated stream rather than returning nonsense.
2. **ONC-RPC** — `_rpc_call_body` builds a CALL with `AUTH_NULL` credentials; `_rpc_tcp`
   frames it with record marking (top bit = last fragment) and reassembles the reply from
   its fragments; `_parse_rpc_reply` validates the transaction id, message type, reply and
   accept status. `_rpc_udp` exists solely for the portmapper fallback.
3. **VXI-11** — `Vxi11Transport`, mapping the transport primitives onto `device_write` and
   `device_read`, plus `clear`, `trigger`, `remote`, `local` and `read_stb`.

Notable behaviour:

- `query_portmapper` tries TCP first (clearer failure mode), then UDP, and raises a
  `ConnectionFailedError` naming both failures if neither answers.
- `_open_link` probes each configured device name in turn and, if all are refused, raises
  an error listing every name and the VXI-11 error each returned — so the user is told what
  to override, not merely that it failed.
- `_send` chunks writes to the negotiated `maxRecvSize`, setting the END flag only on the
  final chunk. `maxRecvSize` is clamped into `[512, 1 MiB]` and defaulted if the instrument
  reports zero.
- `_check` maps VXI-11 error 15 to `TransportTimeoutError` and error 4 to
  `ConnectionFailedError` (dropping the local link id), rather than surfacing raw numbers.
- `read_stb` uses `device_readstb`, which works while the instrument is busy, in preference
  to the `*STB?` query.

---

## SWE3-DD-SOCKET — `tek3014b/transport/socket_raw.py`

Raw TCP transport. Not usable with a TDS3014B (no such service) but supported for later
instruments on the same command set and for gateways. `_recv_chunk` reports `end=True` only
on a closed stream, so framing falls to the terminator. `read_raw` is overridden to use an
inter-byte idle gap, which is the only way to bound an unframed transfer on a stream socket;
this is documented as heuristic. The connection-refused message explicitly redirects the
user to the VXI-11 transport.

---

## SWE3-DD-VISA — `tek3014b/transport/visa_backend.py`

Optional PyVISA transport. `pyvisa` is imported inside `_open_link`, so importing the
package never requires it; absence yields `OptionalDependencyError` naming the extra.
`_recv_chunk` calls `visalib.read` directly and derives the END flag from the status code
(`success_max_count_read` means more data follows), which is what lets the same framing
logic in the base class work unchanged.

---

## SWE3-DD-FACTORY — `tek3014b/transport/factory.py`

`parse_resource()` is separated from `open_transport()` so resource parsing is unit-testable
without opening a connection. Recognised forms are listed in the module docstring. The
significant rule: a bare host or a `TCPIP::…::INSTR` string resolves to the **built-in
VXI-11** transport, not to PyVISA — VISA is opt-in via `backend="visa"` or a `visa://`
prefix.

---

## SWE3-DD-WAVEFORM — `tek3014b/waveform.py`

- `parse_ieee_block(data)` — handles definite (`#<n><len>`) and indefinite (`#0`) forms,
  and passes through a response with no header. Raises `ProtocolError` on a malformed or
  short block.
- `decode_curve(payload, width, signed)` — decodes big-endian 1- or 2-byte codes using
  `array`, byte-swapping only on a little-endian host.
- `WaveformPreamble` — frozen; `time_at(i)` and `volts_at(raw)` implement the manual's
  scaling relations. `start_index` makes a partial transfer report absolute record times.
- `Waveform` — record plus statistics (`minimum`, `maximum`, `peak_to_peak`, `mean`,
  `value_at` with interpolation) and `clipped_sample_count` / `is_clipped`.
- **Constructors, and why there are four:**
  | Constructor | Input | Notes |
  |---|---|---|
  | `from_codes` | decoded codes | the common core |
  | `from_payload` | de-framed binary payload | used by the driver; does **not** parse a block header |
  | `from_block` | complete block with header | parses, then delegates to `from_payload` |
  | `from_ascii` | comma-separated text | for `DATa:ENCdg ASCII` |

  The `from_payload` / `from_block` split is safety-critical: binary sample data can contain
  the byte `0x23` (`#`), which a second pass of the block parser would misread as a header.
- `waveforms_to_csv` — multi-channel export with one shared time column; rejects records of
  differing length.

---

## SWE3-DD-MEASURE — `tek3014b/measure.py`

- `estimate_levels(waveform, bins=64)` — histogram over the record; the most populated bin
  in each half gives the base and top levels. Far more robust than min/max on a signal with
  overshoot or ringing. Falls back to min/max when the histogram is not credibly bimodal.
  Logs a warning when the record is clipped, because every threshold derived from it is
  then wrong.
- `threshold_for(...)` — resolves a percentage-of-amplitude or absolute threshold, returning
  the levels alongside so callers do not re-estimate them.
- `find_crossings(...)` — single forward pass with an arm/disarm state machine implementing
  the hysteresis band. On each accepted crossing the time is interpolated linearly between
  the straddling samples:
  `t = t[i-1] + (threshold - v[i-1]) / (v[i] - v[i-1]) * (t[i] - t[i-1])`.
- `measure_period(...)` — differences between consecutive same-polarity crossings, returned
  as a `PeriodResult` exposing mean, min, max, standard deviation, peak-to-peak jitter and
  frequency. Raises with an actionable message when fewer than two edges are found.
- `measure_pulse_width`, `measure_rise_time` — derived from crossings at the relevant
  percentages.
- `measure_channel_spread(...)` — **the headline unit.** Per channel: resolve the threshold
  (from that channel's own amplitude by default), find the requested edge, record the
  crossing. Then report per-channel times, skews relative to a reference (defaulting to the
  earliest channel), the earliest and latest channel, the spread and the standard deviation.
  `require_all` controls whether a channel with no such edge is an error or is simply
  excluded.

Design note: `SpreadResult` stores the crossings and derives everything else as properties,
so there is one source of truth and no possibility of the summary disagreeing with the data.

---

## SWE3-DD-PLOT — `tek3014b/plotting.py`

`matplotlib` is imported inside `plot_waveforms` and the `Agg` backend is selected, so no
display is needed on a test rig. Channel colours mirror the TDS3014B front panel so a
host-side plot reads the same way as the instrument screen. The time axis is auto-scaled to
an engineering prefix. When a `SpreadResult` is supplied, each channel's crossing is marked
and the spread is annotated — which is what turns a skew number into reviewable evidence.

---

## SWE3-DD-SCOPE — `tek3014b/scope.py`

The application layer. Structure:

| Group | Methods |
|---|---|
| Lifecycle | `connect`, `initialise`, `close`, context manager |
| Primitive I/O | `_write`, `_query`, `_query_float`, `_query_int`, `_after_configuration` |
| Identification / status | `identity`, `model`, `reset`, `event_queue`, `check_errors` |
| Validation | `_validate_channel`, `_validate_channels`, `_validate_range` |
| Vertical | `enable_channel`, `configure_channel`, `apply_setup`, `get_channel_setup`, … |
| Horizontal | `set_time_per_div`, `set_horizontal_delay`, `set_record_length`, … |
| Trigger | `configure_edge_trigger`, `set_trigger_level`, `trigger_state`, `force_trigger` |
| Acquisition | `run`, `stop`, `single`, `is_busy`, `wait_for_acquisition` |
| Capture | `_read_preamble`, `_read_curve_payload`, `capture`, `capture_single` |
| Instrument measurement | `measure`, `measure_period`, `measure_delay`, `measure_summary`, … |
| Host analysis | `measure_channel_spread`, `measure_period_host` |
| Screen | `screenshot` |

Key implementation notes:

- `initialise()` sends `HEADER OFF;:VERBOSE OFF` so queries return bare values, then `*CLS`.
  It deliberately does **not** `*RST`: silently discarding an operator's front-panel setup
  would be a surprising side effect of connecting.
- `_read_preamble` fetches all seven preamble fields in one compound query
  (`WFMPRE:XINCR?;:WFMPRE:XZERO?;…`), turning seven round trips into one.
- `_read_curve_payload` consumes `#`, the digit count and the length field via
  `read_exactly`, then reads exactly the declared number of bytes. It returns the payload
  **already de-framed** (see AD-03 and SWE3-DD-WAVEFORM).
- `capture` validates first, sends one `DATA:*` setup message, then loops the channels. It
  logs a warning for any channel whose record is clipped.
- `wait_for_acquisition` polls `BUSY?` to a deadline and, on timeout, includes the
  instrument's trigger state in the exception message.
- `screenshot` forces `HARDCopy:PORT GPIb`, optionally verifies the format was accepted and
  falls back to `BMPCOLOR`, raises the transport timeout for the transfer and restores it in
  a `finally`, and appends a format-appropriate suffix when the path has none.
- `measure` raises `MeasurementError` when the instrument returns its 9.9E37 sentinel,
  rather than handing the caller a number that is not a measurement.

---

## SWE3-DD-CLI — `tek3014b/cli.py`

`argparse` with sub-commands `idn`, `capture`, `spread`, `period`, `measure`, `screenshot`.
Results are emitted as JSON on stdout, optionally also to `--json PATH`, so the tool
composes into a larger harness. `--resource` defaults to `sim://`, so every command is
demonstrable without hardware. Per-channel options accept either a single value applied to
all channels or one value per channel. Exit status: 0 success, 1 instrument or driver
error, 2 usage error.

Known usage wrinkle: a negative value must be passed with `=` (`--position=-4,-3,-2,-1`),
because `argparse` otherwise treats a leading `-` as an option prefix. This is standard
`argparse` behaviour and is documented in the README.

---

## SWE3-DD-SIM — `tek3014b/simulator.py`

`SimulatedTDS3014B` holds instrument state and dispatches SCPI to `_cmd_*` handlers resolved
by name from the command header, so adding a command is adding a method. Compound messages
are split on `;` with a leading `:` reset, matching SCPI. Unrecognised headers are pushed
into the event queue exactly as the instrument does, which means a wrong command spelling in
the driver surfaces as an `InstrumentError` in test rather than passing silently.

`ChannelSignal` describes each input analytically (frequency, amplitude, baseline, duty,
rise/fall time, delay). `curve_codes` digitises it through the same preamble the driver will
use to undo the scaling, including clipping at the digitiser rail. Measurements are computed
from the model parameters, **not** from the sampled record, so host-side analysis is
validated against an independent reference. `make_png` produces a genuinely valid PNG for
hardcopy.
