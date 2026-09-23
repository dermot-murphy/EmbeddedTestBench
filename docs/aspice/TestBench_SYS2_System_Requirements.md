# System Requirements Specification

*Automotive SPICE® PAM v4.0 | SYS.2 — System Requirements Analysis*

---

## 1. Document Identification & Control

| Field | Value | Field | Value |
|---|---|---|---|
| **Document ID** | TB-SYS2-001 | **Version** | 0.2 |
| **Project** | TestBench | **Date** | 2026-09-23 |
| **Status** | Draft | **Classification** | Internal |
| **Author** | Claude | **Reviewer** | Dermot Murphy |
| **Approver** | Dermot Murphy | **Related Process** | SYS.2 |

> Reviewer and Approver are the same person; see TB-DEV-002.

---

## 2. Revision History

| Version | Date | Author | Description of Change |
|---|---|---|---|
| 0.1 | 2026-09-19 | Claude | Initial |
| 0.2 | 2026-09-23 | Claude | TB-SYS2-051…053 added for the multimeter; TB-SYS2-104 no longer records it as deferred; STK-18 trace updated. |

---

## 3. Purpose & Scope

### 3.1 Purpose

This document states what the TestBench **system** must do, where the system is
the whole bench: a host computer running `benchtools`, the instruments attached
to it, the dongle firmware TestBench itself supplies, and the target under test
as it appears to the bench.

It sits between the stakeholder requirements (TB-SWE1-001 §4) and the software
requirements (TB-SWE1-001 §6–§15). A stakeholder requirement says what the
engineer wants; a system requirement says what the bench must therefore do,
including the parts that are not software; a software requirement says what the
code must do.

Requirements that are purely about the Python package are **not** repeated here.
They live in TB-SWE1-001, and §12 traces down to them.

### 3.2 Referenced Documents

| Document ID | Title | Version |
|---|---|---|
| TB-SYS3-001 | TestBench System Architecture | 0.1 |
| TB-SYS4-001 | TestBench System Integration & Integration Test | 0.1 |
| TB-SYS5-001 | TestBench System Qualification Test | 0.1 |
| TB-SWE1-001 | TestBench Software Requirements Specification | 0.1 |
| TB-RTM-001 | TestBench Traceability Matrix | 0.1 |
| TB-MAN5-001 | TestBench Risk Management Plan | 0.1 |
| TB-ACQ4-001 | TestBench Supplier Monitoring Plan | 0.1 |

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
**I** inspection, **D** demonstration.

---

## 4. System Context

| Actor / external entity | Interacts with the bench by |
|---|---|
| Test engineer | Writing bench specifications, starting runs, reading reports |
| Target under test | Being powered, programmed, run, and interrogated over BLE and RTT |
| Oscilloscope | Ethernet (VXI-11) |
| Bench power supply | USB serial |
| Debug probe | USB, driven over TCP (GDB server, RTT) |
| BLE dongle | USB serial, running TestBench's own firmware |
| Sub-GHz kit | USB serial, running the vendor's firmware |
| CI system | Running the suite and the firmware build on every push |

---

## 5. Purpose of the System

| ID | Requirement | Method |
|---|---|---|
| TB-SYS2-001 | The system shall let an engineer describe a bench test once, run it against a target, and obtain a record from which another engineer can reproduce the run. | D |
| TB-SYS2-002 | The system shall make firmware state — memory, variables, RTT output, execution — an assertable quantity in the same test as instrument measurements. | T |
| TB-SYS2-003 | The system shall distinguish a **failure** (the target did not meet a stated expectation) from an **error** (the bench could not make the measurement), and shall never report one as the other. | T |
| TB-SYS2-004 | The system shall not report a value it did not measure. Where a quantity cannot be obtained, the step shall error rather than substitute a default. | T |

---

## 6. Bench Composition

| ID | Requirement | Method |
|---|---|---|
| TB-SYS2-010 | The system shall support a bench comprising: a Tektronix TDS3014B oscilloscope, a GW Instek GPD-3303D bench power supply, a SEGGER J-Link debug probe, a Nordic nRF52840 dongle running TestBench firmware, and an ST S2-LP development kit. | I |
| TB-SYS2-011 | The system shall allow a bench to contain any subset of those instruments, and a test shall run if the instruments it uses are present. | T |
| TB-SYS2-012 | The system shall provide a simulated counterpart for every instrument, sufficient to run a bench specification end to end with no hardware attached. | T |
| TB-SYS2-013 | Each simulated instrument shall model the instrument's behaviour — its modes, its refusals, its state — and shall not be implemented by returning the replies a test expects. | I |
| TB-SYS2-014 | A bench shall be described as data, in a file, not in code. | I |
| TB-SYS2-015 | The system shall record, for every run, the identity of each instrument used: model, and where the instrument can report them, serial number and firmware revision. | T |
| TB-SYS2-016 | A run in which any instrument was simulated shall be labelled as simulated in every report format the system produces. | T |

> TB-SYS2-013 and TB-SYS2-016 together are the treatment of TB-RISK-001: a
> simulator that echoed expected replies would let a driver defect pass, and an
> unlabelled simulated run would let the result be read as a measurement.

---

## 7. Power

| ID | Requirement | Method |
|---|---|---|
| TB-SYS2-020 | The system shall set the voltage and current limit of each programmable supply channel, and switch the output on and off. | T |
| TB-SYS2-021 | The system shall read back each channel's output voltage and current. | T |
| TB-SYS2-022 | The system shall read the supply's operating state, including which channels are in constant-current, and the tracking mode in force. | T |
| TB-SYS2-023 | Where the supply's tracking mode means a per-channel setpoint would be accepted and silently discarded by the hardware, the system shall refuse the write rather than perform it. | T |
| TB-SYS2-024 | The system shall be able to bring the supply to a known safe state — outputs off, setpoints at zero — and that state shall be reachable whatever mode the supply is in. | T |
| TB-SYS2-025 | The system shall not present the supply's fixed, front-panel-switched auxiliary rail as a controllable channel. | I |

> TB-SYS2-023 is the treatment of TB-RISK-008. The GPD-3303D accepts CH2
> setpoints in series and parallel tracking and discards them; a bench that
> reported the write as successful would let an engineer believe a rail was set
> when it was not.

---

## 8. Target Control and Observation

| ID | Requirement | Method |
|---|---|---|
| TB-SYS2-030 | The system shall programme a target's flash from an image file through the debug probe, and verify what was programmed against that image. | T |
| TB-SYS2-031 | The system shall run, halt, reset and single-step the target, and set and clear breakpoints. | T |
| TB-SYS2-032 | The system shall read and write target memory, at a stated address, width and byte order, and shall refuse a width or byte order it cannot honour. | T |
| TB-SYS2-033 | The system shall read named variables and the call stack from the target. | T |
| TB-SYS2-034 | The system shall read and write the target's RTT channels, and shall be able to log RTT output to a file for the duration of a run. | T |
| TB-SYS2-035 | The system shall measure elapsed time between points in target execution, and shall report the resolution of the method used. | T |
| TB-SYS2-036 | Every firmware image the system programmes shall be accompanied by a manifest stating its version and build date, and the system shall be able to compare the version a running target reports against that manifest. | T |

---

## 9. Wireless Interfaces

| ID | Requirement | Method |
|---|---|---|
| TB-SYS2-040 | The system shall scan for BLE devices and report, for each, its address, name and advertising data. | T |
| TB-SYS2-041 | The system shall connect to a selected BLE device, exchange command/response traffic over a UART service, and disconnect. | T |
| TB-SYS2-042 | The system shall measure the time from the end of a transmitted command to the start of the response. | T |
| TB-SYS2-043 | Response timing shall be measured in the dongle, not inferred from host timestamps; host timestamps shall be retained alongside. | T |
| TB-SYS2-044 | The system shall log a BLE session — commands, responses and their times — to a file. | T |
| TB-SYS2-045 | The system shall select a target by an identifier read from the target's own memory, matching it against the identifier carried in the advertising name. | T |
| TB-SYS2-046 | The system shall programme, read and write every register of the S2-LP transceiver, transmit and receive over the sub-GHz link, and log all data exchanged. | T |
| TB-SYS2-047 | The system shall use the vendor's own firmware for the S2-LP kit; that firmware's command set is an external interface and is not modified. | I |
| TB-SYS2-051 | The system shall measure voltage, current, resistance and frequency with a TTi 1604 bench multimeter over RS-232, reporting every value in SI units. | T |
| TB-SYS2-052 | The system shall report a multimeter reading taken from a frozen display as held, so that a stored value is not recorded as a present measurement. | T |
| TB-SYS2-053 | The system shall report a multimeter overrange as an overrange rather than as a number. | T |

### 9.1 Target Identity

| ID | Requirement | Method |
|---|---|---|
| TB-SYS2-048 | The system shall read the target's sensor identifier from UICR `CUSTOMER[0]` at address 0x10001080: a validity byte, which is zero for a valid identifier, followed by three identifier bytes in address order. | T |
| TB-SYS2-049 | The system shall treat a non-zero validity byte as an invalid identifier and shall not use the following bytes as one. | T |
| TB-SYS2-050 | The system shall render a valid sensor identifier as six uppercase hexadecimal digits, as it appears in the advertising name. | T |

---

## 10. Measurement

| ID | Requirement | Method |
|---|---|---|
| TB-SYS2-060 | The system shall configure oscilloscope channels — enable, vertical scale, position — and the timebase and trigger. | T |
| TB-SYS2-061 | The system shall arm the instrument, capture an acquisition, and retrieve the waveform records. | T |
| TB-SYS2-062 | The system shall measure quantities from a captured record, including period, frequency, edge times, and the spread in time between several channels reaching a threshold. | T |
| TB-SYS2-063 | Analysis of captured records shall be performed on the host from the captured data, so that the same record analysed twice yields the same result. | T |
| TB-SYS2-064 | Every measurement the system reports shall carry its units and, where the method bounds it, its resolution. | T |

---

## 11. Test Definition, Execution and Evidence

| ID | Requirement | Method |
|---|---|---|
| TB-SYS2-070 | A bench test shall be expressible as data — a specification file — separately from the description of the bench it runs on, so the same test runs on different benches. | T |
| TB-SYS2-071 | A specification shall be able to carry a value obtained in one step into a later step, rather than requiring it to be restated. | T |
| TB-SYS2-072 | A specification shall be able to express an expectation as a limit, a tolerance, or an exact text, and shall state which. | T |
| TB-SYS2-073 | The system shall support a command/response test written as a table in a markdown document, where that document is simultaneously the specification of the command set and the test of it. | T |
| TB-SYS2-074 | In such a document a step may be a delay, or a command with no stated expectation; both shall be recorded and reported as skipped, not as passed. | T |
| TB-SYS2-075 | A run shall pass if no step failed, and fail otherwise. | T |
| TB-SYS2-076 | The system shall record, for every step: the test, the step number, what was sent, what was received, what was expected, the elapsed time, and the result. | T |
| TB-SYS2-077 | Elapsed times in a command/response report shall be reported at 10 ms resolution, with the underlying higher-resolution measurement retained. | T |
| TB-SYS2-078 | A report shall name the specification and the bench it ran against, and shall be written to a file. | T |
| TB-SYS2-079 | The system shall produce machine-readable results suitable for a CI system to consume. | T |

---

## 12. Non-Functional Requirements

| ID | Requirement | Method |
|---|---|---|
| TB-SYS2-090 | The host software shall run on Windows and on Linux, and the whole bench shall be capable of running inside a container where the instrument links are network links. | A |
| TB-SYS2-091 | The dongle firmware shall build from a clean checkout in continuous integration, and its flash and RAM usage shall be recorded. | T |
| TB-SYS2-092 | C source in this project shall conform to TB-STD-002 and TB-STY-001, checked mechanically on every push. | T |
| TB-SYS2-093 | No vendor-supplied source or documentation text shall be incorporated into this repository; vendor devices shall be described by independently recorded facts. | I |
| TB-SYS2-094 | The system shall fail loudly on a request it cannot satisfy, with a message naming what was asked and why it could not be done. | T |
| TB-SYS2-095 | Every system requirement in this document shall be traceable to at least one software requirement or firmware element, and to at least one test. | A |

---

## 13. Assumptions and Constraints

| ID | Statement |
|---|---|
| TB-SYS2-100 | The bench is operated by an engineer who is present; the system is not designed for unattended operation with live instruments. |
| TB-SYS2-101 | Instrument accuracy is the manufacturer's specification. TestBench does not improve it and does not restate it. |
| TB-SYS2-102 | TestBench is a test tool. It carries no ASIL classification and is not part of any delivered product. |
| TB-SYS2-103 | The S2-LP kit runs ST's firmware under SLA0072; see TB-ACQ4-001 §4.2. |
| TB-SYS2-104 | The multimeter interface (STK-18) is implemented for the TTi 1604 (TB-SYS2-051…053). Its protocol is taken from cited documentation; no behaviour has been confirmed against a physical meter — see `docs/dmm/TTi1604_Notes.md` §5. |

---

## 14. Traceability

Upward to the stakeholder requirements in TB-SWE1-001 §4, downward to the
software requirements in TB-SWE1-001 §6–§15. The full matrix is TB-RTM-001.

| Stakeholder | System requirements |
|---|---|
| STK-01…STK-05 | TB-SYS2-060…TB-SYS2-064 |
| STK-06 | TB-SYS2-090 |
| STK-07 | TB-SYS2-011, TB-SYS2-014 |
| STK-08 | TB-SYS2-070…TB-SYS2-079 |
| STK-09, STK-10 | TB-SYS2-030…TB-SYS2-036, TB-SYS2-002 |
| STK-11 | TB-SYS2-090 |
| STK-12 | TB-SYS2-073, TB-SYS2-074 |
| STK-13 | TB-SYS2-020…TB-SYS2-025 |
| STK-14, STK-15 | TB-SYS2-040…TB-SYS2-045 |
| STK-16 | TB-SYS2-091 |
| STK-17 | TB-SYS2-044 |
| STK-18 | TB-SYS2-051, TB-SYS2-052, TB-SYS2-053, TB-SYS2-104 |
| STK-19, STK-20 | TB-SYS2-046, TB-SYS2-047, TB-SYS2-103 |

| System requirement group | Software requirements |
|---|---|
| Bench composition §6 | `CORE-FR-*`, `INST-FR-*` |
| Power §7 | `PSU-FR-*`, `PSU-NFR-*` |
| Target control §8 | `JLINK-FR-*`, `JLINK-NFR-*` |
| Wireless §9 | `BLE-FR-*`, `BLE-NFR-*`, `S2LP-FR-*`, `S2LP-NFR-*` |
| Measurement §10 | `SCOPE-FR-*`, `ANA-FR-*` |
| Test definition §11 | `RUN-FR-*` |
| Non-functional §12 | `CORE-NFR-*`, TB-STD-002, TB-STY-001 |

---

## 15. Review & Approval

| Role | Name | Signature / Electronic Approval | Date |
|---|---|---|---|
| Author | Claude | Approved | 2026-09-19 |
| Reviewer | Dermot Murphy | — | *pending* |
| Approver | Dermot Murphy | — | *pending* |
