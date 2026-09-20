# Software Integration & Integration Test

*Automotive SPICE® PAM v4.0 | SWE.5 — Software Integration and Integration Test*

---

## 1. Document Identification & Control

| Field | Value | Field | Value |
|---|---|---|---|
| **Document ID** | TB-SWE5-001 | **Version** | 0.1 |
| **Project** | TestBench | **Date** | 2026-09-19 |
| **Status** | Draft | **Classification** | Internal |
| **Author** | Claude | **Reviewer** | Dermot Murphy |
| **Approver** | Dermot Murphy | **Related Process** | SWE.5 |

> Reviewer and Approver are the same person; see TB-DEV-002.

---

## 2. Revision History

| Version | Date | Author | Description of Change |
|---|---|---|---|
| 0.1 | 2026-09-19 | Claude | Initial |

---

## 3. Purpose & Scope

### 3.1 Purpose

This document says how the software units of TestBench are integrated into the
architecture of TB-SWE2-001, and how the integrated result is tested — that is,
how the **interfaces between units** are shown to work, as distinct from the
units themselves (TB-SWE4-001) and from the software as a whole against its
requirements (TB-SWE6-001).

### 3.2 Referenced Documents

| Document ID | Title | Version |
|---|---|---|
| TB-SWE2-001 | TestBench Software Architecture | 0.1 |
| TB-SWE3-001 | TestBench Software Detailed Design | 0.1 |
| TB-SWE4-001 | TestBench Unit Verification Specification | 0.1 |
| TB-SWE4-002 | TestBench Unit Verification Report | 0.1 |
| TB-SWE6-001 | TestBench Software Qualification Test | 0.1 |
| TB-SYS4-001 | TestBench System Integration & Integration Test | 0.1 |
| TB-SUP9-001 | TestBench Problem Resolution Management Plan | 0.1 |

### 3.3 Scope

The Python package `benchtools` and the dongle firmware's host-facing protocol.
Integration of software with physical instruments is system integration and
belongs to TB-SYS4-001.

---

## 4. Integration Strategy

Integration is **continuous and bottom-up**. There is no separate integration
phase, because there is no period during which the parts exist separately: a
unit is merged only when the suite — which includes every integration test
below — passes with it in place.

| Stage | What is joined | What the joining must show |
|---|---|---|
| I1 | Transports + SCPI plumbing (`core`) | A framed exchange survives the transport's chunking; errors propagate as errors |
| I2 | `core` + one driver | The driver reaches the instrument only through the core's link abstraction |
| I3 | Driver + its simulator | Driver and simulator satisfy the same interface; the driver cannot tell which it has |
| I4 | Drivers + bench model (`core.bench`) | A bench description names instruments and yields opened, identified drivers |
| I5 | Bench + runner | The runner drives real driver objects, resolves saved values between steps, and evaluates expectations against what the drivers returned |
| I6 | Runner + reporting | A run produces markdown and machine-readable output containing every step and every identity |
| I7 | Runner + markdown command scripts | A document in `specs/` is parsed into steps and executed against the dongle driver |
| I8 | Host driver + dongle firmware protocol | Commands framed by the host are accepted by the firmware's parser and answered with dongle-side timestamps |

### 4.1 The Layering Test Is an Integration Test

`tests/test_layering.py` asserts the dependency rules of TB-SWE2-001 §5:
`core` imports no instrument, instruments import no other instrument, the runner
imports drivers only through the registry. It is an integration test in the
strict sense — it tests a property of the assembled whole that no unit test
could see — and it fails the build when the architecture is violated rather than
waiting for a review to notice.

### 4.2 Integration Against Simulators

Integration tests run against the simulated instruments, deliberately. That is
what makes them run on every change with no bench attached. The honest
consequence is stated rather than hidden: an integration test passing against a
simulator shows that the **software** fits together, not that the software fits
the **instrument**. The latter is TB-SYS4-001's job, and the items it has not
yet discharged are listed there.

---

## 5. Integration Test Groups

| Group | Location | Interfaces exercised |
|---|---|---|
| Layering | `tests/test_layering.py` | Every module boundary in TB-SWE2-001 §5 |
| Traceability | `tests/test_traceability.py` | Documents ↔ code ↔ matrix |
| Bench loading | `tests/core/` | Bench description → registry → opened drivers → identity records |
| Transport ↔ protocol | `tests/core/` | Framing, chunking, timeouts, error propagation |
| Driver ↔ simulator | `tests/instruments/*/` | Each driver against its simulator through the shared interface |
| Runner ↔ drivers | `tests/runner/` | Step dispatch, argument resolution, saved-value references, limit evaluation |
| Runner ↔ reporting | `tests/runner/` | Report contents: identities, simulation disclosure, per-step records |
| Command scripts | `tests/instruments/nordic_dongle/test_script.py` | Markdown parsing → step execution → result classification |
| End-to-end specifications | `tests/runner/`, `specs/` | A whole specification against the simulated bench |

---

## 6. Interface Test Cases

The interface properties that integration must establish, each covered by tests
in the groups above:

| ID | Property | Why a unit test cannot show it |
|---|---|---|
| TB-IT-01 | A reply split across transport reads is reassembled into one message | Requires the real framing code above the real chunking |
| TB-IT-02 | A transport error surfaces as an error, never as an empty or default value | The substitution would happen at the boundary between two units |
| TB-IT-03 | A driver behaves identically against instrument and simulator | The property is about two implementations of one interface |
| TB-IT-04 | Opening a bench records every instrument's identity | Spans bench model, registry, drivers and the report |
| TB-IT-05 | A value saved in one step is resolved correctly as an argument in a later step | Spans the resolver, the runner's state and the driver's signature |
| TB-IT-06 | An expectation is evaluated against what the driver actually returned, with its units | Spans driver return types and the limit types |
| TB-IT-07 | A simulated run is labelled simulated in **every** output format | Spans bench model and each report writer |
| TB-IT-08 | A markdown table becomes an ordered sequence of executed steps, including delays and unasserted commands | Spans parser, runner and result classification |
| TB-IT-09 | A step that fails does not stop the following steps from being recorded | A property of the run loop, not of any step |
| TB-IT-10 | The runner reaches a driver only through the registry | Only visible across the assembled package |

---

## 7. Entry and Exit Criteria

**Entry:** the units involved pass their own verification (TB-SWE4-002); the
architecture they must fit is recorded in TB-SWE2-001.

**Exit:** all integration test groups in §5 pass; the layering test passes; no
open Critical or Major problem affects an interface in §6.

Both are checked on every change, so "the integration test has passed" is a
statement about the current revision rather than about a point in the past.

---

## 8. Regression

The whole suite runs on every change. There is no separate regression
selection, because selecting a subset would require knowing which tests a change
could affect — exactly the knowledge a defect at an interface proves was wrong.

---

## 9. Results

| Measure | Value |
|---|---|
| Tests passing | 1 878 (unit and integration together) |
| Statement coverage | 94% |
| Open Critical or Major integration problems | None |

Defects found at integration and their resolutions are recorded in TB-SWE4-002
§17 alongside the unit defects, because in this project they were found by the
same run.

---

## 10. Items Not Covered

| Item | Why | Covered by |
|---|---|---|
| Driver ↔ real instrument behaviour | No hardware in CI | TB-SYS4-001 |
| Host ↔ dongle protocol over real USB | Requires the dongle | TB-SYS4-001 |
| Timing measured through a real transport | Requires hardware | TB-SYS5-001 |
| Firmware internal integration | Built and size-checked in CI; not unit-tested on target | TB-SYS4-001 |

---

## 11. Review & Approval

| Role | Name | Signature / Electronic Approval | Date |
|---|---|---|---|
| Author | Claude | Approved | 2026-09-19 |
| Reviewer | Dermot Murphy | — | *pending* |
| Approver | Dermot Murphy | — | *pending* |
