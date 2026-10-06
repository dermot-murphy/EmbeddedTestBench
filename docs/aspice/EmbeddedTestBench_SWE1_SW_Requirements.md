<img src="../../assets/brand/svg/logos/embeddedtestbench-logo-compact.svg" alt="Embedded Test Bench" width="240">

# Software Requirements Specification

*Automotive SPICE® PAM v4.0 | SWE.1 Software Requirements Analysis*

---

## 1. Document Identification & Control

| Field | Value | Field | Value |
|---|---|---|---|
| **Document ID** | ETB-SWE1-001 | **Version** | 1.27 |
| **Project** | Embedded Test Bench | **Date** | 2026-10-06 |
| **Status** | Draft | **Classification** | Internal |
| **Author** | Claude | **Reviewer** | Dermot Murphy |
| **Approver** | Dermot Murphy | **Related Process** | SWE.1 |

> **Note — Reviewer independence (ETB-DEV-002):** The Reviewer and Approver are the same person (Dermot Murphy). This is accepted under deviation record **ETB-DEV-002** (`docs/aspice/EmbeddedTestBench_DEV002_Independent_Review_Deviation.md`) on the basis that Embedded Test Bench has a single human team member.

---

## 2. Revision History

| Version | Date | Author | Description of Change |
|---|---|---|---|
| 0.1 | 2026-09-19 | Claude | Initial |
| 0.2 | 2026-09-23 | Claude | Section 14 added: `DMM-` requirements for the TTi 1604 multimeter (DMM-FR-001…026, DMM-NFR-001…004). Sections 15 to 18 renumbered. |
| 0.3 | 2026-09-23 | Claude | BLE-FR-025 (choose the strongest advertiser) and DMM-FR-045 (the bench states what the simulated meter reads) added; RUN subsection numbering corrected after the section 14 insertion. |
| 0.4 | 2026-09-24 | Claude | RUN-FR-054…057 added: a specification's safety warning, printed before the bench is opened, and the acknowledgement that gates a warned run on real hardware. |
| 0.5 | 2026-09-25 | Claude | BLE-FR-026 (select by name fragment) and BLE-FR-046…049 (connect window, per-command reply wait, a command the sensor disconnects after, failed links closed) added. BLE-FR-102, -105, -106 and -107 revised and BLE-FR-109…116 added for command documents: results in the order error, skip, fail, pass; variables; connect and disconnect steps; per-step timeouts; `<disconnect>`; notes; the event log; the standalone runner (#46, #48). |
| 0.6 | 2026-09-26 | Claude | PSU-FR-002 rationale corrected: the supply rejects an out-of-range setting, it does not clamp it (#64). PSU-FR-003 no longer promises an exact read-back (#64). PSU-FR-021 and -022 describe the status word as the supply sends it, without a line rate (#63). Header version brought into line with this history. |
| 0.7 | 2026-09-30 | Claude | STK-21 and STK-22 added. Section 15 added: `PICO-` requirements for the Pico 2 + SHT30-D thermometer and its firmware (PICO-FR-001…060, PICO-NFR-001…006); CON-09 and ASM-10 added. Sections 16 to 19 renumbered (#104). |
| 0.8 | 2026-10-02 | Claude | #115: CORE-FR-061 (read a stream as it arrives; discard unread input, the operating system's included) and CORE-FR-062 (a virtual-clock simulator is given the read timeout). DMM-FR-016 revised: the resistance multiplier is derived from the range resolution, not assumed. DMM-FR-021 revised: annunciator bit positions follow the manufacturer's note. DMM-FR-027 … -033 (stream reading, frame validation, confirmation from the readings, ranges, fresh measurement, the frequency gate, Hz on AC only), DMM-FR-046 (a simulator with the meter's resolution and reading rate), DMM-FR-070 (command line, already implemented, now declared), DMM-FR-080 and -081 (bench and panel tests). CON-03 corrected; CON-10 added. |
| 0.9 | 2026-10-02 | Claude | #116: RUN-FR-007 (a relative input path in a bench file is found beside the bench file) and RUN-FR-017 (a relative input path in a step is found beside the specification) added, so a run started outside the TestTools checkout behaves as one started inside it. |
| 1.0 | 2026-10-02 | Claude | #124: BLE-FR-071 added - on the command line, `--select` takes an address, a name or part of a name, and `cmd --addr` connects to the address given. |
| 1.1 | 2026-10-02 | Claude | #126: CORE-FR-060 revised - each record carries the short name of the instrument it came from; CORE-FR-063 (each instrument's records carry its own name, set from construction, with a default per driver) and RUN-FR-008 (the specification allocates names, the bench attaches them, the specification wins, no two share one) added. |
| 1.2 | 2026-10-03 | Claude | #127: §15.5 added - PICO-FR-070 … -076, reflashing the Pico 2 thermometer with no BOOTSEL press: reaching the bootloader (an already-mounted drive, `bootsel`, or the 1200-baud reset), checking the UF2, the copy and reboot, confirming the build afterwards, bounded waits and named errors, the `flash` command, and the simulated board. PICO non-functional renumbered 15.6. CON-09 extended to PICO-OPEN-05. §15.5 note and CON-09 updated for the hardware confirmation on a real Pico 2 on 2026-10-03: PICO-OPEN-01 and -05 closed on Windows; PICO-OPEN-02 not yet tested, as no sensor is connected. |
| 1.3 | 2026-10-03 | Claude | #131: the Pico thermometer answers an `rd` command set in place of `ver` and `temp`, and `reset` is renamed `ecureset`. PICO-FR-006 (`rd name`, `copyright`, `version`, `sha`), PICO-FR-007 (`NAK` for an unknown option), PICO-FR-027 (`rd temperature` to two places, or `Error`), PICO-FR-047 (the driver's `rd` and `NoReadingError`) and PICO-FR-061 (`info`, `rd` and `ecureset` on the command line) added. PICO-FR-001, -002 (now the version scheme and the injected commit), -003, -005, -020 … -023, -030, -040 … -042, -046, -050 and -060 revised. PICO-FR-044 (the raw-word cross-check) withdrawn: the reply no longer carries raw words. The convention for a withdrawn requirement is stated in §15. With #127 merged, `flash` confirms the new build by the `rd` command set: PICO-FR-071, -073 and -076 revised, so the image is recognised by the firmware's name and checked by `rd name`, `rd version` and `rd sha` against the version and commit SHA stored in it, in place of `ver`, the title and the build date; the §15.5 note records the `rd` firmware flashed and confirmed on a real Pico 2 on 2026-10-03. CON-09 records that the change has been built and run on a real Pico 2 (2026-10-03), but not yet with the SHT30-D module connected. |
| 1.4 | 2026-10-03 | Claude | #134: RUN-FR-059 added - running a selected subset of a specification's test cases, those not selected recorded as skipped, "not selected". |
| 1.5 | 2026-10-03 | Claude | #135: CORE-FR-064 (an event record's `kind` and `data`) and RUN-FR-060 (the runner's structured run, test case and step records) added. |
| 1.6 | 2026-10-03 | Claude | #136: RUN-FR-061 … -065 added - the run control channel: 127.0.0.1 only, between steps only, pause and resume, abort with teardown, restart with saved values kept, refusals, and every request in the event log. |
| 1.7 | 2026-10-03 | Claude | #137: STK-23 (watch and control a run, issue #130); element `VIEW-`; §16.6 VIEW-FR-001 … -009 - the test run viewer: 127.0.0.1 and nothing from another site, request guards, the run rebuilt from the event log, the Run page, live events, control, starting a run, the safety warning, attaching and the Event log page. |
| 1.8 | 2026-10-03 | Claude | #138: VIEW-FR-010 … -012 added - each instrument's commands paired with their replies, the supply's and probe's front panels, and a step's own traffic. |
| 1.9 | 2026-10-03 | Claude | #139: S2LP-FR-080 (every packet as a structured `rf_packet` record) and VIEW-FR-013 … -015 (the RF and BLE pages) added. The dongle was checked: it already logs every advertising report as `< +adv t=<board us> addr= type= rssi= pdu= ch= name= data=`, so it needed no change. |
| 1.10 | 2026-10-03 | Claude | #140: CORE-FR-065 (`reading` records), PSU-FR-044, PICO-FR-048, DMM-FR-034 (each driver logs its readings) and VIEW-FR-016 … -018 (the Graphs page) added. |
| 1.11 | 2026-10-03 | Claude | #148: VIEW-FR-019 … -021 added - the Event log page's pause and resume, and its filters by instrument, kind of event, sensor and test. |
| 1.12 | 2026-10-03 | Claude | #149: VIEW-FR-022 … -024 added - the status bar: run state and instruments, test case and steps, and the estimated time left. |
| 1.13 | 2026-10-03 | Claude | #141: VIEW-FR-025 … -027 added - the viewer from another PC: access token, read-only, HTTPS, the control channel still on 127.0.0.1. |
| 1.14 | 2026-10-03 | Claude | #151: S2LP-FR-081 … -083 added - CONFIG parameters named, waveform sample order and ODR, and frames decoded as the firmware builds them (RESPONSE layout corrected). |
| 1.15 | 2026-10-03 | Claude | #152: VIEW-FR-028 … -030 added - rf_monitor's Latest Data, Config and Identification screens. |
| 1.16 | 2026-10-03 | Claude | #153: VIEW-FR-031 … -033 added - rf_monitor's Environment, Short Interval and Ticks graphs. |
| 1.17 | 2026-10-03 | Claude | #154: VIEW-FR-034 … -036 added - rf_monitor's TWF screen: reassembly, waveform and spectrum. |
| 1.18 | 2026-10-03 | Claude | #155: VIEW-FR-037 … -039 added - rf_monitor's Diagnostics and Sync screens. |
| 1.19 | 2026-10-03 | Claude | #156: VIEW-FR-040 … -042 added - notes saved with the run, and the report export as HTML, printable to PDF. |
| 1.20 | 2026-10-03 | Claude | #157: S2LP-FR-084 (`read_setup`), RUN-FR-066 (`read_setup` over the control channel) and VIEW-FR-043 … -045 (the ST GUI page) added. |
| 1.21 | 2026-10-04 | Claude | #170: RUN-FR-007 and RUN-FR-017 say "the EmbeddedTestBench checkout" after the repository rename. The requirements are unchanged. |
| 1.22 | 2026-10-04 | Claude | #176: CON-04 and CON-10 restated after the first hardware qualification campaign (TB-SYS5-002). The J-Link and the TTi 1604 have now run against physical hardware, with the defects found named. |
| 1.23 | 2026-10-04 | Claude | #183: product renamed to Embedded Test Bench - document file name prefix `EmbeddedTestBench_`, identifier prefix `ETB-` (was `TB-`), product name in prose. Earlier revision rows keep the names in use when they were written. |
| 1.24 | 2026-10-05 | Claude | #204: Review & Approval table points to the merge of the pull request that last changed the document, which is the review and approval (ETB-SUP8-001 §5.7); no per-change signatures or dates. |
| 1.25 | 2026-10-05 | Claude | #194: the compact brand logo added above the title, the same line in every controlled document (ETB-SUP8-001 §6.3). |
| 1.26 | 2026-10-05 | Claude | #180: BLE-FR-049 revised - a link that fails to establish (HCI reason 0x3E) is tried again, up to three attempts in all as a `connect` step's are, each failed attempt logged; no other failure is tried again, and a `connect` step makes no more attempts than its own. |
| 1.27 | 2026-10-06 | Claude | #60: BLE-FR-119 added - timeouts by command prefix in a command document, with a per-run override and the timeout that applied stated in each result; BLE-FR-112's empty cell now defers to it. |

---

## 3. Purpose & Scope

### 3.1 Purpose

This Software Requirements Specification refines the system-level requirements of
ETB-SYS2-001 into software-specific, implementable requirements for **Embedded Test Bench**,
the bench test tooling in this repository. It is the direct input to software
architectural design (SWE.2) and defines the verification criteria used in
SWE.4 to SWE.6.

This document satisfies **Automotive SPICE® PAM v4.0, SWE.1 — Software
Requirements Analysis**.

### 3.2 Referenced Documents

| Document ID | Title | Version |
|---|---|---|
| ETB-SYS2-001 | Embedded Test Bench System Requirements Specification | 0.1 |
| ETB-SYS3-001 | Embedded Test Bench System Architecture Description | 0.1 |
| ETB-SWE2-001 | Embedded Test Bench Software Architecture Description | 0.1 |
| ETB-SWE3-001 | Embedded Test Bench Software Detailed Design | 0.1 |
| ETB-SWE4-001 | Embedded Test Bench Software Unit Verification | 0.1 |
| ETB-RTM-001 | Embedded Test Bench Requirements Traceability Matrix | 0.1 |
| ETB-SUP8-001 | Embedded Test Bench Configuration Management Plan | 0.1 |

### 3.3 Scope

Embedded Test Bench is host-side software for automated and semi-automated electronics
bench testing. It provides instrument drivers, analysis of captured records, and
a declarative test runner that drives a bench of instruments and produces
pass/fail evidence.

It is a **test tool**: it is not part of any delivered vehicle software and
carries no ASIL classification. It is developed to this process discipline
because measurement results derived from it are used as evidence.

Out of scope: target application firmware, GPIB, hardware fixture design, and
any instrument not listed in §5.

One piece of embedded software **is** in scope, and is the exception that proves
the rule: the bench dongle's firmware (§11). It is part of the instrument, not
part of any product, and it exists because the measurement it makes - a radio
event timestamped to the microsecond - cannot be made from the host side of a
USB link. It is specified, designed and traced here like the rest of the item.

---

## 4. Stakeholder requirements

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
| STK-23 | Watch a bench test run while it goes, and control it: start one or attach to one, pause, restart from a chosen step, or abort, and see each test case, step and instrument's commands and responses (issue #130). |

## 5. Element structure

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
| `VIEW-` | `benchtools.viewer` | The test run viewer: a browser page onto a run. Separate from `RUN-` because it is a client of the runner - of its event log and control channel - and sits above it in the layering, so the runner never depends on it. |

---

## 6. CORE — instrument-agnostic foundations

### 6.1 Instrument link

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

### 6.2 Generic instrument base

Not every bench instrument speaks SCPI. A debug probe (§10) is driven over GDB/MI,
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

### 6.3 SCPI instrument base

Extends §6.2 with the SCPI and IEEE 488.2 vocabulary.

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

### 6.4 Validation and shared types

| ID | Requirement | Source | Verification |
|---|---|---|---|
| CORE-FR-030 | A shared enumeration base shall accept a member, a member name or a SCPI mnemonic, case-insensitively, and shall reject anything else with a message listing the valid values. | STK-07 | Test |
| CORE-FR-031 | Shared validation shall check ranges, channel availability and enumerated choices, raising a message that names the setting, the offending value, the permitted range and the unit. | STK-03, STK-07 | Test |

### 6.5 Simulator harness

| ID | Requirement | Source | Verification |
|---|---|---|---|
| CORE-FR-050 | A build's manifest - the version and build date its build system recorded beside the image - shall be readable by any element that needs it, and the diagnostic for a missing one shall name every path searched and take from the caller the sentence saying how that particular build produces one. | STK-07, STK-16 | Test |
| CORE-FR-061 | The link layer shall support instruments that send without being asked: reading whatever bytes have arrived without waiting for an end-of-message - which a serial port never signals - and discarding everything received but not yet read, including input held by the operating system, so that a reading taken on request is not one that was waiting in a buffer. | STK-18 | Test |
| CORE-FR-062 | A simulated instrument that streams on a virtual clock shall be told how long the driver is prepared to wait, so that output due later than that is a timeout, as it is on a real link, rather than data the driver would never have received. | STK-07, STK-18 | Test |
| CORE-FR-063 | Each instrument shall carry a short event-log name - 1 to 8 characters, an upper-case letter then A-Z, 0-9 or _ - and every record logged by the instrument or by anything it owns (its transport, its sessions) shall carry that name, from the instrument's construction on, so two instruments of one driver are told apart. Without a name given, it shall be the driver's default: `PSU`, `BLE`, `JLINK`, `RF`, `SCOPE`, `DMM`, `TEMP` (Pico 2 + SHT30-D thermometer); a record from nothing named shall be `BENCH` (#126). | STK-19 | Test |
| CORE-FR-060 | Every instrument's and the runner's log records shall be writable, while a run is in progress, to one event log of one JSON object per line, each carrying the short upper-case name of the instrument it came from (`PSU`, `BLE`, `RF`, `TEMP`, ...) or `TEST` for the runner, so that another program can follow the run as it happens and tell its sources apart. | STK-19 | Test |
| CORE-FR-064 | A record in the event log shall be able to carry, beside its text, a `kind` naming what happened and a `data` object with its details, so that a reader can follow the run without parsing text. `data` shall be standard JSON - a value that is not finite written as text, bytes as hex, a long sequence cut short and saying so - and a reader that ignores the two fields shall be unaffected. | STK-19 | Test |
| CORE-FR-065 | A driver shall be able to log a measured value as a `reading` record - quantity, value, unit, and details such as the channel - where it has the value in hand, so a reader of the event log can graph it without parsing the instrument's reply. | STK-23 | Test |

### 6.6 Simulation

| ID | Requirement | Source | Verification |
|---|---|---|---|
| CORE-FR-040 | A shared simulator harness shall provide SCPI message dispatch, compound-message splitting, the IEEE 488.2 mandated queries, an event queue and binary replies, so each instrument's simulator implements only its own behaviour. | STK-07 | Test |
| CORE-FR-041 | An unrecognised command shall be recorded in the simulated event queue rather than ignored, so that a driver which misspells a command fails a test instead of passing silently. | STK-07 | Test |

### 6.7 CORE non-functional

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

## 7. ANA — analysis of captured records

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
| ANA-FR-022 | Analysis shall hold repeated readings of one quantity, each with what it was read from and when, and report how many were taken against how many were asked for, the lowest, highest and mean, and the spread between the lowest and highest. A set that got fewer readings than asked for shall keep those it got. | STK-05 | Test |

---

## 8. INST — requirements common to all drivers

| ID | Requirement | Source | Verification |
|---|---|---|---|
| INST-FR-001 | A driver shall be provided for any instrument answering ``*IDN?``, supporting identification, error-queue reading and raw SCPI, for instruments without a dedicated driver. | STK-07, STK-08 | Test |
| INST-FR-002 | Each driver shall declare the simulator used for a ``sim://`` resource, so the link layer needs no knowledge of instruments. | STK-07 | Test |
| INST-FR-003 | Each driver's capability envelope shall be data-driven, so another model in the same family can be supported without code change. | STK-07 | Test |

---

## 9. SCOPE — Tektronix TDS3014B driver

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

## 10. JLINK — SEGGER J-Link debug probe driver

The probe is not an instrument in the SCPI sense: it does not answer `*IDN?` and
has no error queue. It is nonetheless a *bench instrument* — it is configured,
it is commanded, and it yields measurements — so it implements the generic base of
§6.2 and is usable from the runner of §15.

### 10.1 Link to the probe

| ID | Requirement | Source | Verification |
|---|---|---|---|
| JLINK-FR-001 | The driver shall communicate with the target through the GDB machine interface (GDB/MI), parsing result, asynchronous, stream and prompt records, including nested tuples and lists, C-string escapes, and repeated result names. | STK-09 | Test |
| JLINK-FR-002 | The driver shall issue MI commands with a sequence token and correlate each reply to its command, shall surface an MI error as a typed exception naming the command and the reason, and shall drain asynchronous records that arrive between commands rather than discarding them. | STK-09 | Test |
| JLINK-FR-003 | The driver shall locate and launch the SEGGER J-Link GDB Server and a GDB for the target architecture, searching the executable names used on Windows first, on `PATH` and then in the directories the SEGGER and Arm installers use, shall accept a GDB only if it can debug an ARM target, and shall report a clear diagnostic naming the missing tool and where it is normally installed. | STK-09, STK-11 | Test |
| JLINK-FR-004 | The driver shall attach to a GDB server already listening, whether started by the user or running on another host, and shall not attempt to spawn a server on a host that is not the local one. | STK-09, STK-11 | Test |
| JLINK-FR-005 | The driver shall close the link and stop only the server it started itself, leaving a server it merely attached to running. | STK-09 | Test |
| JLINK-FR-006 | When the link closes, the driver shall leave the target's core running unless the caller asked for it to stay halted. The GDB Server halts the core on attach and does not resume it on detach, so a read or a verification would otherwise stop the firmware it was looking at (issue #69). | STK-09 | Test |

### 10.2 Target configuration

| ID | Requirement | Source | Verification |
|---|---|---|---|
| JLINK-FR-010 | The driver shall accept the target device name, debug interface (SWD or JTAG), interface speed, probe serial number, and the core clock frequency, and shall hold each probe's capability envelope — hardware breakpoint count, watchpoint count, RTT channel count and maximum transfer size — as data rather than in code. | STK-09 | Test, Inspection |
| JLINK-FR-011 | The driver shall load target symbols from an ELF file, reporting a missing or unreadable file before any target operation is attempted. | STK-09 | Test |

### 10.3 Programming and verification

| ID | Requirement | Source | Verification |
|---|---|---|---|
| JLINK-FR-020 | The driver shall programme the target from an ELF or Intel HEX file and report the sections written, their addresses, their sizes and the elapsed time. It shall keep caller-named address ranges across the programming, writing them back and checking they read back, because programming an image that holds part of a page erases the rest of that page (issue #69). | STK-09 | Test |
| JLINK-FR-021 | The driver shall verify the target's memory against the binary section by section, and shall report per-section verdicts, not merely an overall result. | STK-09 | Test |
| JLINK-FR-022 | A verification mismatch shall raise, naming the sections that differ. A verification over an empty section list shall be reported as not matched, never as a pass. | STK-09 | Test |
| JLINK-FR-023 | The driver shall erase the target's non-volatile memory, from reset with the core halted, and shall confirm the erasure by reading the flash back rather than trusting the server's report, raising if it did not happen. | STK-09 | Test |
| JLINK-FR-024 | The driver shall report what the build system recorded about the image it programmed - the version and the build date - from the manifest beside that image, so a test can state the version it put on a part rather than repeating one into a specification where it would go stale. | STK-09, STK-16 | Test |

### 10.4 Execution control

| ID | Requirement | Source | Verification |
|---|---|---|---|
| JLINK-FR-030 | The driver shall reset the target, optionally halting at the reset vector, and shall run, halt, resume and single-step the core. | STK-09 | Test |
| JLINK-FR-031 | The driver shall report whether the core is halted, its program counter, and its register values. | STK-09 | Test |
| JLINK-FR-032 | The driver shall wait for the target to halt with a bounded timeout, and shall report the reason for the halt — breakpoint, watchpoint, step, signal or an unrecognised reason — rather than only that it stopped. | STK-09 | Test |
| JLINK-FR-033 | The driver shall set a breakpoint by source location, function or address, optionally temporary, optionally conditional, and optionally forced into hardware; it shall list, delete and clear breakpoints. | STK-09 | Test |
| JLINK-FR-034 | The driver shall refuse to set more hardware breakpoints than the probe's envelope allows, reporting the limit, rather than letting the request fail on the target. | STK-09 | Test |
| JLINK-FR-035 | The driver shall set watchpoints on a variable or address for write, read, or either access, within the probe's watchpoint envelope. | STK-09 | Test |
| JLINK-FR-036 | The driver shall run the target to a given location, reporting whether it arrived there or halted for another reason. | STK-09 | Test |

### 10.5 Target state

| ID | Requirement | Source | Verification |
|---|---|---|---|
| JLINK-FR-040 | The driver shall read and write target memory of arbitrary length, splitting transfers to the probe's maximum transfer size, and shall provide byte, half-word and word accessors. | STK-09 | Test |
| JLINK-FR-041 | The driver shall read and write a variable by name, returning integers, floating-point values, booleans, strings and structures (as a field-by-field mapping, nested as the type nests) as the debug information describes them, and shall report a variable's address and size. | STK-09 | Test |
| JLINK-FR-042 | The driver shall evaluate an arbitrary expression in the target's context. | STK-09 | Test |
| JLINK-FR-043 | The driver shall read a field of one to eight bytes as an integer in a byte order the caller states, because the byte order and width of a record programmed into a part are properties of that record and not of the core that loads it. A width or byte order outside what is supported shall be refused, since a misspelling would otherwise read a plausible and entirely wrong number. | STK-09 | Test |
| JLINK-FR-045 | The driver shall read the call stack, reporting for each frame its level, function, source file and line, and the frame address. | STK-09 | Test |

### 10.6 Real Time Transfer

| ID | Requirement | Source | Verification |
|---|---|---|---|
| JLINK-FR-050 | The driver shall read from and write to an RTT channel without halting the core. | STK-09 | Test |
| JLINK-FR-051 | The driver shall read RTT as whole lines, retaining a partial line until its terminator arrives, and shall report how many lines are waiting. | STK-09 | Test |
| JLINK-FR-052 | The driver shall wait for RTT output matching a regular expression with a bounded timeout, and on timeout shall report both the pattern sought and the text that did arrive. | STK-09 | Test |
| JLINK-FR-053 | The driver shall send a command over RTT and return the matching response, so a firmware console is usable as a test interface. | STK-09, STK-10 | Test |
| JLINK-FR-054 | The driver shall report how many RTT lines arrive within a bounded interval, so that "the target is running" is a measurement a limit can fail rather than a timeout that raises. A target that started and said nothing is a failed test, not a broken bench. | STK-09, STK-10 | Test |
| JLINK-FR-055 | The driver shall log every RTT line to a file as it arrives, flushed per line so the log survives a target or host failure, and shall retain the complete history independently of the lines consumed by reads. | STK-09 | Test |

### 10.7 Timing between lines of code

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

### 10.8 Bench and command-line use

| ID | Requirement | Source | Verification |
|---|---|---|---|
| JLINK-FR-080 | The probe shall be registered as a bench driver, so a bench configuration and a test specification reference it by name like any instrument. | STK-10 | Test |
| JLINK-FR-081 | Every probe operation usable as a test step shall return a value or a record of plain types, so a declarative specification can assert on it without driver-specific code. | STK-10, STK-12 | Test |
| JLINK-FR-090 | A simulated probe shall answer the GDB/MI dialogue the driver uses, with a deterministic firmware model — symbols, memory, call stacks, RTT traffic, ITM events and a known interval between two locations — so the driver is fully verifiable without a probe or a target. | STK-09 | Test |
| JLINK-FR-100 | A command-line interface shall expose identification, flashing, verification, erasure, reset, run, halt, memory and variable access, the call stack, RTT and timing, emitting JSON so results are usable from a script. | STK-09, STK-12 | Test |
| JLINK-FR-101 | The driver shall be able to read RTT without ever stopping the target: the GDB Server started with `-nohalt` and GDB never attached. A bench shall be able to offer this as a distinct driver, so a specification that requires it is refused a probe that would attach. | STK-09, STK-10 | Test |
| JLINK-FR-102 | The driver shall take a number from each of the next N RTT lines matching a pattern, counting only lines that arrive after it is asked, and return what it got when fewer arrive in time. | STK-09, STK-10 | Test |

### 10.9 JLINK non-functional

| ID | Requirement | Verification |
|---|---|---|
| JLINK-NFR-001 | The driver shall add no mandatory third-party runtime dependency. | Inspection, Test |
| JLINK-NFR-002 | The driver shall run on Windows and on Linux, with no POSIX-only facility on either the process link or the RTT link. | Inspection, Test |
| JLINK-NFR-003 | Both links to the probe — GDB/MI and RTT — shall be capable of being TCP connections to a host other than the one running the driver, so that the driver can run inside a container while the probe is attached elsewhere. | Test, Inspection |
| JLINK-NFR-004 | A measurement shall never be reported without the method that produced it and that method's resolution. | Test |

---

## 11. BLE — Nordic dongle and its firmware

The element has two halves that must agree: firmware on an nRF52840 dongle, and
a host driver. Requirements are written once and apply to whichever half
implements them; §11.6 says which.

### 11.1 The host link

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

### 11.2 Scanning and selection

| ID | Requirement | Source | Verification |
|---|---|---|---|
| BLE-FR-020 | The dongle shall scan for advertising devices for a given duration and report each device once, with its address, address type, signal strength and advertised name. | STK-15 | Test |
| BLE-FR-021 | A device that advertises no name shall be reported with an empty name rather than omitted. | STK-15 | Test |
| BLE-FR-022 | Scanning shall be filterable by name, by address and by minimum signal strength, and the filter shall be applied in the firmware. | STK-15 | Test |
| BLE-FR-023 | The host shall select one sensor, by index, address, name or object, and that selection shall persist for later commands. The address type shall travel with the address. | STK-15 | Test |
| BLE-FR-024 | Selecting an address that no scan has seen shall be permitted, so a suite that knows its sensor need not scan first. | STK-15 | Test |
| BLE-FR-025 | The host shall be able to choose the sensor heard most strongly, so that a specification can address whichever board is on the bench without naming one. Strength is received power at the dongle and is a property of the link at that moment, not of which board is nearest; a tie shall resolve to the lower scan index, so that repeating a scan selects the same board rather than alternating. Choosing from an empty scan shall be refused where it happens, because the alternative surfaces at connect time and reads as a link fault rather than an empty room. | STK-15 | Test |
| BLE-FR-026 | The host shall choose, from the last scan, the strongest sensor whose advertised name contains a given fragment, ignoring case unless asked not to, and shall name the sensors it heard when none matches. The firmware's own name filter is case-sensitive. | STK-15 | Test |

### 11.3 UART over BLE

| ID | Requirement | Source | Verification |
|---|---|---|---|
| BLE-FR-040 | The dongle shall connect to the selected sensor, discover Nordic's UART Service, and subscribe to its notifications. | STK-14 | Test |
| BLE-FR-041 | The connection interval shall be reported, because it bounds every latency measured over that link. | STK-14 | Test |
| BLE-FR-042 | The host shall write bytes or text to the sensor without waiting for a reply. | STK-14 | Test |
| BLE-FR-043 | The host shall send a command and return the sensor's reply, in one operation. | STK-14 | Test |
| BLE-FR-044 | A sensor that does not reply within the timeout shall be reported as a timeout, not as a round trip of the timeout's length. | STK-14 | Test |
| BLE-FR-045 | A payload longer than the firmware accepts shall be refused by the host before transmission, naming the limit. | STK-14 | Test |
| BLE-FR-046 | A connection attempt shall listen for the sensor continuously for a window the host sets, 1 to 60 s, 15 s by default: a sensor that advertises every 9 s was missed by a fixed 5 s window at half duty. A dongle whose firmware cannot take the window shall be sent none, and the host shall log that it keeps its own. | STK-14, STK-15 | Test |
| BLE-FR-047 | The host shall set, per command, how long the dongle waits for the sensor's reply, 0.1 to 60 s: some commands take longer than others. A wait outside that range shall be refused before transmission; a dongle whose firmware cannot take it keeps its fixed 2 s, and the host shall log that the wait asked for was not honoured. | STK-14 | Test |
| BLE-FR-048 | The host shall send a command after which the sensor is expected to drop the link - a reset - and report whether it did within a timeout and, if so, the time from the write to the disconnection on the dongle's clock and the reason the link ended. A sensor that stays connected is a result, not an exception. | STK-14 | Test |
| BLE-FR-049 | A connection attempt that fails shall leave no link half-open: the host shall disconnect before reporting, so the next attempt is not refused. The report shall say whether the sensor never linked or linked but its UART service was not found, and a failure the dongle has already reported shall end the wait for it. A link that fails to establish - the dongle ends it with HCI reason 0x3E - shall be tried again, up to three attempts in all, the same bound as a `connect` step (BLE-FR-111), and each failed attempt tried again shall be logged with its number and reason, so a flaky link stays visible; no other failure shall be tried again. A `connect` step shall make no more attempts than its own bound, and each of its failed attempts shall be in the run's event log (BLE-FR-115). | STK-14 | Test |

### 11.4 Time until response

| ID | Requirement | Source | Verification |
|---|---|---|---|
| BLE-FR-050 | The round trip from request to reply shall be measured on the dongle's microsecond clock, timestamped when the request is handed to the stack and when the notification arrives. | STK-14 | Test |
| BLE-FR-051 | The host's own round trip shall be measured and reported separately, as a cross-check on the link rather than as the sensor's latency. | STK-14 | Test |
| BLE-FR-052 | A command shall be repeatable, with minimum, maximum, mean, spread and standard deviation reported over the repetitions. | STK-14 | Test |
| BLE-FR-053 | Every latency result shall report the clock that produced it, that clock's resolution, and the connection interval; and shall be flagged as not trustworthy when the measured latency cannot be told apart from the connection interval. | STK-14 | Test |
| BLE-FR-054 | A latency result derived from no samples shall raise rather than report zero. | STK-14 | Test |

### 11.5 Advertising profile

| ID | Requirement | Source | Verification |
|---|---|---|---|
| BLE-FR-030 | The dongle shall report every advertising event from a chosen address, timestamped, with signal strength, channel and payload. | STK-15 | Test |
| BLE-FR-031 | The host shall derive the advertising interval: mean, minimum, maximum, spread and standard deviation. | STK-15 | Test |
| BLE-FR-032 | Advertising reports of one event on several channels shall be coalesced into a single advertising event, so that the interval measured is between beacons and not between channels. | STK-15 | Test |
| BLE-FR-033 | The analysis shall account for the advertising delay the Bluetooth specification requires (0 to 10 ms per interval), stating the jitter a conforming sensor shows, so that correct behaviour is not reported as instability. | STK-15 | Test |
| BLE-FR-034 | Advertising events the sensor did not send shall be counted, against a nominal interval supplied by the caller or inferred from the capture, and the two cases shall be distinguishable. | STK-15 | Test |
| BLE-FR-035 | The proportion of the capture in which the sensor kept to its rate (duty cycle) and the proportion of expected events received shall be reported. | STK-15 | Test |
| BLE-FR-036 | A capture too short for statistics shall report the counts it has and raise only when a statistic is actually asked for. | STK-15 | Test |

### 11.6 Firmware, tooling and bench use

| ID | Requirement | Source | Verification |
|---|---|---|---|
| BLE-FR-060 | The session shall be loggable to a text file: every line in both directions, host-timestamped, flushed per line so a session that then hangs still has a complete log. | STK-17 | Test |
| BLE-FR-061 | The log shall include lines the driver ignored, since a log that omits what the tooling discarded cannot explain why it discarded it. | STK-17 | Test |
| BLE-FR-062 | Comments shall be writable into the log, so a measurement can be annotated with what it was verifying. | STK-17 | Test |
| BLE-FR-070 | A command-line interface shall expose identification, scanning, selection, advertising profile, command/response timing and event monitoring, emitting JSON. | STK-14, STK-15 | Test |
| BLE-FR-071 | On the command line, `select` and every sub-command's `--select` shall accept an address, an exact name, or part of a name in any case, choosing as BLE-FR-026 does; `cmd --addr` shall connect to the address given; and `--addr` with `--select` shall be refused as a usage error rather than one silently winning. An operator types part of a name, because the advertised name carries the firmware version and changes on every reflash (#124). | STK-14, STK-15 | Test |
| BLE-FR-080 | The dongle shall be registered as a bench driver, and a simulated dongle shall answer the same protocol with a deterministic sensor population, so every operation is verifiable without a dongle, a sensor or a radio. | STK-08, STK-15 | Test |
| BLE-FR-100 | The driver shall read a command and response test from a markdown document: a heading per test, and a table of step number, command and expected response. The document that specifies the command set is then the test of it, rather than a second copy of it that can disagree. | STK-12, STK-15 | Test |
| BLE-FR-101 | A step with an expected response shall pass when the reply equals it after trimming, and fail otherwise. An expected response written `/…/` shall be matched as a regular expression, for a reply carrying a value that varies. | STK-12, STK-15 | Test |
| BLE-FR-102 | A step whose reply does not arrive within its timeout shall be an **error** where the document expected a reply - the system failed to deliver one - and **skipped** where it expected none, so a command that does not answer can still be sent. | STK-12, STK-15 | Test |
| BLE-FR-103 | A step written `delay <milliseconds>` shall wait and be recorded as **skipped**: waiting is not a claim about the sensor. | STK-12, STK-15 | Test |
| BLE-FR-104 | A command with no expected response shall be sent, anything arriving within a bounded listening window recorded, and the step recorded as **skipped** - the document made no claim to check, and what the board said is worth seeing anyway. | STK-12, STK-15 | Test |
| BLE-FR-105 | Each step's result shall record the test, the step number, the command, the expected response, the actual response, the time from the end of the command to the start of the response - or to the disconnection, for a step expecting one - at 10 ms resolution together with the clock that measured it, the outcome, and a note: why the outcome is what it is, and the document's own note for the step. The measured figure shall be retained beside the quoted one. | STK-12, STK-15, STK-17 | Test |
| BLE-FR-106 | A run shall be **error** when any step errored, else **fail** when any step failed, else **pass**, and shall report how many steps passed, failed, errored and were skipped - so that a document which checked nothing cannot read as a document that checked everything. | STK-12, STK-15 | Test |
| BLE-FR-107 | A document that cannot be read shall be refused naming the document and the line: a row that cannot be parsed, a step number used twice within a test, a missing column, a delay that is not a positive duration, a delay, connect or disconnect carrying an expected response, a table of steps before any heading, a variable used but not declared, declared twice, badly named, declared after the first step or left without a value, a value given for a variable the document does not declare, a timeout out of range or on a step that does not wait, and a connect naming no sensor. A table that names none of the step columns is prose and is left alone. A row skipped quietly would be a command nobody tested and nobody missed. | STK-12 | Test |
| BLE-FR-108 | The run shall be reportable as a markdown file, and every command shall be sent through the ordinary command path so that the session log carries the whole exchange with both clocks, marked with the test each command belonged to. | STK-12, STK-17 | Test |
| BLE-FR-109 | Each step shall have exactly one result, the first of these that applies: **error** when the system returned a failure code - the dongle refused the command, a connect or disconnect failed, the link or transport failed, or no reply came where one was expected; **skip** when the expected response is empty; **fail** when the actual response differs from the expected one; **pass** when it matches. | STK-12, STK-15 | Test |
| BLE-FR-110 | A document shall be able to declare variables, with or without defaults, and use them as `${NAME}` in any command, expected response, timeout or delay - Robot Framework's syntax - with values supplied when it is run overriding the defaults, so one document tests whichever sensor it is given. | STK-12 | Test |
| BLE-FR-111 | A document shall be able to open its own link with a `connect <sensor>` step - selecting by address, or by a fragment of the advertised name ignoring case - and to close it with `disconnect`. A link the document opened shall be closed when the run ends, pass or fail; a document that connects before its first command shall need no link opened for it. | STK-12, STK-14 | Test |
| BLE-FR-112 | A step shall be able to carry its own timeout, in milliseconds - for the reply, the listening window, the disconnection, or the connection - with an empty cell meaning the document's timeout for the command's prefix (BLE-FR-119), else the run's configurable default. | STK-12, STK-14 | Test |
| BLE-FR-113 | An expected response of `<disconnect>` shall mean the sensor drops the link after the command: **pass** if it does within the step's timeout, **fail** if it does not, the time being measured per BLE-FR-048. | STK-12, STK-14 | Test |
| BLE-FR-114 | A document shall be able to carry a note per step, which the report shows beside the step's result. | STK-12 | Test |
| BLE-FR-115 | A run shall be able to write an event log: one line per event, with the time it happened, the event - TX, RX, DELAY, CONNECT, DISCONNECT or ERROR - the step, the data and the result; each RX line shall carry the dongle's own measurement of the exchange at full resolution. | STK-12, STK-17 | Test |
| BLE-FR-116 | A document shall be runnable on its own from the command line, with variable values, a report and an event log, emitting the run as JSON and exiting 0 only when it passed. | STK-12, STK-15 | Test |
| BLE-FR-117 | The driver shall send one command a given number of times at a given interval, take a number from each reply by a pattern and scale it, and refuse, naming the reply, one that carries no number. | STK-12 | Test |
| BLE-FR-118 | A command's result shall give the value its reply reports - the text after the reply's first ` = `, trimmed, or nothing when there is none - so that it can be compared with the same value from another source, where the rest of the reply is not carried. | STK-12 | Test |
| BLE-FR-119 | A document shall be able to declare a timeout, in milliseconds, for every command that starts with a given prefix, in a table before its first step. A prefix shall match the start of a command sent to the sensor ignoring case, the longest matching prefix winning; it shall be the reply timeout of a command with an expected response, the listening window of one with none, and the timeout of a `<disconnect>`. A step's own timeout shall win over it, and it over the run's default. A value may be a variable; a run shall be able to override or add to the table per prefix; a prefix given twice, an empty prefix or a value out of range shall be refused naming the line. Each step's result shall state the timeout that applied and why. | STK-12, STK-14 | Test |
| BLE-FR-090 | The firmware shall build as a SEGGER Embedded Studio project against nRF5 SDK 17 for the PCA10059 dongle, and shall be packageable as a DFU image for the dongle's factory bootloader. | STK-16 | Inspection |

### 11.7 BLE non-functional

| ID | Requirement | Verification |
|---|---|---|
| BLE-NFR-001 | The firmware shall allocate no memory dynamically, shall not recurse, and shall bound every buffer at compile time. | Test, Inspection |
| BLE-NFR-006 | The firmware shall be verifiable without a dongle: its units shall be testable on a host, and its build shall be reproducible headlessly. | Test |
| BLE-NFR-002 | The firmware shall not block a radio event handler on USB, so that reporting cannot distort the timing being reported. | Inspection |
| BLE-NFR-003 | The command set, events, error codes and size limits shall be defined once and checked automatically for agreement between firmware and host driver. | Test |
| BLE-NFR-004 | The host driver shall add no mandatory third-party dependency; the serial library shall be an optional extra. | Test, Inspection |
| BLE-NFR-005 | A measurement shall never be reported without the clock that produced it and that clock's resolution. | Test |

---

## 12. PSU — GW Instek GPD-3303D bench supply

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
it **rejects** a setting it cannot deliver without replying, keeping the
previous one and reporting it only through `ERR?`, it leaves
**constant-current** operation visible only in a status word, it has **one
output switch for two channels**, and in **series or parallel tracking** it
accepts and discards anything sent to channel 2.

### 12.1 Setting and reading

| ID | Requirement | Source | Verification |
|---|---|---|---|
| PSU-FR-001 | The driver shall set and read back each channel's output voltage and current limit, in volts and amps. | STK-13 | Test |
| PSU-FR-002 | A setting outside what the supply can deliver shall be refused before it is sent. The supply rejects it without replying and keeps its previous setting, reporting the rejection only through `ERR?`, so a test that asked for 35 V would otherwise run at a setting it never asked for. | STK-13 | Test |
| PSU-FR-003 | A setpoint shall be rounded to the supply's programming resolution before it is sent, so that the value the driver returns is the value the supply applies. A value read back agrees with it to the supply's read-back resolution (0.1 V, 0.01 A on firmware V1.09), not exactly. | STK-13 | Test |
| PSU-FR-004 | A channel number the supply does not have shall be refused, naming the channels it does have. | STK-13 | Test |
| PSU-FR-005 | Setting a channel's voltage and current limit together shall set the limit first, so that a channel is never briefly protected by a previous setting. | STK-13 | Test |
| PSU-FR-006 | A setpoint or per-channel output change addressed to a channel the supply is slaving to another shall be refused, naming the tracking mode and what to do instead. In series and parallel tracking the supply accepts such a command and discards it, reporting nothing; the driver shall not be the component that turns that silence into a setpoint a test believes in. A tracking mode the status word does not decode shall be warned about and allowed, so that one unconfirmed status bit cannot disable setting altogether. The supply's own output switch and the safe state shall remain operable in every mode. | STK-13, STK-17 | Test |
| PSU-FR-010 | The driver shall measure each channel's output voltage and output current. A reply carrying its unit shall be read as a number. | STK-13 | Test |
| PSU-FR-011 | Output power shall be available, and shall be identified as derived from the two readings rather than measured. | STK-13 | Test |
| PSU-FR-012 | A single call shall return a channel's measurements, its setpoints and its regulation mode together, so that the mode qualifying a reading comes from the same moment as the reading. | STK-13 | Test |

### 12.2 Regulation and status

| ID | Requirement | Source | Verification |
|---|---|---|---|
| PSU-FR-020 | The driver shall report whether each channel is in constant voltage or constant current. A channel in constant current is not delivering the voltage that was set, and no voltage reading alone says so. | STK-13, STK-17 | Test |
| PSU-FR-021 | The driver shall decode the supply's status word - per-channel mode, tracking, beeper and output state - in the form the supply sends it (ETB-IF-001 §7), and shall retain the raw reply beside the decoded values. The supply does not report its line rate. | STK-13 | Test |
| PSU-FR-022 | A status reply that does not carry eight bits shall be reported as such, naming the line rate as the likely cause, rather than decoded. | STK-13 | Test |
| PSU-FR-023 | The driver shall report whether a channel is *regulated*: energised, in constant voltage, and at its setpoint. | STK-13, STK-17 | Test |
| PSU-FR-024 | The driver shall be able to read and clear whatever the supply reports about a rejected command, carrying its text verbatim. | STK-13 | Test |

### 12.3 Output switching

| ID | Requirement | Source | Verification |
|---|---|---|---|
| PSU-FR-030 | The driver shall switch each channel on and off individually. The supply has one output switch for both channels, so a single channel is switched off by programming it to zero volts; the interface shall state that this is not an isolator and not a safety interlock. | STK-13 | Test, Inspection |
| PSU-FR-031 | A channel switched off shall retain the setpoint it was switched off at, and shall return to it when switched on. | STK-13 | Test |
| PSU-FR-032 | Setting a voltage on a channel that is switched off shall not energise it; the new value shall apply when it is next switched on. | STK-13 | Test |
| PSU-FR-033 | A channel's current limit shall remain in force whether or not the channel is switched on. | STK-13 | Test |
| PSU-FR-034 | When every channel has been switched off, the supply's own output switch shall be opened, so that "all off" is not two rails at zero volts. | STK-13 | Test |
| PSU-FR-035 | The supply's output switch shall be operable directly, on and off, without reference to individual channels. | STK-13 | Test |

### 12.4 Link and bench use

| ID | Requirement | Source | Verification |
|---|---|---|---|
| PSU-FR-040 | Connecting shall identify the supply and read its state, and shall change nothing: a supply powering a board must not be disturbed by a driver attaching to it. | STK-13, STK-17 | Test |
| PSU-FR-041 | Commands shall be paced on a real link. The supply has a small input buffer and no flow control, and a command it drops is silent. | STK-13 | Test |
| PSU-FR-042 | A bare port name shall be taken as a serial port rather than a network host. | STK-13 | Test |
| PSU-FR-043 | The driver shall provide a safe state - outputs off and rails at zero - without altering current limits, which are the protection set for whatever is connected. | STK-13, STK-17 | Test |
| PSU-FR-044 | Each measured output voltage and current shall be logged as a `reading` record (CORE-FR-065) with its channel. | STK-13, STK-23 | Test |
| PSU-FR-050 | The supply shall be registered as a bench driver, and a simulated supply shall answer the same command set with a load model, so that constant-current operation is verifiable without hardware. | STK-08, STK-13 | Test |
| PSU-FR-060 | A command-line interface shall expose identification, status, measurement, setting and output switching, emitting JSON, and shall warn when a channel it read is in current limit or is being slaved to another by the supply's tracking mode. | STK-13 | Test |

### 12.5 PSU non-functional

| ID | Requirement | Verification |
|---|---|---|
| PSU-NFR-001 | The driver shall add no mandatory third-party dependency; the serial library shall be an optional extra. | Test, Inspection |
| PSU-NFR-002 | No operation shall energise an output that the caller did not ask to be energised. | Test, Inspection |
| PSU-NFR-003 | Every value the supply reports shall be presented in SI units, with the regulation mode that qualifies it. | Test |

---

## 13. S2LP — ST S2-LP development kit

A sub-1 GHz transceiver on an evaluation board, reached over USB. The board runs
**ST's own CLI firmware** - the firmware ST's S2-LP DK GUI drives - and this
element is the host half only: no firmware of this project's runs on the kit
(STK-20, AD-20).

Three properties of that firmware shape the requirements below, and each is a
way a capture can be believed when it should not be. Reception is **polled**:
the firmware arms the radio when asked and hears nothing between one call and
the next. Timestamps are the **board's millisecond timer**, not a radio
timestamp. And the radio will accept a frequency the board cannot radiate.

### 13.1 The link to the firmware

| ID | Requirement | Source | Verification |
|---|---|---|---|
| S2LP-FR-001 | The driver shall communicate with ST's CLI firmware over the kit's USB serial port, as ST's GUI does, without replacing or modifying that firmware. | STK-19, STK-20 | Test, Inspection |
| S2LP-FR-002 | A command shall be checked against the firmware's declared argument types before it is sent, and a command or value the firmware would reject shall be reported naming the command and the argument. | STK-19 | Test |
| S2LP-FR-003 | A reply shall be read until the firmware's braces balance, rather than as a fixed number of lines, because the firmware answers some commands on one line and others over several. | STK-19 | Test |
| S2LP-FR-004 | A value the firmware writes in hexadecimal without a prefix shall be read as hexadecimal. A line the driver did not understand shall be kept, not discarded. | STK-19 | Test |
| S2LP-FR-005 | A long-running command shall be stoppable by the means the firmware provides, without resetting the board. | STK-19 | Test |

### 13.2 Registers

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

### 13.3 Radio configuration

| ID | Requirement | Source | Verification |
|---|---|---|---|
| S2LP-FR-030 | The driver shall set and read the carrier frequency, modulation, data rate, frequency deviation, channel filter bandwidth and output power. | STK-19 | Test |
| S2LP-FR-031 | A configuration operation shall report what the radio says it is set to afterwards, not what it was asked for. | STK-19 | Test |
| S2LP-FR-032 | A frequency outside the band the attached board is built for shall be refused, because the radio would accept it and transmit into a filter and matching network that do not pass it. | STK-19 | Test |
| S2LP-FR-033 | The firmware, the radio and its crystal shall be identified at connection. The board, which the firmware does not report, shall be taken from the caller and never assumed; without it only the synthesiser's range is checked. Connecting shall change no radio setting. | STK-19 | Test |
| S2LP-FR-035 | The board's band shall be read from the RF board's identification EEPROM at connection, read-only. It shall bound frequency settings when the caller names no board, and a named board whose band disagrees with the EEPROM shall be refused. A blank or unreadable EEPROM shall leave the band unknown. | STK-19 | Test |
| S2LP-FR-034 | Signal strength shall be reported in dBm, converted by the device's documented scale. | STK-19 | Test |

### 13.4 Transmitting, receiving and logging

| ID | Requirement | Source | Verification |
|---|---|---|---|
| S2LP-FR-040 | The driver shall transmit a payload given as bytes or as text, and shall transmit one repeatedly at an interval timed by the board rather than by the host. | STK-19 | Test |
| S2LP-FR-041 | The driver shall receive a packet, reporting its payload, its signal strength and the board's timestamp. Receiving nothing shall be reported as nothing received, and shall be distinguishable from receiving an empty packet. | STK-19 | Test |
| S2LP-FR-042 | The driver shall capture a number of packets, letting the firmware's own loop re-arm the radio where it can, so that no host round trip falls in a gap. | STK-19 | Test |
| S2LP-FR-043 | A capture shall record how many times the radio was re-armed during it, so that a capture with gaps cannot be quoted as a complete record of the air. | STK-19 | Test |
| S2LP-FR-044 | A capture that is cut short, by time or by the host, shall say so in its result rather than raise. | STK-19 | Test |
| S2LP-FR-045 | Every line exchanged with the board shall be loggable to a text file, host-timestamped and flushed per line, including lines the driver did not understand. | STK-19 | Test |
| S2LP-FR-047 | The driver shall stream received frames until a count, a time or the caller ends it, and shall stop the board when the stream ends however it ends. By default it shall receive through the firmware's own receive loop, so that no host round trip falls between frames; on request it shall instead receive one frame at a time and read a caller-chosen set of radio registers straight after each (by default AFC correction, PQI, SQI with carrier sense, and RSSI). | STK-19 | Test |
| S2LP-FR-048 | Before the first send or receive, the driver shall route the radio's interrupt to the board and confirm the board reads it; a send shall be refused while the radio's TX source is not its FIFO. | STK-19 | Test |
| S2LP-FR-049 | Whenever PQI is read, the driver shall have the radio's PQI check enabled, and shall restore the setting afterwards. It shall measure a transmitter's preamble length from the best frame's PQI and check it against a configured length in bit-pairs (expected PQI 2 x pairs - 1), allowing a stated shortfall. A check at or beyond PQI's ceiling of 255, or with no frame heard, shall be reported as unmeasurable, never as a pass. | STK-19 | Test |
| S2LP-FR-046 | Every packet, sent and received, shall be loggable as one structured record per line, readable after an interrupted capture. Both logs shall be available at once, and a note shall be writable into both. | STK-19 | Test |

### 13.5 Bench use

| ID | Requirement | Source | Verification |
|---|---|---|---|
| S2LP-FR-050 | The kit shall be registered as a bench driver, and a simulated kit shall answer the same firmware command set with a register file and a modelled air interface, so that every operation is verifiable without hardware. | STK-08, STK-19 | Test |
| S2LP-FR-070 | Received frames shall be decodable as the Kepler sensor's frames, by the layouts in its firmware. A payload that cannot be decoded shall keep its raw bytes and state why. | STK-19 | Test |
| S2LP-FR-071 | A frame's raw payload, the registers read after it and its decode shall be logged together, as one record. | STK-19 | Test |
| S2LP-FR-072 | The driver shall take a decoded field from the next N Kepler transmissions from a given sensor and of a given frame type, counting each transmission once however many copies of it are received. | STK-19 | Test |
| S2LP-FR-073 | The driver shall return the whole decode of the next Kepler frame of a given type from a given sensor, with its raw payload, and shall raise, naming the type and sensor, when none arrives in time. | STK-19 | Test |
| S2LP-FR-080 | Every packet the driver sends or receives shall be written to the event log as a structured `rf_packet` record (CORE-FR-064) carrying the packet's direction, payload in hex, length, RSSI, board time, error, extra fields, registers and decode, so a reader of the log has every frame without the driver's packet log. | STK-19, STK-23 | Test |
| S2LP-FR-081 | A decoded CONFIG frame shall name each of its five values - parameter number, name, unit, and the value as its enumeration names it - by the sensor firmware's parameter order and the frame's permutation method: none, distance, or the polynomial with the frame's repeat number as its version. | STK-19, STK-23 | Test |
| S2LP-FR-082 | The waveform sample a TWF slot carries shall be computable under each permutation method, and a TWF frame's frequency code shall be decoded to its output data rate (a code with bit 15 set is a tenth of the rate). | STK-19, STK-23 | Test |
| S2LP-FR-083 | Frames shall be decoded as the sensor firmware builds them: a RESPONSE frame's parameter as 16 bits at 12-13, followed by a 32-bit timer (ms for LORES, us for HIRES) and a slot, or up to ten {id, value} pairs, from a minimum of 14 bytes; a VERSION frame's reset reason as the names of its bits and its PCB code by name; an ALIVE frame's phase by name; the product by name. | STK-19, STK-23 | Test |
| S2LP-FR-084 | `read_setup` shall read the kit's RF setup - the radio's settings, every register, the output power and the board's EEPROM - return it, and log it as one `rf_setup` record, so a reader of the event log has it without the kit's port. | STK-19, STK-23 | Test |
| S2LP-FR-060 | A command-line interface shall expose identification, register dump and access, radio configuration, transmit, receive, capture and strobes, emitting JSON, and shall warn when a capture was not continuous. | STK-19 | Test |

### 13.6 S2LP non-functional

| ID | Requirement | Verification |
|---|---|---|
| S2LP-NFR-001 | The driver shall add no mandatory third-party dependency; the serial library shall be an optional extra. | Test, Inspection |
| S2LP-NFR-002 | No vendor source shall be redistributed in this repository. The register map shall hold facts about the device, not vendor prose. | Inspection |
| S2LP-NFR-003 | A measurement shall never be reported without the clock that produced it and that clock's resolution. | Test, Inspection |
| S2LP-NFR-004 | No operation shall transmit unless the caller asked for a transmission. | Test, Inspection |

---

## 14. DMM — TTi 1604 bench multimeter

A 4-3/4 digit (40 000 count) true-RMS bench meter on an opto-isolated RS-232
link. It has **no command language**: the link carries single ASCII characters
standing for front-panel key presses, and in remote mode the meter streams a
ten-byte binary frame after every measurement. There is no query, no `*IDN?`
and no error queue.

Four properties shape the requirements below, and each is a way a reading can
be believed when it should not be. The **host powers the interface** through
the handshake lines. The **stream has no gaps**, so a reader can land
mid-frame and decode a plausible wrong number. The **digits are a
seven-segment bitmap**, so the display can carry letters where a number is
expected. And the **display can be frozen** by Hold, Touch-Hold or a Min-Max
review, in which case the reading is real but is not now.

### 14.1 The link

| ID | Requirement | Source | Verification |
|---|---|---|---|
| DMM-FR-001 | The driver shall open the port at 9600 baud, 8 data bits, no parity, one stop bit, which is the meter's only configuration. | STK-18 | Test |
| DMM-FR-002 | The driver shall assert DTR and shall not assert RTS. The opto-isolated interface draws its power from these lines; left at a serial library's defaults the meter is mute, and the obvious diagnoses — wrong rate, bad cable, dead meter — are all wrong. | STK-18 | Test |
| DMM-FR-003 | The driver shall not use DTR/DSR flow control, because those lines are carrying interface power rather than flow state. | STK-18 | Test |
| DMM-FR-004 | A bare port name shall be taken as a serial port rather than as a host name. | STK-18 | Test |
| DMM-FR-005 | The driver shall report an identity of its own, stating that the meter answers no identification query, and shall not present a serial number or firmware revision the instrument does not supply. | STK-18, STK-17 | Test |

### 14.2 Remote and local

| ID | Requirement | Source | Verification |
|---|---|---|---|
| DMM-FR-006 | The driver shall put the meter into remote mode on connecting, unless asked not to. Before that the meter streams nothing whatsoever. | STK-18 | Test |
| DMM-FR-007 | The driver shall be able to return the meter to local control. | STK-18 | Test |
| DMM-FR-008 | Connecting shall not press the Operate key. That key toggles the measurement circuits, so pressing it to ensure the meter is on switches off a meter that already was — and because the interface stays powered either way, the mistake does not present as one. | STK-18, STK-17 | Test |
| DMM-FR-009 | Where no measurement arrives, the driver shall name both states in which a healthy meter is silent — not in remote mode, and switched off at Operate — and shall say which of them it has ruled out. | STK-18 | Test |

### 14.3 Frames and decoding

| ID | Requirement | Source | Verification |
|---|---|---|---|
| DMM-FR-010 | The driver shall locate each ten-byte frame by its leading carriage return rather than by taking the next ten bytes. A frame read from the wrong offset decodes the display digits against the wrong columns and yields a plausible wrong number rather than an error. | STK-18 | Test |
| DMM-FR-011 | A frame of the wrong length, or one not beginning at a frame start, shall be refused rather than decoded. | STK-18 | Test |
| DMM-FR-012 | The driver shall decode the five display digits from their seven-segment patterns, with bit 0 as the decimal point. | STK-18 | Test |
| DMM-FR-013 | A segment pattern the driver does not recognise shall be marked in the decoded text rather than dropped. Dropping it turns 1.234 into 1234. | STK-18 | Test |
| DMM-FR-014 | The driver shall decode the measurement type, AC or DC, and the range from the range byte. | STK-18 | Test |
| DMM-FR-015 | The driver shall report every value in SI units — volts, amps, ohms or hertz — whatever the display shows. | STK-18 | Test |
| DMM-FR-016 | Resistance shall be scaled by a multiplier derived from the range's resolution in the instruction manual and the position of the displayed decimal point, since the frame does not carry the k or M annunciator. A display that fits no multiplier of 1, 1 000 or 1 000 000 shall carry no value and shall say why. (Revised by #115: the multiplier was assumed to be 1 000 on every range above 400 ohm.) | STK-18 | Test |
| DMM-FR-017 | With Hz selected the reading shall be reported as a frequency, whichever input the measurement type names. | STK-18 | Test |
| DMM-FR-018 | An overrange display shall be reported as an overrange and shall not carry a numeric value. | STK-18 | Test |
| DMM-FR-019 | The displayed text shall be reported alongside the value, as the evidence for it. | STK-18, STK-17 | Test |
| DMM-FR-020 | A reading taken while the display is frozen — Hold, Touch-Hold, or a Min-Max review — shall be marked as held. The value is a real measurement but is not the present one, and a test that records it as live is measuring the past. | STK-18, STK-17 | Test |
| DMM-FR-021 | The function and status annunciators shall be decoded and reported, at the bit positions the manufacturer's remote-control note gives: Touch-Hold is bit 1 of the function byte and auto-range-set bit 1 of the status byte. (Revised by #115, which corrected both from bits 0 and 2.) | STK-18 | Test |
| DMM-FR-027 | The driver shall read whatever bytes the meter has sent, as they arrive, and shall not wait for an end-of-message the link never signals. Until #115 it did, and on a real serial port every read timed out with the received bytes left unread, so connecting always failed. | STK-18 | Test |
| DMM-FR-028 | A frame shall be accepted only if every display byte is a pattern the meter draws, its units field names a measurement and it carries at most one decimal point. A carriage return that does not begin such a frame shall be passed over and the search resumed, so that a stream joined part-way through a frame resynchronises instead of decoding garbage. | STK-18 | Test |
| DMM-FR-022 | The raw frame shall be retained with the decoded reading. | STK-18 | Test |

### 14.4 Key presses

| ID | Requirement | Source | Verification |
|---|---|---|---|
| DMM-FR-023 | The driver shall send front-panel key presses by name, and shall refuse a name the meter has no key for, listing the keys it has. | STK-18 | Test |
| DMM-FR-024 | The driver shall confirm each key press against the meter's echo and shall resend a command that was not echoed. At 9600 baud with no flow control on the data path a lost keystroke is silent, and the meter is then measuring something other than what the test asked for. | STK-18 | Test |
| DMM-FR-025 | A command that is never echoed shall be reported with the handshake lines named as the likely cause. | STK-18 | Test |
| DMM-FR-029 | Selecting a function or a coupling shall be confirmed from the readings, which carry the meter's state, and not from the echo: some keys toggle, a resend after a lost echo undoes the first press, and a refused key is echoed all the same. A change the readings do not show within the confirmation time shall be reported, naming what the readings show. AC or DC shall be refused on resistance before any key is sent. | STK-18 | Test |
| DMM-FR-030 | The driver shall lock a range named by its full scale in SI units, stepping one range at a time and confirming each step from the readings, and shall turn auto-ranging on without toggling it. A full scale the function does not have shall be refused, naming the ones it has. | STK-18 | Test |
| DMM-FR-031 | A measurement taken on request shall have been measured wholly after the request: everything already received, the operating system's buffer included, shall be discarded, and then the next complete frame. | STK-18, STK-17 | Test |
| DMM-FR-032 | Every wait for a reading shall allow for the meter's reading rate in the state it is in: 0.4 s per reading on most functions, one gate time - 1 s, or 10 s on the 4 kHz range - when measuring frequency. | STK-18 | Test |
| DMM-FR-033 | Frequency shall be selectable only from an AC voltage or current function, which is the only state in which the meter accepts the Hz key, and its range shall be selectable by full scale. | STK-18 | Test |
| DMM-FR-034 | Each measurement read shall be logged as a `reading` record (CORE-FR-065): its measurement, value and unit, AC or DC, the display's text and whether it was over range. | STK-18, STK-23 | Test |
| DMM-FR-026 | The echo shall be identified as the bytes left over once complete frames have been removed from the stream, not by searching the stream for the echoed character. Seven-segment digit patterns collide with the key characters exactly: `0x61` is both the Up key and the pattern for a `1` with its decimal point, so a scan for the character finds one inside an ordinary reading. | STK-18 | Test |

### 14.5 Simulation

| ID | Requirement | Source | Verification |
|---|---|---|---|
| DMM-FR-045 | The bench configuration shall be able to state what the simulated meter reads, so that a specification carrying real limits can be exercised with no hardware. The limits shall remain the specification's and the value the bench's. | STK-18, STK-16 | Test |
| DMM-FR-046 | The simulated meter shall draw its display at each range's resolution, auto-range after a change of function, show OFL beyond a range, refuse Hz on DC and AC/DC on resistance, and send readings at the meter's rate - one per gate measuring frequency - on a virtual clock, so that a driver wait shorter than the meter's is a failure in the tests and not first on the bench. | STK-18 | Test |

### 14.6 Command line and bench use

| ID | Requirement | Source | Verification |
|---|---|---|---|
| DMM-FR-070 | A command-line interface shall identify the meter, report readings with their display text and annunciators as JSON, press keys by name and list them. | STK-18 | Test |
| DMM-FR-080 | An opt-in bench test shall exercise the driver against a real meter named by the operator - link, stream, reading rate, functions, ranges, frequency gate, local and remote, and, where the operator names a wired reference, measurement against it - selecting a current function only when a current reference is named. It shall write a record of what the meter did for the bench confirmation items and shall be excluded from the default test run. | STK-18 | Test |
| DMM-FR-081 | An interactive front-panel check shall change the meter through the driver step by step and ask the operator to confirm each change on the front panel - annunciators, range and displayed value - recording the driver's read-back, each answer, and what the panel showed instead, in a log; and shall leave the meter on DC volts, auto-ranging, in local mode however the run ends. | STK-18 | Test |

### 14.7 DMM non-functional

| ID | Requirement | Verification |
|---|---|---|
| DMM-NFR-001 | The driver shall add no mandatory third-party dependency; the serial library shall be an optional extra. | Test, Inspection |
| DMM-NFR-002 | No operation shall press the Operate key on the caller's behalf. | Test, Inspection |
| DMM-NFR-003 | The protocol facts the driver encodes shall be traceable to a cited source, and anything not confirmed against a physical meter shall be recorded as unconfirmed. | Inspection |
| DMM-NFR-004 | No third-party source shall be redistributed in this repository. Where another implementation was consulted, the protocol facts it demonstrates shall be recorded in this project's own form and its licence and authorship cited. | Inspection |

---

## 15. PICO — Pico 2 + SHT30-D bench thermometer and its firmware

A Raspberry Pi Pico 2 (RP2350) reads a Sensirion SHT30-DIS, carried on a
DollaTek SHT30-D breakout module, over I2C, and reports the temperature to the
host over USB CDC. It is the local-temperature measurement of STK-21; STK-22
asks that the firmware say what it is, which it does through the `rd` command
set (#131).

The requirements are shaped by one property of the measurement: **a failed
reading must never look like a reading**. The sensor can be absent, a frame can
be corrupted on the bus, and the bus can hang; in each case the firmware says
so and reports no value, and the host driver raises rather than returning the
last good one. Reference documents and wiring: `docs/pico_sht30/`.

No requirement here is renumbered when it changes. One that no longer applies
stays in its table, marked **Withdrawn** with the issue that withdrew it, so
that its identifier is never reused for something else.

### 15.1 Firmware: host link and identity

| ID | Requirement | Source | Verification |
|---|---|---|---|
| PICO-FR-001 | The firmware shall accept one command per LF-terminated line over USB CDC ACM, ignoring CR, and shall send exactly one reply per command: for `rd`, a line beginning `ACK` or `NAK` (PICO-FR-006, -007, -027); for every other command, a line beginning `ok` or `err <code> <text>`. | STK-21 | Test |
| PICO-FR-002 | The product name, copyright notice and firmware version shall be defined once, in `firmware_version.h`. The version shall have the form `V<major>.<minor>.<patch>`, the minor number as two digits and the patch number as four (baseline `V1.00.0000`), and shall follow semantic versioning: it shall be bumped with every change to the firmware or its host driver - major for a breaking protocol change, minor for an added command or feature, patch for a fix. The build shall inject the short (7-character) SHA of the commit the image is built from; a build that does not shall report `unknown`. *(Revised by #131: this requirement was the `ver` reply, which is withdrawn.)* | STK-22 | Test, Inspection |
| PICO-FR-003 | An unknown command, or a command with the wrong number of arguments, shall be refused with an `err` reply and shall have no effect: `err 1` for an unknown command - `ver`, `temp` and `reset` included since #131 - and `err 2` for the wrong number of arguments, including `rd` with no option or more than one. | STK-21 | Test |
| PICO-FR-004 | A command line longer than the line buffer shall be discarded whole and refused; it shall never be executed in part. | STK-21 | Test |
| PICO-FR-005 | `rd name`, `rd copyright`, `rd version` and `rd sha` shall answer whether or not the sensor is present, and shall not touch the sensor, so that "no sensor" is distinguishable from "no Pico". | STK-21, STK-22 | Test |
| PICO-FR-006 | `rd name`, `rd copyright`, `rd version` and `rd sha` shall each answer `ACK rd <option> = <value>`, the value being, respectively, `Pico 2 SHT30 Temperature Sensor`, `(c) 2026 Dermot Murphy`, the firmware version and the commit SHA of PICO-FR-002. The value may contain spaces and runs to the end of the line (#131). | STK-22 | Test |
| PICO-FR-007 | `rd` with any other option shall answer `NAK rd <option> = Error`, echoing the option as received, and shall have no other effect. Options shall be matched exactly, case included (#131). | STK-21, STK-22 | Test |

### 15.2 Firmware: the sensor

| ID | Requirement | Source | Verification |
|---|---|---|---|
| PICO-FR-010 | The firmware shall reach the SHT30 on I2C0 at 100 kHz, SDA on GP4 and SCL on GP5, at address 0x44, each overridable at build time without a source edit. | STK-21 | Inspection, Test (build) |
| PICO-FR-020 | Each `rd temperature` shall take one new single-shot, high-repeatability measurement with clock stretching disabled, waiting at least the datasheet's maximum conversion time before reading the result. | STK-21 | Test |
| PICO-FR-021 | Every word received from the sensor shall be checked against its CRC-8 (polynomial 0x31, initial value 0xFF). A mismatch shall be reported - by `rd temperature` as `Error` (PICO-FR-027), by `status` as `err 5` - and no value shall be reported. | STK-21 | Test |
| PICO-FR-022 | The temperature shall be converted from its raw word with the datasheet formula in integer arithmetic, rounded to the nearest thousandth of a degree Celsius, before it is formatted for reporting (PICO-FR-027). *(Revised by #131: humidity and the raw words are no longer reported.)* | STK-21 | Test |
| PICO-FR-023 | A sensor that does not acknowledge, and a bus transfer that does not complete within its timeout, shall be reported - by `rd temperature` as `Error` (PICO-FR-027), by `status` and `sreset` as `err 4` and `err 6` respectively. In neither case shall a value be reported. | STK-21 | Test |
| PICO-FR-024 | `status` shall report the sensor's status register, CRC-checked. | STK-21 | Test |
| PICO-FR-025 | The firmware shall soft-reset the sensor at start-up, and on `sreset`. | STK-21 | Test, Inspection |
| PICO-FR-026 | A failed check shall leave no partially updated reading behind for a caller to report. | STK-21 | Test |
| PICO-FR-027 | `rd temperature` shall answer `ACK rd temperature = <value>`, the value in degrees Celsius to exactly two decimal places, rounded half away from zero from the thousandths of PICO-FR-022 (`22.848` → `22.85`, `-1.235` → `-1.24`), and never written `-0.00`. When no reading can be made - the sensor is absent, a frame fails its CRC, or the bus times out - the value shall be `Error`, never a previous reading (#131). | STK-21 | Test |

### 15.3 Firmware: maintenance and build

| ID | Requirement | Source | Verification |
|---|---|---|---|
| PICO-FR-030 | `ecureset` (named `reset` before #131) shall reboot the Pico, and `bootsel` shall reboot it into the ROM's USB bootloader ready for a UF2 image. In both cases the `ok` reply shall be sent before the reboot, and a refused command shall not reboot. | STK-21 | Test |
| PICO-FR-031 | The firmware shall build with the Raspberry Pi Pico C SDK for the Pico 2 (RP2350, Arm Cortex-M33) into a UF2 image that can be copied onto the board. | STK-21 | Test (build) |

### 15.4 Host driver and bench use

| ID | Requirement | Source | Verification |
|---|---|---|---|
| PICO-FR-040 | Connecting shall identify the thermometer with `rd name`, `rd copyright`, `rd version` and `rd sha`, and shall refuse a device whose `rd name` is not `Pico 2 SHT30 Temperature Sensor`. It shall send nothing the firmware does not define. *(Revised by #131: the firmware no longer reports a protocol revision for the driver to compare.)* | STK-21, STK-22 | Test |
| PICO-FR-041 | The driver shall expose the name, copyright, version and commit SHA as typed values, and shall report the version as the firmware gives it rather than refuse one it does not expect. | STK-22 | Test |
| PICO-FR-042 | The driver shall return the temperature as a number, together with the text the firmware sent and a host timestamp; each reading shall be a new measurement. *(Revised by #131: no humidity and no raw words.)* | STK-21 | Test |
| PICO-FR-043 | An `err` reply shall raise an error carrying the firmware's code; no reading shall be returned. | STK-21 | Test |
| PICO-FR-044 | **Withdrawn** (#131). Was: the driver shall recompute each value from its raw word with the firmware's arithmetic, and shall refuse a reply in which they disagree. `rd temperature` carries no raw word; the check that replaces it is the format check of PICO-FR-047. | STK-21 | — |
| PICO-FR-045 | A bare port name shall be taken as a serial port rather than a network host. | STK-21 | Test |
| PICO-FR-046 | The driver shall decode the sensor status register, and shall provide sensor soft reset, Pico reboot (`ecureset`) and bootloader entry. | STK-21 | Test |
| PICO-FR-047 | The driver shall send `rd <option>` and return the value of its `ACK`. A `NAK` shall raise `RdRefusedError`, an `err` reply `SensorError`, and a reply for another option, or one that is neither `ACK` nor `NAK`, `ProtocolError`. A temperature of `Error` shall raise `NoReadingError` - never a stale value - and a temperature that is not a number to exactly two decimal places shall be refused with `ProtocolError` (#131). | STK-21 | Test |
| PICO-FR-048 | Each temperature read shall be logged as a `reading` record (CORE-FR-065) in degC, with the text the firmware sent. | STK-21, STK-23 | Test |
| PICO-FR-050 | The thermometer shall be registered as a bench driver, and a simulated thermometer shall answer the same command set with the same reply text, `rd` included, with injectable faults - sensor absent, CRC failure and bus timeout - each of which makes `rd temperature` answer `Error`. | STK-08, STK-21 | Test |
| PICO-FR-060 | A command-line interface shall expose `temp` (one reading or a series, each by `rd temperature`), `status`, `sreset` and `bootsel`, emitting JSON. *(Revised by #131: `ver` is replaced by PICO-FR-061.)* | STK-21, STK-22 | Test |
| PICO-FR-061 | The command-line interface shall also expose `info` (name, copyright, version and commit SHA), `rd <option>` for exactly the five options of PICO-FR-006 and -027, refusing any other before anything is sent, and `ecureset`, emitting JSON (#131). | STK-21, STK-22 | Test |

### 15.5 Host: reflashing without BOOTSEL

Reflashing used to take three manual steps: send `bootsel`, wait for the
`RP2350` drive, and copy the UF2 onto it. Nothing checked afterwards that the
build now running was the one copied. These requirements make it one command
that ends by confirming the result (#127).

What they cannot do is reach a Pico whose firmware has crashed or never appears
on USB: that still needs the BOOTSEL button or an SWD probe. They have been
verified against a simulated board, and on a real Pico 2 on Windows on
2026-10-03 by all three routes into the bootloader (PICO-OPEN-05, closed).
The same day, with the `rd` firmware of #131, `flash` reflashed the board by
`bootsel` and confirmed its name, version `V1.00.0000` and commit SHA.
Drive discovery on Linux and macOS has not been tried on hardware.

| ID | Requirement | Source | Verification |
|---|---|---|---|
| PICO-FR-070 | The host shall bring the Pico into its USB bootloader without a button press. If an `RP2350` bootloader drive is already mounted - a blank board, or one already in its bootloader - that drive shall be used as it is. Otherwise the running thermometer shall be sent `bootsel`; if the port does not answer the protocol, the host shall open and close it at 1200 baud, the Pico SDK's USB-stdio request to reboot into the bootloader. A drive shall be recognised as the bootloader by its `INFO_UF2.TXT` naming `Board-ID: RP2350`, searched for on Windows (drive letters C: to Z:), Linux (`/media`, `/run/media`, `/mnt`) and macOS (`/Volumes`); a drive may also be named explicitly. | STK-21 | Test |
| PICO-FR-071 | Before anything is sent to the Pico, the image shall be checked: every 512-byte block shall carry the UF2 magic numbers and a payload that fits; every block shall be for the RP2350 (the Arm secure, Arm non-secure and RISC-V families, and the absolute and data families an SDK 2.x build may add); an RP2040 image shall be refused. An image that does not carry the thermometer firmware's name (`Pico 2 SHT30 Temperature Sensor`, NUL-terminated) shall be refused unless the user says it is intended. *(Revised by #131: was the title `Pico2-SHT30-Thermometer`.)* | STK-21 | Test |
| PICO-FR-072 | The image shall be written to the bootloader drive, and the copy shall be complete only when the drive has gone away, i.e. the Pico has rebooted into the new image. An error on closing the file shall be ignored if the drive has already gone, since the Pico reboots as the last block lands; while the drive remains, it shall be a failure. | STK-21 | Test |
| PICO-FR-073 | After the copy, the host shall find the thermometer's port again (the one given, or the only serial port with the Raspberry Pi USB vendor ID 0x2E8A), wait until it answers the `rd` command set, and compare `rd name` with the thermometer's name, `rd version` with the version expected if one was given and otherwise with the single version (`V<major>.<minor>.<patch>`, PICO-FR-002) stored in the image, and `rd sha` with the single 7-character commit SHA stored in the image. A mismatch shall be reported in the result, not raised, and an image with no single version or no single commit SHA shall be noted as not compared on that point. *(Revised by #131: was `ver`, the title and the ISO 8601 build date.)* Verification may be switched off, and is not attempted for an image that is not the thermometer firmware. | STK-21, STK-22 | Test |
| PICO-FR-074 | Every wait - for the bootloader drive, for the drive to go after the copy, and for the port and the thermometer to come back - shall be bounded by a timeout, and shall end in an error that names what was being waited for. It shall also be an error, naming the remedy, to find more than one bootloader drive or Raspberry Pi port, to have neither a drive nor a port to start from, or to need drive discovery on an operating system it does not support. | STK-21 | Test |
| PICO-FR-075 | `benchtools thermo -r <port> flash <uf2>` shall perform PICO-FR-070 to -074, with `--expect-version`, `--drive`, `--any-image`, `--no-verify`, `--bootloader-timeout` and `--port-timeout`. It shall print the result as JSON - the image, the drive, how the bootloader was reached, the firmware before and after, each check and any notes - and exit 0 only if every check passed; a mismatch or an error shall exit 1. | STK-21, STK-22 | Test |
| PICO-FR-076 | With `-r sim://`, `flash` shall run against a simulated Pico 2 that presents a bootloader drive on `bootsel` or a 1200-baud reset, takes a copied image, reboots, and then reports the image's version and commit SHA through `rd` (and, for an image that is not the thermometer, a different name), so that every path can be exercised with no Pico attached. | STK-08, STK-21 | Test |

### 15.6 PICO non-functional

| ID | Requirement | Verification |
|---|---|---|
| PICO-NFR-001 | The firmware's logic shall be separated from the hardware by a single HAL seam, so that it is unit tested on the host unchanged. | Inspection, Test |
| PICO-NFR-002 | The firmware shall be written to MISRA C:2012: no `<stdio.h>` formatting, no dynamic memory, no recursion, fixed-width types, and every deviation recorded where it occurs and in `docs/pico_sht30/Pico_SHT30_Notes.md`. | Inspection, Test |
| PICO-NFR-003 | The firmware's own sources shall compile with `-Wall -Wextra -Wconversion -Wshadow -Wstrict-prototypes` as errors, in both the target and the host test builds; the host tests shall run under AddressSanitizer and UndefinedBehaviorSanitizer. | Test |
| PICO-NFR-004 | The protocol shall be defined once, in `firmware/pico_sht30/include/protocol.h`, and the host driver's constants shall be checked against it by a test. | Test |
| PICO-NFR-005 | The host driver shall add no mandatory third-party dependency; the serial library shall be an optional extra. | Inspection, Test |
| PICO-NFR-006 | All of the firmware's C code - sources, headers and host unit tests - shall conform to ETB-STD-002 and ETB-STY-001 as checked by CStyleCheck, with no baseline: any finding at any severity fails the build. Module aliases and rule exclusions shall be confined to the Pico step and justified where they are declared. | Test |

---

## 16. RUN — bench test runner

### 16.1 Bench configuration

| ID | Requirement | Source | Verification |
|---|---|---|---|
| RUN-FR-001 | The bench configuration shall be separate from the test specification, so the same suite runs on a different rig by pointing at a different configuration. | STK-08 | Test |
| RUN-FR-002 | A bench shall name each instrument by alias, driver and resource, and shall be loadable from JSON or YAML. | STK-08 | Test |
| RUN-FR-003 | Instrument drivers shall be selected by registered name, so a specification cannot name arbitrary code. | STK-08 | Test |
| RUN-FR-004 | Instruments shall connect on first use, and whatever was opened shall be closed on exit, including after a failure. | STK-08 | Test |
| RUN-FR-005 | The runner shall support replacing every instrument with its simulator, so a specification can be exercised without hardware. | STK-08 | Test |
| RUN-FR-006 | A run shall be recorded as simulated whenever no instrument on the bench is real hardware, so simulated results cannot be mistaken for measurements. | STK-08 | Test |
| RUN-FR-007 | A bench option that a driver declares as an input file, given as a relative path, shall be looked for in the bench file's directory, then the working directory, then the EmbeddedTestBench checkout, and the first that exists used. One found in none shall be passed to the driver unchanged and the locations searched logged, since a simulator may not read it. The runner is normally started in the repository of the firmware under test, not in this one (#116). | STK-08 | Test |
| RUN-FR-008 | A specification shall be able to allocate an event-log name to each instrument it uses, and a bench to attach one to each actual instrument. The specification's name shall win, the bench's apply where the specification gives none, and the driver's default where neither does. An invalid name, or two instruments given one name in a specification or a bench, shall be refused at load; two instruments a run uses that would share a name, defaults included, shall be refused before any instrument connects. Each instrument's name shall appear in the run record and the report (#126). | STK-08, STK-19 | Test |

### 16.2 Test specification

| ID | Requirement | Source | Verification |
|---|---|---|---|
| RUN-FR-010 | A test specification shall be data, not code, and shall be loadable from JSON (requiring no third-party package) or YAML. | STK-08 | Test |
| RUN-FR-011 | A specification shall declare a suite name, optional setup and teardown steps, and one or more named tests, each with steps. | STK-08 | Test |
| RUN-FR-012 | Each test shall be able to name the requirement it verifies. | STK-08 | Test |
| RUN-FR-013 | A step shall name an instrument method and its arguments, and shall be able to address values inside the returned result by path. | STK-08 | Test |
| RUN-FR-014 | A malformed specification shall be rejected with a message identifying what to fix. | STK-08 | Test |
| RUN-FR-015 | A test shall be markable as skipped, with a reason. | STK-08 | Test |
| RUN-FR-016 | A step shall be able to save its result under a name, and any later step shall be able to use that saved value - or a value addressed inside it - as an argument or as a limit, optionally rendered through a format template. A reference to a name nothing has saved shall be refused, naming what has been saved. Without this a chained test would have to write down what an earlier step established, which makes the test assert its own input. | STK-08, STK-16 | Test |
| RUN-FR-017 | A step argument that the driver declares as an input file, given as a relative path, shall be looked for in the specification's directory, then the working directory, then the EmbeddedTestBench checkout, and the first that exists used. One found in none shall be an execution error naming the argument and every location searched. An output path shall be written relative to the working directory, as before. A specification shall mean the same thing wherever the runner is started from (#116). | STK-08 | Test |

### 16.3 Limits

| ID | Requirement | Source | Verification |
|---|---|---|---|
| RUN-FR-020 | A limit shall support a lower bound, an upper bound, or both. | STK-08 | Test |
| RUN-FR-021 | A limit shall support a nominal value with an absolute or percentage tolerance. | STK-08 | Test |
| RUN-FR-022 | A measured value shall be scalable before the limit is checked, so a limit can be stated in convenient units. | STK-08 | Test |
| RUN-FR-023 | A limit shall render as human-readable text for the report, and a failure shall state by how much the value missed. | STK-08 | Test |
| RUN-FR-025 | A measurement shall be reportable through a format template, so a value whose meaning is not decimal - an identifier, an address, a mask - reads in the record as it reads on the part. The template shall not affect the check, which remains against the number; the number shall be retained in the result record; and the limit's own bounds shall be rendered the same way, since a hexadecimal value beside decimal bounds is less legible than either alone. A template that cannot be applied shall be an error, not a silent fall back to the number. | STK-08, STK-16 | Test |
| RUN-FR-024 | A limit shall support exact comparison against text - a version, a device name - reported as the text itself rather than as a number. Matching shall be exact on the stripped value: a looser rule would pass 1.4.20 for 1.4.2, which is the failure such a limit exists to catch. | STK-08, STK-16 | Test |

### 16.4 Execution

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

### 16.5 Reporting

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
| RUN-FR-054 | A specification shall be able to carry a safety warning, and the runner shall print it before the bench is opened and before any setup step runs. A hazard disclosed in the report has been disclosed after the event. | STK-08, STK-17 | Test |
| RUN-FR-055 | The warning shall be written to the error stream, so that a run whose output is redirected still puts it in front of the operator. | STK-08 | Test |
| RUN-FR-056 | On a bench that is not simulated, a warned specification shall not start until the operator acknowledges the warning, either by an explicit option or by answering a prompt at a terminal. Confirmation shall be exact: nothing but the full word shall count. A warning a script can step over by not reading it is not a control, and what it protects cannot be recovered afterwards. | STK-08, STK-17 | Test |
| RUN-FR-057 | A simulated run shall not be gated, because nothing is energised and an unattended run has nobody to ask. Refusal to start shall be reported with its own exit status, distinct from a test failure. | STK-08 | Test |
| RUN-FR-058 | A specification shall be able to name values once, in a `parameters` block at its top, and use them anywhere below - an argument, a bound, a tolerance, or rendered into text. An undefined name shall be refused, and the values a run used shall appear in its record and report. | STK-08 | Test |
| RUN-FR-059 | A run shall be able to execute a chosen subset of a specification's test cases, named on the command line. A test case not chosen shall be recorded as skipped with the rationale "not selected", setup and teardown shall still run, the selection shall appear in the run record and every report, and a name matching no test case shall be refused before the bench is opened. (ASPICE 4.0: verification measure selection set, 08-58; verification measure not executed with a rationale, 13-25.) | STK-08 | Test |
| RUN-FR-060 | The runner shall write structured records to the event log: `run_start` carrying the whole plan (setup, every test case with its steps and whether it is selected, teardown), `case_start` and `case_end`, `step_start` and `step_end` (phase, test case and step index, action, resolved arguments, result, saved value, status, error, measurements, duration), and `run_end` carrying the verdict and totals, so that the tree of a run and every result can be rebuilt from the log alone, including by a reader that starts part-way through. | STK-19 | Test |
| RUN-FR-061 | `benchtools run --control PORT` shall serve a control channel - one JSON request per line, one JSON reply per line - on 127.0.0.1 only, never on another address, because a run drives the bench's supply. Port 0 shall pick a free port, and the port used shall be printed and written to the event log. Without the option no port shall be opened. | STK-08, STK-19 | Test |
| RUN-FR-062 | Control requests shall take effect between steps only, never during one. `pause` shall hold the run before its next step until `resume`, `abort` or a restart; `status` shall report whether the run is running, paused or idle, and its phase, test case and step. | STK-08, STK-19 | Test |
| RUN-FR-063 | `abort` shall stop the run after the current step. Teardown shall still run. The interrupted test case shall be recorded as an error, "aborted by operator", with the steps it ran, and every test case after it as not executed with the same rationale (one not selected stays "not selected"). An abort during setup shall be recorded as the setup error. | STK-08, STK-19 | Test |
| RUN-FR-064 | `restart_test` shall run the current test case again from its first step, and `restart_from` from a given test case and step, continuing in order from there. Values saved earlier in the run shall be kept; a restart shall be refused, naming the value, if a step from the target on needs a value no step has saved and none from the target on will save. Instrument state shall not be reset. Records of what runs again shall be replaced; steps before the target step keep their earlier records; test cases jumped over going forward shall be recorded as not executed, "skipped by operator". A target that does not exist, is not selected or is marked skip shall be refused. | STK-08, STK-19 | Test |
| RUN-FR-065 | Teardown shall not be interruptible: abort and restart during it, and any request during setup but pause, resume and abort, shall be refused with the reason. Every request, accepted or refused, and every action the runner takes on one, shall be written to the event log, so the evidence shows the operator's intervention. | STK-08, STK-19 | Test |
| RUN-FR-066 | The control channel shall take `read_setup`: at the next step every open instrument that can read its setup shall, without interrupting the run - the step runs as it would have, and a reader's failure is logged, never a step's error. It shall be refused in teardown and with no run. | STK-23 | Test |

---

### 16.6 VIEW — test run viewer

A browser page onto a bench run (#130, #137), served by `benchtools view`. It is a client of the runner: it reads the event log (RUN-FR-060) and drives the control channel (RUN-FR-061 … -065).

| ID | Requirement | Source | Verification |
|---|---|---|---|
| VIEW-FR-001 | `benchtools view` shall serve a page and a JSON API on 127.0.0.1 only, built on the standard library with no new dependency. The page shall be plain HTML, JavaScript and CSS served by the viewer, loading nothing from another site, so it works on a bench PC with no internet connection. | STK-23 | Test |
| VIEW-FR-002 | A request that changes anything - start, attach, control - shall carry the header `X-Benchtools: 1`, and every request's `Host` shall name this machine (`127.0.0.1`, `localhost`, `::1`); anything else shall be refused. A page from another site open in the same browser shall not be able to start, steer or abort a run. | STK-23 | Test |
| VIEW-FR-003 | The viewer shall follow a run's event log and rebuild the run from its structured records alone (RUN-FR-060): the same picture whether the viewer started the run, attached part-way through, or opened the log after it finished. A log holding several runs shall show the latest. | STK-23 | Test |
| VIEW-FR-004 | The Run page shall show the test specification, then setup, each test case and teardown, each with its steps; each step in words ("PSU set voltage: channel 2, volts 3.3", or the specification's own description), with its live status, duration, result or saved value, measurements against their limits, and error. Test cases not selected shall be shown as such, and the verdict when the run ends. | STK-23 | Test |
| VIEW-FR-005 | Changes shall reach the page as they happen, as Server-Sent Events: the event-log records and the run's state. A page that connects later shall be sent what it missed, and no record shall be lost between two reads. | STK-23 | Test |
| VIEW-FR-006 | The Run page shall offer pause, resume, abort (asking for confirmation, and saying that teardown still runs), restart of the current test case, and restart from any step, passed to the runner's control channel (RUN-FR-061 … -065). A button that does not apply shall be disabled, a refusal shall be shown with its reason, and a run without a control channel shall say so. | STK-23 | Test |
| VIEW-FR-007 | The viewer shall start a run: a test specification chosen from the directories it was given, a bench from its bench directories or a simulated bench, and the test cases ticked (RUN-FR-059). It shall run `benchtools run` as a separate process with an event log, a control channel, and JSON and markdown reports written to its runs directory, and follow it. Anything not offered shall be refused, and only one run started from the viewer shall be in progress at a time. | STK-23 | Test |
| VIEW-FR-008 | A test specification carrying a safety warning shall show it before a run is started; on a bench that is not simulated the run shall be refused unless the operator acknowledges it on the page, which is then passed as `--acknowledge` (RUN-FR-056). | STK-23 | Test |
| VIEW-FR-009 | The viewer shall attach to a run given its event log, taking the control port from the log (`control_listening`) unless one is given. An Event log page shall list every record - time, source, text - with each source shown or hidden by a checkbox. | STK-23 | Test |
| VIEW-FR-010 | An Instruments page shall show each instrument's traffic, per event-log source: each command paired with the replies that followed it and the milliseconds to the first, lines an instrument sends unasked (a BLE scan report, the probe stopping, an RTT line) as events that do not end the command whose reply is still to come, a reply with no command before it as unasked, and the driver's other lines as notes. | STK-23 | Test |
| VIEW-FR-011 | The Instruments page shall show the GPD-3303D's front panel - identity, each channel's readings, set voltage, current limit and CV or CC, the output and tracking - and the J-Link's state - probe, target, firmware, core running or halted and where, last flash and verify, breakpoints, RTT - rebuilt from their traffic; a value the log has not given shall show as a dash. | STK-23 | Test |
| VIEW-FR-012 | Selecting a step on the Run page shall show every instrument's traffic sent between that step's start and end, in time order, naming each instrument. | STK-23 | Test |
| VIEW-FR-013 | An RF page shall list the Kepler frames received - time, sensor, frame type, length, RSSI and what the frame says - decoding with the Kepler decoder any frame the driver did not, and stating why a frame could not be decoded or was rejected by the radio. Selecting a frame shall show its payload and whole decode. | STK-23 | Test |
| VIEW-FR-014 | The RF page shall show, per sensor, the frames heard, when last heard, the RSSI and the latest frame of each type, and shall be filterable to one sensor or all. | STK-23 | Test |
| VIEW-FR-015 | A BLE page shall show the devices the dongle has heard - address, name, advertising reports counted, mean advertising interval from the dongle's own clock, latest and mean RSSI, when last heard - the dongle's other events (scan, sensor, connection), and its commands paired with their replies. | STK-23 | Test |
| VIEW-FR-016 | A Graphs page shall plot every instrument's readings (CORE-FR-065) against time - supply current and voltage per channel, the thermometer's temperature, the multimeter's readings - one chart per unit, so no chart has two y-axes, each instrument, quantity and channel a series of its own. | STK-23 | Test |
| VIEW-FR-017 | For a chosen BLE device - by default the one heard most - the Graphs page shall plot, on the dongle's own clock, the interval between consecutive adverts, each interval's difference from the expected period the operator gives or else the median interval, and each advert's RSSI. | STK-23 | Test |
| VIEW-FR-018 | The charts of readings shall mark when each step started, naming it, so a change can be tied to the step that caused it; hovering a chart shall give the time and each series' nearest value. | STK-23 | Test |
| VIEW-FR-019 | The Event log page shall pause and resume its list: while paused, records that arrive are held and counted, not added, and resuming adds every one of them. This is the display only; the run's own pause is the Run page's (VIEW-FR-006). | STK-23 | Test |
| VIEW-FR-020 | The Event log page shall filter by instrument - each event-log source shown or hidden - and to chosen kinds of event that cut across instruments: RF frames received, RF frames sent, BLE adverts, readings, the runner's records and control. | STK-23 | Test |
| VIEW-FR-021 | The Event log page shall filter to one sensor, or none - a record matching when it names that sensor (a frame's Kepler sensor ID, the ID in a BLE device's name) or its text contains it - and, when the log holds more than one test, to one run and test case, each record tagged with the run and test case in progress when it was logged. | STK-23 | Test |
| VIEW-FR-022 | A status bar shall be visible on every page of the viewer, at any width, showing the run's state - running, paused, its verdict, or waiting - and each instrument by its event-log name: open or closed, the time since it last sent or received, and whether its last record was a warning or an error, each state named in words as well as by colour, the instrument's last line given on hovering. | STK-23 | Test |
| VIEW-FR-023 | The status bar shall show the test case running - its number of the test cases, name and requirement - or setup or teardown, and the steps run of the steps the run will execute: setup, teardown and the steps of selected test cases not marked skip, less those a test case that ended early will not run, counting again any a restart returns to pending. | STK-23 | Test |
| VIEW-FR-024 | The status bar shall estimate the time left, stated as an estimate: each remaining step expected to take what the same step with the same arguments last took, else its action's mean, else the mean of all steps run; unknown until three steps have run; built from step durations so that a pause does not inflate it. | STK-23 | Test |
| VIEW-FR-025 | `benchtools view --bind ADDRESS` shall listen on an address other than this machine's own only with an access token, generated at start and printed with the address to open: every request without it - page, files and API alike - shall be refused. Opening the printed address shall keep the token as an HttpOnly, SameSite cookie; a program may send it as `Authorization: Bearer`. Without `--bind` nothing shall be reachable from another machine. | STK-23 | Test |
| VIEW-FR-026 | `--read-only` shall refuse every request that changes anything - start, attach, control - so a run can be watched from another PC without being steered. | STK-23 | Test |
| VIEW-FR-027 | `--tls-cert` and `--tls-key` shall serve the viewer over HTTPS, the cookie then marked Secure; served over plain HTTP to another machine, the viewer shall say that the token crosses the network in clear. The runner's control channel shall stay on 127.0.0.1 whatever the viewer listens on. | STK-23 | Test |
| VIEW-FR-028 | The RF page shall show rf_monitor's Latest Data: each received frame, newest first, of one sensor or all - its time, sensor, type and RSSI; its raw bytes coloured by role (header, type, permute control, frame counter, payload); its packet header (sensor, product, capabilities, permute control, frame counter n of m); and its payload, each field with its unit and CONFIG values by parameter name - with a pause. | STK-23 | Test |
| VIEW-FR-029 | The RF page shall show rf_monitor's Config: for a sensor, each of the 60 configuration parameters - block, number, name, latest value as its enumeration names it, unit, when last received - disabled parameters and parameters not yet received shown as such, and rf_monitor's summary groups (operation timings, trigger settings, sampling, sync, FFT, other). | STK-23 | Test |
| VIEW-FR-030 | The RF page shall show rf_monitor's Identification: from a sensor's last VERSION frame, when it was received, the sensor and product, firmware version and SHA, capabilities and PCB, temperature and loaded battery, ticks and the reset reason by name, or that no VERSION frame has arrived. | STK-23 | Test |
| VIEW-FR-031 | The RF page shall plot rf_monitor's Environment for a sensor: temperature (°C) and battery (V) against time, from its ALIVE, TWF and VERSION frames, each frame once however many copies the sensor sent. | STK-23 | Test |
| VIEW-FR-032 | The RF page shall plot rf_monitor's Short Interval for a sensor and a chosen axis: acceleration RMS and peak to peak in mg and velocity RMS in mm/s, from ALIVE frames and TWF frames by their SI type, at the sensor's full scale (8 << si_scale g, 32767 counts), the raw count given on hovering, one y-axis per chart; and the magnetometer's frequency and amplitude in counts. | STK-23 | Test |
| VIEW-FR-033 | The RF page shall plot rf_monitor's Ticks for a sensor: the tick counter from its ALIVE frames and the change from one frame to the next, a fall shown as 0; and its graphs shall zoom in and out about the time last hovered, and reset. | STK-23 | Test |
| VIEW-FR-034 | The RF page shall reassemble a sensor's time waveforms from its TWF frames, per buffer (TWFA or TWFB, as the frame's param says) and axis: every sample placed where the frame's permutation (S2LP-FR-082) says, each polynomial repeat contributing its own samples, scaled to mg by the TWF scale (8 << twf_scale g), timed by the decoded ODR; a sample no frame carried left as a gap. A packet 0 after a complete waveform, or a change of packet count or permutation, starts the next. | STK-23 | Test |
| VIEW-FR-035 | The RF page shall show rf_monitor's TWF screen: the waveform (mg against ms) with gaps where samples are missing; its spectrum - gaps filled by straight lines, a Hann window, |X(k)| * 2 / N in mg at k * ODR / N Hz - the same with or without NumPy; a status line (receiving, or complete with ODR, scale, samples, duration, permutation); and the packets received and missed, as a percentage and a signal grade. | STK-23 | Test |
| VIEW-FR-036 | The TWF screen shall select buffer and axis, show the other buffer when the one chosen has nothing, and zoom the waveform in and out about the time last hovered within the capture, and reset. | STK-23 | Test |
| VIEW-FR-037 | The RF page shall show rf_monitor's Diagnostics for a sensor, per frame type: frames (each once), packets (every copy), copies expected and dropped and the success percentage - a burst of copies ending at the next frame's first copy, when all its copies are in, or after 1 s with none - and the period between frames: mean, population standard deviation, shortest and longest with the frames either side; the overall success; and a reset. | STK-23 | Test |
| VIEW-FR-038 | Diagnostics shall show the last ten frames of a type, newest first, with the time since the one before - following the type last received, or held on a type chosen. A frame of an unknown type shall be counted, not an error. | STK-23 | Test |
| VIEW-FR-039 | The RF page shall show rf_monitor's Sync for every sensor, unfiltered: from CMD and RESPONSE frames, the phase, retry, slot, and the LORES and HIRES countdowns - timed from the frames' own times, so a replayed log counts down as it did live - a NACK, a HIRES countdown and a fired HIRES each marked, and a sensor idle for 20 minutes dropped. | STK-23 | Test |
| VIEW-FR-040 | The viewer shall keep rf_monitor's Fault Description and Findings notes for a run, saved beside its event log so they outlive the viewer, refused while no event log is followed and in a read-only viewer. | STK-23 | Test |
| VIEW-FR-041 | The viewer shall export the run as one self-contained HTML report - no script, nothing fetched - holding the notes, the run and its test cases, and for a sensor its identification, Environment, Short Interval, Ticks and TWF graphs as inline SVG, its configuration, its Diagnostics period statistics and its latest frames. | STK-23 | Test |
| VIEW-FR-042 | The report shall be printable to PDF from the browser, laid out so that a chart or table is not split across pages, needing no PDF library. | STK-23 | Test |
| VIEW-FR-043 | The RF page shall show the Embedded Test Bench monitor's ST GUI page from the latest `rf_setup` record: the RF setup - board band and crystal; frequency, modulation, data rate, deviation, channel filter, output power; and the packet settings decoded from the registers - and when it was read. | STK-23 | Test |
| VIEW-FR-044 | The ST GUI page shall list every register - address, name, value, reset default - a writable register changed from its default marked, each expanding to its fields, with expand and collapse all, and export them as a register file the driver's `--setup` applies. | STK-23 | Test |
| VIEW-FR-045 | The ST GUI page shall list the frames received as ST's GUI does - timestamp, bytes, RSSI, data, a CRC failure as "Packet lost" - with a count, pause, follow and clear; and Refresh shall ask the runner to read the setup (RUN-FR-066), never opening the kit's port from the viewer. | STK-23 | Test |

## 17. Assumptions and constraints

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
| CON-07 | The dongle firmware targets nRF5 SDK 17.1.0. It **builds, links, fits and packages** against that SDK in CI (`.github/workflows/firmware.yml`), and also compiles against SDK 15.2.0 headers in the `canembed/canembed-arm` image. It has **not** been flashed or run on a dongle. See `docs/ble/BLE_Dongle_Notes.md` §5. |
| CON-08 | Only RTT-free, connection-oriented UART is supported; the dongle connects to one sensor at a time. |
| CON-03 | Instrument families named for future work - loads, signal sources, logic and protocol analysers - have no requirements in this revision. The core is designed for them but not validated against them. STK-13 (the GPD-3303D supply) and STK-18 (the TTi 1604 multimeter) are specified in §12 and §14. |
| CON-10 | The TTi 1604 driver is verified against a simulated meter and over a serial loopback. Against the physical meter (ETB-SYS5-002 §6.10, 2026-10-04) the link, key echo, reading rate, frame format and local/remote were confirmed; frequency selection and open-input overrange failed (#181). The remaining bench confirmation items are in `docs/dmm/TTi1604_Notes.md` (DMM-OPEN-01 … -08). |
| CON-04 | The J-Link driver is verified against a simulated probe and target, and since 2026-10-04 against a physical J-Link on an nRF52840 (ETB-SYS5-002 §6.1, §6.2): erase, flash and verify, memory, RTT, breakpoints, stepping, variables, the call stack and cycle-counter timing. Two defects found there are open: #177 (`reset(halt=False)` leaves the core halted) and #178 (registers stale just after a reset). The remaining bench confirmation item is JLINK-OPEN-03 in `docs/jlink/JLink_Integration_Notes.md` §4. |
| CON-05 | The scaling of SWO/ITM local timestamps to core cycles depends on the trace prescaler configured by the GDB server and the firmware. It is implemented from the ARMv7-M architecture reference manual and requires confirmation against a part before SWO timing figures are quoted (JLINK-OPEN-03). |
| CON-09 | The Pico 2 thermometer firmware **builds** (Pico SDK 2.1.1, Arm GNU 14.2.1, UF2 produced) and its portable logic passes its host unit tests. On 2026-10-03 it **ran on a real Pico 2** (Windows 10 bench PC): it enumerated on USB and reported the expected identity (PICO-OPEN-01, closed), and the `flash` command (PICO-FR-070 … -076) reflashed it by all three routes into the bootloader (PICO-OPEN-05, closed). The `rd` command set (#131) was cross-compiled on the bench PC and run on the same Pico 2 the same day, with no SHT30-D module connected: identity, `NAK`, the `err` replies, `Error` for the missing sensor and `ecureset` all behaved as specified, and `flash` installed it and confirmed its name, version and commit SHA by `rd`. It has **not** yet been run with a sensor attached, so a real temperature value is unconfirmed (PICO-OPEN-02, -03, -06). Drive discovery on Linux and macOS is untested on hardware. Bench confirmation items are in `docs/pico_sht30/Pico_SHT30_Notes.md` §7 (PICO-OPEN-01 … -06). |
| ASM-10 | The SHT30-D module is powered from the Pico's 3V3(OUT) and carries its own I2C pull-ups; its ADDR pin is tied low (0x44). |
| CON-06 | Markdown-to-Robot-Framework translation (STK-12) is not implemented in this revision. The driver's return types are constrained by JLINK-FR-081 so that it can be added without changing the driver. |

---

## 18. Requirements Traceability

The consolidated trace - stakeholder requirement to software requirement to
architecture element to design unit to source to test - is maintained as a
single work product, **ETB-RTM-001**
(`docs/aspice/EmbeddedTestBench_Traceability_Matrix.md`), rather than being restated in
each document.

That matrix is checked mechanically by `tests/test_traceability.py`, which fails
the build if a requirement declared here is absent from it, if a requirement
cited in source or tests is not declared here, or if a design unit or test group
is cited without being declared. Traceability in this project is therefore a
property the suite enforces rather than a table someone maintains by hand.

---

## 19. Review & Approval

Review and approval of this document are not entered in this table. They are
given by the merge of the pull request that last changed the document, and that
merge is the record (ETB-SUP8-001 §5.7). The evidence is the pull request, its
CI result and its merge record: who merged it, when, and the merge commit. The
last row of the revision history names the issue, and the issue links the pull
request.

| Role | Name | Recorded by |
|---|---|---|
| Author | Claude | The commits in the pull request |
| Technical Reviewer | Dermot Murphy | The merge of the pull request that last changed this document |
| Quality Assurance | Dermot Murphy | The merge of the pull request that last changed this document |
| Approver | Dermot Murphy | The merge of the pull request that last changed this document |

> **Note:** This document is under configuration management (SUP.8). Post-approval changes require a change request (SUP.10) and a new document version.
