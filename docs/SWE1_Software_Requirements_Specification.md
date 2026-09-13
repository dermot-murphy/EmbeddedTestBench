# SWE.1 — Software Requirements Specification

| Field | Value |
|---|---|
| Document ID | BENCHTOOLS-SWE1-001 |
| Version | 4.1 |
| Date | 2026-09-13 |
| Process reference | Automotive SPICE V4.0, SWE.1 Software Requirements Analysis |
| Item | **BenchTools** — bench test tooling (`benchtools` 4.0.0) |

## 1. Scope

BenchTools is host-side software for automated and semi-automated electronics
bench testing. It provides instrument drivers, analysis of captured records, and
a declarative test runner that drives a bench of instruments and produces
pass/fail evidence.

It is a **test tool**: it is not part of any delivered vehicle software and
carries no ASIL classification. It is developed to this process discipline
because measurement results derived from it are used as evidence.

Out of scope: target application firmware, GPIB, hardware fixture design, and
any instrument not listed in §3.

One piece of embedded software **is** in scope, and is the exception that proves
the rule: the bench dongle's firmware (§9). It is part of the instrument, not
part of any product, and it exists because the measurement it makes - a radio
event timestamped to the microsecond - cannot be made from the host side of a
USB link. It is specified, designed and traced here like the rest of the item.

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
| STK-09 | Debug and exercise target firmware through a SEGGER J-Link: flash, verify against a binary, run, stop, set breakpoints, read and write RAM, read variables, read and write RTT, log RTT, measure the time between lines of code, and read the call stack. |
| STK-10 | Use the J-Link driver from the test bench, so firmware state is an assertable quantity in a bench test alongside instrument measurements. |
| STK-11 | Run first on a Windows PC; eventually run the entire test bench inside Docker. |
| STK-12 | Possibly express tests in Markdown and translate them to Robot Framework files. |
| STK-13 | Control the sensor supply voltage with a programmable power supply. *(future)* |
| STK-14 | Send BLE UART commands through a Nordic dongle in command/response mode, read the responses, and measure the time until each response. |
| STK-15 | Scan for BLE sensors, select one, and measure its advertising profile. |
| STK-16 | Provide the dongle's embedded firmware, built with SEGGER Embedded Studio against nRF5 SDK 17. |
| STK-17 | Log the BLE session to a text file. |
| STK-18 | Measure current with a multimeter over RS-232 through a USB converter. *(future)* |

## 3. Element structure

Requirements are grouped by the element that implements them. Identifier
prefixes are per element so they stay unique as instruments are added.

| Prefix | Element | Rationale for being separate |
|---|---|---|
| `CORE-` | `benchtools.core` | Shared by every instrument: the link, SCPI plumbing, validation, simulator harness. Must contain nothing instrument-specific. |
| `ANA-` | `benchtools.analysis` | Operates on captured records, not live instruments, so it is deterministic and replayable. |
| `INST-` | `benchtools.instruments` | Requirements common to all drivers. |
| `SCOPE-` | `benchtools.instruments.tek3014b` | The oscilloscope driver. |
| `JLINK-` | `benchtools.instruments.jlink` | The SEGGER J-Link debug probe driver. Not a SCPI instrument, and the only element that reaches the target through a debug probe rather than a measurement link. |
| `BLE-` | `benchtools.instruments.nordic_dongle` **and** `firmware/nordic_dongle` | The BLE bench dongle: host driver and the dongle's own firmware. One element, because the protocol between them is one design decision and splitting it across two elements would let the halves drift apart. |
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
| CORE-FR-009 | The link layer shall provide a transport to a child process over its standard input and output, for tools that speak a line protocol rather than listening on a socket. It shall work on Windows as well as POSIX hosts, retain the child's diagnostic output, and report that output if the child exits unexpectedly. | STK-07, STK-09, STK-11 | Test |
| CORE-FR-017 | The link layer shall provide a serial-port transport, selecting the port by name (``COM5``, ``/dev/ttyACM0``), and shall also accept a port published over TCP so that a container can reach a device attached to another machine. The serial library shall be an optional dependency. | STK-14, STK-18 | Test |
| CORE-FR-010 | Transport backends and resource-string schemes shall be held in registries, so a new link type can be added from its own module without modifying the factory. | STK-07 | Test, Inspection |
| CORE-FR-011 | The link layer shall accept a host name, an IPv4 address, or a VISA-style resource string, and shall select a transport automatically. | STK-01 | Test |

### 4.2 Generic instrument base

Not every bench instrument speaks SCPI. A debug probe (§8) is driven over GDB/MI,
a BLE dongle over its own serial protocol. The lifecycle those drivers share with
a SCPI instrument is therefore specified separately from the SCPI vocabulary, so
the runner can treat any of them as a bench instrument.

| ID | Requirement | Source | Verification |
|---|---|---|---|
| CORE-FR-012 | A generic instrument base shall provide the link lifecycle — open, initialise to a known state, close, and use as a context manager — without assuming any particular command language. | STK-07, STK-09 | Test |
| CORE-FR-013 | The generic base shall hold instrument identification as manufacturer, model, serial number and firmware, populated through a hook each driver implements, and shall cache it until a refresh is requested. | STK-07 | Test |
| CORE-FR-014 | The generic base shall declare the simulator class used when the resource string selects simulation, so that any driver is verifiable without hardware irrespective of its command language. | STK-07 | Test |
| CORE-FR-015 | The generic base shall provide an event-queue read and an error check that a driver may override, defaulting to reporting no events for instruments that have no error queue. | STK-07 | Test |
| CORE-FR-016 | Closing an instrument shall never raise, so that a failure during a measurement cannot be masked by a failure while cleaning up. | STK-07 | Test |

### 4.3 SCPI instrument base

Extends §4.2 with the SCPI and IEEE 488.2 vocabulary.

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

### 4.4 Validation and shared types

| ID | Requirement | Source | Verification |
|---|---|---|---|
| CORE-FR-030 | A shared enumeration base shall accept a member, a member name or a SCPI mnemonic, case-insensitively, and shall reject anything else with a message listing the valid values. | STK-07 | Test |
| CORE-FR-031 | Shared validation shall check ranges, channel availability and enumerated choices, raising a message that names the setting, the offending value, the permitted range and the unit. | STK-03, STK-07 | Test |

### 4.5 Simulator harness

| ID | Requirement | Source | Verification |
|---|---|---|---|
| CORE-FR-040 | A shared simulator harness shall provide SCPI message dispatch, compound-message splitting, the IEEE 488.2 mandated queries, an event queue and binary replies, so each instrument's simulator implements only its own behaviour. | STK-07 | Test |
| CORE-FR-041 | An unrecognised command shall be recorded in the simulated event queue rather than ignored, so that a driver which misspells a command fails a test instead of passing silently. | STK-07 | Test |

### 4.6 CORE non-functional

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

## 8. JLINK — SEGGER J-Link debug probe driver

The probe is not an instrument in the SCPI sense: it does not answer `*IDN?` and
has no error queue. It is nonetheless a *bench instrument* — it is configured,
it is commanded, and it yields measurements — so it implements the generic base of
§4.2 and is usable from the runner of §9.

### 8.1 Link to the probe

| ID | Requirement | Source | Verification |
|---|---|---|---|
| JLINK-FR-001 | The driver shall communicate with the target through the GDB machine interface (GDB/MI), parsing result, asynchronous, stream and prompt records, including nested tuples and lists, C-string escapes, and repeated result names. | STK-09 | Test |
| JLINK-FR-002 | The driver shall issue MI commands with a sequence token and correlate each reply to its command, shall surface an MI error as a typed exception naming the command and the reason, and shall drain asynchronous records that arrive between commands rather than discarding them. | STK-09 | Test |
| JLINK-FR-003 | The driver shall locate and launch the SEGGER J-Link GDB Server and a GDB for the target architecture, searching the executable names used on Windows first, and shall report a clear diagnostic naming the missing tool and where it is normally installed. | STK-09, STK-11 | Test |
| JLINK-FR-004 | The driver shall attach to a GDB server already listening, whether started by the user or running on another host, and shall not attempt to spawn a server on a host that is not the local one. | STK-09, STK-11 | Test |
| JLINK-FR-005 | The driver shall close the link and stop only the server it started itself, leaving a server it merely attached to running. | STK-09 | Test |

### 8.2 Target configuration

| ID | Requirement | Source | Verification |
|---|---|---|---|
| JLINK-FR-010 | The driver shall accept the target device name, debug interface (SWD or JTAG), interface speed, probe serial number, and the core clock frequency, and shall hold each probe's capability envelope — hardware breakpoint count, watchpoint count, RTT channel count and maximum transfer size — as data rather than in code. | STK-09 | Test, Inspection |
| JLINK-FR-011 | The driver shall load target symbols from an ELF file, reporting a missing or unreadable file before any target operation is attempted. | STK-09 | Test |

### 8.3 Programming and verification

| ID | Requirement | Source | Verification |
|---|---|---|---|
| JLINK-FR-020 | The driver shall programme the target from an ELF file and report the sections written, their addresses, their sizes and the elapsed time. | STK-09 | Test |
| JLINK-FR-021 | The driver shall verify the target's memory against the binary section by section, and shall report per-section verdicts, not merely an overall result. | STK-09 | Test |
| JLINK-FR-022 | A verification mismatch shall raise, naming the sections that differ. A verification over an empty section list shall be reported as not matched, never as a pass. | STK-09 | Test |
| JLINK-FR-023 | The driver shall erase the target's non-volatile memory. | STK-09 | Test |

### 8.4 Execution control

| ID | Requirement | Source | Verification |
|---|---|---|---|
| JLINK-FR-030 | The driver shall reset the target, optionally halting at the reset vector, and shall run, halt, resume and single-step the core. | STK-09 | Test |
| JLINK-FR-031 | The driver shall report whether the core is halted, its program counter, and its register values. | STK-09 | Test |
| JLINK-FR-032 | The driver shall wait for the target to halt with a bounded timeout, and shall report the reason for the halt — breakpoint, watchpoint, step, signal or an unrecognised reason — rather than only that it stopped. | STK-09 | Test |
| JLINK-FR-033 | The driver shall set a breakpoint by source location, function or address, optionally temporary, optionally conditional, and optionally forced into hardware; it shall list, delete and clear breakpoints. | STK-09 | Test |
| JLINK-FR-034 | The driver shall refuse to set more hardware breakpoints than the probe's envelope allows, reporting the limit, rather than letting the request fail on the target. | STK-09 | Test |
| JLINK-FR-035 | The driver shall set watchpoints on a variable or address for write, read, or either access, within the probe's watchpoint envelope. | STK-09 | Test |
| JLINK-FR-036 | The driver shall run the target to a given location, reporting whether it arrived there or halted for another reason. | STK-09 | Test |

### 8.5 Target state

| ID | Requirement | Source | Verification |
|---|---|---|---|
| JLINK-FR-040 | The driver shall read and write target memory of arbitrary length, splitting transfers to the probe's maximum transfer size, and shall provide byte, half-word and word accessors. | STK-09 | Test |
| JLINK-FR-041 | The driver shall read and write a variable by name, returning integers, floating-point values and strings as the debug information describes them, and shall report a variable's address and size. | STK-09 | Test |
| JLINK-FR-042 | The driver shall evaluate an arbitrary expression in the target's context. | STK-09 | Test |
| JLINK-FR-045 | The driver shall read the call stack, reporting for each frame its level, function, source file and line, and the frame address. | STK-09 | Test |

### 8.6 Real Time Transfer

| ID | Requirement | Source | Verification |
|---|---|---|---|
| JLINK-FR-050 | The driver shall read from and write to an RTT channel without halting the core. | STK-09 | Test |
| JLINK-FR-051 | The driver shall read RTT as whole lines, retaining a partial line until its terminator arrives, and shall report how many lines are waiting. | STK-09 | Test |
| JLINK-FR-052 | The driver shall wait for RTT output matching a regular expression with a bounded timeout, and on timeout shall report both the pattern sought and the text that did arrive. | STK-09 | Test |
| JLINK-FR-053 | The driver shall send a command over RTT and return the matching response, so a firmware console is usable as a test interface. | STK-09, STK-10 | Test |
| JLINK-FR-055 | The driver shall log every RTT line to a file as it arrives, flushed per line so the log survives a target or host failure, and shall retain the complete history independently of the lines consumed by reads. | STK-09 | Test |

### 8.7 Timing between lines of code

| ID | Requirement | Source | Verification |
|---|---|---|---|
| JLINK-FR-060 | The driver shall measure the elapsed time between two locations in the target's code, by a method the caller selects, and shall report the result in cycles and in seconds together with the method used. | STK-09 | Test |
| JLINK-FR-061 | The driver shall provide measurement by the Cortex-M DWT cycle counter, enabling the trace unit and the counter, and shall account for the counter's 32-bit wrap. | STK-09 | Test |
| JLINK-FR-062 | The driver shall provide measurement by the host clock, for targets with no cycle counter, and shall not present its result as more precise than the host clock permits. | STK-09 | Test |
| JLINK-FR-063 | The driver shall provide measurement from a target timer captured into variables by the firmware, given the timer's frequency. | STK-09 | Test |
| JLINK-FR-064 | The driver shall provide measurement from SWO/ITM trace, decoding the ITM packet stream, so that the interval is measured **without halting the core**. | STK-09 | Test |
| JLINK-FR-065 | Every timing result shall report the resolution of the method that produced it, and shall be flagged as not trustworthy when the measured interval is not large enough with respect to that resolution. Halting methods shall declare that they halt the target. | STK-09 | Test |
| JLINK-FR-066 | The driver shall repeat a timing measurement and report minimum, maximum, mean, spread and standard deviation over the repetitions. | STK-05, STK-09 | Test |
| JLINK-FR-067 | A timing result derived from no samples shall raise rather than report zero. | STK-09 | Test |

### 8.8 Bench and command-line use

| ID | Requirement | Source | Verification |
|---|---|---|---|
| JLINK-FR-080 | The probe shall be registered as a bench driver, so a bench configuration and a test specification reference it by name like any instrument. | STK-10 | Test |
| JLINK-FR-081 | Every probe operation usable as a test step shall return a value or a record of plain types, so a declarative specification can assert on it without driver-specific code. | STK-10, STK-12 | Test |
| JLINK-FR-090 | A simulated probe shall answer the GDB/MI dialogue the driver uses, with a deterministic firmware model — symbols, memory, call stacks, RTT traffic, ITM events and a known interval between two locations — so the driver is fully verifiable without a probe or a target. | STK-09 | Test |
| JLINK-FR-100 | A command-line interface shall expose identification, flashing, verification, reset, run, halt, memory and variable access, the call stack, RTT and timing, emitting JSON so results are usable from a script. | STK-09, STK-12 | Test |

### 8.9 JLINK non-functional

| ID | Requirement | Verification |
|---|---|---|
| JLINK-NFR-001 | The driver shall add no mandatory third-party runtime dependency. | Inspection, Test |
| JLINK-NFR-002 | The driver shall run on Windows and on Linux, with no POSIX-only facility on either the process link or the RTT link. | Inspection, Test |
| JLINK-NFR-003 | Both links to the probe — GDB/MI and RTT — shall be capable of being TCP connections to a host other than the one running the driver, so that the driver can run inside a container while the probe is attached elsewhere. | Test, Inspection |
| JLINK-NFR-004 | A measurement shall never be reported without the method that produced it and that method's resolution. | Test |

---

## 9. BLE — Nordic dongle and its firmware

The element has two halves that must agree: firmware on an nRF52840 dongle, and
a host driver. Requirements are written once and apply to whichever half
implements them; §9.6 says which.

### 9.1 The host link

| ID | Requirement | Source | Verification |
|---|---|---|---|
| BLE-FR-001 | The dongle and the host shall communicate over USB CDC with a line protocol in which a command is one line, a reply is one line beginning ``ok`` or ``err``, and an unsolicited event is one line beginning ``+``. The protocol shall be defined in a single artefact that both halves are built from. | STK-14, STK-15 | Test, Inspection |
| BLE-FR-002 | Every command shall produce exactly one reply, including when it fails, so that a lost reply is detectable rather than appearing as a hang. A failure shall carry a numeric code and text. | STK-14 | Test |
| BLE-FR-003 | The firmware shall queue outgoing lines rather than block a radio event handler on the USB endpoint, and shall count lines it could not send. | STK-15 | Test, Inspection |
| BLE-FR-004 | The host shall be able to reconcile what it received against what the dongle sent, and a capture that lost lines shall be reported as incomplete rather than analysed as if complete. | STK-15, STK-17 | Test |
| BLE-FR-010 | Every event shall carry a timestamp taken on the dongle, resolving one microsecond, taken as close to the radio event as the stack allows. The timestamp shall not wrap within a measurement session. | STK-14, STK-15 | Test |
| BLE-FR-011 | The host shall record its own arrival time beside the dongle's timestamp, and shall not present the host figure as the measurement. | STK-14 | Test |

### 9.2 Scanning and selection

| ID | Requirement | Source | Verification |
|---|---|---|---|
| BLE-FR-020 | The dongle shall scan for advertising devices for a given duration and report each device once, with its address, address type, signal strength and advertised name. | STK-15 | Test |
| BLE-FR-021 | A device that advertises no name shall be reported with an empty name rather than omitted. | STK-15 | Test |
| BLE-FR-022 | Scanning shall be filterable by name, by address and by minimum signal strength, and the filter shall be applied in the firmware. | STK-15 | Test |
| BLE-FR-023 | The host shall select one sensor, by index, address, name or object, and that selection shall persist for later commands. The address type shall travel with the address. | STK-15 | Test |
| BLE-FR-024 | Selecting an address that no scan has seen shall be permitted, so a suite that knows its sensor need not scan first. | STK-15 | Test |

### 9.3 UART over BLE

| ID | Requirement | Source | Verification |
|---|---|---|---|
| BLE-FR-040 | The dongle shall connect to the selected sensor, discover Nordic's UART Service, and subscribe to its notifications. | STK-14 | Test |
| BLE-FR-041 | The connection interval shall be reported, because it bounds every latency measured over that link. | STK-14 | Test |
| BLE-FR-042 | The host shall write bytes or text to the sensor without waiting for a reply. | STK-14 | Test |
| BLE-FR-043 | The host shall send a command and return the sensor's reply, in one operation. | STK-14 | Test |
| BLE-FR-044 | A sensor that does not reply within the timeout shall be reported as a timeout, not as a round trip of the timeout's length. | STK-14 | Test |
| BLE-FR-045 | A payload longer than the firmware accepts shall be refused by the host before transmission, naming the limit. | STK-14 | Test |

### 9.4 Time until response

| ID | Requirement | Source | Verification |
|---|---|---|---|
| BLE-FR-050 | The round trip from request to reply shall be measured on the dongle's microsecond clock, timestamped when the request is handed to the stack and when the notification arrives. | STK-14 | Test |
| BLE-FR-051 | The host's own round trip shall be measured and reported separately, as a cross-check on the link rather than as the sensor's latency. | STK-14 | Test |
| BLE-FR-052 | A command shall be repeatable, with minimum, maximum, mean, spread and standard deviation reported over the repetitions. | STK-14 | Test |
| BLE-FR-053 | Every latency result shall report the clock that produced it, that clock's resolution, and the connection interval; and shall be flagged as not trustworthy when the measured latency cannot be told apart from the connection interval. | STK-14 | Test |
| BLE-FR-054 | A latency result derived from no samples shall raise rather than report zero. | STK-14 | Test |

### 9.5 Advertising profile

| ID | Requirement | Source | Verification |
|---|---|---|---|
| BLE-FR-030 | The dongle shall report every advertising event from a chosen address, timestamped, with signal strength, channel and payload. | STK-15 | Test |
| BLE-FR-031 | The host shall derive the advertising interval: mean, minimum, maximum, spread and standard deviation. | STK-15 | Test |
| BLE-FR-032 | Advertising reports of one event on several channels shall be coalesced into a single advertising event, so that the interval measured is between beacons and not between channels. | STK-15 | Test |
| BLE-FR-033 | The analysis shall account for the advertising delay the Bluetooth specification requires (0 to 10 ms per interval), stating the jitter a conforming sensor shows, so that correct behaviour is not reported as instability. | STK-15 | Test |
| BLE-FR-034 | Advertising events the sensor did not send shall be counted, against a nominal interval supplied by the caller or inferred from the capture, and the two cases shall be distinguishable. | STK-15 | Test |
| BLE-FR-035 | The proportion of the capture in which the sensor kept to its rate (duty cycle) and the proportion of expected events received shall be reported. | STK-15 | Test |
| BLE-FR-036 | A capture too short for statistics shall report the counts it has and raise only when a statistic is actually asked for. | STK-15 | Test |

### 9.6 Firmware, tooling and bench use

| ID | Requirement | Source | Verification |
|---|---|---|---|
| BLE-FR-060 | The session shall be loggable to a text file: every line in both directions, host-timestamped, flushed per line so a session that then hangs still has a complete log. | STK-17 | Test |
| BLE-FR-061 | The log shall include lines the driver ignored, since a log that omits what the tooling discarded cannot explain why it discarded it. | STK-17 | Test |
| BLE-FR-062 | Comments shall be writable into the log, so a measurement can be annotated with what it was verifying. | STK-17 | Test |
| BLE-FR-070 | A command-line interface shall expose identification, scanning, selection, advertising profile, command/response timing and event monitoring, emitting JSON. | STK-14, STK-15 | Test |
| BLE-FR-080 | The dongle shall be registered as a bench driver, and a simulated dongle shall answer the same protocol with a deterministic sensor population, so every operation is verifiable without a dongle, a sensor or a radio. | STK-08, STK-15 | Test |
| BLE-FR-090 | The firmware shall build as a SEGGER Embedded Studio project against nRF5 SDK 17 for the PCA10059 dongle, and shall be packageable as a DFU image for the dongle's factory bootloader. | STK-16 | Inspection |

### 9.7 BLE non-functional

| ID | Requirement | Verification |
|---|---|---|
| BLE-NFR-001 | The firmware shall allocate no memory dynamically, shall not recurse, and shall bound every buffer at compile time. | Test, Inspection |
| BLE-NFR-002 | The firmware shall not block a radio event handler on USB, so that reporting cannot distort the timing being reported. | Inspection |
| BLE-NFR-003 | The command set, events, error codes and size limits shall be defined once and checked automatically for agreement between firmware and host driver. | Test |
| BLE-NFR-004 | The host driver shall add no mandatory third-party dependency; the serial library shall be an optional extra. | Test, Inspection |
| BLE-NFR-005 | A measurement shall never be reported without the clock that produced it and that clock's resolution. | Test |

---

## 10. RUN — bench test runner

### 10.1 Bench configuration

| ID | Requirement | Source | Verification |
|---|---|---|---|
| RUN-FR-001 | The bench configuration shall be separate from the test specification, so the same suite runs on a different rig by pointing at a different configuration. | STK-08 | Test |
| RUN-FR-002 | A bench shall name each instrument by alias, driver and resource, and shall be loadable from JSON or YAML. | STK-08 | Test |
| RUN-FR-003 | Instrument drivers shall be selected by registered name, so a specification cannot name arbitrary code. | STK-08 | Test |
| RUN-FR-004 | Instruments shall connect on first use, and whatever was opened shall be closed on exit, including after a failure. | STK-08 | Test |
| RUN-FR-005 | The runner shall support replacing every instrument with its simulator, so a specification can be exercised without hardware. | STK-08 | Test |
| RUN-FR-006 | A run shall be recorded as simulated whenever no instrument on the bench is real hardware, so simulated results cannot be mistaken for measurements. | STK-08 | Test |

### 10.2 Test specification

| ID | Requirement | Source | Verification |
|---|---|---|---|
| RUN-FR-010 | A test specification shall be data, not code, and shall be loadable from JSON (requiring no third-party package) or YAML. | STK-08 | Test |
| RUN-FR-011 | A specification shall declare a suite name, optional setup and teardown steps, and one or more named tests, each with steps. | STK-08 | Test |
| RUN-FR-012 | Each test shall be able to name the requirement it verifies. | STK-08 | Test |
| RUN-FR-013 | A step shall name an instrument method and its arguments, and shall be able to address values inside the returned result by path. | STK-08 | Test |
| RUN-FR-014 | A malformed specification shall be rejected with a message identifying what to fix. | STK-08 | Test |
| RUN-FR-015 | A test shall be markable as skipped, with a reason. | STK-08 | Test |

### 10.3 Limits

| ID | Requirement | Source | Verification |
|---|---|---|---|
| RUN-FR-020 | A limit shall support a lower bound, an upper bound, or both. | STK-08 | Test |
| RUN-FR-021 | A limit shall support a nominal value with an absolute or percentage tolerance. | STK-08 | Test |
| RUN-FR-022 | A measured value shall be scalable before the limit is checked, so a limit can be stated in convenient units. | STK-08 | Test |
| RUN-FR-023 | A limit shall render as human-readable text for the report, and a failure shall state by how much the value missed. | STK-08 | Test |

### 10.4 Execution

| ID | Requirement | Source | Verification |
|---|---|---|---|
| RUN-FR-030 | The runner shall execute each specification's setup, tests and teardown, and shall record per-measurement, per-step, per-test and per-run outcomes. | STK-08 | Test |
| RUN-FR-031 | A measurement outside its limit shall be reported as a **failure**; a step that could not be executed shall be reported as an **error**. These shall be distinguished throughout. | STK-08 | Test |
| RUN-FR-032 | A setup failure shall abort the suite, because no measurement taken afterwards would be meaningful. Teardown shall run regardless of outcome. | STK-08 | Test |
| RUN-FR-033 | A test failure shall not stop later tests. Stopping after an error shall be selectable. | STK-08 | Test |
| RUN-FR-034 | A specification shall not be able to invoke private driver methods. | STK-08 | Test |
| RUN-FR-035 | The runner shall verify the bench provides every instrument the specification uses before executing anything. | STK-08 | Test |

### 10.5 Reporting

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

## 11. Assumptions and constraints

| ID | Statement |
|---|---|
| ASM-01 | The instrument's Ethernet interface is enabled and has a reachable IPv4 address. |
| ASM-02 | The host can reach the instrument's portmapper on port 111 and the dynamically assigned core channel port; no intervening firewall blocks them. |
| ASM-03 | The TDS3014B supports a limited number of simultaneous VXI-11 links (in practice one). |
| CON-01 | Verification to date is against protocol simulators and loopback servers, not physical hardware. Bench confirmation items are listed in the VISA determination report §5.1. |
| CON-02 | TDS3000 SCPI command spellings were not transcribed from the programmer manual during development (the manual host was unreachable from the build environment) and require spot-checking on first bench use. |
| ASM-04 | The J-Link GDB Server and a GDB for the target architecture are installed on the host that has the probe attached, and the server's ports (2331 GDB, 2332 SWO, 19021 RTT) are reachable from the host running the driver. |
| ASM-05 | The target is a Cortex-M part whose DWT unit is present and not locked by the vendor, for the cycle-counter timing method. Targets without it are served by the other three methods. |
| ASM-06 | Target firmware built with debug information (`-g`) and, for the RTT and SWO methods, linked against SEGGER RTT and with SWO enabled by the firmware or the server. |
| ASM-07 | The dongle is an nRF52840 USB dongle (PCA10059) with its factory bootloader and S140 SoftDevice, enumerating as a USB CDC serial port on the host. |
| ASM-08 | The sensor under test exposes Nordic's UART Service and answers a text console over it. A sensor with a different service needs a firmware change, not a driver change. |
| ASM-09 | Advertising is on the primary channels (37, 38, 39) at 1 Mbit/s; extended advertising and coded PHY are not scanned for in this revision. |
| CON-07 | The dongle firmware targets nRF5 SDK 17.1.0. It **compiles** against real SDK headers (SDK 15.2.0, in the `canembed/canembed-arm` image) with zero warnings, apart from four lines using SDK 17-only API; it has **not** been linked, flashed or run, and SDK 17.1.0 itself could not be obtained in the build environment. See `docs/ble/BLE_Dongle_Notes.md` §5. |
| CON-08 | Only RTT-free, connection-oriented UART is supported; the dongle connects to one sensor at a time. |
| CON-03 | Instrument families named for future work (STK-13 and STK-18: power supplies and a multimeter over RS-232) have no requirements in this revision. The core is designed for them but not validated against them. |
| CON-04 | The J-Link driver is verified against a simulated probe and a simulated target, not against physical hardware. Bench confirmation items are listed in `docs/jlink/JLink_Integration_Notes.md` §4. |
| CON-05 | The scaling of SWO/ITM local timestamps to core cycles depends on the trace prescaler configured by the GDB server and the firmware. It is implemented from the ARMv7-M architecture reference manual and requires confirmation against a part before SWO timing figures are quoted (JLINK-OPEN-03). |
| CON-06 | Markdown-to-Robot-Framework translation (STK-12) is not implemented in this revision. The driver's return types are constrained by JLINK-FR-081 so that it can be added without changing the driver. |
