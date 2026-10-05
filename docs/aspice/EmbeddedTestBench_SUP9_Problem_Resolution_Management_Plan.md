# Problem Resolution Management Plan

*Automotive SPICE® PAM v4.0 | SUP.9 — Problem Resolution Management*

---

## 1. Document Identification & Control

| Field | Value | Field | Value |
|---|---|---|---|
| **Document ID** | ETB-SUP9-001 | **Version** | 0.3 |
| **Project** | Embedded Test Bench | **Date** | 2026-10-05 |
| **Status** | Draft | **Classification** | Internal |
| **Author** | Claude | **Reviewer** | Dermot Murphy |
| **Approver** | Dermot Murphy | **Related Process** | SUP.9 |

> Reviewer and Approver are the same person; see ETB-DEV-002.

---

## 2. Revision History

| Version | Date | Author | Description of Change |
|---|---|---|---|
| 0.1 | 2026-09-19 | Claude | Initial |
| 0.2 | 2026-10-04 | Claude | #183: product renamed to Embedded Test Bench - document file name prefix `EmbeddedTestBench_`, identifier prefix `ETB-` (was `TB-`), product name in prose. Earlier revision rows keep the names in use when they were written. |
| 0.3 | 2026-10-05 | Claude | #204: Review & Approval table points to the merge of the pull request that last changed the document, which is the review and approval (ETB-SUP8-001 §5.7); no per-change signatures or dates. |

---

## 3. Purpose & Scope

### 3.1 Purpose

This plan says what counts as a problem in Embedded Test Bench, how problems are recorded,
classified, resolved and closed, and what may never be done to make one go away.

### 3.2 Referenced Documents

| Document ID | Title | Version |
|---|---|---|
| ETB-SUP1-001 | Embedded Test Bench Quality Assurance Plan | 0.1 |
| ETB-SUP8-001 | Embedded Test Bench Configuration Management Plan | 0.1 |
| ETB-SUP10-001 | Embedded Test Bench Change Request Management Plan | 0.1 |
| ETB-MAN5-001 | Embedded Test Bench Risk Management Plan | 0.1 |
| ETB-TMPL-001 | Embedded Test Bench Work Product Review Record — Template | 0.1 |

### 3.3 Scope

Problems found anywhere: in the code, the firmware, the documents, the bench
specifications, the CI workflows, or in an instrument's behaviour that Embedded Test Bench
must accommodate.

---

## 4. What Is a Problem

A problem is any observed difference between what Embedded Test Bench does and what its
documents say it does, or any observation that a Embedded Test Bench result cannot be
trusted. Specifically:

| Kind | Examples |
|---|---|
| Functional defect | A driver returns a wrong value; a limit compares the wrong way round |
| Evidence defect | A report omits an instrument identity; a simulated run is not labelled as such |
| Document defect | A requirement contradicts another; the design describes an interface that does not exist |
| Process defect | A change merged with a red build; a document not updated with its code |
| External behaviour | An instrument does something its documentation does not describe |
| Test defect | A test passes when the thing it tests is broken; a test asserts the simulator |

A **failing test is a problem**, always. It is never an infrastructure flake
until that has been shown, and showing it means identifying what failed and why
it was unrelated to the change.

---

## 5. Classification

| Severity | Meaning | Response |
|---|---|---|
| S1 Critical | A measurement produced by Embedded Test Bench could be wrong and be believed | Stop other work; fix before anything else is merged |
| S2 Major | A documented capability does not work, or evidence is missing from a result | Fix before the affected capability is used or released |
| S3 Minor | Incorrect but not misleading; a workaround exists | Scheduled against a milestone |
| S4 Cosmetic | Wording, formatting, a broken link | Fixed opportunistically |

| Priority | Meaning |
|---|---|
| P1 | Blocking work now |
| P2 | Needed for the next milestone |
| P3 | Whenever convenient |

Severity is about consequence and is not negotiable. Priority is about order of
work and is the project lead's call.

---

## 6. Problem Record

Problems are recorded as repository issues, and problems found during a review
are additionally listed in that review record (ETB-TMPL-001 §7). A problem
record carries:

| Field | Content |
|---|---|
| **Problem ID** | ETB-PR-nnn |
| **Raised by / date** | |
| **Found in** | Revision, document ID and version, or bench run |
| **Severity / Priority** | Per §5 |
| **Observed** | What happened, verbatim where possible — output, failing assertion, instrument reply |
| **Expected** | What should have happened, and which requirement says so |
| **Reproduction** | The exact steps or command; "intermittent" is recorded as such with the frequency observed |
| **Analysis** | The cause, once known — not the symptom |
| **Resolution** | The change made, by revision |
| **Verification** | The test that now fails without the fix |
| **Related** | Risk ID if it materialised a risk; change request ID if one was needed |

---

## 7. Lifecycle

| State | Meaning | Exit |
|---|---|---|
| Open | Recorded, not yet analysed | Analysis complete |
| Analysed | Cause identified, severity confirmed | Resolution agreed |
| In progress | Being fixed | Change ready |
| Resolved | Change merged, with a test that fails without it | Verified on the affected configuration |
| Closed | Verified; documents updated | — |
| Rejected | Not a problem, with the reason recorded | — |
| Deferred | Real, not being fixed now, with the reason and the milestone recorded | Reopened at that milestone |

A problem is closed only when there is a test that would catch it again. A fix
without such a test leaves the problem free to return unnoticed, which is the
same as not having fixed it.

---

## 8. Prohibited Resolutions

None of the following closes a problem:

1. Skipping, `xfail`-ing, deleting or weakening the test that found it.
2. Re-running CI until it passes, without identifying why it failed.
3. Widening a tolerance so a measurement fits, unless the wider tolerance is
   justified against the instrument's specification and the requirement is
   changed to match, through ETB-SUP10-001.
4. Recording an unexplained failure as a flake.
5. Changing the document to match the code when the code is what is wrong.

Item 5 has a legitimate mirror image: when the *document* is wrong, changing it
is the correct fix — and it goes through the same record, so the decision about
which was wrong is visible.

---

## 9. Trend Analysis

At each milestone the open and closed problems are looked at together for
patterns: repeated problems in one element, repeated problems of one kind,
problems found late that earlier checks should have caught. A pattern is treated
as a defect in the process and raised against this plan or ETB-SUP1-001, not as a
run of bad luck.

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
