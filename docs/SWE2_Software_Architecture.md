# SWE.2 — Software Architectural Design

| Field | Value |
|---|---|
| Document ID | TEK3014B-SWE2-001 |
| Version | 1.0 |
| Date | 2026-09-12 |
| Process reference | Automotive SPICE V4.0, SWE.2 Software Architectural Design |

## 1. Architectural drivers

| # | Driver | Consequence |
|---|---|---|
| D1 | VISA must be optional (STK-06, SWE1-NFR-001) | The protocol is implemented in-package, and the choice of protocol stack is pushed behind an abstraction so it becomes a deployment decision, not an architectural one. |
| D2 | Cross-channel timing must be trustworthy (SWE1-FR-062) | All channels are read from **one** acquisition; analysis operates on records, never on a live instrument, so it is deterministic and replayable. |
| D3 | Must be verifiable without hardware (SWE1-FR-090) | A test double is placed at the transport boundary — the widest seam that still exercises the SCPI vocabulary. |
| D4 | An invalid setting must not half-configure the instrument (SWE1-NFR-004) | Validation precedes transmission; a complete setup is sent as one compound message. |
| D5 | Optional features must not become mandatory weight (SWE1-NFR-003) | `matplotlib` and `pyvisa` are imported lazily, inside the functions that need them. |

## 2. Layering

```
                 +-------------------------------------------+
   Presentation  |  cli.py           __main__.py             |
                 +-------------------------------------------+
                                    |
                 +-------------------------------------------+
   Application   |  scope.Tek3014B                           |
                 |  SCPI vocabulary, validation, sequencing   |
                 +-------------------------------------------+
                        |                    |            |
        +---------------+          +---------+        +---+------------+
        |                          |                  |                |
 +--------------+        +------------------+   +-----------+   +-------------+
 |  waveform    |        |  measure         |   | plotting  |   | constants   |
 |  decode,     |        |  levels, edges,  |   | (lazy     |   | enums,      |
 |  scale, CSV  |        |  period, spread  |   | matplotlib|   | ModelLimits |
 +--------------+        +------------------+   +-----------+   +-------------+
        |                          |
        +------------+-------------+
                     |
     +-----------------------------------------------+
     |  transport.Transport  (abstract)              |
     |  buffered framing: read_message / read_exactly|
     |                     / read_raw                |
     +-----------------------------------------------+
        |             |              |             |
 +-----------+  +-----------+  +------------+  +----------+
 | Vxi11     |  | Socket    |  | Visa       |  | Mock     |
 | (stdlib   |  | (raw TCP) |  | (pyvisa,   |  | (-> simulator)
 |  ONC-RPC) |  |           |  |  optional) |  |          |
 +-----------+  +-----------+  +------------+  +----------+
        |                                            |
   [ instrument ]                            +-----------------+
                                             | simulator       |
                                             | SimulatedTDS3014B|
                                             +-----------------+
```

Dependencies point downwards only. `waveform` and `measure` have no knowledge of the
transport; `transport` has no knowledge of SCPI semantics beyond message framing.

## 3. Architectural elements

| ID | Element | Responsibility | Key interfaces |
|---|---|---|---|
| SWE2-ARC-001 | `scope.Tek3014B` | Owns the SCPI vocabulary, validates settings against `ModelLimits`, sequences acquisitions, converts responses into typed results. | `configure_channel`, `set_time_per_div`, `configure_edge_trigger`, `capture_single`, `measure`, `measure_channel_spread`, `screenshot` |
| SWE2-ARC-002 | `transport.Transport` | Abstract instrument link. Supplies buffered message framing on top of three subclass primitives (`_send`, `_recv_chunk`, open/close). | `write`, `read_message`, `read_exactly`, `read_raw`, `query`, `clear`, `read_stb` |
| SWE2-ARC-003 | Concrete transports | Four interchangeable implementations: `Vxi11Transport`, `SocketTransport`, `VisaTransport`, `MockTransport`, selected by `open_transport`. | per `Transport` |
| SWE2-ARC-004 | `waveform` | Data model. De-frames IEEE 488.2 blocks, decodes digitiser codes, scales to seconds and volts, exports CSV, detects clipping. | `Waveform`, `WaveformPreamble`, `parse_ieee_block` |
| SWE2-ARC-005 | `measure` | Pure analysis over `Waveform` objects: level estimation, interpolated edge detection, period statistics, N-channel spread. | `measure_period`, `measure_channel_spread`, `find_crossings` |
| SWE2-ARC-006 | `simulator` + `MockTransport` | Behavioural instrument model used as a test double at the transport boundary. | `SimulatedTDS3014B.respond` |
| SWE2-ARC-007 | `constants` | Single definition point for every SCPI mnemonic and the `ModelLimits` capability envelope. | enums, `TDS3014B_LIMITS` |
| SWE2-ARC-008 | `plotting` | Host-side rendering, with `matplotlib` imported lazily. | `plot_waveforms` |
| SWE2-ARC-009 | `cli` | Command-line front end producing JSON on stdout. | `main` |
| SWE2-ARC-010 | `errors` | Single typed exception hierarchy rooted at `Tek3014BError`. | exception classes |

## 4. Key architectural decisions

### AD-01 — Implement VXI-11 rather than depend on VISA
*Decision:* implement the ONC-RPC/VXI-11 core channel directly on the standard library.
*Rationale:* VXI-11 is an open published protocol; a VISA library is one implementation of
it. Implementing it removes a heavyweight, platform-specific, sometimes licensed
dependency from every test host, and makes the driver deployable in locked-down CI.
*Cost:* roughly 320 lines of protocol code that must itself be verified — addressed by
testing against an independently written RPC server and cross-checking against pyvisa-py.
*Alternatives rejected:* mandatory PyVISA (moves the dependency problem to every host);
raw socket (the instrument has no such service).

### AD-02 — Framing primitives in the base transport, not in each transport
*Decision:* subclasses supply `_recv_chunk() -> (data, end)`; the base class builds
`read_message`, `read_exactly` and `read_raw` on top.
*Rationale:* the three framing modes SCPI needs (terminator-delimited, length-delimited,
read-to-END) are identical across transports; only the notion of "end" differs. Writing
them once removes the most likely place for the transports to diverge in behaviour.

### AD-03 — Read binary blocks by declared length, not to end-of-message
*Decision:* `CURVe?` responses are read by consuming the IEEE 488.2 header and then exactly
the declared number of bytes.
*Rationale:* binary sample data can legitimately contain the terminator byte, and a raw
socket has no END indication at all. Reading by length is correct on every transport.
*Consequence:* the payload returned is already de-framed and must **not** be passed through
the block parser again — `Waveform.from_payload` exists for exactly this, distinct from
`Waveform.from_block`. (A defect of precisely this kind was found and fixed during
development; see the unit test report.)

### AD-04 — N-channel timing analysis host-side, from one acquisition
*Decision:* the spread measurement captures all channels from a single acquisition and
computes edge times on the host.
*Rationale:* the instrument's `DELay` measurement takes two sources, so an N-channel spread
would need N-1 sequential instrument measurements taken over different acquisitions — which
measures instrument repeatability as much as signal skew. One acquisition on a common time
base is the only way to get a meaningful figure. It is also deterministic and unit-testable.
*Consequence:* correctness depends on the record being unclipped, which is why clipping
detection (SWE1-FR-052) is a requirement rather than a nicety.

### AD-05 — Validate before transmitting
*Decision:* `ModelLimits` is checked before any byte is sent, and a complete channel setup
is emitted as one compound message.
*Rationale:* a partially applied setup is worse than a rejected one, because it is silent.

### AD-06 — Poll `BUSY?` rather than `*OPC?` for acquisition completion
*Decision:* acquisition completion is detected by polling `BUSY?`.
*Rationale:* on this instrument family `*OPC?` returns when the command is parsed, not when
the acquisition finishes, so it would report completion immediately.

### AD-07 — Test double at the transport boundary
*Decision:* the simulator sits behind `MockTransport`, not behind `Tek3014B`.
*Rationale:* it is the widest seam that still exercises the real SCPI command strings,
the real framing code and the real scaling arithmetic. A mock at a higher level would
leave the command vocabulary untested, which is precisely where silent failures live.
*Consequence:* the simulator computes measurements analytically from its signal model
rather than from the sampled record, so host-side analysis is checked against an
independent reference rather than against itself.

## 5. Dynamic behaviour — a capture-and-spread sequence

```
caller            Tek3014B          Transport         Instrument
  |                   |                  |                 |
  |-- configure_channel(1..4) ---------->|                 |
  |                   |-- validate ------|                 |
  |                   |-- "SELECT:CH1 ON;:CH1:SCALE ..." -->|
  |                   |-- "ALLEV?" ----------------------->|
  |                   |<----------------- no events -------|
  |-- configure_edge_trigger() --------->|                 |
  |-- measure_channel_spread([1,2,3,4]) |                 |
  |                   |-- "ACQUIRE:STOPAFTER SEQUENCE;:ACQUIRE:STATE RUN"
  |                   |-- "BUSY?" (poll until 0) --------->|
  |                   |   for each channel:                |
  |                   |     "DATA:SOURCE CHn"              |
  |                   |     "WFMPRE:XINCR?;:..."           |
  |                   |     "CURVE?"  -> read header,      |
  |                   |                  then N bytes      |
  |                   |-- scale to (s, V) ----------------|
  |                   |-- estimate levels, find edges,     |
  |                   |   interpolate, compute spread      |
  |<-- (waveforms, SpreadResult) --------|                 |
```

## 6. Resource and performance characteristics

| Aspect | Value |
|---|---|
| Memory per captured channel | ~10 000 points held as three Python lists (raw, times, volts), roughly 1 MB per channel. Acceptable for a host tool; a numpy path would be the optimisation if it ever matters. |
| Round trips per channel captured | 3 (`DATA:SOURCE`, batched preamble, `CURVe?`). The preamble is fetched as one compound query rather than seven. |
| Round trips per channel configured | 2 (one compound setup message, one `ALLEV?` error check). The error check is disableable via `auto_check_errors=False`. |
| Wire volume per 10 000-point record | ~10 kB binary (1-byte width), versus ~50 kB for ASCII. Binary is the default. |

## 7. Interfaces to external elements

| Interface | Direction | Description |
|---|---|---|
| Ethernet / VXI-11 | bidirectional | ONC-RPC to the instrument, per TEK3014B-VISA-001 §4. |
| File system | out | CSV records, PNG plots, hardcopy images, JSON results. |
| `matplotlib` | out | Optional, lazily imported, for host-side plots only. |
| `pyvisa` | bidirectional | Optional, lazily imported, alternative transport only. |
