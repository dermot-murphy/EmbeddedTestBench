<img src="../../assets/brand/svg/logos/embeddedtestbench-logo-compact.svg" alt="Embedded Test Bench" width="240">

# Software Detailed Design

*Automotive SPICE® PAM v4.0 | SWE.3 Software Detailed Design and Unit Construction*

---

## 1. Document Identification & Control

| Field | Value | Field | Value |
|---|---|---|---|
| **Document ID** | ETB-SWE3-001 | **Version** | 1.20 |
| **Project** | Embedded Test Bench | **Date** | 2026-10-05 |
| **Status** | Draft | **Classification** | Internal |
| **Author** | Claude | **Reviewer** | Dermot Murphy |
| **Approver** | Dermot Murphy | **Related Process** | SWE.3 |

> **Note — Reviewer independence (ETB-DEV-002):** The Reviewer and Approver are the same person (Dermot Murphy). This is accepted under deviation record **ETB-DEV-002** (`docs/aspice/EmbeddedTestBench_DEV002_Independent_Review_Deviation.md`) on the basis that Embedded Test Bench has a single human team member.

---

## 2. Revision History

| Version | Date | Author | Description of Change |
|---|---|---|---|
| 0.1 | 2026-09-19 | Claude | Initial |
| 0.2 | 2026-09-23 | Claude | Design units added for the TTi 1604: DMM-DD-CONST, DMM-DD-PROTO, DMM-DD-DMM, DMM-DD-SIM, DMM-DD-CLI. |
| 0.3 | 2026-09-25 | Claude | BLE-DD-SCRIPT narrowed to reading, with variables, connect, timeouts and `<disconnect>`; BLE-DD-SCRIPTRUN added for running, results in priority order and the event log; BLE-DD-CMD gains the connect and reply timeouts, and BLE-DD-CMDARGS is added (#46, #48). |
| 0.4 | 2026-09-26 | Claude | CORE-DD-TRANSPORT gains the separate read terminator and CORE-DD-SERIAL the timeout guard (#61). PSU-DD-CONST, -PSU and -SIM describe the protocol as captured from a real supply, and the rejection of out-of-range settings (#61, #64). References TB-IF-001 and TB-SWE3-002 (#63). Header version brought into line with this history. |
| 0.5 | 2026-09-30 | Claude | Section 5.8 added: 14 PICO design units for the Pico 2 + SHT30-D thermometer and its firmware; RUN renumbered 5.9. Identifiers follow TB-STY-001 as checked by CStyleCheck (#104). |
| 0.6 | 2026-10-02 | Claude | #115: CORE-DD-TRANSPORT gains `read_available` and `discard_input`; CORE-DD-SERIAL and CORE-DD-MOCK extend `discard_input`, and the mock transport gives a virtual-clock simulator its timeout. DMM-DD-CONST, -PROTO, -DMM and -SIM revised for the stream read, frame validation, the derived resistance multiplier, confirmation from the readings, ranges, fresh measurement, the frequency gate and the simulator's reading rate. |
| 0.7 | 2026-10-02 | Claude | #116: CORE-DD-PATHS added - drivers declare which arguments are input files, and a relative one is found beside the file that names it, then in the working directory, then in the checkout. RUN-DD-BENCH resolves declared bench options; RUN-DD-RUNNER resolves declared step arguments. CORE count 16 → 17. |
| 0.8 | 2026-10-02 | Claude | #124: BLE-DD-CLI - `--select` resolves an address, a name or part of one through `select_by_name`, with an unfiltered rescan when the case-sensitive firmware filter hears nothing; `cmd --addr` selects; `--addr` and `--select` are mutually exclusive. |
| 0.9 | 2026-10-02 | Claude | #126: CORE-DD-EVENTS - event names per instrument (`EventSource`, `SourceLogger`, `connecting_as`, `validate_source_name`), upper-case defaults with `TEMP`; CORE-DD-INSTRUMENT - `EVENT_SOURCE`, `event_source`, `_adopt`; RUN-DD-SPEC, RUN-DD-BENCH and RUN-DD-REPORT - names from the specification and the bench. |
| 1.0 | 2026-10-03 | Claude | #127: PICO-DD-FLASH added - `Uf2Image`, the operating-system seams (drive discovery per system, the 1200-baud touch, the copy), `PicoFlasher` and the simulated board `SimulatedRp2350`. PICO-DD-CLI gains the `flash` sub-command, run without connecting first; PICO-DD-SIM gains the `on_bootloader` hook. PICO count 14 → 15. PICO-DD-FLASH: `touch_1200()` returns an error from the port as a note instead of raising, found on a real Pico 2 on Windows, and the 1200-baud reset is recorded as confirmed on hardware (PICO-OPEN-05). |
| 1.1 | 2026-10-03 | Claude | #131: the Pico thermometer's `rd` command set. PICO-DD-PROTOCOL (`rd` replies, `ecureset`, `PROTO_VERSION` 2.0), PICO-DD-VERSION (name, copyright, `V1.00.0000`, the injected commit SHA), PICO-DD-TEXT (`text_centi`), PICO-DD-PARSER (`cmd_rd`, handlers write the whole reply), PICO-DD-MAIN, PICO-DD-BUILD (SHA injection and re-configure on a new commit), PICO-DD-TEST, PICO-DD-CONST, PICO-DD-DRIVER (`rd`, `NoReadingError`, `RdRefusedError`; the raw-word cross-check removed), PICO-DD-SIM and PICO-DD-CLI (`info`, `rd`, `ecureset`) revised. With #127 merged, PICO-DD-FLASH revised to confirm the new build by `rd`: `Uf2Image` reads the firmware name, the version and the commit SHA from the image in place of the title and the build date, the checks are `name`, `version` and `sha`, `--expect-version` takes `VX.YY.ZZZZ`, and `SimulatedRp2350` takes the image's version and SHA. |
| 1.2 | 2026-10-03 | Claude | #134: RUN-DD-RUNNER - `run(spec, selection)`, `NOT_SELECTED` and `check_selection`; RUN-DD-RESULTS `RunRecord.selection`; RUN-DD-CLI `--test`. |
| 1.3 | 2026-10-03 | Claude | #135: CORE-DD-EVENTS - `log_event`, `jsonable`, `MAX_ITEMS`, and the `kind` and `data` fields; RUN-DD-RUNNER - the structured run, test case and step records. |
| 1.4 | 2026-10-03 | Claude | #136: RUN-DD-CONTROL added - `RunControl`, `Command`, `ControlServer`; RUN-DD-RUNNER obeys it between steps (`_run_tests`, `_restart`, `_restart_refusal`, `_Interrupted`); RUN-DD-CLI `--control`. |
| 1.5 | 2026-10-03 | Claude | #137: §5.10 VIEW added - VIEW-DD-STATE, VIEW-DD-SERVER and VIEW-DD-PAGE, the test run viewer. |
| 1.6 | 2026-10-03 | Claude | #138: VIEW-DD-TRAFFIC added - `classify`, `Traffic`, `PsuPanel`, `JlinkPanel`, `panel_for`, `Hub.instruments`, `/api/instruments`; VIEW-DD-PAGE gains the Instruments tab and a step's traffic. |
| 1.7 | 2026-10-03 | Claude | #139: S2LP-DD-S2LP `_record` logs `rf_packet`; VIEW-DD-RADIO added (`RfFrames`, `BleAir`, `parse_fields`, `/api/radio`, `/api/ble`); VIEW-DD-PAGE gains the RF and BLE tabs. |
| 1.8 | 2026-10-03 | Claude | #140: CORE-DD-EVENTS `log_reading`; PSU-DD-PSU, PICO-DD-DRIVER and DMM-DD-DMM log readings; VIEW-DD-GRAPHS added (`Readings`, `advertising`, `step_markers`, `/api/graphs`, `graphs.js`); the GET API is a table of handlers (`_GET_API`). |
| 1.9 | 2026-10-03 | Claude | #148: VIEW-DD-TAGS added (`Tagger`, `sensor_of`); VIEW-DD-PAGE's Event log tab gains pause and resume and its filters. |
| 1.10 | 2026-10-03 | Claude | #149: VIEW-DD-STATUS added (`InstrumentStatus`, `progress`, `_expected`, `/api/status`, `status.js`). |
| 1.11 | 2026-10-03 | Claude | #141: VIEW-DD-SERVER - access token, sign-in cookie, read-only, HTTPS, `_POST_API`. |
| 1.12 | 2026-10-03 | Claude | #151: S2LP-DD-KEPLER - the decoder checked against the sensor firmware point by point; RESPONSE corrected; `kepler_tables.py` added. |
| 1.13 | 2026-10-03 | Claude | #152: VIEW-DD-KEPLER added (`KeplerView`, `byte_roles`, `header_rows`, `payload_rows`, `CONFIG_GROUPS`, `/api/kepler`, `kepler.js`). |
| 1.14 | 2026-10-03 | Claude | #153: VIEW-DD-SENSOR added (`SensorSeries`, `to_mg`, `to_mm_s`, `/api/sensor`); `lineChart` takes its container and shows raw counts; RF sub-tabs Environment, Short Interval and Ticks. |
| 1.15 | 2026-10-03 | Claude | #154: VIEW-DD-TWF added (`TwfAssembler`, `spectrum`, `fill_gaps`, `/api/twf`); `lineChart` breaks at nulls, clips to its span, and labels ms or Hz. |
| 1.16 | 2026-10-03 | Claude | #155: VIEW-DD-DIAG added (`Diagnostics`, `SyncTracker`, `/api/diagnostics`, `/api/diagnostics/reset`). |
| 1.17 | 2026-10-03 | Claude | #156: VIEW-DD-REPORT added (`NotesStore`, `build_report`, `svg_chart`, `/api/notes`, `/api/report`, `notes.js`); VIEW-DD-SENSOR sorts its points by time. |
| 1.18 | 2026-10-03 | Claude | #157: S2LP-DD-S2LP `read_setup`; RUN-DD-CONTROL `READ_SETUP`; VIEW-DD-STGUI added (`StGui`, `rf_setup_rows`, `register_rows`, `regs_text`, `st_row`). |
| 1.19 | 2026-10-04 | Claude | #183: product renamed to Embedded Test Bench - document file name prefix `EmbeddedTestBench_`, identifier prefix `ETB-` (was `TB-`), product name in prose. Earlier revision rows keep the names in use when they were written. |
| 1.20 | 2026-10-05 | Claude | #194: the compact brand logo added above the title, the same line in every controlled document (ETB-SUP8-001 §6.3). |

---

## 3. Purpose & Scope

### 3.1 Purpose

This document describes the detailed design of every software unit of
**Embedded Test Bench**: what each unit is, what it holds, and - where the reason is not
obvious from the code - why it is built the way it is. It refines ETB-SWE2-001
and is the basis for unit verification (ETB-SWE4-001).

This document satisfies **Automotive SPICE® PAM v4.0, SWE.3 — Software Detailed
Design and Unit Construction**.

### 3.2 Referenced Documents

| Document ID | Title | Version |
|---|---|---|
| ETB-SWE1-001 | Embedded Test Bench Software Requirements Specification | 0.1 |
| ETB-SWE2-001 | Embedded Test Bench Software Architecture Description | 0.1 |
| ETB-SWE4-001 | Embedded Test Bench Software Unit Verification Specification | 0.2 |
| ETB-RTM-001 | Embedded Test Bench Requirements Traceability Matrix | 0.6 |
| ETB-IF-001 | GPD-3303D Remote Control Interface Specification | 0.1 |
| ETB-SWE3-002 | GPD-3303D Driver Design and Lessons Learned | 0.1 |

### 3.3 Unit Identification

Each unit is named `<ELEMENT>-DD-<NAME>` and is cited from the module docstring
of the source file that implements it. The citation is checked mechanically:
`tests/test_traceability.py` fails if a module cites a unit this document does
not declare.

---

## 4. Unit Catalogue

| # | Element | Package | Design units |
|---|---|---|---|
| 5.1 | CORE | `benchtools.core` | 17 |
| 5.2 | ANA | `benchtools.analysis` | 4 |
| 5.3 | INST | `benchtools.instruments` | 5 |
| 5.4 | JLINK | `benchtools.instruments.jlink` | 10 |
| 5.5 | BLE | `benchtools.instruments.nordic_dongle` and `firmware/nordic_dongle` | 20 |
| 5.6 | S2LP | `benchtools.instruments.s2lp` | 13 |
| 5.7 | PSU | `benchtools.instruments.gpd3303d` | 4 |
| 5.8 | PICO | `benchtools.instruments.pico_sht30` and `firmware/pico_sht30` | 15 |
| 5.9 | RUN | `benchtools.runner` | 8 |
| | **Total** | | **76** |

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
| `read_message()` | To the read terminator, or to end-of-message | Ordinary SCPI query responses |
| `read_exactly(n)` | Exactly *n* bytes, terminator-transparent | IEEE 488.2 block payloads |
| `read_raw()` | Everything to end-of-message | Images and other unframed transfers |
| `read_available()` | Whatever has arrived; waits only if nothing has | Instruments that stream without being asked (CORE-FR-061) |
| `discard_input()` | Drops everything received and unread, and counts it | A fresh reading from a streaming instrument (CORE-FR-061) |

Design points:

- `write()` discards unread buffered bytes first. Without this, a stale response
  would be returned as the answer to the next query — a failure mode producing
  plausible wrong data rather than an error.
- `read_message()` breaks out of the fill loop as soon as a terminator is visible,
  so an already-buffered response costs no extra round trip.
- `MAX_RESPONSE_BYTES` (64 MiB) bounds a runaway read if an instrument never
  asserts end-of-message.
- The terminator appended to commands and the one that ends a response are
  separate (`read_terminator`, defaulting to the same bytes). The GPD-3303D
  takes LF and replies with CR alone (ETB-IF-001 §5), and an instrument driver
  that knows its instrument sets the read terminator itself.
- Context-manager support guarantees the link is released on an exception path.
- `read_raw()` reads until end-of-message, which a serial port never signals: on
  one it can only time out, leaving what did arrive in the buffer. That is
  #115. `read_available()` is the stream primitive instead; it clears a previous
  end-of-message before asking the link again, because for a stream that says
  nothing about whether another byte is coming.
- `discard_input()` is the base of a chain: the base empties its buffer, the
  serial transport also empties the operating system's, the mock transport
  also drops its pending reply. Each returns how many bytes it dropped.

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

#### CORE-DD-PATHS — `paths.py`

`input_paths`, `input_path_names`, `resolve_input_path`, `resolve_arguments`,
`search_locations`, `TESTTOOLS_ROOT`. How an input file named by a relative path
is found wherever the tools are started from (RUN-FR-007, RUN-FR-017, #116).

Design points:

- **The driver declares; the runner resolves.** `@input_paths("source")` marks
  the arguments of a driver method that name a file the driver will read. Only
  the driver knows that `source` on the S2-LP is a register file while `source`
  on the oscilloscope is a channel, so guessing from an argument's name or value
  would be wrong somewhere. Only the runner knows which file named the path, so
  the search is the runner's. The mark is a function attribute, applied beneath
  `@classmethod`/`@staticmethod`, and is read through bound and class access
  alike.
- **Search order: the declaring file's directory, the working directory, the
  checkout.** The declaring file comes first so a specification or bench file
  means the same thing wherever it is run from. The working directory comes
  before the checkout so a bench file naming the firmware repository's own
  `build/` (`benches/lab1.yaml`) keeps finding it there; the checkout comes last
  so the shipped `configs/` and `benches/simulated/` are found from anywhere.
  This differs from the order first proposed in #116 (checkout before working
  directory) for that reason. Duplicate locations are searched once.
- **An absolute path, and anything not a string, is passed through.** An
  absolute path already means one thing, and whether it exists is the driver's
  to report. A `RegisterConfiguration`, `CommandScript` or `FirmwareBuild` handed
  over from Python is not a path at all.
- **Not found: an error naming every location, or the driver's call.** With
  `required=True` (step arguments) a `ConfigurationError` lists each location
  searched. With `required=False` (bench options) the value is passed on
  unchanged, because a simulator may never read it - the simulated probe skips
  its ELF check - and the driver that does read it reports what is missing.
- **Output paths are not declared.** A log, a report or a screenshot is written
  relative to the working directory, as before.
- **`TESTTOOLS_ROOT` is the directory above the package.** Installed as a package
  rather than run from a checkout, nothing is found there and the search simply
  ends with the working directory.

Drivers that declare input files: `JLinkProbe.connect` (`elf`, `firmware`),
`load_symbols`, `flash`, `image_build`, `verify`; `JLinkRttReader.connect`;
`NordicDongle.connect`, `expect_firmware`, `check_firmware`, `update_firmware`,
`ensure_firmware` (`firmware`), `run_script` (`source`); `S2lpDevkit.load_configuration`,
`apply_configuration`, `verify_configuration` (`source`). The GPD-3303D, the
TTi 1604, the TDS3014B and the Pico SHT30 read no input file.

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
- **pyserial's timeout is assigned only when it has changed.** pyserial
  reconfigures the port on every assignment, and on Windows that loses bytes
  in flight: assigning it before every read lost about one GPD-3303D reply in
  five (ETB-IF-001 §10.2, ETB-SWE3-002 LL-07).
- `discard_input()` extends the base with `reset_input_buffer()`, because the
  bytes a streaming instrument sent while nobody was reading are in the
  operating system, not in the transport.

#### CORE-DD-MOCK — `transport/mock.py`

Loopback transport accepting any `Responder` — anything with
`respond(bytes) -> bytes | None`. It has no knowledge of which instrument is
simulated. Responses are returned in small chunks so that framing and
reassembly are exercised rather than bypassed. The description is derived from
the responder's `*IDN?` model field, so it is meaningful for any instrument.

A responder that implements `poll_within(timeout)` is called with this
transport's timeout instead of `poll()` (CORE-FR-062): output due later than the
read would wait is a `TransportTimeoutError`, and the simulator's clock moves on
by the timeout, as time does on a real port. Without it a simulator on a
virtual clock delivers data a driver would have given up on, and a wait that is
too short passes every test. `discard_input()` also drops the pending reply.

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

`EVENT_SOURCE` is each driver's default event-log name, and `event_source` the
instrument's current one, held in an `EventSource` created at construction -
from `connecting_as` if the bench is connecting it, else from `EVENT_SOURCE`.
`_logger` is the instrument's `SourceLogger`, under its own module's logger;
`_adopt(*owned)` binds what it owns - transport, session, RTT client, GDB
Server, ITM decoder - to the same name (CORE-FR-063). `Transport` gives every
link a `_logger` under its own module, and `ScpiInstrument` adopts its transport
and logs its I/O through `_io_log`, which is now that logger.


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

#### CORE-DD-EVENTS — `events.py`

One event log for a run, followed live by the Embedded Test Bench monitor (#82). Every
driver already reports its I/O and the runner its steps through `logging`;
`EventLogHandler` writes each `benchtools` record as one JSON object per line -
host time, source, level, logger, text - flushed per record. `start_event_log`
attaches it, and first pins any console handler to the root level, so lowering
the package's level for the log does not flood the console. `EventTail` follows
a growing log, leaving a partial last line for the next read. `benchtools run
--event-log PATH` writes the log for a run.

The **source** is the short upper-case name of the instrument a record came
from (CORE-FR-060, CORE-FR-063, AD-28, #126):

- `EventSource` holds one instrument's name; `validate_source_name` enforces
  1-8 characters, `[A-Z][A-Z0-9_]*`. It is mutable, so a rename reaches every
  logger already bound to it.
- `SourceLogger`, a `LoggerAdapter`, adds the bound name to each record as
  `event_source`. An instrument and everything it owns log through one.
- `connecting_as(name)` sets a per-thread pending name while the bench builds an
  instrument. An `Instrument` or `SourceLogger` created inside it takes the name
  from the start, and the handler gives it to records logged meanwhile by
  module-level code (the transport factory), so connecting is named too.
- The handler's order: the record's `event_source`, else the pending name, else
  `source_of` the logger name - the driver defaults `PSU`, `BLE`, `JLINK`, `RF`,
  `SCOPE`, `DMM`, `TEMP` (`pico_sht30`), `TEST` (the runner), and `BENCH` for
  anything else.

`log_event(logger, kind, text, data)` logs *text* as usual and attaches `kind`
and `data` to the record; the handler writes them as two more fields, after
`jsonable` has made `data` standard JSON: dataclasses, mappings and sequences
converted item by item, bytes as hex, an enum as its value, a non-finite float
as text (a browser's `JSON.parse` refuses `NaN`), a sequence longer than
`MAX_ITEMS` (256) cut short with a note, anything else as its `repr`
(CORE-FR-064, #135). A console handler sees only the text.

---

`log_reading(logger, quantity, value, unit, **detail)` logs a `reading` record through `log_event` at DEBUG, with the detail - channel, AC, display text - beside quantity, value and unit (CORE-FR-065, #140).

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

#### ANA-DD-SAMPLES — `samples.py`

`SampleSet` holds repeated readings of one quantity - the values, what each
was read from (a reply, a log line, a frame) and when - with `count`,
`complete`, `minimum`, `maximum`, `mean` and `spread` as properties, so a
specification can bound the spread and compare one source's mean with
another's. A set that got fewer readings than it asked for is returned, not
raised: a sensor that went quiet is a result, and `count` is the limit that
fails. Statistics are `None` only for an empty set. `extract_number` takes the
number from a pattern's first group and refuses a pattern with no group. The
dongle, the probe and the S2-LP each fill one (#95).

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
- An unnamed tuple among the results is accepted and its fields merged in. GDB's
  own `load` emits one - `+download,{section=".sec1",...}` - and rejecting it
  abandoned a flash half-way (issue #69).
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
  (`JLinkGDBServerCL.exe`, `JLinkGDBServer.exe`) then the Unix ones, on `PATH`
  and then in the SEGGER install directories (`SEGGER/JLink*`), newest release
  first; the diagnostic names the tool and where SEGGER installs it.
- `find_gdb` accepts `arm-none-eabi-gdb` or `gdb-multiarch` on `PATH`, then one in
  the Arm GNU Toolchain install directories, and a plain `gdb` only if
  `gdb_debugs_arm` says it can: MinGW's `gdb` is i386-only, and picking it failed
  later at attach with an error that did not name the cause (issue #69).
- `port_is_open` is checked **before** spawning: a server already listening is used,
  never duplicated — a second server on the same probe fails in a way that reads
  like a hardware fault.
- The server is spawned only for a local target (AD-13); for a remote one the driver
  attaches and says so.
- `was_spawned` gates `stop()`: a server the driver did not start is a server it must
  not kill (JLINK-FR-005).
- Flags: `-nogui -strict`. `-strict` so a bad device name fails at start rather
  than producing a half-working link. `-singlerun` was used, and removed: it makes
  the server exit when its first client disconnects, and the first client is
  `start()`'s own readiness check, so GDB found nothing listening (issue #69).
  `stop()` ends the server instead. `-silent` was removed too, so the start-up
  banner is printed.
- The server's output is drained by a reader thread, keeping the last lines for a
  start-up diagnostic and the banner for `probe_identity()`, which returns the
  probe's serial number, firmware and hardware. An undrained pipe fills and blocks
  the server on its next write.

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
- **`close` resumes the core unless `leave_halted` is set** (JLINK-FR-006). The
  GDB Server halts the core on attach, and `-target-detach` leaves it halted:
  observed on an nRF52840 with J-Link V9.42 as DHCSR `0x00030003` and a sensor
  that stopped advertising until reset. `close` therefore sends `monitor go`
  before detaching.
- **`flash(path)` loads the file by name, then reads it as the executable** for
  `verify`. GDB 15.2 on Windows exited with status 3 after `file` then `load` of
  an Intel HEX file on a mapped drive ("has changed; re-reading symbols");
  `load <file>` first did not. ELF and Intel HEX both work, and HEX images are
  verified section by section like ELF ones.
- **`flash(preserve=...)` keeps named ranges.** Flashing an nRF52840 image whose
  HEX holds a UICR record erased the whole UICR page, including a sensor ID at
  `0x10001080` the image did not contain. Each preserved range is read after the
  reset, written back after programming and verification if it changed, and
  read again; a range that will not stick raises.
- **Structures are parsed before strings.** `_parse_gdb_value` recognises
  `{name = value, ...}` first and splits it at top-level commas outside quotes and
  nested braces (`_split_fields`); before, a structure holding a `char *` came
  back as that pointer's string.
- **`erase` resets and halts first, then checks.** On an nRF52840 running its
  firmware, `monitor flash erase` reported "Flash erase: O.K." and erased
  nothing; from reset with the core halted it erased flash and UICR. The word at
  `blank_check_address` (default 0) must then read `0xFFFFFFFF`, or `erase`
  raises.
- **`rtt_start` does not require `monitor rtt start`.** J-Link GDB Server V9.42
  rejects it and serves RTT channel 0 on its RTT port unasked, so the command is
  sent but an error is ignored.
- **Identity falls back to the server banner.** J-Link GDB Server V9 answers
  `monitor version` with "Unsupported remote command"; when that yields nothing,
  `_read_identity` uses `GdbServer.probe_identity()` of a server the driver
  started. For a server it only attached to, the identity says no version was
  reported rather than guessing.
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
- `connect(attach=False)` reads RTT without ever stopping the target: the GDB
  Server is started with `-nohalt`, `_post_open` does not attach, and `rtt_start`
  sends no `monitor rtt start` (V9.42 serves RTT unasked). A GDB attach halts the
  core even with `-nohalt`; on 5C1712 that dropped the BLE link and the
  SoftDevice then faulted (#95). `JLinkRttReader` is the same class with
  `attach=False` forced, registered as driver `jlink-rtt`, so a specification
  that needs it is refused a bench offering an ordinary `jlink`.
- `rtt_samples` takes a number from each of the next N matching RTT lines,
  discarding lines already buffered - they were logged before the test asked.

#### JLINK-DD-CLI — `jlink/cli.py`

Sub-commands `info`, `flash`, `verify`, `erase`, `reset`, `run`, `halt`, `read`,
`write`, `var`, `stack`, `rtt`, `time`, emitting JSON (AD-15). `halt`, `reset`
without `--run`, and `run --until` set `leave_halted`, since a halted core is their
purpose; every other sub-command leaves the target running (JLINK-FR-006). The `time` sub-command adds a
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

`ResponseSample.value` is what a reply reports: the text after its first
` = `, trimmed (#102). A specification compares it with the same value from
elsewhere - a VERSION frame's SHA against `RD SHA` - where the rest of the
reply is not carried.

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
- `sample_command` sends one command N times, each start an interval after the
  last, and takes a number from each reply into a `SampleSet`. A reply without
  a number raises, naming it: a `NACK` is not a reading to average in.

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

`select` and `--select` go through one helper, `_choose` (BLE-FR-071). An
address is selected as given. Anything else is a name or part of one: a scan
with the firmware's name filter first, then - if that heard no name containing
the target, ignoring case, because the filter is case-sensitive - an unfiltered
scan, and `select_by_name` chooses the strongest match (BLE-FR-026). The
driver's `select()` is unchanged: it matches a name exactly, and a
specification names its sensor by address. `--addr` and `--select` are an
argparse mutually exclusive group on `profile`, `cmd` and `monitor`, so giving
both exits 2; `cmd --addr` selects the address before connecting, where it was
previously ignored (#124).

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
firmware error. `parse_reply` collects the reply's brace-delimited tags and keeps
every line verbatim. The reply shapes are the ones a kit sent (2026-09-27, #76):
the command named in parentheses, `{{(Name)} API call...`, and most getters
answering in a tag called `value`.

Details that bite:

- **How a value is written depends on the command, not on the value.** ST's
  `&tx`/`&t2x`/`&t4x` print bare hex, `&td` signed decimal, and one command a
  `%.1f` float. The caller chooses `Reply.hex_number`, `Reply.number` or
  `Reply.real`, because `{value:70}` is 0x70 from one command and seventy from
  another. Read as decimal, an RSSI register of `D4` is 4 - wrong by 104 dB.
- **Signs are kept.** `S2LPQiGetRssidBm` answers `-116.0`; dropping the sign
  gives an impossible +116 dBm that nothing downstream would question. The
  power setting is signed too, although ST's table declares it `w`, so this
  module adds its own letter `i` for a signed argument.
- **`FIRMWARE_ERRORS`** lists the interpreter's own error lines (`no such
  command`, `wrong number of arguments`, ...), sent instead of a reply.

#### S2LP-DD-SESSION — `session.py`

Commands out, replies in, every line logged.

- **Where a reply ends** is decided by counting braces, because the firmware
  closes some replies on the first line and others five lines later. Waiting for
  a fixed number of lines would truncate half the command set. The command's
  echo and the `>` prompt are not part of a reply; an echo that ran into the
  reply on one line (seen with `SdkEvalRfboardIdentification`) is split off at
  the reply's `{{`.
- **An interpreter error fails at once**, as a `ProtocolError` naming the
  command, rather than as a timeout.
- **`execute` takes only its own command's reply.** A send interrupted by a stop
  acknowledges *after* the stop does; that stale reply is skipped and kept in
  `unclaimed` rather than taken as the next command's answer.
- **The port timeout is set once**, to `READ_POLL`, and never changed per read.
  Changing it reconfigures a serial port, and on Windows that lost bytes from
  replies - the same fault as #61 on the GPD-3303D.
- **`stop()` sends a single `S`**, with no terminator: ST's firmware polls the
  port for that character inside its loops. Sent to an idle board it sits in
  the command buffer and spoils the next command, so `stop()` waits for the
  `StopCmd` acknowledgement and, when none comes, ends the line and swallows the
  `no such command` it produces. The write keeps any half-read reply in the
  transport buffer (`Transport.write(keep_buffer=True)`).
- `collect()` yields replies as they arrive, so a caller can log each packet as
  it lands; a batch cut short returns what arrived rather than raising, because
  a truncated capture is a fact the caller needs.
- The **raw session log** is written here: every line, both directions,
  host-timestamped, flushed per line.

#### S2LP-DD-PACKETS — `packets.py`

`Packet` (direction, payload, RSSI, both clocks, error, the firmware's extra
fields), `Capture` (the packets, the rejected receptions, and how they were
taken), `PacketLog` (JSON Lines, one object per line), `BoardClock`, and
`packet_from_reply`, which turns one receive report into a packet.

The design point is `Capture.gaps`. The radio is re-armed after every packet -
by the host in a polled capture, and by ST's own loop in a batch capture - and a
packet arriving while it is re-armed is not lost so much as *invisible*. A
capture records how many times it re-armed and who did it (`rearm`), and
`is_continuous` is true only when it never did, so "nothing was transmitted" and
"we were not listening" stay distinguishable. A count of what was missed is not
available from this hardware path, and this package does not invent one.

**Board time is in microseconds** (measured: 2,041,139 counts in 2,043 ms), and
the 32-bit counter wraps every 71.6 minutes; `BoardClock` unwraps it by counting
a smaller reading as one wrap.

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
| Radio | `configure_radio`, `radio_info`, `frequency_hz`, `set_frequency`, `modulation`, `set_modulation`, `power_dbm`, `power_level_dbm`, `set_power_dbm`, `rssi_dbm`, `configure_packets`, `packet_info`, `payload_length`, `set_payload_length` |
| Traffic | from S2LP-DD-TRAFFIC: `prepare_traffic`, `transmit`, `transmit_batch`, `receive`, `capture`, `stop` |
| Logging | `start_log`, `start_packet_log`, `log_note`, `log_path`, `packet_log_path`; `_record` writes every packet as an `rf_packet` event record (S2LP-FR-080); `read_setup` reads `radio_info`, `read_all_registers`, the power at `PA_LEVEL_MAX_IDX` and the EEPROM and logs them as one `rf_setup` record (S2LP-FR-084) |

Design points:

- **`_post_open` identifies and configures nothing.** Connecting must not retune
  a radio somebody left set up.
- **The board is the caller's to name.** ST's firmware never reports it
  (`SdkEvalRfboardIdentification` answers with no tags), so no board is
  assumed. A named board's band is enforced: the radio would accept a frequency
  outside it and transmit into a filter and matching network that do not pass
  it. Without a board, only the synthesiser's own ranges are checked.
- **Reset checks cover writable registers only.** Status registers are never at
  a "reset value" on a live radio. A power reset through ST's firmware lands at
  the defaults with ten registers set (`AFTER_SHUTDOWN_EXIT`), and is checked
  against that.
- **`write_field` reads, modifies and writes**, so the other fields of the
  register keep their values. Writing a field's value to the whole register is
  the mistake this method exists to prevent.
- **A register read is checked against the addresses that came back.** The
  firmware interleaves address and value; if the addresses are not the ones asked
  for, neither are the values.
- **Verification is `radio_info()` after configuration**, not the values that
  were sent. The two differ whenever a setting is not reachable.

#### S2LP-DD-TRAFFIC — `traffic.py`

`TrafficMixin`: send, receive and capture, split from S2LP-DD-S2LP so that each
can be read on its own. It relies on the driver's session, clock, packet log and
register access. Three facts found on a kit (#76) shape it:

- **The radio's interrupt has to be routed.** ST's send and receive wait for an
  interrupt that, out of reset, reaches nothing. `prepare_traffic` puts nIRQ on
  S2-LP GPIO3 (GPIO_MODE 2, output; the CLI's help numbers the modes one lower,
  which makes the pin an input), unmasks the interrupts the firmware waits for,
  enables the board's input, and confirms the board reads the line high. It
  runs once per session, on the first send or receive, not on connecting.
- **The TX source has to be the FIFO.** PCKTCTRL1.TXSOURCE powers up as 3, a PN9
  test pattern that the radio sends indefinitely. A send is refused until it is
  0 (`configure_packets`, or a register file).
- **PCKTLEN has to match the payload.** Given fewer bytes the radio waits in TX
  for the rest, so a send sets the length first when it differs.

Every wait is the host's, because the firmware's are unbounded: a receive that
times out is stopped on the board, and a send that never completes is stopped
and the radio aborted before the error is raised. A batch capture switches
`S2LPGetNBytesReportAll` on, so ST's loop re-arms the radio before printing each
report rather than after, and keeps rejected receptions (CRC, address filter)
apart from packets.

**Streaming** (`stream`) has two modes (#87).

* **`batch`, the default.** It starts ST's receive loop once
  (`S2LPGetNBytesBatch 0 <count or 0xFFFFFFFF>`), as ST's own GUI does, with
  `S2LPGetNBytesReportAll` on so the board re-arms before printing each
  report. It then decodes, records and yields each report as it arrives. No
  host round trip falls between frames.
* **`polled`.** It receives one frame at a time with `S2LPGetNBytes` asking for
  0xFFFF bytes, which ST's firmware takes as "one packet, whatever its length".
  It then reads the chosen registers in one command (by default 0x9E-0xA2:
  AFC correction, PQI, carrier sense with SQI, RSSI). The host re-arms after
  each frame, and gaps under about 105 ms were missed on the bench.

Before the first receive of a session, `prepare_receive` sets receiving up as
ST's GUI does - an infinite RX timeout (`S2LPTimerSetRxTimeoutUs 0`) and
low-power receive off - read from the kit while the GUI was receiving.
Asking for registers in batch mode is refused, because the loop cannot read
them. Both modes stop the board however the stream ends, including when the
caller stops iterating (the batch generator's `finally`). With a count, the
loop's closing reply is read before the last frame is handed over, so a caller
that stops there leaves nothing running. An `until` callable ends a stream
from another thread, by cancelling the wait in the session (`ReadCancelled`).

`kepler_samples` takes a decoded field from the next N Kepler transmissions of
a given sensor and frame type. Copies of one transmission are recognised by
their repeat number, which the decoder reads from wherever the type keeps it -
byte 8, or byte 9 in TWF and CONFIG, whose permute control byte is at 8 - and a
copy whose repeat number is not higher than the last one's starts a new
transmission. Bytes cannot be compared instead: 5C1712 clears ALIVE_STATUS's
"SI updated" bit after the first copy (#95).

`kepler_frame` returns the whole decode of the next frame of a given type from
a given sensor, with its payload as `raw`, for a frame whose fields are text or
are compared with each other (#102). The first copy heard is taken: the copies
of one transmission carry the same fields. No frame within the timeout raises
`MeasurementError`, since the specification waiting on it has nothing to check.

#### S2LP-DD-EEPROM — `eeprom.py`

The RF board's identification EEPROM (#80), read through ST's
`EepromReadPage`, which its CLI's `help` hides. Page 0 holds, per ST's
middleware: byte 0 programmed (not 0x00/0xFF), byte 1 the crystal code, byte
3 the band code (0 169, 1 315, 2 433, 3 868, 4 915, 5 450 MHz). The bench kit
reads `03 04 09 02 ...`: a 50 MHz crystal and the 433 MHz band.

In S2LP-DD-S2LP, `_read_identity` reads page 0 at connection (a read; nothing
is configured). `band` is the named board's range, or else the EEPROM's; a
named board whose range differs from the EEPROM's band is refused with a
`ConfigurationError`, so a bench file naming the wrong board fails at connect
rather than tuning into a filter that does not pass it.

#### S2LP-DD-PREAMBLE — `preamble.py`

A transmitter's preamble length, measured from PQI (#89). PQI (LINK_QUALIF2)
reads 0 unless the radio's PQI check is on (QI.PQI_TH > 0). With the check on
it counts the preamble heard: 2 x pairs - 1, up to the 8-bit ceiling of 255.
Measured on the kit against sensor 5C1712 at 32, 48 and 128 pairs.

`PreambleMeasurement` holds one source's PQI readings; the measurement is the
maximum, because a frame caught part-way reads low. `check_preamble` compares
it with a configured length and returns `pass`, `fail` (longer than set, or
shorter beyond the tolerance) or `unmeasurable` (no frame, or an expected
value at or past the ceiling, where every longer preamble reads the same).

In S2LP-DD-TRAFFIC, a polled stream that reads PQI switches the PQI check on
if it is off and puts QI back when the stream ends (`_enable_pqi`), so a 0
cannot pass for a result. `measure_preamble` and `check_preamble` receive in
polled mode and attribute frames by the decoder's sensor ID.

#### S2LP-DD-KEPLER — `kepler.py`

`decode_kepler_frame` turns a Kepler sensor payload into a dictionary: the
common header, then the fields of its PL_TYPE (VERSION, ALIVE and
INSTALL_ASSIST, TWF, CONFIG, FFT, FFT2, CMD, RESPONSE). Offsets and encodings are
the sensor firmware's (`api_radio_transport_cfg.h`, `api_radio_field.c`).
Units are converted only where the firmware defines them - temperature in
0.1 °C, battery in 20 mV steps - and permuted contents are reported as sent. A
payload too short for its type, or of an unknown type, raises
`KeplerFrameError`; a longer one, or one with another RF_CAP, is decoded with a
warning. Checked against frames from sensor 5C1712 received on the kit.

**Checked against the firmware (#151).** The Kepler project's rf_monitor and
this decoder disagreed; the sensor firmware at V11.00.0000-96-g25a54b97a
(`software/source` of the reference project) settled each point:

| Point | Firmware | This decoder | rf_monitor |
|---|---|---|---|
| Frame counter | high nibble the repeat, 1-based (`API_Radio_LLC_FrameCountLoad`, llc.c:118); on VERSION, ALIVE and CMD at 8, TWF and CONFIG at 9; none on FFT, FFT2, RESPONSE | Right | Right bits, but read on frames that have none |
| Permute Control at 8 | TWF and CONFIG only (transport.c:554) | Right | Right |
| ALIVE RMS, velocity, peak-to-peak | unsigned 16-bit (field.c:153-155) | Right | Signed - wrong |
| ALIVE status | phase bits 5:2, install assist bit 7 (field.c:1627) | Right | `(s>>2)&0x3F` folds install assist into the state - wrong |
| VERSION | version 53 bytes at 16; ticks u16 at 81; 83 bytes (cfg.h:479, 281) | Right | 57-byte version; ticks u32 needing 85 bytes, so never decoded - wrong |
| CONFIG | mux at 10, values at 11; 60 parameters by `APP_Normal_ParamsSaveToRadio` | Right offsets, unnamed until now | Right, and named; parameters 5 and 6 mislabelled |
| TWF | layout to 100 bytes with time taken, group and sync attribute; FREQ a compressed ODR code | Right | Right offsets, no trailing fields; FREQ called Hz |
| FFT, FFT2 | no counter; temperature at 8 | Right | Byte 8 called a counter - wrong |
| RESPONSE | parameter u16 at 12-13, payload at 14, minimum 14 bytes (transport.c:2003-2168, app_sync.c:1258) | Wrong until now: one byte at 12 | Right |
| STARTUP (type 0) | never sent | Rejected - right | Named |

The decoder now reads RESPONSE as the firmware builds it, and adds the names
the screens need: `kepler_tables.py` (S2LP-FR-081 … -083) holds the 60
configuration parameters in the firmware's order with their units and
enumerations - "Transit Max Time" and "Transit Wait Time" for parameters 5
and 6, as the firmware sends them, where rf_monitor said "Transit Wait Time"
and "Transit Wake Time" - `config_parameter` (none `mux*5 + slot`, distance
`mux + slot*12`, polynomial `permute_poly_any_size(60, mux*5 + slot, repeat)`),
`permute_poly` with the firmware's constants, `twf_sample` (none
`packet*32 + slot`, distance `packet + slot*(N/32)`, polynomial
`permute_poly(N, packet*32 + slot, repeat)`), `odr_hz`, `reset_reasons`, and
the PCB, product and phase names. CONFIG frames carry `parameters`, TWF
`odr_hz` and `axis`, VERSION `reset_reasons`, `pcb`, ALIVE `phase_name`, every
frame `product`.

#### S2LP-DD-SIM — `simulator.py`

A register file with a radio attached, satisfying `Responder` (CORE-DD-MOCK).
Writing PCKTCTRL3 changes what the packet-format query answers; a strobe flushes
a FIFO; a packet queued on the simulated air is delivered to exactly one receive
and is then gone.

Its replies are the shapes a kit sent (#76), echo and prompt included. The
behaviours modelled are the ones that mislead: a receive with nothing on the air
sends nothing until stopped; a stop sent to an idle board spoils the next
command; a stopped send acknowledges after the stop; send and receive never
finish until the interrupt is routed; the power-on TX source is PN9; a payload
shorter than PCKTLEN never goes; and a packet arriving while the radio is not
armed is counted and lost. A write to a read-only register is accepted and
discarded, as the hardware discards it - which is what the driver's refusal
(S2LP-FR-013) protects a test from.

#### S2LP-DD-CLI — `cli.py`

Sub-commands `info`, `registers`, `radio`, `config`, `packets`, `tx`, `rx`,
`capture`, `stream`, `preamble`, `strobe`, emitting JSON (AD-15); `stream` prints one JSON
line per frame, with `--decode kepler` and `--registers`. `--log` and `--packet-log` open both
logs at once; `--board` names the kit board; `--setup` applies a register file
straight after connecting. `rx` with nothing on the air exits 1 and says why
that is not the same as the air being quiet; `capture` adds a warning when the
capture was not continuous.

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

Ratings, programming and read-back resolution, the reply terminator, the
status-word layout, line rates, and the CV/CC and tracking vocabularies. Each
value that describes the instrument's behaviour is taken from ETB-IF-001. They are here so an out-of-range setting can be
refused *before* it is sent: this supply rejects it without replying, keeps
its previous setting and reports it only through `ERR?`, so a test that asked
for 35 V would run at the previous setting and never be told.

#### DMM-DD-CONST — `constants.py`

What the 1604 is, and what its protocol says: link settings, the handshake
states that power the interface, frame layout and field positions, the
seven-segment patterns, the key characters, and the published reading rate.
Each entry cites the source it came from.

The segment table is the load-bearing one. It is a bitmap, not a character
code, and the identifying relationship is that `8` is every segment (`0xFE`)
and `0` is that less the middle (`0xFC`). That relationship is what fixes bit 1
as the middle segment and bit 0 as the decimal point rather than a segment.

`RANGES` holds each range's full scale and resolution from the instruction
manual, keyed by measurement type and coupling, in the order Up steps through
them; `FREQUENCY_RANGES` the two frequency ranges, chosen by the gate flag.
`GATE_TIME`, `CONFIRM_TIMEOUT` and `READ_POLL` are the timing the driver's waits
are built from. The two annunciator bits the manufacturer's note places
differently from the summary first used - Touch-Hold and auto-range-set, both
bit 1 - follow the note (#115).

#### DMM-DD-PROTO — `protocol.py`

Pure decoding: ten bytes to a `Reading`. It knows nothing about serial ports,
because a wrong number originates here and this is the part that must be
testable without a meter, a port, or a simulator.

| Group | Members |
|---|---|
| Decoding | `decode`, `digits_text`, `unit_and_scale`, `resistance_scale`, `find_frame_start` |
| Framing | `frame_problem`, `FrameAssembler.feed`, `.frames`, `.residue`, `.pending`, `.clear` |
| Result | `Reading`, `Reading.held`, `Reading.is_live`, `Reading.function` |

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

**Validation is how the assembler resynchronises** (DMM-FR-028).
`frame_problem` requires every display byte to be a listed pattern, the units
field to name a measurement and at most one decimal point. A carriage return
that begins a candidate failing those checks is moved to the residue and the
search resumes one byte later, so a stream joined part-way through a frame
yields the next real frame rather than a plausible wrong number.

**The resistance multiplier is derived** (DMM-FR-016). The frame says which
resistance range is selected but not whether the display is in ohms, kilohms
or megohms. `resistance_scale` divides the range's resolution by the value of
the last displayed digit; the ratio must be 1, 1 000 or 1 000 000, or the
reading carries no value and `Reading.problem` says why (DMM-OPEN-08). This is
right whichever display convention the meter uses, which is why it replaced
the assumed factor of 1 000.

#### DMM-DD-DMM — `dmm.py`

`Tti1604`, the driver façade.

| Group | Members |
|---|---|
| Lifecycle | `connect`, `_normalise_resource`, `_post_open`, `_read_identity`, `check_errors` |
| Stream | `_receive`, `_drain`, `_next_frame`, `_discard_input`, `_patience` |
| Keys | `press`, `_send_character` |
| Confirmation | `current_state`, `_await`, `last_reading` |
| Function | `select_volts`, `select_millivolts`, `select_amps`, `select_milliamps`, `select_ohms`, `select_ac`, `select_dc`, `select_hertz` |
| Range | `select_auto_range`, `set_range` |
| Mode | `remote`, `local`, `is_remote` |
| Reading | `read`, `read_many`, `measure` |

`check_errors` is a documented no-op: the meter has no error queue, and a
driver that pretended otherwise would be inventing a clean bill of health.
`_post_open` enters remote mode and does nothing else — in particular it does
not press Operate, which toggles.

Design points added by #115:

- **The link is read as a stream** (DMM-FR-027). `_receive` calls
  `Transport.read_available()` with the transport's timeout fixed at
  `READ_POLL` and loops to its own deadline. It never varies that timeout per
  read, because pyserial reconfigures the port on every change and on Windows
  loses bytes in flight (ETB-SWE3-002 LL-07). Before #115, `_drain` used
  `read_raw()`, which on a serial port only ever times out.
- **Every deadline is on `_clock`**: `time.monotonic` on a port, and a
  simulated meter's virtual clock when talking to one, so the 20 s allowed for
  a 10 s gate costs a test nothing.
- **Selections are confirmed from the readings** (DMM-FR-029). Each `select_*`
  presses its key, then `_await`s a reading whose measurement type, coupling or
  Hz flag shows the change, within `CONFIRM_TIMEOUT` (more for frequency). The
  failure names the function and range the readings show. AC/DC on resistance
  is refused before any key is sent. With remote mode declined there are no
  readings to confirm by, and the key is pressed unconfirmed.
- **Ranges** (DMM-FR-030). `set_range` moves one step per pass - Up or Down
  towards the target, or Auto/Man to lock the present range - and confirms
  each, the passes bounded by the number of ranges. `select_auto_range` presses
  nothing when the meter is already auto-ranging; it used to toggle.
- **`measure` is fresh** (DMM-FR-031): `_discard_input` empties the transport,
  the operating system's buffer and the assembler, one complete frame is
  discarded, and the next returned.
- **Waits allow for the gate** (DMM-FR-032). `_patience` is the settling time,
  plus two gate times when the last reading was a frequency one; the frequency
  paths name the gate they are moving to, since the last reading describes the
  gate being left.
- **Echoes** are matched only among the bytes left once frames are extracted,
  and the echo buffer is cleared before each key is sent, since nothing
  received before the write can be its echo.

`read` logs each measurement with `log_reading`: its measurement as the quantity, value, unit, AC, display text and over range; a reading with no value (over range) is not logged as a number (DMM-FR-034).

#### DMM-DD-SIM — `simulator.py`

A behavioural model rather than canned frames: front-panel state, key handling,
and frame encoding built from the same segment table the decoder reads, so the
two cannot disagree. It reproduces the two states in which a real meter is
silent — local mode, and Operate off — because both look like a dead link from
the far end and neither is a fault.

Since #115 it also draws the display at each range's resolution from
`RANGES`, auto-ranges after a change of function (`range_index=None`, the
default), shows OFL beyond a range, refuses Hz on DC and AC/DC on resistance,
and keeps a schedule on a virtual clock: a reading every 0.4 s, or once per
gate measuring frequency, restarted by a key that changes what is measured.
`poll_within(timeout)` delivers only what is due in time (CORE-FR-062), so a
driver wait shorter than the meter's fails here. Fault injection:
`drop_keys`, `ignore_keys`, `garbage`.

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
  the driver. `read_event_queue` uses `ERR?` and carries its text verbatim.
- **The protocol is the instrument's, not the manual's** (ETB-IF-001). Replies
  are read to CR; `status()` accepts the spaced V1.09 form and the manual's
  compact form, reads the two-line legend the V1.09 sends, takes the output
  from bit 6 and the tracking pair bit 2 first; `in_current_limit` requires
  the channel to be on; `regulated` allows 1.5 read-back steps. The component
  view, the decisions and the lessons behind them are in ETB-SWE3-002.

`measure_voltage` and `measure_current` log each value with `log_reading`, with its channel; `read_channel` measures through them, so its readings are logged too (PSU-FR-044).

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
it **rejects** an out-of-range setting exactly as the hardware does - setpoint
unchanged, `Data out of range.` for `ERR?` - which is the behaviour PSU-FR-002
exists to protect a test from. An unrecognised command is
met with silence, as the hardware meets it, so a driver that misspells one sees
a timeout in a test rather than only on the bench.

Its replies are copied from captures of a real supply (ETB-IF-001 Annex A): CR
terminator, read-back formats, the `STATUS?` legend, and the supply's own error
texts. It does not reproduce the 0.1 V shortfall `VOUT` shows on the bench, or
reply timing.

#### PSU-DD-CLI — `cli.py`

Sub-commands `info`, `read`, `set`, `on`, `off`, `status`, emitting JSON
(AD-15). Two deliberate choices, both about not damaging what is connected:
`set` programs a channel and does **not** energise it (`--on` does that,
explicitly), and `off` with a channel number reports in its output that the
channel is parked at zero volts rather than disconnected. `read` adds a
`warning` key when a channel it read is in current limit.

---

### 5.8 PICO — `benchtools.instruments.pico_sht30` and `firmware/pico_sht30`

A Raspberry Pi Pico 2 reads a Sensirion SHT30-DIS on a DollaTek SHT30-D module
over I2C and reports the temperature, with its name, copyright, version and
commit, over USB CDC. One element across two languages, like BLE: `include/protocol.h` is
the interface both halves are built from.

#### PICO-DD-PROTOCOL — `firmware/pico_sht30/include/protocol.h`

The single definition of the host link. Two X-macro tables: `PROTO_COMMAND_TABLE`
(`name, min_args, max_args, help`) generates the firmware's dispatch table and
handler prototypes; `PROTO_ERROR_TABLE` (`symbol, code, text`) generates
`proto_error_t` and the error texts. `PROTO_VERSION` is `2.0` (#131: `rd`
replaces `ver` and `temp`, and `reset` is renamed `ecureset`); the firmware
does not report it, and the host checks it only against the header. Limits:
`PROTO_MAX_LINE` 64 (command, terminator included), `PROTO_MAX_REPLY` 192,
`PROTO_MAX_TOKENS` 4.

| Command | Reply |
|---|---|
| `rd name` | `ACK rd name = Pico 2 SHT30 Temperature Sensor` |
| `rd copyright` | `ACK rd copyright = (c) 2026 Dermot Murphy` |
| `rd version` | `ACK rd version = V1.00.0000` |
| `rd sha` | `ACK rd sha = <7 hex digits, or unknown>` |
| `rd temperature` | `ACK rd temperature = <°C, 2 dp>`, or `ACK rd temperature = Error` when no reading could be made |
| `rd <other>` | `NAK rd <other> = Error` |
| `rd`, `rd a b` | `err 2 wrong number of arguments` |
| `status` | `ok status=0x<hhhh>` |
| `sreset` | `ok` |
| `ecureset`, `bootsel` | `ok` (the reboot follows the reply) |
| `help` | one `# <name> - <help>` line per command, then `ok` |
| `ver`, `temp`, `reset` | `err 1 unknown command` since 2.0 |

An `rd` reply is a whole line with no `ok` in front, in the `ACK`/`NAK` form the
other bench devices use; everything after `= ` is the value, spaces included.

| Code | Symbol | Meaning |
|---|---|---|
| 1 | `PROTO_ERR_UNKNOWN` | unknown command |
| 2 | `PROTO_ERR_ARGS` | wrong number of arguments |
| 3 | `PROTO_ERR_TOO_LONG` | line too long |
| 4 | `PROTO_ERR_NO_SENSOR` | the sensor did not acknowledge |
| 5 | `PROTO_ERR_CRC` | the sensor checksum did not match |
| 6 | `PROTO_ERR_BUS` | I2C bus timeout |

#### PICO-DD-VERSION — `firmware/pico_sht30/include/firmware_version.h`, `src/firmware_version.c`

`FIRMWARE_NAME` (`Pico 2 SHT30 Temperature Sensor`), `FIRMWARE_COPYRIGHT`
(`(c) 2026 Dermot Murphy`) and `FIRMWARE_VERSION` (`V1.00.0000`) are edited here
and nowhere else, each as a single quoted string so that
`SWE4-UT-PICOFWPROTO` can read it as text. The version is
`V<major>.<minor, 2 digits>.<patch, 4 digits>`, semantic, and bumped with every
change to the firmware or its host driver (PICO-FR-002). `FIRMWARE_GIT_SHA` is
injected by CMake (PICO-DD-BUILD); a build that does not inject it gets
`unknown`. The strings are defined once, in `firmware_version.c`, as
`firmware_g_name`, `firmware_g_copyright`, `firmware_g_version` and
`firmware_g_sha`. The build date and `FIRMWARE_TITLE` are gone (#131).

#### PICO-DD-BOARD — `firmware/pico_sht30/include/board_config.h`

Wiring constants, each overridable with `-D`: `BOARD_I2C_INSTANCE` 0,
`BOARD_I2C_SDA_PIN` 4, `BOARD_I2C_SCL_PIN` 5, `BOARD_I2C_BAUD_HZ` 100000,
`BOARD_I2C_TIMEOUT_US` 10000 (ten times a six-byte transfer at 100 kHz),
`BOARD_SHT30_ADDRESS` 0x44.

#### PICO-DD-HAL — `firmware/pico_sht30/include/hal.h`, `src/hal_pico.c`

The only seam between portable code and the board (PICO-NFR-001): I2C write
and read with STOP, returning `HAL_STATUS_OK`, `HAL_STATUS_ERR_NACK` or `HAL_STATUS_ERR_TIMEOUT`;
millisecond delay; line output (the HAL appends LF); board unique ID; uptime;
reboot; reboot to bootloader. `hal_pico.c` implements it on the Pico SDK -
`i2c_write_timeout_us`/`i2c_read_timeout_us` (a short count or
`PICO_ERROR_GENERIC` is a NACK, `PICO_ERROR_TIMEOUT` a timeout),
`stdio_puts_raw` for output (no CRLF translation), `pico_get_unique_board_id_string`,
`watchdog_reboot` and `reset_usb_boot`. Both reboots flush stdio and wait 50 ms
first so the `ok` reaches the host. It is the only file that includes SDK
headers, and it holds the two MISRA deviations (Rule 21.6 for the SDK's own
output routine, Dir 4.6 for SDK prototypes).

#### PICO-DD-SHT30 — `firmware/pico_sht30/src/sht30.c`

* `sht30_crc8`: bitwise CRC-8, polynomial 0x31, initial 0xFF, no reflection, no
  final XOR; check value CRC(0xBE 0xEF) = 0x92 (datasheet).
* Conversion: `T_mC = round(175000 · S / 65535) − 45000`,
  `RH_m% = round(100000 · S / 65535)`, in 64-bit intermediate arithmetic
  because 175000 · 65535 exceeds 32 bits. Results fit `int32_t` exactly.
* `sht30_decode`: checks both CRCs before writing anything to the caller's
  reading (PICO-FR-026).
* `sht30_measure`: write `0x2400` (single shot, high repeatability, no clock
  stretching), `hal_delay_ms(16)` (datasheet max 15 ms), read six bytes, decode.
* `sht30_read_status`: write `0xF32D`, read three bytes, CRC-check.
* `sht30_soft_reset`: write `0x30A2`, wait 2 ms (datasheet max 1.5 ms) only if
  it was acknowledged.

HAL errors map to `SHT30_STATUS_ERR_NACK` / `SHT30_STATUS_ERR_TIMEOUT`; a NULL
pointer is `SHT30_STATUS_ERR_PARAM`. Status-register bits are `SHT30_STATREG_*`.

#### PICO-DD-TEXT — `firmware/pico_sht30/src/text.c`

A bounded line builder in place of `snprintf` (MISRA Rules 21.6, 17.1).
`text_t` holds the caller's buffer, its capacity, the length and an `overflow`
flag; every append is bounded and sets the flag rather than writing past the
end. Formats: string, token (spaces to `_`), unsigned decimal, milli-units to
three places with the sign on the whole value (negation done in unsigned
arithmetic so `INT32_MIN` is defined), and fixed-width upper-case hex (8 and
16 bit). `text_centi` (#131, PICO-FR-027) writes milli-units to two places:
it rounds the magnitude half away from zero (`(|m| + 5) / 10`, in unsigned
arithmetic, which holds for `INT32_MIN`), then adds the sign only if the
rounded value is not zero, so that −0.004 is `0.00` and never `-0.00`.

#### PICO-DD-PARSER — `firmware/pico_sht30/src/cmd_parser.c`

*Line assembly* (`cmd_line_push`): CR ignored; LF completes the line; a line
that reaches `PROTO_MAX_LINE − 1` characters switches to discarding until the
next LF, which then returns `CMD_LINE_RESULT_OVERFLOW` so that no part of it runs
(PICO-FR-004).

*Dispatch* (`cmd_execute`, split into `cmd_lookup`, `cmd_run` and
`cmd_finish` to stay within the 60-line function limit, with a single return
each): tokenise in place on space and tab, counting tokens
past `PROTO_MAX_TOKENS` without storing them so an over-long command fails its
argument check rather than being truncated; look the first token up
(case-sensitive); check the argument count; run the handler, which writes its
whole reply line - `ok …`, or for `rd`, `ACK …` or `NAK …` - into an empty
buffer. A handler returning an error sends `err <code> <text>` instead, and
whatever it wrote is discarded. A reply that overflowed is replaced by `err 3`,
never sent truncated. `ecureset` and `bootsel` set a pending action that runs
only *after* the reply has been written (PICO-FR-030). Sensor status maps, for
`status` and `sreset`: CRC → 5, timeout → 6, NACK/parameter → 4.

*`rd`* (`cmd_rd`, #131): the single option is matched exactly against
`cmd_rd_fields` - `name`, `copyright`, `version`, `sha`, each bound to its
`firmware_g_*` string - and answered `ACK rd <option> = <value>` without
touching the sensor (PICO-FR-005, -006). `temperature` is not in that table,
because it is measured: `cmd_rd_temperature` calls `sht30_measure` and writes
`text_centi` of the milli-degrees, or `Error` on any sensor failure, still as an
`ACK` - the command was understood, and it is the reading that failed
(PICO-FR-027). Any other option is answered `NAK rd <option> = Error`, the option
echoed as received (PICO-FR-007). `rd` always returns `PROTO_ERR_NONE`; an
option count other than one is refused by the generic argument check with
`err 2`.

#### PICO-DD-MAIN — `firmware/pico_sht30/src/main.c`

`stdio_init_all`, `hal_init`, soft-reset the sensor (a failure is ignored so
that `rd name` still answers, PICO-FR-005), then for ever: `getchar_timeout_us(1000)`,
accept 0–0x7F, push into the line, execute on READY, report on OVERFLOW.

#### PICO-DD-BUILD — `firmware/pico_sht30/CMakeLists.txt`, `pico_sdk_import.cmake`

`PICO_BOARD=pico2`, `PICO_PLATFORM=rp2350-arm-s`, C11 (the SDK requires
`static_assert`; MISRA C:2012 Amendment 3 covers C11). The firmware's own
sources, and only those, compile with `-Wall -Wextra -Wconversion -Wshadow
-Wstrict-prototypes -Werror`. Links `pico_stdlib`, `pico_unique_id`,
`pico_bootrom`, `hardware_i2c`, `hardware_watchdog`; stdio on USB, not UART;
`pico_add_extra_outputs` produces the `.uf2`. The SDK is found from
`PICO_SDK_PATH`, or fetched at tag 2.1.1 with `-DPICO_SDK_FETCH_FROM_GIT=ON`.
The program name is `Pico 2 SHT30 Temperature Sensor`.

The commit SHA (#131, PICO-FR-002): at configure time
`git rev-parse --short=7 HEAD` is run in the source directory and passed as
`FIRMWARE_GIT_SHA`; without git, or outside a checkout, the value is `unknown`.
So that a new commit re-configures the build, the files that hold HEAD are added
to `CMAKE_CONFIGURE_DEPENDS`: `HEAD` and `logs/HEAD`, and, when a branch is
checked out, its ref and `packed-refs`. Each is resolved with
`git rev-parse --git-path`, which finds it in a worktree too (where `.git` is a
file), and a file that does not exist is skipped. The SHA is printed as a
configure-time status message.

#### PICO-DD-TEST — `firmware/pico_sht30/test/`

Host build (CMake + Unity v2.6.0 + CTest) of `cmd_parser.c`, `sht30.c`,
`text.c` and `firmware_version.c`, unchanged, against `support/fake_hal.c`.
The fake records every I2C write, answers reads from a queue (an empty queue is
a NACK - an absent sensor), accumulates delays, captures output lines, and
records how many lines had been sent when a reboot was requested. Built with the
target's warning set as errors plus `-fsanitize=address,undefined`.
`FIRMWARE_GIT_SHA` is fixed at `0123abc`, so that the tests exercise the
injected path.

#### PICO-DD-CONST — `benchtools/instruments/pico_sht30/constants.py`

The command and error tables, `NAME`, `COPYRIGHT`, protocol version (`2.0`),
sensor, default address, status bits and datasheet accuracy, mirrored from the
firmware headers and checked against them by `SWE4-UT-PICOFWPROTO`.
`RD_OPTIONS` lists the five `rd` options and `RD_ERROR` is `Error`.
`raw_to_celsius` and `raw_to_percent` repeat the firmware's integer arithmetic
exactly, and `milli_to_centi_text` repeats `text_centi`; the simulator uses all
three, so that its readings are ones the firmware could produce.

#### PICO-DD-DRIVER — `benchtools/instruments/pico_sht30/thermometer.py`

`PicoSht30` subclasses CORE-DD-SCPI for its transport and lifecycle and
replaces the SCPI parts: `_post_open` reads the identity (not `*CLS`) and
refuses a device whose `rd name` is not `NAME`; `_read_identity` builds the
identity from it (firmware `<version> (<sha>)`, no serial number);
`read_event_queue` is empty. Both command forms share `_send`, which writes a
line and reads lines skipping `#` lines.

* `execute()` is for the control commands: it returns the `key=value` fields of
  an `ok` reply, raises `SensorError(code, text)` for `err`, and
  `ProtocolError` for anything else.
* `rd(option)` matches `^(ACK|NAK) rd (\S+) = (.*)$`, refuses a reply for
  another option with `ProtocolError`, raises `RdRefusedError` for `NAK` and
  `SensorError` for `err`, and returns the value of an `ACK` (PICO-FR-047).
* `firmware_info()` is four `rd` reads - name, copyright, version, sha - cached
  until `refresh` or a reboot; `name`, `version` and `sha` are properties.
* `read()` is `rd temperature`: `Error` raises `NoReadingError`, and a value not
  matching `^-?\d+\.\d{2}$` raises `ProtocolError`. The raw-word cross-check
  and the humidity are gone (#131): the reply carries neither.
* `reset()` sends `ecureset` and forgets the cached identity.

`FirmwareInfo` (name, copyright, version, sha), `Reading` (temperature, text,
timestamp) and `SensorStatus` are frozen dataclasses with `as_dict()` for JSON
reports. `NoReadingError` and `RdRefusedError` are `InstrumentError`s.
`connect()` takes a bare port name as a serial port.

`read` logs the temperature with `log_reading` in degC, with the firmware's text (PICO-FR-048).

#### PICO-DD-SIM — `benchtools/instruments/pico_sht30/simulator.py`

`SimulatedPicoSht30` answers the firmware's command set with its exact reply
text, checking argument counts against `COMMANDS`. The ambient temperature is
quantised to a raw word, converted to milli-degrees with the firmware's integer
arithmetic and formatted with `milli_to_centi_text`, so the simulator is held
to the same arithmetic and rounding as the firmware. `rd` answers name,
copyright, `version` (default `V1.00.0000`) and `sha` (default `0c0ffee`), and
`NAK` for any other option. Faults: `sensor_present = False`, `corrupt_next`
(one reading) and `bus_timeout` each make `rd temperature` answer `Error`, and
`status` and `sreset` answer `err 4`, `err 5` and `err 6` respectively. It
counts measurements, reboots (`ecureset`) and bootloader requests. An optional
`on_bootloader` callable is invoked after `bootsel` has been answered;
PICO-DD-FLASH's simulated board uses it to present its bootloader drive.

#### PICO-DD-CLI — `benchtools/instruments/pico_sht30/cli.py`

`benchtools thermo` with sub-commands `info` (name, copyright, version, sha),
`rd <option>` (argparse `choices` from `RD_OPTIONS`, so an unknown option is
refused before anything is sent), `temp [--count N --interval S]`, `status`,
`sreset`, `ecureset`, `bootsel` and `flash`, emitting JSON (AD-15), `--json PATH`
to also write it to a file. Exit status 0 on success, 1 on a connection or
instrument error.

`flash <uf2> [--expect-version VX.YY.ZZZZ] [--drive D] [--any-image] [--no-verify]
[--bootloader-timeout S] [--port-timeout S]` is marked `standalone`: `main`
does not connect to the thermometer first, because the Pico may already be in
its bootloader with no port to open. Its handler builds a `PicoFlasher` - or,
for a `sim`/`mock` resource, a `SimulatedRp2350` and the flasher wired to it -
prints `FlashResult.as_dict()`, and exits 1 if any check failed. A
`FlashError` (or any `BenchToolsError`) is printed as `error: ...` on stderr and
exits 1 (PICO-FR-075).

#### PICO-DD-FLASH — `benchtools/instruments/pico_sht30/flash.py`

Reflashing with no BOOTSEL press (PICO-FR-070 … -076). The RP2350 boot ROM's
UF2 drive was chosen over `picotool load -x`: it needs no extra tool on the
bench PC, and the boot ROM checks what it is given. The module has four parts.

- **`Uf2Image`** (frozen dataclass). `load()` reads the file and `parse()`
  checks it: a whole number of 512-byte blocks, each with the three magic
  numbers (`0x0A324655`, `0x9E5D5157`, `0x0AB16F30`) and a payload of at most
  476 bytes. It collects the family IDs of blocks that carry one, and the
  payload of every main-flash block. `for_rp2350` is true when every family is
  one an RP2350 accepts - `rp2350-arm-s`, `rp2350-arm-ns`, `rp2350-riscv`, and
  the `absolute` and `data` families an SDK 2.x build may place ahead of the
  image; `rp2040` is not among them. `is_thermometer` looks for the firmware name
  `Pico 2 SHT30 Temperature Sensor` (`NAME` in PICO-DD-CONST) followed by a NUL
  in the payload. `version` is the version string, matched as
  `V\d+\.\d{2}\.\d{4}` followed by a NUL, and `sha` the 7-character
  lower-case hexadecimal commit SHA followed by a NUL; each is empty unless
  exactly one distinct such string is present. *(Revised by #131: was the title
  `Pico2-SHT30-Thermometer` and an ISO 8601 build date, `built`.)*
- **Operating-system seams**, each a plain function. `candidate_roots()` lists
  the mount points to search: `C:\` to `Z:\` on Windows (A: and B: are skipped,
  since probing an empty floppy drive can stall), `/media/*/*`,
  `/run/media/*/*`, `/media/*` and `/mnt/*` on Linux, `/Volumes/*` on macOS;
  any other system raises `FlashError` asking for `--drive`.
  `find_bootloader_drives()` keeps the roots whose `INFO_UF2.TXT` has a
  `Board-ID: RP2350` line. `find_pico_ports()` lists serial ports with USB
  vendor ID 0x2E8A through pyserial. `touch_1200()` opens the port at 1200 baud
  and closes it. A `SerialException` or `OSError` from that open or close is
  returned as a note, not raised: on Windows the Pico reboots while pyserial is
  still configuring the port, which raises `PermissionError(13, 'A device
  attached to the system is not functioning.')` even though the reset worked.
  Whether it worked is decided by the bootloader drive appearing; if it does
  not, the wait for the drive times out. It returns `None` when the port opened
  and closed cleanly. `copy_image()` writes the file to the drive and `fsync`s it;
  an `OSError` is raised as `FlashError` only if the drive is still there.
- **`PicoFlasher`** takes every seam, plus a clock and a sleep, as constructor
  arguments, so tests and the simulated board replace any of them.
  `flash(path, expect_version, any_image, verify)` runs in order:
  1. Load and check the image; refuse a non-RP2350 image, and a
     non-thermometer image unless `any_image`.
  2. `_enter_bootloader`: if exactly one bootloader drive is present (or the one
     named by `drive`), use it - method `already-in-bootloader`. Otherwise
     open the port: if it answers, record its `firmware_info()` (`rd name`,
     `copyright`, `version`, `sha`) as `before`, send `bootsel` -
     method `bootsel`; if opening raises a `BenchToolsError`, note it and call
     the 1200-baud touch, adding any note it returns - method `1200-baud`.
     Then poll for the drive.
     With neither a drive nor a port, raise.
  3. Copy, then poll until the drive is no longer listed.
  4. Unless `verify` is off or the image is not the thermometer (each recorded
     as a note), `_verify`: take the port given, or poll for exactly one
     Raspberry Pi port; poll until the thermometer opens (connecting checks
     `rd name`, PICO-DD-DRIVER); read `firmware_info()` as `after`; record the
     checks, each `{expected, actual, ok}`: `name` against `NAME`; `version`
     against `expect_version` if given, otherwise against the image's
     `version` - or, if the image has no single version, a note that the
     version was not compared; and `sha` against the image's `sha` - or, if it
     has no single SHA, a note. *(Revised by #131: was `ver`, with checks
     `title`, `version` (only if expected) and `built`.)*

  Every poll goes through `_wait_for(condition, timeout, what)`, which checks
  every 0.25 s and raises `FlashError("timed out after N s waiting for <what>")`.
  The timeouts default to 15 s for the drive to appear, 15 s for it to go, and
  20 s for the port. More than one drive or port raises, naming them. A
  mismatch is not raised: it is in the `FlashResult`, whose `ok` is true only if
  every check passed and whose `as_dict()` is the JSON the command line prints.
- **`SimulatedRp2350`** is the board for `sim://` (PICO-FR-076). It holds a
  `SimulatedPicoSht30` whose `on_bootloader` makes a temporary directory
  appear as the drive, with an `INFO_UF2.TXT` naming `RP2350`; a 1200-baud
  touch does the same. Its `copy` writes the image with `copy_image`, removes
  the drive, leaves the bootloader, and sets the simulated firmware's version
  and SHA to the image's (keeping its own where the image has none, and the
  name `unknown` for a non-thermometer image), so verification by `rd` sees
  what a real board would report. While in the bootloader it has no serial port.
  `flasher(**kwargs)` returns a `PicoFlasher` wired to it; `close()` removes
  the temporary directory.

What this unit cannot do is reach a Pico whose firmware has crashed or does
not enumerate on USB: that still needs BOOTSEL or an SWD probe. The 1200-baud
reset relies on `PICO_STDIO_USB_ENABLE_RESET_VIA_BAUD_RATE`, which Pico SDK
2.1.1's `stdio_usb.h` turns on by default when the application does not use
TinyUSB directly, as this firmware does not; this was read from the SDK source
on 2026-10-03 and confirmed the same day on a real Pico 2 running this
firmware, on Windows, where `flash` reached the bootloader by each of its three
methods (PICO-OPEN-05, closed). Also on 2026-10-03, `flash` installed the `rd`
firmware of #131 (built from commit `5c80ae7`) by `bootsel` and its checks
`name`, `version` (`V1.00.0000`) and `sha` (`5c80ae7`) all passed. Drive
discovery on Linux and macOS has not been tried on hardware.

---

### 5.9 RUN — `benchtools.runner`

#### RUN-DD-SPEC — `spec.py`

The specification model: `TestSpec` → `TestCase` → `Step` → `Expectation`, all
frozen dataclasses built by `from_mapping` classmethods that validate as they go
and raise `SpecError` naming what to fix. `load_mapping` reads JSON with the
standard library and YAML when `pyyaml` is present. `TestSpec.instruments_used`
collects the aliases referenced anywhere, so the runner can verify the bench
before starting. `TestSpec` and `TestCase` set `__test__ = False`: their names
would otherwise make pytest try to collect them.

A `parameters` block is applied first, on the raw mapping: `substitute_parameters`
replaces every `{param: name}` with the value, or with the value rendered
through `format` (`{param: period, format: "WR ALIVE-PERIOD {}"}`), so a
parameter can stand wherever a literal could and is validated by the same
rules. An undefined name is refused with the list of those defined.
`TestSpec.parameters` carries the values into the run record and report (#95).

An `instruments:` entry is a driver name or a mapping with `driver` and
`event`; `_parse_instruments` splits them into `instrument_drivers` and
`instrument_events`, validating each name and refusing two aliases one name
(RUN-FR-008).


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

Before an instrument connects, each option its driver's `connect` declares as an
input file (CORE-DD-PATHS) is resolved against `BenchConfig.directory`, the bench
file's own directory (RUN-FR-007). A file found nowhere is passed on unchanged and
the locations searched are logged as a warning, since a simulator may never read
it and the driver that does says what is missing. A bench built in code
(`BenchConfig.simulated`) has no directory, and the search starts at the working
directory.

`describe_instruments()` asks every instrument the run actually opened what it
is - driver, model, serial number, resource, and the firmware build where the
instrument reports one - and is called *after* the run rather than before, so an
instrument the suite refreshed in setup is recorded as the one that produced the
measurements. It never opens an instrument to describe it: doing so would change
what the run did. An instrument that will not identify is recorded with an
`identity_error` rather than dropped, because silence about the bench is worse
than a recorded failure.

Event-log names (RUN-FR-008, AD-28): `InstrumentConfig.event` is the bench's
name for an instrument, validated and unique within the bench. `name_events`
takes the specification's, renaming any instrument already open;
`event_source_for` resolves specification, then bench, then the driver's
`EVENT_SOURCE`; `check_event_sources` refuses two instruments a run uses that
would share a name, defaults included. `get` connects inside `connecting_as`,
and `describe_instruments` records each instrument's `event`.


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

After references are resolved, each argument the bound method declares as an
input file (CORE-DD-PATHS) is resolved against the directory of the
specification being run (RUN-FR-017). A file found nowhere is a
`ConfigurationError` naming the action, the argument and every location
searched, and so a step **error**.

The runner writes its progress as structured records through `log_event`
(RUN-FR-060, #135): `run_start` with the plan from `_plan` - the whole tree,
each test case marked selected or not - then `case_start`/`case_end` per test
case (a test case not selected has only `case_end`), `step_start`/`step_end`
per step with `phase` (`PHASE_SETUP`, `PHASE_TEST`, `PHASE_TEARDOWN`), `case`
and `step` indices, and `run_end` with the verdict, in a `finally`, so a run
refused before setup still starts and ends in the log. Step records are DEBUG,
the rest INFO. `_execute_step` returns the record with the resolved arguments
and the result, which `run_step` puts in `step_end`.

`run(spec, selection)` runs only the test cases named in `selection`; empty
runs them all (RUN-FR-059). A test case left out gets a `CaseRecord` with
status SKIP and `skip_reason` `NOT_SELECTED` ("not selected"), so the record
lists every test case and says why one was not executed. Setup and teardown run
regardless. `check_selection(specs, selection)` raises `SpecError` for a name no
specification contains, naming the test cases there are; the command line calls
it before the bench is opened. `RunRecord.selection` carries the selection into
the JSON record, the markdown header and the JUnit properties.

#### RUN-DD-CONTROL — `control.py`

`RunControl` holds what an operator has asked of a run and where the run is,
under one `threading.Condition` (RUN-FR-061 … -065, #136). The runner calls
`begin(suite, validator)`, `checkpoint(phase, case, step)` before every step,
and `finish()`; the server's threads call `request(message)`.

- `checkpoint` records the position, then waits while paused and nothing is
  pending, and returns the pending `Command` - `ABORT`, or `RESTART_FROM` with a
  target - or `None`. In teardown (`interruptible=False`) it only records.
- `request` validates and accepts: an unknown command, no run, anything but
  status in teardown, a restart in setup, pause when paused, resume when not, and
  a second abort are refused with the reason. `restart_test` becomes
  `RESTART_FROM` the current test case, step 0. A restart target is checked by
  the runner's validator. Every request is logged as `control`, and every action
  the runner takes as `control_applied`.
- `ControlServer` is a `socketserver.ThreadingTCPServer` bound to `HOST`
  (127.0.0.1) only, one JSON request and reply per line, requests longer than
  4 KiB refused. Port 0 binds a free port; `start` logs `control_listening`.

In the runner, `run_steps` calls `checkpoint` before each step and raises
`_Interrupted` with the steps done for a command. `_run_tests` replaces the
plain loop over test cases with one that obeys it: on abort the interrupted
test case is an ERROR, `ABORTED`, and the rest SKIP with that rationale; on a
restart `_restart` drops the records at or after the target that will run again,
marks test cases jumped over `SKIPPED_BY_OPERATOR`, and `run_case(case, index,
first, kept)` resumes at the target step with the earlier steps' records kept.
After the last test case it checks once more, so a restart asked during the last
step is honoured and a pause holds the run before teardown. `_restart_refusal`
walks the steps from the target on, with `_references_in` finding each saved
name a step's arguments and expectations use, and refuses a name neither saved
nor saved earlier in that walk. An abort in setup becomes the setup error.

`READ_SETUP` (#157): `request` sets a flag, not a pending command, so it neither ends a pause nor competes with an abort. `checkpoint` returns it when nothing else is pending; the runner calls `_read_setups` - `read_setup` on every connected instrument that has one, a failure logged as a warning - then checks the checkpoint again and runs the step. After the last test case it does the same and carries on. Refused in teardown and with no run (RUN-FR-066).

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

The Instruments table carries each instrument's event-log name, so a line in
the event log can be traced to the instrument in the report (RUN-FR-008).


#### RUN-DD-CLI — `cli.py` and `benchtools/cli.py`

`benchtools run` takes one or more specifications, a `--bench` or `--simulate`,
and report destinations; with several specifications the report paths are suffixed
so they do not overwrite. Exit status is 0 pass, 1 failure or error, 2 usage.
`benchtools/cli.py` dispatches `run`, `scope`, `drivers` and `backends` by name
rather than nesting argparse parsers, so each tool keeps its own complete
`--help`.

---

### 5.10 VIEW — `benchtools.viewer`

#### VIEW-DD-STATE — `state.py`

`RunState.apply(record)` dispatches on the record's `kind` to `_on_<kind>`;
a record without one changes nothing (VIEW-FR-003). `run_start` resets the
state and builds the tree from the plan - setup, test cases (PENDING, or NOT
SELECTED), teardown - each step described by `describe_step`, which writes the
instrument alias upper case, the method in words and each argument as `name
value`, a saved-value reference as `<name>`, or uses the step's description.
`step_start`/`step_end` and `case_start`/`case_end` update the step or test
case they name by phase and index; a step beyond the plan is added, for a log
attached without its `run_start`. `case_start` with `first_step` returns the
steps from there to PENDING. `control_listening` records the control port;
`control_applied` records the position and pause, and a restart returns later
test cases to PENDING. `snapshot()` is a deep copy, so a server thread can
serialise it outside the lock.

#### VIEW-DD-SERVER — `server.py`

`Hub` follows one event log with `EventTail`, on a thread polling every 0.2 s.
Under one condition it appends each record with a sequence number (the last
`KEEP_RECORDS`, 5 000, are kept), applies it to `RunState` and notifies
waiters. `follow(path, port)` starts afresh on another log and bumps the
generation. `since(sequence, generation)` returns, under the same lock, the
current sequence and generation, the records after *sequence* (all when the
generation changed) and the state, so a record is never counted seen without
being returned (VIEW-FR-005).

`ViewerServer` is a `ThreadingHTTPServer` on `HOST`. `_Handler` refuses any
request whose `Host` is not `127.0.0.1`, `localhost` or `::1`, and any POST
without `X-Benchtools: 1` (VIEW-FR-002). `GET /` and `/static/<file>` serve the
page from `static/`, refusing a path resolving outside it. `/api/events` writes
`reset`, `record` and `state` events, then waits on the hub, with a keep-alive
comment every 15 s. `/api/control` sends the request with `send_control` to the
control port - given on attach, else announced in the log - and returns the
runner's reply, 409 without a port and 502 when the runner does not answer.
`/api/attach` follows another log. `Catalogue` lists specification files
(`.yaml`, `.yml`, `.json`) with their test cases and warning, or why one will
not load, and bench files. `Launcher.start` checks the request against the
catalogue - specification, bench, test cases, the warning acknowledged on
hardware - refuses a second run while one it started is in progress, and runs
`python -m benchtools run` with `--event-log`, `--control 0`, `--json`,
`--markdown`, `--test` for each test case ticked and `--acknowledge` when
acknowledged, its console to a file beside them (VIEW-FR-007, -008).

**From another PC (#141).** `ViewerServer` takes `token`, `read_only` and `tls`, and refuses a non-loopback host (`is_loopback`) without a token. With a token, `_authorised` compares the presented token - `Authorization: Bearer`, else the `benchtools_view` cookie - with `hmac.compare_digest`, and refuses with 401; the Host check is then skipped, the token being the guard. `GET /?token=` with the right token (`_sign_in`) sets the cookie (HttpOnly, SameSite=Strict, Secure under TLS) and redirects to `/`. `_post_refusal` refuses, in order, a missing token, a read-only viewer, and a missing guard header or wrong Host. `tls` wraps the listening socket. `main` makes a token with `new_token` (32 random bytes) for a non-loopback `--bind`, prints the address with it, flushed, and warns when it is plain HTTP. The POST API is a table of handlers (`_POST_API`) like the GET API (VIEW-FR-025 … -027).

#### VIEW-DD-TRAFFIC — `traffic.py`

`classify(text)` names a line `sent` (`>> `, `> `; a GDB/MI token stripped),
`received` (`<< `, `< `, `console `), `event` (`< +`, `async `, `rtt: `) or a
`note` (VIEW-FR-010). `Traffic.feed(record)` skips the runner and structured
records, notes each source's driver from its logger, and keeps per source a
deque of the last `KEEP_EXCHANGES` (2 000) entries. A sent line opens an
exchange and becomes the source's open one; a received line joins the open
exchange - setting `reply_t` and `ms` on the first - however many events came
between; with none open it is `unasked`. `view(t0, t1, limit)` copies, per
source, the entries whose command was sent within the window, or the latest
*limit*. `PsuPanel` and `JlinkPanel`, ported from the Embedded Test Bench monitor's
`sources.py` (#82), rebuild the front panels from the same lines and give
`rows()`; `panel_for(logger)` picks one by driver (VIEW-FR-011).

`Hub._apply` feeds every record to the state, the traffic and the source's
panel - created from the first line whose logger names a driver, since the
first may be the transport's - and starts traffic and panels afresh on
`run_start`. `Hub.instruments(t0, t1)` returns both; `GET /api/instruments`
serves it, `?t0=&t1=` refused unless finite numbers (VIEW-FR-012).

#### VIEW-DD-RADIO — `radio.py`

`RfFrames.feed` takes `rf_packet` records (S2LP-FR-080): a transmitted packet
is counted as sent; a received one is decoded with `decode_kepler_frame` if the
driver did not, its problem stated when the radio rejected it or it would not
decode, and appended to a deque of `KEEP_FRAMES` (1 000) with a one-line
summary of its fields. Per sensor it keeps the frames heard, last time, RSSI and
the latest frame of each type with the `SUMMARY_FIELDS` it carries.
`view(sensor)` filters to one sensor (VIEW-FR-013, -014).

`BleAir.feed` takes the dongle session's `< +event key=value ...` lines,
parsed by `parse_fields` (integers as numbers): `adv` and `sensor` update a
device table by address - name, adverts, RSSI latest and mean, first and last
board time in microseconds - and `adv` reports go to their own deque; other
events (`scan`, `conn`, `disc`, ...) to the event list. `view()` gives each
device's mean interval as the board-time span over the adverts less one
(VIEW-FR-015). `Hub.radio` and `Hub.bluetooth` serve them, the latter with the
dongle's exchanges from VIEW-DD-TRAFFIC, at `/api/radio?sensor=` and
`/api/ble`.

#### VIEW-DD-GRAPHS — `graphs.py`, `static/graphs.js`

`Readings.feed` keeps every `reading` record with a numeric value and a time,
keyed `<source> <quantity>[ ch<n>]`, `KEEP_POINTS` (5 000) per series;
`charts()` groups them one chart per unit, titled from `UNIT_NAMES`
(VIEW-FR-016). `advertising(adverts, address, expected_ms)` picks the device
heard most unless one is named, takes its adverts with a board time, and gives
three charts with `x: "dongle"`: the interval between consecutive adverts in
ms, the interval less the expected period or the median, and RSSI - each at
seconds on the dongle's clock from its first advert, because the dongle reports
adverts in batches and the host's times bunch together (VIEW-FR-017).
`step_markers(state)` lists each started step's start time and name. `Hub.graphs`
serves all three at `/api/graphs?ble=&expected_ms=`, the latter refused unless a
finite number.

`graphs.js` draws each chart as SVG with no library: `niceTicks` gives round
y-ticks covering the data (and zero for a delta chart), x-ticks on the host's
clock to the places the step needs, or seconds on the dongle's; 2 px lines in
the categorical palette's fixed order, points when there are few, a legend
above when there are several series and the series named in the title when one;
dashed step markers with their name as a tooltip, on charts of the host's
clock only; a crosshair and tooltip with each series' nearest value. The
palette (`--series-1` … `-8`, light and dark) passed the dataviz palette
validator on both surfaces; its light-mode contrast warning is answered by the
legend and the hover values (VIEW-FR-018).

#### VIEW-DD-TAGS — `tags.py`

`Tagger.tag(record)` gives every record, as the hub reads it and before
anything else sees it, `record["tags"]` (VIEW-FR-020, -021): `kinds` -
`rf_rx`/`rf_tx` for `rf_packet` by direction, `reading`, `runner` for
`run_`/`case_`/`step_` records, `control`, `ble_adv` for a dongle's `< +adv` line;
`sensor` from `sensor_of` - a frame's decoded sensor ID, decoding the payload
if the driver did not, or the six hex digits after the dash in a BLE line's
`name=`; and `test`, the run and test case in progress, `"<run>. <suite> >
<test case>"` with `setup` and `teardown`, moved on by `run_start`,
`case_start` and a teardown `step_start`, cleared after `run_end`. A test case
not selected tags its own `case_end`. `Tagger.tests` lists every label in
order, and the state snapshot carries it as `tests`.

#### VIEW-DD-STATUS — `status.py`, `static/status.js`

`InstrumentStatus.feed` keeps per source (not `TEST`, `BENCH` or the runner's
records) whether the link is open - from the transport's `opened`/`closed`
lines, open if first seen otherwise - the time, level and text of its last
record; `view(now)` gives each a state: `closed`, `error` or `warning` by the
last level, `silent` after `SILENT_AFTER_S` (30 s), else `ok` (VIEW-FR-022).
`progress(state)` counts, from the run's state, the steps to run - setup, the
steps of test cases neither not selected nor skipped, without the unrun steps
of a test case already ended, and teardown - and those done; names the test
case at the position, or the phase; and, while running and once
`MIN_STEPS_FOR_ESTIMATE` (3) have a duration, sums `_expected` over the
remaining steps: the last duration of the same action with the same arguments,
else the action's mean, else the mean of all (VIEW-FR-023, -024).
`Hub.status(now)` serves both at `/api/status`.

`status.js` polls it every second and draws the fixed footer on every page:
the state badge, the test case, "Steps n / m", "About … left" or "Time left:
estimating", and a chip per instrument with a status-palette dot, its name and
"ok"-time or its state in words, its last line as the tooltip.

#### VIEW-DD-KEPLER — `kepler_view.py`, `static/kepler.js`

`RfFrames` now remembers the frame its last `feed` added (`last_frame`), and
the hub hands it to `KeplerView.feed`, which keeps the last `KEEP_LATEST` (500)
frames with `byte_roles` (bytes 0-6 header, 7 type, 8 permute control when the
frame has one, the counter at 8 or 9, the rest payload), `header_rows` and
`payload_rows` - every decoded field not the header's, ticks also as
DD:HH:MM:SS, a CONFIG frame's parameters by name with their units; per sensor,
each configuration parameter's latest value, keyed by the parameter the
firmware's mapping says the slot carries (S2LP-FR-081); and per sensor its last
VERSION frame. `view(sensor)` gives the latest 50 frames, the 60-row
configuration table with block, unit, time, and `disabled` for an enable set
to 0, the `CONFIG_GROUPS` summaries, and the identification - of the sensor
chosen, or the first heard (VIEW-FR-028 … -030). `/api/kepler?sensor=` serves
it. The frames list's summary names a CONFIG frame's parameters and leaves the
product out.

`kepler.js` adds sub-tabs to the RF page - Frames, Latest Data, Config,
Identification - polling `/api/kepler` every second while one is shown;
Latest Data has its own pause, holding the newest reply until resumed.

#### VIEW-DD-SENSOR — `sensor_series.py`

`SensorSeries.feed` takes each frame `RfFrames` adds (as `KeplerView` does) and
keeps, per sensor, `KEEP_POINTS` (1 000) per series. A copy is plotted only if
it is the first heard of its frame: repeat 0, or a later repeat more than
`REPEAT_WINDOW_S` (1 s) after the last plotted frame of its type (and, for TWF,
packet) - so a lost first copy is replaced by the next, and no frame is
plotted twice, where rf_monitor plotted every copy. Temperature and battery
(VERSION's loaded battery) from ALIVE, TWF and VERSION; from ALIVE, per axis,
acceleration RMS and peak to peak through `to_mg` and velocity through
`to_mm_s` - full scale `8 << si_scale` g, `32767 / full scale` counts per g,
mg `raw * 1000 / cpg`, mm/s `raw * 10 / cpg` - each point keeping its raw
count, and the ticks; from TWF, its three SI values by SI type (0 acceleration,
1 velocity, 2 peak to peak, 3 magnetometer frequency, 4 amplitude, both
counts). `view(sensor, axis)` gives the Environment, Short Interval and Ticks
charts, the tick delta `max(0, next - this)` (VIEW-FR-031 … -033).
`/api/sensor?sensor=&axis=` serves it. The RF page's Environment, Short
Interval (with an X/Y/Z selector) and Ticks sub-tabs draw them with
`lineChart`, whose tooltip adds a point's raw count; Zoom in and out halve or
double the span about the time last hovered, and Reset restores it.

#### VIEW-DD-TWF — `twf.py`

`TwfAssembler.feed` keys a TWF frame by sensor, buffer - B when the param's
`twfb` bits are set - and axis, and keeps a `_Capture` per key: packet count,
permutation, TWF scale, ODR (`odr_hz`), and the samples per `(packet,
version)` - the version being the repeat under the polynomial, 0 otherwise,
where copies are the same. A different packet count or permutation, or packet
0 after the capture completed, starts a new one; a completed capture is kept
as `complete`. `_Capture.waveform` places each sample at `twf_sample(method,
packet, slot, N, version)` in mg at `(8 << twf_scale) * 1000 / 32767` per
count, `None` where unheard (VIEW-FR-034). `spectrum` fills gaps with
`fill_gaps`, applies a Hann window, and gives `|X(k)| * 2 / N` per bin -
NumPy's `rfft`, else `_fft` (radix 2) or a direct transform for a length that
is not a power of two (VIEW-FR-035). `view(sensor, buffer, axis)` falls back to
the other buffer and gives the waveform with its gaps as nulls, the spectrum
and the reception figures, signal Excellent ≥ 99 %, Good ≥ 95, Fair ≥ 80,
else Poor. `/api/twf?sensor=&buffer=&axis=` serves it.

Three choices differ from rf_monitor, each from the firmware (#151): the
buffer is the frame's, not guessed by alternation; the scale is the TWF scale,
param bits 13:12, not the SI scale; the ODR is decoded from its code. The RF
page's TWF sub-tab draws the waveform and spectrum with `lineChart`, which now
breaks its line at a null, draws only what is inside its span (clipped), and
labels a numeric x-axis in its unit; Zoom in/out/Reset act on the waveform
within the capture (VIEW-FR-036).

#### VIEW-DD-DIAG — `diagnostics.py`

`Diagnostics.feed` keeps, per sensor and frame type (`UNKNOWN` when the type
is missing), a `_TypeStats`: packets; frame times - a copy starts a frame when
it is copy 1, or more than `BURST_GAP_S` (1 s) after the last frame - and the
last ten with their deltas; and the burst - the copies heard and the total the
counter states. A burst closes at the next copy 1, when every copy is in, or
when `BURST_GAP_S` passes with none, adding the total to `expected` and the
copies missing to `dropped`; one still arriving is not counted yet. `view`
closes a quiet burst at "now", the latest frame time, and gives the gaps'
mean, population standard deviation, and the shortest and longest with the
times either side (VIEW-FR-037, -038). `reset(sensor)` clears.

`SyncTracker.feed` takes CMD frames by the sensor's ID - REQ_LORES starts
afresh; each parameter names a phase - and RESPONSE frames by the echoed
sensor ID: LORES sets a deadline `t + timer/1000`, HIRES `t + timer/1e6`, with
the slot. `view` gives each sensor heard within `SYNC_IDLE_S` (1 200 s) of
"now" its remaining times and a state - `nack`, `hires` or `fired`
(VIEW-FR-039). Both are timed by the frames, not the viewer's clock: rf_monitor
anchored them to when it processed a frame, so a replayed log's countdowns
meant nothing. `/api/diagnostics?sensor=` serves both, and `POST
/api/diagnostics/reset` resets. The RF page's Diagnostics sub-tab draws the
period table (a row's tooltip naming the frames either side of its extremes),
Reset, Auto/Hold and the last ten; Sync the table with its states coloured.

#### VIEW-DD-REPORT — `report.py`, `static/notes.js`

`NotesStore(event_log)` reads and writes `<event log>.notes.json` - fault,
findings, when saved - each note text of at most `MAX_NOTE` characters; with no
event log `save` refuses, and a damaged file reads as empty (VIEW-FR-040).
`GET /api/notes` reads them; `POST /api/notes` saves them, guarded like every
change and so refused by a read-only viewer.

`build_report(hub, sensor)` writes one HTML document with its CSS inline and no
script: when made, from which log, which sensor; the notes, escaped; the run
and its test cases; and from the hub's own views (`kepler_screens`,
`sensor_graphs`, `waveform`, `diagnostic_screens`) the identification, the
Environment, Short Interval (Z) and Ticks charts, each TWF buffer and axis
with its waveform and spectrum, the configuration parameters received, the
period statistics and the latest frames as text (VIEW-FR-041). `svg_chart`
draws a chart as SVG without a script - gridlines, round ticks, the time or a
unit on the x-axis, a line per series broken at a gap. Print CSS keeps charts
and tables whole (VIEW-FR-042). `GET /api/report?sensor=&download=1` serves it,
as an attachment when asked. The page's Notes & report tab saves the notes on
change and offers Download and Print / save as PDF, which opens the report and
the browser's print dialogue.

The sensor graphs are now in time order whatever order their frames were read
in, which a report from a log stitched together showed was needed.

#### VIEW-DD-STGUI — `st_gui.py`, `static/stgui.js`

`StGui.feed` keeps the latest `rf_setup` record per source, its register keys
back to addresses. `rf_setup_rows`, `register_rows` and `regs_text` are ported
from the Embedded Test Bench monitor's `sources.py`: the RF setup in sections, the
registers with fields and a `changed` flag for a writable register off its
reset value, and the register file of every changed writable register.
`st_row` lists a frame as ST's GUI does, a CRC failure (error 2) as "Packet
lost. CRC error". `Hub.st_gui_screen` and `Hub.registers_file` serve
`/api/stgui` and `/api/stgui/regs` (400 before any setup is read); `POST
/api/stgui/refresh` sends `read_setup` to the runner's control channel, so the
port stays with the run (VIEW-FR-043 … -045). The RF page's ST GUI sub-tab
lays them out as ST's GUI does: setup and frames on the left, registers on the
right, each register row expanding to its fields.

#### VIEW-DD-PAGE — `static/index.html`, `app.js`, `app.css`

The Event log tab has Pause/Resume - records arriving while paused are held in `heldBack` and counted, and added on resume - a checkbox per instrument, "Show only" checkboxes per kind (any checked restricts to those), a sensor selector of the sensors seen, and a test selector shown when there are two or more; `shown(record)` applies all of them. One page, seven tabs: Run, Instruments, RF, BLE, Graphs, Event log, Start / attach. RF shows a sensor selector, the sensor table and the frames, a frame's decode on selecting it; BLE the device table, events and the dongle's exchanges; both polled every second while shown. The Instruments tab shows the front panels, a button per source with its count, and that source's exchanges - time, sent, replies, milliseconds - polled every second while shown; a step's text on the Run page, once it has started, opens its traffic below it. `app.js` opens an
`EventSource` on `/api/events`, keeps the latest state and up to 3 000 records,
and redraws on the next animation frame. The Run page draws each group's
status dot, name, requirement and reason, and each step's text, duration,
result or saved value, measurements and error; a ↻ on each test step restarts
from it. Buttons are enabled from the state: pause when running and not paused,
resume when paused, restart test case in a test case, none in teardown or
without a control port. Abort asks for confirmation. The Event log page shows
time, source and text, with a checkbox per source. The start form fills from
`/api/catalogue`, shows a specification's warning, and sends the ticked test
cases, or none when all are ticked. Colours are CSS variables with a dark set
under `prefers-color-scheme`; the layout narrows to a phone's width without
scrolling sideways.

## 6. Review & Approval

| Role | Name | Signature / Electronic Approval | Date |
|---|---|---|---|
| Author | Claude | Approved | 2026-09-19 |
| Technical Reviewer | Dermot Murphy | — | *pending* |
| Quality Assurance | Dermot Murphy | — | *pending* |
| Approver | Dermot Murphy | — | *pending* |

> **Note:** This document is under configuration management (SUP.8). Post-approval changes require a change request (SUP.10) and a new document version.
