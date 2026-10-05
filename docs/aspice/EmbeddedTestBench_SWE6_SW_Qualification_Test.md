<img src="../../assets/brand/svg/logos/embeddedtestbench-logo-compact.svg" alt="Embedded Test Bench" width="240">

# Software Qualification Test

*Automotive SPICE® PAM v4.0 | SWE.6 — Software Qualification Test*

---

## 1. Document Identification & Control

| Field | Value | Field | Value |
|---|---|---|---|
| **Document ID** | ETB-SWE6-001 | **Version** | 0.6 |
| **Project** | Embedded Test Bench | **Date** | 2026-10-05 |
| **Status** | Draft | **Classification** | Internal |
| **Author** | Claude | **Reviewer** | Dermot Murphy |
| **Approver** | Dermot Murphy | **Related Process** | SWE.6 |

> Reviewer and Approver are the same person; see ETB-DEV-002.

---

## 2. Revision History

| Version | Date | Author | Description of Change |
|---|---|---|---|
| 0.1 | 2026-09-19 | Claude | Initial |
| 0.2 | 2026-09-23 | Claude | TB-QT-02a added: the five-instrument specification run against the simulated bench. |
| 0.3 | 2026-09-24 | Claude | TB-QT-05 added: the bench self-check, simulated and gated. |
| 0.4 | 2026-10-04 | Claude | #183: product renamed to Embedded Test Bench - document file name prefix `EmbeddedTestBench_`, identifier prefix `ETB-` (was `TB-`), product name in prose. Earlier revision rows keep the names in use when they were written. |
| 0.5 | 2026-10-05 | Claude | #204: Review & Approval table points to the merge of the pull request that last changed the document, which is the review and approval (ETB-SUP8-001 §5.7); no per-change signatures or dates. |
| 0.6 | 2026-10-05 | Claude | #194: the compact brand logo added above the title, the same line in every controlled document (ETB-SUP8-001 §6.3). |

---

## 3. Purpose & Scope

### 3.1 Purpose

This document says how the integrated software is shown to meet the software
requirements of ETB-SWE1-001 — not unit by unit and not interface by interface,
but as the thing an engineer actually uses.

### 3.2 Referenced Documents

| Document ID | Title | Version |
|---|---|---|
| ETB-SWE1-001 | Embedded Test Bench Software Requirements Specification | 0.1 |
| ETB-SWE5-001 | Embedded Test Bench Software Integration & Integration Test | 0.1 |
| ETB-SYS5-001 | Embedded Test Bench System Qualification Test | 0.1 |
| ETB-RTM-001 | Embedded Test Bench Traceability Matrix | 0.1 |
| ETB-TMPL-002 | Embedded Test Bench Test Case Specification — Template | 0.1 |

### 3.3 Scope

`benchtools` as installed: its command-line interfaces, its bench and
specification file formats, and its reports. Qualification of the whole bench
including instruments is ETB-SYS5-001.

---

## 4. Qualification Strategy

Qualification is by **use**: the software is exercised the way an engineer
exercises it — a bench file, a specification file, a command, a report — and the
result is compared with what ETB-SWE1-001 says should happen.

Three properties shape the strategy:

1. **Every requirement must be covered.** `tests/test_traceability.py` fails the
   build if a requirement in ETB-SWE1-001 has no covering test, so coverage of
   requirements is mechanical rather than asserted here.
2. **Qualification runs against the simulated bench.** This is what lets it run
   on every change; what it therefore does *not* show is stated in §8.
3. **Negative cases qualify as much as positive ones.** A tool whose value is
   refusing to make unsupported claims is not qualified by showing that it works
   when everything is fine.

---

## 5. Qualification Test Cases

| ID | Qualifies | Scenario | Pass criterion |
|---|---|---|---|
| ETB-QT-01 | `CORE-FR-*`, `INST-FR-*` | Load `benches/simulated_bench.yaml` and open every instrument in it | Every driver opens; every identity is recorded |
| ETB-QT-02 | `RUN-FR-*` | Run `specs/sensor_bringup.yaml` against the simulated bench | Run completes; report names spec, bench and every identity; result is pass |
| ETB-QT-02a | `RUN-FR-*`, `DMM-FR-*`, `BLE-FR-025` | Run `specs/sensor_power_signal_and_link.yaml` against the simulated bench: five instruments in one pass, including a current measured through the meter and a board chosen by signal strength | Run completes; every instrument identity recorded; result is pass. A bench stating a simulated current outside the specification's band fails that test and only that test |
| ETB-QT-05 | `RUN-FR-054` … `-057` | Run `specs/bench_self_check.yaml`: against the simulated bench unattended, and against a non-simulated bench with no terminal and no `--acknowledge` | Simulated run prints the warning and passes ungated; the hardware run prints the warning, exits 3 and opens no instrument |
| ETB-QT-03 | `RUN-FR-*`, `BLE-FR-*` | Run `specs/sensor_commands.yaml`, which executes `specs/sensor_commands.md` | Each markdown test appears in the report with per-step command, response, expectation, time and result |
| ETB-QT-04 | `RUN-FR-*` | A markdown step that is a delay, and a step with no stated expectation | Both recorded as **skip**, in order, neither as pass |
| ETB-QT-05 | `RUN-FR-*` | A step whose response does not match its expectation | Step **fail**; following steps still executed and recorded; overall result fail |
| ETB-QT-06 | `RUN-FR-*` | A specification that saves a value in one step and uses it in a later one | The later step receives the saved value; the report shows both |
| ETB-QT-07 | `RUN-FR-025` | A value with a `format:` presentation | Report shows the formatted value; the raw value is retained |
| ETB-QT-08 | `PSU-FR-*` | Set channel 1 to 3.2 V, limit 500 mA, output on, read back | Setpoints and readings agree; state reported |
| ETB-QT-09 | `PSU-FR-*` | Attempt a per-channel write while the supply is tracking | The write is **refused** with a message naming the reason; no setpoint is sent |
| ETB-QT-10 | `PSU-FR-*` | Reset the supply from a tracking mode | Safe state reached — outputs off, setpoints zero |
| ETB-QT-11 | `JLINK-FR-*` | Flash an image with a manifest, verify, read UICR 0x10001080 | Programmed image verifies; identifier read and rendered as six uppercase hex digits |
| ETB-QT-12 | `JLINK-FR-043` | Read memory with an unsupported width or byte order | Refused with an error; no value returned |
| ETB-QT-13 | `JLINK-FR-054` | Start the target and check RTT output within a timeout | Output observed within the timeout, or a clear timeout error |
| ETB-QT-14 | `BLE-FR-*` | Scan, match the advertising name against the rendered identifier, connect, send `rd version` | Connected device's identifier matches; version matches the manifest of the flashed image |
| ETB-QT-15 | `BLE-FR-*` | A command that receives no reply | Recorded as an error or an empty response as the specification requires — never as a pass |
| ETB-QT-16 | `SCOPE-FR-*`, `ANA-FR-*` | Configure channels, capture, measure period and inter-channel spread | Measurements returned with units and resolution |
| ETB-QT-17 | `CORE-NFR-*` | Run a specification against a bench containing a simulated instrument | Every report format states that the run was simulated |
| ETB-QT-18 | `CORE-NFR-*` | Ask for an instrument that the bench does not contain | Clear error naming what was asked for; no run started |
| ETB-QT-19 | `RUN-FR-*` | Produce machine-readable results | Output consumable by CI, containing each test and its result |
| ETB-QT-20 | `CORE-FR-*` | A version mismatch between a device and its firmware manifest | Run fails with the two versions named |

Test cases ETB-QT-01…20 are realised as automated tests in `tests/runner/` and
`tests/instruments/`; the traceability check links each requirement to the tests
that cover it. Manually performed qualification cases, where any are added, are
written on ETB-TMPL-002.

---

## 6. Entry and Exit Criteria

**Entry:** integration complete per ETB-SWE5-001 §7; the requirement set under
qualification is at a known version.

**Exit:**

| # | Criterion | State |
|---|---|---|
| X1 | Every requirement in ETB-SWE1-001 has at least one covering test | Enforced by `tests/test_traceability.py` |
| X2 | All qualification cases in §5 pass | Yes, against the simulated bench |
| X3 | No open Critical or Major problem against a qualified requirement | Yes |
| X4 | Items not covered are listed with the document that will cover them | §8 |

---

## 7. Results

| Measure | Value |
|---|---|
| Tests passing | 1 878 |
| Statement coverage | 94% |
| Requirements without a covering test | 0 |
| Qualification cases failing | 0 |
| Bench used | Simulated |

The last row is the one that matters most when reading the four above it.

---

## 8. Items Not Covered

Qualification against the simulated bench cannot show:

| Item | Covered by |
|---|---|
| That a driver's understanding of an instrument's command set is correct | ETB-SYS5-001 |
| That measured times reflect real transport and radio behaviour | ETB-SYS5-001 |
| That the supply's real tracking behaviour matches what the simulator models | ETB-SYS5-001, PSU bench-confirmation items |
| That flash programming and verification behave as modelled on a real target | ETB-SYS5-001, JLINK bench-confirmation items |
| Firmware behaviour on the dongle hardware | ETB-SYS5-001, BLE bench-confirmation items |

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
