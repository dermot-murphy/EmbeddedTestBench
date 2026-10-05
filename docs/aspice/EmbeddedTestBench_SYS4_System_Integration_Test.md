# System Integration & Integration Test

*Automotive SPICE® PAM v4.0 | SYS.4 — System Integration and Integration Test*

---

## 1. Document Identification & Control

| Field | Value | Field | Value |
|---|---|---|---|
| **Document ID** | ETB-SYS4-001 | **Version** | 0.4 |
| **Project** | Embedded Test Bench | **Date** | 2026-10-05 |
| **Status** | Draft | **Classification** | Internal |
| **Author** | Claude | **Reviewer** | Dermot Murphy |
| **Approver** | Dermot Murphy | **Related Process** | SYS.4 |

> Reviewer and Approver are the same person; see ETB-DEV-002.

---

## 2. Revision History

| Version | Date | Author | Description of Change |
|---|---|---|---|
| 0.1 | 2026-09-19 | Claude | Initial |
| 0.2 | 2026-09-26 | Claude | TB-SIT-03 and -04: informal bench evidence recorded against each; neither is yet executed on TB-TMPL-002 (#63). TB-SIT-03: operator confirmed all ten front-panel steps. |
| 0.3 | 2026-10-04 | Claude | #183: product renamed to Embedded Test Bench - document file name prefix `EmbeddedTestBench_`, identifier prefix `ETB-` (was `TB-`), product name in prose. Earlier revision rows keep the names in use when they were written. |
| 0.4 | 2026-10-05 | Claude | #204: Review & Approval table points to the merge of the pull request that last changed the document, which is the review and approval (ETB-SUP8-001 §5.7); no per-change signatures or dates. |

---

## 3. Purpose & Scope

### 3.1 Purpose

This document says how the system elements of ETB-SYS3-001 are assembled into a
working bench, and how each interface between them is shown to work.

It is the document where the distinction this project cares most about is
drawn: software that fits together (ETB-SWE5-001) is not the same as software
that fits the **instrument**. Everything below is about the second.

### 3.2 Referenced Documents

| Document ID | Title | Version |
|---|---|---|
| ETB-SYS2-001 | Embedded Test Bench System Requirements Specification | 0.1 |
| ETB-SYS3-001 | Embedded Test Bench System Architecture | 0.1 |
| ETB-SYS5-001 | Embedded Test Bench System Qualification Test | 0.1 |
| ETB-SWE5-001 | Embedded Test Bench Software Integration & Integration Test | 0.1 |
| ETB-TMPL-002 | Embedded Test Bench Test Case Specification — Template | 0.1 |
| ETB-SUP9-001 | Embedded Test Bench Problem Resolution Management Plan | 0.1 |

### 3.3 Scope

The interfaces ETB-SIF-01 … ETB-SIF-11 of ETB-SYS3-001 §6, and the assembly of the
elements either side of them.

---

## 4. Integration Strategy

Integration proceeds outward from the host, one interface at a time, because an
interface that is brought up alongside another cannot be diagnosed when it
misbehaves.

| Stage | Assembled | Confirms |
|---|---|---|
| S1 | Host + simulated bench | The software configuration is complete and runs end to end (ETB-SWE5-001) |
| S2 | Host + one real instrument, per instrument | That instrument's transport, identity query, and command set as the driver understands it |
| S3 | Host + probe + target | Programming, verification, run control, memory and RTT against real silicon |
| S4 | Host + dongle firmware on real dongle | The dongle protocol over real USB, and dongle-side timestamping |
| S5 | Dongle + target over BLE | Advertising, name matching, connection, command/response |
| S6 | Supply + target | Powering the target, and the tracking-mode refusal against the real supply |
| S7 | Scope + target | Capture and analysis of real signals |
| S8 | Whole bench | A complete bring-up specification, hardware throughout |

Each stage is entered only when the previous one has been recorded as passed.
A stage that is skipped is recorded as skipped; it is not implied to have passed
by the success of a later one.

---

## 5. Integration Test Cases

Each case is performed on the form in ETB-TMPL-002 and its execution recorded
there. The table states what must be shown; it does not state that it has been.

| ID | Interface | What must be shown | Status |
|---|---|---|---|
| ETB-SIT-01 | ETB-SIF-01 | The scope answers the portmapper and accepts a VXI-11 link; its identity string is read; a configuration command takes effect on the front panel | **Not performed** |
| ETB-SIT-02 | ETB-SIF-01 | A capture retrieved over VXI-11 matches what the instrument displays, in scale and in record length | **Not performed** |
| ETB-SIT-03 | ETB-SIF-02 | The supply answers on its serial port at the configured rate, reports its identity, and accepts a setpoint that the front panel then shows | **Not performed** formally. Informal evidence 2026-09-26: answers at 9600, identity read, setpoints read back (ETB-IF-001 Annex A). Front panel observed during a timed run of `examples/10_psu_front_panel_check.py` for CH1: output voltages matched the remote read-back (3.2 V, 1.7 V), and a parked channel fell to 0 V in 2–3 s. The operator confirmed every other step as expected, including the settings shown with the output off, the OUTPUT indicator, and the reset to 0 V. |
| ETB-SIT-04 | ETB-SIF-02 | The `STATUS?` reply decodes as the driver expects — bit order and tracking bits (PSU-OPEN-01, PSU-OPEN-06) | **Not performed** formally. Informal evidence 2026-09-26: bit order and independent tracking confirmed, after the decode was corrected (#61); series and parallel not observed |
| ETB-SIT-05 | ETB-SIF-02, ETB-SIF-09 | With the supply tracking, a per-channel write is refused by the driver, and the supply's own behaviour on such a write is observed and recorded (PSU-OPEN-05) | **Not performed** |
| ETB-SIT-06 | ETB-SIF-03 | The J-Link GDB server accepts a connection and the driver's MI exchanges behave as parsed against a real server version (JLINK-OPEN-01, JLINK-OPEN-02) | **Not performed** |
| ETB-SIT-07 | ETB-SIF-03, ETB-SIF-08 | An image is programmed and verifies; run, halt, breakpoint and step behave as specified | **Not performed** |
| ETB-SIT-08 | ETB-SIF-08 | UICR 0x10001080 reads back the validity byte and three identifier bytes in address order on a real part | **Not performed** |
| ETB-SIT-09 | ETB-SIF-04 | RTT output is read from a running target and logged for the duration of a run | **Not performed** |
| ETB-SIT-10 | ETB-SIF-05 | The dongle enumerates, runs this project's firmware, and answers the host protocol; flash and RAM figures match the CI build | **Partially** — the build and its figures are confirmed in CI (BLE-OPEN-01 discharged); nothing has run on silicon (BLE-OPEN-02…04) |
| ETB-SIT-11 | ETB-SIF-05 | Dongle-side timestamps and host timestamps are both present, and their difference is what the transport plausibly explains | **Not performed** |
| ETB-SIT-12 | ETB-SIF-07 | A real target's advertising name carries the identifier read at ETB-SIT-08, and the dongle connects to it | **Not performed** |
| ETB-SIT-13 | ETB-SIF-07 | `rd version` over BLE returns the version in the manifest of the image programmed at ETB-SIT-07 | **Not performed** |
| ETB-SIT-14 | ETB-SIF-06 | The S2-LP kit's firmware replies as the driver parses them; register reads match the documented reset values (S2LP-OPEN-01…05) | **Not performed** |
| ETB-SIT-15 | ETB-SIF-10 | Scope measurements of a target signal agree with the same signal measured through the probe's timing methods, within the stated resolutions | **Not performed** |
| ETB-SIT-16 | ETB-SIF-11 | A CI run consumes the machine-readable results of a hardware run | **Not performed** |

### 5.1 Why the Status Column Says What It Says

This bench has not been assembled with hardware. Recording sixteen "not
performed" rows is the point of the table: it makes the gap between what
Embedded Test Bench is shown to do and what it is claimed to do visible at a glance, in
the document whose job is that gap. When a case is performed, its row is updated
and the execution record filed under ETB-TMPL-002 §5.

---

## 6. Entry and Exit Criteria

**Entry to hardware integration:**

| # | Criterion | State |
|---|---|---|
| E1 | The software configuration passes integration against simulators | Met — ETB-SWE5-001 §9 |
| E2 | The firmware builds and fits | Met — ETB-SWE4-002 §4.6 |
| E3 | The instruments are available, with their model, serial and firmware revision recorded | Not met |
| E4 | A safe power-up procedure for the target is agreed | Not met |

**Exit:** every case in §5 performed and passed, each with an execution record;
every element-level bench-confirmation item either closed by one of those cases
or explicitly carried forward into ETB-SYS5-001 §7.

---

## 7. Defect Handling

A failure at integration is a problem under ETB-SUP9-001. Where the failure is a
difference between the instrument and the simulator, **both** are corrected: the
driver so it works, and the simulator so that every future simulated run reflects
what the instrument really does. Correcting only the driver would leave the
suite asserting a behaviour the instrument does not have, which is ETB-RISK-007.

---

## 8. Review & Approval

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
