# SWE.1 — Software Requirements Specification

| Field | Value |
|---|---|
| Document ID | BENCHTOOLS-SWE1-001 |
| Version | 2.0 |
| Date | 2026-09-13 |
| Process reference | Automotive SPICE V4.0, SWE.1 Software Requirements Analysis |
| Item | **BenchTools** — bench test tooling (`benchtools` 2.0.0) |

## 1. Scope

BenchTools is host-side software for automated and semi-automated electronics
bench testing. It provides instrument drivers, analysis of captured records, and
a declarative test runner that drives a bench of instruments and produces
pass/fail evidence.

It is a **test tool**: it is not part of any delivered vehicle software and
carries no ASIL classification. It is developed to this process discipline
because measurement results derived from it are used as evidence.

Out of scope: instrument firmware, GPIB and RS-232 interfaces, hardware fixture
design, and any instrument not listed in §5.

## 2. Stakeholder requirements

| ID | Requirement |
|---|---|
| STK-01 | Interface to a Tektronix TDS3014B oscilloscope over Ethernet. |
| STK-02 | Enable up to four oscilloscope channels. |
| STK-03 | Set screen position and volts per division for each channel. |
| STK-04 | Trigger the instrument and capture a plot. |
| STK-05 | Take measurements, for example period, and the spread in time of a number of channels going high. |
| STK-06 | Determine whether VISA must be used. |
| STK-07 | Host further instrument tools in the same repository, sharing common code. |
| STK-08 | Provide an overall bench test runner that drives those tools. |

## 3. Element structure

Requirements are grouped by the element that implements them. Identifier
prefixes are per element so they stay unique as instruments are added.

| Prefix | Element | Rationale for being separate |
|---|---|---|
| `CORE-` | `benchtools.core` | Shared by every instrument: the link, SCPI plumbing, validation, simulator harness. Must contain nothing instrument-specific. |
| `ANA-` | `benchtools.analysis` | Operates on captured records, not live instruments, so it is deterministic and replayable. |
| `INST-` | `benchtools.instruments` | Requirements common to all drivers. |
| `SCOPE-` | `benchtools.instruments.tek3014b` | The oscilloscope driver. |
| `RUN-` | `benchtools.runner` | The bench test runner. |

---

## 4. CORE — instrument-agnostic foundations

### 4.1 Instrument link

| ID | Requirement | Source | Verification |
|---|---|---|---|
| CORE-FR-001 | The link layer shall establish a connection to an instrument using the VXI-11 TCP/IP Instrument Protocol over ONC-RPC, implemented without any third-party library. | STK-01, STK-06 | Test |
| CORE-FR-002 | The link layer shall discover the VXI-11 core channel port via the instrument's portmapper (TCP, falling back to UDP), and shall accept an explicit port override. | STK-01 | Test |
| CORE-FR-003 | The link layer shall provide a raw TCP socket transport for instruments that expose a SCPI socket. | STK-01, STK-07 | Test |
| CORE-FR-004 | The link layer shall provide an in-process transport driven by a simulated instrument, and shall not depend on any particular instrument's simulator. | STK-07 | Test |
| CORE-FR-005 | The link layer shall provide message framing for terminator-delimited responses, length-delimited binary blocks, and responses bounded only by end-of-message. | STK-01 | Test |
| CORE-FR-006 | The link layer shall provide an optional transport that delegates to a VISA library, which shall not be required for normal operation. | STK-06 | Test |
| CORE-FR-007 | The link layer shall transfer messages of arbitrary length, chunking writes to the link's negotiated maximum and reassembling chunked responses. | STK-01 | Test |
| CORE-FR-008 | The link layer shall probe the VXI-11 logical device names used by both VXI-11.2 and VXI-11.3 devices, and shall report which was accepted. | STK-01 | Test |
| CORE-FR-010 | Transport backends and resource-string schemes shall be held in registries, so a new link type can be added from its own module without modifying the factory. | STK-07 | Test, Inspection |
| CORE-FR-011 | The link layer shall accept a host name, an IPv4 address, or a VISA-style resource string, and shall select a transport automatically. | STK-01 | Test |

### 4.2 SCPI instrument base

| ID | Requirement | Source | Verification |
|---|---|---|---|
| CORE-FR-020 | A common base shall provide the link lifecycle: connect, initialise to a known communication state, close, and use as a context manager. | STK-07 | Test |
| CORE-FR-021 | The base shall provide command and query primitives, including typed scalar queries and compound multi-field queries. | STK-07 | Test |
| CORE-FR-022 | The base shall parse and cache the ``*IDN?`` response into manufacturer, model, serial number and firmware, and shall degrade rather than fail on a response with fewer fields. | STK-07 | Test |
| CORE-FR-023 | The base shall provide the IEEE 488.2 mandated operations: reset, clear status, operation complete, event status register. | STK-07 | Test |
| CORE-FR-024 | The base shall read the instrument's error queue and raise if any event was reported. The default implementation shall follow SCPI-1999 ``SYSTem:ERRor?``, and shall be overridable for instrument families that differ. | STK-07 | Test |
| CORE-FR-025 | Error queue polling shall be bounded, so a stuck queue cannot hang the caller. | STK-07 | Test |
| CORE-FR-026 | Connecting shall not reset the instrument's front-panel setup. | STK-01 | Test |
| CORE-FR-027 | The base shall encode and decode IEEE 488.2 definite- and indefinite-length arbitrary block data, for use by waveform transfer, trace transfer and bulk upload. | STK-04, STK-07 | Test |
| CORE-FR-028 | The base shall provide raw command and query access, for instrument features a driver does not wrap. | STK-07 | Test |

### 4.3 Validation and shared types

| ID | Requirement | Source | Verification |
|---|---|---|---|
| CORE-FR-030 | A shared enumeration base shall accept a member, a member name or a SCPI mnemonic, case-insensitively, and shall reject anything else with a message listing the valid values. | STK-07 | Test |
| CORE-FR-031 | Shared validation shall check ranges, channel availability and enumerated choices, raising a message that names the setting, the offending value, the permitted range and the unit. | STK-03, STK-07 | Test |

### 4.4 Simulator harness

| ID | Requirement | Source | Verification |
|---|---|---|---|
| CORE-FR-040 | A shared simulator harness shall provide SCPI message dispatch, compound-message splitting, the IEEE 488.2 mandated queries, an event queue and binary replies, so each instrument's simulator implements only its own behaviour. | STK-07 | Test |
| CORE-FR-041 | An unrecognised command shall be recorded in the simulated event queue rather than ignored, so that a driver which misspells a command fails a test instead of passing silently. | STK-07 | Test |

### 4.5 CORE non-functional

| ID | Requirement | Verification |
|---|---|---|
| CORE-NFR-001 | The package shall have no mandatory third-party runtime dependencies. | Inspection, Test |
| CORE-NFR-002 | The package shall run on CPython 3.8 or later. | Inspection |
| CORE-NFR-003 | Optional dependencies shall be imported lazily, and their absence shall produce a diagnostic naming the missing extra rather than an ``ImportError``. | Test |
| CORE-NFR-004 | Settings shall be validated before transmission; a rejected setting shall leave the instrument unmodified. | Test |
| CORE-NFR-005 | All errors shall be reported through a single typed exception hierarchy, and diagnostics shall name the probable cause and the corrective action. | Test |
| CORE-NFR-006 | Every I/O operation shall be bounded by a timeout. | Test, Inspection |
| CORE-NFR-007 | Statement coverage of the unit test suite shall be at least 90%. | Test |
| CORE-NFR-008 | `benchtools.core` shall contain no reference to any instrument, and shall be importable without importing any other element. | Test |
| CORE-NFR-009 | Dependencies between elements shall point one way only: core, then analysis, then instruments, then runner. | Test |

---

## 5. ANA — analysis of captured records

| ID | Requirement | Source | Verification |
|---|---|---|---|
| ANA-FR-001 | Analysis shall decode raw digitiser codes from binary transfers of 1 or 2 bytes per point, signed or unsigned, big-endian. | STK-04 | Test |
| ANA-FR-002 | Analysis shall scale a record to seconds and volts using the instrument's preamble, per `Xn = XZEro + XINcr(n - PT_Off)` and `Yn = YZEro + YMUlt(raw - YOFf)`. | STK-04 | Test |
| ANA-FR-003 | A record transferred as a sub-range shall still report absolute record times. | STK-04 | Test |
| ANA-FR-004 | Analysis shall detect samples at the digitiser rail and report them, because level estimation and every threshold-derived timing result is invalid on a clipped record. | STK-05 | Test |
| ANA-FR-005 | Analysis shall export records to CSV, with one shared time column for a multi-channel capture. | STK-04 | Test |
| ANA-FR-010 | Analysis shall estimate the base and top levels of a two-state signal robustly in the presence of overshoot and ringing. | STK-05 | Test |
| ANA-FR-011 | Analysis shall locate threshold crossings of a given polarity. | STK-05 | Test |
| ANA-FR-012 | Crossing times shall be refined by interpolation between the straddling samples, so timing resolution is not limited to the sample interval. | STK-05 | Test |
| ANA-FR-013 | Edge detection shall apply a hysteresis band to suppress duplicate edges caused by noise near the threshold. | STK-05 | Test |
| ANA-FR-014 | Thresholds shall be derivable either from each channel's own amplitude as a percentage, or as one absolute voltage applied to every channel. | STK-05 | Test |
| ANA-FR-015 | Analysis shall measure every period in a record and report mean, minimum, maximum, standard deviation, peak-to-peak jitter and frequency. | STK-05 | Test |
| ANA-FR-016 | Analysis shall measure the timing spread of an arbitrary number of channels crossing a threshold in a given direction, reporting per-channel times, per-channel skews relative to a reference, the earliest and latest channel, and the overall spread. | STK-05 | Test |
| ANA-FR-017 | Analysis shall measure pulse widths and transition times. | STK-05 | Test |
| ANA-FR-020 | Analysis shall render records to an image file host-side. | STK-04 | Test |
| ANA-FR-021 | A rendered plot shall be annotatable with each channel's measured edge and the resulting spread. | STK-05 | Test |

---

## 6. INST — requirements common to all drivers

| ID | Requirement | Source | Verification |
|---|---|---|---|
| INST-FR-001 | A driver shall be provided for any instrument answering ``*IDN?``, supporting identification, error-queue reading and raw SCPI, for instruments without a dedicated driver. | STK-07, STK-08 | Test |
| INST-FR-002 | Each driver shall declare the simulator used for a ``sim://`` resource, so the link layer needs no knowledge of instruments. | STK-07 | Test |
| INST-FR-003 | Each driver's capability envelope shall be data-driven, so another model in the same family can be supported without code change. | STK-07 | Test |

---

## 7. SCOPE — Tektronix TDS3014B driver

| ID | Requirement | Source | Verification |
|---|---|---|---|
| SCOPE-FR-010 | Enable and disable each of up to four input channels independently. | STK-02 | Test |
| SCOPE-FR-011 | Report which channels are currently displayed. | STK-02 | Test |
| SCOPE-FR-012 | Set the volts per division of each channel over 1 mV/div to 10 V/div. | STK-03 | Test |
| SCOPE-FR-013 | Set the vertical screen position of each channel over -5 to +5 divisions. | STK-03 | Test |
| SCOPE-FR-014 | Set the input offset, coupling and bandwidth limit of each channel. | STK-03 | Test |
| SCOPE-FR-015 | Read back the complete vertical setup of a channel. | STK-03 | Test |
| SCOPE-FR-016 | Apply a complete vertical setup in a single instrument message. | STK-03 | Test |
| SCOPE-FR-020 | Set the main time base over 4 ns/div to 10 s/div. | STK-04 | Test |
| SCOPE-FR-021 | Set the horizontal delay. | STK-04 | Test |
| SCOPE-FR-022 | Set the acquisition record length to a supported value (500 or 10 000 points). | STK-04 | Test |
| SCOPE-FR-030 | Configure an A-event edge trigger: source, level, slope, coupling and mode. | STK-04 | Test |
| SCOPE-FR-031 | Report the trigger state and force a trigger. | STK-04 | Test |
| SCOPE-FR-040 | Arm a single-sequence acquisition and wait for completion within a caller-specified timeout. | STK-04 | Test |
| SCOPE-FR-041 | Start and stop free-running acquisition. | STK-04 | Test |
| SCOPE-FR-042 | Select the acquisition mode and, for averaging, the average count. | STK-04 | Test |
| SCOPE-FR-043 | On acquisition timeout, raise a distinct exception naming the likely cause and reporting the trigger state. | STK-04 | Test |
| SCOPE-FR-050 | Transfer waveform records from one or more channels of a single acquisition, so the channels share a common time base. | STK-04, STK-05 | Test |
| SCOPE-FR-051 | Support 1-byte and 2-byte transfer widths and both binary and ASCII encodings, decoding all to identical digitiser codes. | STK-04 | Test |
| SCOPE-FR-052 | Transfer a caller-specified sub-range of the record. | STK-04 | Test |
| SCOPE-FR-053 | Report digitiser clipping on a captured record. | STK-05 | Test |
| SCOPE-FR-060 | Take immediate measurements using the instrument's own engine, including period, frequency, amplitude, rise time and two-source delay. | STK-05 | Test |
| SCOPE-FR-061 | Report an instrument measurement that could not be computed as an error, not as the instrument's 9.9E37 sentinel. | STK-05 | Test |
| SCOPE-FR-062 | Provide the N-channel timing spread and host-side period statistics from a single acquisition, using the analysis element. | STK-05 | Test |
| SCOPE-FR-080 | Capture the instrument's screen over the instrument link and write it to a file. | STK-04 | Test |
| SCOPE-FR-081 | Fall back to a supported hardcopy format if the requested one is refused. | STK-04 | Test |
| SCOPE-FR-090 | Provide a behavioural simulator sufficient to exercise every layer above the socket without hardware. | STK-06 | Test |
| SCOPE-FR-100 | Provide a command-line interface covering identification, capture, screen capture, measurement, period statistics and channel spread. | STK-04, STK-05 | Test |
| SCOPE-FR-101 | Report the instrument's event queue using the Tektronix ``ALLEv?`` form. | STK-01 | Test |

---

## 8. RUN — bench test runner

### 8.1 Bench configuration

| ID | Requirement | Source | Verification |
|---|---|---|---|
| RUN-FR-001 | The bench configuration shall be separate from the test specification, so the same suite runs on a different rig by pointing at a different configuration. | STK-08 | Test |
| RUN-FR-002 | A bench shall name each instrument by alias, driver and resource, and shall be loadable from JSON or YAML. | STK-08 | Test |
| RUN-FR-003 | Instrument drivers shall be selected by registered name, so a specification cannot name arbitrary code. | STK-08 | Test |
| RUN-FR-004 | Instruments shall connect on first use, and whatever was opened shall be closed on exit, including after a failure. | STK-08 | Test |
| RUN-FR-005 | The runner shall support replacing every instrument with its simulator, so a specification can be exercised without hardware. | STK-08 | Test |
| RUN-FR-006 | A run shall be recorded as simulated whenever no instrument on the bench is real hardware, so simulated results cannot be mistaken for measurements. | STK-08 | Test |

### 8.2 Test specification

| ID | Requirement | Source | Verification |
|---|---|---|---|
| RUN-FR-010 | A test specification shall be data, not code, and shall be loadable from JSON (requiring no third-party package) or YAML. | STK-08 | Test |
| RUN-FR-011 | A specification shall declare a suite name, optional setup and teardown steps, and one or more named tests, each with steps. | STK-08 | Test |
| RUN-FR-012 | Each test shall be able to name the requirement it verifies. | STK-08 | Test |
| RUN-FR-013 | A step shall name an instrument method and its arguments, and shall be able to address values inside the returned result by path. | STK-08 | Test |
| RUN-FR-014 | A malformed specification shall be rejected with a message identifying what to fix. | STK-08 | Test |
| RUN-FR-015 | A test shall be markable as skipped, with a reason. | STK-08 | Test |

### 8.3 Limits

| ID | Requirement | Source | Verification |
|---|---|---|---|
| RUN-FR-020 | A limit shall support a lower bound, an upper bound, or both. | STK-08 | Test |
| RUN-FR-021 | A limit shall support a nominal value with an absolute or percentage tolerance. | STK-08 | Test |
| RUN-FR-022 | A measured value shall be scalable before the limit is checked, so a limit can be stated in convenient units. | STK-08 | Test |
| RUN-FR-023 | A limit shall render as human-readable text for the report, and a failure shall state by how much the value missed. | STK-08 | Test |

### 8.4 Execution

| ID | Requirement | Source | Verification |
|---|---|---|---|
| RUN-FR-030 | The runner shall execute each specification's setup, tests and teardown, and shall record per-measurement, per-step, per-test and per-run outcomes. | STK-08 | Test |
| RUN-FR-031 | A measurement outside its limit shall be reported as a **failure**; a step that could not be executed shall be reported as an **error**. These shall be distinguished throughout. | STK-08 | Test |
| RUN-FR-032 | A setup failure shall abort the suite, because no measurement taken afterwards would be meaningful. Teardown shall run regardless of outcome. | STK-08 | Test |
| RUN-FR-033 | A test failure shall not stop later tests. Stopping after an error shall be selectable. | STK-08 | Test |
| RUN-FR-034 | A specification shall not be able to invoke private driver methods. | STK-08 | Test |
| RUN-FR-035 | The runner shall verify the bench provides every instrument the specification uses before executing anything. | STK-08 | Test |

### 8.5 Reporting

| ID | Requirement | Source | Verification |
|---|---|---|---|
| RUN-FR-040 | The runner shall report the worst outcome per requirement, as the trace from requirement to result. | STK-08 | Test |
| RUN-FR-041 | The runner shall write a lossless JSON result record. | STK-08 | Test |
| RUN-FR-042 | The runner shall write a markdown report leading with the verdict, then requirements, then problems, then all measurements. | STK-08 | Test |
| RUN-FR-043 | The runner shall write a JUnit XML report in which a limit failure and an execution error are distinct elements. | STK-08 | Test |
| RUN-FR-050 | The runner shall provide a command-line interface accepting one or more specifications, a bench configuration or ``--simulate``, and report destinations. | STK-08 | Test |
| RUN-FR-051 | The command line shall exit 0 when everything passed, 1 on a failure or error, and 2 on a usage or specification error. | STK-08 | Test |
| RUN-FR-052 | Running several specifications shall write per-specification reports without overwriting each other. | STK-08 | Test |
| RUN-FR-053 | A single top-level command shall dispatch to each tool's own command line. | STK-07, STK-08 | Test |

---

## 9. Assumptions and constraints

| ID | Statement |
|---|---|
| ASM-01 | The instrument's Ethernet interface is enabled and has a reachable IPv4 address. |
| ASM-02 | The host can reach the instrument's portmapper on port 111 and the dynamically assigned core channel port; no intervening firewall blocks them. |
| ASM-03 | The TDS3014B supports a limited number of simultaneous VXI-11 links (in practice one). |
| CON-01 | Verification to date is against protocol simulators and loopback servers, not physical hardware. Bench confirmation items are listed in the VISA determination report §5.1. |
| CON-02 | TDS3000 SCPI command spellings were not transcribed from the programmer manual during development (the manual host was unreachable from the build environment) and require spot-checking on first bench use. |
| CON-03 | Instrument families named for future work (power supplies and loads, DMMs, signal sources, logic and protocol analysers, BLE and RF) have no requirements in this revision. The core is designed for them but not validated against them. |
