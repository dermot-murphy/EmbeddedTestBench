# Quality Assurance Plan

*Automotive SPICE® PAM v4.0 | SUP.1 — Quality Assurance*

---

## 1. Document Identification & Control

| Field | Value | Field | Value |
|---|---|---|---|
| **Document ID** | TB-SUP1-001 | **Version** | 0.1 |
| **Project** | TestBench | **Date** | 2026-09-19 |
| **Status** | Draft | **Classification** | Internal |
| **Author** | Claude | **Reviewer** | Dermot Murphy |
| **Approver** | Dermot Murphy | **Related Process** | SUP.1 |

> Reviewer and Approver are the same person; see TB-DEV-002.

---

## 2. Revision History

| Version | Date | Author | Description of Change |
|---|---|---|---|
| 0.1 | 2026-09-19 | Claude | Initial |

---

## 3. Purpose & Scope

### 3.1 Purpose

This plan says what quality means for TestBench, what is checked, by what, and
what happens when a check fails.

Quality assurance here is deliberately mechanical wherever it can be. A check
that runs on every change and fails the build is worth more than a checklist
that depends on someone remembering, and far more than a signature on a review
that nobody can reconstruct.

### 3.2 Referenced Documents

| Document ID | Title | Version |
|---|---|---|
| TB-MAN3-001 | TestBench Project Management Plan | 0.1 |
| TB-SUP8-001 | TestBench Configuration Management Plan | 0.1 |
| TB-SUP9-001 | TestBench Problem Resolution Management Plan | 0.1 |
| TB-SUP10-001 | TestBench Change Request Management Plan | 0.1 |
| TB-TMPL-001 | TestBench Work Product Review Record — Template | 0.1 |
| TB-STD-002 | TestBench Embedded C Coding Standard | 0.1 |
| TB-STY-001 | TestBench Embedded C Style Guide | 0.1 |
| TB-DEV-001 | TestBench AI Authorship Deviation | 0.1 |
| TB-DEV-002 | TestBench Independent Review Deviation | 0.1 |

### 3.3 Scope

Every work product of TestBench: the documents in `docs/`, the Python package
`benchtools`, the firmware under `firmware/`, the specifications under `specs/`
and `benches/`, and the workflows under `.github/`.

---

## 4. Quality Objectives

| ID | Objective | Measure | Target |
|---|---|---|---|
| TB-QA-001 | The suite passes | `pytest` | All tests pass, every change |
| TB-QA-002 | Code is exercised, not merely present | `pytest --cov=benchtools` statement coverage | ≥ 90% (currently 94%) |
| TB-QA-003 | Documents and code agree | `tests/test_traceability.py` | Passes, every change |
| TB-QA-004 | Every requirement is verified | Traceability check | No requirement without a covering test |
| TB-QA-005 | Firmware builds from a clean checkout | `.github/workflows/firmware.yml` | Green, every push |
| TB-QA-008 | The suite and the lint check run where they can block a merge | `.github/workflows/tests.yml`, `lint.yml` | Green, every push |
| TB-QA-006 | C source conforms to the standard | `.github/workflows/style.yml` (CStyleCheck) | Green, every push |
| TB-QA-007 | Nothing unconfirmed is presented as confirmed | Review check C6, TB-TMPL-001 | No exceptions |

---

## 5. Work Products Subject to Quality Assurance

| Work product | Checks applied |
|---|---|
| ASPICE documents (`docs/aspice/`) | Review on TB-TMPL-001 before status leaves Draft; traceability check for the requirement, design and test documents |
| Python source (`benchtools/`) | Unit tests, coverage, traceability of requirement citations |
| Firmware source (`firmware/`) | Build in CI, CStyleCheck against TB-STD-002 and TB-STY-001, flash and RAM figures recorded |
| Bench specifications (`specs/`, `benches/`) | Executed against the simulated bench in the suite |
| Workflows (`.github/`) | Exercised by being run; a workflow that has never run green is not relied upon |
| This document set | Reviewed as above; the deviations in TB-DEV-001 and TB-DEV-002 are restated in each document's identification block |

---

## 6. Quality Activities

### 6.1 On Every Change

1. The full test suite runs and passes before the change is committed.
2. The traceability check runs as part of it.
3. Documents affected by the change are updated **in the same change**. A change
   that alters behaviour and leaves the documents for later has not been made
   correctly; it has been half made.
4. New behaviour arrives with the tests that fail without it.

### 6.2 On Every Push

The workflows in `.github/workflows/` build the firmware, run the C
coding-standard check, run the bench specifications against the simulated
bench, run the Python suite with coverage, and lint the Python. A red workflow
is a problem under TB-SUP9-001, not a thing to re-run until it passes.

### 6.3 Before a Document Leaves Draft

A review is held and recorded on TB-TMPL-001. Critical and Major findings are
closed before approval.

### 6.4 At Each Milestone

Quality objectives in §4 are measured and recorded; risks are reviewed
(TB-MAN5-001 §7); open bench-confirmation items are counted.

---

## 7. Evidence and Honesty

The following rules are the ones this project would rather break a schedule
than break:

1. **A test that was not run is not recorded as passed.** Reports state whether
   a run was simulated.
2. **A review that was not held is not recorded.** This baseline ships review
   *templates* and no review *records*, because no reviews have been held.
3. **A measurement not taken on hardware is listed as an open
   bench-confirmation item**, in the element's own notes, where someone
   reading about that element will see it.
4. **A test is never weakened to make a build green.** Skipping, `xfail`-ing or
   deleting a failing test in place of fixing what it found is prohibited; the
   failure is raised as a problem instead.
5. **Coverage is not gamed.** Tests exist to catch defects; a test written only
   to execute a line is a defect in the suite.

---

## 8. Escalation

A quality issue that cannot be resolved by the person who found it is raised as
a problem (TB-SUP9-001) and, if it needs a change of plan or scope, as a change
request (TB-SUP10-001). The project lead decides. There is no higher authority
in this project, and pretending otherwise would make the escalation path a
fiction.

Where the quality issue *is* the process — a check that cannot be met as
written — the plan is changed or a deviation is recorded (TB-DEV-001,
TB-DEV-002 are the standing examples).

---

## 9. Records

| Record | Location |
|---|---|
| Test results | CI run logs; `pytest` output in the commit's checks |
| Coverage | CI run logs |
| Review records | `docs/aspice/reviews/` (none yet) |
| Problems | `docs/aspice/problems/` and the repository issue tracker (TB-SUP9-001 §6) |
| Change requests | TB-SUP10-001 §6 |
| Deviations | `docs/aspice/TestBench_DEV*.md` |
| Baselines | Git tags (TB-SUP8-001 §7) |

---

## 10. Review & Approval

| Role | Name | Signature / Electronic Approval | Date |
|---|---|---|---|
| Author | Claude | Approved | 2026-09-19 |
| Reviewer | Dermot Murphy | — | *pending* |
| Approver | Dermot Murphy | — | *pending* |
