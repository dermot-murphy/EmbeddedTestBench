# Deviation Record — Reviewer Independence

*Automotive SPICE® PAM v4.0 | GP 2.2.3 — Review and Adjust Work Products*

---

## 1. Document Identification & Control

| Field | Value | Field | Value |
|---|---|---|---|
| **Document ID** | ETB-DEV-002 | **Version** | 0.3 |
| **Project** | Embedded Test Bench | **Date** | 2026-10-05 |
| **Status** | Draft | **Classification** | Internal |
| **Author** | Claude | **Reviewer** | Dermot Murphy |
| **Approver** | Dermot Murphy | **Related Process** | GP 2.2.3 |

---

## 2. Revision History

| Version | Date | Author | Description of Change |
|---|---|---|---|
| 0.1 | 2026-09-19 | Claude | Initial |
| 0.2 | 2026-10-04 | Claude | #183: product renamed to Embedded Test Bench - document file name prefix `EmbeddedTestBench_`, identifier prefix `ETB-` (was `TB-`), product name in prose. Earlier revision rows keep the names in use when they were written. |
| 0.3 | 2026-10-05 | Claude | #204: §4 states how review and approval are given - Reviewer and Approver remain the same person by decision, both given in one act, the merge of the pull request; evidence is the pull request, its CI result and its merge record. §5 states that the compensating measures remain. §7 points to the merge (ETB-SUP8-001 §5.7). |

---

## 3. Deviation Summary

| Field | Value |
|---|---|
| **Deviation ID** | ETB-DEV-002 |
| **Severity** | SEV-3 Minor |
| **Standard Clause** | ASPICE PAM v4.0, GP 2.2.3 — Review and Adjust Work Products |
| **Affected Work Products** | Every document in `docs/aspice/` |
| **Disposition** | **Accepted with justification** |

---

## 4. Non-Conformance Description

GP 2.2.3 expects work products to be reviewed against their requirements by
parties who did not produce them, and expects reviewer and approver to be
distinguishable roles.

Embedded Test Bench has one human team member. In every document of this set, the
Reviewer and the Approver are the same person: Dermot Murphy. Independence of
review in the organisational sense is therefore not achieved, and cannot be
while the team is one person.

This is stated in the identification block of each document rather than left
for a reader to notice.

**How review and approval are given (owner's decision, 2026-10-05, #204).**

- The Reviewer and the Approver remain the same person, Dermot Murphy, by
  decision. There is no second reviewer, and no bot or machine account gives
  approvals.
- Review and approval are given in a single act: the merge of the pull request
  that carries the change. The owner merges it, or explicitly instructs its
  merge, after examining the change and its CI result (ETB-SUP8-001 §5.7).
- The evidence is the pull request, its CI result and its merge record: who
  merged it, when, and the merge commit. Each document's Review & Approval table
  points to that record rather than carrying a signature.

---

## 5. Justification for Acceptance

**The author and the reviewer are genuinely different parties**, which is the
part of GP 2.2.3 that does the work. Documents are drafted by the model and
reviewed by the engineer; neither is reviewing its own output. The weakness is
that reviewer and *approver* coincide, not that review is absent.

**Review is against something checkable.** These documents do not stand on a
reviewer's opinion alone. A reviewer who wants to know whether SWE.1 is honest
can run the suite: the traceability check reads the requirements out of the
document and fails if the code cites something the document does not declare, or
if the matrix omits something the document does. That mechanism does not care
who wrote or reviewed anything.

**The scope of what independence would protect is small.** Embedded Test Bench is a test
tool (ETB-DEV-001 §5). A defect in it that survives review shows up as a bench
measurement that cannot be reproduced, not as a fault in a delivered vehicle.

**The compensating measures remain in force.** The automated checks — the
required status checks that must be green before any merge (ETB-SUP8-001 §5.5)
— and the traceability tests apply to every change, and the author is a
different party from the reviewer (ETB-DEV-001). Giving review and approval in
one act, the merge, does not weaken them: it ties the approval to a record that
already exists for every change.

**The alternative is worse.** Inventing a second reviewer's name, or recording a
review meeting that did not take place, would corrupt the record in exchange for
a formality. This project's whole argument — in the tool and in its documents —
is that evidence nobody can challenge is not evidence.

---

## 6. Corrective Action

None while the team is one person. Should a second engineer join the project:

1. reviewer and approver are separated for all new and revised documents;
2. the documents carrying this note are reissued without it as they are next
   revised, rather than in a sweep;
3. this deviation is closed with the date the separation took effect.

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
| ETB-DEV-001 | Embedded Test Bench AI Authorship Deviation | 0.1 |
| ETB-SUP1-001 | Embedded Test Bench Quality Assurance Plan | 0.1 |
| ETB-PA2-001 | Embedded Test Bench Process Capability Records | 0.1 |
