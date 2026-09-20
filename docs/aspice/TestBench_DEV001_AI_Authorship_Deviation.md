# Deviation Record — AI Authorship of Work Products

*Automotive SPICE® PAM v4.0 | GP 2.1.1, GP 2.2.1 — Process Performance and Work Product Management*

---

## 1. Document Identification & Control

| Field | Value | Field | Value |
|---|---|---|---|
| **Document ID** | TB-DEV-001 | **Version** | 0.1 |
| **Project** | TestBench | **Date** | 2026-09-19 |
| **Status** | Draft | **Classification** | Internal |
| **Author** | Claude | **Reviewer** | Dermot Murphy |
| **Approver** | Dermot Murphy | **Related Process** | GP 2.1.1, GP 2.2.1 |

---

## 2. Revision History

| Version | Date | Author | Description of Change |
|---|---|---|---|
| 0.1 | 2026-09-19 | Claude | Initial |

---

## 3. Deviation Summary

| Field | Value |
|---|---|
| **Deviation ID** | TB-DEV-001 |
| **Severity** | SEV-3 Minor |
| **Standard Clause** | ASPICE PAM v4.0, GP 2.1.1 (plan and monitor process performance), GP 2.2.1 (define requirements for work products) |
| **Affected Work Products** | Every document in `docs/aspice/`, the source under `benchtools/`, the firmware under `firmware/`, and the test suite |
| **Disposition** | **Accepted with justification** |

---

## 4. Non-Conformance Description

Automotive SPICE assumes work products are produced by identified competent
people, and that competence is a thing the organisation manages (GP 2.1.5). The
work products of TestBench are written by a large language model — Claude —
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

**The tool is a test tool, not deliverable software.** TestBench carries no
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

None required while TestBench remains a test tool. If any part of it were ever
proposed for use inside delivered software, this deviation would have to be
closed before that happened, by:

1. re-review of every affected work product by a competent named engineer;
2. a competence record for that engineer against the affected processes;
3. reissue of the affected documents under that engineer's authorship.

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
| TB-DEV-002 | TestBench Independent Review Deviation | 0.1 |
| TB-SUP1-001 | TestBench Quality Assurance Plan | 0.1 |
| TB-MAN3-001 | TestBench Project Management Plan | 0.1 |
| TB-PA2-001 | TestBench Process Capability Records | 0.1 |
