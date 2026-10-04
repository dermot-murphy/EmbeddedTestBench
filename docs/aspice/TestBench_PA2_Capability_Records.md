# Process Capability Records — Level 2

*Automotive SPICE® PAM v4.0 | PA 2.1 Performance Management, PA 2.2 Work Product Management*

---

## 1. Document Identification & Control

| Field | Value | Field | Value |
|---|---|---|---|
| **Document ID** | TB-PA2-001 | **Version** | 0.1 |
| **Project** | TestBench | **Date** | 2026-09-19 |
| **Status** | Draft | **Classification** | Internal |
| **Author** | Claude | **Reviewer** | Dermot Murphy |
| **Approver** | Dermot Murphy | **Related Process** | PA 2.1, PA 2.2 |

> Reviewer and Approver are the same person; see TB-DEV-002.

---

## 2. Revision History

| Version | Date | Author | Description of Change |
|---|---|---|---|
| 0.1 | 2026-09-19 | Claude | Initial |

---

## 3. Purpose & Scope

### 3.1 Purpose

This document records, for each Level 2 generic practice, what TestBench
actually does and what evidence exists — and rates each honestly, including
where the rating is **Partially achieved** or **Not achieved**.

It is a self-assessment, not an audit. No independent assessor has looked at
this project, and this document does not stand in for one.

### 3.2 Referenced Documents

Every document of the set; each generic practice below cites its own.

### 3.3 Scope

The processes TestBench performs: SYS.2–SYS.5, SWE.1–SWE.6, SUP.1, SUP.8,
SUP.9, SUP.10, MAN.3, MAN.5, ACQ.4.

---

## 4. Rating Scale

| Rating | Meaning | Achievement |
|---|---|---|
| **F** Fully achieved | Evidence complete; no significant weakness | > 85% |
| **L** Largely achieved | Evidence present; weaknesses recorded | > 50–85% |
| **P** Partially achieved | Some evidence; significant weaknesses | > 15–50% |
| **N** Not achieved | Little or no evidence | 0–15% |

---

## 5. PA 2.1 — Performance Management

### GP 2.1.1 — Identify the objectives for the performance of the process

**Rating: L**

Objectives are stated and measurable: TB-MAN3-001 §4 for the project,
TB-SUP1-001 §4 for quality, each with a stated measure. The weakness is that
they carry no dates (TB-MAN3-001 §7 explains why), so "on time" is not among the
things this project can judge itself on.

*Evidence:* TB-MAN3-001 §4, §7; TB-SUP1-001 §4.

### GP 2.1.2 — Plan the performance of the process

**Rating: L**

TB-MAN3-001 defines the work packages, their dependencies, the life cycle and
the milestones; the support processes each have their own plan. No schedule
exists, deliberately.

*Evidence:* TB-MAN3-001 §6, §7; TB-SUP1-001; TB-SUP8-001; TB-SUP9-001;
TB-SUP10-001; TB-MAN5-001; TB-ACQ4-001.

### GP 2.1.3 — Determine resource requirements

**Rating: P**

Tool and platform requirements are determined and pinned (TB-SVD-001 §5.5).
Human resource is one person, which is stated rather than planned. Bench
instruments are named but their availability is an open risk (TB-RISK-010),
and it is the resource gap that currently blocks milestone M6.

*Evidence:* TB-SVD-001 §5.5; TB-MAN3-001 §5; TB-MAN5-001 TB-RISK-010.

### GP 2.1.4 — Identify and make available resources

**Rating: P**

Software resources are available and pinned. **Hardware is not**: no instrument
has been attached, which is why TB-SYS4-001 §5 records sixteen cases as not
performed and TB-SYS5-001 §6 shows one hardware pass out of eight scenarios.
This is the single largest gap in the project's capability, and it is a
resource gap rather than a process one.

*Evidence:* TB-SYS4-001 §5, §6; TB-SYS5-001 §6, §7.

### GP 2.1.5 — Monitor and adjust the performance of the process

**Rating: L**

Performance is monitored continuously and mechanically: the suite and the
traceability check on every change, the firmware and style workflows on every
push, with the measures in TB-MAN3-001 §8. Adjustment happens in the open —
when a plan could not be followed, the plan changed or a deviation was recorded.
Milestone reviews are defined but none has been formally held.

*Evidence:* TB-MAN3-001 §8, §10; TB-SUP1-001 §6; CI run history.

### GP 2.1.6 — Identify and involve stakeholders

**Rating: L**

The stakeholders are identified (TB-MAN3-001 §5) and the stakeholder
requirements are recorded and traced (TB-SWE1-001 §4, TB-SYS2-001 §14). With a
one-person project, involvement is direct and continuous; there is no evidence
of stakeholder communication beyond the repository, and none is claimed.

*Evidence:* TB-MAN3-001 §5, §11; TB-SWE1-001 §4; TB-SYS2-001 §14.

---

## 6. PA 2.2 — Work Product Management

### GP 2.2.1 — Define the requirements for the work products

**Rating: L**

Requirements for work products are defined: the document layout is uniform and
stated, TB-SUP1-001 §5 lists which checks apply to which work product, and
TB-TMPL-001 §6 states what each kind of work product must satisfy. The
weakness is authorship competence, recorded as TB-DEV-001.

*Evidence:* TB-SUP1-001 §5; TB-TMPL-001 §6; TB-DEV-001.

### GP 2.2.2 — Define the requirements for documentation and control

**Rating: F**

Every work product carries a Document ID, version, status, author, reviewer,
approver and revision history. TB-SUP8-001 defines the configuration items,
versioning, baselines and status accounting, and git enforces the history.

*Evidence:* TB-SUP8-001 §4–§9; the identification block of every document.

### GP 2.2.3 — Identify, document and control the work products

**Rating: L**

All work products are in the repository under version control, identified and
versioned. Control is real: no change reaches `main` except through a pull
request with a green build.

*Evidence:* TB-SUP8-001 §5, §6; TB-SVD-001 §5.

### GP 2.2.4 — Review and adjust work products

**Rating: P**

This is the weakest practice in the set and the rating says so.

What exists: mechanical review that runs on every change — the traceability
check binds documents to code, the layering test binds code to the
architecture, 1 878 tests at 94% coverage bind behaviour to requirements. These
catch the class of defect a human reviewer most often misses, and they cannot be
skipped.

What does not exist: **a single recorded human review**. The review form
(TB-TMPL-001) and the test case form (TB-TMPL-002) ship blank. Every document in
this baseline is Draft and none has been through the review its own process
requires. Reviewer and approver are the same person, recorded as TB-DEV-002.

Filing review records for reviews that did not happen would have raised this
rating on paper and destroyed the only thing this document is for.

*Evidence:* `tests/test_traceability.py`; `tests/test_layering.py`;
TB-SWE4-002; TB-TMPL-001; TB-DEV-002; TB-SVD-001 §5.3.

---

## 7. Summary

| Practice | Rating |
|---|---|
| GP 2.1.1 Identify objectives | L |
| GP 2.1.2 Plan performance | L |
| GP 2.1.3 Determine resources | P |
| GP 2.1.4 Make resources available | P |
| GP 2.1.5 Monitor and adjust | L |
| GP 2.1.6 Involve stakeholders | L |
| GP 2.2.1 Requirements for work products | L |
| GP 2.2.2 Documentation and control | F |
| GP 2.2.3 Identify and control work products | L |
| GP 2.2.4 Review and adjust | P |

**Overall: Capability Level 2 is not achieved.** Three practices are Partially
achieved, and CL2 requires all Level 1 and Level 2 practices to be at least
Largely achieved.

### 7.1 What Would Close the Gap

| Practice | What is needed |
|---|---|
| GP 2.1.3, GP 2.1.4 | Bench instruments made available, and the integration and qualification cases performed against them |
| GP 2.2.4 | Reviews held on the work products and recorded on TB-TMPL-001; separation of reviewer and approver would close TB-DEV-002 as well |

Neither is a documentation exercise. That is the point of rating them P.

---

## 8. Work Product Index

| Process | Work product | Document ID |
|---|---|---|
| SYS.2 | System Requirements Specification | TB-SYS2-001 |
| SYS.3 | System Architecture | TB-SYS3-001 |
| SYS.4 | System Integration & Integration Test | TB-SYS4-001 |
| SYS.5 | System Qualification Test | TB-SYS5-001 |
| SWE.1 | Software Requirements Specification | TB-SWE1-001 |
| SWE.2 | Software Architecture | TB-SWE2-001 |
| SWE.3 | Software Detailed Design | TB-SWE3-001 |
| SWE.4 | Unit Verification Specification / Report | TB-SWE4-001 / TB-SWE4-002 |
| SWE.5 | Software Integration & Integration Test | TB-SWE5-001 |
| SWE.6 | Software Qualification Test | TB-SWE6-001 |
| All | Traceability Matrix | TB-RTM-001 |
| MAN.3 | Project Management Plan | TB-MAN3-001 |
| MAN.5 | Risk Management Plan | TB-MAN5-001 |
| SUP.1 | Quality Assurance Plan | TB-SUP1-001 |
| SUP.8 | Configuration Management Plan / SVD | TB-SUP8-001 / TB-SVD-001 |
| SUP.9 | Problem Resolution Management Plan | TB-SUP9-001 |
| SUP.10 | Change Request Management Plan | TB-SUP10-001 |
| ACQ.4 | Supplier Monitoring Plan | TB-ACQ4-001 |
| SWE.3/4, SUP.1 | C coding standard, style guide, standards applicability | TB-STD-002, TB-STY-001, TB-STD-001 |
| SUP.1 | Repository Analysis Report | TB-ANA-001 |
| GP 2.2.3 | Review and test case templates | TB-TMPL-001, TB-TMPL-002 |
| GP 2.1, GP 2.2 | Deviations | TB-DEV-001, TB-DEV-002 |

---

## 9. Review & Approval

| Role | Name | Signature / Electronic Approval | Date |
|---|---|---|---|
| Author | Claude | Approved | 2026-09-19 |
| Reviewer | Dermot Murphy | — | *pending* |
| Approver | Dermot Murphy | — | *pending* |
