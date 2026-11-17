<img src="../../assets/brand/svg/logos/embeddedtestbench-logo-compact.svg" alt="Embedded Test Bench" width="240">

# Process Capability Records — Level 2

*Automotive SPICE® PAM v4.0 | PA 2.1 Performance Management, PA 2.2 Work Product Management*

---

## 1. Document Identification & Control

| Field | Value | Field | Value |
|---|---|---|---|
| **Document ID** | ETB-PA2-001 | **Version** | [latest, §2](#2-revision-history) |
| **Project** | Embedded Test Bench | **Date** | [latest, §2](#2-revision-history) |
| **Status** | [by location, ETB-SUP1-001 §6.3](EmbeddedTestBench_SUP1_Quality_Assurance_Plan.md#63-document-status) | **Classification** | Internal |
| **Author** | Claude | **Reviewer** | Dermot Murphy |
| **Approver** | Dermot Murphy | **Related Process** | PA 2.1, PA 2.2 |

> Reviewer and Approver are the same person; see ETB-DEV-002.

---

## 2. Revision History

| Version | Date | Author | Description of Change |
|---|---|---|---|
| 0.1 | 2026-09-19 | Claude | Initial |
| 0.2 | 2026-10-04 | Claude | #183: product renamed to Embedded Test Bench - document file name prefix `EmbeddedTestBench_`, identifier prefix `ETB-` (was `TB-`), product name in prose. Earlier revision rows keep the names in use when they were written. |
| 0.3 | 2026-10-05 | Claude | #204: Review & Approval table points to the merge of the pull request that last changed the document, which is the review and approval (ETB-SUP8-001 §5.7); no per-change signatures or dates. |
| 0.4 | 2026-10-05 | Claude | #194: the compact brand logo added above the title, the same line in every controlled document (ETB-SUP8-001 §6.3). |
| 0.5 | 2026-10-25 | Claude | #210: Version and Date in the identification table are links to the last revision history row, which holds them (ETB-SUP8-001 §6.2). |
| next | 2026-11-17 | Claude | #371: the Status cell links to the status rule, ETB-SUP1-001 §6.3. A document's status follows from where it is in the repository (Released, Agreed, In review, In work) and is not written in by hand. GP 2.2.1 cites the content requirements, ETB-SUP1-001 §6.6. GP 2.2.4 no longer says no review exists: it describes review by merge (#204), the QA review per pull request (#371) and the status rule. The ratings are not changed here; the re-audit sets them (#380). §8 lists the templates under GP 2.2.4. |
| next | 2026-11-17 | Claude | #374: §8 work product index lists ETB-SUP8-002, the configuration audit and recovery check record. |
| next | 2026-11-17 | Claude | #373: §8 lists ETB-SUP1-003 and ETB-DEV-003. |
| next | 2026-11-17 | Claude | #372: §8 lists ETB-MAN3-002. |
| next | 2026-11-17 | Claude | #362: GP 2.1.4 says the instruments have been available since 2026-10-04 and that the integration cases' bench time is deferred by ETB-DEV-004; §8 lists ETB-DEV-004. The rating is not changed here (#380). |

---

## 3. Purpose & Scope

### 3.1 Purpose

This document records, for each Level 2 generic practice, what Embedded Test Bench
actually does and what evidence exists — and rates each honestly, including
where the rating is **Partially achieved** or **Not achieved**.

It is a self-assessment, not an audit. No independent assessor has looked at
this project, and this document does not stand in for one.

### 3.2 Referenced Documents

Every document of the set; each generic practice below cites its own.

### 3.3 Scope

The processes Embedded Test Bench performs: SYS.2–SYS.5, SWE.1–SWE.6, SUP.1, SUP.8,
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

Objectives are stated and measurable: ETB-MAN3-001 §4 for the project,
ETB-SUP1-001 §4 for quality, each with a stated measure. The weakness is that
they carry no dates (ETB-MAN3-001 §7 explains why), so "on time" is not among the
things this project can judge itself on.

*Evidence:* ETB-MAN3-001 §4, §7; ETB-SUP1-001 §4.

### GP 2.1.2 — Plan the performance of the process

**Rating: L**

ETB-MAN3-001 defines the work packages, their dependencies, the life cycle and
the milestones; the support processes each have their own plan. No schedule
exists, deliberately.

*Evidence:* ETB-MAN3-001 §6, §7; ETB-SUP1-001; ETB-SUP8-001; ETB-SUP9-001;
ETB-SUP10-001; ETB-MAN5-001; ETB-ACQ4-001.

### GP 2.1.3 — Determine resource requirements

**Rating: P**

Tool and platform requirements are determined and pinned (ETB-SVD-001 §5.5).
Human resource is one person, which is stated rather than planned. Bench
instruments are named but their availability is an open risk (ETB-RISK-010),
and it is the resource gap that currently blocks milestone M6.

*Evidence:* ETB-SVD-001 §5.5; ETB-MAN3-001 §5; ETB-MAN5-001 ETB-RISK-010.

### GP 2.1.4 — Identify and make available resources

**Rating: P**

Software resources are available and pinned. The bench instruments are
available and have been used since 2026-10-04: the qualification campaign
(ETB-SYS5-002) and the bench runs since then. The exception is the TDS3014B
oscilloscope, which has not been on the bench. What is not yet done is
allocating bench time to the system integration cases: their execution is
deferred to `v0.05.0000` (ETB-DEV-004). Each case now states its resources
(ETB-SYS4-001 §5), and the bench time is estimated in ETB-MAN3-001 §8.1.

*Evidence:* ETB-SYS4-001 §5, §6, §8; ETB-SYS5-002; ETB-DEV-004;
ETB-MAN3-001 §8.1.

### GP 2.1.5 — Monitor and adjust the performance of the process

**Rating: L**

Performance is monitored continuously and mechanically: the suite and the
traceability check on every change, the firmware and style workflows on every
push, with the measures in ETB-MAN3-001 §8. Adjustment happens in the open —
when a plan could not be followed, the plan changed or a deviation was recorded.
Milestone reviews are defined but none has been formally held.

*Evidence:* ETB-MAN3-001 §8, §10; ETB-SUP1-001 §6; CI run history.

### GP 2.1.6 — Identify and involve stakeholders

**Rating: L**

The stakeholders are identified (ETB-MAN3-001 §5) and the stakeholder
requirements are recorded and traced (ETB-SWE1-001 §4, ETB-SYS2-001 §14). With a
one-person project, involvement is direct and continuous; there is no evidence
of stakeholder communication beyond the repository, and none is claimed.

*Evidence:* ETB-MAN3-001 §5, §11; ETB-SWE1-001 §4; ETB-SYS2-001 §14.

---

## 6. PA 2.2 — Work Product Management

### GP 2.2.1 — Define the requirements for the work products

**Rating: L**

Requirements for work products are defined: the document layout is uniform and
stated, ETB-SUP1-001 §5 lists which checks apply to which work product, and
ETB-TMPL-001 §6 states what each kind of work product must satisfy, and
ETB-SUP1-001 §6.6 states what each type must contain (#371). The weakness is
authorship competence, recorded as ETB-DEV-001.

*Evidence:* ETB-SUP1-001 §5, §6.6; ETB-TMPL-001 §6; ETB-DEV-001.

### GP 2.2.2 — Define the requirements for documentation and control

**Rating: F**

Every work product carries a Document ID, version, status, author, reviewer,
approver and revision history. ETB-SUP8-001 defines the configuration items,
versioning, baselines and status accounting, and git enforces the history.

*Evidence:* ETB-SUP8-001 §4–§9; the identification block of every document.

### GP 2.2.3 — Identify, document and control the work products

**Rating: L**

All work products are in the repository under version control, identified and
versioned. Control is real: no change reaches `main` except through a pull
request with a green build.

*Evidence:* ETB-SUP8-001 §5, §6; ETB-SVD-001 §5.

### GP 2.2.4 — Review and adjust work products

**Rating: P**

This is the weakest practice in the set and the rating says so.

What exists: mechanical review that runs on every change — the traceability
check binds documents to code, the layering test binds code to the
architecture, 1 878 tests at 94% coverage bind behaviour to requirements. These
catch the class of defect a human reviewer most often misses, and they cannot be
skipped.

What exists for human review: since #204 (2026-10-05) every change is reviewed
and approved by the merge of its pull request, by the Reviewer or on his
instruction (ETB-SUP1-001 §6.5, ETB-SUP8-001 §5.7). What the audit of
`v0.03.0000` found missing (ETB-SUP1-002, AUD-v0.03-110, -111) is a record that
checks C1 to C6 were applied: the reviews on the pull requests were automated
comments, and the merge records only the approval. Since #371 (2026-11-17) the
*PR Review* session posts a QA review with C1 to C6 per work product on every
pull request before the merge (ETB-SUP1-001 §6.5, ETB-DEV-002 §4). A document's
status follows from where it is (ETB-SUP1-001 §6.3), so no document is left in
Draft. Reviewer and approver are the same person, recorded as ETB-DEV-002.

Filing review records for reviews that did not happen would have raised this
rating on paper and destroyed the only thing this document is for.

*Evidence:* `tests/test_traceability.py`; `tests/test_layering.py`;
ETB-SWE4-002; ETB-TMPL-001; ETB-DEV-002; ETB-SUP1-001 §6.3, §6.5; the QA
review on each pull request.

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
| GP 2.2.4 | Reviews held on the work products and recorded on ETB-TMPL-001; separation of reviewer and approver would close ETB-DEV-002 as well |

Neither is a documentation exercise. That is the point of rating them P.

---

## 8. Work Product Index

| Process | Work product | Document ID |
|---|---|---|
| SYS.2 | System Requirements Specification | ETB-SYS2-001 |
| SYS.3 | System Architecture | ETB-SYS3-001 |
| SYS.4 | System Integration & Integration Test | ETB-SYS4-001 |
| SYS.5 | System Qualification Test | ETB-SYS5-001 |
| SWE.1 | Software Requirements Specification | ETB-SWE1-001 |
| SWE.2 | Software Architecture | ETB-SWE2-001 |
| SWE.3 | Software Detailed Design | ETB-SWE3-001 |
| SWE.4 | Unit Verification Specification / Report | ETB-SWE4-001 / ETB-SWE4-002 |
| SWE.5 | Software Integration & Integration Test | ETB-SWE5-001 |
| SWE.6 | Software Qualification Test | ETB-SWE6-001 |
| All | Traceability Matrix | ETB-RTM-001 |
| MAN.3 | Project Management Plan | ETB-MAN3-001 |
| MAN.5 | Risk Management Plan | ETB-MAN5-001 |
| MAN.3, MAN.5 | Release Progress and Risk Review Record | ETB-MAN3-002 |
| SUP.1 | Quality Assurance Plan | ETB-SUP1-001 |
| SUP.8 | Configuration Management Plan / SVD / Configuration Audit Record | ETB-SUP8-001 / ETB-SVD-001 / ETB-SUP8-002 |
| SUP.9 | Problem Resolution Management Plan | ETB-SUP9-001 |
| SUP.10 | Change Request Management Plan | ETB-SUP10-001 |
| ACQ.4 | Supplier Monitoring Plan | ETB-ACQ4-001 |
| SWE.3/4, SUP.1 | C coding standard, style guide, standards applicability | ETB-STD-002, ETB-STY-001, ETB-STD-001 |
| SUP.1 | Repository Analysis Report | ETB-ANA-001 |
| GP 2.2.4 | Review and test case templates | ETB-TMPL-001, ETB-TMPL-002 |
| SUP.1 | Process QA Record | ETB-SUP1-003 |
| GP 2.1, GP 2.2, SUP.1, SYS.4, SYS.5 | Deviations | ETB-DEV-001, ETB-DEV-002, ETB-DEV-003, ETB-DEV-004 |

---

## 9. Review & Approval

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
