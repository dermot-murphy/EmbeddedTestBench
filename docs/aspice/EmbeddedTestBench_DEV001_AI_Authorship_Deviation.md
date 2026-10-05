# Deviation Record — AI Authorship of Work Products

*Automotive SPICE® PAM v4.0 | GP 2.1.1, GP 2.2.1 — Process Performance and Work Product Management*

---

## 1. Document Identification & Control

| Field | Value | Field | Value |
|---|---|---|---|
| **Document ID** | ETB-DEV-001 | **Version** | 0.3 |
| **Project** | Embedded Test Bench | **Date** | 2026-10-05 |
| **Status** | Draft | **Classification** | Internal |
| **Author** | Claude | **Reviewer** | Dermot Murphy |
| **Approver** | Dermot Murphy | **Related Process** | GP 2.1.1, GP 2.2.1 |

---

## 2. Revision History

| Version | Date | Author | Description of Change |
|---|---|---|---|
| 0.1 | 2026-09-19 | Claude | Initial |
| 0.2 | 2026-10-04 | Claude | #183: product renamed to Embedded Test Bench - document file name prefix `EmbeddedTestBench_`, identifier prefix `ETB-` (was `TB-`), product name in prose. Earlier revision rows keep the names in use when they were written. |
| 0.3 | 2026-10-05 | Claude | #204: Review & Approval table points to the merge of the pull request that last changed the document, which is the review and approval (ETB-SUP8-001 §5.7); no per-change signatures or dates. |

---

## 3. Deviation Summary

| Field | Value |
|---|---|
| **Deviation ID** | ETB-DEV-001 |
| **Severity** | SEV-3 Minor |
| **Standard Clause** | ASPICE PAM v4.0, GP 2.1.1 (plan and monitor process performance), GP 2.2.1 (define requirements for work products) |
| **Affected Work Products** | Every document in `docs/aspice/`, the source under `benchtools/`, the firmware under `firmware/`, and the test suite |
| **Disposition** | **Accepted with justification** |

---

## 4. Non-Conformance Description

Automotive SPICE assumes work products are produced by identified competent
people, and that competence is a thing the organisation manages (GP 2.1.5). The
work products of Embedded Test Bench are written by a large language model — Claude —
acting on the instructions of one engineer, Dermot Murphy, who directs, reviews
and accepts them.

Three specific expectations are not met in the way the standard assumes:

1. **Author competence cannot be evidenced by record.** There is no CV, no
   training record and no qualification behind the author field of these
   documents. The author is a model invoked per session.
2. **Authorship is not stable between sessions.** The same name in the author
   field does not denote continuity of knowledge: each session begins without
   memory of the last, and what carries over is only what is written down.
3. **The author cannot be held accountable.** Accountability for every work
   product rests with the human approver, not with the named author.

---

## 5. Justification for Acceptance

**The tool is a test tool, not deliverable software.** Embedded Test Bench carries no
ASIL classification and ships in no vehicle. What it produces is evidence about
*other* software, and the integrity of that evidence is checked by the
mechanisms in §5.3 rather than by the pedigree of whoever wrote the code.

**The engineer is the accountable party and reviews everything.** Dermot Murphy
directs the work, reviews each change, and approves each work product. The model
is used the way a compiler or a code generator is used: its output is an input
to a human decision, not a substitute for one.

**The process compensates where authorship cannot be evidenced.** Competence
arguments are replaced by checks that run:

| Concern | Compensating control |
|---|---|
| The author may claim something untrue | `tests/test_traceability.py` fails the build if a requirement, design unit or test group is cited without being declared, or declared without appearing in the matrix |
| The author may not know what the code does | 1 878 automated tests, 94% statement coverage, and every instrument modelled by a simulator that behaves like the instrument rather than echoing its replies |
| Sessions do not remember each other | Everything relied upon is written into these documents or into the repository; nothing important lives only in a conversation |
| The author may assert a measurement it did not make | Each element's notes carry explicit bench-confirmation items for everything that has not been checked against hardware, and a simulated run is disclosed as simulated in every report format |

**The deviation is disclosed rather than hidden.** The author field of every
document names Claude. A reader who wishes to weigh that has been told.

---

## 6. Corrective Action

None required while Embedded Test Bench remains a test tool. If any part of it were ever
proposed for use inside delivered software, this deviation would have to be
closed before that happened, by:

1. re-review of every affected work product by a competent named engineer;
2. a competence record for that engineer against the affected processes;
3. reissue of the affected documents under that engineer's authorship.

---

## 7. Approval

Review and approval of this document are not entered in this table. They are
given by the merge of the pull request that last changed the document, and that
merge is the record (ETB-SUP8-001 §5.7). The evidence is the pull request, its
CI result and its merge record: who merged it, when, and the merge commit. The
last row of the revision history names the issue, and the issue links the pull
request.

| Role | Name | Recorded by |
|---|---|---|
| Raised by | Claude | The commits in the pull request |
| Quality Assurance | Dermot Murphy | The merge of the pull request that last changed this document |
| Approver | Dermot Murphy | The merge of the pull request that last changed this document |

---

## 8. Referenced Documents

| Document ID | Title | Version |
|---|---|---|
| ETB-DEV-002 | Embedded Test Bench Independent Review Deviation | 0.1 |
| ETB-SUP1-001 | Embedded Test Bench Quality Assurance Plan | 0.1 |
| ETB-MAN3-001 | Embedded Test Bench Project Management Plan | 0.1 |
| ETB-PA2-001 | Embedded Test Bench Process Capability Records | 0.1 |
