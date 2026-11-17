<img src="../../assets/brand/svg/logos/embeddedtestbench-logo-compact.svg" alt="Embedded Test Bench" width="240">

# System Integration & Integration Test

*Automotive SPICE® PAM v4.0 | SYS.4 — System Integration and Integration Test*

---

## 1. Document Identification & Control

| Field | Value | Field | Value |
|---|---|---|---|---|---|---|---|
| **Document ID** | ETB-SYS4-001 | **Version** | [latest, §2](#2-revision-history) |
| **Project** | Embedded Test Bench | **Date** | [latest, §2](#2-revision-history) |
| **Status** | [by location, ETB-SUP1-001 §6.3](EmbeddedTestBench_SUP1_Quality_Assurance_Plan.md#63-document-status) | **Classification** | Internal |
| **Author** | Claude | **Reviewer** | Dermot Murphy |
| **Approver** | Dermot Murphy | **Related Process** | SYS.4 |

> Reviewer and Approver are the same person; see ETB-DEV-002.

---

## 2. Revision History

| Version | Date | Author | Description of Change |
|---|---|---|---|---|---|---|---|
| 0.1 | 2026-09-19 | Claude | Initial |
| 0.2 | 2026-09-26 | Claude | TB-SIT-03 and -04: informal bench evidence recorded against each; neither is yet executed on TB-TMPL-002 (#63). TB-SIT-03: operator confirmed all ten front-panel steps. |
| 0.3 | 2026-10-04 | Claude | #183: product renamed to Embedded Test Bench - document file name prefix `EmbeddedTestBench_`, identifier prefix `ETB-` (was `TB-`), product name in prose. Earlier revision rows keep the names in use when they were written. |
| 0.4 | 2026-10-05 | Claude | #204: Review & Approval table points to the merge of the pull request that last changed the document, which is the review and approval (ETB-SUP8-001 §5.7); no per-change signatures or dates. |
| 0.5 | 2026-10-05 | Claude | #194: the compact brand logo added above the title, the same line in every controlled document (ETB-SUP8-001 §6.3). |
| 0.6 | 2026-10-25 | Claude | #210: Version and Date in the identification table are links to the last revision history row, which holds them (ETB-SUP8-001 §6.2). |
| next | 2026-11-17 | Claude | #371: the Status cell links to the status rule, ETB-SUP1-001 §6.3. A document's status follows from where it is in the repository (Released, Agreed, In review, In work) and is not written in by hand. |
| next | 2026-11-17 | Claude | #377: Referenced Documents cite each controlled document at the version of its last numbered revision row, kept by `scripts/doc_versions.py` (ETB-SUP8-001 §6.2). |
| next | 2026-11-17 | Claude | #362: §3.3 covers ETB-SIF-01 to -19. §5 - each case traces to its system elements and requirements, states its resources and its status at `v0.03.0000`, and the evidence other bench runs give; ETB-SIT-17 to -24 added for the PicoScope, PPK2, TTi 1604, PICO2 Test Board, serial capture and the S2-LP kit firmware. §5.1 restated: the bench has been assembled; performing the cases is deferred by ETB-DEV-004. §5.2 adds the selection and regression rule. §6 E3 and E4 are met. §8 adds the integration report for `v0.03.0000`; Review & Approval is now §9. |

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
| ETB-SYS2-001 | Embedded Test Bench System Requirements Specification | 0.10 |
| ETB-SYS3-001 | Embedded Test Bench System Architecture | 0.8 |
| ETB-SYS5-001 | Embedded Test Bench System Qualification Test | 0.7 |
| ETB-SWE5-001 | Embedded Test Bench Software Integration & Integration Test | 0.5 |
| ETB-TMPL-002 | Embedded Test Bench Test Case Specification — Template | 0.5 |
| ETB-SUP9-001 | Embedded Test Bench Problem Resolution Management Plan | 0.5 |

### 3.3 Scope

The interfaces ETB-SIF-01 … ETB-SIF-19 of ETB-SYS3-001 §6, and the assembly of the
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
Each case traces up to the system elements either side of its interface and to
the system requirements it supports; ETB-RTM-001, section "System Requirements to Integration Cases", holds the reverse trace.
The resources are the instruments the case needs and its estimated bench time,
planned in ETB-MAN3-001 §8.1.

| ID | Interface | What must be shown | Elements (ETB-SYS3-001) | Requirements (ETB-SYS2-001) | Resources | Status at `v0.03.0000` | Evidence from other bench runs |
|---|---|---|---|---|---|---|---|
| ETB-SIT-01 | ETB-SIF-01 | The scope answers the portmapper and accepts a VXI-11 link; its identity string is read; a configuration command takes effect on the front panel | SE-HOST, SE-SCOPE | ETB-SYS2-010, -060 | TDS3014B on the bench network; 15 min | Not performed as an integration case (ETB-DEV-004) | None: the oscilloscope has not been on the bench (ETB-SYS5-002 §3.3) |
| ETB-SIT-02 | ETB-SIF-01 | A capture retrieved over VXI-11 matches what the instrument displays, in scale and in record length | SE-HOST, SE-SCOPE | ETB-SYS2-061, -064 | TDS3014B and a signal; 20 min | Not performed as an integration case (ETB-DEV-004) | None, as ETB-SIT-01 |
| ETB-SIT-03 | ETB-SIF-02 | The supply answers on its serial port at the configured rate, reports its identity, and accepts a setpoint that the front panel then shows | SE-HOST, SE-PSU | ETB-SYS2-010, -015, -020, -021 | GPD-3303D; 15 min | Not performed as an integration case (ETB-DEV-004) | QS-03 and QS-10 (2026-10-04) opened, identified and set the supply |
| ETB-SIT-04 | ETB-SIF-02 | The `STATUS?` reply decodes as the driver expects — bit order and tracking bits (PSU-OPEN-01, PSU-OPEN-06) | SE-HOST, SE-PSU | ETB-SYS2-022 | GPD-3303D; 15 min | Not performed as an integration case (ETB-DEV-004) | QS-03 read the status word in independent mode |
| ETB-SIT-05 | ETB-SIF-02, ETB-SIF-09 | With the supply tracking, a per-channel write is refused by the driver, and the supply's own behaviour on such a write is observed and recorded (PSU-OPEN-05) | SE-PSU, SE-TARGET | ETB-SYS2-023, -024 | GPD-3303D, no target wired (tracking is refused with a target wired, User Manual §8); 20 min | Not performed as an integration case (ETB-DEV-004) | QS-06b refusals; tracking with the supply's own behaviour observed is not done |
| ETB-SIT-06 | ETB-SIF-03 | The J-Link GDB server accepts a connection and the driver's MI exchanges behave as parsed against a real server version (JLINK-OPEN-01, JLINK-OPEN-02) | SE-HOST, SE-PROBE | ETB-SYS2-030 to -035 | J-Link and target (5C1712); 15 min | Not performed as an integration case (ETB-DEV-004) | QS-01 and QS-01b; JLINK-OPEN-01 and -02 closed (ETB-SYS5-002 §9) |
| ETB-SIT-07 | ETB-SIF-03, ETB-SIF-08 | An image is programmed and verifies; run, halt, breakpoint and step behave as specified | SE-PROBE, SE-TARGET | ETB-SYS2-030, -031, -036 | J-Link and target; 30 min | Not performed as an integration case (ETB-DEV-004) | QS-01 (flash and verify) and QS-01b (run, halt, breakpoint, step) |
| ETB-SIT-08 | ETB-SIF-08 | UICR 0x10001080 reads back the validity byte and three identifier bytes in address order on a real part | SE-PROBE, SE-TARGET | ETB-SYS2-048 to -050 | J-Link and target; 10 min | Not performed as an integration case (ETB-DEV-004) | QS-01: UICR identifier 5C1712 read, erased and restored |
| ETB-SIT-09 | ETB-SIF-04 | RTT output is read from a running target and logged for the duration of a run | SE-PROBE, SE-TARGET | ETB-SYS2-034 | J-Link and target; 10 min | Not performed as an integration case (ETB-DEV-004) | QS-01: RTT lines within 20 s of reset |
| ETB-SIT-10 | ETB-SIF-05 | The dongle enumerates, runs this project's firmware, and answers the host protocol; flash and RAM figures match the CI build | SE-HOST, SE-DONGLE | ETB-SYS2-040, -041, -091 | nRF52840 dongle; 10 min | Not performed as an integration case (ETB-DEV-004) | QS-01, QS-02 and the runs in ETB-SWE4-002 §10.5 to §10.8 |
| ETB-SIT-11 | ETB-SIF-05 | Dongle-side timestamps and host timestamps are both present, and their difference is what the transport plausibly explains | SE-HOST, SE-DONGLE | ETB-SYS2-042, -043 | Dongle and a sensor; 20 min | Not performed as an integration case (ETB-DEV-004) | QS-02 recorded both timestamps; their difference was not analysed against the transport |
| ETB-SIT-12 | ETB-SIF-07 | A real target's advertising name carries the identifier read at ETB-SIT-08, and the dongle connects to it | SE-DONGLE, SE-TARGET | ETB-SYS2-045, -048 to -050 | Dongle, J-Link and target; 15 min | Not performed as an integration case (ETB-DEV-004) | QS-01: the board advertising `KAPPA_5C1712_...` was found by the UICR identifier |
| ETB-SIT-13 | ETB-SIF-07 | `rd version` over BLE returns the version in the manifest of the image programmed at ETB-SIT-07 | SE-DONGLE, SE-TARGET | ETB-SYS2-036, -041 | Dongle and target; 10 min | Not performed as an integration case (ETB-DEV-004) | QS-01: `RD VERSION` over BLE equalled the manifest |
| ETB-SIT-14 | ETB-SIF-06 | The S2-LP kit's firmware replies as the driver parses them; register reads match the documented reset values (S2LP-OPEN-01…05) | SE-HOST, SE-S2LP | ETB-SYS2-046, -047 | S2-LP kit on ST's firmware; 20 min | Not performed as an integration case (ETB-DEV-004) | QS-07 |
| ETB-SIT-15 | ETB-SIF-10 | Scope measurements of a target signal agree with the same signal measured through the probe's timing methods, within the stated resolutions | SE-SCOPE, SE-PROBE, SE-TARGET | ETB-SYS2-035, -062 | TDS3014B, J-Link and target; 45 min | Not performed as an integration case (ETB-DEV-004) | None, as ETB-SIT-01 |
| ETB-SIT-16 | ETB-SIF-11 | A CI run consumes the machine-readable results of a hardware run | SE-HOST, CI | ETB-SYS2-079 | A hardware run's JUnit and the CI workflow; 20 min | Not performed as an integration case (ETB-DEV-004) | None |
| ETB-SIT-17 | ETB-SIF-12 | The PicoScope opens through `ps3000a`, reports its variant and serial, and a capture's ranges and timebase are those the driver set | SE-HOST, SE-PSCOPE | ETB-SYS2-010, -065 | PicoScope 3405D; 20 min | Not performed as an integration case (ETB-DEV-004) | The #200 bench check of 2026-11-13 (ETB-SWE1-001 CON-11) |
| ETB-SIT-18 | ETB-SIF-13 | One acquisition holds analogue and logic records of the same target signal on one time base, and the signal generator drives the stated stimulus | SE-PSCOPE, SE-TARGET | ETB-SYS2-065 | PicoScope, PICO2 Test Board as the source; 30 min | Not performed as an integration case (ETB-DEV-004) | Partly: channel A wired to the PICO2 Test Board (ETB-SYS3-001 ETB-SIF-13) |
| ETB-SIT-19 | ETB-SIF-14 | The PPK2 is found by its USB serial number, reports its metadata, and streams 100 000 samples a second without loss | SE-HOST, SE-PPK | ETB-SYS2-010, -026 | PPK2; 15 min | Not performed as an integration case (ETB-DEV-004) | The #342 bench check of 2026-11-14, nothing wired (CON-12) |
| ETB-SIT-20 | ETB-SIF-15 | Supplying a target, and in its supply line, the PPK2 measures the current of a known load within the kit's accuracy | SE-PPK, SE-TARGET | ETB-SYS2-026 | PPK2 and a known load; 45 min | Not performed as an integration case (ETB-DEV-004) | None (#344) |
| ETB-SIT-21 | ETB-SIF-16 | The TTi 1604's stream is decoded, a key press is confirmed from the readings, and an overrange is reported as one | SE-HOST, SE-DMM | ETB-SYS2-051 to -053 | TTi 1604; 30 min | Not performed as an integration case (ETB-DEV-004) | QS-09 (2026-10-04) and the #181 findings (2026-10-28) |
| ETB-SIT-22 | ETB-SIF-17 | The PICO2 Test Board answers its protocol, reports its identity, and its sensor, LEDs and generator do what the commands set | SE-HOST, SE-PICO2 | ETB-SYS2-017 | PICO2 Test Board; 20 min | Not performed as an integration case (ETB-DEV-004) | CON-09: run on a real Pico 2 since 2026-10-03 |
| ETB-SIT-23 | ETB-SIF-18 | A target's serial output is captured through the adapter, every line recorded, and nothing written to the port | SE-TARGET, SE-SERIAL, SE-HOST | ETB-SYS2-037 | USB serial adapter on a target UART; 15 min | Not performed as an integration case (ETB-DEV-004) | The #247 bench run (ETB-SWE1-001 §16) |
| ETB-SIT-24 | ETB-SIF-19 | The S2-LP kit on the project's own firmware identifies itself, receives on the interrupt and reports its deaf time | SE-HOST, SE-S2LP | ETB-SYS2-046, -047 | S2-LP kit with the kit firmware; 20 min | Not performed as an integration case (ETB-DEV-004) | The #84 bench run of 2026-11-14 (`docs/aspice/qualification/2026-11-14/84_kit_firmware/`) |

### 5.1 Why the Status Column Says What It Says

No case has been performed as an integration case: that execution is deferred
to `v0.05.0000` by the owner's decision, recorded as ETB-DEV-004. The bench has
been assembled with hardware, though. The qualification campaign of 2026-10-04
(ETB-SYS5-002) and the bench runs since then exercised much of what the cases
must show, and the last column says where. That evidence is not the case
performed: it was gathered for another purpose, against another record. When a
case is performed, its row is updated and the execution record filed under
ETB-TMPL-002 §5.

### 5.2 Selection and Regression (SYS.4.BP2)

| When | Cases selected |
|---|---|
| First integration of an interface | Every case on that interface |
| A release | Every case whose interface, driver or instrument changed since the previous release, by the release's diff; and every case not yet performed |
| A new instrument firmware revision (ETB-RISK-002) | Every case on that instrument's interfaces |
| A change to a system element's simulator only | None: that is ETB-SWE5-001's |

The selection for each release is stated in its integration report (§9).

---

## 6. Entry and Exit Criteria

**Entry to hardware integration:**

| # | Criterion | State |
|---|---|---|
| E1 | The software configuration passes integration against simulators | Met — ETB-SWE5-001 §9 |
| E2 | The firmware builds and fits | Met — ETB-SWE4-002 §4.6 |
| E3 | The instruments are available, with their model, serial and firmware revision recorded | Met for every instrument but the TDS3014B: each run records the identities (QS-10, 2026-10-04; CON-09 to CON-12) |
| E4 | A safe power-up procedure for the target is agreed | Met: `docs/User_Manual.md` §8, and the supply limits with a sensor wired |

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

## 8. Integration Reports

### 8.1 Release `v0.03.0000` (#362, 2026-11-17)

| Item | Result |
|---|---|
| Cases selected | All 24: none had been performed (§5.2) |
| Cases performed as integration cases | 0. Deferred to `v0.05.0000` by the owner's decision of 2026-11-17 (ETB-DEV-004) |
| Cases with evidence from other bench runs | 17 of 24 (the last column of §5) |
| Cases with no hardware evidence at all | ETB-SIT-01, -02, -15 (TDS3014B not on the bench); ETB-SIT-16 (CI consuming hardware results); ETB-SIT-20 (PPK2 against a known load, #344) |
| Problems raised by integration | None, since no case was performed. The problems found by the other bench runs are in ETB-SUP9-001 §9.1 |
| Exit criteria (§6) | Not met |

---

## 9. Review & Approval

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
