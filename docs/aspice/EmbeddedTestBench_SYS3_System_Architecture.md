# System Architecture

*Automotive SPICE® PAM v4.0 | SYS.3 — System Architectural Design*

---

## 1. Document Identification & Control

| Field | Value | Field | Value |
|---|---|---|---|
| **Document ID** | ETB-SYS3-001 | **Version** | 0.3 |
| **Project** | Embedded Test Bench | **Date** | 2026-10-04 |
| **Status** | Draft | **Classification** | Internal |
| **Author** | Claude | **Reviewer** | Dermot Murphy |
| **Approver** | Dermot Murphy | **Related Process** | SYS.3 |

> Reviewer and Approver are the same person; see ETB-DEV-002.

---

## 2. Revision History

| Version | Date | Author | Description of Change |
|---|---|---|---|
| 0.1 | 2026-09-19 | Claude | Initial |
| 0.2 | 2026-09-26 | Claude | TB-SIF-02 refers to its interface specification, TB-IF-001 (#63). |
| 0.3 | 2026-10-04 | Claude | #183: product renamed to Embedded Test Bench - document file name prefix `EmbeddedTestBench_`, identifier prefix `ETB-` (was `TB-`), product name in prose. Earlier revision rows keep the names in use when they were written. |

---

## 3. Purpose & Scope

### 3.1 Purpose

This document describes the Embedded Test Bench system as a set of physical and logical
elements and the interfaces between them, and allocates the system requirements
of ETB-SYS2-001 to those elements.

The software architecture — how `benchtools` is decomposed internally — is
ETB-SWE2-001. This document stops at the boundary of the host software and
describes what is on the other side of each wire.

### 3.2 Referenced Documents

| Document ID | Title | Version |
|---|---|---|
| ETB-SYS2-001 | Embedded Test Bench System Requirements Specification | 0.1 |
| ETB-SYS4-001 | Embedded Test Bench System Integration & Integration Test | 0.1 |
| ETB-SWE2-001 | Embedded Test Bench Software Architecture | 0.1 |
| ETB-SWE1-001 | Embedded Test Bench Software Requirements Specification | 0.1 |
| ETB-MAN5-001 | Embedded Test Bench Risk Management Plan | 0.1 |
| ETB-ACQ4-001 | Embedded Test Bench Supplier Monitoring Plan | 0.1 |

### 3.3 Scope

The bench host, the instruments, the transports between them, the firmware
Embedded Test Bench supplies, and the target under test as the bench sees it.

---

## 4. Architectural Drivers

| ID | Driver | Source | Consequence |
|---|---|---|---|
| ETB-SAD-01 | A result must be reproducible from what was recorded | ETB-SYS2-001 | Every element that can identify itself does so, and the identity is recorded per run |
| ETB-SAD-02 | The bench must run with no hardware attached | ETB-SYS2-012 | Every instrument element has a simulated counterpart behind the same interface |
| ETB-SAD-03 | The bench should containerise | ETB-SYS2-090 | Transports are network links where the instrument allows it; USB-bound elements are the ones that constrain this |
| ETB-SAD-04 | Timing must be attributable | ETB-SYS2-043, ETB-SYS2-077 | Measurement is done as close to the event as the hardware allows, and the method's resolution travels with the number |
| ETB-SAD-05 | A tool must not make a claim it cannot support | ETB-SYS2-003, ETB-SYS2-004, ETB-SYS2-016 | Failure and error are distinct; simulation is disclosed; unsatisfiable requests are refused |
| ETB-SAD-06 | No vendor source may be vendored | ETB-ACQ4-001 §4.2 | The S2-LP element is a host driver over a vendor firmware interface, not a firmware element |

---

## 5. System Elements

### 5.1 Physical Elements

| Element | What it is | Supplied by | Interface to the host |
|---|---|---|---|
| **SE-HOST** | The bench host — a PC or a container running `benchtools` | This project (software) | — |
| **SE-SCOPE** | Tektronix TDS3014B oscilloscope | Tektronix | Ethernet, VXI-11 |
| **SE-PSU** | GW Instek GPD-3303D bench supply | GW Instek | USB serial, 9600 8N1 |
| **SE-PROBE** | SEGGER J-Link debug probe | SEGGER | USB, presented as TCP: GDB server and RTT |
| **SE-DONGLE** | Nordic nRF52840 dongle (PCA10059) | Hardware: Nordic. Firmware: **this project** | USB serial (CDC ACM) |
| **SE-S2LP** | ST S2-LP development kit | Hardware and firmware: STMicroelectronics | USB serial |
| **SE-TARGET** | The device under test | The project being tested | Debug port (to SE-PROBE), BLE (to SE-DONGLE), power (from SE-PSU), signals (to SE-SCOPE) |

### 5.2 Logical Elements on the Host

| Element | Responsibility | Detailed in |
|---|---|---|
| **SE-CORE** | Transports, framing, validation, bench model, report writing, firmware manifests | ETB-SWE2-001 §5 |
| **SE-DRIVERS** | One driver per instrument, each with a simulator behind the same interface | ETB-SWE2-001 §6 |
| **SE-RUNNER** | Loads a specification and a bench, executes steps, evaluates expectations, writes reports | ETB-SWE2-001 §6 |
| **SE-ANALYSIS** | Measures quantities from captured records, on the host | ETB-SWE2-001 §6 |

### 5.3 The Dongle Is One Element in Two Halves

SE-DONGLE's firmware and its host driver are designed together and specified as
one element (`BLE-` in ETB-SWE1-001 §11). The protocol between them is a single
design decision; splitting it across two elements would let the halves drift
apart, and the timing requirement ETB-SYS2-043 — measure in the dongle, keep the
host's timestamps beside it — only makes sense if both halves are designed to
it at once.

The S2-LP element is deliberately **not** like this: its firmware is ST's
(ETB-SYS2-047), so the command set is an external interface that Embedded Test Bench
observes rather than defines.

---

## 6. Interfaces

| ID | Between | Medium | Protocol | Notes |
|---|---|---|---|---|
| ETB-SIF-01 | SE-HOST ↔ SE-SCOPE | Ethernet | VXI-11 / SCPI | Implemented directly; no VISA runtime required (ETB-SWE2-001 AD-01) |
| ETB-SIF-02 | SE-HOST ↔ SE-PSU | USB serial | GW Instek command set | Not SCPI; LF out, CR back; status word spaced and followed by a legend. Specified in ETB-IF-001 |
| ETB-SIF-03 | SE-HOST ↔ SE-PROBE (control) | TCP | GDB/MI to the J-Link GDB server | Network link, so this element containerises |
| ETB-SIF-04 | SE-HOST ↔ SE-PROBE (RTT) | TCP | J-Link RTT telnet channel | As above |
| ETB-SIF-05 | SE-HOST ↔ SE-DONGLE | USB serial | Embedded Test Bench dongle protocol — this project's own | Carries dongle-side timestamps (ETB-SYS2-043) |
| ETB-SIF-06 | SE-HOST ↔ SE-S2LP | USB serial | ST's firmware command set | External interface; observed, not defined here |
| ETB-SIF-07 | SE-DONGLE ↔ SE-TARGET | BLE | GAP advertising; UART service for command/response | Target identifier appears in the advertising name (ETB-SYS2-045) |
| ETB-SIF-08 | SE-PROBE ↔ SE-TARGET | SWD | Debug access, RTT control block in target RAM | |
| ETB-SIF-09 | SE-PSU ↔ SE-TARGET | Wires | Power | Tracking mode constrains what may be set (ETB-SYS2-023) |
| ETB-SIF-10 | SE-TARGET ↔ SE-SCOPE | Probes | Analogue signals | Up to four channels |
| ETB-SIF-11 | SE-HOST ↔ CI | Files | JUnit XML, markdown reports | ETB-SYS2-079 |

### 6.1 Containerisation

ETB-SAD-03 is satisfied for SE-SCOPE and SE-PROBE, whose links are TCP. SE-PSU,
SE-DONGLE and SE-S2LP are USB serial and require the device to be passed into
the container. This is a property of the instruments, not a decision, and is
recorded so that a reader does not expect otherwise.

---

## 7. Requirement Allocation

| System requirement | Allocated to |
|---|---|
| ETB-SYS2-001…004 | SE-CORE, SE-RUNNER |
| ETB-SYS2-010…016 | SE-CORE (bench model, identity recording, simulation disclosure), all drivers |
| ETB-SYS2-020…025 | SE-PSU driver, SE-PSU |
| ETB-SYS2-030…036 | SE-PROBE driver, SE-PROBE, SE-CORE (firmware manifests) |
| ETB-SYS2-040…045 | SE-DONGLE driver **and** SE-DONGLE firmware |
| ETB-SYS2-046, 047 | SE-S2LP driver |
| ETB-SYS2-048…050 | SE-PROBE driver (UICR read), SE-DONGLE driver (name matching) |
| ETB-SYS2-060…064 | SE-SCOPE driver, SE-ANALYSIS |
| ETB-SYS2-070…079 | SE-RUNNER, SE-CORE |
| ETB-SYS2-090 | SE-HOST, SE-CORE |
| ETB-SYS2-091, 092 | SE-DONGLE firmware, CI workflows |
| ETB-SYS2-093 | SE-S2LP driver, and every element by rule |
| ETB-SYS2-094, 095 | All elements |

---

## 8. Dynamic Behaviour

A bench specification run, at system level:

1. The host loads the bench description and the specification.
2. For each instrument the specification uses, the host opens the transport and
   queries the instrument's identity; identities are recorded. An instrument
   that is configured as simulated is noted as such.
3. The supply is set and enabled; if the supply's tracking mode forbids the
   write, the run errors here rather than proceeding on an unset rail.
4. The target is programmed through the probe from an image with a manifest, and
   verified against that image.
5. The target's identity is read from UICR and rendered as hex.
6. The target is started; RTT output confirms it is running and is logged for
   the rest of the run.
7. The dongle scans, matches the advertising name against the rendered
   identifier, and connects.
8. Command/response steps run; the dongle timestamps each response, the host
   keeps its own timestamps beside them.
9. Measurements from the scope, where the specification asks for them, are
   captured and analysed on the host.
10. The report is written: identities, simulation state, every step, every
    measurement with units and resolution, and the overall result.

Step 2 is where ETB-SAD-01 is discharged, and step 3 is where ETB-SAD-05 most
often bites.

---

## 9. Resource and Performance Characteristics

| Element | Characteristic | Value / source |
|---|---|---|
| SE-DONGLE firmware | Flash and RAM used | Recorded by the CI firmware build |
| SE-DONGLE | Response time resolution | Dongle-side timestamps; reported at 10 ms in command/response reports, finer value retained |
| SE-PROBE | Timing method resolution | Four methods, each reporting its own (ETB-SWE2-001 AD-14) |
| SE-PSU | Settling after a setpoint change | Bench-confirmation item; not asserted |
| SE-SCOPE | Acquisition completion | Polled, not inferred (ETB-SWE2-001 AD-07) |

---

## 10. Architectural Decisions at System Level

### SD-01 — The bench is described as data, separately from the test

A specification says what to do; a bench description says what to do it with.
The same specification therefore runs against the simulated bench in CI and
against real instruments on a desk, and the report says which it was. Merging
the two would have made every test carry its bench with it, and would have made
ETB-SYS2-012 impossible to satisfy honestly.

### SD-02 — Simulators model behaviour, not expectations

A simulator that returned what a test expected would pass every test and catch
no defect. Each simulator is written from the instrument's documentation and
models its state: the supply's tracking modes and its silent discard of CH2
setpoints, the dongle's advertising and connection states, the probe's halt and
run states. This is the architectural half of ETB-RISK-001's treatment; the
process half is the review check in ETB-TMPL-001 §6.4 T5.

### SD-03 — Measure where the event is

Response timing is taken in the dongle because the host's view is separated from
the radio by USB, scheduling and buffering. The host's timestamps are kept, not
discarded, so that a disagreement between the two is visible rather than hidden
by whichever was chosen.

### SD-04 — Identity is recorded, not assumed

Every instrument that can report a model, serial number or firmware revision is
asked at connection, and the answer goes into the report. This is what makes
ETB-RISK-002 detectable: a vendor firmware revision that changes a command's
meaning shows up as a revision nobody has seen before, rather than as a
measurement that quietly means something else.

### SD-05 — The S2-LP kit keeps the vendor's firmware

STK-20 asked for it, SLA0072 requires that no ST source be vendored, and the
kit's firmware already does what the bench needs. The consequence is accepted
deliberately: Embedded Test Bench does not control that command set and must track it as
an external interface (ETB-ACQ4-001 §5).

---

## 11. Review & Approval

| Role | Name | Signature / Electronic Approval | Date |
|---|---|---|---|
| Author | Claude | Approved | 2026-09-19 |
| Reviewer | Dermot Murphy | — | *pending* |
| Approver | Dermot Murphy | — | *pending* |
