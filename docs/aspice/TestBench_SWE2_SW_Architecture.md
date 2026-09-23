# Software Architecture Description

*Automotive SPICE® PAM v4.0 | SWE.2 Software Architectural Design*

---

## 1. Document Identification & Control

| Field | Value | Field | Value |
|---|---|---|---|
| **Document ID** | TB-SWE2-001 | **Version** | 0.2 |
| **Project** | TestBench | **Date** | 2026-09-23 |
| **Status** | Draft | **Classification** | Internal |
| **Author** | Claude | **Reviewer** | Dermot Murphy |
| **Approver** | Dermot Murphy | **Related Process** | SWE.2 |

> **Note — Reviewer independence (TB-DEV-002):** The Reviewer and Approver are the same person (Dermot Murphy). This is accepted under deviation record **TB-DEV-002** (`docs/aspice/TestBench_DEV002_Independent_Review_Deviation.md`) on the basis that TestBench has a single human team member.

---

## 2. Revision History

| Version | Date | Author | Description of Change |
|---|---|---|---|
| 0.1 | 2026-09-19 | Claude | Initial |
| 0.2 | 2026-09-23 | Claude | DMM-ARC-001 added: the TTi 1604 multimeter element. |

---

## 3. Purpose & Scope

### 3.1 Purpose

This document describes the software architecture of **TestBench**: the elements it is decomposed into, the dependencies permitted between them, and the decisions that shaped both. It refines TB-SWE1-001 and is the direct input to detailed design (TB-SWE3-001).

This document satisfies **Automotive SPICE® PAM v4.0, SWE.2 — Software Architectural Design**.

### 3.2 Referenced Documents

| Document ID | Title | Version |
|---|---|---|
| TB-SYS2-001 | TestBench System Requirements Specification | 0.1 |
| TB-SWE1-001 | TestBench Software Requirements Specification | 0.1 |
| TB-SWE2-001 | TestBench Software Architecture Description | 0.1 |
| TB-SWE3-001 | TestBench Software Detailed Design | 0.1 |
| TB-RTM-001 | TestBench Requirements Traceability Matrix | 0.1 |

---

## 4. Architectural drivers

| # | Driver | Consequence |
|---|---|---|
| D1 | VISA must be optional (STK-06, CORE-NFR-001) | The VXI-11 protocol is implemented in-package, and the choice of protocol stack is pushed behind an abstraction, making it a deployment decision rather than an architectural one. |
| D2 | More instruments are coming (STK-07): power supplies and loads, DMMs, signal sources, logic and protocol analysers, BLE and RF | Everything not specific to one instrument is factored into a shared core. Transports and drivers are held in registries so new ones are added without modifying existing code. |
| D3 | A bench runner must drive the tools (STK-08) | Test intent lives in data, not code. The runner depends on drivers through a uniform base class, never on any specific one. |
| D4 | Cross-channel timing must be trustworthy (ANA-FR-016) | All channels are read from one acquisition; analysis operates on records, never on a live instrument, so it is deterministic and replayable. |
| D5 | Must be verifiable without hardware (SCOPE-FR-090, RUN-FR-005) | A test double sits at the transport boundary — the widest seam that still exercises the SCPI vocabulary — and a simulator harness is shared so each instrument writes only its own behaviour. |
| D6b | Not every bench instrument speaks SCPI (STK-09, and STK-14 to come) | The instrument lifecycle is separated from the SCPI vocabulary: `Instrument` carries connect/initialise/close/identify/simulate, `ScpiInstrument` adds 488.2 and SCPI. The runner depends only on the former, so a debug probe or a BLE dongle is a bench instrument on equal terms. |
| D7 | The probe must be reachable from a container (STK-11, JLINK-NFR-003) | Both links to the probe are TCP: GDB/MI to the J-Link GDB Server and RTT to its RTT port. Nothing in the driver requires the probe to be on the same host, and the driver refuses to spawn a server on a host that is not local. |
| D8 | Timing figures must be defensible (JLINK-FR-065, JLINK-NFR-004) | Timing is a strategy with four implementations of differing resolution and intrusiveness. A result carries its method, its resolution and whether it halted the target, and flags itself when the interval is too small for the method used. |
| D10 | One instrument is partly embedded software (STK-16) | The dongle's firmware and its host driver are one architectural element with one interface artefact, `protocol.h`, that both are built from and that a test parses. The alternative - two elements and a prose protocol - is how firmware and host drift apart. |
| D11 | A radio measurement cannot be timed from the host (STK-14, STK-15) | Timestamps are taken in the dongle's radio event handler on a 1 us clock, and the host's own arrival time is carried beside them as a cross-check rather than as the measurement. USB contributes about a millisecond, which is the same order as a 20 ms advertising interval. |
| D9 | Tests may later be authored in Markdown and run under Robot Framework (STK-12) | The driver boundary returns plain types and dataclasses of plain types, never objects a keyword layer would have to unwrap. Test intent already lives in data (D3), so a translator becomes a front end to the existing runner rather than a second execution engine. |
| D6 | An invalid setting must not half-configure an instrument (CORE-NFR-004) | Validation precedes transmission; a complete setup is sent as one compound message. |

## 5. Layering

```
   +--------------------------------------------------------------+
   |  benchtools.runner                                           |
   |  spec -> bench -> runner -> results -> report   +  cli       |
   +--------------------------------------------------------------+
                        |                    |
   +--------------------------------------------------------------+
   |  benchtools.instruments                                      |
   |  tek3014b (scope, constants, simulator, cli)                 |
   |  jlink    (probe, gdbmi, session, server, rtt, swo,          |
   |            timing, constants, simulator, cli)                |
   |  nordic_dongle (dongle, protocol, session, profile,          |
   |            latency, constants, simulator, cli)               |
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
   |  instrument (Instrument: lifecycle, identity, simulate)      |
   |  scpi (ScpiInstrument, 488.2 blocks)                         |
   |  simulator (SimulatedInstrument, Responder)                  |
   |  enums   validation   errors                                 |
   |  transport: base / vxi11 / socket_raw / visa_backend /        |
   |             process / serial_port / mock / factory (registry)|
   +--------------------------------------------------------------+
            |                  |                       |
    [ instrument ]   [ J-Link GDB Server ]    [ USB CDC ]
                       |            |               |
                  [ probe ] --- [ target ]   [ dongle firmware ]
                                                    | radio
                                              [ BLE sensor ]
```

Dependencies point one way only: **core, then analysis, then instruments, then
runner**. This is not merely a convention — it is enforced by
`tests/test_layering.py`, which parses every module's imports and fails the build
on a violation. The core is additionally checked to contain no reference to any
instrument, and to be importable without importing any other element.

## 6. Architectural elements

| ID | Element | Responsibility | Key interfaces |
|---|---|---|---|
| CORE-ARC-006 | `core.instrument.Instrument` | The instrument lifecycle, independent of command language: open, initialise, close, context manager, cached identity, declared simulator class, overridable event queue. The runner depends on this and on nothing below it. | `connect`, `initialise`, `close`, `identify`, `read_event_queue`, `check_errors`, `SIMULATOR_CLASS` |
| CORE-ARC-001 | `core.scpi.ScpiInstrument` | Extends CORE-ARC-006 with SCPI: command and query primitives, `*IDN?` parsing, IEEE 488.2 operations, `SYSTem:ERRor?` polling, 488.2 block codec. Every SCPI driver subclasses it. | `_command`, `_query`, `_query_float`, `reset`, `parse_ieee_block` |
| CORE-ARC-002 | `core.transport.Transport` | Abstract instrument link with buffered message framing built on three subclass primitives. | `write`, `read_message`, `read_exactly`, `read_raw`, `query`, `clear` |
| CORE-ARC-003 | Concrete transports and the factory | Four interchangeable transports selected by resource string, held in a registry so a new link type registers itself. | `open_transport`, `parse_resource`, `register_backend` |
| CORE-ARC-004 | `core.simulator.SimulatedInstrument` | Shared simulator harness: dispatch, compound messages, 488.2 queries, event queue, binary replies. `Responder` is the protocol the mock transport accepts. | `respond`, `handle`, `_cmd_*`, `push_event` |
| CORE-ARC-007 | `core.firmware` | What a build system recorded about an image, read from the manifest beside it. Here rather than in an instrument because two need it and neither may import the other (AD-22): the dongle reads one to decide whether to refresh itself, the debug probe to say what it just flashed. | `FirmwareBuild`, `MANIFEST_NAME`, `parse_build_date` |
| CORE-ARC-005 | `core.validation`, `core.enums`, `core.errors` | Range and channel validation, the SCPI enumeration base, and the single exception hierarchy. | `validate_range`, `ScpiEnum`, `BenchToolsError` |
| ANA-ARC-001 | `analysis.waveform` | Data model: decode digitiser codes, scale to seconds and volts, detect clipping, export CSV. | `Waveform`, `WaveformPreamble` |
| ANA-ARC-002 | `analysis.measure`, `analysis.plotting` | Pure analysis over `Waveform` objects, and host-side rendering. | `measure_channel_spread`, `measure_period`, `plot_waveforms` |
| INST-ARC-001 | `instruments.*` | One subpackage per instrument, adding only its command vocabulary, capability envelope and simulator. | per `ScpiInstrument` |
| SCOPE-ARC-001 | `instruments.tek3014b` | The TDS3000 SCPI vocabulary and the oscilloscope's capability envelope. | `Tek3014B` |
| BLE-ARC-001 | `instruments.nordic_dongle` **and** `firmware/nordic_dongle` | The BLE bench dongle, as one element across two languages. Host side: the line protocol (`protocol`), the command/event session with its log (`session`), advertising statistics (`profile`), latency statistics (`latency`), command documents read and run (`script`, AD-23), the driver façade (`dongle`) and a simulated dongle. Dongle side: USB CDC line transport, command dispatch, scanner, UART client and the microsecond clock. `include/protocol.h` is the interface both are built from. | `NordicDongle`, `DongleSession`, `AdvertisingProfile`, `ResponseTiming`, `SimulatedDongle`; `cmd_parser_handle`, `scanner_on_ble_evt`, `nus_client_command` |
| JLINK-ARC-001 | `instruments.jlink` | The debug probe driver. `JLinkProbe` is the façade over seven collaborators, each independently testable: MI record parsing (`gdbmi`), the command/response session (`session`), server discovery and lifetime (`server`), RTT (`rtt`), ITM/SWO decoding (`swo`), timing results (`timing`), and the probe and target envelope (`constants`). Its simulator answers the MI dialogue. | `JLinkProbe`, `GdbMiSession`, `RttClient`, `ItmDecoder`, `TimingResult`, `GdbServer` |
| S2LP-ARC-001 | `instruments.s2lp` | The ST S2-LP development kit, host side only: ST's firmware runs on the board (AD-20). The line protocol (`protocol`), the command/reply session with its raw log (`session`), the device's register map (`registers`), packet records and their structured log (`packets`), the driver façade (`s2lp`) and a simulated kit with a register file and a modelled air interface. | `S2lpDevkit`, `S2lpSession`, `Register`, `Packet`, `Capture`, `SimulatedS2lp` |
| PSU-ARC-001 | `instruments.gpd3303d` | The GW Instek bench supply, programmable channels 1 and 2; its fixed rail is a front-panel switch and is outside the element. Not a SCPI instrument: it takes the transport and lifecycle from `ScpiInstrument` and replaces the SCPI-specific parts (`*CLS`, `*RST`, `SYSTem:ERRor?`) with its own. Its own command grammar, a load-modelling simulator, and a command line. | `Gpd3303D`, `ChannelReading`, `SupplyStatus`, `SimulatedGpd` |
| DMM-ARC-001 | `instruments.tti1604` | The TTi 1604 bench multimeter, on an opto-isolated RS-232 link. Not a SCPI instrument and not close to one: no command language, no query, no `*IDN?`, no error queue. The link carries single characters standing for key presses, and the meter streams a ten-byte binary frame per measurement. Frame decoding (`protocol`) is pure and separate from the link, because decoding is where a wrong number comes from and it should be testable without a meter. The instrument envelope and protocol facts (`constants`), the driver façade (`dmm`), a behavioural simulator and a command line. | `Tti1604`, `Reading`, `FrameAssembler`, `decode`, `SimulatedTti1604` |
| RUN-ARC-001 | `runner` | Specification model, bench resolution, execution engine, result records, report writers, command line. | `load_spec`, `BenchConfig`, `BenchRunner`, `write_*` |

## 7. Key architectural decisions

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

### AD-11 — The instrument lifecycle is separated from the SCPI vocabulary

**Context.** `ScpiInstrument` carried both the lifecycle every driver needs
(connect, initialise, close, identify, simulate, check errors) and the SCPI
specifics (`*IDN?`, `*CLS`, `SYSTem:ERRor?`, 488.2 blocks). The runner depended on
that class, so "bench instrument" meant "SCPI instrument".

**Decision.** Split it. `core.instrument.Instrument` holds the lifecycle and knows
nothing of any command language; `ScpiInstrument` subclasses it and adds SCPI. The
runner's driver registry is typed on `Instrument`.

**Consequences.** A debug probe is a bench instrument without pretending to speak
SCPI — no stub `*IDN?`, no empty error queue implementation. The BLE dongle and the
RS-232 multimeter to come will need exactly the same seam. The cost is one more
class in the hierarchy, and identity parsing moving to the SCPI layer where it
belongs: `InstrumentIdentity.from_idn()` is IEEE 488.2, so it is not in the generic
constructor, and a non-SCPI driver populates the fields itself.

**Alternatives rejected.** Making the probe a `ScpiInstrument` with stubbed SCPI
would have put lies in the type. A separate `Probe` hierarchy alongside
`ScpiInstrument` would have forced the runner to know which kind it holds.

### AD-12 — Drive the probe through the J-Link GDB Server and GDB/MI

**Context.** Three ways to reach a J-Link: the `JLinkARM` DLL through `ctypes` (or
`pylink-square`), the server's telnet/`monitor` interface, or the GDB Server with a
GDB speaking the machine interface.

**Decision.** GDB/MI through the J-Link GDB Server, with `monitor` commands for the
probe-specific operations that have no MI equivalent.

**Consequences.** Symbolic operations — a breakpoint at `sensor.c:75`, the value of
`sensor_mv`, a call stack with file and line — come from GDB's DWARF reader, which
is the requirement (JLINK-FR-041, -045) and is a large amount of code not to write.
Both links are TCP, which is what makes D7 achievable. MI is a stable, documented,
versioned interface, unlike the DLL's ABI. The costs: two processes to manage
instead of none, an MI parser to write and test (`gdbmi`, 37 tests), and asynchronous
records that can arrive at any moment — handled by draining the transport before
each command rather than discarding whatever is buffered.

**Alternatives rejected.** The DLL is the shortest path to memory and flash but has
no symbol knowledge, would have to be shipped per platform, and is a native library
inside a container. `pylink-square` is a third-party dependency (CORE-NFR-001,
JLINK-NFR-001) and still has no DWARF reader.

### AD-13 — Both links to the probe are TCP, so the bench containerises

**Context.** The whole bench is to move into Docker (STK-11), but a probe is a USB
device and USB pass-through into a container is awkward and host-specific.

**Decision.** The driver reaches the probe only over TCP: GDB/MI to the GDB Server's
port and RTT to its RTT port. `jlink://host:port` attaches to a server anywhere. The
driver spawns a server only when the target is local, and refuses otherwise with a
diagnostic saying so.

**Consequences.** The container needs no USB access and no J-Link software: the
server runs on the machine the probe is plugged into — which is also the Windows PC
of the first deployment — and the container connects to it. Nothing has to change
when the bench is containerised, which is why this decision is taken now rather
than then. The cost is that a stale server on the expected port is used rather than
replaced; this is deliberate, since a server the driver did not start is also a
server it must not kill (JLINK-FR-005).

### AD-14 — Four timing methods, each reporting its own resolution

**Context.** "Measure the time between two lines of code" has no single correct
implementation. A cycle counter is exact but halts the core; the host clock works
anywhere but resolves milliseconds; SWO does not halt but needs trace wiring; a
target timer is exact but needs firmware cooperation.

**Decision.** Implement all four behind one call with a selectable method. Every
result carries the method, the resolution of that method, whether it halted the
target, and a `is_trustworthy` flag that is false when the interval is not at least
an order of magnitude above the resolution.

**Consequences.** The caller chooses the trade-off knowingly, and a measurement can
never be quoted without the means by which it was obtained (JLINK-NFR-004). This is
an evidence-integrity property, not a convenience: the host-clock method returns
about 93 µs for a 1 ms interval in the simulated bench, and the flag is what stops
that figure being read as a measurement.

**Alternatives rejected.** Picking one method would have made the driver unusable on
some targets. Choosing automatically would have hidden which one ran, and with it
the resolution the number should be read at.

### AD-15 — Plain types at the driver boundary, for a keyword layer later

**Context.** Tests may be authored in Markdown and translated to Robot Framework
(STK-12). Robot keywords exchange strings and simple values.

**Decision.** Every probe operation returns a plain type or a dataclass of plain
types — `VerifyResult`, `FlashResult`, `HaltInfo`, `StackFrame`, `TimingResult` with
`as_dict()`. No operation returns a live handle the caller must manage, and every
one is reachable through the declarative runner's dotted method paths.

**Consequences.** A Robot keyword library, or a Markdown translator, is a thin front
end over the same runner; neither needs driver-specific glue. The CLI already
demonstrates it by emitting JSON. No Robot dependency is taken in this revision, so
the decision costs nothing if that path is not followed.

### AD-16 — Firmware and driver are one element with one interface artefact

**Context.** The dongle needs custom firmware: nothing off the shelf timestamps
an advertising report at the radio and reports it over USB in a form a test can
assert on. That makes part of this item embedded C, in a different language and
a different build, changed by different tools.

**Decision.** Treat the dongle firmware and its host driver as **one**
architectural element (BLE-ARC-001), with `firmware/nordic_dongle/include/protocol.h`
as the sole definition of what passes between them. The firmware builds its
command table from that header; the host driver mirrors it in `constants.py`;
and `test_firmware_protocol.py` parses the header and fails the build if the two
disagree about a command, an event, an error code or a size limit.

**Consequences.** A command added to one side and forgotten on the other is a red
test rather than "unknown command" at a bench six weeks later. The firmware also
comes under the same traceability rules as the Python: every C file carries its
`Traces to:` line, and the same test checks that, that no file allocates
dynamically, and that the house indentation holds. The cost is that the header
must stay free of anything that is merely an internal firmware choice - hence
`app_ble_config.h` beside it for the things the host has no business knowing.

**Alternatives rejected.** A separate `FW-` element with its own document set
would double the paperwork for one interface. Nordic's stock `ble_connectivity`
firmware with `pc-ble-driver-py` on the host would have removed the firmware
entirely, but it puts the BLE stack on the *host* side of the USB link, so every
timestamp would carry USB jitter - which is precisely the measurement this
element exists to avoid (AD-17).

### AD-17 — Timestamps are taken in the dongle, and the host's are kept beside them

**Context.** An advertising interval is 20 ms to 10 s; a connection interval is
7.5 ms to 4 s. USB polling plus host scheduling contributes roughly a
millisecond, with millisecond-scale jitter.

**Decision.** Every event carries `t=`, a microsecond timestamp taken in the
dongle's radio event handler from a TIMER peripheral, extended to 64 bits. The
host records its own arrival time in the `Event`, and every latency result
carries a `LatencySource` saying which clock produced it.

**Consequences.** Interval statistics are about the sensor. The host figures are
kept, not discarded, because the difference between the two *is* the overhead of
the host link, and a bench that cannot see that overhead cannot tell a slow
sensor from a busy host. `ResponseTiming.is_trustworthy` is false when a figure
is inside the connection interval, for the same reason the J-Link driver flags a
figure inside its clock's resolution (AD-14): a number that cannot be
distinguished from the instrument's own floor is not a measurement of the thing
under test.

### AD-18 — Filter in the firmware, count in both places

**Context.** A busy room produces hundreds of advertising reports a second. The
USB link and the host both have limits, and dropping reports silently would show
up as a sensor that skipped beacons.

**Decision.** Address and name filtering happen in the firmware, before anything
is sent. The firmware counts what the radio delivered and what it managed to
send; the host counts what it received. `AdvertisingProfile.is_complete`
compares them, and a profile computed from a lossy stream says so.

**Consequences.** A missed advertising event can be attributed to the sensor
rather than the plumbing - or explicitly cannot be, which is the honest
alternative. The firmware's outgoing queue drops whole lines and counts them
rather than truncating one, because half a line would be a parse error in the
host and would look like a protocol fault rather than congestion.

### AD-19 — Emulate per-channel output, and say so at every turn

**Context.** The GPD-3303D has one output switch for two channels. A bench
specification, and every other supply driver, wants per-channel control.

**Decision.** The driver presents `output_on(channel)` and
`output_off(channel)`, implemented by programming the channel to zero volts and
remembering its setpoint. The supply's real switch is opened only when *every*
channel has been switched off, so "all off" means off. The emulation is stated
in the method's own docstring, in the command line's output, and in the notes:
a channel switched off this way is at 0 V with its current limit unchanged, not
open circuit.

**Alternatives.** Exposing only the global switch would have been the most
honest interface and the least usable one: a two-rail test would have to drive
the two channels as one. Hiding the emulation entirely would have been usable
and dangerous - somebody would eventually use `output_off` as an interlock.

**Consequences.** A channel that is "off" will still sink current from a board
powered by something else, and cannot be used as a safety measure. In exchange,
a specification written against this supply reads like one written against a
two-channel supply, and the one place the abstraction leaks is documented
wherever a caller will meet it. The parked setpoint is driver state, not
instrument state: a second program talking to the same supply does not know
about it, which is why the driver reads the hardware rather than its own
bookkeeping wherever the hardware can answer.

### AD-20 — Use the vendor's firmware where the vendor already provides one

**Context.** The S2-LP development kit is driven by ST's GUI through firmware ST
ships for it: a CLI application over the kit's USB serial port, with commands for
SPI register access, radio configuration, transmit and receive. The BLE dongle in
this repository has firmware of our own (AD-16), so the precedent pulled the
other way.

**Decision.** Use ST's firmware unchanged, and write only the host driver. The
firmware's command set becomes an **external interface** to this project rather
than something it controls: it is written down in `constants.COMMANDS`, and every
command the driver sends is checked against it.

**Why this is not AD-16.** The dongle's firmware exists because a radio event
must be timestamped on the radio's side of a USB link, and no stock firmware did
that. Here the requirement is register access, transmit, receive and logging -
all of which ST's firmware already does, and none of which is made more accurate
by being reimplemented. Writing firmware would have added a build, a flashing
procedure, a licence question and a second thing to keep in step with the
datasheet, in exchange for nothing the measurement needs.

**Consequences.** The kit works with the firmware it arrives with, and with ST's
GUI, and nothing has to be flashed before a bench session. In exchange this
element inherits the firmware's limits and cannot fix them: reception is polled,
so the radio is deaf between calls; timestamps are the motherboard's
millisecond timer; and the command set is what it is. The driver's job is
therefore to be **honest about those limits** rather than to hide them - hence
the re-arm count carried in every capture (S2LP-FR-033) and the millisecond
resolution stated wherever a board timestamp is reported.

**Licence.** ST's package is under SLA0072, a limited licence, not a permissive
one. Interoperating with the protocol is not redistribution; vendoring the
source would be. No ST source is in this repository, and the register map holds
facts about the silicon rather than vendor prose (S2LP-NFR-002).

### AD-21 — Refuse what a tracking supply would discard, rather than report it

**Context.** The GPD-3303D's front panel selects independent, series or parallel
tracking. In series and parallel the supply drives CH2 from CH1 and **accepts
and discards** anything addressed to CH2: no error, nothing in `STATUS?`, and
`VSET2?` answering with CH1's setting. The same is true of the emulated
per-channel switch of AD-19, which is built on programming a channel to zero.

**Decision.** The driver reads the mode at the moment of the write and raises
for a setpoint or per-channel switch addressed to the slaved channel, naming the
mode and what to do instead. Channel 1 is untouched - it is the master in both
modes - and the global switch and the safe state stay operable in every mode,
because a safe state must never be unreachable. A mode the status word does not
decode is warned about and allowed: the bit order is a confirmation item
(PSU-OPEN-01, PSU-OPEN-06), and one unconfirmed bit should not leave the driver
unable to set anything. `TRACK<n>` is never sent: which rails are tied together
is a wiring decision, and changing it from a test script could put a board
across two channels in series at twice the voltage the operator set up.

**Alternatives.** Reporting the mode and passing the write through was the
previous behaviour, inherited from the two-channel GPD-2303S where it was
harmless. It is the exact shape of D-30 and D-31: a command that appears to
succeed and changes nothing. Caching the mode at connect was rejected because it
is a switch a person can move between two commands.

**Consequences.** A specification written for independent operation fails
immediately and legibly on a supply someone left in series, instead of
configuring a rail that was never configured. The cost is one `STATUS?` query
before each write to the slaved channel, which is 50 ms on a paced link, and
only on that channel.

### AD-22 — A specification carries values between steps rather than repeating them

**Context.** The first test of a bench session is a chain: power the board,
program it, read the identifier the part was programmed with at manufacture,
find that board over the air by it, and confirm it reports the version that was
just flashed onto it. Until now a step's result could be saved and nothing could
read it, so every one of those facts would have had to be written into the
specification.

**Decision.** `save:` keeps a step's result; `{from: <name>}` takes it in any
later step, as an argument or as a limit, with an optional `format` template for
when the thing on the wire is a rendering of the value rather than the value
(RUN-FR-016). Limits gained exact comparison against text, because a version and
a device name are not numbers (RUN-FR-024), and the reader of a build manifest
moved into the core so the debug probe can say what it flashed without importing
the dongle (CORE-FR-050, CORE-DD-FIRMWARE).

**Alternatives.** Writing the identifier and the version into the specification
was the alternative, and it fails in a specific way: the test asserts its own
input. It passes against the wrong board, because the identifier it looks for is
the one it was told to look for; and it goes stale silently the day someone
rebuilds the firmware. Letting a specification carry arbitrary expressions was
rejected for the reason specifications are data at all (AD-08): a reviewer must
be able to read one without reading code.

**Consequences.** A chained test states relationships between facts the bench
establishes, rather than restating constants. The cost is that a reference
cannot be checked when the specification is loaded - what `build.version` refers
to does not exist until that step has run - so an unresolvable reference is a
run-time error, and it names every value that *has* been saved.

### AD-23 — The document that specifies a command set is the test of it

**Context.** A sensor's command set is written down long before anyone tests
it. Turning that document into a test means copying the commands into a
specification, which makes two things that must agree - and they stop agreeing
the first time someone adds a command to one of them. STK-12 asked for tests
that come from a markdown document; CON-06 deferred the general question of
adopting Robot Framework for it.

**Decision.** The driver reads the document directly
(BLE-DD-SCRIPT, BLE-FR-100 … -108): a heading per test, a table of step number,
command and expected response. Running it produces a result per row - what was
sent, what came back, what was expected, how long the exchange took and whether
it passed - and a run passes when no step failed. The specification that runs
it is four lines, and holds no commands at all.

**Alternatives.** A new construct in the specification language - a step that
iterates a table - was rejected because it puts the commands back in the
specification, in a second format. Robot Framework remains undecided (CON-06,
OPEN-04) and is not needed for this: what STK-12 wanted here was a document a
test engineer maintains, not a framework.

**Consequences.** The document is maintained by whoever owns the command set,
and the test follows it without a code change. In exchange the document must be
strict about its own shape - an unreadable row is refused naming the line,
because a row skipped quietly is a command nobody tested and nobody missed - and
the three step kinds must stay distinguishable in the report: a step that was
skipped must never read as one that passed, which is why a run states how many
steps it checked as well as how many passed.

## 8. Dynamic behaviour — a runner invocation

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

## 9. Resource and performance characteristics

| Aspect | Value |
|---|---|
| Memory per captured channel | ~10 000 points as three Python lists, roughly 1 MB per channel. |
| Round trips per channel captured | 3 (`DATA:SOURCE`, batched preamble, `CURVe?`); the preamble is one compound query rather than seven. |
| Round trips per channel configured | 2 (one compound setup message, one error check). The error check is disableable. |
| Wire volume per 10 000-point record | ~10 kB binary versus ~50 kB ASCII. Binary is the default. |
| Instrument connections per run | One per alias actually used; connection is lazy. |
| Processes per probe connection | Two at most: the GDB Server (only if not already listening) and one GDB. |
| Round trips per probe halt/read/resume | 3 MI commands; a variable read is 1. Memory is chunked at the probe's maximum transfer size (64 kB). |
| Advertising reports per second, one sensor | 3 channels at the advertising rate; at 20 ms that is up to 150 lines/s, about 20 kB/s over USB. |
| Dongle event queue | 32 lines. Above that, lines are dropped and counted rather than truncated. |
| Host event backlog | 4096 events, bounded so an unattended session cannot grow without limit. |
| Cost of a halting timing measurement | Two breakpoint stops per repetition; the target is stopped for the duration, which is why JLINK-FR-064 exists. |

## 10. Interfaces to external elements

| Interface | Direction | Description |
|---|---|---|
| Ethernet / VXI-11 | bidirectional | ONC-RPC to instruments. |
| File system | in | Test specifications and bench configurations (JSON or YAML). |
| File system | out | CSV records, plots, hardcopy images, JSON/markdown/JUnit reports. |
| Process exit status | out | 0 pass, 1 failure or error, 2 usage — so the runner is usable directly as a CI step. |
| `pyyaml` | in | Optional; YAML specifications. JSON needs nothing. |
| `matplotlib` | out | Optional; host-side plots. |
| `pyvisa` | bidirectional | Optional; alternative transport. |
| J-Link GDB Server | bidirectional | TCP: GDB/MI via GDB on port 2331, RTT on 19021, SWO on 2332. May be on another host. |
| `arm-none-eabi-gdb` | bidirectional | Child process over stdin/stdout, speaking GDB/MI. Required for the J-Link driver only. |
| SWD / JTAG | bidirectional | Probe to target, below the GDB Server; not visible to this software. |
| USB CDC (serial) | bidirectional | The BLE dongle's line protocol. May be a local port or one published over TCP by a terminal server, which is how a container reaches a dongle on another machine. |
| Bluetooth Low Energy | bidirectional | Dongle to sensor: advertising reports in, UART service both ways. Below the dongle firmware; not visible to the host driver except as events. |
| `pyserial` | bidirectional | Optional; the serial transport. |
| nRF5 SDK 17.1.0 + S140 | in | Builds the dongle firmware. Not needed to run the host driver or the tests. |

---

## 11. Review & Approval

| Role | Name | Signature / Electronic Approval | Date |
|---|---|---|---|
| Author | Claude | Approved | 2026-09-19 |
| Technical Reviewer | Dermot Murphy | — | *pending* |
| Quality Assurance | Dermot Murphy | — | *pending* |
| Approver | Dermot Murphy | — | *pending* |

> **Note:** This document is under configuration management (SUP.8). Post-approval changes require a change request (SUP.10) and a new document version.
