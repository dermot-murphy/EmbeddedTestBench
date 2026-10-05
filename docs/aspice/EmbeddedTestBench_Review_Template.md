# Work Product Review Record — Template

*Automotive SPICE® PAM v4.0 | GP 2.2.3, SUP.1, SUP.9*

---

## 1. Document Identification & Control

| Field | Value | Field | Value |
|---|---|---|---|
| **Document ID** | ETB-TMPL-001 | **Version** | 0.4 |
| **Project** | Embedded Test Bench | **Date** | 2026-10-05 |
| **Status** | Draft | **Classification** | Internal |
| **Author** | Claude | **Reviewer** | Dermot Murphy |
| **Approver** | Dermot Murphy | **Related Process** | GP 2.2.3 |

> Reviewer and Approver are the same person; see ETB-DEV-002.

---

## 2. Revision History

| Version | Date | Author | Description of Change |
|---|---|---|---|
| 0.1 | 2026-09-19 | Claude | Initial |
| 0.2 | 2026-10-04 | Claude | #183: product renamed to Embedded Test Bench - document file name prefix `EmbeddedTestBench_`, identifier prefix `ETB-` (was `TB-`), product name in prose. Earlier revision rows keep the names in use when they were written. |
| 0.3 | 2026-10-04 | Claude | #187: C4 names the revision history order - oldest entry first (ETB-SUP8-001 §6.2). |
| 0.4 | 2026-10-05 | Claude | #204: §3.1 states that a pull request merge is an accepted form of review record and that checks C1 to C6 are what the Reviewer applies before merging. §9 points to the merge of the pull request that adds or last changes the record (ETB-SUP8-001 §5.7). |

---

## 3. Purpose & Scope

### 3.1 Purpose

This is the form a Embedded Test Bench work product review is recorded on. It is a
**template**: copy it, fill it in, and store the completed copy under
`docs/aspice/reviews/` named `<work-product-id>_Review_<date>.md`.

No completed review records are shipped with this document set. A review that
did not happen is not recorded as though it had (ETB-SUP1-001 §7).

**A pull request merge is also an accepted form of review record**
(ETB-SUP1-001 §6.5, ETB-SUP8-001 §5.7). Checks C1 to C6 in §6.1 are what the
Reviewer applies to each work product in a pull request before merging it, and
the merge is the Reviewer's and the Approver's approval. A finding is raised on
the pull request, or as a problem under ETB-SUP9-001 when it is Critical or
Major, and the pull request is not merged until it is resolved. No copy of this
form is needed for such a review; the pull request, its CI result and its merge
record are the record.

### 3.2 Referenced Documents

| Document ID | Title | Version |
|---|---|---|
| ETB-SUP1-001 | Embedded Test Bench Quality Assurance Plan | 0.1 |
| ETB-SUP9-001 | Embedded Test Bench Problem Resolution Management Plan | 0.1 |
| ETB-DEV-002 | Embedded Test Bench Independent Review Deviation | 0.1 |

### 3.3 Scope

Applies to every work product listed in ETB-SUP1-001 §5 as requiring review:
the ASPICE documents, the source under `benchtools/` and `firmware/`, and the
bench specifications under `specs/`.

---

## 4. Review Identification

| Field | Value |
|---|---|
| **Review ID** | *ETB-REV-nnn* |
| **Work Product** | *document ID or path* |
| **Work Product Version** | *e.g. 0.1* |
| **Review Type** | *Walkthrough / Inspection / Technical review / Checklist-based* |
| **Review Date** | *YYYY-MM-DD* |
| **Moderator** | *name* |
| **Author** | *name* |
| **Reviewers** | *names* |
| **Effort (person-hours)** | *n* |

---

## 5. Entry Criteria

| # | Criterion | Met | Evidence |
|---|---|---|---|
| E1 | The work product is complete enough to review (no placeholder sections) | ☐ | |
| E2 | The documents it derives from are approved, or their status is stated | ☐ | |
| E3 | `pytest` passes on the reviewed revision | ☐ | *run output* |
| E4 | The traceability check passes (`tests/test_traceability.py`) | ☐ | |
| E5 | Reviewers have had the work product for at least one working day | ☐ | |

A review that starts with an unmet entry criterion records which one and why it
was started anyway.

---

## 6. Checklist

Tick, cross, or mark n/a. A cross needs a finding in §7.

### 6.1 All work products

| # | Question | Result |
|---|---|---|
| C1 | Does it say what it is for, and for whom? | |
| C2 | Is every claim in it checkable by someone who was not there? | |
| C3 | Is each statement traceable up to what it satisfies and down to what satisfies it? | |
| C4 | Are the identification block, revision history and status filled in and correct, with the revision history oldest entry first (ETB-SUP8-001 §6.2)? | |
| C5 | Are referenced documents cited by ID and version? | |
| C6 | Does it distinguish what has been confirmed on hardware from what has not? | |

### 6.2 Requirements documents (SYS.2, SWE.1)

| # | Question | Result |
|---|---|---|
| R1 | Is each requirement singular, unambiguous and verifiable? | |
| R2 | Does each requirement have a verification method and a test that covers it? | |
| R3 | Are the requirement's units, ranges and tolerances stated where it makes a numeric claim? | |
| R4 | Is each requirement free of design? | |
| R5 | Do the requirements between them cover the stakeholder needs they claim to? | |

### 6.3 Architecture and design (SYS.3, SWE.2, SWE.3)

| # | Question | Result |
|---|---|---|
| D1 | Is every element's responsibility stated, and disjoint from its siblings'? | |
| D2 | Is every interface specified — arguments, returns, errors, units? | |
| D3 | Are the dynamic aspects (sequence, timing, resource use) described where they matter? | |
| D4 | Does each element trace to requirements, and each requirement to an element? | |
| D5 | Are the design decisions that could reasonably have gone the other way recorded with their reason? | |

### 6.4 Test documents (SWE.4, SWE.5, SWE.6, SYS.4, SYS.5)

| # | Question | Result |
|---|---|---|
| T1 | Does each test case state its preconditions, inputs, steps and expected result? | |
| T2 | Would the test fail if the thing it tests were broken? | |
| T3 | Are negative and boundary cases present, not only the happy path? | |
| T4 | Is a simulated result reported as simulated? | |
| T5 | Does the test avoid asserting the simulator's behaviour in place of the instrument's? | |

### 6.5 Source code

| # | Question | Result |
|---|---|---|
| S1 | Does it match the detailed design, or has the design been updated with it? | |
| S2 | Does C code conform to ETB-STY-001 and the MISRA C:2012 subset in ETB-STD-002? | |
| S3 | Does it fail loudly rather than continue on an unsatisfiable request? | |
| S4 | Are the error paths tested, not only the successful ones? | |
| S5 | Are magic numbers named, and are units in the names or the types? | |

---

## 7. Findings

| # | Location | Severity | Finding | Raised as | Disposition |
|---|---|---|---|---|---|
| F1 | *file:line or §* | *Critical / Major / Minor / Editorial* | *what is wrong, and why it matters* | *problem ID (ETB-PR-nnn) or "fixed in review"* | *Accepted / Rejected / Deferred* |

**Severity:**

| Severity | Meaning |
|---|---|
| Critical | The work product asserts something untrue, or would cause a wrong measurement to be believed |
| Major | A requirement, interface or test is missing, unverifiable or contradicts another document |
| Minor | Incomplete or unclear, but not misleading |
| Editorial | Spelling, formatting, a broken link |

Critical and Major findings are raised as problems under ETB-SUP9-001 and closed
before the work product is approved. Minor and Editorial findings may be
deferred with a recorded reason.

---

## 8. Exit Criteria & Result

| # | Criterion | Met |
|---|---|---|
| X1 | Every Critical and Major finding is closed or formally deferred by the approver | ☐ |
| X2 | The work product has been updated and its revision history reflects this review | ☐ |
| X3 | Traceability is intact after the changes (`pytest tests/test_traceability.py`) | ☐ |
| X4 | The full suite passes on the revised work product | ☐ |

**Result:** *Accepted / Accepted with actions / Rework and re-review*

**Follow-up review required:** *yes (date) / no*

---

## 9. Review & Approval

Approvals are not entered in this table. A review record made from this
template, like this template itself, is reviewed and approved by the merge of
the pull request that adds or last changes it (ETB-SUP8-001 §5.7). The evidence
is the pull request, its CI result and its merge record: who merged it, when,
and the merge commit.

| Role | Name | Recorded by |
|---|---|---|
| Author | *name* | The commits in the pull request |
| Reviewer | *name* | The merge of the pull request that adds or last changes the record |
| Approver | *name* | The merge of the pull request that adds or last changes the record |
