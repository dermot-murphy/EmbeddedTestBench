<img src="../../assets/brand/svg/logos/embeddedtestbench-logo-compact.svg" alt="Embedded Test Bench" width="240">

# Quality Assurance Plan

*Automotive SPICE® PAM v4.0 | SUP.1 — Quality Assurance*

---

## 1. Document Identification & Control

| Field | Value | Field | Value |
|---|---|---|---|
| **Document ID** | ETB-SUP1-001 | **Version** | [latest, §2](#2-revision-history) |
| **Project** | Embedded Test Bench | **Date** | [latest, §2](#2-revision-history) |
| **Status** | [by location, ETB-SUP1-001 §6.3](#63-document-status) | **Classification** | Internal |
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
| 0.5 | 2026-10-25 | Claude | #210: Version and Date in the identification table are links to the last revision history row, which holds them (ETB-SUP8-001 §6.2). |
| next | 2026-11-17 | Claude | #371: the Status cell links to the status rule, ETB-SUP1-001 §6.3. A document's status follows from where it is in the repository (Released, Agreed, In review, In work) and is not written in by hand. §6.5 adds the QA review that the PR Review session posts on every pull request, with checks C1 to C6 per work product, as the per-pull-request QA record; the merge remains the approval. §6.6 added: content requirements per work product type (GP 2.2.1), for content added or changed from #371 on. §5, §7 and §9 updated to match. Review round 1 (PR #381): §6.3 statuses are exclusive, in order Released, Agreed, In review, In work; §6.5 says what the QA reviewer is given. Review round 2: the status is found from the commit that last changed the file. |

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
| ASPICE documents (`docs/aspice/`) | QA review on the pull request and approval by its merge (§6.5); status by location (§6.3); content as §6.6; traceability check for the requirement, design and test documents |
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

### 6.3 Document Status

A document's status is not written into it by hand. It follows from where the
document is in the repository, and the Status cell of every identification
table links here.

Status belongs to a copy of the document at a commit, not to the document in
general. The first row that applies is the status:

| Status | The copy is | What makes it so |
|---|---|---|
| Released | In the tree of a release tag `v<version>` on `main` | The tag (ETB-SUP8-001 §7) |
| Agreed | On `develop`, merged since the last release tag | The merge of the pull request that last changed it: the Reviewer's and Approver's approval (§6.5, ETB-SUP8-001 §5.7) |
| In review | On any other branch, in an open pull request | The pull request; the QA review on it (§6.5) |
| In work | On any other branch with no open pull request | Nothing yet: it has not been offered for review |

A document on `develop` that has not changed since a release is the same text
as in the tag, so it is Released. A copy on a branch is In review or In work
even when the same text is Agreed on `develop`. The status of the copy a reader
holds is found from the commit that last changed it, not from the cell. Take
`C=$(git log -1 --format=%H <commit> -- <file>)`, the last change to the file
at the commit the reader holds; then `git tag --contains $C` (Released if it
names a release tag), `git branch --contains $C` (Agreed if it names
`develop`), and the open pull requests for the branch, give it.

Before a change to a document is agreed, it passes the QA review in §6.5, and
Critical and Major findings are closed. There is no separate step from Draft to
Approved; the merge is that step, for every change. A review recorded on a
completed copy of ETB-TMPL-001 is also accepted.

### 6.4 At Each Milestone

Quality objectives in §4 are measured and recorded; risks are reviewed
(ETB-MAN5-001 §7); open bench-confirmation items are counted.

### 6.5 Review and Approval by Pull Request Merge

Every change reaches `develop` or `main` through a pull request
(ETB-SUP8-001 §5.1). Merging that pull request is the Reviewer's approval and
the Approver's approval of everything in it (ETB-SUP8-001 §5.7, ETB-DEV-002).
**A pull request merge is therefore an accepted form of review record.**

**QA review, on every pull request.** Before the pull request is merged, the QA
reviewer reviews it and posts the result on the pull request as a review. The QA
reviewer is the *PR Review* session: a Claude Code session separate from the
session that wrote the change, given the pull request and the form of review in this
section, and doing no authoring on it (ETB-DEV-002 §4 records what this independence does and does
not give). The review:

1. names each work product the pull request changes;
2. gives, for each, the result of checks C1 to C6 of ETB-TMPL-001 §6.1, and of
   the checks in §6.2 to §6.5 for its type, as a table of pass, fail or n/a;
3. raises each failed check as a finding: a review comment on the line or
   section, with its severity (ETB-TMPL-001 §7);
4. states the verdict: no findings, or findings to resolve.

The author resolves each finding with a change or a reply, and resolves the
thread. When the change is substantial, the QA reviewer reviews again. This
review is the per-pull-request QA record (SUP.1.BP3) and the record that C1 to
C6 were applied (GP 2.2.4).

**Approval, by the merge.** Before merging, the Reviewer:

1. confirms that every required status check is green (ETB-SUP8-001 §5.5);
2. reads the QA review and the resolution of its findings, and applies checks C1
   to C6 to the change;
3. raises any further finding on the pull request, and as a problem
   (ETB-SUP9-001) when it is Critical or Major, and does not merge until it is
   resolved.

The record is the pull request (its description, changes, QA review and
comments), its CI result, and its merge record: who merged it, when, and the
merge commit. The Review & Approval table of each document points to that record
and is not filled in. A merge without a QA review on the pull request is a
non-conformance, raised under ETB-SUP9-001.

### 6.6 Content Requirements per Work Product Type

What each type of work product must contain (GP 2.2.1). The layout every
controlled document shares is in ETB-SUP8-001 §6. The checks in ETB-TMPL-001 §6
are applied against this table.

The table applies to content added or changed from #371 (2026-11-17) on. Content
written before then does not all meet it; those gaps are the audit findings of
ETB-SUP1-002 and are tracked on their issues (#362 to #370, #372 to #376 and
#379). A pull request that changes such content brings what it changes up to
the table.

| Type | Documents | Must contain |
|---|---|---|
| Requirements specification | ETB-SYS2-001, ETB-SWE1-001 | Each requirement with a unique ID, its text, verification method and criterion, priority and release; its source (parent requirement or stakeholder need); a recorded analysis of correctness, feasibility and verifiability; the context or operating environment the requirements apply to |
| Architecture | ETB-SYS3-001, ETB-SWE2-001 | Every element with its responsibility and interfaces; static and dynamic views; the requirements allocated to each element; design decisions with the alternatives considered and the criteria used; resource use where it matters |
| Detailed design | ETB-SWE3-001, ETB-SWE3-002 | A catalogue of units, each with its interface, behaviour and the code that implements it; dynamic behaviour of units with state or timing; trace from unit to architecture element and to code |
| Interface specification | ETB-IF-001, ETB-IF-002 | The interface as built: commands, parameters, units, timing and errors; which facts are confirmed on hardware and which are not |
| Verification specification | ETB-SWE4-001, ETB-SWE5-001, ETB-SWE6-001, ETB-SYS4-001, ETB-SYS5-001 | Each case with a unique ID, its preconditions, steps and expected result, and the requirements or elements it verifies; the selection rule, including what is rerun for a change (regression); entry and exit criteria |
| Verification report | ETB-SWE4-002, ETB-SYS5-002 | The baseline tested; the result of each case, with the record it rests on; totals that agree with the case results; open items; whether each result was simulated or on hardware |
| Traceability matrix | ETB-RTM-001 | Trace in both directions for each level, and the mechanical check that keeps it current |
| Plan | ETB-MAN3-001, ETB-MAN5-001, ETB-SUP1-001, ETB-SUP8-001, ETB-SUP9-001, ETB-SUP10-001, ETB-ACQ4-001 | Objectives and strategy of the process; activities, responsibilities, resources and schedule; the records kept and where |
| Report or record | ETB-ANA-001, ETB-PA2-001, ETB-SUP1-002, ETB-SVD-001 | The baseline or date it describes; each statement with the evidence it rests on |
| Deviation | ETB-DEV-001, ETB-DEV-002 | The clause not met, why, the compensating measures, and what would close it |
| Standard, guide or template | ETB-STD-001, ETB-STD-002, ETB-STY-001, ETB-TMPL-001, ETB-TMPL-002 | The rules or fields, each with its rationale where it is not obvious |

---

## 7. Evidence and Honesty

The following rules are the ones this project would rather break a schedule
than break:

1. **A test that was not run is not recorded as passed.** Reports state whether
   a run was simulated.
2. **A review that was not held is not recorded.** A QA review is recorded as a
   review on the pull request (§6.5); the Reviewer's review and approval are
   recorded by the merge of the pull request, or on a completed copy of
   ETB-TMPL-001, and in no other way. No approval is entered in a document's Review & Approval table,
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
| QA review records | The QA review posted on each pull request (§6.5) |
| Review and approval records | The merged pull request, its CI result and its merge record (§6.5); a completed ETB-TMPL-001 copy, when one is used, in `docs/aspice/reviews/` |
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
