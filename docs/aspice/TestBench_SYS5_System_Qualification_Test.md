# System Qualification Test

*Automotive SPICE® PAM v4.0 | SYS.5 — System Qualification Test*

---

## 1. Document Identification & Control

| Field | Value | Field | Value |
|---|---|---|---|
| **Document ID** | TB-SYS5-001 | **Version** | 0.3 |
| **Project** | TestBench | **Date** | 2026-10-04 |
| **Status** | Draft | **Classification** | Internal |
| **Author** | Claude | **Reviewer** | Dermot Murphy |
| **Approver** | Dermot Murphy | **Related Process** | SYS.5 |

> Reviewer and Approver are the same person; see TB-DEV-002.

---

## 2. Revision History

| Version | Date | Author | Description of Change |
|---|---|---|---|
| 0.1 | 2026-09-19 | Claude | Initial |
| 0.2 | 2026-09-23 | Claude | The multimeter replaces the deferred row in the bench-confirmation table, with open items DMM-OPEN-01…05. |
| 0.3 | 2026-10-04 | Claude | #176: first hardware campaign, reported in TB-SYS5-002. QS-01b, QS-09 and QS-10 added. §5.1 names the hardware specifications. §6 hardware column filled in. §7 and §8 updated from the results. |

---

## 3. Purpose & Scope

### 3.1 Purpose

This document says how the assembled bench is shown to meet the system
requirements of TB-SYS2-001, and records what remains to be shown.

### 3.2 Referenced Documents

| Document ID | Title | Version |
|---|---|---|
| TB-SYS2-001 | TestBench System Requirements Specification | 0.1 |
| TB-SYS3-001 | TestBench System Architecture | 0.1 |
| TB-SYS4-001 | TestBench System Integration & Integration Test | 0.1 |
| TB-SWE6-001 | TestBench Software Qualification Test | 0.1 |
| TB-SWE4-002 | TestBench Unit Verification Report | 0.1 |
| TB-TMPL-002 | TestBench Test Case Specification — Template | 0.1 |
| TB-RTM-001 | TestBench Traceability Matrix | 0.1 |
| TB-SYS5-002 | TestBench System Qualification Test Report | 1.0 |

### 3.3 Scope

The whole bench, operated as an engineer operates it, against the requirements
of TB-SYS2-001.

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

*Qualifies:* TB-SYS2-001, -002, -004, -015, -020, -021, -030, -031, -034, -036,
-040, -041, -045, -048, -049, -050, -070, -076, -078.

### QS-02 — BLE command set as a document

Run `specs/sensor_commands.md` through `specs/sensor_commands.yaml`: each
heading a test, each row a step, delays and unasserted commands recorded as
skipped, timings at 10 ms resolution with the finer value retained, overall
pass only if no step failed.

*Qualifies:* TB-SYS2-003, -042, -043, -044, -073, -074, -075, -076, -077.

### QS-03 — The supply refuses what it cannot honour

With the supply in each tracking mode in turn, attempt a per-channel write;
observe that the driver refuses, and that the supply's own behaviour on such a
write is what the simulator models. Then reset to the safe state from each mode.

*Qualifies:* TB-SYS2-022, -023, -024, -025.

### QS-04 — A measurement with the scope

Configure channels, timebase and trigger; capture; measure period and the spread
in time of several channels crossing a threshold; compare against the same
quantity measured through the probe's timing methods.

*Qualifies:* TB-SYS2-060, -061, -062, -063, -064.

### QS-05 — Evidence is sufficient to reproduce the run

Take a report produced by QS-01 on hardware, hand it to someone who was not
present, and have them reproduce the run from it alone.

*Qualifies:* TB-SYS2-001, -015, -016, -078, -079.

### QS-06 — The bench refuses rather than invents

Provoke, in turn: an instrument missing from the bench; a transport that stops
answering mid-exchange; an unsupported memory width; a firmware version that
disagrees with its manifest; a command that gets no reply. Each must produce an
error naming what was asked and why it failed, and none must produce a value.

*Qualifies:* TB-SYS2-003, -004, -032, -036, -094.

### QS-07 — Sub-GHz link

Programme and read back every S2-LP register, transmit and receive over the
link, and confirm that all data exchanged is logged.

*Qualifies:* TB-SYS2-046, -047.

### QS-08 — Build and standards

The firmware builds from a clean checkout in CI with its flash and RAM figures
recorded, and the C source passes the coding-standard check.

*Qualifies:* TB-SYS2-091, -092.

### QS-01b — Debug control and firmware state

Added in 0.3. QS-01's image may have no symbols, and without them there are no
variables by name and no source breakpoints. This scenario programmes an image
whose ELF is available, then:
- halts, steps and breaks at `main`;
- reads the call stack and a named variable;
- times start-up from `SystemInit` to `main` on the cycle counter, stating the
  resolution;
- checks the reported version against the manifest.

*Qualifies:* TB-SYS2-002, -030, -031, -033, -035, -036, -041.

### QS-09 — Multimeter

Added in 0.3; no earlier scenario covered the multimeter. Run the opt-in bench
test `tests/bench/tti1604` (DMM-FR-080) against the real meter with its inputs
open: the link and key echo, frame decoding, the reading rate, the function and
range tour, the frequency gate, an open input on ohms as overrange, and local
and remote. Wire the references the test names to cover DC volts, resistance,
current and frequency against known values.

*Qualifies:* TB-SYS2-051, -052, -053.

### QS-10 — Bench identity

Added in 0.3. Read every instrument once without changing anything, so one
report records each instrument's model, serial number and firmware. Run the
same specification again on the simulated bench.

*Qualifies:* TB-SYS2-010, -011, -012, -014, -015, -016, -070, -078, -079, -084.

### 5.1 Hardware specifications

The hardware configuration of each scenario is in `specs/qualification/`, run
against `benches/bench_pc.yaml`. `specs/qualification/README.md` is the
procedure, including the owner's limits on the supply while a sensor is wired
to it.

---

## 6. Results

The hardware column is from the 2026-10-04 campaign; TB-SYS5-002 has the
details and the evidence.

| Scenario | Simulated | Hardware (TB-SYS5-002) |
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

**44 of the 64 system requirements are qualified** (TB-SYS5-002 §7). Before
this campaign, only TB-SYS2-091 and -092 were.

---

## 7. Open Bench-Confirmation Items

Every item below must be closed by a recorded run against hardware before the
requirement it touches can be called qualified. They are held in each element's
own notes, where someone reading about that element sees them, and summarised
here.

| Group | Items | Held in | Touches |
|---|---|---|---|
| Oscilloscope | OPEN-01, OPEN-02 — VXI-11 device name, portmapper transport, hardcopy format, measurement settling, record length; SCPI spellings against the programmer manual | `docs/tek3014b/` VISA determination report §5.1 | TB-SYS2-060…064 |
| J-Link | JLINK-OPEN-03 (OPEN-05) — SWO timestamp scaling. 01 and 02 closed and 04's figures recorded, 2026-10-04 (TB-SYS5-002 §9) | `docs/jlink/JLink_Integration_Notes.md` §4 | TB-SYS2-030…036 |
| BLE dongle | BLE-OPEN-02, -03 (OPEN-06) — behaviour under load, timestamp offset. BLE-OPEN-04 closed 2026-10-04 | TB-SWE4-002 §4.6 | TB-SYS2-040…045 |
| Power supply | PSU-OPEN-01…06 (OPEN-08) — `STATUS?` bit order and tracking bits, `ERR?` text, command interval, settling time, whether a slaved-channel setpoint is discarded silently | `docs/psu/GPD3303D_Notes.md` §5 | TB-SYS2-020…025 |
| S2-LP | S2LP-OPEN-01…05 (OPEN-07) — the vendor firmware's reply text and error codes, board naming, register behaviour | `docs/s2lp/S2LP_Devkit_Notes.md` §7 | TB-SYS2-046, -047 |
| Multimeter | DMM-OPEN-01…05 — the segment patterns beyond the ten digits, the continuity and diode reading formats, the echo's timing relative to the measurement stream, and whether a range change emits a frame taken under the previous setting | `docs/dmm/TTi1604_Notes.md` §5 | TB-SYS2-051…053, TB-SYS2-104 |

---

## 8. Entry and Exit Criteria

**Entry:** system integration complete per TB-SYS4-001 §6, with every case in
TB-SYS4-001 §5 performed and passed.

**Exit:**

| # | Criterion | State |
|---|---|---|
| X1 | Every scenario in §5 passes in the hardware configuration | Not met. QS-01b, QS-07 and QS-09 fail on hardware; QS-04 is out of scope; QS-05 was not performed (TB-SYS5-002 §10) |
| X2 | Every system requirement traces to a passing scenario | Not met. 44 of 64 qualified (TB-SYS5-002 §7) |
| X3 | Every item in §7 is closed by a recorded run | Not met |
| X4 | No open Critical or Major problem against a qualified requirement | Met |

This is milestone M6 in TB-MAN3-001 §7, and it is the largest piece of work
remaining on the project.

---

## 9. Review & Approval

| Role | Name | Signature / Electronic Approval | Date |
|---|---|---|---|
| Author | Claude | Approved | 2026-09-19 |
| Reviewer | Dermot Murphy | — | *pending* |
| Approver | Dermot Murphy | — | *pending* |
