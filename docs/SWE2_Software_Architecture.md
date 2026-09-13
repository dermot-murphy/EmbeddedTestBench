# SWE.2 — Software Architectural Design

| Field | Value |
|---|---|
| Document ID | BENCHTOOLS-SWE2-001 |
| Version | 2.0 |
| Date | 2026-09-13 |
| Process reference | Automotive SPICE V4.0, SWE.2 Software Architectural Design |

## 1. Architectural drivers

| # | Driver | Consequence |
|---|---|---|
| D1 | VISA must be optional (STK-06, CORE-NFR-001) | The VXI-11 protocol is implemented in-package, and the choice of protocol stack is pushed behind an abstraction, making it a deployment decision rather than an architectural one. |
| D2 | More instruments are coming (STK-07): power supplies and loads, DMMs, signal sources, logic and protocol analysers, BLE and RF | Everything not specific to one instrument is factored into a shared core. Transports and drivers are held in registries so new ones are added without modifying existing code. |
| D3 | A bench runner must drive the tools (STK-08) | Test intent lives in data, not code. The runner depends on drivers through a uniform base class, never on any specific one. |
| D4 | Cross-channel timing must be trustworthy (ANA-FR-016) | All channels are read from one acquisition; analysis operates on records, never on a live instrument, so it is deterministic and replayable. |
| D5 | Must be verifiable without hardware (SCOPE-FR-090, RUN-FR-005) | A test double sits at the transport boundary — the widest seam that still exercises the SCPI vocabulary — and a simulator harness is shared so each instrument writes only its own behaviour. |
| D6 | An invalid setting must not half-configure an instrument (CORE-NFR-004) | Validation precedes transmission; a complete setup is sent as one compound message. |

## 2. Layering

```
   +--------------------------------------------------------------+
   |  benchtools.runner                                           |
   |  spec -> bench -> runner -> results -> report   +  cli       |
   +--------------------------------------------------------------+
                        |                    |
   +--------------------------------------------------------------+
   |  benchtools.instruments                                      |
   |  tek3014b (scope, constants, simulator, cli)                 |
   |  generic  (anything answering *IDN?)                         |
   +--------------------------------------------------------------+
              |                                    |
   +-------------------------------+               |
   |  benchtools.analysis          |               |
   |  waveform  measure  plotting  |               |
   +-------------------------------+               |
              |                                    |
   +--------------------------------------------------------------+
   |  benchtools.core                                             |
   |  scpi (ScpiInstrument, 488.2 blocks)                         |
   |  simulator (SimulatedInstrument, Responder)                  |
   |  enums   validation   errors                                 |
   |  transport: base / vxi11 / socket_raw / visa_backend /        |
   |             mock / factory (registry)                        |
   +--------------------------------------------------------------+
                              |
                       [ instrument ]
```

Dependencies point one way only: **core, then analysis, then instruments, then
runner**. This is not merely a convention — it is enforced by
`tests/test_layering.py`, which parses every module's imports and fails the build
on a violation. The core is additionally checked to contain no reference to any
instrument, and to be importable without importing any other element.

## 3. Architectural elements

| ID | Element | Responsibility | Key interfaces |
|---|---|---|---|
| CORE-ARC-001 | `core.scpi.ScpiInstrument` | The link lifecycle, command and query primitives, identification, IEEE 488.2 operations, error checking, 488.2 block codec. Every driver subclasses it. | `connect`, `initialise`, `identify`, `read_event_queue`, `check_errors`, `_query_*` |
| CORE-ARC-002 | `core.transport.Transport` | Abstract instrument link with buffered message framing built on three subclass primitives. | `write`, `read_message`, `read_exactly`, `read_raw`, `query`, `clear` |
| CORE-ARC-003 | Concrete transports and the factory | Four interchangeable transports selected by resource string, held in a registry so a new link type registers itself. | `open_transport`, `parse_resource`, `register_backend` |
| CORE-ARC-004 | `core.simulator.SimulatedInstrument` | Shared simulator harness: dispatch, compound messages, 488.2 queries, event queue, binary replies. `Responder` is the protocol the mock transport accepts. | `respond`, `handle`, `_cmd_*`, `push_event` |
| CORE-ARC-005 | `core.validation`, `core.enums`, `core.errors` | Range and channel validation, the SCPI enumeration base, and the single exception hierarchy. | `validate_range`, `ScpiEnum`, `BenchToolsError` |
| ANA-ARC-001 | `analysis.waveform` | Data model: decode digitiser codes, scale to seconds and volts, detect clipping, export CSV. | `Waveform`, `WaveformPreamble` |
| ANA-ARC-002 | `analysis.measure`, `analysis.plotting` | Pure analysis over `Waveform` objects, and host-side rendering. | `measure_channel_spread`, `measure_period`, `plot_waveforms` |
| INST-ARC-001 | `instruments.*` | One subpackage per instrument, adding only its command vocabulary, capability envelope and simulator. | per `ScpiInstrument` |
| SCOPE-ARC-001 | `instruments.tek3014b` | The TDS3000 SCPI vocabulary and the oscilloscope's capability envelope. | `Tek3014B` |
| RUN-ARC-001 | `runner` | Specification model, bench resolution, execution engine, result records, report writers, command line. | `load_spec`, `BenchConfig`, `BenchRunner`, `write_*` |

## 4. Key architectural decisions

### AD-01 — Implement VXI-11 rather than depend on VISA
*Decision:* implement the ONC-RPC/VXI-11 core channel on the standard library.
*Rationale:* VXI-11 is an open published protocol; a VISA library is one
implementation of it. Implementing it removes a heavyweight, platform-specific,
sometimes licensed dependency from every test host.
*Cost:* ~320 lines of protocol code that must itself be verified — addressed by
testing against an independently written RPC server and cross-checking against
pyvisa-py.

### AD-02 — A shared core with enforced one-way dependencies
*Decision:* factor the transport, SCPI plumbing, validation and simulator harness
into `benchtools.core`, and enforce the layering with a test.
*Rationale:* roughly half of the original single-instrument driver was already
instrument-agnostic. With six more instrument families planned, that code is
either shared once or duplicated six times.
*Consequence:* a specific coupling had to be broken. `transport/mock.py`
previously imported the oscilloscope's simulator, so the entire transport package
— and therefore every future driver — depended on one oscilloscope. The mock
transport now accepts any `Responder`, and each driver declares its own simulator
via `SIMULATOR_CLASS`. The dependency is inverted: instruments know about the
core, never the reverse.

### AD-03 — Registries, not if-chains, for transports and drivers
*Decision:* transports, resource schemes and instrument drivers are registered by
name.
*Rationale:* BLE and RF instruments will need link types that are not SCPI over
LAN — serial dongles, USBTMC, HTTP-controlled boxes. A registry lets those arrive
in their own modules. It also means a bench configuration names a driver as data,
so a test specification cannot reach arbitrary code.

### AD-04 — Framing primitives in the base transport
*Decision:* subclasses supply `_recv_chunk() -> (data, end)`; the base builds
`read_message`, `read_exactly` and `read_raw`.
*Rationale:* the three framing modes SCPI needs are identical across transports;
only the notion of "end" differs. Writing them once removes the most likely place
for transports to diverge.

### AD-05 — Read binary blocks by declared length, not to end-of-message
*Decision:* `CURVe?` responses are read by consuming the IEEE 488.2 header and
then exactly the declared number of bytes.
*Rationale:* binary sample data can legitimately contain the terminator byte, and
a raw socket has no end-of-message indication at all.
*Consequence:* the payload returned is already de-framed and must **not** be
passed through the block parser again — `Waveform.from_payload` exists for
exactly this, distinct from `from_block`. A defect of precisely this kind was
found and fixed during development; see the test report.

### AD-06 — N-channel timing analysis host-side, from one acquisition
*Decision:* the spread measurement captures all channels from a single
acquisition and computes edge times on the host.
*Rationale:* an oscilloscope's `DELay` measurement takes two sources, so an
N-channel spread would need N-1 sequential measurements over different
acquisitions — which measures instrument repeatability as much as signal skew.
*Consequence:* correctness depends on the record being unclipped, which is why
clipping detection is a requirement rather than a nicety.

### AD-07 — Poll for acquisition completion rather than `*OPC?`
*Decision:* acquisition completion is detected by polling the instrument's busy
indication.
*Rationale:* on the TDS3000 family `*OPC?` returns when the command is parsed,
not when the acquisition finishes.

### AD-08 — Test intent as data, separated from the bench
*Decision:* the runner takes a declarative specification (what to do, what counts
as a pass) and a separate bench configuration (which instruments, where).
*Rationale:* limits and intent stay reviewable by a test engineer and trace
directly to a requirement, which is the reason for not writing bench tests as
scripts. Separating the bench makes a specification portable across rigs and
runnable against simulators unchanged.
*Consequence:* the runner needs a generic way to address a value inside a driver's
return type, which is `runner.resolve`. This is the price of the decision and is
confined to one small module.

### AD-09 — Failure and error are distinct throughout
*Decision:* a measurement outside its limit is a *failure*; a step that could not
execute is an *error*. The distinction is carried through result records, the
markdown report and JUnit XML.
*Rationale:* conflating them turns a broken rig into a pile of apparent product
defects, and hides real ones.

### AD-10 — A run against simulators is always disclosed
*Decision:* a run is flagged simulated when `--simulate` is used *or* when no
instrument on the bench is real hardware, and every report says so.
*Rationale:* a report is evidence. Simulated numbers presented without that
qualification would be read as hardware measurements.

## 5. Dynamic behaviour — a runner invocation

```
CLI            BenchRunner        Bench           Tek3014B        Transport
 |                  |               |                 |                |
 |- load_spec ----->|               |                 |                |
 |- load_bench ---->|               |                 |                |
 |- run(spec) ----->|               |                 |                |
 |                  |- require() -->|  (fail fast if an alias is absent)
 |                  |   setup steps:                  |                |
 |                  |- get("scope")->|- connect() --->|- open() ------>|
 |                  |- configure_channel(...) ------->|- write ------->|
 |                  |   per test, per step:           |                |
 |                  |- measure_channel_spread() ----->|- acquire,      |
 |                  |                                 |  capture,      |
 |                  |                                 |  analyse       |
 |                  |<- (waveforms, SpreadResult) ----|                |
 |                  |- resolve_path("1.spread")       |                |
 |                  |- Limit.check(scaled)            |                |
 |                  |   teardown steps, then close    |                |
 |<- RunRecord -----|- close() ----->|- close() ----->|- close() ----->|
 |- write_json / write_markdown / write_junit          |                |
```

## 6. Resource and performance characteristics

| Aspect | Value |
|---|---|
| Memory per captured channel | ~10 000 points as three Python lists, roughly 1 MB per channel. |
| Round trips per channel captured | 3 (`DATA:SOURCE`, batched preamble, `CURVe?`); the preamble is one compound query rather than seven. |
| Round trips per channel configured | 2 (one compound setup message, one error check). The error check is disableable. |
| Wire volume per 10 000-point record | ~10 kB binary versus ~50 kB ASCII. Binary is the default. |
| Instrument connections per run | One per alias actually used; connection is lazy. |

## 7. Interfaces to external elements

| Interface | Direction | Description |
|---|---|---|
| Ethernet / VXI-11 | bidirectional | ONC-RPC to instruments. |
| File system | in | Test specifications and bench configurations (JSON or YAML). |
| File system | out | CSV records, plots, hardcopy images, JSON/markdown/JUnit reports. |
| Process exit status | out | 0 pass, 1 failure or error, 2 usage — so the runner is usable directly as a CI step. |
| `pyyaml` | in | Optional; YAML specifications. JSON needs nothing. |
| `matplotlib` | out | Optional; host-side plots. |
| `pyvisa` | bidirectional | Optional; alternative transport. |
