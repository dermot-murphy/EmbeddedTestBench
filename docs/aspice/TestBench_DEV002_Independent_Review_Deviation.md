# Deviation Record — Reviewer Independence

*Automotive SPICE® PAM v4.0 | GP 2.2.3 — Review and Adjust Work Products*

---

## 1. Document Identification & Control

| Field | Value | Field | Value |
|---|---|---|---|
| **Document ID** | TB-DEV-002 | **Version** | 0.1 |
| **Project** | TestBench | **Date** | 2026-09-19 |
| **Status** | Draft | **Classification** | Internal |
| **Author** | Claude | **Reviewer** | Dermot Murphy |
| **Approver** | Dermot Murphy | **Related Process** | GP 2.2.3 |

---

## 2. Revision History

| Version | Date | Author | Description of Change |
|---|---|---|---|
| 0.1 | 2026-09-19 | Claude | Initial |

---

## 3. Deviation Summary

| Field | Value |
|---|---|
| **Deviation ID** | TB-DEV-002 |
| **Severity** | SEV-3 Minor |
| **Standard Clause** | ASPICE PAM v4.0, GP 2.2.3 — Review and Adjust Work Products |
| **Affected Work Products** | Every document in `docs/aspice/` |
| **Disposition** | **Accepted with justification** |

---

## 4. Non-Conformance Description

GP 2.2.3 expects work products to be reviewed against their requirements by
parties who did not produce them, and expects reviewer and approver to be
distinguishable roles.

TestBench has one human team member. In every document of this set, the
Reviewer and the Approver are the same person: Dermot Murphy. Independence of
review in the organisational sense is therefore not achieved, and cannot be
while the team is one person.

This is stated in the identification block of each document rather than left
for a reader to notice.

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

**The scope of what independence would protect is small.** TestBench is a test
tool (TB-DEV-001 §5). A defect in it that survives review shows up as a bench
measurement that cannot be reproduced, not as a fault in a delivered vehicle.

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

| Role | Name | Signature / Electronic Approval | Date |
|---|---|---|---|
| Raised by | Claude | Approved | 2026-09-19 |
| Quality Assurance | Dermot Murphy | — | *pending* |
| Approver | Dermot Murphy | — | *pending* |

---

## 8. Referenced Documents

| Document ID | Title | Version |
|---|---|---|
| TB-DEV-001 | TestBench AI Authorship Deviation | 0.1 |
| TB-SUP1-001 | TestBench Quality Assurance Plan | 0.1 |
| TB-PA2-001 | TestBench Process Capability Records | 0.1 |
