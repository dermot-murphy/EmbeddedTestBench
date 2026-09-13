# SWE.3 — Software Detailed Design

| Field | Value |
|---|---|
| Document ID | BENCHTOOLS-SWE3-001 |
| Version | 3.0 |
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

## CORE-DD-PROCESS — `transport/process.py`

`ProcessTransport`: a `Transport` over a child process's standard input and output,
registered as the `process` and `stdio` backends. Written for GDB (JLINK-DD-SESSION)
and usable by any tool with a line protocol.

Design points:

- **Reader threads, not `select`.** `select` does not accept pipe handles on
  Windows, and the first deployment is a Windows PC (STK-11). One thread drains
  stdout into a `queue.Queue`, another drains stderr into a bounded `deque` of 200
  lines. Bounded, because a tool that prints a warning per command must not become
  a memory leak over a long bench run.
- `bufsize=0` and `stream.read(65536)`: the read returns as soon as any bytes are
  available, so the transport blocks per *block* rather than per byte, without
  waiting for a buffer to fill.
- `ready_timeout` (0.5 s) catches the common failure: the executable exists but
  exits immediately — a missing shared library, a bad argument. The diagnostic is
  the child's own stderr, which is the only text that says what was actually wrong.
- `returncode` is retained after `close()`, so a post-mortem can say how the tool
  died after the transport has gone.

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

## CORE-DD-INSTRUMENT — `instrument.py`

`Instrument`, the lifecycle every driver shares, with no command language in it
(AD-11). `ScpiInstrument` and `JLinkProbe` both derive from it, and the runner's
driver registry is typed on it.

| Group | Members |
|---|---|
| Lifecycle | `connect` (classmethod), `initialise`, `close`, `__enter__`, `__exit__` |
| Subclass hooks | `_open`, `_close`, `is_open`, `_post_open`, `_read_identity` |
| Identity | `identify`, `identity`, `manufacturer`, `model`, `serial_number`, `firmware` |
| Simulation | `SIMULATOR_CLASS`, `MODEL_NAME` |
| Errors | `read_event_queue`, `check_errors`, `_after_configuration` |

Design points:

- The hooks are separated from the template methods so a subclass overrides *what*
  opening means, never *when* initialisation happens. `_post_open` is a chain: the
  SCPI layer sends `*CLS` there, the probe loads symbols and attaches, and neither
  has to remember to call the other's setup.
- `close()` never raises (CORE-FR-016). A transport that is already dead must not
  turn a measurement failure into a confusing secondary error from the `finally`
  block that was trying to tidy up.
- `InstrumentIdentity` lives here because the runner reports identity for any
  instrument, but `from_idn()` — the IEEE 488.2 four-field split — is a *SCPI*
  parse, so it is a named constructor rather than the constructor. A probe fills
  the fields from what the GDB server reports about the emulator.
- `read_event_queue` defaults to returning nothing, because an instrument with no
  error queue is the normal case outside SCPI. `check_errors` is therefore a no-op
  by default rather than a forced override.

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

# JLINK — `benchtools.instruments.jlink`

Seven collaborators and a façade (JLINK-ARC-001). The split is by *reason to
change*: the MI grammar changes with GDB, RTT with SEGGER's protocol, ITM with the
ARM architecture, the envelope with the probe model.

## JLINK-DD-GDBMI — `jlink/gdbmi.py`

The GDB/MI grammar, and nothing else: no I/O, no state. `parse_line` returns a
`ResultRecord`, `AsyncRecord`, `StreamRecord`, `PromptRecord`, or `None` for a line
that is not MI at all (GDB emits those on start-up).

Parsing points that matter:

- `parse_value` is a recursive-descent parser over a `_Cursor`, because MI values
  nest arbitrarily: `frame={args=[{name="x",value="1"}]}`.
- A list whose elements all carry the **same** name — `[frame={…},frame={…}]`, which
  is how a backtrace arrives — becomes a plain list of three frames, not a
  one-element dict that silently loses two. This is the defect this module exists to
  prevent; `test_gdbmi.py` pins it.
- Repeated result names at the top level accumulate into a list for the same reason.
- `unescape_cstring` is separate and separately tested: MI strings carry `\n`,
  `\"`, `\\` and octal escapes, and a mis-unescaped path is a wrong file name.

## JLINK-DD-SESSION — `jlink/session.py`

`GdbMiSession`: one command, one reply, over any `Transport`.

- Every command is prefixed with a monotonic token and the reply is matched on it,
  so a late reply cannot be read as the answer to the next question.
- **Drain before write.** MI async records (`*stopped`, `=thread-exited`) arrive
  unbidden, and the base transport discards buffered data before a write to avoid
  reading a stale reply. That is right for SCPI and wrong here, so the session
  drains asynchronous records into a queue first, using
  `Transport.has_buffered_data` to know there is something to drain.
- `wait_for_async` returns a record already buffered before waiting, re-raises
  `ConnectionFailedError` — a dead GDB is not a timeout — and treats any other
  transport error as "nothing yet" until the deadline.
- `execute_console` wraps `-interpreter-exec console "…"` with `\` and `"` escaped,
  for the commands that have no MI form (`monitor`, `compare-sections`, `load`).
- `GdbError` names the command and GDB's own reason, because "error" alone from a
  debugger is worthless.

## JLINK-DD-SERVER — `jlink/server.py`

Discovery and lifetime of the J-Link GDB Server and GDB.

- `find_gdb_server` searches the Windows executable names first
  (`JLinkGDBServerCL.exe`, `JLinkGDBServer.exe`) then the Unix ones, and the
  diagnostic names the tool and where SEGGER installs it.
- `port_is_open` is checked **before** spawning: a server already listening is used,
  never duplicated — a second server on the same probe fails in a way that reads
  like a hardware fault.
- The server is spawned only for a local target (AD-13); for a remote one the driver
  attaches and says so.
- `was_spawned` gates `stop()`: a server the driver did not start is a server it must
  not kill (JLINK-FR-005).
- Flags: `-nogui -silent -singlerun -strict`. `-singlerun` so the server exits with
  the session; `-strict` so a bad device name fails at start rather than producing a
  half-working link.

## JLINK-DD-RTT — `jlink/rtt.py`

RTT over the server's RTT port, behind an `RttSource` protocol so the socket and the
simulator are interchangeable.

- `_pending` and `_history` are separate deques: reads consume `_pending`, while
  `_history` keeps every line for the report. They were one deque, and `history`
  then returned only what had not been read — a log with the interesting lines
  missing.
- `_pump()` is called synchronously at the start of every read, so a test's result
  does not depend on when a background thread happened to run.
- A partial line is retained until its terminator arrives; firmware writes half a
  line all the time.
- `RttTimeout` names the pattern sought **and** the text that did arrive. The text
  is usually the answer — a firmware assertion, a different prompt.
- `log_to` flushes per line, so the log of a target that then hung is complete.

## JLINK-DD-SWO — `jlink/swo.py`

ITM/SWO packet decoding (ARMv7-M ARM Appendix D) and the SWO socket reader.

- `ItmDecoder.feed()` is incremental: SWO arrives in arbitrary TCP fragments.
- A source packet is identified by `header & 0x03 != 0` — the two-bit *size* field.
  Testing bit 0 alone, which reads plausibly, classifies every 16-bit ITM write as a
  protocol packet and silently drops it. `test_swo.py` pins the 1-, 2- and 4-byte
  cases.
- Local timestamp formats 1 and 2, extension, global timestamp, overflow and sync
  are decoded, because a decoder that skips the ones it does not need desynchronises
  on the first one it meets.
- `encode_software_event` and `encode_local_timestamp` exist so the tests build real
  packet streams rather than asserting against the decoder's own output.
- `timestamp_cycles` scales timestamps by the trace prescaler. **This scaling is
  from the architecture manual and is unconfirmed against a part** (CON-05,
  JLINK-OPEN-03), and the module says so where a reader will see it.

## JLINK-DD-TIMING — `jlink/timing.py`

`TimingSample` and `TimingResult`: the result type, with no measuring in it.

`TimingResult` carries the method, the samples, the core clock and whether the
target was halted, and derives `seconds`, `microseconds`, `cycles`, `minimum`,
`maximum`, `spread`, `standard_deviation`, `resolution_seconds` and
`is_trustworthy` (false when the interval is under ten times the method's
resolution). `as_dict()` is the plain-types boundary of AD-15.

An empty sample list raises `MeasurementError` rather than reporting zero seconds —
a zero would be indistinguishable from a fast interval.

## JLINK-DD-CONST — `jlink/constants.py`

The vocabulary and the envelope, as data (JLINK-FR-010): `DebugInterface`,
`ResetType`, `HaltReason` (with an `UNKNOWN` fallback, so a GDB version reporting a
reason this driver has not met does not crash the run), `BreakpointKind`,
`WatchpointKind`, `TimingMethod`, the server's ports, the DEMCR/DWT register
addresses, and `ProbeLimits` — hardware breakpoints, watchpoints, RTT channels,
maximum transfer size, core clock, and `cycle_counter_max_seconds`, the interval
beyond which the 32-bit cycle counter wraps.

`TimingMethod` carries the trade-off of each method in its docstring, next to the
member, because that is where the choice is made.

## JLINK-DD-SIM — `jlink/simulator.py`

A simulated probe **and** a simulated target: `SimulatedFirmware` holds the
execution flow, cycle counts per location, symbols, memory, call stacks, RTT
traffic, ITM events and sections; `SimulatedJLink` answers the MI dialogue.

- The default firmware puts `sensor.c:40` at 5 000 cycles and `sensor.c:75` at
  69 000 — exactly 64 000 cycles, which at 64 MHz is exactly 1.000 ms. The timing
  tests therefore assert an exact figure rather than a range, and a scaling error of
  any size fails.
- `read_memory` special-cases `DWT_CYCCNT` so the counter advances with simulated
  execution.
- `-break-insert` is split with `shlex.split`, not `split()`: a condition contains
  spaces and quotes, and the naive split truncated `if sensor_count > 3` to
  `sensor_count`.
- A hardware breakpoint is reported as `type="hw breakpoint"`, which is what GDB
  says. Reporting `"breakpoint"` for both made the driver's hardware-breakpoint
  count always zero, so the envelope limit could never trip.

## JLINK-DD-PROBE — `jlink/probe.py`

`JLinkProbe`, the façade: an `Instrument` (CORE-DD-INSTRUMENT) whose transport is a
GDB process or a simulator.

| Group | Members |
|---|---|
| Lifecycle | `connect`, `_post_open`, `load_symbols`, `attach`, `monitor`, `close` |
| Programming | `flash`, `verify`, `erase` |
| Execution | `reset`, `run`/`resume`, `halt`/`stop`, `step`, `wait_for_halt`, `is_halted`, `program_counter`, `registers`, `run_to` |
| Breakpoints | `set_breakpoint`, `set_watchpoint`, `list_breakpoints`, `delete_breakpoint`, `clear_breakpoints` |
| Memory | `read_memory`, `write_memory`, `read_word`, `write_word`, `read_u8`, `read_u16`, `read_ram`, `write_ram` |
| Symbols | `read_variable`, `write_variable`, `variable_address`, `variable_size`, `evaluate`, `call_stack`/`backtrace` |
| RTT | `rtt_start`, `rtt_stop`, `rtt_read_lines`, `rtt_write`, `rtt_expect`, `rtt_command`, `rtt_log` |
| Timing | `enable_cycle_counter`, `read_cycle_counter`, `measure_time_between` |

Design points:

- `_parse_target` accepts `sim://`, `jlink://`, `gdb://` and `tcp://`, with or
  without a host and port, so one resource string covers the simulator, a local
  probe and a probe on another machine (AD-13).
- Memory transfers are chunked to `ProbeLimits.max_transfer_bytes`; a 1 MB read is
  not one MI command.
- `_counter_delta` handles the cycle counter's 32-bit wrap; over a 64 MHz core that
  is every 67 s, well inside a plausible measurement.
- `measure_time_between` dispatches on `TimingMethod` to `_run_to_breakpoint`,
  `_measure_target_variables` or `_measure_swo`, and every path returns the same
  `TimingResult`, so a specification asserting on `microseconds` does not care which
  method produced it.
- `VerifyResult.matched` is false for an empty section list: "nothing was compared"
  must never render as a pass (JLINK-FR-022).
- The RTT client is attached automatically when the transport's responder is a
  simulated probe, so a simulated bench exercises the RTT paths rather than skipping
  them.

## JLINK-DD-CLI — `jlink/cli.py`

Sub-commands `info`, `flash`, `verify`, `reset`, `run`, `halt`, `read`, `write`,
`var`, `stack`, `rtt`, `time`, emitting JSON (AD-15). The `time` sub-command adds a
`warning` key when the result is not trustworthy, so a figure quoted from a shell
script carries the same caveat the API gives.

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
