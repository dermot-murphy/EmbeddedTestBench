<img src="../../assets/brand/svg/logos/embeddedtestbench-logo-compact.svg" alt="Embedded Test Bench" width="240">

# System Qualification Test

*Automotive SPICE® PAM v4.0 | SYS.5 — System Qualification Test*

---

## 1. Document Identification & Control

| Field | Value | Field | Value |
|---|---|---|---|
| **Document ID** | ETB-SYS5-001 | **Version** | [latest, §2](#2-revision-history) |
| **Project** | Embedded Test Bench | **Date** | [latest, §2](#2-revision-history) |
| **Status** | [by location, ETB-SUP1-001 §6.3](EmbeddedTestBench_SUP1_Quality_Assurance_Plan.md#63-document-status) | **Classification** | Internal |
| **Author** | Claude | **Reviewer** | Dermot Murphy |
| **Approver** | Dermot Murphy | **Related Process** | SYS.5 |

> Reviewer and Approver are the same person; see ETB-DEV-002.

---

## 2. Revision History

| Version | Date | Author | Description of Change |
|---|---|---|---|
| 0.1 | 2026-09-19 | Claude | Initial |
| 0.2 | 2026-09-23 | Claude | The multimeter replaces the deferred row in the bench-confirmation table, with open items DMM-OPEN-01…05. |
| 0.3 | 2026-10-04 | Claude | #176: first hardware campaign, reported in TB-SYS5-002. QS-01b, QS-09 and QS-10 added. §5.1 names the hardware specifications. §6 hardware column filled in. §7 and §8 updated from the results. |
| 0.4 | 2026-10-04 | Claude | #183: product renamed to Embedded Test Bench - document file name prefix `EmbeddedTestBench_`, identifier prefix `ETB-` (was `TB-`), product name in prose. Earlier revision rows keep the names in use when they were written. |
| 0.5 | 2026-10-05 | Claude | #204: Review & Approval table points to the merge of the pull request that last changed the document, which is the review and approval (ETB-SUP8-001 §5.7); no per-change signatures or dates. |
| 0.6 | 2026-10-05 | Claude | #194: the compact brand logo added above the title, the same line in every controlled document (ETB-SUP8-001 §6.3). |
| 0.7 | 2026-10-25 | Claude | #210: Version and Date in the identification table are links to the last revision history row, which holds them (ETB-SUP8-001 §6.2). |
| next | 2026-11-17 | Claude | #371: the Status cell links to the status rule, ETB-SUP1-001 §6.3. A document's status follows from where it is in the repository (Released, Agreed, In review, In work) and is not written in by hand. |
| next | 2026-11-17 | Claude | #377: Referenced Documents cite each controlled document at the version of its last numbered revision row, kept by `scripts/doc_versions.py` (ETB-SUP8-001 §6.2). |
| next | 2026-11-17 | Claude | #363: every system requirement is now named by a scenario. QS-01 adds -071 and -072; QS-02 adds -080 to -083; QS-08 adds -090. QS-11 (inspection: -013, -093, -095), QS-12 (PPK2, -026), QS-13 (serial capture, -037), QS-14 (PicoScope, -065) and QS-15 (PICO2 Test Board, -017) are added. QS-15 reads the temperature only: #131 removed humidity. §4.1 states the selection and regression rule. §8 records that the entry criterion was not met for the 2026-10-04 campaign. X2 counts against the 68 requirements. |

---

## 3. Purpose & Scope

### 3.1 Purpose

This document says how the assembled bench is shown to meet the system
requirements of ETB-SYS2-001, and records what remains to be shown.

### 3.2 Referenced Documents

| Document ID | Title | Version |
|---|---|---|
| ETB-SYS2-001 | Embedded Test Bench System Requirements Specification | 0.10 |
| ETB-SYS3-001 | Embedded Test Bench System Architecture | 0.8 |
| ETB-SYS4-001 | Embedded Test Bench System Integration & Integration Test | 0.6 |
| ETB-SWE6-001 | Embedded Test Bench Software Qualification Test | 0.7 |
| ETB-SWE4-002 | Embedded Test Bench Unit Verification Report | 1.87 |
| ETB-TMPL-002 | Embedded Test Bench Test Case Specification — Template | 0.5 |
| ETB-RTM-001 | Embedded Test Bench Traceability Matrix | 1.83 |
| ETB-SYS5-002 | Embedded Test Bench System Qualification Test Report | 1.4 |

### 3.3 Scope

The whole bench, operated as an engineer operates it, against the requirements
of ETB-SYS2-001.

---

## 4. Qualification Strategy

Qualification is a set of **end-to-end scenarios**, each one a thing an engineer
would actually do, run on the bench and recorded. A scenario qualifies several
requirements at once, because that is how they are used.

Each scenario is run in two configurations:

| Configuration | What it shows | What it cannot show |
|---|---|---|
| **Simulated** — every instrument simulated | That the scenario is expressible, that the software executes it, that the report is complete | Anything about instrument behaviour |
| **Hardware** — real instruments and a real target | That the bench measures what it claims to | — |

A requirement is **qualified** only by the hardware configuration. The simulated
run is a precondition for attempting the hardware one, not a substitute for it.
§6 therefore reports two columns, and they do not currently agree.

Every system requirement is named by at least one scenario, and the scenario
that qualifies each one is listed in ETB-RTM-001, section "System Requirements to Qualification Scenarios" (#363).

### 4.1 Selection and Regression (SYS.5.BP2)

| When | Scenarios selected |
|---|---|
| A release that makes the qualification claim (from `v0.05.0000`) | Every scenario, in the hardware configuration, against the requirements as they stand at that release |
| Any other release | Every scenario in the simulated configuration (through the suite); in hardware, every scenario whose requirements, elements or instruments changed since the last hardware campaign. Under ETB-DEV-004, `v0.04.0000` performs none in hardware |
| A requirement added or changed | The scenario that names it, and a new scenario where none can show it (ETB-SUP10-001 §5, step 2) |

The selection for a release is recorded in its qualification report
(ETB-SYS5-002 or its successor).

---

## 5. Qualification Scenarios

### QS-01 — Sensor bring-up, end to end

The scenario in `specs/sensor_bringup.yaml`: power the target at 3.2 V with a
500 mA limit; check the dongle and refresh its firmware if needed; programme the
sensor firmware through the probe; read the sensor identifier from UICR
0x10001080 and render it as hex; start the sensor; confirm from RTT that it is
running; scan for BLE devices; connect to the one whose advertising name carries
that identifier; send `rd version`; confirm the version matches the manifest of
the image that was programmed.

*Qualifies:* ETB-SYS2-001, -002, -004, -015, -020, -021, -030, -031, -034, -036,
-040, -041, -045, -048, -049, -050, -070, -071, -072, -076, -078. The
specification carries the identifier read in one step into the scan and the
selection (-071), and states each expectation as a limit, a tolerance or an exact
text (-072).

### QS-02 — BLE command set as a document

Run `specs/sensor_commands.md` through `specs/sensor_commands.yaml`: each
heading a test, each row a step, delays and unasserted commands recorded as
skipped, timings at 10 ms resolution with the finer value retained, overall
pass only if no step failed.

*Qualifies:* ETB-SYS2-003, -042, -043, -044, -073, -074, -075, -076, -077, -080,
-081, -082, -083. The document's steps take each result in the order -080 sets,
take the sensor as a parameter and connect to it (-081), set their own timeouts
(-082), and expect a disconnection after `WR MODE` (-083).

### QS-03 — The supply refuses what it cannot honour

With the supply in each tracking mode in turn, attempt a per-channel write;
observe that the driver refuses, and that the supply's own behaviour on such a
write is what the simulator models. Then reset to the safe state from each mode.

*Qualifies:* ETB-SYS2-022, -023, -024, -025.

### QS-04 — A measurement with the scope

Configure channels, timebase and trigger; capture; measure period and the spread
in time of several channels crossing a threshold; compare against the same
quantity measured through the probe's timing methods.

*Qualifies:* ETB-SYS2-060, -061, -062, -063, -064.

### QS-05 — Evidence is sufficient to reproduce the run

Take a report produced by QS-01 on hardware, hand it to someone who was not
present, and have them reproduce the run from it alone.

*Qualifies:* ETB-SYS2-001, -015, -016, -078, -079.

### QS-06 — The bench refuses rather than invents

Provoke, in turn: an instrument missing from the bench; a transport that stops
answering mid-exchange; an unsupported memory width; a firmware version that
disagrees with its manifest; a command that gets no reply. Each must produce an
error naming what was asked and why it failed, and none must produce a value.

*Qualifies:* ETB-SYS2-003, -004, -032, -036, -094.

### QS-07 — Sub-GHz link

Programme and read back every S2-LP register, transmit and receive over the
link, and confirm that all data exchanged is logged.

*Qualifies:* ETB-SYS2-046, -047.

### QS-08 — Build and standards

The firmware builds from a clean checkout in CI with its flash and RAM figures
recorded, and the C source passes the coding-standard check.

*Qualifies:* ETB-SYS2-090, -091, -092. CI runs the host software on Linux, and
the bench PC runs it on Windows; the container is ETB-DOCK-001 (-090, by
analysis).

### QS-01b — Debug control and firmware state

Added in 0.3. QS-01's image may have no symbols, and without them there are no
variables by name and no source breakpoints. This scenario programmes an image
whose ELF is available, then:
- halts, steps and breaks at `main`;
- reads the call stack and a named variable;
- times start-up from `SystemInit` to `main` on the cycle counter, stating the
  resolution;
- checks the reported version against the manifest.

*Qualifies:* ETB-SYS2-002, -030, -031, -033, -035, -036, -041.

### QS-09 — Multimeter

Added in 0.3; no earlier scenario covered the multimeter. Run the opt-in bench
test `tests/bench/tti1604` (DMM-FR-080) against the real meter with its inputs
open: the link and key echo, frame decoding, the reading rate, the function and
range tour, the frequency gate, an open input on ohms as overrange, and local
and remote. Wire the references the test names to cover DC volts, resistance,
current and frequency against known values.

*Qualifies:* ETB-SYS2-051, -052, -053.

### QS-10 — Bench identity

Added in 0.3. Read every instrument once without changing anything, so one
report records each instrument's model, serial number and firmware. Run the
same specification again on the simulated bench.

*Qualifies:* ETB-SYS2-010, -011, -012, -014, -015, -016, -070, -078, -079, -084.

### QS-11 — Inspection and analysis of the bench as built

Inspect the repository and the simulators for the requirements a run cannot
show: the simulators model behaviour, not replies (ETB-SYS2-013, against
ETB-TMPL-001 T5 and the simulators' state); no vendor source or documentation
text is in the repository (ETB-SYS2-093, against ETB-ACQ4-001 §4.2); every
system requirement traces to software requirements and to a test (ETB-SYS2-095,
by the traceability check and ETB-RTM-001).

*Qualifies:* ETB-SYS2-013, -093, -095.

### QS-12 — Current drawn by the target

Run `specs/ppk2.yaml` with the PPK2 supplying a known load, and in the line of
an outside supply: the average current over a window, the charge and the pulses,
against the load's known values; the voltage stays within the bench's
`voltage_limit`.

*Qualifies:* ETB-SYS2-026.

### QS-13 — A target's serial output

Run `specs/serial_capture.yaml` against a target printing on its UART through a
USB serial adapter: every line is recorded in the run's evidence, the capture
ends at the expected pattern or at the window, and nothing is written to the
port.

*Qualifies:* ETB-SYS2-037.

### QS-14 — Analogue and logic together

With the PicoScope, capture a target's analogue signal and its logic lines in one
acquisition, and relate a logic edge to the analogue waveform on the one time
base; drive a stated stimulus from the signal generator into the target and
capture it.

*Qualifies:* ETB-SYS2-065.

### QS-15 — The reference test board

Run `specs/pico2_test_board.yaml` against the PICO2 Test Board: its identity,
its temperature and humidity against a reference, its LEDs set and read back,
and its generator's frequency measured by the PicoScope.

*Qualifies:* ETB-SYS2-017.

### 5.1 Hardware specifications

The hardware configuration of each scenario is in `specs/qualification/`, run
against `benches/bench_pc.yaml`. `specs/qualification/README.md` is the
procedure, including the owner's limits on the supply while a sensor is wired
to it.

---

## 6. Results

The hardware column is from the 2026-10-04 campaign; ETB-SYS5-002 has the
details and the evidence.

| Scenario | Simulated | Hardware (ETB-SYS5-002) |
|---|---|---|
| QS-01 Sensor bring-up | **Pass** | **Pass**, with a workaround for #177 |
| QS-01b Debug control | Expressible; the simulated target has no such symbols | **Fail**, 12 of 13 measurements: #178 |
| QS-02 BLE command document | **Pass** | **Pass** |
| QS-03 Supply | **Pass** | **Pass**, independent tracking only, outputs off (owner's limits) |
| QS-04 Scope measurement | **Pass** | Out of scope: the scope is not yet live |
| QS-05 Evidence sufficiency | Not applicable | Not performed: needs an engineer who was not present |
| QS-06 Refuse rather than invent | **Pass** | **Pass** |
| QS-07 Sub-GHz link | **Pass** | **Error**: receive after transmit (#179) |
| QS-08 Build and standards | **Pass** | **Pass** |
| QS-09 Multimeter | Dry run only | **Fail** (#181) |
| QS-10 Bench identity | **Pass** | **Pass** |

**44 of the 64 system requirements are qualified** (ETB-SYS5-002 §7). Before
this campaign, only ETB-SYS2-091 and -092 were.

---

## 7. Open Bench-Confirmation Items

Every item below must be closed by a recorded run against hardware before the
requirement it touches can be called qualified. They are held in each element's
own notes, where someone reading about that element sees them, and summarised
here.

| Group | Items | Held in | Touches |
|---|---|---|---|
| Oscilloscope | OPEN-01, OPEN-02 — VXI-11 device name, portmapper transport, hardcopy format, measurement settling, record length; SCPI spellings against the programmer manual | `docs/tek3014b/` VISA determination report §5.1 | ETB-SYS2-060…064 |
| J-Link | JLINK-OPEN-03 (OPEN-05) — SWO timestamp scaling. 01 and 02 closed and 04's figures recorded, 2026-10-04 (ETB-SYS5-002 §9) | `docs/jlink/JLink_Integration_Notes.md` §4 | ETB-SYS2-030…036 |
| BLE dongle | BLE-OPEN-02, -03 (OPEN-06) — behaviour under load, timestamp offset. BLE-OPEN-04 closed 2026-10-04 | ETB-SWE4-002 §4.6 | ETB-SYS2-040…045 |
| Power supply | PSU-OPEN-01…06 (OPEN-08) — `STATUS?` bit order and tracking bits, `ERR?` text, command interval, settling time, whether a slaved-channel setpoint is discarded silently | `docs/psu/GPD3303D_Notes.md` §5 | ETB-SYS2-020…025 |
| S2-LP | S2LP-OPEN-01…05 (OPEN-07) — the vendor firmware's reply text and error codes, board naming, register behaviour | `docs/s2lp/S2LP_Devkit_Notes.md` §7 | ETB-SYS2-046, -047 |
| Multimeter | DMM-OPEN-01…05 — the segment patterns beyond the ten digits, the continuity and diode reading formats, the echo's timing relative to the measurement stream, and whether a range change emits a frame taken under the previous setting | `docs/dmm/TTi1604_Notes.md` §5 | ETB-SYS2-051…053, ETB-SYS2-104 |

---

## 8. Entry and Exit Criteria

**Entry:** system integration complete per ETB-SYS4-001 §6, with every case in
ETB-SYS4-001 §5 performed and passed.

This entry criterion was **not met** when the 2026-10-04 campaign ran: no
integration case had been performed as one (ETB-SYS4-001 §8.1). The campaign ran
by the owner's decision of that time, and its results stand as recorded. They
were gathered with integration-level failures still possible, and three
scenarios did fail on integration-level defects (#178, #179, #181). From
`v0.05.0000` the criterion is met before the campaign, or a deviation is
recorded first (ETB-DEV-004 covers `v0.04.0000`).

**Exit:**

| # | Criterion | State |
|---|---|---|
| X1 | Every scenario in §5 passes in the hardware configuration | Not met. QS-01b, QS-07 and QS-09 fail on hardware; QS-04 is out of scope; QS-05 was not performed (ETB-SYS5-002 §10) |
| X2 | Every system requirement traces to a passing scenario | Not met. 44 of the 64 requirements of 2026-10-04 were qualified (ETB-SYS5-002 §7). Against the 68 of 2026-11-17, the four added since (-017, -026, -037, -065) have no qualification run (ETB-SYS5-002 §11) |
| X3 | Every item in §7 is closed by a recorded run | Not met |
| X4 | No open Critical or Major problem against a qualified requirement | Met |

This is milestone M6 in ETB-MAN3-001 §7, and it is the largest piece of work
remaining on the project.

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
