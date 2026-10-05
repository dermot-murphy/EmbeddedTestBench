<img src="../../assets/brand/svg/logos/embeddedtestbench-logo-compact.svg" alt="Embedded Test Bench" width="240">

# Quality Assurance Plan

*Automotive SPICE® PAM v4.0 | SUP.1 — Quality Assurance*

---

## 1. Document Identification & Control

| Field | Value | Field | Value |
|---|---|---|---|
| **Document ID** | ETB-SUP1-001 | **Version** | 0.4 |
| **Project** | Embedded Test Bench | **Date** | 2026-10-05 |
| **Status** | Draft | **Classification** | Internal |
| **Author** | Claude | **Reviewer** | Dermot Murphy |
| **Approver** | Dermot Murphy | **Related Process** | SUP.1 |

> Reviewer and Approver are the same person; see ETB-DEV-002.

---

## 2. Revision History

| Version | Date | Author | Description of Change |
|---|---|---|---|
| 0.1 | 2026-09-19 | Claude | Initial |
| 0.2 | 2026-10-04 | Claude | #183: product renamed to Embedded Test Bench - document file name prefix `EmbeddedTestBench_`, identifier prefix `ETB-` (was `TB-`), product name in prose. Earlier revision rows keep the names in use when they were written. |
| 0.3 | 2026-10-05 | Claude | #204: §6.5 added - a pull request merge is an accepted form of review record, and the Reviewer applies ETB-TMPL-001 checks C1 to C6 before merging. §5, §6.3, §7 and §9 updated to match; §10 points to the merge (ETB-SUP8-001 §5.7). |
| 0.4 | 2026-10-05 | Claude | #194: the compact brand logo added above the title, the same line in every controlled document (ETB-SUP8-001 §6.3). |

---

## 3. Purpose & Scope

### 3.1 Purpose

This plan says what quality means for Embedded Test Bench, what is checked, by what, and
what happens when a check fails.

Quality assurance here is deliberately mechanical wherever it can be. A check
that runs on every change and fails the build is worth more than a checklist
that depends on someone remembering, and far more than a signature on a review
that nobody can reconstruct.

### 3.2 Referenced Documents

| Document ID | Title | Version |
|---|---|---|
| ETB-MAN3-001 | Embedded Test Bench Project Management Plan | 0.1 |
| ETB-SUP8-001 | Embedded Test Bench Configuration Management Plan | 0.1 |
| ETB-SUP9-001 | Embedded Test Bench Problem Resolution Management Plan | 0.1 |
| ETB-SUP10-001 | Embedded Test Bench Change Request Management Plan | 0.1 |
| ETB-TMPL-001 | Embedded Test Bench Work Product Review Record — Template | 0.1 |
| ETB-STD-002 | Embedded Test Bench Embedded C Coding Standard | 0.1 |
| ETB-STY-001 | Embedded Test Bench Embedded C Style Guide | 0.1 |
| ETB-DEV-001 | Embedded Test Bench AI Authorship Deviation | 0.1 |
| ETB-DEV-002 | Embedded Test Bench Independent Review Deviation | 0.1 |

### 3.3 Scope

Every work product of Embedded Test Bench: the documents in `docs/`, the Python package
`benchtools`, the firmware under `firmware/`, the specifications under `specs/`
and `benches/`, and the workflows under `.github/`.

---

## 4. Quality Objectives

| ID | Objective | Measure | Target |
|---|---|---|---|
| ETB-QA-001 | The suite passes | `pytest` | All tests pass, every change |
| ETB-QA-002 | Code is exercised, not merely present | `pytest --cov=benchtools` statement coverage | ≥ 90% (currently 94%) |
| ETB-QA-003 | Documents and code agree | `tests/test_traceability.py` | Passes, every change |
| ETB-QA-004 | Every requirement is verified | Traceability check | No requirement without a covering test |
| ETB-QA-005 | Firmware builds from a clean checkout | `.github/workflows/firmware.yml` | Green, every push |
| ETB-QA-008 | The suite and the lint check run where they can block a merge | `.github/workflows/tests.yml`, `lint.yml` | Green, every push |
| ETB-QA-006 | C source conforms to the standard | `.github/workflows/style.yml` (CStyleCheck) | Green, every push |
| ETB-QA-007 | Nothing unconfirmed is presented as confirmed | Review check C6, ETB-TMPL-001 | No exceptions |

---

## 5. Work Products Subject to Quality Assurance

| Work product | Checks applied |
|---|---|
| ASPICE documents (`docs/aspice/`) | Review and approval by the merge of the pull request that changes them (§6.5); review before status leaves Draft (§6.3); traceability check for the requirement, design and test documents |
| Python source (`benchtools/`) | Unit tests, coverage, traceability of requirement citations |
| Firmware source (`firmware/`) | Build in CI, CStyleCheck against ETB-STD-002 and ETB-STY-001, flash and RAM figures recorded |
| Bench specifications (`specs/`, `benches/`) | Executed against the simulated bench in the suite |
| Workflows (`.github/`) | Exercised by being run; a workflow that has never run green is not relied upon |
| This document set | Reviewed as above; the deviations in ETB-DEV-001 and ETB-DEV-002 are restated in each document's identification block |

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
is a problem under ETB-SUP9-001, not a thing to re-run until it passes.

### 6.3 Before a Document Leaves Draft

A review is held and recorded, either by the merge of the pull request that
changes the document's status (§6.5) or on a completed copy of ETB-TMPL-001.
Critical and Major findings are closed before approval.

### 6.4 At Each Milestone

Quality objectives in §4 are measured and recorded; risks are reviewed
(ETB-MAN5-001 §7); open bench-confirmation items are counted.

### 6.5 Review and Approval by Pull Request Merge

Every change reaches `develop` or `main` through a pull request
(ETB-SUP8-001 §5.1). Merging that pull request is the Reviewer's approval and
the Approver's approval of everything in it (ETB-SUP8-001 §5.7, ETB-DEV-002).
**A pull request merge is therefore an accepted form of review record.**

Before merging, the Reviewer:

1. confirms that every required status check is green (ETB-SUP8-001 §5.5);
2. applies checks C1 to C6 of ETB-TMPL-001 §6.1 to each work product the pull
   request changes;
3. raises each finding on the pull request, and as a problem (ETB-SUP9-001) when
   it is Critical or Major, and does not merge until it is resolved.

The record is the pull request (its description, changes and comments), its CI
result, and its merge record: who merged it, when, and the merge commit. The
Review & Approval table of each document points to that record and is not
filled in.

---

## 7. Evidence and Honesty

The following rules are the ones this project would rather break a schedule
than break:

1. **A test that was not run is not recorded as passed.** Reports state whether
   a run was simulated.
2. **A review that was not held is not recorded.** A review is recorded by the
   merge of a pull request (§6.5) or on a completed copy of ETB-TMPL-001, and in
   no other way. No approval is entered in a document's Review & Approval table,
   and none is recorded on the owner's behalf.
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
a problem (ETB-SUP9-001) and, if it needs a change of plan or scope, as a change
request (ETB-SUP10-001). The project lead decides. There is no higher authority
in this project, and pretending otherwise would make the escalation path a
fiction.

Where the quality issue *is* the process — a check that cannot be met as
written — the plan is changed or a deviation is recorded (ETB-DEV-001,
ETB-DEV-002 are the standing examples).

---

## 9. Records

| Record | Location |
|---|---|
| Test results | CI run logs; `pytest` output in the commit's checks |
| Coverage | CI run logs |
| Review and approval records | The merged pull request, its CI result and its merge record (§6.5); completed ETB-TMPL-001 copies in `docs/aspice/reviews/` (none yet) |
| Problems | `docs/aspice/problems/` and the repository issue tracker (ETB-SUP9-001 §6) |
| Change requests | ETB-SUP10-001 §6 |
| Deviations | `docs/aspice/EmbeddedTestBench_DEV*.md` |
| Baselines | Git tags (ETB-SUP8-001 §7) |

---

## 10. Review & Approval

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
