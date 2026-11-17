<img src="../../assets/brand/svg/logos/embeddedtestbench-logo-compact.svg" alt="Embedded Test Bench" width="240">

# System Requirements Specification

*Automotive SPICE® PAM v4.0 | SYS.2 — System Requirements Analysis*

---

## 1. Document Identification & Control

| Field | Value | Field | Value |
|---|---|---|---|
| **Document ID** | ETB-SYS2-001 | **Version** | [latest, §2](#2-revision-history) |
| **Project** | Embedded Test Bench | **Date** | [latest, §2](#2-revision-history) |
| **Status** | [by location, ETB-SUP1-001 §6.3](EmbeddedTestBench_SUP1_Quality_Assurance_Plan.md#63-document-status) | **Classification** | Internal |
| **Author** | Claude | **Reviewer** | Dermot Murphy |
| **Approver** | Dermot Murphy | **Related Process** | SYS.2 |

> Reviewer and Approver are the same person; see ETB-DEV-002.

---

## 2. Revision History

| Version | Date | Author | Description of Change |
|---|---|---|---|
| 0.1 | 2026-09-19 | Claude | Initial |
| 0.2 | 2026-09-23 | Claude | TB-SYS2-051…053 added for the multimeter; TB-SYS2-104 no longer records it as deferred; STK-18 trace updated. |
| 0.3 | 2026-09-25 | Claude | TB-SYS2-075 and -076 revised, and TB-SYS2-080…084 added, for command/response tests: an error result and the order results are decided in, the sensor as a parameter with connect and disconnect steps, per-step timeouts, an expected disconnection, and the event log (#46, #48). |
| 0.4 | 2026-10-04 | Claude | #183: product renamed to Embedded Test Bench - document file name prefix `EmbeddedTestBench_`, identifier prefix `ETB-` (was `TB-`), product name in prose. Earlier revision rows keep the names in use when they were written. |
| 0.5 | 2026-10-05 | Claude | #204: Review & Approval table points to the merge of the pull request that last changed the document, which is the review and approval (ETB-SUP8-001 §5.7); no per-change signatures or dates. |
| 0.6 | 2026-10-05 | Claude | #194: the compact brand logo added above the title, the same line in every controlled document (ETB-SUP8-001 §6.3). |
| 0.7 | 2026-10-25 | Claude | #210: Version and Date in the identification table are links to the last revision history row, which holds them (ETB-SUP8-001 §6.2). |
| 0.8 | 2026-10-28 | Claude | #247: ETB-SYS2-037 - capture a target's serial output, record every line, write nothing to the port; traced to STK-24 and `SER-` (ETB-SWE1-001 §16). The software requirement sections referred to are §6 to §17 (RUN is now §17). |
| 0.9 | 2026-11-13 | Claude | #200: ETB-SYS2-065 - capture analogue and logic signals together on one time base, and drive a stimulus from a signal generator; traced to STK-02, STK-04, STK-05 and STK-07 and to `PSCOPE-` (ETB-SWE1-001 §17). The software requirement sections referred to are §6 to §18 (RUN is now §18). |
| 0.10 | 2026-11-14 | Claude | #342: ETB-SYS2-026 - measure the target's current at 100 000 samples a second, as its supply or in its supply line, with the average, charge and pulses, within the bench's voltage limit; traced to STK-25 and `PPK-` (ETB-SWE1-001 §18). The software requirement sections referred to are §6 to §19 (RUN is now §19). |
| next | 2026-11-17 | Claude | #371: the Status cell links to the status rule, ETB-SUP1-001 §6.3. A document's status follows from where it is in the repository (Released, Agreed, In review, In work) and is not written in by hand. Blank lines that split this table removed. |
| next | 2026-11-17 | Claude | #377: Referenced Documents cite each controlled document at the version of its last numbered revision row, kept by `scripts/doc_versions.py` (ETB-SUP8-001 §6.2). |
| next | 2026-11-17 | Claude | #365: §3.4 - the verification criterion is the requirement's text; each requirement carries its first release, read from the tags; the priority rule. §3.5 - each change records its impact on the system context. §4 - the context lists the PicoScope, PPK2, TTi 1604, PICO2 Test Board, the target's serial port and product repositories. ETB-SYS2-010 lists every instrument, method T as ETB-SYS5-002. ETB-SYS2-017 added for the PICO2 Test Board. ETB-SYS2-104 records the TTi 1604 hardware runs. §15 - requirements analysis per group, and the impact of each requirement added since `v0.01.0000`. Review & Approval is now §16. |
| next | 2026-11-17 | Claude | #365, review round 1 (PR #393): ETB-SYS2-017's capability dates from `v0.01.0000`, when the Pico 2 thermometer shipped. |
| next | 2026-11-17 | Claude | #364: ETB-SYS2-018 (device plugins), -054 (advertising profile), -055 (firmware update over BLE), -085 (watch and control a run, STK-23) and -086 (safety warning) added, so that every software requirement has a system parent. ETB-SYS2-017 no longer promises humidity (#131) and covers the board's firmware identity (STK-22). §14 traces every stakeholder requirement to its system requirements and points to the per-requirement trace in ETB-RTM-001. |

---

## 3. Purpose & Scope

### 3.1 Purpose

This document states what the Embedded Test Bench **system** must do, where the system is
the whole bench: a host computer running `benchtools`, the instruments attached
to it, the dongle firmware Embedded Test Bench itself supplies, and the target under test
as it appears to the bench.

It sits between the stakeholder requirements (ETB-SWE1-001 §4) and the software
requirements (ETB-SWE1-001 §6–§19). A stakeholder requirement says what the
engineer wants; a system requirement says what the bench must therefore do,
including the parts that are not software; a software requirement says what the
code must do.

Requirements that are purely about the Python package are **not** repeated here.
They live in ETB-SWE1-001, and §12 traces down to them.

### 3.2 Referenced Documents

| Document ID | Title | Version |
|---|---|---|
| ETB-SYS3-001 | Embedded Test Bench System Architecture | 0.8 |
| ETB-SYS4-001 | Embedded Test Bench System Integration & Integration Test | 0.6 |
| ETB-SYS5-001 | Embedded Test Bench System Qualification Test | 0.7 |
| ETB-SWE1-001 | Embedded Test Bench Software Requirements Specification | 1.70 |
| ETB-RTM-001 | Embedded Test Bench Traceability Matrix | 1.83 |
| ETB-MAN5-001 | Embedded Test Bench Risk Management Plan | 0.7 |
| ETB-ACQ4-001 | Embedded Test Bench Supplier Monitoring Plan | 0.11 |

### 3.3 Scope

**In scope:** the bench as a measuring instrument — what it controls, what it
measures, what it records, and what it must refuse.

**Out of scope:** the sensor products measured with it; the accuracy of the
instruments themselves, which is the manufacturers' specification and is cited
rather than restated; anything about the host operating system beyond what
§10 requires.

### 3.4 Requirement Notation

| Word | Meaning |
|---|---|
| **shall** | A requirement. Its absence is a defect |
| **should** | A recommendation. Departing from it is recorded, not silently done |
| **may** | Permission. Neither doing nor not doing it is a defect |

Each requirement carries a verification method: **T** test, **A** analysis,
**I** inspection, **D** demonstration. The verification criterion is the
requirement's own text, which states the observable result; the system
qualification scenario that verifies it is named in ETB-SYS5-001.

Each requirement also carries its **release**: the first release whose baseline
contains it, read from the tags. A requirement written on a branch shows the
release it is planned for (#365).

**Priority.** Every system requirement is mandatory for the release that carries
it. A capability that is optional is not written as a system requirement here;
it stays a software requirement or an issue. So no per-row priority is carried:
the priority of every row is "mandatory" (#365, AUD-v0.03-002).

### 3.5 Change Impact

A change to a requirement in this document records its impact on the system
context (§4): which actors and external entities it adds, changes or removes,
and which interfaces of ETB-SYS3-001 §6 it touches. The impact statement goes in
the change request (ETB-SUP10-001 §5, step 2) and in the revision history row.
The impacts of the requirements added since `v0.01.0000` are recorded in §15.2.

---

## 4. System Context

| Actor / external entity | Interacts with the bench by |
|---|---|
| Test engineer | Writing bench specifications, starting runs, reading reports |
| Target under test | Being powered, programmed, run, and interrogated over BLE, RTT and its serial port |
| Oscilloscope (TDS3014B) | Ethernet (VXI-11) |
| Mixed-signal oscilloscope (PicoScope 3405D) | USB, through Pico Technology's `ps3000a` library |
| Bench power supply (GPD-3303D) | USB serial |
| Current profiler (PPK2) | USB CDC, the kit's own binary protocol; it powers the target or sits in its supply line |
| Multimeter (TTi 1604) | RS-232 through a USB serial adapter, read as a stream of display frames |
| Debug probe | USB, driven over TCP (GDB server, RTT) |
| BLE dongle | USB serial, running Embedded Test Bench's own firmware |
| Sub-GHz kit | USB serial, running the vendor's firmware |
| PICO2 Test Board | USB serial, running Embedded Test Bench's own firmware; a reference source of known quantities |
| Target's serial port | USB serial adapter; the bench only listens (ETB-SYS2-037) |
| Product repositories | Loading device-specific plugins (decoders, panels) through the plugin interface |
| CI system | Running the suite and the firmware build on every push |

---

## 5. Purpose of the System

| ID | Requirement | Method | Release |
|---|---|---|---|
| ETB-SYS2-001 | The system shall let an engineer describe a bench test once, run it against a target, and obtain a record from which another engineer can reproduce the run. | D | `v0.01.0000` |
| ETB-SYS2-002 | The system shall make firmware state — memory, variables, RTT output, execution — an assertable quantity in the same test as instrument measurements. | T | `v0.01.0000` |
| ETB-SYS2-003 | The system shall distinguish a **failure** (the target did not meet a stated expectation) from an **error** (the bench could not make the measurement), and shall never report one as the other. | T | `v0.01.0000` |
| ETB-SYS2-004 | The system shall not report a value it did not measure. Where a quantity cannot be obtained, the step shall error rather than substitute a default. | T | `v0.01.0000` |

---

## 6. Bench Composition

| ID | Requirement | Method | Release |
|---|---|---|---|
| ETB-SYS2-010 | The system shall support a bench comprising: a Tektronix TDS3014B oscilloscope, a PicoScope 3405D mixed-signal oscilloscope, a GW Instek GPD-3303D bench power supply, a Nordic Power Profiler Kit II, a TTi 1604 bench multimeter, a SEGGER J-Link debug probe, a Nordic nRF52840 dongle running Embedded Test Bench firmware, an ST S2-LP development kit, a PICO2 Test Board, and a serial port on which a target prints. | T | `v0.01.0000` |
| ETB-SYS2-011 | The system shall allow a bench to contain any subset of those instruments, and a test shall run if the instruments it uses are present. | T | `v0.01.0000` |
| ETB-SYS2-012 | The system shall provide a simulated counterpart for every instrument, sufficient to run a bench specification end to end with no hardware attached. | T | `v0.01.0000` |
| ETB-SYS2-013 | Each simulated instrument shall model the instrument's behaviour — its modes, its refusals, its state — and shall not be implemented by returning the replies a test expects. | I | `v0.01.0000` |
| ETB-SYS2-014 | A bench shall be described as data, in a file, not in code. | I | `v0.01.0000` |
| ETB-SYS2-015 | The system shall record, for every run, the identity of each instrument used: model, and where the instrument can report them, serial number and firmware revision. | T | `v0.01.0000` |
| ETB-SYS2-016 | A run in which any instrument was simulated shall be labelled as simulated in every report format the system produces. | T | `v0.01.0000` |
| ETB-SYS2-017 | The system shall drive a reference test board, the PICO2 Test Board, which gives the bench known quantities to check itself against: a temperature reading, indicator LEDs, and an analogue and audio signal of stated frequency; and shall read the board's firmware name and version and check them against the image it installed (#365, #364). | T | `v0.04.0000` (capability since `v0.01.0000`) |
| ETB-SYS2-018 | The system shall load the code specific to a device under test - its frame decoders, register files and viewer panels - from a folder outside the bench's own package, named by the bench or the specification, and shall record in every run which was loaded and at which version (#364). | T | `v0.04.0000` (capability since `v0.03.0000`) |

> ETB-SYS2-013 and ETB-SYS2-016 together are the treatment of ETB-RISK-001: a
> simulator that echoed expected replies would let a driver defect pass, and an
> unlabelled simulated run would let the result be read as a measurement.

---

## 7. Power

| ID | Requirement | Method | Release |
|---|---|---|---|
| ETB-SYS2-020 | The system shall set the voltage and current limit of each programmable supply channel, and switch the output on and off. | T | `v0.01.0000` |
| ETB-SYS2-021 | The system shall read back each channel's output voltage and current. | T | `v0.01.0000` |
| ETB-SYS2-022 | The system shall read the supply's operating state, including which channels are in constant-current, and the tracking mode in force. | T | `v0.01.0000` |
| ETB-SYS2-023 | Where the supply's tracking mode means a per-channel setpoint would be accepted and silently discarded by the hardware, the system shall refuse the write rather than perform it. | T | `v0.01.0000` |
| ETB-SYS2-024 | The system shall be able to bring the supply to a known safe state — outputs off, setpoints at zero — and that state shall be reachable whatever mode the supply is in. | T | `v0.01.0000` |
| ETB-SYS2-025 | The system shall not present the supply's fixed, front-panel-switched auxiliary rail as a controllable channel. | I | `v0.01.0000` |
| ETB-SYS2-026 | The system shall measure the current the target draws, from under a microamp to about 1 A, at 100 000 samples a second, either supplying the target itself at a set voltage or in the line of an outside supply; and shall report the average current over a window, the charge drawn, and the pulses in it - their count, widths and charges - marked by a current threshold or by a logic signal from the target (#342). It shall not set or switch on a voltage above the limit the bench states for what is wired. | T | `v0.03.0000` |

> ETB-SYS2-023 is the treatment of ETB-RISK-008. The GPD-3303D accepts CH2
> setpoints in series and parallel tracking and discards them; a bench that
> reported the write as successful would let an engineer believe a rail was set
> when it was not.

---

## 8. Target Control and Observation

| ID | Requirement | Method | Release |
|---|---|---|---|
| ETB-SYS2-030 | The system shall programme a target's flash from an image file through the debug probe, and verify what was programmed against that image. | T | `v0.01.0000` |
| ETB-SYS2-031 | The system shall run, halt, reset and single-step the target, and set and clear breakpoints. | T | `v0.01.0000` |
| ETB-SYS2-032 | The system shall read and write target memory, at a stated address, width and byte order, and shall refuse a width or byte order it cannot honour. | T | `v0.01.0000` |
| ETB-SYS2-033 | The system shall read named variables and the call stack from the target. | T | `v0.01.0000` |
| ETB-SYS2-034 | The system shall read and write the target's RTT channels, and shall be able to log RTT output to a file for the duration of a run. | T | `v0.01.0000` |
| ETB-SYS2-035 | The system shall measure elapsed time between points in target execution, and shall report the resolution of the method used. | T | `v0.01.0000` |
| ETB-SYS2-036 | Every firmware image the system programmes shall be accompanied by a manifest stating its version and build date, and the system shall be able to compare the version a running target reports against that manifest. | T | `v0.01.0000` |
| ETB-SYS2-037 | The system shall capture the lines a target prints on a serial port, for a stated time or until a line matches an expected pattern, shall record every line it captures in the run's evidence, and shall write nothing to that port (#247). | T | `v0.03.0000` |

---

## 9. Wireless Interfaces

| ID | Requirement | Method | Release |
|---|---|---|---|
| ETB-SYS2-040 | The system shall scan for BLE devices and report, for each, its address, name and advertising data. | T | `v0.01.0000` |
| ETB-SYS2-041 | The system shall connect to a selected BLE device, exchange command/response traffic over a UART service, and disconnect. | T | `v0.01.0000` |
| ETB-SYS2-042 | The system shall measure the time from the end of a transmitted command to the start of the response. | T | `v0.01.0000` |
| ETB-SYS2-043 | Response timing shall be measured in the dongle, not inferred from host timestamps; host timestamps shall be retained alongside. | T | `v0.01.0000` |
| ETB-SYS2-044 | The system shall log a BLE session — commands, responses and their times — to a file. | T | `v0.01.0000` |
| ETB-SYS2-045 | The system shall select a target by an identifier read from the target's own memory, matching it against the identifier carried in the advertising name. | T | `v0.01.0000` |
| ETB-SYS2-046 | The system shall programme, read and write every register of the S2-LP transceiver, transmit and receive over the sub-GHz link, and log all data exchanged. | T | `v0.01.0000` |
| ETB-SYS2-047 | The system shall drive the S2-LP kit with either the vendor's CLI firmware, whose command set is an external interface and is not modified, or this project's own kit firmware (`firmware/s2lp_kit`, #84), which contains no vendor source. It shall identify which one the kit runs. | I | `v0.01.0000` |
| ETB-SYS2-051 | The system shall measure voltage, current, resistance and frequency with a TTi 1604 bench multimeter over RS-232, reporting every value in SI units. | T | `v0.01.0000` |
| ETB-SYS2-052 | The system shall report a multimeter reading taken from a frozen display as held, so that a stored value is not recorded as a present measurement. | T | `v0.01.0000` |
| ETB-SYS2-053 | The system shall report a multimeter overrange as an overrange rather than as a number. | T | `v0.01.0000` |
| ETB-SYS2-054 | The system shall measure a BLE device's advertising profile: every advertising event from a chosen device, timestamped, with its signal strength and channel; the interval between events and its spread; and the events it missed, reported as missed rather than as a slower interval (#364). | T | `v0.04.0000` (capability since `v0.01.0000`) |
| ETB-SYS2-055 | The system shall update a target's firmware over BLE through its bootloader, from a DFU package, and shall detect a piece the target did not receive, resend it within a stated bound, and report the transfer as failed when it cannot complete (#364). | T | `v0.04.0000` (capability since `v0.02.0000`) |

### 9.1 Target Identity

| ID | Requirement | Method | Release |
|---|---|---|---|
| ETB-SYS2-048 | The system shall read the target's sensor identifier from UICR `CUSTOMER[0]` at address 0x10001080: a validity byte, which is zero for a valid identifier, followed by three identifier bytes in address order. | T | `v0.01.0000` |
| ETB-SYS2-049 | The system shall treat a non-zero validity byte as an invalid identifier and shall not use the following bytes as one. | T | `v0.01.0000` |
| ETB-SYS2-050 | The system shall render a valid sensor identifier as six uppercase hexadecimal digits, as it appears in the advertising name. | T | `v0.01.0000` |

---

## 10. Measurement

| ID | Requirement | Method | Release |
|---|---|---|---|
| ETB-SYS2-060 | The system shall configure oscilloscope channels — enable, vertical scale, position — and the timebase and trigger. | T | `v0.01.0000` |
| ETB-SYS2-061 | The system shall arm the instrument, capture an acquisition, and retrieve the waveform records. | T | `v0.01.0000` |
| ETB-SYS2-062 | The system shall measure quantities from a captured record, including period, frequency, edge times, and the spread in time between several channels reaching a threshold. | T | `v0.01.0000` |
| ETB-SYS2-063 | Analysis of captured records shall be performed on the host from the captured data, so that the same record analysed twice yields the same result. | T | `v0.01.0000` |
| ETB-SYS2-064 | Every measurement the system reports shall carry its units and, where the method bounds it, its resolution. | T | `v0.01.0000` |
| ETB-SYS2-065 | The system shall capture analogue and digital (logic) signals of the target together, in one acquisition on one time base, with the analogue records in seconds and volts and each logic line as a record of 0 and 1, so that a test can relate a logic event to an analogue one; and it shall drive a stated stimulus waveform into the target from a signal generator, within that generator's stated limits (#200). | T | `v0.03.0000` |

---

## 11. Test Definition, Execution and Evidence

| ID | Requirement | Method | Release |
|---|---|---|---|
| ETB-SYS2-070 | A bench test shall be expressible as data — a specification file — separately from the description of the bench it runs on, so the same test runs on different benches. | T | `v0.01.0000` |
| ETB-SYS2-071 | A specification shall be able to carry a value obtained in one step into a later step, rather than requiring it to be restated. | T | `v0.01.0000` |
| ETB-SYS2-072 | A specification shall be able to express an expectation as a limit, a tolerance, or an exact text, and shall state which. | T | `v0.01.0000` |
| ETB-SYS2-073 | The system shall support a command/response test written as a table in a markdown document, where that document is simultaneously the specification of the command set and the test of it. | T | `v0.01.0000` |
| ETB-SYS2-074 | In such a document a step may be a delay, or a command with no stated expectation; both shall be recorded and reported as skipped, not as passed. | T | `v0.01.0000` |
| ETB-SYS2-075 | A run shall be in error if any step errored, fail if any step failed, and pass otherwise. | T | `v0.01.0000` |
| ETB-SYS2-076 | The system shall record, for every step: the test, the step number, what was sent, what was received, what was expected, the elapsed time, the result, and a note saying why. | T | `v0.01.0000` |
| ETB-SYS2-077 | Elapsed times in a command/response report shall be reported at 10 ms resolution, with the underlying higher-resolution measurement retained. | T | `v0.01.0000` |
| ETB-SYS2-078 | A report shall name the specification and the bench it ran against, and shall be written to a file. | T | `v0.01.0000` |
| ETB-SYS2-079 | The system shall produce machine-readable results suitable for a CI system to consume. | T | `v0.01.0000` |
| ETB-SYS2-080 | A step's result shall be the first that applies of: error, when the system returned a failure code; skip, when nothing was expected; fail, when the response differs from what was expected; pass, when it matches. | T | `v0.01.0000` |
| ETB-SYS2-081 | A command/response test shall be able to take the sensor under test as a parameter, and to connect to it and disconnect from it as steps. | T | `v0.01.0000` |
| ETB-SYS2-082 | A step shall be able to set how long it waits for its response, since some commands take longer than others. | T | `v0.01.0000` |
| ETB-SYS2-083 | A step shall be able to expect the sensor to disconnect after a command, and the time from the command to the disconnection shall be measured. | T | `v0.01.0000` |
| ETB-SYS2-084 | A run shall be able to log each event - transmission, reception, delay, connection, disconnection, error - with the time it occurred, the step, the data and the result. | T | `v0.01.0000` |
| ETB-SYS2-085 | The system shall let an engineer watch a run while it executes and control it: start a run, or attach to one already running or finished; pause and resume it; restart it from a chosen test case and step; or abort it, teardown still running. It shall show each test case and step with its result, and each instrument's commands, responses and readings, as they occur, rebuilt from the run's event log alone. Control shall take effect only between steps, and shall be accepted only from the host running the bench unless the engineer grants access by token (#364). | T | `v0.04.0000` (capability since `v0.01.0000`) |
| ETB-SYS2-086 | A specification shall be able to carry a safety warning, which the system shall show before any instrument is opened; a run on real instruments shall not start without the engineer's acknowledgement of it (#364). | T | `v0.04.0000` (capability since `v0.01.0000`) |

---

## 12. Non-Functional Requirements

| ID | Requirement | Method | Release |
|---|---|---|---|
| ETB-SYS2-090 | The host software shall run on Windows and on Linux, and the whole bench shall be capable of running inside a container where the instrument links are network links. | A | `v0.01.0000` |
| ETB-SYS2-091 | The dongle firmware shall build from a clean checkout in continuous integration, and its flash and RAM usage shall be recorded. | T | `v0.01.0000` |
| ETB-SYS2-092 | C source in this project shall conform to ETB-STD-002 and ETB-STY-001, checked mechanically on every push. | T | `v0.01.0000` |
| ETB-SYS2-093 | No vendor-supplied source or documentation text shall be incorporated into this repository; vendor devices shall be described by independently recorded facts. | I | `v0.01.0000` |
| ETB-SYS2-094 | The system shall fail loudly on a request it cannot satisfy, with a message naming what was asked and why it could not be done. | T | `v0.01.0000` |
| ETB-SYS2-095 | Every system requirement in this document shall be traceable to at least one software requirement or firmware element, and to at least one test. | A | `v0.01.0000` |

---

## 13. Assumptions and Constraints

| ID | Statement |
|---|---|
| ETB-SYS2-100 | The bench is operated by an engineer who is present; the system is not designed for unattended operation with live instruments. |
| ETB-SYS2-101 | Instrument accuracy is the manufacturer's specification. Embedded Test Bench does not improve it and does not restate it. |
| ETB-SYS2-102 | Embedded Test Bench is a test tool. It carries no ASIL classification and is not part of any delivered product. |
| ETB-SYS2-103 | The S2-LP kit runs ST's firmware under SLA0072; see ETB-ACQ4-001 §4.2. |
| ETB-SYS2-104 | The multimeter interface (STK-18) is implemented for the TTi 1604 (ETB-SYS2-051…053). It has been run against a physical meter: QS-09 on 2026-10-04 (ETB-SYS5-002 §5.2) and the #181 bench findings of 2026-10-28 (`docs/aspice/qualification/2026-10-28/181_tti1604/`). The items still not confirmed are listed in `docs/dmm/TTi1604_Notes.md` §5. |

---

## 14. Traceability

Upward to the stakeholder requirements in ETB-SWE1-001 §4, downward to the
software requirements in ETB-SWE1-001 §6 to §19 and to the system elements of
ETB-SYS3-001. The per-requirement trace, both ways, is in ETB-RTM-001, sections
"Stakeholder Needs to System Requirements" and "System Requirements to Elements
and Software Requirements", and `tests/test_traceability.py` checks it (#364).

| Stakeholder | System requirements |
|---|---|
| STK-01 | ETB-SYS2-010, ETB-SYS2-060, ETB-SYS2-061 |
| STK-02 | ETB-SYS2-060, ETB-SYS2-065 |
| STK-03 | ETB-SYS2-060 |
| STK-04 | ETB-SYS2-060, ETB-SYS2-061, ETB-SYS2-063, ETB-SYS2-065 |
| STK-05 | ETB-SYS2-004, ETB-SYS2-062, ETB-SYS2-063, ETB-SYS2-064, ETB-SYS2-065 |
| STK-06 | ETB-SYS2-090 |
| STK-07 | ETB-SYS2-010, ETB-SYS2-011, ETB-SYS2-012, ETB-SYS2-013, ETB-SYS2-014, ETB-SYS2-018, ETB-SYS2-065, ETB-SYS2-094 |
| STK-08 | ETB-SYS2-001, ETB-SYS2-003, ETB-SYS2-004, ETB-SYS2-011, ETB-SYS2-012, ETB-SYS2-013, ETB-SYS2-014, ETB-SYS2-015, ETB-SYS2-016, ETB-SYS2-018, ETB-SYS2-070, ETB-SYS2-071, ETB-SYS2-072, ETB-SYS2-075, ETB-SYS2-076, ETB-SYS2-078, ETB-SYS2-079, ETB-SYS2-086, ETB-SYS2-094, ETB-SYS2-095 |
| STK-09 | ETB-SYS2-002, ETB-SYS2-010, ETB-SYS2-030, ETB-SYS2-031, ETB-SYS2-032, ETB-SYS2-033, ETB-SYS2-034, ETB-SYS2-035, ETB-SYS2-036, ETB-SYS2-045, ETB-SYS2-048, ETB-SYS2-049 |
| STK-10 | ETB-SYS2-002, ETB-SYS2-034 |
| STK-11 | ETB-SYS2-090 |
| STK-12 | ETB-SYS2-073, ETB-SYS2-074, ETB-SYS2-075, ETB-SYS2-076, ETB-SYS2-077, ETB-SYS2-080, ETB-SYS2-081, ETB-SYS2-082, ETB-SYS2-083, ETB-SYS2-084 |
| STK-13 | ETB-SYS2-010, ETB-SYS2-020, ETB-SYS2-021, ETB-SYS2-022, ETB-SYS2-023, ETB-SYS2-024, ETB-SYS2-025 |
| STK-14 | ETB-SYS2-010, ETB-SYS2-041, ETB-SYS2-042, ETB-SYS2-043, ETB-SYS2-044, ETB-SYS2-055, ETB-SYS2-077, ETB-SYS2-081, ETB-SYS2-082, ETB-SYS2-083 |
| STK-15 | ETB-SYS2-040, ETB-SYS2-041, ETB-SYS2-045, ETB-SYS2-048, ETB-SYS2-049, ETB-SYS2-050, ETB-SYS2-054 |
| STK-16 | ETB-SYS2-036, ETB-SYS2-043, ETB-SYS2-091, ETB-SYS2-092 |
| STK-17 | ETB-SYS2-015, ETB-SYS2-044, ETB-SYS2-076, ETB-SYS2-084, ETB-SYS2-086 |
| STK-18 | ETB-SYS2-010, ETB-SYS2-051, ETB-SYS2-052, ETB-SYS2-053, ETB-SYS2-093 |
| STK-19 | ETB-SYS2-010, ETB-SYS2-046, ETB-SYS2-047, ETB-SYS2-092 |
| STK-20 | ETB-SYS2-047, ETB-SYS2-093 |
| STK-21 | ETB-SYS2-010, ETB-SYS2-017, ETB-SYS2-092 |
| STK-22 | ETB-SYS2-017, ETB-SYS2-036 |
| STK-23 | ETB-SYS2-085 |
| STK-24 | ETB-SYS2-010, ETB-SYS2-037 |
| STK-25 | ETB-SYS2-010, ETB-SYS2-026 |

---

## 15. Requirements Analysis

### 15.1 Correctness, Feasibility and Verifiability (SYS.2.BP3)

Analysed 2026-11-17 (#365), group by group, against the stakeholder needs
(ETB-SWE1-001 §4), the qualification record (ETB-SYS5-002) and the code. A group
is analysed again when a requirement in it changes.

| Group | Correct | Feasible | Verifiable | Findings |
|---|---|---|---|---|
| §5 Purpose, ETB-SYS2-001 to -004 | Yes. Each states an outcome, not a design. -003 and -004 are the bench's honesty rules and do not conflict | Shown: implemented in the runner and every driver | -001 by demonstration (QS-01); -002 to -004 by test | None |
| §6 Bench composition, -010 to -017 | -010 listed only five instruments until #365, so it was incorrect against the bench; corrected | Shown: every listed instrument has a driver and a simulator | -010 by test (QS-10, every instrument identified on the bench); -013 by inspection of the simulators | -010's method changed from I to T, to match ETB-SYS5-002 §7. -017 added for the PICO2 Test Board, which had software requirements (`PICO-`) and no system requirement |
| §7 Power, -020 to -026 | Yes. -023 and -024 are safety rules from ETB-RISK-008 | Shown on hardware: the GPD-3303D (QS-02, QS-06) and the PPK2 (#342, 2026-11-14) | By test, with numeric limits in the software requirements | -026's range (under 1 µA to about 1 A) is the kit's, not measured end to end on the bench. Recorded for SYS.5 (#363) |
| §8 Target control, -030 to -037 | Yes | Shown on hardware: QS-01, J-Link runs (ETB-SYS5-002 §9) | By test | -035's resolution is reported per method; the criterion is that it is reported, not a value |
| §9 Wireless and identity, -040 to -053 | Yes. -048 to -050 fix the identifier format to the Kepler reference device; ETB-SYS2-102 and #197 record that it is the reference device | Shown on hardware: BLE (QS-03), S2-LP (QS-07), TTi 1604 (QS-09) | By test | -043 is a design constraint (measure in the dongle) stated as a requirement on purpose, because the timing is only meaningful so; kept |
| §10 Measurement, -060 to -065 | Yes | -060 to -064: the TDS3014B was out of scope in the campaign (ETB-SYS5-002 §3.3). -065: shown on the PicoScope (#200) | By test | The TDS3014B half of -060 to -062 has no hardware evidence; carried by #363 |
| §11 Test definition, -070 to -084 | Yes. -075 and -080 together define every result state, with no overlap | Shown: the runner and the command-document runner | By test, mostly in simulation, which is enough for host-only behaviour | None |
| §12 Non-functional, -090 to -095 | -090's container clause holds only where links are network links, as it says | -091, -092 shown in CI; -090 shown on Windows (bench PC) and Linux (CI) | -090 by analysis; -093 by inspection; the rest by test | -095 is a rule about this document. It is verified by the trace check in ETB-RTM-001 (#364) |

### 15.2 Impact on the System Context (SYS.2.BP4)

The impact of each requirement added or changed since `v0.01.0000`.

| Requirement | Change | Impact on the context (§4) | Interfaces (ETB-SYS3-001 §6) |
|---|---|---|---|
| ETB-SYS2-051 to -053 | Added for the TTi 1604 (before `v0.01.0000`, recorded here for completeness) | New external entity: the multimeter | ETB-SIF-16 |
| ETB-SYS2-037 | Added, #247 | New external entity: the target's serial port, listened to only | ETB-SIF-18 |
| ETB-SYS2-065 | Added, #200 | New external entity: the PicoScope 3405D | ETB-SIF-12, -13 |
| ETB-SYS2-026 | Added, #342 | New external entity: the PPK2, which can be the target's supply | ETB-SIF-14, -15 |
| ETB-SYS2-017 | Added, #365 | New external entity: the PICO2 Test Board | ETB-SIF-17 |
| ETB-SYS2-010 | Changed, #365: the full instrument list | None new: it lists the entities above | — |
| — | The plugin interface (#238) | New external entity: product repositories supplying plugins | None at system level: plugins load on the host |

---

## 16. Review & Approval

Review and approval of this document are not entered in this table. They are
given by the merge of the pull request that last changed the document, and that
merge is the record (ETB-SUP8-001 §5.7). The evidence is the pull request, its
CI result and its merge record: who merged it, when, and the merge commit. The
last row of the revision history names the issue, and the issue links the pull
request.

| Role | Name | Recorded by |
|---|---|---|
| Author | Claude | The commits in the pull request |
| Reviewer | Dermot Murphy | The merge of the pull request that last changed this document |
| Approver | Dermot Murphy | The merge of the pull request that last changed this document |
