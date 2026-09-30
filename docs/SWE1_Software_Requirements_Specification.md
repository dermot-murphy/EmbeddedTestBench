# SWE.1 — Software Requirements Specification

| Field | Value |
|---|---|
| Document ID | BENCHTOOLS-SWE1-001 |
| Version | 4.3 |
| Date | 2026-09-30 |
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
The bench thermometer's firmware (§12) is in scope for the same reason: it is
the instrument, running on a Raspberry Pi Pico 2 beside an SHT30 sensor.

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
| STK-13 | Control the sensor supply voltage with a programmable power supply. |
| STK-14 | Send BLE UART commands through a Nordic dongle in command/response mode, read the responses, and measure the time until each response. |
| STK-15 | Scan for BLE sensors, select one, and measure its advertising profile. |
| STK-16 | Provide the dongle's embedded firmware, built with SEGGER Embedded Studio against nRF5 SDK 17. |
| STK-17 | Log the BLE session to a text file. |
| STK-18 | Measure current with a multimeter over RS-232 through a USB converter. *(future)* |
| STK-19 | Evaluate a sub-1 GHz radio with an ST S2-LP development kit over USB: program and read every register, transmit, receive, and log all data to a file. |
| STK-20 | Use the kit's existing ST firmware if it is fit for purpose, rather than writing firmware for it. |
| STK-21 | Read the local temperature using a Raspberry Pi Pico 2 and a DollaTek SHT30-D temperature sensor (issue #104). |
| STK-22 | The firmware downloaded to the Pico shall report its title and version number. |

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
| `S2LP-` | `benchtools.instruments.s2lp` | The ST S2-LP development kit. Unlike the BLE dongle, the firmware is **ST's own** (STK-20), so this element is a host driver only and the firmware's command set is an external interface rather than something this project controls. |
| `PSU-` | `benchtools.instruments.gpd3303d` | The GW Instek GPD-3303D bench supply. Separate from `INST-` because its command set is neither SCPI nor shared with any other instrument here, and its single output switch is a hardware constraint that shapes its whole interface. |
| `PICO-` | `benchtools.instruments.pico_sht30` **and** `firmware/pico_sht30` | The Pico 2 + SHT30-D bench thermometer: host driver and the Pico's own firmware. One element for the same reason as `BLE-`: the line protocol between them is one design decision. |
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
| CORE-FR-050 | A build's manifest - the version and build date its build system recorded beside the image - shall be readable by any element that needs it, and the diagnostic for a missing one shall name every path searched and take from the caller the sentence saying how that particular build produces one. | STK-07, STK-16 | Test |

### 4.7 Simulation

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
| JLINK-FR-024 | The driver shall report what the build system recorded about the image it programmed - the version and the build date - from the manifest beside that image, so a test can state the version it put on a part rather than repeating one into a specification where it would go stale. | STK-09, STK-16 | Test |

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
| JLINK-FR-043 | The driver shall read a field of one to eight bytes as an integer in a byte order the caller states, because the byte order and width of a record programmed into a part are properties of that record and not of the core that loads it. A width or byte order outside what is supported shall be refused, since a misspelling would otherwise read a plausible and entirely wrong number. | STK-09 | Test |
| JLINK-FR-045 | The driver shall read the call stack, reporting for each frame its level, function, source file and line, and the frame address. | STK-09 | Test |

### 8.6 Real Time Transfer

| ID | Requirement | Source | Verification |
|---|---|---|---|
| JLINK-FR-050 | The driver shall read from and write to an RTT channel without halting the core. | STK-09 | Test |
| JLINK-FR-051 | The driver shall read RTT as whole lines, retaining a partial line until its terminator arrives, and shall report how many lines are waiting. | STK-09 | Test |
| JLINK-FR-052 | The driver shall wait for RTT output matching a regular expression with a bounded timeout, and on timeout shall report both the pattern sought and the text that did arrive. | STK-09 | Test |
| JLINK-FR-053 | The driver shall send a command over RTT and return the matching response, so a firmware console is usable as a test interface. | STK-09, STK-10 | Test |
| JLINK-FR-054 | The driver shall report how many RTT lines arrive within a bounded interval, so that "the target is running" is a measurement a limit can fail rather than a timeout that raises. A target that started and said nothing is a failed test, not a broken bench. | STK-09, STK-10 | Test |
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
| BLE-FR-012 | The firmware shall report, on request, the version and the build date of the image it is running. The build date shall be the instant the image was built, in UTC, and shall be produced from a single source shared with the build. | STK-14, STK-16 | Test, Inspection |
| BLE-FR-013 | The firmware shall, on request, answer first and then restart into its bootloader, so that the host can refresh it over the same link without the operator touching the hardware. | STK-14 | Test |
| BLE-FR-014 | The host shall compare the version and build date on the dongle against those of a named build, shall report a difference in either as a mismatch, and shall be able to refresh the dongle and confirm afterwards that the intended image is running. | STK-14, STK-16, STK-17 | Test |

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
| BLE-FR-100 | The driver shall read a command and response test from a markdown document: a heading per test, and a table of step number, command and expected response. The document that specifies the command set is then the test of it, rather than a second copy of it that can disagree. | STK-12, STK-15 | Test |
| BLE-FR-101 | A step with an expected response shall pass when the reply equals it after trimming, and fail otherwise. An expected response written `/…/` shall be matched as a regular expression, for a reply carrying a value that varies. | STK-12, STK-15 | Test |
| BLE-FR-102 | A step whose reply does not arrive within the timeout shall **fail**: the document said the sensor would answer. | STK-12, STK-15 | Test |
| BLE-FR-103 | A step written `delay <milliseconds>` shall wait and be recorded as **skipped**: waiting is not a claim about the sensor. | STK-12, STK-15 | Test |
| BLE-FR-104 | A command with no expected response shall be sent, anything arriving within a bounded listening window recorded, and the step recorded as **skipped** - the document made no claim to check, and what the board said is worth seeing anyway. | STK-12, STK-15 | Test |
| BLE-FR-105 | Each step's result shall record the test, the step number, the command, the response, the expected response, the time from the end of the command to the start of the response at 10 ms resolution together with the clock that measured it, and the outcome. The measured figure shall be retained beside the quoted one. | STK-12, STK-15, STK-17 | Test |
| BLE-FR-106 | A run shall pass when no step failed, and shall report how many steps passed, failed and were skipped - so that a document which checked nothing cannot read as a document that checked everything. | STK-12, STK-15 | Test |
| BLE-FR-107 | A document that cannot be read shall be refused naming the document and the line: a row that cannot be parsed, a step number used twice within a test, a missing column, a delay that is not a positive duration, a delay carrying an expected response, or a table before any heading. A row skipped quietly would be a command nobody tested and nobody missed. | STK-12 | Test |
| BLE-FR-108 | The run shall be reportable as a markdown file, and every command shall be sent through the ordinary command path so that the session log carries the whole exchange with both clocks, marked with the test each command belonged to. | STK-12, STK-17 | Test |
| BLE-FR-090 | The firmware shall build as a SEGGER Embedded Studio project against nRF5 SDK 17 for the PCA10059 dongle, and shall be packageable as a DFU image for the dongle's factory bootloader. | STK-16 | Inspection |

### 9.7 BLE non-functional

| ID | Requirement | Verification |
|---|---|---|
| BLE-NFR-001 | The firmware shall allocate no memory dynamically, shall not recurse, and shall bound every buffer at compile time. | Test, Inspection |
| BLE-NFR-006 | The firmware shall be verifiable without a dongle: its units shall be testable on a host, and its build shall be reproducible headlessly. | Test |
| BLE-NFR-002 | The firmware shall not block a radio event handler on USB, so that reporting cannot distort the timing being reported. | Inspection |
| BLE-NFR-003 | The command set, events, error codes and size limits shall be defined once and checked automatically for agreement between firmware and host driver. | Test |
| BLE-NFR-004 | The host driver shall add no mandatory third-party dependency; the serial library shall be an optional extra. | Test, Inspection |
| BLE-NFR-005 | A measurement shall never be reported without the clock that produced it and that clock's resolution. | Test |

---

## 10. PSU — GW Instek GPD-3303D bench supply

A linear supply with two programmable 30 V / 3 A channels, reached over RS-232
or its USB-serial port. It is the sensor supply of STK-13.

The supply also has a **third** output: a fixed 2.5 / 3.3 / 5 V, 3 A rail
selected by a front-panel switch. It is outside this element, deliberately. No
command reaches it, so nothing the driver could report about it would be a
measurement - it would be a repetition of whatever the bench file had been told
about a switch position. A rail may be taken from CH3 if that suits the bench;
which position the switch is in is then recorded by hand, like any other piece
of wiring.

The requirements below are shaped by four properties of this particular
instrument, each of which is a way a test can record a number that is not true:
it **clamps** a setting it cannot deliver instead of refusing it, it leaves
**constant-current** operation visible only in a status word, it has **one
output switch for two channels**, and in **series or parallel tracking** it
accepts and discards anything sent to channel 2.

### 10.1 Setting and reading

| ID | Requirement | Source | Verification |
|---|---|---|---|
| PSU-FR-001 | The driver shall set and read back each channel's output voltage and current limit, in volts and amps. | STK-13 | Test |
| PSU-FR-002 | A setting outside what the supply can deliver shall be refused before it is sent. The supply clamps silently, so a test that asked for 35 V would otherwise record a pass for a condition it never applied. | STK-13 | Test |
| PSU-FR-003 | A setpoint shall be rounded to the supply's programming resolution before it is sent, so that a value read back compares equal to the value written. | STK-13 | Test |
| PSU-FR-004 | A channel number the supply does not have shall be refused, naming the channels it does have. | STK-13 | Test |
| PSU-FR-005 | Setting a channel's voltage and current limit together shall set the limit first, so that a channel is never briefly protected by a previous setting. | STK-13 | Test |
| PSU-FR-006 | A setpoint or per-channel output change addressed to a channel the supply is slaving to another shall be refused, naming the tracking mode and what to do instead. In series and parallel tracking the supply accepts such a command and discards it, reporting nothing; the driver shall not be the component that turns that silence into a setpoint a test believes in. A tracking mode the status word does not decode shall be warned about and allowed, so that one unconfirmed status bit cannot disable setting altogether. The supply's own output switch and the safe state shall remain operable in every mode. | STK-13, STK-17 | Test |
| PSU-FR-010 | The driver shall measure each channel's output voltage and output current. A reply carrying its unit shall be read as a number. | STK-13 | Test |
| PSU-FR-011 | Output power shall be available, and shall be identified as derived from the two readings rather than measured. | STK-13 | Test |
| PSU-FR-012 | A single call shall return a channel's measurements, its setpoints and its regulation mode together, so that the mode qualifying a reading comes from the same moment as the reading. | STK-13 | Test |

### 10.2 Regulation and status

| ID | Requirement | Source | Verification |
|---|---|---|---|
| PSU-FR-020 | The driver shall report whether each channel is in constant voltage or constant current. A channel in constant current is not delivering the voltage that was set, and no voltage reading alone says so. | STK-13, STK-17 | Test |
| PSU-FR-021 | The driver shall decode the supply's status word - per-channel mode, tracking, beeper, output state and line rate - and shall retain the raw reply beside the decoded values. | STK-13 | Test |
| PSU-FR-022 | A status reply that is not the documented length shall be reported as such, naming the line rate as the likely cause, rather than decoded. | STK-13 | Test |
| PSU-FR-023 | The driver shall report whether a channel is *regulated*: energised, in constant voltage, and at its setpoint. | STK-13, STK-17 | Test |
| PSU-FR-024 | The driver shall be able to read and clear whatever the supply reports about a rejected command, carrying its text verbatim. | STK-13 | Test |

### 10.3 Output switching

| ID | Requirement | Source | Verification |
|---|---|---|---|
| PSU-FR-030 | The driver shall switch each channel on and off individually. The supply has one output switch for both channels, so a single channel is switched off by programming it to zero volts; the interface shall state that this is not an isolator and not a safety interlock. | STK-13 | Test, Inspection |
| PSU-FR-031 | A channel switched off shall retain the setpoint it was switched off at, and shall return to it when switched on. | STK-13 | Test |
| PSU-FR-032 | Setting a voltage on a channel that is switched off shall not energise it; the new value shall apply when it is next switched on. | STK-13 | Test |
| PSU-FR-033 | A channel's current limit shall remain in force whether or not the channel is switched on. | STK-13 | Test |
| PSU-FR-034 | When every channel has been switched off, the supply's own output switch shall be opened, so that "all off" is not two rails at zero volts. | STK-13 | Test |
| PSU-FR-035 | The supply's output switch shall be operable directly, on and off, without reference to individual channels. | STK-13 | Test |

### 10.4 Link and bench use

| ID | Requirement | Source | Verification |
|---|---|---|---|
| PSU-FR-040 | Connecting shall identify the supply and read its state, and shall change nothing: a supply powering a board must not be disturbed by a driver attaching to it. | STK-13, STK-17 | Test |
| PSU-FR-041 | Commands shall be paced on a real link. The supply has a small input buffer and no flow control, and a command it drops is silent. | STK-13 | Test |
| PSU-FR-042 | A bare port name shall be taken as a serial port rather than a network host. | STK-13 | Test |
| PSU-FR-043 | The driver shall provide a safe state - outputs off and rails at zero - without altering current limits, which are the protection set for whatever is connected. | STK-13, STK-17 | Test |
| PSU-FR-050 | The supply shall be registered as a bench driver, and a simulated supply shall answer the same command set with a load model, so that constant-current operation is verifiable without hardware. | STK-08, STK-13 | Test |
| PSU-FR-060 | A command-line interface shall expose identification, status, measurement, setting and output switching, emitting JSON, and shall warn when a channel it read is in current limit or is being slaved to another by the supply's tracking mode. | STK-13 | Test |

### 10.5 PSU non-functional

| ID | Requirement | Verification |
|---|---|---|
| PSU-NFR-001 | The driver shall add no mandatory third-party dependency; the serial library shall be an optional extra. | Test, Inspection |
| PSU-NFR-002 | No operation shall energise an output that the caller did not ask to be energised. | Test, Inspection |
| PSU-NFR-003 | Every value the supply reports shall be presented in SI units, with the regulation mode that qualifies it. | Test |

---

## 11. S2LP — ST S2-LP development kit

A sub-1 GHz transceiver on an evaluation board, reached over USB. The board runs
**ST's own CLI firmware** - the firmware ST's S2-LP DK GUI drives - and this
element is the host half only: no firmware of this project's runs on the kit
(STK-20, AD-20).

Three properties of that firmware shape the requirements below, and each is a
way a capture can be believed when it should not be. Reception is **polled**:
the firmware arms the radio when asked and hears nothing between one call and
the next. Timestamps are the **board's millisecond timer**, not a radio
timestamp. And the radio will accept a frequency the board cannot radiate.

### 11.1 The link to the firmware

| ID | Requirement | Source | Verification |
|---|---|---|---|
| S2LP-FR-001 | The driver shall communicate with ST's CLI firmware over the kit's USB serial port, as ST's GUI does, without replacing or modifying that firmware. | STK-19, STK-20 | Test, Inspection |
| S2LP-FR-002 | A command shall be checked against the firmware's declared argument types before it is sent, and a command or value the firmware would reject shall be reported naming the command and the argument. | STK-19 | Test |
| S2LP-FR-003 | A reply shall be read until the firmware's braces balance, rather than as a fixed number of lines, because the firmware answers some commands on one line and others over several. | STK-19 | Test |
| S2LP-FR-004 | A value the firmware writes in hexadecimal without a prefix shall be read as hexadecimal. A line the driver did not understand shall be kept, not discarded. | STK-19 | Test |
| S2LP-FR-005 | A long-running command shall be stoppable by the means the firmware provides, without resetting the board. | STK-19 | Test |

### 11.2 Registers

| ID | Requirement | Source | Verification |
|---|---|---|---|
| S2LP-FR-010 | The driver shall read and write any register of the transceiver, by name or by address, singly or as a block. | STK-19 | Test |
| S2LP-FR-011 | The driver shall hold the device's register map - every documented register by name and address, with its reset value, its access and its named bit fields - and shall decode a reading against it. | STK-19 | Test |
| S2LP-FR-012 | A named bit field shall be writable without disturbing the other fields of its register, and a value too wide for a field shall be refused rather than truncated. | STK-19 | Test |
| S2LP-FR-013 | A write to a register the device treats as read-only shall be refused, rather than sent and silently discarded. | STK-19 | Test |
| S2LP-FR-014 | The driver shall dump every register in one operation, reading consecutive addresses in blocks, and shall be able to report which registers differ from their reset values. | STK-19 | Test |
| S2LP-FR-015 | A reply whose register addresses do not match those asked for shall be reported as an error, not read as values. | STK-19 | Test |
| S2LP-FR-016 | The driver shall send any command strobe, by name or opcode. | STK-19 | Test |
| S2LP-FR-017 | The driver shall read the register values a test requires from a file of register names and values. The file shall tolerate the punctuation such files are written with - a space, `=`, `:` or `,` between name and value, comments, and an address in place of a name - and values shall be hexadecimal. | STK-19 | Test |
| S2LP-FR-018 | A register file that cannot be applied shall be refused, naming the file and the line: an unknown register, a value that does not fit a register, a read-only register, a register set twice, or a line that is not a setting. An empty file shall be refused rather than applied silently. | STK-19 | Test |
| S2LP-FR-019 | The driver shall apply a register file to the radio and confirm by read-back that it took, and shall check the radio against a file without writing to it. The check shall be available in two forms: the registers the file names, or additionally that every register it does not name is at its reset value. | STK-19 | Test |
| S2LP-FR-021 | Applying a register file shall be able to put the radio at its register defaults first, either by writing them or by a power-on reset, so that a file naming some registers produces a known state rather than one that depends on what ran before. The reset shall be confirmed by read-back before the file is written. The device's reset **strobe** shall not be offered for this: it resets the digital section and leaves the registers as they were. | STK-19 | Test |
| S2LP-FR-020 | The driver shall write the radio's current register values out as a file of the same form, so a radio configured by hand or by the vendor's GUI can be captured and replayed. Registers that cannot be written shall be omitted from it. | STK-19 | Test |

### 11.3 Radio configuration

| ID | Requirement | Source | Verification |
|---|---|---|---|
| S2LP-FR-030 | The driver shall set and read the carrier frequency, modulation, data rate, frequency deviation, channel filter bandwidth and output power. | STK-19 | Test |
| S2LP-FR-031 | A configuration operation shall report what the radio says it is set to afterwards, not what it was asked for. | STK-19 | Test |
| S2LP-FR-032 | A frequency outside the band the attached board is built for shall be refused, because the radio would accept it and transmit into a filter and matching network that do not pass it. | STK-19 | Test |
| S2LP-FR-033 | The board shall be identified at connection, and its band taken from what it reports rather than from configuration. Connecting shall change no radio setting. | STK-19 | Test |
| S2LP-FR-034 | Signal strength shall be reported in dBm, converted by the device's documented scale. | STK-19 | Test |

### 11.4 Transmitting, receiving and logging

| ID | Requirement | Source | Verification |
|---|---|---|---|
| S2LP-FR-040 | The driver shall transmit a payload given as bytes or as text, and shall transmit one repeatedly at an interval timed by the board rather than by the host. | STK-19 | Test |
| S2LP-FR-041 | The driver shall receive a packet, reporting its payload, its signal strength and the board's timestamp. Receiving nothing shall be reported as nothing received, and shall be distinguishable from receiving an empty packet. | STK-19 | Test |
| S2LP-FR-042 | The driver shall capture a number of packets, keeping the radio armed for the whole capture where the firmware allows it. | STK-19 | Test |
| S2LP-FR-043 | A capture shall record how many times the radio was re-armed during it, so that a capture with gaps cannot be quoted as a complete record of the air. | STK-19 | Test |
| S2LP-FR-044 | A capture that is cut short, by time or by the host, shall say so in its result rather than raise. | STK-19 | Test |
| S2LP-FR-045 | Every line exchanged with the board shall be loggable to a text file, host-timestamped and flushed per line, including lines the driver did not understand. | STK-19 | Test |
| S2LP-FR-046 | Every packet, sent and received, shall be loggable as one structured record per line, readable after an interrupted capture. Both logs shall be available at once, and a note shall be writable into both. | STK-19 | Test |

### 11.5 Bench use

| ID | Requirement | Source | Verification |
|---|---|---|---|
| S2LP-FR-050 | The kit shall be registered as a bench driver, and a simulated kit shall answer the same firmware command set with a register file and a modelled air interface, so that every operation is verifiable without hardware. | STK-08, STK-19 | Test |
| S2LP-FR-060 | A command-line interface shall expose identification, register dump and access, radio configuration, transmit, receive, capture and strobes, emitting JSON, and shall warn when a capture was not continuous. | STK-19 | Test |

### 11.6 S2LP non-functional

| ID | Requirement | Verification |
|---|---|---|
| S2LP-NFR-001 | The driver shall add no mandatory third-party dependency; the serial library shall be an optional extra. | Test, Inspection |
| S2LP-NFR-002 | No vendor source shall be redistributed in this repository. The register map shall hold facts about the device, not vendor prose. | Inspection |
| S2LP-NFR-003 | A measurement shall never be reported without the clock that produced it and that clock's resolution. | Test, Inspection |
| S2LP-NFR-004 | No operation shall transmit unless the caller asked for a transmission. | Test, Inspection |

---

## 12. PICO — Pico 2 + SHT30-D bench thermometer and its firmware

A Raspberry Pi Pico 2 (RP2350) reads a Sensirion SHT30-DIS, carried on a
DollaTek SHT30-D breakout module, over I2C, and reports temperature and
humidity to the host over USB CDC. It is the local-temperature measurement of
STK-21; STK-22 asks that the firmware say what it is.

The requirements are shaped by one property of the measurement: **a failed
reading must never look like a reading**. The sensor can be absent, a frame can
be corrupted on the bus, and the bus can hang; in each case the firmware says
so and reports no value, and the host driver raises rather than returning the
last good one. Reference documents and wiring: `docs/pico_sht30/`.

### 12.1 Firmware: host link and identity

| ID | Requirement | Source | Verification |
|---|---|---|---|
| PICO-FR-001 | The firmware shall accept one command per LF-terminated line over USB CDC ACM, ignoring CR, and shall send exactly one reply per command, beginning `ok` or `err <code> <text>`. | STK-21 | Test |
| PICO-FR-002 | `ver` shall report the product title and the firmware version, together with the build date (ISO 8601 UTC when injected by the build, tagged `local:` otherwise), protocol revision, board, board unique identifier, sensor part, sensor I2C address and uptime, each as one `key=value` token with no space inside a value. | STK-22 | Test |
| PICO-FR-003 | An unknown command, or a command with the wrong number of arguments, shall be refused with an `err` reply and shall have no effect. | STK-21 | Test |
| PICO-FR-004 | A command line longer than the line buffer shall be discarded whole and refused; it shall never be executed in part. | STK-21 | Test |
| PICO-FR-005 | `ver` shall answer whether or not the sensor is present, so that "no sensor" is distinguishable from "no Pico". | STK-21, STK-22 | Test |

### 12.2 Firmware: the sensor

| ID | Requirement | Source | Verification |
|---|---|---|---|
| PICO-FR-010 | The firmware shall reach the SHT30 on I2C0 at 100 kHz, SDA on GP4 and SCL on GP5, at address 0x44, each overridable at build time without a source edit. | STK-21 | Inspection, Test (build) |
| PICO-FR-020 | `temp` shall take one single-shot, high-repeatability measurement with clock stretching disabled, waiting at least the datasheet's maximum conversion time before reading the result. | STK-21 | Test |
| PICO-FR-021 | Every word received from the sensor shall be checked against its CRC-8 (polynomial 0x31, initial value 0xFF). A mismatch shall be reported as `err 5` and no value shall be reported. | STK-21 | Test |
| PICO-FR-022 | Temperature and humidity shall be converted with the datasheet formulas in integer arithmetic, rounded to the nearest thousandth, and reported in degrees Celsius and percent RH to three decimals, together with the raw words they came from. | STK-21 | Test |
| PICO-FR-023 | A sensor that does not acknowledge shall be reported as `err 4`, and a bus transfer that does not complete within its timeout as `err 6`. In neither case shall a value be reported. | STK-21 | Test |
| PICO-FR-024 | `status` shall report the sensor's status register, CRC-checked. | STK-21 | Test |
| PICO-FR-025 | The firmware shall soft-reset the sensor at start-up, and on `sreset`. | STK-21 | Test, Inspection |
| PICO-FR-026 | A failed check shall leave no partially updated reading behind for a caller to report. | STK-21 | Test |

### 12.3 Firmware: maintenance and build

| ID | Requirement | Source | Verification |
|---|---|---|---|
| PICO-FR-030 | `reset` shall reboot the Pico, and `bootsel` shall reboot it into the ROM's USB bootloader ready for a UF2 image. In both cases the `ok` reply shall be sent before the reboot. | STK-21 | Test |
| PICO-FR-031 | The firmware shall build with the Raspberry Pi Pico C SDK for the Pico 2 (RP2350, Arm Cortex-M33) into a UF2 image that can be copied onto the board. | STK-21 | Test (build) |

### 12.4 Host driver and bench use

| ID | Requirement | Source | Verification |
|---|---|---|---|
| PICO-FR-040 | Connecting shall identify the thermometer with `ver`, and shall refuse a firmware whose protocol major revision differs from the driver's. It shall send nothing the firmware does not define. | STK-21, STK-22 | Test |
| PICO-FR-041 | The driver shall expose the title and version, and the rest of `ver`, as typed values. | STK-22 | Test |
| PICO-FR-042 | The driver shall return temperature and humidity together with their raw words and a host timestamp. | STK-21 | Test |
| PICO-FR-043 | An `err` reply shall raise an error carrying the firmware's code; no reading shall be returned. | STK-21 | Test |
| PICO-FR-044 | The driver shall recompute each value from its raw word with the firmware's arithmetic, and shall refuse a reply in which they disagree. | STK-21 | Test |
| PICO-FR-045 | A bare port name shall be taken as a serial port rather than a network host. | STK-21 | Test |
| PICO-FR-046 | The driver shall decode the sensor status register, and shall provide sensor soft reset, Pico reboot and bootloader entry. | STK-21 | Test |
| PICO-FR-050 | The thermometer shall be registered as a bench driver, and a simulated thermometer shall answer the same command set with the same reply text, with injectable faults: sensor absent, CRC failure and bus timeout. | STK-08, STK-21 | Test |
| PICO-FR-060 | A command-line interface shall expose `ver`, `temp` (one reading or a series), `status`, `sreset` and `bootsel`, emitting JSON. | STK-21, STK-22 | Test |

### 12.5 PICO non-functional

| ID | Requirement | Verification |
|---|---|---|
| PICO-NFR-001 | The firmware's logic shall be separated from the hardware by a single HAL seam, so that it is unit tested on the host unchanged. | Inspection, Test |
| PICO-NFR-002 | The firmware shall be written to MISRA C:2012: no `<stdio.h>` formatting, no dynamic memory, no recursion, fixed-width types, and every deviation recorded where it occurs and in `docs/pico_sht30/Pico_SHT30_Notes.md`. | Inspection, Test |
| PICO-NFR-003 | The firmware's own sources shall compile with `-Wall -Wextra -Wconversion -Wshadow -Wstrict-prototypes` as errors, in both the target and the host test builds; the host tests shall run under AddressSanitizer and UndefinedBehaviorSanitizer. | Test |
| PICO-NFR-004 | The protocol shall be defined once, in `firmware/pico_sht30/include/protocol.h`, and the host driver's constants shall be checked against it by a test. | Test |
| PICO-NFR-005 | The host driver shall add no mandatory third-party dependency; the serial library shall be an optional extra. | Inspection, Test |

---

## 13. RUN — bench test runner

### 13.1 Bench configuration

| ID | Requirement | Source | Verification |
|---|---|---|---|
| RUN-FR-001 | The bench configuration shall be separate from the test specification, so the same suite runs on a different rig by pointing at a different configuration. | STK-08 | Test |
| RUN-FR-002 | A bench shall name each instrument by alias, driver and resource, and shall be loadable from JSON or YAML. | STK-08 | Test |
| RUN-FR-003 | Instrument drivers shall be selected by registered name, so a specification cannot name arbitrary code. | STK-08 | Test |
| RUN-FR-004 | Instruments shall connect on first use, and whatever was opened shall be closed on exit, including after a failure. | STK-08 | Test |
| RUN-FR-005 | The runner shall support replacing every instrument with its simulator, so a specification can be exercised without hardware. | STK-08 | Test |
| RUN-FR-006 | A run shall be recorded as simulated whenever no instrument on the bench is real hardware, so simulated results cannot be mistaken for measurements. | STK-08 | Test |

### 13.2 Test specification

| ID | Requirement | Source | Verification |
|---|---|---|---|
| RUN-FR-010 | A test specification shall be data, not code, and shall be loadable from JSON (requiring no third-party package) or YAML. | STK-08 | Test |
| RUN-FR-011 | A specification shall declare a suite name, optional setup and teardown steps, and one or more named tests, each with steps. | STK-08 | Test |
| RUN-FR-012 | Each test shall be able to name the requirement it verifies. | STK-08 | Test |
| RUN-FR-013 | A step shall name an instrument method and its arguments, and shall be able to address values inside the returned result by path. | STK-08 | Test |
| RUN-FR-014 | A malformed specification shall be rejected with a message identifying what to fix. | STK-08 | Test |
| RUN-FR-015 | A test shall be markable as skipped, with a reason. | STK-08 | Test |
| RUN-FR-016 | A step shall be able to save its result under a name, and any later step shall be able to use that saved value - or a value addressed inside it - as an argument or as a limit, optionally rendered through a format template. A reference to a name nothing has saved shall be refused, naming what has been saved. Without this a chained test would have to write down what an earlier step established, which makes the test assert its own input. | STK-08, STK-16 | Test |

### 13.3 Limits

| ID | Requirement | Source | Verification |
|---|---|---|---|
| RUN-FR-020 | A limit shall support a lower bound, an upper bound, or both. | STK-08 | Test |
| RUN-FR-021 | A limit shall support a nominal value with an absolute or percentage tolerance. | STK-08 | Test |
| RUN-FR-022 | A measured value shall be scalable before the limit is checked, so a limit can be stated in convenient units. | STK-08 | Test |
| RUN-FR-023 | A limit shall render as human-readable text for the report, and a failure shall state by how much the value missed. | STK-08 | Test |
| RUN-FR-025 | A measurement shall be reportable through a format template, so a value whose meaning is not decimal - an identifier, an address, a mask - reads in the record as it reads on the part. The template shall not affect the check, which remains against the number; the number shall be retained in the result record; and the limit's own bounds shall be rendered the same way, since a hexadecimal value beside decimal bounds is less legible than either alone. A template that cannot be applied shall be an error, not a silent fall back to the number. | STK-08, STK-16 | Test |
| RUN-FR-024 | A limit shall support exact comparison against text - a version, a device name - reported as the text itself rather than as a number. Matching shall be exact on the stripped value: a looser rule would pass 1.4.20 for 1.4.2, which is the failure such a limit exists to catch. | STK-08, STK-16 | Test |

### 13.4 Execution

| ID | Requirement | Source | Verification |
|---|---|---|---|
| RUN-FR-030 | The runner shall execute each specification's setup, tests and teardown, and shall record per-measurement, per-step, per-test and per-run outcomes. | STK-08 | Test |
| RUN-FR-031 | A measurement outside its limit shall be reported as a **failure**; a step that could not be executed shall be reported as an **error**. These shall be distinguished throughout. | STK-08 | Test |
| RUN-FR-032 | A setup failure shall abort the suite, because no measurement taken afterwards would be meaningful. Teardown shall run regardless of outcome. | STK-08 | Test |
| RUN-FR-033 | A test failure shall not stop later tests. Stopping after an error shall be selectable. | STK-08 | Test |
| RUN-FR-034 | A specification shall not be able to invoke private driver methods. | STK-08 | Test |
| RUN-FR-035 | The runner shall verify the bench provides every instrument the specification uses before executing anything. | STK-08 | Test |
| RUN-FR-036 | A step shall be able to name a driver property as well as a method. A property shall be read when the step executes and shall take no arguments. | STK-08 | Test |
| RUN-FR-037 | The run record and every report shall identify each instrument the run used - driver, model, serial number, resource and, where the instrument reports one, the firmware build - recorded after the run rather than before. An instrument that would not identify shall be recorded as such rather than omitted. | STK-08, STK-16, STK-17 | Test |

### 13.5 Reporting

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

## 14. Assumptions and constraints

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
| CON-09 | The Pico 2 thermometer firmware **builds** (Pico SDK 2.1.1, Arm GNU 14.2.1, UF2 produced) and its portable logic passes its host unit tests; it has **not** yet been run on a Pico 2 with a sensor attached. Bench confirmation items are in `docs/pico_sht30/Pico_SHT30_Notes.md` §7 (PICO-OPEN-01 … -04). |
| ASM-10 | The SHT30-D module is powered from the Pico's 3V3(OUT) and carries its own I2C pull-ups; its ADDR pin is tied low (0x44). |
| CON-06 | Markdown-to-Robot-Framework translation (STK-12) is not implemented in this revision. The driver's return types are constrained by JLINK-FR-081 so that it can be added without changing the driver. |
