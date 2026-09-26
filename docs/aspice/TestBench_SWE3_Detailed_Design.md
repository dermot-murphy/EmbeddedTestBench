# Software Detailed Design

*Automotive SPICE® PAM v4.0 | SWE.3 Software Detailed Design and Unit Construction*

---

## 1. Document Identification & Control

| Field | Value | Field | Value |
|---|---|---|---|
| **Document ID** | TB-SWE3-001 | **Version** | 0.2 |
| **Project** | TestBench | **Date** | 2026-09-23 |
| **Status** | Draft | **Classification** | Internal |
| **Author** | Claude | **Reviewer** | Dermot Murphy |
| **Approver** | Dermot Murphy | **Related Process** | SWE.3 |

> **Note — Reviewer independence (TB-DEV-002):** The Reviewer and Approver are the same person (Dermot Murphy). This is accepted under deviation record **TB-DEV-002** (`docs/aspice/TestBench_DEV002_Independent_Review_Deviation.md`) on the basis that TestBench has a single human team member.

---

## 2. Revision History

| Version | Date | Author | Description of Change |
|---|---|---|---|
| 0.1 | 2026-09-19 | Claude | Initial |
| 0.2 | 2026-09-23 | Claude | Design units added for the TTi 1604: DMM-DD-CONST, DMM-DD-PROTO, DMM-DD-DMM, DMM-DD-SIM, DMM-DD-CLI. |
| 0.3 | 2026-09-25 | Claude | BLE-DD-SCRIPT narrowed to reading, with variables, connect, timeouts and `<disconnect>`; BLE-DD-SCRIPTRUN added for running, results in priority order and the event log; BLE-DD-CMD gains the connect and reply timeouts, and BLE-DD-CMDARGS is added (#46, #48). |

---

## 3. Purpose & Scope

### 3.1 Purpose

This document describes the detailed design of every software unit of
**TestBench**: what each unit is, what it holds, and - where the reason is not
obvious from the code - why it is built the way it is. It refines TB-SWE2-001
and is the basis for unit verification (TB-SWE4-001).

This document satisfies **Automotive SPICE® PAM v4.0, SWE.3 — Software Detailed
Design and Unit Construction**.

### 3.2 Referenced Documents

| Document ID | Title | Version |
|---|---|---|
| TB-SWE1-001 | TestBench Software Requirements Specification | 0.1 |
| TB-SWE2-001 | TestBench Software Architecture Description | 0.1 |
| TB-SWE4-001 | TestBench Software Unit Verification Specification | 0.1 |
| TB-RTM-001 | TestBench Requirements Traceability Matrix | 0.1 |

### 3.3 Unit Identification

Each unit is named `<ELEMENT>-DD-<NAME>` and is cited from the module docstring
of the source file that implements it. The citation is checked mechanically:
`tests/test_traceability.py` fails if a module cites a unit this document does
not declare.

---

## 4. Unit Catalogue

| # | Element | Package | Design units |
|---|---|---|---|
| 5.1 | CORE | `benchtools.core` | 15 |
| 5.2 | ANA | `benchtools.analysis` | 3 |
| 5.3 | INST | `benchtools.instruments` | 5 |
| 5.4 | JLINK | `benchtools.instruments.jlink` | 10 |
| 5.5 | BLE | `benchtools.instruments.nordic_dongle` and `firmware/nordic_dongle` | 20 |
| 5.6 | S2LP | `benchtools.instruments.s2lp` | 9 |
| 5.7 | PSU | `benchtools.instruments.gpd3303d` | 4 |
| 5.8 | RUN | `benchtools.runner` | 8 |
| | **Total** | | **74** |

### 4.1 Package Structure

```
benchtools/
├── core/          instrument lifecycle, transports, SCPI base, validation, build manifests
├── analysis/      waveform model, measurement, plotting
├── instruments/   one subpackage per instrument, plus the generic driver
│   ├── tek3014b/      oscilloscope
│   ├── jlink/         debug probe
│   ├── nordic_dongle/ BLE dongle - host half of the element
│   ├── gpd3303d/      bench supply
│   └── s2lp/          sub-1 GHz development kit
└── runner/        bench configuration, specifications, limits, execution, reports

firmware/nordic_dongle/    the dongle's own half of the BLE element, in C
```

---

## 5. Detailed Unit Design

### 5.1 CORE — `benchtools.core`

#### CORE-DD-ERR — `errors.py`

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

#### CORE-DD-ENUMS — `enums.py`

`ScpiEnum` is a `str` enum whose value is the literal SCPI argument. `coerce()`
accepts a member, a member name or a mnemonic, case-insensitively, and otherwise
raises with the valid values listed. Only cross-instrument enumerations live here
(`EdgeDirection`, `Slope`); model-specific ones belong in that instrument's
`constants` module.

#### CORE-DD-VALIDATE — `validation.py`

`validate_range`, `validate_channel`, `validate_channels`, `validate_choice`.
Messages name the setting, the offending value, the permitted range and the unit.
`validate_channels` rejects duplicates rather than collapsing them: a duplicate
almost always means the caller built the list wrongly, and quietly returning
fewer channels than asked for would hide that.

#### CORE-DD-TRANSPORT — `transport/base.py`

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

#### CORE-DD-VXI11 — `transport/vxi11.py`

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

#### CORE-DD-SOCKET — `transport/socket_raw.py`

Raw TCP transport, for instruments that expose a SCPI socket. `_recv_chunk`
reports `end=True` only on a closed stream, so framing falls to the terminator.
`read_raw` uses an inter-byte idle gap, the only way to bound an unframed transfer
on a stream socket; this is documented as heuristic and is the main technical
argument for preferring VXI-11 where both exist.

#### CORE-DD-VISA — `transport/visa_backend.py`

Optional PyVISA transport. `pyvisa` is imported inside `_open_link`, so importing
the package never requires it. `_recv_chunk` derives the END flag from the VISA
status code, which is what lets the base class's framing work unchanged.

#### CORE-DD-FIRMWARE — `firmware.py`

`FirmwareBuild`: what a build system recorded about an image, read from the
`firmware_manifest.json` written beside it. `MANIFEST_NAME`, `parse_build_date`.

Design points:

- **It is in the core because two elements need it and neither may import the
  other** (CORE-NFR-008, CORE-NFR-009). The dongle reads a manifest to decide
  whether to refresh itself (BLE-DD-FIRMWARE); the debug probe reads one to say
  what version it has just flashed onto a target (JLINK-DD-PROBE). Duplicating
  the reader is how the two would drift apart on what a manifest is.
- **Two facts identify a build, and both are needed**: the version, which
  changes when someone deliberately changes behaviour, and the build date, which
  distinguishes two builds of the *same* version - the usual case during
  development, and precisely when a stale image is most misleading.
- **The "how to produce one" sentence comes from the caller**, as a `hint`. The
  core cannot know it: `make dfu` is the dongle's answer and means nothing to a
  sensor build. What the core does know is every path it searched, and it says
  so with or without a hint.
- **A build date the build did not inject is not a date.** A `local:` prefix
  marks the compiler's own macros - local time, no zone - and `built_at` returns
  `None` for it rather than a wrong instant. Two dongles built in different
  timezones would otherwise compare wrongly.

#### CORE-DD-PROCESS — `transport/process.py`

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

#### CORE-DD-SERIAL — `transport/serial_port.py`

`SerialTransport`, registered as the `serial`, `com` and `rs232` backends. Opens
through pyserial's URL handler rather than a device node, so one class covers a
local port (`COM5`, `/dev/ttyACM0`), a port published over TCP
(`socket://bench-pc:4001`, which is how a container reaches a dongle attached to
another machine), and pyserial's own `loop://`, which is what the tests drive.

Design points:

- **No reader thread**, unlike `CORE-DD-PROCESS`. A serial port supports a read
  timeout on Windows as well as POSIX; a pipe does not. A thread here would add
  a hand-off and buy nothing.
- pyserial is imported inside `_open_link`, so the package installs and runs
  without it and its absence is a diagnostic naming the extra (CORE-NFR-003).
- A trailing `:<digits>` in the resource is a line rate, except where it is a
  TCP port: `COM5:9600` is 9600 baud, `socket://host:4001` is not 4001 baud.
- A write the far end will not take is reported as a **timeout**, not a
  connection failure. The port is fine; flow control is asserted or the device
  stopped reading, and saying "connection failed" sends the reader to look at
  the cable.

#### CORE-DD-MOCK — `transport/mock.py`

Loopback transport accepting any `Responder` — anything with
`respond(bytes) -> bytes | None`. It has no knowledge of which instrument is
simulated. Responses are returned in small chunks so that framing and
reassembly are exercised rather than bypassed. The description is derived from
the responder's `*IDN?` model field, so it is meaningful for any instrument.

#### CORE-DD-FACTORY — `transport/factory.py`

`parse_resource()` is separated from `open_transport()` so parsing is testable
without opening a connection. Backends and URL schemes live in registries
(`register_backend`), so a new link type is added from its own module. The
significant rule: a bare host or a `TCPIP::…::INSTR` string resolves to the
**built-in VXI-11** transport; VISA is opt-in.

`open_transport` accepts a `responder_factory`, called when the resource selects
the simulator. This is how an instrument driver supplies *its own* simulator
without this module knowing about any instrument.

#### CORE-DD-INSTRUMENT — `instrument.py`

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

#### CORE-DD-SCPI — `scpi.py`

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

#### CORE-DD-SIM — `simulator.py`

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

### 5.2 ANA — `benchtools.analysis`

#### ANA-DD-WAVEFORM — `waveform.py`

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

#### ANA-DD-MEASURE — `measure.py`

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

#### ANA-DD-PLOT — `plotting.py`

`matplotlib` is imported inside `plot_waveforms` and the `Agg` backend selected,
so no display is needed on a test rig. Channel colours mirror the oscilloscope
front panel; the time axis auto-scales to an engineering prefix. Given a
`SpreadResult`, each channel's crossing is marked and the spread annotated — which
is what turns a skew number into reviewable evidence.

---

### 5.3 INST — `benchtools.instruments`

#### INST-DD-GENERIC — `generic.py`

`GenericScpiInstrument` adds nothing to `ScpiInstrument` beyond a model name. It
covers the part of every instrument that is always the same — prove it is
reachable, find out what it is, read its errors, send raw SCPI — and is what the
runner uses for a bench entry with no dedicated driver. Because it adds nothing,
it also demonstrates that the core is genuinely instrument-agnostic.

#### SCOPE-DD-CONST — `tek3014b/constants.py`

TDS3000-family enumerations and `ModelLimits`, the capability envelope
(channel count, volts/div range, position range, time/div range, record lengths,
average counts, bandwidth options). `TDS3014B_LIMITS` is the default instance;
supporting another family member is constructing a different one and passing it to
`Tek3014B(limits=...)` or `connect(..., limits=...)`.

#### SCOPE-DD-SCOPE — `tek3014b/scope.py`

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

#### SCOPE-DD-SIM — `tek3014b/simulator.py`

`SimulatedTDS3014B` subclasses `SimulatedInstrument`, adding the TDS3000 command
set, instrument state and `ChannelSignal` — an analytic description of each input
(frequency, amplitude, baseline, duty, rise and fall time, delay). `curve_codes`
digitises it through the same preamble the driver uses to undo the scaling,
including clipping at the digitiser rail. Measurements are computed from the model
parameters, **not** from the sampled record, so host-side analysis is validated
against an independent reference. `make_png` produces a genuinely valid PNG.

#### SCOPE-DD-CLI — `tek3014b/cli.py`

Sub-commands `idn`, `capture`, `spread`, `period`, `measure`, `screenshot`,
emitting JSON so the tool composes into a harness. `--resource` defaults to
`sim://`. Per-channel options accept one value for all channels or one per
channel. A negative value must be passed with `=` (`--position=-4,-3`), standard
`argparse` behaviour, documented in the README.

---

### 5.4 JLINK — `benchtools.instruments.jlink`

Seven collaborators and a façade (JLINK-ARC-001). The split is by *reason to
change*: the MI grammar changes with GDB, RTT with SEGGER's protocol, ITM with the
ARM architecture, the envelope with the probe model.

#### JLINK-DD-GDBMI — `jlink/gdbmi.py`

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

#### JLINK-DD-SESSION — `jlink/session.py`

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

#### JLINK-DD-SERVER — `jlink/server.py`

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

#### JLINK-DD-RTT — `jlink/rtt.py`

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

#### JLINK-DD-SWO — `jlink/swo.py`

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

#### JLINK-DD-TIMING — `jlink/timing.py`

`TimingSample` and `TimingResult`: the result type, with no measuring in it.

`TimingResult` carries the method, the samples, the core clock and whether the
target was halted, and derives `seconds`, `microseconds`, `cycles`, `minimum`,
`maximum`, `spread`, `standard_deviation`, `resolution_seconds` and
`is_trustworthy` (false when the interval is under ten times the method's
resolution). `as_dict()` is the plain-types boundary of AD-15.

An empty sample list raises `MeasurementError` rather than reporting zero seconds —
a zero would be indistinguishable from a fast interval.

#### JLINK-DD-CONST — `jlink/constants.py`

The vocabulary and the envelope, as data (JLINK-FR-010): `DebugInterface`,
`ResetType`, `HaltReason` (with an `UNKNOWN` fallback, so a GDB version reporting a
reason this driver has not met does not crash the run), `BreakpointKind`,
`WatchpointKind`, `TimingMethod`, the server's ports, the DEMCR/DWT register
addresses, and `ProbeLimits` — hardware breakpoints, watchpoints, RTT channels,
maximum transfer size, core clock, and `cycle_counter_max_seconds`, the interval
beyond which the 32-bit cycle counter wraps.

`TimingMethod` carries the trade-off of each method in its docstring, next to the
member, because that is where the choice is made.

#### JLINK-DD-SIM — `jlink/simulator.py`

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
- `SimulatedFirmware.memory` holds bytes that belong to the **part** rather than
  to the program: the identity record at UICR `CUSTOMER[0]` — a validity byte of
  zero and then three identifier bytes in address order, `00 0A 1B 2C`. Raw
  bytes, not a word, because such a record has its own layout and byte order and
  writing it as a word would bake a guess about that into the fixture. The
  identifier renders as `0A1B2C`, which is in the name of the board the
  simulated dongle advertises (BLE-DD-SIM); the two must agree or the bring-up
  specification could not run without hardware.
- A reset **with the run argument runs** (D-39). Modelling `monitor reset 0` as
  reset-and-halt left a silent, stopped target for every test that starts the
  firmware and then asks whether it is running.

#### JLINK-DD-PROBE — `jlink/probe.py`

`JLinkProbe`, the façade: an `Instrument` (CORE-DD-INSTRUMENT) whose transport is a
GDB process or a simulator.

| Group | Members |
|---|---|
| Lifecycle | `connect`, `_post_open`, `load_symbols`, `attach`, `monitor`, `close` |
| Programming | `flash`, `verify`, `erase`, `image_build` |
| Execution | `reset`, `run`/`resume`, `halt`/`stop`, `step`, `wait_for_halt`, `is_halted`, `program_counter`, `registers`, `run_to` |
| Breakpoints | `set_breakpoint`, `set_watchpoint`, `list_breakpoints`, `delete_breakpoint`, `clear_breakpoints` |
| Memory | `read_memory`, `write_memory`, `read_word`, `write_word`, `read_u8`, `read_u16`, `read_integer`, `read_ram`, `write_ram` |
| Symbols | `read_variable`, `write_variable`, `variable_address`, `variable_size`, `evaluate`, `call_stack`/`backtrace` |
| RTT | `rtt_start`, `rtt_stop`, `rtt_read_lines`, `rtt_lines_within`, `rtt_write`, `rtt_expect`, `rtt_command`, `rtt_log` |
| Timing | `enable_cycle_counter`, `read_cycle_counter`, `measure_time_between` |

Design points:

- `_parse_target` accepts `sim://`, `jlink://`, `gdb://` and `tcp://`, with or
  without a host and port, so one resource string covers the simulator, a local
  probe and a probe on another machine (AD-13).
- **`read_integer` states the byte order; the word accessors do not.** A word is
  little-endian because that is how the core loads one. A record a part was
  *programmed* with - an identifier written at manufacture - is usually in
  address order and need not be four bytes wide, and both are properties of the
  record rather than of the debugger. A misspelled byte order is refused rather
  than treated as little-endian, because it would otherwise read a plausible and
  entirely wrong number.
- **`image_build` is a claim about the file, not about the part** (CORE-DD-FIRMWARE).
  It reads the manifest beside the image the probe flashed, so a test can state
  the version it *put* on a board. Comparing that with what the running firmware
  reports over its own link is then a check on two independent things agreeing;
  a version typed into a specification would make it circular.
- **`rtt_lines_within` counts rather than waits.** `rtt_expect` raises on
  timeout, which a runner records as an error - the wrong verdict for a board
  that started and said nothing. A count is a measurement a limit can fail, so
  silence reads as a failed test (RUN-FR-031).
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

#### JLINK-DD-CLI — `jlink/cli.py`

Sub-commands `info`, `flash`, `verify`, `reset`, `run`, `halt`, `read`, `write`,
`var`, `stack`, `rtt`, `time`, emitting JSON (AD-15). The `time` sub-command adds a
`warning` key when the result is not trustworthy, so a figure quoted from a shell
script carries the same caveat the API gives.

---

### 5.5 BLE — `benchtools.instruments.nordic_dongle` and `firmware/nordic_dongle`

One element in two languages (AD-16). The host units come first, then the
firmware units; `BLE-DD-PROTOCOL` is the interface both sides are built from.

#### BLE-DD-PROTOCOL — `protocol.py` and `firmware/include/protocol.h`

The header is the contract: command table, event table, error table and size
limits, as X-macro tables the firmware expands into its dispatch table and the
host's test suite parses. `protocol.py` is the host's parser for the same
grammar: `parse_line` returns a `Reply`, an `Event`, or `None` for a line that
is not ours - a boot banner, a stray newline.

Points that matter:

- A value may be empty (`name=` for a sensor advertising no name) and may
  contain `=`; only the first `=` of a token separates. A token with no `=` is
  kept under its own name, which is how the positional words of
  `ok Nordic PCA10059 proto=1.0` survive.
- Addresses are validated and upper-cased, and carry an optional `/<type>`
  suffix. The type travels with the address everywhere because connecting with
  the wrong one fails by never finding the device - the least diagnosable
  failure in BLE.
- No I/O and no state, so every shape is a one-line test rather than a hardware
  session.

#### BLE-DD-SESSION — `session.py`

`DongleSession`: command in, reply out, with events queued beside it.

- Lines are classified before use, so an advertising report that arrives while a
  command is outstanding is never mistaken for its reply. Nothing is discarded:
  that report is exactly what a profile capture must not lose.
- `collect(duration, on_event, stop)` reads events; `stop` ends collection on a
  predicate. That predicate is what lets a capture be bounded by the *dongle's*
  clock: against a simulator, whose clock advances as fast as it is read, a
  wall-clock bound would collect eight minutes of advertising in a quarter of a
  second (defect D-16).
- `wait_for_event` is satisfied by an event already queued, so a caller that
  asks a moment late is not made to wait for a second one.
- Session logging lives here because this is the only place that sees the whole
  conversation, including lines the driver ignored. A log that omits what the
  tooling discarded cannot explain why it discarded it. Flushed per line.

#### BLE-DD-PROFILE — `profile.py`

`AdvertisingEvent` and `AdvertisingProfile`. Three subtleties, each handled here
rather than left to whoever reads the numbers:

| Subtlety | Handling |
|---|---|
| One advertising event is up to three packets (channels 37/38/39) | Reports within `COALESCE_WINDOW_S` (5 ms) are one event; the first is kept, so the interval is measured from the same point each time |
| The specification *requires* jitter: advDelay is a uniform 0-10 ms added to every interval | `expected_jitter_s` states what a conforming sensor shows (2.89 ms); `within_specification` allows for it; the inferred nominal interval subtracts the mean 5 ms |
| A missing beacon and a lost USB line look identical | The firmware counts what the radio delivered, the host counts what arrived, `is_complete` compares them |

Intervals are subtracted as integer microseconds and converted once. Subtracting
two floats puts an exactly nominal 100 ms interval at 0.09999999999999998, which
fails a limit written as ">= 0.1" - a sensor rejected by floating-point
representation rather than by behaviour (defect D-15).

#### BLE-DD-SCRIPT — `script.py`

`CommandScript`, `ScriptTest`, `ScriptStep`; `parse_script`, `load_script`.
The document that specifies the sensor's command set, read as the test of it
(AD-23). Running it is BLE-DD-SCRIPTRUN.

Design points:

- **The reader is strict and the diagnostic names the line.** A row that cannot
  be read, a step number used twice in one test, a delay that is not a positive
  duration: each is refused. These documents are maintained by hand, and a row
  skipped quietly is a command nobody tested and nobody missed.
- **What a row is, is decided by its cells.** `delay <ms>`, `connect <sensor>`
  and `disconnect` act on the dongle; any other command goes to the sensor. An
  expected response of `<disconnect>` says the sensor will drop the link. The
  Timeout and Note columns are optional, and a table naming none of the step
  columns is prose.
- **Variables are substituted as the rows are read**, from a `| Variable |
  Default |` table that must come before the first step, overridden by the values
  given for the run. An undeclared name, a value for one, or a required variable
  left unset is refused naming the line, so a misspelt `--var` cannot leave a
  default silently in force. The syntax is Robot Framework's, `${NAME}`.
- **The reader is split from the runner** because together they passed the
  1000-line limit; `_Reader` holds the state of one document being read, so each
  kind of row has one place.
- **Outcomes are plain strings**, not the runner's `Status`: an instrument may
  not import the runner (CORE-NFR-009), and these strings end up in a document
  a person reads.

#### BLE-DD-SCRIPTRUN — `script_run.py`

`run_script`, `StepResult`, `ScriptRun`, `EventLog`. Runs a document read by
BLE-DD-SCRIPT, one step at a time.

- **One result per step, the first that applies.** ERROR when the system
  returned a failure code (a `BenchToolsError` from the dongle, including no
  reply where one was expected); SKIP when nothing was expected; FAIL when the
  reply differs; PASS when it matches. Silence where nothing was expected stays
  a SKIP, so a command that never answers can still be sent. A run is ERROR,
  else FAIL, else PASS.
- **A skipped step must never read as one that passed.** `ScriptRun` reports
  passed, failed, errored *and* skipped, and `CommandScript.checks` says how many
  rows make a claim at all.
- **The time is the dongle's, quoted at 10 ms and kept at microseconds.**
  `RESOLUTION_S` is what the report shows; `StepResult.elapsed_s` is what was
  measured and `clock` is which clock measured it (BLE-NFR-005). For a
  `<disconnect>` step it is the write to the `+disc`; a reason of `0x08` means a
  supervision timeout, so the figure includes the dongle's 4 s wait.
- **A step never raises.** Its outcome *is* its result: an exception from one
  command would abandon the rest of a document. The handlers catch
  `BenchToolsError` only, so a bug still surfaces.
- **A link the document opened is closed** in a `finally`, pass or fail.
- **The event log is written as it happens**, one tab-separated line per event,
  flushed per line so an interrupted run still leaves it, and kept on the
  `ScriptRun` as well. Its time is the host's to the millisecond; the dongle's
  measurement travels in the RX line's data.

#### BLE-DD-LATENCY — `latency.py`

`ResponseSample` and `ResponseTiming`: the result type for a command/response
round trip, with no measuring in it.

Two clocks are carried: the dongle's (the measurement) and the host's (the
cross-check). `resolution_s` is 1 us for the first and 1 ms for the second - not
the microsecond `perf_counter` will print, because the figure carries USB
polling and OS scheduling. `quantisation_s` is the connection interval: a reply
cannot arrive between connection events, so a latency inside one interval says
where the write landed, not what the firmware did, and `is_trustworthy` is false
there.

Deliberately a sibling of `JLINK-DD-TIMING` rather than a shared type: the two
measure different things with different floors. If a third instrument needs
statistics of this shape, the place for them is `benchtools.analysis`.

#### BLE-DD-CONST — `constants.py`

The command set, event names, error codes, address types and the firmware's
capability envelope, as data. Every name here also appears in `protocol.h`, and
`test_firmware_protocol.py` compares the two (BLE-NFR-003).

`DongleError.coerce` and `AddressType.coerce` fall back rather than raising, so
a dongle running newer firmware that reports a code this driver has not met
degrades instead of crashing a run. `DongleLimits` holds the `PROTO_MAX_*`
figures so the driver refuses an over-long payload with a clear message rather
than letting the firmware truncate it silently, and states both clocks'
resolutions - 1 us on the dongle, 1 ms on the host - in one place.

#### BLE-DD-DONGLE — `dongle.py`

`NordicDongle`, the façade: an `Instrument` (CORE-DD-INSTRUMENT) whose transport
is a serial port or a simulator.

| Group | Members |
|---|---|
| Lifecycle | `connect`, `_open`, `_close`, `_post_open`, `_read_identity`, `reset` |
| Discovery | `scan`, `refresh_sensors`, `sensors`, `find_sensor`, `select`, `selected` |
| Link | `open_link`, `close_link`, `is_linked`, `connection_interval_us` |
| UART | `write`, `command`, `measure_response_time` |
| Advertising | `measure_advertising_profile` |
| Logging | `start_log`, `stop_log`, `log_note`, `log_path` |
| Firmware | `firmware_version`, `firmware_built`, `firmware_built_at`, `protocol_version`, `protocol_is_compatible`, `expect_firmware`, `check_firmware`, `enter_dfu`, `update_firmware`, `ensure_firmware` |

Design points:

- `_normalise_resource` turns a bare `COM5` into `serial://COM5`. Without it the
  factory would read it as a network host, which is the right default everywhere
  else in the package and exactly wrong here.
- `_post_open` checks the firmware's protocol version against the driver's and
  refuses a mismatch at connection time, rather than failing three commands later.
  Only the **major** version is fatal. A minor difference means one side has
  commands the other lacks, which shows up per command and is recoverable; a
  major difference means the two disagree about what a line means, which is not.
  `update_firmware=True` suspends the check entirely, because refusing to talk
  to an out-of-date dongle would mean refusing to fix it.
- `_read_identity` parses `fw=` and `built=` out of the `ver` reply and puts the
  **build**, not the protocol version, in `Identity.firmware`. A report reader
  needs to know which image produced the numbers; the protocol version is a
  property of the conversation, not of the evidence.
- The capture in `measure_advertising_profile` is bounded by the dongle's clock
  with the host's wall clock as a backstop, so a sensor that goes silent still
  ends the capture.
- The connection interval is taken from the `+conn` event rather than a later
  query, because it is the floor under every latency measured on that link.

#### BLE-DD-FIRMWARE — `firmware.py`

Build identity and refresh, kept out of `dongle.py` because it is about images
on disk rather than about the link.

| Unit | Responsibility |
|---|---|
| `FirmwareBuild` | What the build produced: version, build instant, protocol, model, hex, DFU package, SHA-256. Loaded from `firmware_manifest.json` (BLE-DD-VERSION), located from a manifest, a build directory or a project directory. |
| `FirmwareStatus` | The comparison: `version_matches`, `date_matches`, `matches`, `is_older`, `compared`, `updated`, and `describe()` for a log line. |
| `parse_build_date` | ISO 8601 text to an aware UTC instant, or `None`. |
| `run_nrfutil` | The default flasher: `nrfutil dfu usb-serial`, with its output carried into the exception when it fails. |

Design points:

- **The date is compared, not only the version.** During development every image
  is `1.1.0`; comparing versions alone would call a week-old dongle up to date.
  This is the case the unit exists for.
- `is_older` is three-valued. A build date the driver cannot order - a
  `local:` date from a compiler macro, or anything not ISO 8601 - gives `None`,
  not `False`: "unknown" and "no" are different answers, and only one of them
  justifies leaving the dongle alone.
- `matches` is false when there is nothing to compare against. A run that never
  established which image was under test has not established that it matched.
- The package is required only when flashing. Checking a dongle against a build
  that was never packaged is a legitimate thing to do, and `make dfu` is the
  advice to give if flashing is then asked for.
- After flashing, the driver reconnects and re-reads `ver`. "The tool reported
  success" and "the dongle is running the image" are different facts, and only
  the second one is worth recording.

#### BLE-DD-VERSION — `firmware/include/firmware_version.h`, `firmware/src/firmware_version.c`, `Makefile`

One version string, in a header the firmware compiles and the Makefile greps, so
the image and the manifest cannot disagree - the failure mode that would make
every comparison above meaningless.

The build date is injected as `-DFIRMWARE_BUILD_DATE`, derived from
`SOURCE_DATE_EPOCH` when set, so a reproducible build reproduces its date. When
nothing injects it, `firmware_build_date()` falls back to the compiler's
`__DATE__` and `__TIME__`, rearranged once at first call as
`local:Sep-05-2026T20:13:52`. It is tagged `local:` precisely so the host refuses
to treat it as an instant: the compiler macros carry no timezone and no ordering.
It carries no spaces because the link protocol splits fields on them; the
macros' own form arrived at the host as `local:Sep` (issue #34).

The date is held in **one translation unit**, `firmware_version.c`, whose object
the Makefile deletes before every build. This is not tidiness: the date arrives
through `CFLAGS`, and make does not recompile a file because a command line
changed. Without the deletion an incremental build would leave the *first*
build's date in the image while the manifest carried today's - and the host,
comparing the two, would report a dongle as out of date immediately after
refreshing it, for ever. One compile per build buys the guarantee that the two
cannot disagree. CI pins `SOURCE_DATE_EPOCH` to the commit's timestamp, so its
several make invocations all stamp one identity.

`make manifest` writes `firmware_manifest.json` beside the image - version,
build instant, protocol, model, hex, DFU package, SHA-256 - which is what
BLE-DD-FIRMWARE reads and what CI uploads with the artefacts.

#### BLE-DD-BOOTLOADER — `firmware/src/bootloader.c`

Entry into the Nordic USB bootloader is by **pin reset**. The PCA10059 open
bootloader in nRF5 SDK 17.1.0 is built with `NRF_BL_DFU_ENTER_METHOD_PINRESET 1`
and `NRF_BL_DFU_ENTER_METHOD_GPREGRET 0`: it enters DFU after a pin reset and
ignores `GPREGRET`. So the firmware drives P0.19 low, which on the PCA10059 is
wired to nRESET (`BSP_SELF_PINRESET_PIN`, the method Nordic's own USB DFU trigger
uses). If the chip is still running 10 ms later the pin is not wired on this
board, and it falls back to `NVIC_SystemReset()`.

Before that it still sets `GPREGRET` to `BOOTLOADER_DFU_START` (0xB1), for a
bootloader built to honour it. The write goes through `sd_power_gpregret_clr/set`
while the SoftDevice is enabled and straight to `NRF_POWER->GPREGRET` when it is
not - writing the peripheral directly under an enabled SoftDevice is undefined.

`cmd_parser` sends the reply first, so the host receives `ok dfu=1` rather than
a silence it would have to interpret. It keeps servicing USB until the transmit
queue is empty (`cdc_acm_tx_idle()`) and a further 50 ms have passed, bounded at
250 ms. The grace period is needed: a transfer is complete for the dongle once
the USB peripheral has it, and resetting at that point lost the reply every time
on a PCA10059 under Windows (issue #33).

#### BLE-DD-SIM — `simulator.py`

A simulated dongle and the sensors it can hear, satisfying `Streamer`
(CORE-DD-MOCK): `respond()` answers commands, `poll()` produces advertising.

The model is exact rather than lifelike. Advertising events are placed on a
virtual microsecond clock at the nominal interval plus a rotating pattern of
advertising delays (0, 3, 7, 10 ms), so a 100 ms sensor reads as a mean of
exactly 105 ms with a spread of exactly 10 ms. The clock advances only when the
host reads, so a two minute capture runs in milliseconds and still produces the
intervals a two minute capture would.

The default population is part of the contract the tests assert against:
`SENS-0A1B2C` at 100 ms, `SENS-0B2C3D` at 250 ms missing one beacon in five (so gap
detection has something to find), and an unnamed, unconnectable beacon (so
filtering and refusals have something to work on). The names carry the board
identifier as six hex digits because that is how these boards name themselves,
and `SENS-0A1B2C` is the identity record the simulated part carries (JLINK-DD-SIM)
- the two have to agree or the bring-up specification could not be run without
hardware. `drop_every` models a dongle
whose USB queue could not keep up, which is what `is_complete` exists to detect.

#### BLE-DD-CLI — `cli.py`

Sub-commands `info`, `scan`, `select`, `profile`, `cmd`, `monitor`, `firmware`,
emitting
JSON. `--log` records the whole session beside whatever the sub-command prints:
that file is the evidence, the JSON is the summary. `profile` and `cmd` add a
`warning` key when the result is incomplete or not resolvable, so a figure
quoted from a shell script carries the same caveat the API gives. `firmware`
exits 1 on a mismatch, so a build step stops rather than publishing numbers
taken with the wrong image; `--update` refreshes the dongle instead.

---

#### BLE-DD-TEST — `firmware/test/`

Host-side unit tests for the firmware: Unity, built by CMake, run by CTest.

The seam is the **SDK boundary**. `test/support/include/` holds fake headers -
`ble_gap.h`, `nrf_ble_scan.h`, `app_usbd_cdc_acm.h`, `nrfx_timer.h` and the rest
- placed ahead of everything on the include path, so the firmware's own sources
compile unchanged and what runs under test is the code that runs on the dongle.
Each fake does the least that keeps the firmware honest, with one deliberate
exception: where behaviour depends on the SDK's *semantics* rather than its
signature - `ble_advdata_search` returning the offset of the payload, not of the
length byte - the fake implements the semantics, because a stub returning a
constant would hide exactly the mistake worth finding.

| Binary | Unit under test | Fakes linked |
|---|---|---|
| `test_timestamp` | `timestamp.c` | SDK |
| `test_cdc_acm` | `cdc_acm.c` | SDK |
| `test_ble_scanner` | `ble_scanner.c` | SDK, host link |
| `test_nus_client` | `nus_client.c` | SDK, host link, scanner |
| `test_cmd_parser` | `cmd_parser.c` | SDK, host link, scanner, UART client |

A binary links only the fakes it needs: a fake beside the module it stands in
for is a duplicate symbol, which is why there is no reset-everything helper and
each `setUp` resets what its own binary has.

Three points about state. The firmware's modules hold static state with no
reset - as they do on the dongle, where the only reset is a reset - so:
`cmd_parser_init` clears the selection (it is "start from a known state", which
the target wants too); `test_cdc_acm` drains whatever the previous test left in
flight, which exercises the drain path as a side benefit; and the two timestamp
tests that must run before initialisation are run first, deliberately and in
writing, with everything after them made order-independent by measuring deltas.

The critical-region fakes keep the SDK's brace-pair shape rather than being flat
calls, so the misuse of defect D-23 cannot compile here either.

#### BLE-DD-CDC — `firmware/src/cdc_acm.c`

USB CDC ACM as a line transport, with a 32-line outgoing queue.

Output is queued, never written from a radio event handler: a burst of
advertising reports arrives faster than USB will take it, and blocking in the
handler would delay the next radio event and corrupt the very measurement being
made. When the queue is full a whole line is **dropped and counted**, never
truncated - half a line is a parse error in the host and would look like a
protocol fault rather than congestion.

Input is read a byte at a time (which is how the CDC driver reports it) and
assembled into a line; an over-long line is discarded rather than acted on in
part.

#### BLE-DD-TIMESTAMP — `firmware/src/timestamp.c`

A 1 MHz TIMER (TIMER3; TIMER0 belongs to the SoftDevice) captured on demand and
extended to 64 bits by counting overflows in its interrupt.

Not `app_timer`: that counts 32.768 kHz RTC ticks, resolving 30.5 us, which is
the same order as the jitter being measured. The 32-bit hardware counter wraps
every 71.6 minutes at 1 MHz, so the overflow count is re-read after the capture
and the capture repeated if it changed - a read that straddles an overflow
cannot return a stale figure, and at most one retry is ever needed.

#### BLE-DD-SCANNER — `firmware/src/ble_scanner.c`

Scanning, the sensor table and advertising-report timestamping.

- The timestamp is taken **first**, before the payload is parsed: every
  microsecond spent before it is added to the interval being measured.
- Discovery and profiling share one scan; only the reporting differs. Profiling
  filters to one address in the firmware, because forwarding every packet from a
  busy room over USB is what causes the drops that would then be misread as the
  sensor missing an advertising event (AD-18).
- A 100 ms window inside a 100 ms interval is a continuous scan: a duty-cycled
  scan would add its own gaps to the sensor's, and afterwards the two would be
  indistinguishable.
- The sensor table is bounded and does not evict: once full, a new address is
  ignored rather than displacing one the host may already have selected.
- Addresses are formatted most significant octet first, as they are written,
  while the stack stores them the other way round.

#### BLE-DD-NUS — `firmware/src/nus_client.c`

Nordic's UART Service as a command/response channel. Connects, discovers,
subscribes, and provides write and timed-command operations.

The round trip is timestamped at both ends in the dongle: when the write is
handed to the SoftDevice, and when the notification arrives. The write timestamp
is the instant the request left the application, not the antenna - the
difference is bounded by the connection interval, which is reported alongside so
the figure can be read correctly. USB is serviced while waiting for a reply, so
a five second timeout does not cost the host five seconds of advertising events.

#### BLE-DD-CMD — `firmware/src/cmd_parser.c`

The dispatcher: one line in, exactly one `ok` or `err` line out.

Argument bounds come from `PROTO_COMMAND_TABLE`, so the checks and the
documented command set cannot drift. Handlers are attached **by name** rather
than by position, and `cmd_parser_init` verifies at start-up that every
documented command has one - a command documented with no implementation would
otherwise answer "unknown command" at a bench. A timeout waiting for a sensor is
reported as an error, not as a round trip of the timeout's length, which would
enter the log as a measurement.

`connect` and, from protocol 1.3, `cmd` take an optional `timeout=<ms>`; the
connect window defaults to 15 s and the reply wait to 2 s. Reading those
arguments is BLE-DD-CMDARGS, kept apart so `cmd_parser.c` stays under the
800-line limit.

#### BLE-DD-CMDARGS — `firmware/src/cmd_args.c`

`cmd_args_timeout` reads one `timeout=<ms>` token against the bounds its caller
gives - `PROTOCOL_CONNECT_*` or `PROTOCOL_CMD_*` - and says separately whether
the token was a timeout and whether its value was good, so a malformed one is
refused rather than read as an address. `cmd_args_connect` reads `connect`'s
address and timeout in either order.

#### BLE-DD-MAIN — `firmware/src/main.c`

Start-up and the main loop: clock, timestamp, USB, SoftDevice, GATT, discovery,
scanner, UART client, then `cdc_acm_process()` and one command line per pass.
The BLE observer dispatches to the scanner first (so reports are timestamped
before anything else looks at them), then the UART client, then discovery.

#### BLE-DD-BUILD — `firmware/ses/`, `firmware/config/sdk_config.h`, `firmware/scripts/`

A SEGGER Embedded Studio project with `SDK_ROOT` as its one external macro, a
flash placement putting the application above the S140 SoftDevice at 0x27000,
and a minimal `sdk_config.h` enabling only what is used - SDK components test
their own switch with `NRF_MODULE_ENABLED`, which reads an undefined symbol as
disabled, so a component enabled without its settings fails to compile and names
the missing symbol. `package_dfu.sh`/`.bat` wrap the built hex for the dongle's
factory bootloader with `nrfutil`, since a PCA10059 has no onboard debugger.

The Makefile beside the SES project is the headless build: CI cannot licence an
IDE, and "the firmware builds" is worth knowing on every push. It is modelled on
Nordic's own armgcc makefiles and includes the SDK's `Makefile.common`, with
`gcc/nordic_dongle_gcc_nrf52.ld` repeating the flash and RAM figures the SES
project carries - if the SoftDevice changes, both change together.

`compile_check.sh` compiles every unit against real SDK headers inside the
`canembed/canembed-arm` image, which carries GCC 10.2.1 and nRF5 SDK 15.2.0.
It is a cross-version check - the firmware targets 17.1.0 - so it lists, rather
than hides, the lines using SDK 17 API that the older SDK lacks. Its value is
that it needs no bench and no Nordic download: it found seven defects the
document-and-test discipline had not (SWE.4 report §4.4).

---

### 5.6 S2LP — `benchtools.instruments.s2lp`

An ST S2-LP development kit over USB. The board runs **ST's own CLI firmware**
(AD-20), so every unit here is host-side and the firmware's command set is an
external interface.

#### S2LP-DD-CONST — `constants.py`

The boards and their bands, the modulation and strobe codes, the FIFO and
payload limits, and `COMMANDS`: the firmware's command names with the argument
types ST declares for each. Written down so that a driver mistake - a command
that does not exist, or an argument that does not fit - fails as a named error in
a test rather than as a timeout on the bench.

#### S2LP-DD-REGS — `registers.py`

The device's register map: 123 registers by name and address, each with its reset
value, its access and its named bit fields. `Field` extracts and inserts bits;
`Register.describe` renders one readable line; `contiguous_runs` groups the
sparse map into blocks that can be read in one command each.

Design points:

- **It is what makes "read all registers" useful.** A dump of 123 hex bytes says
  nothing. `PCKTCTRL3 = 0xC0  PCKT_FRMT=3` says what the radio was configured to
  do, and `registers_differing_from_reset` answers the question behind the
  question: what has this radio been set up to do?
- **`Field.insert` refuses a value too wide for its field.** Truncating silently
  would write a different configuration from the one asked for, and the read-back
  would agree with the truncation.
- **Reserved bits are not fields.** Anything this map names, the datasheet names.
- **It holds facts, not prose** (S2LP-NFR-002): addresses, reset values, field
  names and bit positions. Field descriptions belong in the datasheet, and the
  vendor's wording stays in the vendor's document.
- The dump reads **contiguous runs**: 15 commands instead of 123, which on a
  115200 baud link is the difference between instant and not.

#### S2LP-DD-CONFIG — `configuration.py`

Register values read from a file, applied to a radio and checked against it.
The list of settings lives in a file rather than in a test because the person
who works out the settings is rarely the person writing the specification, and a
setting that moves should not require a code change.

| Unit | Responsibility |
|---|---|
| `RegisterSetting` | One register, the value asked for, and the line it came from |
| `RegisterConfiguration` | The settings of one file, **in the file's order** |
| `ConfigurationCheck` | What the radio holds against what the file asked for: `mismatches`, `unexpected`, `matches` |
| `parse_register_file` / `load_register_file` | Text or file to a configuration |
| `format_register_file` | A configuration back out as text |

Design points:

- **Forgiving about punctuation, strict about content.** These files are written
  by hand and exported by tools that each punctuate differently, so the
  separator may be a space, `=`, `:` or `,`; `#`, `;` and `//` start comments;
  and a register may be named by address. But every line ends up written to a
  radio, so an unknown register, a value that does not fit a byte, a read-only
  register, a register named twice, or a line that is not a setting is an error
  naming the file and the line.
- **Values are hexadecimal**, with or without `0x`. Guessing per line - `10` as
  ten in one file and sixteen in the next - is exactly the ambiguity that
  produces a radio configured almost right.
- **A C `#define` line is deliberately not accepted.** Supporting it would mean
  deciding whether a `#` starts a comment by looking at what follows it, and a
  format where a typo turns a setting into a comment silently is worse than one
  that refuses the line.
- **The file's order is kept**, because some settings only take effect written
  after another; `_runs_of` still groups consecutive addresses into single
  writes without reordering.
- **A register set twice is an error, not last-wins.** A file that sets a
  register twice does not say what it wants.
- **Two verification modes** (S2LP-FR-019). The loose check answers "is what
  this test needs set?"; the strict check adds "and is nothing else set?",
  which is what catches a register left behind by whatever ran before. The
  loose check reads only the registers the file names; the strict one reads the
  whole map, because it has to.
- **Applying verifies by default.** A write is acknowledged by the firmware, not
  by the radio: "the command was accepted" and "the register holds the value"
  are different facts.
- **`reset` decides what the file is written on top of** (S2LP-FR-021).
  `"defaults"` writes every writable register back to its documented value;
  `"power"` takes the radio through shutdown and back. Either is *confirmed* by
  read-back before anything is applied, because "the reset was commanded" and
  "the radio is at defaults" are different facts and the file is written on top
  of the second. The default is `"none"`: wiping 123 registers is a larger
  action than applying three and should be asked for.
- **The reset strobe is not one of the choices.** ST's command header calls
  `SRES` a "reset of all digital part, except SPI registers", so a radio reset
  that way comes back configured exactly as it was. Offering it here would
  invite precisely the mistake this option exists to prevent.
- **`format_register_file` omits read-only registers.** A captured file that
  names one cannot be applied, and a record that cannot be replayed is a trap.

#### S2LP-DD-PROTOCOL — `protocol.py`

The host's half of ST's CLI line protocol, and nothing else: it formats a command
line and parses a reply, and knows nothing about radios.

`format_command` checks arguments against the types the firmware declares, so an
out-of-range value is caught naming the command rather than producing a terse
firmware error. `parse_reply` collects the reply's brace-delimited tags -
`regs_list`, `bytes`, `rssi`, `error`, `timer` - and keeps every line verbatim.

Two details that bite:

- **`Reply.hex_number` exists because the firmware writes some tags with `%x`**,
  which emits bare hex. Read as decimal, an RSSI of `D4` is 4 - a plausible
  figure that is wrong by 104 dB. The tags the firmware writes in hex are read in
  hex, explicitly.
- **The number pattern accepts a minus sign.** `S2LPQiGetRssidBm` answers in dBm,
  and dropping the sign turns -110 dBm into +110 dBm: not merely wrong but
  impossible, and nothing downstream would question it.

#### S2LP-DD-SESSION — `session.py`

Commands out, replies in, every line logged.

- **Where a reply ends** is decided by counting braces, because the firmware
  closes some replies on the first line and others five lines later. Waiting for
  a fixed number of lines would truncate half the command set.
- **`stop()` sends a single `S`**, with no terminator: ST's firmware polls the
  port for that character inside its capture loops, and it is the only way to end
  a long capture without resetting the board.
- `collect()` yields replies as they arrive, so a caller can log each packet as
  it lands; a batch cut short returns what arrived rather than raising, because
  a truncated capture is a fact the caller needs.
- The **raw session log** is written here: every line, both directions,
  host-timestamped, flushed per line.

#### S2LP-DD-PACKETS — `packets.py`

`Packet` (direction, payload, RSSI, both clocks, error), `Capture` (the packets
plus how they were taken) and `PacketLog` (JSON Lines, one object per line).

The design point is `Capture.gaps`. ST's firmware receives when asked: each
polled receive arms the radio, waits, and returns, and a packet arriving between
calls is not lost so much as *invisible*. A capture therefore records how many
times it re-armed, and `is_continuous` is false when it did - so "nothing was
transmitted" and "we were not listening" stay distinguishable. A count of what
was missed is not available from this hardware path, and this package does not
invent one.

JSON Lines rather than one JSON document, so a capture interrupted half way
through is still a readable file - which is the usual case, since a capture is
usually interrupted on purpose.

#### S2LP-DD-S2LP — `s2lp.py`

`S2lpDevkit`, the façade: an `Instrument` (CORE-DD-INSTRUMENT) over a serial
transport.

| Group | Members |
|---|---|
| Lifecycle | `connect`, `_normalise_resource`, `_post_open`, `_read_identity`, `reset` |
| Registers | `read_register(s)`, `write_register(s)`, `read_all_registers`, `dump_registers`, `registers_differing_from_reset`, `read_field`, `write_field`, `strobe`, `restore_defaults` |
| Radio | `configure_radio`, `radio_info`, `frequency_hz`, `set_frequency`, `modulation`, `set_modulation`, `power_dbm`, `set_power_dbm`, `rssi_dbm`, `payload_length`, `set_payload_length` |
| Traffic | `transmit`, `transmit_batch`, `receive`, `capture`, `stop` |
| Logging | `start_log`, `start_packet_log`, `log_note`, `log_path`, `packet_log_path` |

Design points:

- **`_post_open` identifies and configures nothing.** Connecting must not retune
  a radio somebody left set up.
- **The band comes from the board**, not from configuration, and a frequency
  outside it is refused: the radio would accept it, report it faithfully, and
  transmit into a filter and matching network that do not pass it.
- **`write_field` reads, modifies and writes**, so the other fields of the
  register keep their values. Writing a field's value to the whole register is
  the mistake this method exists to prevent.
- **A register read is checked against the addresses that came back.** The
  firmware interleaves address and value; if the addresses are not the ones asked
  for, neither are the values.
- **`capture(continuous=True)` keeps the board in its own loop** and has no gaps.
  The polled path is bounded by an attempt count as well as by time, because an
  arm that finds nothing returns immediately and an unbounded loop would spend
  the whole timeout re-arming and call the result a capture.
- **Verification is `radio_info()` after configuration**, not the values that
  were sent. The two differ whenever a setting is not reachable.

#### S2LP-DD-SIM — `simulator.py`

A register file with a radio attached, satisfying `Responder` (CORE-DD-MOCK).
Writing PCKTCTRL3 changes what the packet-format query answers; a strobe flushes
a FIFO; a packet queued on the simulated air is delivered to exactly one receive
and is then gone.

Two behaviours are modelled because they are the ones that mislead: a receive
that finds nothing answers with an error after its timeout rather than an empty
packet, and a packet arriving while the radio is not armed is counted and lost.
A write to a read-only register is accepted and discarded, as the hardware
discards it - which is what the driver's refusal (S2LP-FR-013) protects a test
from.

#### S2LP-DD-CLI — `cli.py`

Sub-commands `info`, `registers`, `radio`, `tx`, `rx`, `capture`, `strobe`,
emitting JSON (AD-15). `--log` and `--packet-log` open both logs at once. `rx`
with nothing on the air exits 1 and says why that is not the same as the air
being quiet; `capture` adds a warning when the capture was not continuous.

---

### 5.7 PSU — `benchtools.instruments.gpd3303d`

A GW Instek GPD-3303D: two programmable channels, 30 V and 3 A each, over
RS-232 or its USB-serial port. It answers `*IDN?` and nothing else from
IEEE 488.2, so the units below take the transport and lifecycle from
CORE-DD-SCPI and replace `*CLS`, `*RST` and the error queue with this supply's
own.

The supply's third output - the fixed 2.5 / 3.3 / 5 V rail - is outside the
element: it is selected by a front-panel switch that no command reaches, so
there is nothing about it a driver could set or measure.

#### PSU-DD-CONST — `constants.py`

Ratings, programming resolution, line rates, the status-word tables and the
CV/CC and tracking vocabularies. They are here so an out-of-range setting can be
refused *before* it is sent: this supply clamps rather than refusing, and a test
that asked for 35 V, was given 30 V and never told would report a pass against a
condition it never applied.

#### DMM-DD-CONST — `constants.py`

What the 1604 is, and what its protocol says: link settings, the handshake
states that power the interface, frame layout and field positions, the
seven-segment patterns, the key characters, and the published reading rate.
Each entry cites the source it came from.

The segment table is the load-bearing one. It is a bitmap, not a character
code, and the identifying relationship is that `8` is every segment (`0xFE`)
and `0` is that less the middle (`0xFC`). That relationship is what fixes bit 1
as the middle segment and bit 0 as the decimal point rather than a segment.

#### DMM-DD-PROTO — `protocol.py`

Pure decoding: ten bytes to a `Reading`. It knows nothing about serial ports,
because a wrong number originates here and this is the part that must be
testable without a meter, a port, or a simulator.

| Group | Members |
|---|---|
| Decoding | `decode`, `digits_text`, `unit_and_scale`, `find_frame_start` |
| Framing | `FrameAssembler.feed`, `.frames`, `.residue`, `.pending` |
| Result | `Reading`, `Reading.held` |

`FrameAssembler` exists because frames and command echoes share one direction
of one link. It separates them **by structure rather than by value**: complete
frames are extracted first, and whatever remains is echo. Searching the stream
for the echoed character instead would be wrong, and not rarely — `0x61` is
both the Up key and the seven-segment pattern for a `1` carrying its decimal
point, so an ordinary reading of 1.0 volts contains one.

`Reading.held` is deliberately a property over three separate annunciators —
Hold, Touch-Hold, and the Min-Max review. A caller should not have to know
which of the three froze the display in order to know that the number is not
this moment's.

#### DMM-DD-DMM — `dmm.py`

`Tti1604`, the driver façade.

| Group | Members |
|---|---|
| Lifecycle | `connect`, `_normalise_resource`, `_post_open`, `_read_identity`, `check_errors` |
| Keys | `press`, `_send_character`, `_await_echo`, `select_*` |
| Mode | `remote`, `local`, `is_remote` |
| Reading | `read`, `read_many`, `measure`, `_drain` |

`check_errors` is a documented no-op: the meter has no error queue, and a
driver that pretended otherwise would be inventing a clean bill of health.
`_post_open` enters remote mode and does nothing else — in particular it does
not press Operate, which toggles.

#### DMM-DD-SIM — `simulator.py`

A behavioural model rather than canned frames: front-panel state, key handling,
and frame encoding built from the same segment table the decoder reads, so the
two cannot disagree. It reproduces the two states in which a real meter is
silent — local mode, and Operate off — because both look like a dead link from
the far end and neither is a fault.

#### DMM-DD-CLI — `cli.py`

`benchtools dmm`. Reports `held` beside every value, and `--reject-held` turns
a frozen display into a non-zero exit. No `on` sub-command exists, because
Operate toggles.

#### PSU-DD-PSU — `psu.py`

`Gpd3303D`, and the two records it returns.

| Group | Members |
|---|---|
| Lifecycle | `connect`, `_normalise_resource`, `_post_open`, `_read_identity`, `reset` |
| Setting | `set_voltage`, `set_current_limit`, `configure_channel`, `_check_tracking` |
| Reading | `voltage_setpoint`, `current_limit`, `measure_voltage`, `measure_current`, `measure_power`, `read_channel`, `read_all`, `channel_mode` |
| Status | `status`, `read_event_queue`, `output`, `tracking` |
| Switching | `output_on`, `output_off`, `set_output`, `is_output_on`, `all_outputs_on`, `all_outputs_off` |

Design points:

- **`ChannelReading` carries the mode with the numbers.** A voltage reading
  alone cannot say whether the supply was holding the voltage it was asked for
  or holding a current limit instead, and those are different experiments.
  `regulated` answers the question a test usually means by "is it on": energised,
  in constant voltage, and at its setpoint.
- **Per-channel output is emulated** (AD-19). `_parked` maps a channel to the
  setpoint it was switched off at, and membership of that map *is* what parked
  means - deriving it from the supply's global switch as well would be two facts
  that can disagree. `output_off` programs the channel to zero and opens the
  real switch only when every channel is parked; `set_voltage` on a parked
  channel updates the parked value rather than the live one, so setting a
  voltage can never energise a rail as a side effect.
- **`_check_tracking` refuses what the supply would discard** (AD-21,
  PSU-FR-006). In series and parallel tracking the supply drives CH2 from CH1
  and silently discards anything sent to CH2, so `set_voltage`,
  `set_current_limit`, `output_on` and `output_off` raise for that channel,
  naming the mode. The mode is read at the moment of the write, not cached: it
  is a front-panel switch and can move between two commands. `all_outputs_on`,
  `all_outputs_off` and `reset` deliberately do not call it - they act on the
  supply's real switch and on CH1, and a safe state must be reachable in every
  mode. An undecodable mode warns and allows, so that one unconfirmed status
  bit cannot disable setting altogether.
- **The current limit is never parked.** It is the protection for whatever is
  connected, and it applies whether the channel is on or off. `reset` leaves the
  limits alone for the same reason: a reset that silently raised them would be
  the opposite of safe.
- **`configure_channel` sets the limit before the voltage**, so a channel coming
  up at a new voltage is never even briefly protected by the previous test's
  limit.
- **Commands are paced** on a real link (`_pace`, `DEFAULT_COMMAND_INTERVAL`).
  The supply has a small input buffer and no flow control; a command it drops is
  silent, and the next query answers perfectly well while the rail is not where
  the test believes it is. A simulated or loopback link is not paced - there is
  no buffer to overrun, and 50 ms a command would cost the suite minutes.
- **`_post_open` changes nothing.** Connecting to a supply that is powering a
  board must not disturb the board, so it identifies the supply, reads its
  status, and stops.
- **Error checking is off by default.** At 9600 baud a poll after every command
  doubles the time of a sweep, and the range checking that matters is done in
  the driver. `read_event_queue` uses `ERR?` and carries its text verbatim,
  because the exact wording is a bench confirmation item (PSU-OPEN-02).

#### PSU-DD-SIM — `simulator.py`

A supply *with a load on it*, which is what makes it worth having: a channel
whose load draws more than its limit falls into CC and its voltage drops, so a
driver that ignores the mode fails a test here rather than on the rig.

`SimulatedChannel.output()` is the whole of regulation in two branches - a
voltage source until the current it would have to deliver exceeds the limit,
then a current source at that limit with the voltage left to the load.

It is not built on CORE-DD-SIM: that class splits messages on `;` and on a
space, which is SCPI's grammar and not this supply's - `VSET1:3.300` is one
command, not a header and a sub-system. It models the single output switch, and
it **clamps** an out-of-range setting exactly as the hardware does, which is the
behaviour PSU-FR-002 exists to protect a test from. An unrecognised command is
met with silence, as the hardware meets it, so a driver that misspells one sees
a timeout in a test rather than only on the bench.

#### PSU-DD-CLI — `cli.py`

Sub-commands `info`, `read`, `set`, `on`, `off`, `status`, emitting JSON
(AD-15). Two deliberate choices, both about not damaging what is connected:
`set` programs a channel and does **not** energise it (`--on` does that,
explicitly), and `off` with a channel number reports in its output that the
channel is parked at zero volts rather than disconnected. `read` adds a
`warning` key when a channel it read is in current limit.

---

### 5.8 RUN — `benchtools.runner`

#### RUN-DD-SPEC — `spec.py`

The specification model: `TestSpec` → `TestCase` → `Step` → `Expectation`, all
frozen dataclasses built by `from_mapping` classmethods that validate as they go
and raise `SpecError` naming what to fix. `load_mapping` reads JSON with the
standard library and YAML when `pyyaml` is present. `TestSpec.instruments_used`
collects the aliases referenced anywhere, so the runner can verify the bench
before starting. `TestSpec` and `TestCase` set `__test__ = False`: their names
would otherwise make pytest try to collect them.

#### RUN-DD-LIMITS — `limits.py`

`Limit` supports `minimum`, `maximum`, `equals` with `tolerance` or
`tolerance_percent`, in any consistent combination, validated at construction.
`from_mapping` accepts `min`/`max`/`nominal` aliases because that is what reads
naturally in YAML, and ignores unknown keys because an expectation carries
name/unit/scale alongside them. `check()` returns a `LimitOutcome` carrying the
rendered limit text and, on failure, by how much the value missed. A `None` or NaN
value fails rather than passing.

#### RUN-DD-RESOLVE — `resolve.py`

Driver methods return whatever suits them: a float, a dataclass, a dict keyed by
channel, a tuple of records and a result object. `resolve_path` addresses into
that with a dotted path, trying each element as a mapping key (by string then by
int, because YAML gives keys as text while a channel-keyed dict uses ints), then a
sequence index, then an attribute, then a zero-argument method. This is the price
of AD-08 and is confined to this module.

#### RUN-DD-BENCH — `bench.py`

`InstrumentConfig` and `BenchConfig` model the bench; `Bench` holds the live
instruments. Drivers are selected from a registry by name (`register_driver`), so
a specification names data rather than code. Instruments connect on first use, so
a suite touching one instrument does not require the whole bench powered up, and
`close()` releases whatever was opened even after a failure. `require()` fails
fast when the bench lacks an alias the specification uses. `is_simulated` is true
when `--simulate` was given *or* every configured resource is a simulator, which
is what lets every report disclose it.

`describe_instruments()` asks every instrument the run actually opened what it
is - driver, model, serial number, resource, and the firmware build where the
instrument reports one - and is called *after* the run rather than before, so an
instrument the suite refreshed in setup is recorded as the one that produced the
measurements. It never opens an instrument to describe it: doing so would change
what the run did. An instrument that will not identify is recorded with an
`identity_error` rather than dropped, because silence about the bench is worse
than a recorded failure.

#### RUN-DD-RESULTS — `results.py`

`Status` (PASS/FAIL/ERROR/SKIP) with a `severity` ordering and a `worst()`
aggregator, so roll-up from measurement to step to case to run is one rule applied
at each level. `MeasurementRecord`, `StepRecord`, `CaseRecord` and `RunRecord` are
plain data with `as_dict()`; `RunRecord.requirements_verified` groups cases by
requirement and reports the worst outcome of each. `RunRecord.instruments` holds
what the bench said it was, keyed by alias (RUN-FR-037): a measurement without
the instrument that made it is not evidence, and for a programmable instrument
the firmware build decides whether the number means what it appears to mean.
Report writers read only these, so a new format needs no change to the engine.

#### RUN-DD-RUNNER — `runner.py`

`BenchRunner` resolves each step's `do:` to a bound method on a bench instrument —
rejecting private names, and on an unknown name listing what is available — calls
it, extracts the declared measurements and checks them. A `BenchToolsError`, a
`TypeError` from wrong arguments, or any other exception becomes an **error**; a
measurement outside its limit becomes a **failure**. Setup failures abort the
suite; teardown runs in a `finally`. `BUILTIN_ACTIONS` holds actions not bound to
an instrument (currently `sleep`, so a settling time is stated explicitly rather
than hidden in a driver).

A `do:` that names a **property** rather than a method is read when the step
runs, and rejects `with:` arguments (RUN-FR-036). Refusing properties would
force a driver to wrap `firmware_version` in a `get_firmware_version()` for the
runner's benefit, which is the tail wagging the dog; reading it at resolution
time would report the value from before the step rather than at it.

#### RUN-DD-REPORT — `report.py`

`write_json` (lossless), `format_markdown`/`write_markdown` (verdict, then
requirements, then problems, then all measurements; simulation disclosed), and
`write_junit` (a limit failure is `<failure>`, an execution error is `<error>`, the
requirement is the classname). `summary_line` gives a one-line console or commit
status.

The markdown report carries an **Instruments** table - alias, driver, model,
firmware, resource - from `RunRecord.instruments`, omitted when the run recorded
none. It sits with the verdict rather than in an appendix: whoever reads the
numbers needs to know, on the same page, which dongle and which firmware build
produced them.

#### RUN-DD-CLI — `cli.py` and `benchtools/cli.py`

`benchtools run` takes one or more specifications, a `--bench` or `--simulate`,
and report destinations; with several specifications the report paths are suffixed
so they do not overwrite. Exit status is 0 pass, 1 failure or error, 2 usage.
`benchtools/cli.py` dispatches `run`, `scope`, `drivers` and `backends` by name
rather than nesting argparse parsers, so each tool keeps its own complete
`--help`.

---

## 6. Review & Approval

| Role | Name | Signature / Electronic Approval | Date |
|---|---|---|---|
| Author | Claude | Approved | 2026-09-19 |
| Technical Reviewer | Dermot Murphy | — | *pending* |
| Quality Assurance | Dermot Murphy | — | *pending* |
| Approver | Dermot Murphy | — | *pending* |

> **Note:** This document is under configuration management (SUP.8). Post-approval changes require a change request (SUP.10) and a new document version.
