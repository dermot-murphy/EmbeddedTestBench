<img src="../../assets/brand/svg/logos/embeddedtestbench-logo-compact.svg" alt="Embedded Test Bench" width="240">

# Test Case Specification — Template

*Automotive SPICE® PAM v4.0 Capability Level 2 | SWE.4, SWE.5, SWE.6, SYS.4, SYS.5*

---

## 1. Document Identification & Control

| Field | Value | Field | Value |
|---|---|---|---|
| **Document ID** | ETB-TMPL-002 | **Version** | 0.3 |
| **Project** | Embedded Test Bench | **Date** | 2026-10-05 |
| **Status** | Draft | **Classification** | Internal |
| **Author** | Claude | **Reviewer** | Dermot Murphy |
| **Approver** | Dermot Murphy | **Related Process** | SWE.4, SWE.5, SWE.6 |

> Reviewer and Approver are the same person; see ETB-DEV-002.

---

## 2. Revision History

| Version | Date | Author | Description of Change |
|---|---|---|---|
| 0.1 | 2026-09-19 | Claude | Initial |
| 0.2 | 2026-10-04 | Claude | #183: product renamed to Embedded Test Bench - document file name prefix `EmbeddedTestBench_`, identifier prefix `ETB-` (was `TB-`), product name in prose. Earlier revision rows keep the names in use when they were written. |
| 0.3 | 2026-10-05 | Claude | #194: the compact brand logo added above the title, the same line in every controlled document (ETB-SUP8-001 §6.3). |

---

## 3. Purpose & Scope

### 3.1 Purpose

This is the form a Embedded Test Bench test case is written on when it is written by hand
rather than generated from the suite. Copy the block in §4 once per test case.

Most Embedded Test Bench test cases are **not** written on this form: they are pytest
functions, whose docstring and identifier carry the same information and whose
traceability is checked mechanically. Use this template for test cases that a
person performs — bench-confirmation items against real instruments, and system
qualification runs — where there is no code to carry the record.

### 3.2 Referenced Documents

| Document ID | Title | Version |
|---|---|---|
| ETB-SWE4-001 | Embedded Test Bench Unit Verification Specification | 0.1 |
| ETB-SWE5-001 | Embedded Test Bench Software Integration & Integration Test | 0.1 |
| ETB-SWE6-001 | Embedded Test Bench Software Qualification Test | 0.1 |
| ETB-SYS4-001 | Embedded Test Bench System Integration & Integration Test | 0.1 |
| ETB-SYS5-001 | Embedded Test Bench System Qualification Test | 0.1 |

### 3.3 Scope

Applies to manually performed test cases at any level. It does not replace the
automated suite, and a test case written on this form must still appear in
ETB-RTM-001 against the requirement it verifies.

---

## 4. Test Case

| Field | Value |
|---|---|
| **Test Case ID** | *ETB-TC-nnn* |
| **Title** | *one line* |
| **Level** | *Unit / SW integration / SW qualification / System integration / System qualification* |
| **Verifies** | *requirement IDs, e.g. ETB-SYS2-010, PSU-FR-004* |
| **Method** | *Test / Analysis / Inspection / Demonstration* |
| **Type** | *Normal / Boundary / Negative / Robustness / Resource / Timing / Regression* |
| **Automated** | *no — or the pytest node ID if it is* |
| **Bench required** | *simulated / real instrument (which)* |
| **Duration (estimate)** | *n min* |

### 4.1 Preconditions

| # | Precondition |
|---|---|
| P1 | *what must be true before the first step; instrument state, firmware build, connections* |

### 4.2 Test Data

| Name | Value | Note |
|---|---|---|
| *name* | *value with units* | *where the value comes from* |

### 4.3 Steps

| # | Action | Expected result |
|---|---|---|
| 1 | *what the tester does, exactly* | *what must be observed, with tolerance and units* |

Each step's expected result must be observable. "The supply works" is not an
expected result; "`CH1` reads 3.200 V ± 0.05 V on the front panel and
`read_voltage(1)` returns a value within 0.01 V of it" is.

### 4.4 Postconditions

| # | Postcondition |
|---|---|
| Q1 | *the state the bench is left in — outputs off, supplies at zero* |

### 4.5 Pass / Fail Criteria

**Pass:** every step's expected result observed, within the stated tolerances.

**Fail:** any step's expected result not observed, or any step not performed.

A step that could not be performed is recorded as **blocked**, with the reason.
It is not a pass.

---

## 5. Execution Record

One row per execution. Do not overwrite an earlier row.

| Run | Date | Tester | Build / revision | Bench | Result | Problem ID | Note |
|---|---|---|---|---|---|---|---|
| 1 | *YYYY-MM-DD* | *name* | *git revision* | *simulated / serial number* | *Pass / Fail / Blocked* | *ETB-PR-nnn* | |

A failed run is raised as a problem under ETB-SUP9-001 before the test case is
run again, so that the second run cannot quietly replace the first.

---

## 6. Review & Approval

| Role | Name | Signature / Electronic Approval | Date |
|---|---|---|---|
| Author | Claude | Approved | 2026-09-19 |
| Reviewer | Dermot Murphy | — | *pending* |
| Approver | Dermot Murphy | — | *pending* |
