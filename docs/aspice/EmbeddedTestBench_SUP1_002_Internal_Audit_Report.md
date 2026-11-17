<img src="../../assets/brand/svg/logos/embeddedtestbench-logo-compact.svg" alt="Embedded Test Bench" width="240">

# Internal Audit Report — Release v0.03.0000

*Automotive SPICE® PAM v4.0 | SUP.1 — Quality Assurance | Capability Level 2*

---

## 1. Document Identification & Control

| Field | Value | Field | Value |
|---|---|---|---|
| **Document ID** | ETB-SUP1-002 | **Version** | [latest, §2](#2-revision-history) |
| **Project** | Embedded Test Bench | **Date** | [latest, §2](#2-revision-history) |
| **Status** | [by location, ETB-SUP1-001 §6.3](EmbeddedTestBench_SUP1_Quality_Assurance_Plan.md#63-document-status) | **Classification** | Internal |
| **Author** | Claude | **Reviewer** | Dermot Murphy |
| **Approver** | Dermot Murphy | **Related Process** | SUP.1 |

> Reviewer and Approver are the same person; see ETB-DEV-002. The author and
> auditor is an AI assistant; see ETB-DEV-001 and §4.3.

---

## 2. Revision History

| Version | Date | Author | Description of Change |
|---|---|---|---|
| 0.1 | 2026-11-17 | Claude | #198: first issue. First internal audit, of release `v0.03.0000` against Capability Level 2. |
| next | 2026-11-17 | Claude | #198: review round 1 (PR #378). §5.1 applies the ISO/IEC 33020 capability level rule (CL2 needs PA 1.1 F): 0 of 17 processes reach CL2, 9 reach CL1. SWE.3 BP3 rated L, not F, because lint and the C standard pass against baselines of known violations; new finding AUD-v0.03-112 on its own issue. SWE.3 BP3 module count corrected to 146. §4.2: generic practice titles are unverified too. |
| next | 2026-11-17 | Claude | #371: the Status cell links to the status rule, ETB-SUP1-001 §6.3. A document's status follows from where it is in the repository (In review, Agreed, Released) and is not written in by hand. |

---

## 3. Purpose & Scope

### 3.1 Purpose

This report records an internal audit of whether Embedded Test Bench reaches
Capability Level 2 with PA 1.1, PA 2.1 and PA 2.2 **Fully achieved** for each
process in scope. It rates every base practice and every PA 2.1 and PA 2.2
generic practice on cited evidence, and records a finding for every rating
below F. It does not fix findings; each finding is carried on an issue (§9).

### 3.2 Referenced Documents

| Document ID | Title | Version at `v0.03.0000` |
|---|---|---|
| ETB-SUP1-001 | Quality Assurance Plan | 0.5 |
| ETB-PA2-001 | Process Capability Records — Level 2 | 0.5 |
| ETB-SUP8-001 | Configuration Management Plan | 0.21 |
| ETB-SVD-001 | Software Version Description | 0.10 |
| ETB-DEV-001 | Deviation Record — AI Authorship of Work Products | 0.5 |
| ETB-DEV-002 | Deviation Record — Reviewer Independence | 0.5 |
| ETB-RTM-001 | Requirements Traceability Matrix | 1.83 |

Every other work product cited is at the version ETB-SVD-001 §5.3 lists.

### 3.3 Scope

| Item | Value |
|---|---|
| Model | Automotive SPICE PAM v4.0 |
| Target | Capability Level 2, PA 1.1, PA 2.1 and PA 2.2 all **F** for every process in scope |
| Baseline audited | `v0.03.0000`, annotated tag on 4b71a51 (`main`, PR #360, 2026-11-17). Later work on `develop` is not credited |
| Processes | SYS.2, SYS.3, SYS.4, SYS.5, SWE.1, SWE.2, SWE.3, SWE.4, SWE.5, SWE.6, MAN.3, MAN.5, SUP.1, SUP.8, SUP.9, SUP.10, ACQ.4 |
| Audit date | 2026-11-17 |
| Issue | #198 |

---

## 4. Method

### 4.1 Evidence

Every document was read from a checkout of the tag (`git worktree add --detach
<dir> v0.03.0000`), not from `develop`. CI evidence is the runs on the tag
commit 4b71a51: `tests` 44057132180 (4 555 passed, 2 skipped, statement
coverage 95.3 % on Python 3.12), `lint` 44057131989, `style` 44057131775,
`bench` 44057132025, `firmware` 44057131868, all success, and the 19 check
runs on PR #360. GitHub records (issues, pull requests, merge commits, labels,
milestones) were read through `gh` on 2026-11-17. Each rating cites its
evidence; a rating with no cited evidence is not given.

### 4.2 Rating

Practices are rated on the PAM v4.0 scale: **N** 0–15 %, **P** >15–50 %,
**L** >50–85 %, **F** >85–100 %. A process attribute is rated from its
practices by this audit's rule: **F** only if every practice is F; otherwise
the mean of the practice ratings (N=0, P=1, L=2, F=3), below 0.5 N, below 1.5
P, otherwise L. The rule is this audit's, stated so the aggregation can be
checked; PAM v4.0 leaves the aggregation to the assessment.

A plan that defines an activity is evidence for the definition, not for the
activity. Performance is credited only where a record of it exists.

The base and generic practice titles are those of PAM v4.0 as the auditor knows them. They
were not checked against the VDA text in this session, which is not in the
repository; this is recorded as unverified (ETB-RISK-004).

### 4.3 Auditor Independence

The audit was performed by Claude Code, the same AI assistant that authored
the work products it audits (ETB-DEV-001). It is therefore **not independent**
of the work, in the same way that review is not independent (ETB-DEV-002).
Its ratings are a structured self-assessment with cited evidence, not an
independent assessment. The compensation is the citation rule of §4.1: each
rating can be checked against the tag by anyone. SUP.1 BP1 is rated on this
basis (§6).

### 4.4 Constraints

- No finding was fixed on the audit branch.
- No entry was made in any Review & Approval table, and no approval is recorded
  on the owner's behalf.

---

## 5. Summary

### 5.1 Process Attribute Ratings

| Process | PA 1.1 | PA 2.1 | PA 2.2 | Capability level | Target met |
|---|---|---|---|---|---|
| SYS.2 | P | L | L | CL0 | No |
| SYS.3 | P | L | L | CL0 | No |
| SYS.4 | N | P | L | CL0 | No |
| SYS.5 | L | L | L | CL1 | No |
| SWE.1 | P | L | L | CL0 | No |
| SWE.2 | L | L | L | CL1 | No |
| SWE.3 | L | L | L | CL1 | No |
| SWE.4 | L | L | L | CL1 | No |
| SWE.5 | L | L | L | CL1 | No |
| SWE.6 | P | L | L | CL0 | No |
| MAN.3 | P | L | L | CL0 | No |
| MAN.5 | L | L | L | CL1 | No |
| SUP.1 | P | L | L | CL0 | No |
| SUP.8 | L | L | L | CL1 | No |
| SUP.9 | P | L | L | CL0 | No |
| SUP.10 | L | L | L | CL1 | No |
| ACQ.4 | L | L | L | CL1 | No |

**Verdict: the target is not met.** No process in scope has PA 1.1, PA 2.1
and PA 2.2 all Fully achieved.

The capability level column applies the ISO/IEC 33020 rule: a level is
achieved when its own attributes are L or F and every lower-level attribute is
F. Capability Level 2 therefore needs PA 1.1 F with PA 2.1 and PA 2.2 L or F.
0 of 17 processes reach Capability Level 2. 9 reach Capability Level 1 (SYS.5, SWE.2, SWE.3, SWE.4, SWE.5, MAN.5, SUP.8, SUP.10, ACQ.4); the rest are at Capability Level 0.

### 5.2 The Four Gaps Named in #198

| Gap when #198 was opened | At `v0.03.0000` |
|---|---|
| No work product reviewed (ETB-SVD-001 §7 item 9) | Partly changed. Since #204 the merge of a PR is the review record, and every document version was merged by or on the instruction of the owner (ETB-SVD-001 §5.3). Item 9 now reads "No document in this baseline has left Draft status". No record shows the owner's review against ETB-TMPL-001 C1 to C6; the reviews visible on PRs are `claude-auto-review` comments. Still a finding (GP 2.2.4, SUP.1 BP3) |
| Reviewer and approver the same person (ETB-DEV-002) | Unchanged; accepted by ETB-DEV-002 |
| System qualification 44 of 64 (ETB-SYS5-002) | Unchanged and now understated: ETB-SYS2-001 holds 67 requirements, 3 never assessed. Not rerun for this release (ETB-SVD-001 §6) |
| System integration cases not formally performed (ETB-SYS4-001) | Unchanged: 0 of 16 performed (ETB-SYS4-001 §5) |

### 5.3 Findings by Issue

| Issue | Subject | Findings |
|---|---|---|
| #362 | SYS.4: perform the system integration cases and bring ETB-SYS4-001 up to date | AUD-v0.03-012, AUD-v0.03-013, AUD-v0.03-014, AUD-v0.03-015, AUD-v0.03-016, AUD-v0.03-100, AUD-v0.03-102 |
| #363 | SYS.5: rerun system qualification against the current 67 system requirements | AUD-v0.03-017, AUD-v0.03-018, AUD-v0.03-019, AUD-v0.03-020, AUD-v0.03-021, AUD-v0.03-103 |
| #364 | Traceability chain stakeholder to system to software: SYS2, SYS3, SWE1, RTM and its check | AUD-v0.03-005, AUD-v0.03-010, AUD-v0.03-026, AUD-v0.03-031 |
| #365 | SYS.2 and SYS.3 content: analysis, system context, missing elements, dynamic views | AUD-v0.03-001, AUD-v0.03-002, AUD-v0.03-003, AUD-v0.03-004, AUD-v0.03-007, AUD-v0.03-008, AUD-v0.03-009 |
| #366 | SWE.1 requirement attributes: verification criteria, priority, release, analysis | AUD-v0.03-022, AUD-v0.03-023, AUD-v0.03-024, AUD-v0.03-025 |
| #367 | SWE.2 and SWE.3 refresh: stale views, catalogue, dynamic design, resource analysis | AUD-v0.03-028, AUD-v0.03-029, AUD-v0.03-030, AUD-v0.03-033, AUD-v0.03-034 |
| #368 | Traceability checker blind spots and code-to-design trace defects | AUD-v0.03-035 |
| #369 | ETB-SWE4-002 results, verdict and figures out of date | AUD-v0.03-037, AUD-v0.03-038, AUD-v0.03-039, AUD-v0.03-040, AUD-v0.03-041 |
| #370 | SWE.5 and SWE.6: case-level results and traceability, stale figures, duplicate QT-05 | AUD-v0.03-042, AUD-v0.03-043, AUD-v0.03-044, AUD-v0.03-045, AUD-v0.03-046, AUD-v0.03-047, AUD-v0.03-048, AUD-v0.03-049, AUD-v0.03-050, AUD-v0.03-051 |
| #371 | Review evidence: owner's review against C1 to C6, Draft status, stale review statements | AUD-v0.03-006, AUD-v0.03-011, AUD-v0.03-027, AUD-v0.03-032, AUD-v0.03-036, AUD-v0.03-069, AUD-v0.03-108, AUD-v0.03-110, AUD-v0.03-111 |
| #372 | MAN.3 and MAN.5: plan refresh, process objectives, schedule, milestone and risk reviews | AUD-v0.03-052, AUD-v0.03-053, AUD-v0.03-054, AUD-v0.03-055, AUD-v0.03-056, AUD-v0.03-057, AUD-v0.03-058, AUD-v0.03-059, AUD-v0.03-060, AUD-v0.03-061, AUD-v0.03-062, AUD-v0.03-063, AUD-v0.03-064, AUD-v0.03-065, AUD-v0.03-066, AUD-v0.03-096, AUD-v0.03-097, AUD-v0.03-098, AUD-v0.03-099, AUD-v0.03-101, AUD-v0.03-104, AUD-v0.03-105, AUD-v0.03-107 |
| #373 | SUP.1: process quality assurance and QA reporting | AUD-v0.03-067, AUD-v0.03-068, AUD-v0.03-070, AUD-v0.03-071, AUD-v0.03-072, AUD-v0.03-073 |
| #374 | SUP.8: configuration audit, backup and recovery check, CM inconsistencies | AUD-v0.03-074, AUD-v0.03-075, AUD-v0.03-076, AUD-v0.03-077 |
| #375 | SUP.9 and SUP.10: issue records do not follow the plans | AUD-v0.03-078, AUD-v0.03-079, AUD-v0.03-080, AUD-v0.03-081, AUD-v0.03-082, AUD-v0.03-083, AUD-v0.03-084, AUD-v0.03-085, AUD-v0.03-086, AUD-v0.03-087, AUD-v0.03-088, AUD-v0.03-089, AUD-v0.03-090 |
| #376 | ACQ.4: AI model supplier, joint activities and stale supplier facts | AUD-v0.03-091, AUD-v0.03-092, AUD-v0.03-093, AUD-v0.03-094, AUD-v0.03-095, AUD-v0.03-106 |
| #377 | Referenced Documents tables cite version 0.1 throughout | AUD-v0.03-109 |
| #379 | SWE.3 unit conformance: baselined lint and C-standard violations, MISRA, compiler flags | AUD-v0.03-112 |

---

## 6. PA 1.1 — Base Practice Ratings

### 6.1 SYS.2 — PA 1.1 = P

| Practice | Rating | Evidence | Finding |
|---|---|---|---|
| BP1 Specify system requirements | **L** | ETB-SYS2-001 §5 to §12: 67 requirements, each with a verification method (T, A, I, D); §13 assumptions ETB-SYS2-100 to -104. | AUD-v0.03-001 |
| BP2 Structure system requirements | **L** | ETB-SYS2-001 groups by topic with a §4 context table and §3.4 notation. | AUD-v0.03-002 |
| BP3 Analyze system requirements | **P** | Verification method column; risk notes under §6 and §7 tie ETB-SYS2-013, -016, -023 to ETB-RISK-001 and -008. | AUD-v0.03-003 |
| BP4 Analyze the impact on the system context | **N** | None found. | AUD-v0.03-004 |
| BP5 Ensure consistency and establish bidirectional traceability | **P** | ETB-SYS2-001 §14 maps STK ranges to SYS2 ranges; `specs/qualification/*.yaml` carry `requirements:` lists. | AUD-v0.03-005 |
| BP6 Communicate agreed system requirements | **P** | Published in the repository and wiki; listed in ETB-SVD-001 §5.3 (0.10, Draft); merged by PR. | AUD-v0.03-006 |

### 6.2 SYS.3 — PA 1.1 = P

| Practice | Rating | Evidence | Finding |
|---|---|---|---|
| BP1 Specify static aspects of the system architecture | **L** | ETB-SYS3-001 §5.1 nine physical elements, §5.2 four logical elements, §6 interfaces ETB-SIF-01 to -15. | AUD-v0.03-007 |
| BP2 Specify dynamic aspects of the system architecture | **P** | ETB-SYS3-001 §8: one ten-step bring-up sequence; §9 resource characteristics. | AUD-v0.03-008 |
| BP3 Analyze the system architecture | **P** | ETB-SYS3-001 §4 drivers ETB-SAD-01 to -06; §10 decisions SD-01 to -05 with rationale. | AUD-v0.03-009 |
| BP4 Ensure consistency and establish bidirectional traceability | **P** | ETB-SYS3-001 §7 allocation table by range. | AUD-v0.03-010 |
| BP5 Communicate agreed system architecture | **P** | Published; ETB-SVD-001 §5.3 (0.8, Draft). | AUD-v0.03-011 |

### 6.3 SYS.4 — PA 1.1 = N

| Practice | Rating | Evidence | Finding |
|---|---|---|---|
| BP1 Specify verification measures for system integration | **P** | ETB-SYS4-001 §4 stages S1 to S8; §5 cases ETB-SIT-01 to -16. | AUD-v0.03-012 |
| BP2 Select verification measures | **N** | None found. | AUD-v0.03-013 |
| BP3 Integrate system elements and perform integration verification | **N** | ETB-SYS4-001 §5: 0 of 16 formally performed; ETB-SIT-10 partial (CI build only); ETB-SIT-03, -04 informal (2026-09-26); §6 entry criteria E3, E4 not met; ETB-SVD-001 §7 item 8. | AUD-v0.03-014 |
| BP4 Ensure consistency and establish bidirectional traceability | **P** | Cases trace to SIF IDs and OPEN items. | AUD-v0.03-015 |
| BP5 Summarize and communicate results | **N** | ETB-SVD-001 §7 item 8 discloses the gap. | AUD-v0.03-016 |

### 6.4 SYS.5 — PA 1.1 = L

| Practice | Rating | Evidence | Finding |
|---|---|---|---|
| BP1 Specify verification measures for system verification | **L** | ETB-SYS5-001 §5 eleven scenarios QS-01, QS-01b, QS-02 to QS-10; §4 two configurations; `specs/qualification/` nine specifications. | AUD-v0.03-017 |
| BP2 Select verification measures | **P** | ETB-SVD-001 §6: not rerun for this release. | AUD-v0.03-018 |
| BP3 Perform verification of the integrated system | **L** | ETB-SYS5-002 §5.3, §7.1: one hardware campaign 2026-10-04, records in `docs/aspice/qualification/2026-10-04/`; 44 qualified, 3 partial, 10 not qualified, 2 not performed, 5 out of scope, of 64. Kepler regression 2026-11-15/16 (ETB-SVD-001 §6). | AUD-v0.03-019 |
| BP4 Ensure consistency and establish bidirectional traceability | **L** | ETB-SYS5-002 §7 per-requirement table; YAML `requirements:` lists. | AUD-v0.03-020 |
| BP5 Summarize and communicate results | **L** | ETB-SYS5-002 §10, §11; ETB-SVD-001 §6, §7. | AUD-v0.03-021 |

### 6.5 SWE.1 — PA 1.1 = P

| Practice | Rating | Evidence | Finding |
|---|---|---|---|
| BP1 Specify software requirements | **L** | ETB-SWE1-001 §6 to §19: 577 requirements (537 FR of which 536 in force, 40 NFR); each has a Verification cell. | AUD-v0.03-022 |
| BP2 Structure software requirements | **P** | Grouped by element prefix (§5) and subsection. | AUD-v0.03-023 |
| BP3 Analyze software requirements | **P** | Implicit in §20 ASM-01 to -10, CON-01 to -12. | AUD-v0.03-024 |
| BP4 Analyze the impact on the operating environment | **P** | §3.3 scope; ASM and CON entries. | AUD-v0.03-025 |
| BP5 Ensure consistency and establish bidirectional traceability | **P** | All 638 FR source citations are STK-xx; all 577 IDs appear in ETB-RTM-001; `tests/test_traceability.py`. | AUD-v0.03-026 |
| BP6 Communicate agreed software requirements | **P** | Merged by PR, published to the wiki, listed in ETB-SVD-001 §5.3 (1.70, Draft). | AUD-v0.03-027 |

### 6.6 SWE.2 — PA 1.1 = L

| Practice | Rating | Evidence | Finding |
|---|---|---|---|
| BP1 Specify static aspects of the software architecture | **L** | ETB-SWE2-001 §5 layering, §6 22 elements, §10 external interfaces; allocation in ETB-RTM-001 Architecture column and §17. | AUD-v0.03-028 |
| BP2 Specify dynamic aspects of the software architecture | **P** | ETB-SWE2-001 §8 one sequence diagram (runner with TDS3014B). | AUD-v0.03-029 |
| BP3 Analyze the software architecture | **L** | §4 drivers D1 to D11; §7 decisions AD-01 to AD-32 with rationale; §9 resources for scope, J-Link, BLE. | AUD-v0.03-030 |
| BP4 Ensure consistency and establish bidirectional traceability | **L** | `test_every_decision_is_traced_in_the_matrix`; ETB-RTM-001 §17, §18. | AUD-v0.03-031 |
| BP5 Communicate agreed software architecture | **P** | Merged by PR; ETB-SVD-001 §5.3 (0.33, Draft). | AUD-v0.03-032 |

### 6.7 SWE.3 — PA 1.1 = L

| Practice | Rating | Evidence | Finding |
|---|---|---|---|
| BP1 Specify the static aspects of the detailed design | **L** | ETB-SWE3-001 §5.1 to §5.13: 150 design units; ETB-SWE3-002 for the GPD-3303D. | AUD-v0.03-033 |
| BP2 Specify dynamic aspects of the detailed design | **P** | Prose; ETB-SWE3-002 §5.3 sequence diagram, §5.4 state. | AUD-v0.03-034 |
| BP3 Develop software units | **L** | 146 Python modules under `benchtools/`; three firmware trees; CStyleCheck v1.6.1 (`style.yml`) against ETB-STD-002; pylint (`lint.yml`); both green on 4b71a51 (CI run 44057131775, 44057131989). | AUD-v0.03-112 |
| BP4 Ensure consistency and establish bidirectional traceability | **L** | ETB-RTM-001 §5 to §17 trace requirement, architecture, design unit, source, test. | AUD-v0.03-035 |
| BP5 Communicate agreed design and developed units | **P** | Merged by PR; ETB-SVD-001 §5.3 (1.90, Draft). | AUD-v0.03-036 |

### 6.8 SWE.4 — PA 1.1 = L

| Practice | Rating | Evidence | Finding |
|---|---|---|---|
| BP1 Specify software unit verification measures | **L** | ETB-SWE4-001 §5 133 test groups with verified requirements; §4.7 pass criteria PC-1 to PC-12; §4.3 oracle independence; §4.5 layering. | AUD-v0.03-037 |
| BP2 Select software unit verification measures | **L** | ETB-SWE4-001 §4.6 techniques, one regression test per defect; whole suite every change (`tests.yml`, gate 90%). | AUD-v0.03-038 |
| BP3 Verify software units | **L** | CI on 4b71a51: 4 555 passed, 2 skipped, coverage 95.3 % (run 44057132180); firmware unit tests green (run 44057131868). ETB-SWE4-002 §5 per-group results. | AUD-v0.03-039 |
| BP4 Ensure consistency and establish bidirectional traceability | **L** | ETB-RTM-001 requirement to test; `TestVerificationReport` group to result. | AUD-v0.03-040 |
| BP5 Summarize and communicate results | **P** | ETB-SWE4-002 §16 verdict PASS; ETB-SVD-001 §6. | AUD-v0.03-041 |

### 6.9 SWE.5 — PA 1.1 = L

| Practice | Rating | Evidence | Finding |
|---|---|---|---|
| BP1 Specify software integration verification measures | **L** | ETB-SWE5-001 §4 stages I1 to I8, §5 nine groups, §6 ETB-IT-01 to -10, §7 criteria. | AUD-v0.03-042 |
| BP2 Select software integration verification measures | **L** | §8 whole suite every change. | AUD-v0.03-043 |
| BP3 Integrate software elements and perform integration verification | **L** | Continuous: `tests.yml` and `bench.yml` (Simulated bench) green on 4b71a51 (runs 44057132180, 44057132025). | AUD-v0.03-044 |
| BP4 Ensure consistency and establish bidirectional traceability | **P** | Cases mapped to directories. | AUD-v0.03-045 |
| BP5 Summarize and communicate results | **P** | ETB-SWE5-001 §9, §10. | AUD-v0.03-046 |

### 6.10 SWE.6 — PA 1.1 = P

| Practice | Rating | Evidence | Finding |
|---|---|---|---|
| BP1 Specify verification measures for software verification | **L** | ETB-SWE6-001 §5: 21 cases ETB-QT-01 to -20 and -02a; §4 strategy; §6 exit criteria. | AUD-v0.03-047 |
| BP2 Select verification measures | **P** | Implicit: the whole suite. | AUD-v0.03-048 |
| BP3 Verify the integrated software | **P** | ETB-SWE6-001 §7; release figures in ETB-SVD-001 §6. | AUD-v0.03-049 |
| BP4 Ensure consistency and establish bidirectional traceability | **P** | Two test modules cite a QT ID; requirement coverage via ETB-RTM-001. | AUD-v0.03-050 |
| BP5 Summarize and communicate results | **P** | ETB-SWE6-001 §7, §8; ETB-SVD-001 §6, §7. | AUD-v0.03-051 |

### 6.11 MAN.3 — PA 1.1 = P

| Practice | Rating | Evidence | Finding |
|---|---|---|---|
| BP1 Define the scope of work | **F** | ETB-MAN3-001 §3.3 scope; §4 objectives ETB-OBJ-001 to -005. | — |
| BP2 Define project life cycle | **L** | §7 incremental life cycle, milestones M1 to M6. | AUD-v0.03-052 |
| BP3 Evaluate feasibility of the project | **N** | None found. | AUD-v0.03-053 |
| BP4 Define and monitor work packages | **L** | §6 WP1 to WP7, §6.1 dependencies; issue #300 (24 dated comments, 2026-10-25 to 2026-11-15). | AUD-v0.03-054 |
| BP5 Define and monitor project estimates and resources | **P** | §8 proxy measures. | AUD-v0.03-055 |
| BP6 Define and monitor required skills, knowledge and experience | **P** | §5.1; ETB-DEV-001. | AUD-v0.03-056 |
| BP7 Define and monitor project interfaces and agreed commitments | **P** | §9 interfaces. | AUD-v0.03-057 |
| BP8 Define and monitor project schedule | **N** | §7 "No dates are given"; fix order in #300. | AUD-v0.03-058 |
| BP9 Ensure consistency | **P** | Plan referenced by other plans. | AUD-v0.03-059 |
| BP10 Review and report progress of the project | **P** | §11 commit history as progress report; #300 comments; ETB-SVD-001 per release; #325 closing comment. | AUD-v0.03-060 |

### 6.12 MAN.5 — PA 1.1 = L

| Practice | Rating | Evidence | Finding |
|---|---|---|---|
| BP1 Establish risk management scope | **F** | ETB-MAN5-001 §3.3, §4. | — |
| BP2 Identify potential undesirable events | **L** | §6 register ETB-RISK-001 to -013. | AUD-v0.03-061 |
| BP3 Determine risks | **L** | §5, §6 probability, impact, exposure. | AUD-v0.03-062 |
| BP4 Define risk treatment options | **L** | Treatment and trigger per risk. | AUD-v0.03-063 |
| BP5 Define and perform risk treatment activities | **L** | ETB-RISK-006, -008, -009 Mitigated; ETB-RISK-011 treated 2026-10-06 (#229). | AUD-v0.03-064 |
| BP6 Monitor risks | **N** | §7 "No review records are shipped with this baseline; none have been held." | AUD-v0.03-065 |
| BP7 Take corrective action | **P** | ETB-RISK-011 via #229 and ETB-ACQ4-001 §7. | AUD-v0.03-066 |

### 6.13 SUP.1 — PA 1.1 = P

| Practice | Rating | Evidence | Finding |
|---|---|---|---|
| BP1 Ensure independence of quality assurance | **N** | ETB-MAN3-001 §5: QA held by the project lead, also Reviewer and Approver; ETB-DEV-002 accepted. | AUD-v0.03-067 |
| BP2 Define criteria for quality assurance | **L** | ETB-SUP1-001 §4 ETB-QA-001 to -008, §5; ETB-TMPL-001 §6 C1 to C6. | AUD-v0.03-068 |
| BP3 Assure quality of work products | **P** | Required checks green on every PR (PR #360: 19 check runs success); `claude-auto-review` reviews on PRs. | AUD-v0.03-069 |
| BP4 Assure quality of process activities | **N** | None before this audit; #198 opened 2026-10-05 with no comments. | AUD-v0.03-070 |
| BP5 Summarize and communicate QA activities and results | **P** | ETB-ANA-001 snapshot. | AUD-v0.03-071 |
| BP6 Ensure resolution of non-conformances | **P** | ETB-ANA-001 §8 actions, some done. | AUD-v0.03-072 |
| BP7 Escalate non-conformances | **L** | ETB-SUP1-001 §8; project lead is final authority. | AUD-v0.03-073 |

### 6.14 SUP.8 — PA 1.1 = L

| Practice | Rating | Evidence | Finding |
|---|---|---|---|
| BP1 Identify configuration items | **L** | ETB-SUP8-001 §4. | AUD-v0.03-074 |
| BP2 Define configuration item properties | **L** | §4 "Versioned by"; §6.1 firmware manifests. | AUD-v0.03-075 |
| BP3 Establish configuration item baselines | **F** | Annotated tags v0.01.0000 to v0.03.0000, tag ruleset (§5.5); ETB-SVD-001 §4, §5.3 match `doc_versions.py list`. | — |
| BP4 Control modifications | **F** | 172 merged PRs, all by `dermot-murphy`; required checks; PR #360 merge commit 4b71a51 with the merge note; back-merge #361. | — |
| BP5 Verify the information about configured items | **P** | §9 status accounting; `tests/test_doc_versions.py`; settings read back 2026-10-05, 2026-10-24. | AUD-v0.03-076 |
| BP6 Manage the storage of configuration items and baselines | **P** | §10 GitHub and clones; recovery procedure in CLAUDE.md. | AUD-v0.03-077 |

### 6.15 SUP.9 — PA 1.1 = P

| Practice | Rating | Evidence | Finding |
|---|---|---|---|
| BP1 Identify and record the problem | **L** | 39 issues labelled `bug`, all closed. | AUD-v0.03-078 |
| BP2 Determine the cause and the impact of the problem | **P** | Cause analysed in 20 of 39 bug issues. | AUD-v0.03-079 |
| BP3 Authorize urgent resolution action | **P** | §5 S1 "stop other work". | AUD-v0.03-080 |
| BP4 Raise alert notifications | **N** | None defined. | AUD-v0.03-081 |
| BP5 Initiate problem resolution | **L** | Fix by PR; ETB-SVD-001 §4 maps issue to PR. | AUD-v0.03-082 |
| BP6 Track problems to closure | **L** | Issues closed after merge with a regression test (§7). | AUD-v0.03-083 |
| BP7 Report the status of problem resolution activities | **P** | ETB-SVD-001 §7 known problems. | AUD-v0.03-084 |

### 6.16 SUP.10 — PA 1.1 = L

| Practice | Rating | Evidence | Finding |
|---|---|---|---|
| BP1 Identify and record the change requests | **P** | `enhancement` issues (48 closed, 7 open). | AUD-v0.03-085 |
| BP2 Analyze and assess change requests | **P** | Issue and PR prose. | AUD-v0.03-086 |
| BP3 Approve change requests before implementation | **P** | CLAUDE.md: work starts on the owner's request. | AUD-v0.03-087 |
| BP4 Establish bidirectional traceability | **L** | Issue, PR, merge commit; ETB-RTM-001. | AUD-v0.03-088 |
| BP5 Confirm the implementation of change requests | **L** | Required checks; ETB-SVD-001 §6. | AUD-v0.03-089 |
| BP6 Track change requests to closure | **L** | Issues closed after merge (e.g. #325). | AUD-v0.03-090 |

### 6.17 ACQ.4 — PA 1.1 = L

| Practice | Rating | Evidence | Finding |
|---|---|---|---|
| BP1 Agree on and maintain joint activities, interfaces and information exchanged | **P** | ETB-ACQ4-001 §9 "Not applicable: no agreements". | AUD-v0.03-091 |
| BP2 Exchange all agreed information | **L** | Upstream defects CStyleCheck#439, #447; Dependabot PRs declined with reasons (#219, #222 to #224, #248, #250). | AUD-v0.03-092 |
| BP3 Review development work products with the supplier | **L** | CStyleCheck v1.6.0 (2026-10-05) and v1.6.1 (2026-10-06) re-checked (§7); ps3000a library 2026-11-13 (§4.4). | AUD-v0.03-093 |
| BP4 Review progress of the supplier | **L** | Dependabot; weekly constraints refresh (§6). | AUD-v0.03-094 |
| BP5 Act to correct deviations | **L** | Pin away from defects (§7). | AUD-v0.03-095 |

---

## 7. PA 2.1 and PA 2.2 — Generic Practice Ratings

### 7.1 Ratings per Process

| Process | 2.1.1 | 2.1.2 | 2.1.3 | 2.1.4 | 2.1.5 | 2.1.6 | 2.2.1 | 2.2.2 | 2.2.3 | 2.2.4 | PA 2.1 | PA 2.2 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| SYS.2 | P | L | L | L | P | L | L | F | L | P | **L** | **L** |
| SYS.3 | P | L | L | L | P | L | L | F | L | P | **L** | **L** |
| SYS.4 | P | P | P | P | P | L | L | F | L | P | **P** | **L** |
| SYS.5 | P | L | L | L | P | L | L | F | L | P | **L** | **L** |
| SWE.1 | P | L | L | L | L | L | L | F | L | L | **L** | **L** |
| SWE.2 | P | L | L | L | L | L | L | F | L | L | **L** | **L** |
| SWE.3 | P | L | L | L | L | L | L | F | L | L | **L** | **L** |
| SWE.4 | L | L | L | L | L | L | L | F | L | L | **L** | **L** |
| SWE.5 | P | L | L | L | P | L | L | F | L | P | **L** | **L** |
| SWE.6 | P | L | L | L | P | L | L | F | L | P | **L** | **L** |
| MAN.3 | P | P | L | L | P | L | L | F | L | P | **L** | **L** |
| MAN.5 | P | L | L | L | P | L | L | F | L | P | **L** | **L** |
| SUP.1 | L | L | L | L | P | P | L | F | L | P | **L** | **L** |
| SUP.8 | P | L | L | L | L | L | L | F | L | P | **L** | **L** |
| SUP.9 | P | L | L | L | P | L | L | F | L | P | **L** | **L** |
| SUP.10 | P | L | L | L | P | L | L | F | L | P | **L** | **L** |
| ACQ.4 | P | L | L | L | L | P | L | F | L | P | **L** | **L** |

### 7.2 Evidence per Generic Practice

#### GP 2.1.1 — Identify the objectives and define a strategy for the performance of the process

| Processes | Rating | Evidence | Finding |
|---|---|---|---|
| SWE.4, SUP.1 | **L** | Measurable objectives: ETB-SUP1-001 §4 ETB-QA-001 to -008; ETB-SWE4-001 §4.7 PC-1 to PC-12 (coverage gate 90 %). | AUD-v0.03-096 |
| SYS.2, SYS.3, SYS.4, SYS.5, SWE.1, SWE.2, SWE.3, SWE.5, SWE.6, MAN.3, MAN.5, SUP.8, SUP.9, SUP.10, ACQ.4 | **P** | Product objectives only: ETB-MAN3-001 §4 ETB-OBJ-001 to -005. | AUD-v0.03-097 |

#### GP 2.1.2 — Plan the performance of the process

| Processes | Rating | Evidence | Finding |
|---|---|---|---|
| SYS.4, MAN.3 | **P** | ETB-MAN3-001 §6, §7; ETB-SYS4-001 §4. | AUD-v0.03-098 |
| SYS.2, SYS.3, SYS.5, SWE.1, SWE.2, SWE.3, SWE.4, SWE.5, SWE.6, MAN.5, SUP.1, SUP.8, SUP.9, SUP.10, ACQ.4 | **L** | Work packages, life cycle and the support plans (ETB-SUP1-001, ETB-SUP8-001, ETB-SUP9-001, ETB-SUP10-001, ETB-MAN5-001, ETB-ACQ4-001); CI workflows run the SWE processes on every change. | AUD-v0.03-099 |

#### GP 2.1.3 — Determine resource needs

| Processes | Rating | Evidence | Finding |
|---|---|---|---|
| SYS.4 | **P** | ETB-SYS4-001 §6 entry criteria E3, E4. | AUD-v0.03-100 |
| SYS.2, SYS.3, SYS.5, SWE.1, SWE.2, SWE.3, SWE.4, SWE.5, SWE.6, MAN.3, MAN.5, SUP.1, SUP.8, SUP.9, SUP.10, ACQ.4 | **L** | Tools pinned (ETB-SVD-001 §5.5); bench PC described (`benches/bench_pc.yaml`); roles (ETB-MAN3-001 §5). | AUD-v0.03-101 |

#### GP 2.1.4 — Identify and make available resources

| Processes | Rating | Evidence | Finding |
|---|---|---|---|
| SYS.4 | **P** | Bench PC qualified 2026-10-04 and used through 2026-11-16 (`docs/aspice/qualification/`). | AUD-v0.03-102 |
| SYS.2, SYS.3, SYS.5, SWE.1, SWE.2, SWE.3, SWE.4, SWE.5, SWE.6, MAN.3, MAN.5, SUP.1, SUP.8, SUP.9, SUP.10, ACQ.4 | **L** | Software resources pinned; bench PC with J-Link, dongle, S2-LP kit, GPD-3303D, TTi 1604, Pico 2 in use. | AUD-v0.03-103 |

#### GP 2.1.5 — Monitor and adjust the performance of the process

| Processes | Rating | Evidence | Finding |
|---|---|---|---|
| SWE.1, SWE.2, SWE.3, SWE.4, SUP.8, ACQ.4 | **L** | Monitored mechanically on every change (required checks, ETB-SUP8-001 §5.5); documents revised in the same change (e.g. ETB-SWE4-002 1.87, #352). | AUD-v0.03-104 |
| SYS.2, SYS.3, SYS.4, SYS.5, SWE.5, SWE.6, MAN.3, MAN.5, SUP.1, SUP.9, SUP.10 | **P** | Plans and specifications exist. | AUD-v0.03-105 |

#### GP 2.1.6 — Manage the interfaces between involved parties

| Processes | Rating | Evidence | Finding |
|---|---|---|---|
| SUP.1, ACQ.4 | **P** | ETB-MAN3-001 §5 roles; ETB-ACQ4-001 suppliers. | AUD-v0.03-106 |
| SYS.2, SYS.3, SYS.4, SYS.5, SWE.1, SWE.2, SWE.3, SWE.4, SWE.5, SWE.6, MAN.3, MAN.5, SUP.8, SUP.9, SUP.10 | **L** | ETB-MAN3-001 §5, §9, §11; owner instructions and decisions recorded on issues (e.g. #300). | AUD-v0.03-107 |

#### GP 2.2.1 — Define the requirements for the work products

| Processes | Rating | Evidence | Finding |
|---|---|---|---|
| SYS.2, SYS.3, SYS.4, SYS.5, SWE.1, SWE.2, SWE.3, SWE.4, SWE.5, SWE.6, MAN.3, MAN.5, SUP.1, SUP.8, SUP.9, SUP.10, ACQ.4 | **L** | Uniform document layout; ETB-SUP1-001 §5; ETB-TMPL-001 §6 C1 to C6; ETB-TMPL-002. | AUD-v0.03-108 |

#### GP 2.2.2 — Define the requirements for storage and control of the work products

| Processes | Rating | Evidence | Finding |
|---|---|---|---|
| SYS.2, SYS.3, SYS.4, SYS.5, SWE.1, SWE.2, SWE.3, SWE.4, SWE.5, SWE.6, MAN.3, MAN.5, SUP.1, SUP.8, SUP.9, SUP.10, ACQ.4 | **F** | ETB-SUP8-001 §4 to §9: identification, versioning (§6.2), baselines, storage, status accounting; ETB-SUP1-001 §6.3 status rule. | — |

#### GP 2.2.3 — Identify, store and control the work products

| Processes | Rating | Evidence | Finding |
|---|---|---|---|
| SYS.2, SYS.3, SYS.4, SYS.5, SWE.1, SWE.2, SWE.3, SWE.4, SWE.5, SWE.6, MAN.3, MAN.5, SUP.1, SUP.8, SUP.9, SUP.10, ACQ.4 | **L** | Git, document IDs, revision histories checked by `scripts/doc_versions.py check` (exit 0 at the tag); annotated tag v0.03.0000; ETB-SVD-001 §5.3. | AUD-v0.03-109 |

#### GP 2.2.4 — Review and adjust work products

| Processes | Rating | Evidence | Finding |
|---|---|---|---|
| SWE.1, SWE.2, SWE.3, SWE.4 | **L** | Changes reviewed in rounds on the PR (e.g. #352 review rounds 1 and 2) and merged by or on the instruction of the owner (ETB-SUP8-001 §5.7). | AUD-v0.03-110 |
| SYS.2, SYS.3, SYS.4, SYS.5, SWE.5, SWE.6, MAN.3, MAN.5, SUP.1, SUP.8, SUP.9, SUP.10, ACQ.4 | **P** | Merge of the PR is the review (ETB-SUP8-001 §5.7, ETB-DEV-002 §4). | AUD-v0.03-111 |

---

## 8. Findings Register

Every rating below F has one finding. A generic practice finding covers the
processes that share the rating and the gap.

| ID | Process | Practice | Rating | Evidence seen | Gap | What F needs | Issue |
|---|---|---|---|---|---|---|---|
| AUD-v0.03-001 | SYS.2 | SYS.2.BP1 Specify system requirements | L | ETB-SYS2-001 §5 to §12: 67 requirements, each with a verification method (T, A, I, D); §13 assumptions ETB-SYS2-100 to -104. | ETB-SYS2-010 still lists only the original five instruments; ETB-SYS2-104 says the TTi 1604 is unconfirmed against hardware, contradicted by QS-09 (2026-10-04) and `qualification/2026-10-28/181_tti1604`. ETB-SYS5-002 §7 gives ETB-SYS2-010 method T, ETB-SYS2-001 gives I. | Every requirement current and consistent with the qualification record. | #365 |
| AUD-v0.03-002 | SYS.2 | SYS.2.BP2 Structure system requirements | L | ETB-SYS2-001 groups by topic with a §4 context table and §3.4 notation. | No priority or release attribute. | Requirements carry priority and release allocation, or the plan states why not. | #365 |
| AUD-v0.03-003 | SYS.2 | SYS.2.BP3 Analyze system requirements | P | Verification method column; risk notes under §6 and §7 tie ETB-SYS2-013, -016, -023 to ETB-RISK-001 and -008. | No recorded analysis of correctness, technical feasibility or verifiability. | A recorded analysis per requirement or group, kept with the specification. | #365 |
| AUD-v0.03-004 | SYS.2 | SYS.2.BP4 Analyze the impact on the system context | N | None found. | No impact analysis. The §4 context table omits the multimeter, PicoScope, PPK2, Pico 2 and serial target. | Context table current; an impact statement recorded for each change to the requirements. | #365 |
| AUD-v0.03-005 | SYS.2 | SYS.2.BP5 Ensure consistency and establish bidirectional traceability | P | ETB-SYS2-001 §14 maps STK ranges to SYS2 ranges; `specs/qualification/*.yaml` carry `requirements:` lists. | STK-21, -22, -23 trace to no system requirement; ETB-SYS2-001, -003, -004, -010, -012, -013, -015, -016, -048 to -050, -092 to -095 have no STK parent; downward trace is by group only; ETB-RTM-001 has no SYS2 rows; no test checks the system trace. | Per-requirement trace both ways, in ETB-RTM-001, enforced by a test. | #364 |
| AUD-v0.03-006 | SYS.2 | SYS.2.BP6 Communicate agreed system requirements | P | Published in the repository and wiki; listed in ETB-SVD-001 §5.3 (0.10, Draft); merged by PR. | Agreement rests on a merge whose review content is not recorded (see AUD finding on GP 2.2.4); the document is Draft. | A recorded agreement of the baseline, with its status set accordingly. | #371 |
| AUD-v0.03-007 | SYS.3 | SYS.3.BP1 Specify static aspects of the system architecture | L | ETB-SYS3-001 §5.1 nine physical elements, §5.2 four logical elements, §6 interfaces ETB-SIF-01 to -15. | TTi 1604 multimeter, PICO2 Test Board and serial capture have no element or interface. | Every system element in the release in the architecture. | #365 |
| AUD-v0.03-008 | SYS.3 | SYS.3.BP2 Specify dynamic aspects of the system architecture | P | ETB-SYS3-001 §8: one ten-step bring-up sequence; §9 resource characteristics. | No state, timing or error-path views. | Dynamic views for the operating modes and error paths. | #365 |
| AUD-v0.03-009 | SYS.3 | SYS.3.BP3 Analyze the system architecture | P | ETB-SYS3-001 §4 drivers ETB-SAD-01 to -06; §10 decisions SD-01 to -05 with rationale. | No evaluation criteria and no comparison of alternatives. | Recorded analysis against stated criteria for each decision. | #365 |
| AUD-v0.03-010 | SYS.3 | SYS.3.BP4 Ensure consistency and establish bidirectional traceability | P | ETB-SYS3-001 §7 allocation table by range. | ETB-SYS2-026, -037, -051, -052, -053, -065, -080 to -084 allocated to no element; no back-trace in ETB-RTM-001. | Every system requirement allocated; trace both ways in ETB-RTM-001. | #364 |
| AUD-v0.03-011 | SYS.3 | SYS.3.BP5 Communicate agreed system architecture | P | Published; ETB-SVD-001 §5.3 (0.8, Draft). | As SYS.2 BP6. | As SYS.2 BP6. | #371 |
| AUD-v0.03-012 | SYS.4 | SYS.4.BP1 Specify verification measures for system integration | P | ETB-SYS4-001 §4 stages S1 to S8; §5 cases ETB-SIT-01 to -16. | Cases cover ETB-SIF-01 to -11 only; ETB-SIF-12 to -15, the multimeter and serial capture have none. §5.1 says the bench has not been assembled with hardware, contradicted by ETB-SYS5-002. Content unchanged since 0.2 (2026-09-26, #63). | Cases for every interface in the release; document current. | #362 |
| AUD-v0.03-013 | SYS.4 | SYS.4.BP2 Select verification measures | N | None found. | No selection or regression rule; §4 requires each stage passed before the next, but none after S1 is recorded. | A stated selection and regression rule, applied per release. | #362 |
| AUD-v0.03-014 | SYS.4 | SYS.4.BP3 Integrate system elements and perform integration verification | N | ETB-SYS4-001 §5: 0 of 16 formally performed; ETB-SIT-10 partial (CI build only); ETB-SIT-03, -04 informal (2026-09-26); §6 entry criteria E3, E4 not met; ETB-SVD-001 §7 item 8. | Integration verification not performed. Hardware runs that exercised SIT-06 to -09, -12, -13 behaviour (QS-01, JLINK-OPEN-01/-02 closed in ETB-SYS5-002 §9) are not carried back. | All cases performed on the bench with recorded results. | #362 |
| AUD-v0.03-015 | SYS.4 | SYS.4.BP4 Ensure consistency and establish bidirectional traceability | P | Cases trace to SIF IDs and OPEN items. | No trace to system requirements or architecture elements; not in ETB-RTM-001. | Cases traced to SYS3 elements and SYS2 requirements, both ways. | #362 |
| AUD-v0.03-016 | SYS.4 | SYS.4.BP5 Summarize and communicate results | N | ETB-SVD-001 §7 item 8 discloses the gap. | No integration test report. | A dated integration report per release. | #362 |
| AUD-v0.03-017 | SYS.5 | SYS.5.BP1 Specify verification measures for system verification | L | ETB-SYS5-001 §5 eleven scenarios QS-01, QS-01b, QS-02 to QS-10; §4 two configurations; `specs/qualification/` nine specifications. | ETB-SYS2-013, -026, -037, -065, -071, -072, -080 to -083, -090, -093, -095 in no scenario's Qualifies list. | Every system requirement in a scenario. | #363 |
| AUD-v0.03-018 | SYS.5 | SYS.5.BP2 Select verification measures | P | ETB-SVD-001 §6: not rerun for this release. | No selection or regression rule per release. ETB-SYS5-001 §8 entry criterion (every SYS4 case passed) was not met when qualification ran. | A selection rule applied per release; entry criteria met or deviated. | #363 |
| AUD-v0.03-019 | SYS.5 | SYS.5.BP3 Perform verification of the integrated system | L | ETB-SYS5-002 §5.3, §7.1: one hardware campaign 2026-10-04, records in `docs/aspice/qualification/2026-10-04/`; 44 qualified, 3 partial, 10 not qualified, 2 not performed, 5 out of scope, of 64. Kepler regression 2026-11-15/16 (ETB-SVD-001 §6). | ETB-SYS2-001 now holds 67 requirements; ETB-SYS2-026, -037, -065 added after the campaign and never assessed. Fixes for #179, #181 and the J-Link not requalified (ETB-SVD-001 §7 items 1 to 3). Kepler run folders are held in innovateuk-sensor, not here. | All 67 requirements qualified on hardware for the release, records in this repository. | #363 |
| AUD-v0.03-020 | SYS.5 | SYS.5.BP4 Ensure consistency and establish bidirectional traceability | L | ETB-SYS5-002 §7 per-requirement table; YAML `requirements:` lists. | Table is against 64, not 67; not in ETB-RTM-001. | Per-requirement trace current and in ETB-RTM-001. | #363 |
| AUD-v0.03-021 | SYS.5 | SYS.5.BP5 Summarize and communicate results | L | ETB-SYS5-002 §10, §11; ETB-SVD-001 §6, §7. | Later hardware runs (2026-10-06 to 2026-11-16) not cited by ETB-SYS5-002; ETB-SVD-001 §7 item 3 counts against 64. | A qualification summary per release against the current requirement set. | #363 |
| AUD-v0.03-022 | SWE.1 | SWE.1.BP1 Specify software requirements | L | ETB-SWE1-001 §6 to §19: 577 requirements (537 FR of which 536 in force, 40 NFR); each has a Verification cell. | The Verification cell holds a method only, not a verification criterion, although §3.1 claims the document defines the criteria. CON-01 and CON-07 are stale (hardware runs exist, `qualification/2026-10-23/`). | A verification criterion per requirement; constraints current. | #366 |
| AUD-v0.03-023 | SWE.1 | SWE.1.BP2 Structure software requirements | P | Grouped by element prefix (§5) and subsection. | No priority and no release allocation on any requirement. | Priority and release attributes, or a stated rule replacing them. | #366 |
| AUD-v0.03-024 | SWE.1 | SWE.1.BP3 Analyze software requirements | P | Implicit in §20 ASM-01 to -10, CON-01 to -12. | No recorded analysis of correctness, feasibility or verifiability. | Recorded analysis kept with the specification. | #366 |
| AUD-v0.03-025 | SWE.1 | SWE.1.BP4 Analyze the impact on the operating environment | P | §3.3 scope; ASM and CON entries. | No explicit operating-environment impact analysis. | Impact on the host, target and bench recorded per change. | #366 |
| AUD-v0.03-026 | SWE.1 | SWE.1.BP5 Ensure consistency and establish bidirectional traceability | P | All 638 FR source citations are STK-xx; all 577 IDs appear in ETB-RTM-001; `tests/test_traceability.py`. | No trace to any ETB-SYS2 requirement or ETB-SYS3 element; the 40 NFR have no source; ETB-RTM-001 §18 counts 532/533, actual 536/537. | Each SW requirement traced to system requirements and architecture, both ways, checked by a test. | #364 |
| AUD-v0.03-027 | SWE.1 | SWE.1.BP6 Communicate agreed software requirements | P | Merged by PR, published to the wiki, listed in ETB-SVD-001 §5.3 (1.70, Draft). | As SYS.2 BP6. | As SYS.2 BP6. | #371 |
| AUD-v0.03-028 | SWE.2 | SWE.2.BP1 Specify static aspects of the software architecture | L | ETB-SWE2-001 §5 layering, §6 22 elements, §10 external interfaces; allocation in ETB-RTM-001 Architecture column and §17. | §5 diagram omits the s2lp, gpd3303d, tti1604 and picoscope packages; §10 omits the GPD-3303D, TTi 1604, S2-LP kit and J-Link Commander links; ETB-RTM-001 §17 has no DMM-ARC-001 or SER-ARC-001 rows. | Views and allocation current with the release. | #367 |
| AUD-v0.03-029 | SWE.2 | SWE.2.BP2 Specify dynamic aspects of the software architecture | P | ETB-SWE2-001 §8 one sequence diagram (runner with TDS3014B). | No state models; dynamic behaviour of 15 other elements not described. | Dynamic views for each element with behaviour over time. | #367 |
| AUD-v0.03-030 | SWE.2 | SWE.2.BP3 Analyze the software architecture | L | §4 drivers D1 to D11; §7 decisions AD-01 to AD-32 with rationale; §9 resources for scope, J-Link, BLE. | Alternatives recorded for 4 of 32 decisions; no resource analysis for PSU, DMM, S2LP, PICO, PSCOPE, PPK, VIEW. | Alternatives and resource analysis for every significant element. | #367 |
| AUD-v0.03-031 | SWE.2 | SWE.2.BP4 Ensure consistency and establish bidirectional traceability | L | `test_every_decision_is_traced_in_the_matrix`; ETB-RTM-001 §17, §18. | No trace to the system architecture (ETB-SYS3-001). | Architecture elements traced to SYS3 elements. | #364 |
| AUD-v0.03-032 | SWE.2 | SWE.2.BP5 Communicate agreed software architecture | P | Merged by PR; ETB-SVD-001 §5.3 (0.33, Draft). | As SYS.2 BP6. | As SYS.2 BP6. | #371 |
| AUD-v0.03-033 | SWE.3 | SWE.3.BP1 Specify the static aspects of the detailed design | L | ETB-SWE3-001 §5.1 to §5.13: 150 design units; ETB-SWE3-002 for the GPD-3303D. | §4 catalogue says 95 units with wrong per-element counts and no DMM or VIEW rows; §4.1 package tree omits tti1604, pico2_test_board, viewer and two firmware trees. | Catalogue and package tree current. | #367 |
| AUD-v0.03-034 | SWE.3 | SWE.3.BP2 Specify dynamic aspects of the detailed design | P | Prose; ETB-SWE3-002 §5.3 sequence diagram, §5.4 state. | No sequence or state diagrams in ETB-SWE3-001. | Dynamic design for units with state or timing behaviour. | #367 |
| AUD-v0.03-035 | SWE.3 | SWE.3.BP4 Ensure consistency and establish bidirectional traceability | L | ETB-RTM-001 §5 to §17 trace requirement, architecture, design unit, source, test. | `core/transport/vxi11.py`, `socket_raw.py`, `visa_backend.py` cite legacy IDs (`SWE3-DD-VXI11`, etc.); `instruments/generic.py` cites no unit; the 19 `firmware/s2lp_kit` files carry no trace line; six units cited by no code; ETB-RTM-001 §18 "every module names its design unit" is overstated. | Every unit traced to code and code to unit, checked mechanically. | #368 |
| AUD-v0.03-036 | SWE.3 | SWE.3.BP5 Communicate agreed design and developed units | P | Merged by PR; ETB-SVD-001 §5.3 (1.90, Draft). | As SYS.2 BP6. | As SYS.2 BP6. | #371 |
| AUD-v0.03-037 | SWE.4 | SWE.4.BP1 Specify software unit verification measures | L | ETB-SWE4-001 §5 133 test groups with verified requirements; §4.7 pass criteria PC-1 to PC-12; §4.3 oracle independence; §4.5 layering. | Section numbering stale (§1.4a/§1.4b inside §4; PC-5, PC-6 cite §1.5, §1.4); §4.2 states CPython 3.11.15; §4.1 "no test is skipped" conflicts with SWE4-UT-DMMBENCH; pylint not stated as a unit measure. | Specification internally consistent and current. | #369 |
| AUD-v0.03-038 | SWE.4 | SWE.4.BP2 Select software unit verification measures | L | ETB-SWE4-001 §4.6 techniques, one regression test per defect; whole suite every change (`tests.yml`, gate 90%). | `firmware.yml` runs only on `firmware/**` changes; the rule is not stated in ETB-SWE4-001. | Selection rule stated, including path-filtered firmware runs. | #369 |
| AUD-v0.03-039 | SWE.4 | SWE.4.BP3 Verify software units | L | CI on 4b71a51: 4 555 passed, 2 skipped, coverage 95.3 % (run 44057132180); firmware unit tests green (run 44057131868). ETB-SWE4-002 §5 per-group results. | ETB-SWE4-002 §4 last whole-suite record is 3 374 tests (1.32, 2026-10-24); §5 rows sum to about 4 789; SWE4-UT-DMMBENCH not run; the release coverage is not recorded in any document. | Results recorded for the released baseline, totals consistent. | #369 |
| AUD-v0.03-040 | SWE.4 | SWE.4.BP4 Ensure consistency and establish bidirectional traceability | L | ETB-RTM-001 requirement to test; `TestVerificationReport` group to result. | Results per group only; JUnit records not kept. | Results traceable per test for the release (CI artefact or record). | #369 |
| AUD-v0.03-041 | SWE.4 | SWE.4.BP5 Summarize and communicate results | P | ETB-SWE4-002 §16 verdict PASS; ETB-SVD-001 §6. | §16 cites 2 558 tests, 61 firmware cases and a retired ID; §17 cites 1 807 passed; §4 and §16 say the dongle firmware never ran, §10.5 to §10.8 record runs on COM10. | Verdict and summary current and consistent. | #369 |
| AUD-v0.03-042 | SWE.5 | SWE.5.BP1 Specify software integration verification measures | L | ETB-SWE5-001 §4 stages I1 to I8, §5 nine groups, §6 ETB-IT-01 to -10, §7 criteria. | Unchanged in substance since 2026-09. | Specification current with the release's elements. | #370 |
| AUD-v0.03-043 | SWE.5 | SWE.5.BP2 Select software integration verification measures | L | §8 whole suite every change. | Selection not linked to the cases in §6. | Selection per case stated. | #370 |
| AUD-v0.03-044 | SWE.5 | SWE.5.BP3 Integrate software elements and perform integration verification | L | Continuous: `tests.yml` and `bench.yml` (Simulated bench) green on 4b71a51 (runs 44057132180, 44057132025). | All simulated by design; no record per ETB-IT case. | Results recorded per integration case. | #370 |
| AUD-v0.03-045 | SWE.5 | SWE.5.BP4 Ensure consistency and establish bidirectional traceability | P | Cases mapped to directories. | No test cites an ETB-IT ID; no SWE.5 column in ETB-RTM-001; not checked by `test_traceability.py`. | Cases traced to tests and results, checked. | #370 |
| AUD-v0.03-046 | SWE.5 | SWE.5.BP5 Summarize and communicate results | P | ETB-SWE5-001 §9, §10. | §9 says 1 878 tests and 94 %; points to ETB-SWE4-002 §17 for defects (they are in §15). | Results summary per release. | #370 |
| AUD-v0.03-047 | SWE.6 | SWE.6.BP1 Specify verification measures for software verification | L | ETB-SWE6-001 §5: 21 cases ETB-QT-01 to -20 and -02a; §4 strategy; §6 exit criteria. | ETB-QT-05 used for two different cases; most cases name requirement groups by wildcard. | Unique case IDs, each naming the requirements it qualifies. | #370 |
| AUD-v0.03-048 | SWE.6 | SWE.6.BP2 Select verification measures | P | Implicit: the whole suite. | No selection stated per release; ETB-TMPL-002 manual cases none. | Selection per release stated. | #370 |
| AUD-v0.03-049 | SWE.6 | SWE.6.BP3 Verify the integrated software | P | ETB-SWE6-001 §7; release figures in ETB-SVD-001 §6. | §7 says 1 878 tests and 94 % (2026-09); no per-case results for ETB-QT-01 to -20. | Per-case results for the release. | #370 |
| AUD-v0.03-050 | SWE.6 | SWE.6.BP4 Ensure consistency and establish bidirectional traceability | P | Two test modules cite a QT ID; requirement coverage via ETB-RTM-001. | QT cases not traced to tests or results. | Each QT case traced to its tests and result. | #370 |
| AUD-v0.03-051 | SWE.6 | SWE.6.BP5 Summarize and communicate results | P | ETB-SWE6-001 §7, §8; ETB-SVD-001 §6, §7. | Stale; only ETB-SVD-001 is current. | A qualification summary per release. | #370 |
| AUD-v0.03-052 | MAN.3 | MAN.3.BP2 Define project life cycle | L | §7 incremental life cycle, milestones M1 to M6. | "M5 is in progress" unchanged since 2026-09-19; releases v0.01 to v0.03 not mapped to milestones. | Life cycle and milestone status current. | #372 |
| AUD-v0.03-053 | MAN.3 | MAN.3.BP3 Evaluate feasibility of the project | N | None found. | No feasibility evaluation. | A recorded feasibility evaluation, revisited at milestones. | #372 |
| AUD-v0.03-054 | MAN.3 | MAN.3.BP4 Define and monitor work packages | L | §6 WP1 to WP7, §6.1 dependencies; issue #300 (24 dated comments, 2026-10-25 to 2026-11-15). | Work packages omit the PICO2 Test Board, S2-LP kit firmware and plugins; status not tracked against the plan. | Work packages current and their status monitored. | #372 |
| AUD-v0.03-055 | MAN.3 | MAN.3.BP5 Define and monitor project estimates and resources | P | §8 proxy measures. | No estimates; §8 gives 1 878 tests and 94 % (actual 4 555, 95.3 %). | Estimates and resources defined and monitored. | #372 |
| AUD-v0.03-056 | MAN.3 | MAN.3.BP6 Define and monitor required skills, knowledge and experience | P | §5.1; ETB-DEV-001. | No competence record; deviation accepted. | Skills defined and monitored, or the deviation re-confirmed per release. | #372 |
| AUD-v0.03-057 | MAN.3 | MAN.3.BP7 Define and monitor project interfaces and agreed commitments | P | §9 interfaces. | Commitments not recorded; interfaces omit Pico Technology, Nordic PPK2 and the AI supplier. | Interfaces current; commitments recorded. | #372 |
| AUD-v0.03-058 | MAN.3 | MAN.3.BP8 Define and monitor project schedule | N | §7 "No dates are given"; fix order in #300. | No schedule; 0 GitHub milestones. | A schedule, even coarse, monitored against actuals. | #372 |
| AUD-v0.03-059 | MAN.3 | MAN.3.BP9 Ensure consistency | P | Plan referenced by other plans. | Plan not kept consistent with the project (BP2, BP4, BP5). | Plan revised when the project changes. | #372 |
| AUD-v0.03-060 | MAN.3 | MAN.3.BP10 Review and report progress of the project | P | §11 commit history as progress report; #300 comments; ETB-SVD-001 per release; #325 closing comment. | No milestone review held (ETB-PA2-001 GP 2.1.5). | Dated progress reviews at each milestone or release. | #372 |
| AUD-v0.03-061 | MAN.5 | MAN.5.BP2 Identify potential undesirable events | L | §6 register ETB-RISK-001 to -013. | Only ETB-RISK-013 (#141) added since the initial version; risks from new instruments and the plugin transition not identified. | Register revisited when the scope changes. | #372 |
| AUD-v0.03-062 | MAN.5 | MAN.5.BP3 Determine risks | L | §5, §6 probability, impact, exposure. | Not re-assessed since entry. | Ratings re-assessed at each review. | #372 |
| AUD-v0.03-063 | MAN.5 | MAN.5.BP4 Define risk treatment options | L | Treatment and trigger per risk. | As BP3. | As BP3. | #372 |
| AUD-v0.03-064 | MAN.5 | MAN.5.BP5 Define and perform risk treatment activities | L | ETB-RISK-006, -008, -009 Mitigated; ETB-RISK-011 treated 2026-10-06 (#229). | ETB-RISK-001 still Open although hardware runs exist (2026-10-04 to 2026-11-16). | Treatment status current. | #372 |
| AUD-v0.03-065 | MAN.5 | MAN.5.BP6 Monitor risks | N | §7 "No review records are shipped with this baseline; none have been held." | No risk review held. | Dated risk reviews. | #372 |
| AUD-v0.03-066 | MAN.5 | MAN.5.BP7 Take corrective action | P | ETB-RISK-011 via #229 and ETB-ACQ4-001 §7. | Only one instance; no review triggers corrective action. | Corrective action recorded from each review. | #372 |
| AUD-v0.03-067 | SUP.1 | SUP.1.BP1 Ensure independence of quality assurance | N | ETB-MAN3-001 §5: QA held by the project lead, also Reviewer and Approver; ETB-DEV-002 accepted. | QA not independent of the work it assures; this audit is performed by the author of the work products. | QA performed by a party independent of the work, or a deviation that covers QA explicitly. | #373 |
| AUD-v0.03-068 | SUP.1 | SUP.1.BP2 Define criteria for quality assurance | L | ETB-SUP1-001 §4 ETB-QA-001 to -008, §5; ETB-TMPL-001 §6 C1 to C6. | No criteria for process QA (only work products). | Process QA criteria defined. | #373 |
| AUD-v0.03-069 | SUP.1 | SUP.1.BP3 Assure quality of work products | P | Required checks green on every PR (PR #360: 19 check runs success); `claude-auto-review` reviews on PRs. | No record that C1 to C6 were applied before merge; no completed ETB-TMPL-001; `docs/aspice/reviews/` absent. | A record per PR that C1 to C6 were applied, by the Reviewer. | #371 |
| AUD-v0.03-070 | SUP.1 | SUP.1.BP4 Assure quality of process activities | N | None before this audit; #198 opened 2026-10-05 with no comments. | No process QA activity defined or performed. | Process audits defined in ETB-SUP1-001 and held. | #373 |
| AUD-v0.03-071 | SUP.1 | SUP.1.BP5 Summarize and communicate QA activities and results | P | ETB-ANA-001 snapshot. | ETB-ANA-001 stale (1 878 tests, 113 C violations against 107; §6.5 conflicts with #204). | A QA summary per release. | #373 |
| AUD-v0.03-072 | SUP.1 | SUP.1.BP6 Ensure resolution of non-conformances | P | ETB-ANA-001 §8 actions, some done. | Open actions 6.3 (MISRA) and 6.4 (-std) not tracked to closure (ETB-SVD-001 §7 items 10, 11). | Each non-conformance tracked to closure on an issue. | #373 |
| AUD-v0.03-073 | SUP.1 | SUP.1.BP7 Escalate non-conformances | L | ETB-SUP1-001 §8; project lead is final authority. | No escalation beyond the project lead; declared. | Escalation path recorded as a deviation, or one beyond the lead. | #373 |
| AUD-v0.03-074 | SUP.8 | SUP.8.BP1 Identify configuration items | L | ETB-SUP8-001 §4. | §4 ID column heading still "Document ID (TB-…)". | CI list current. | #374 |
| AUD-v0.03-075 | SUP.8 | SUP.8.BP2 Define configuration item properties | L | §4 "Versioned by"; §6.1 firmware manifests. | CI job still named "Pico thermometer" after #330 (tag CI check runs). | Names and properties current. | #374 |
| AUD-v0.03-076 | SUP.8 | SUP.8.BP5 Verify the information about configured items | P | §9 status accounting; `tests/test_doc_versions.py`; settings read back 2026-10-05, 2026-10-24. | No configuration or baseline audit; `scripts/doc_versions.py` keeps the SVD in `HELD_BACK` although ETB-SVD-001 0.10 uses the links (§6.2 says it is removed). | A configuration audit per baseline; inconsistencies fixed. | #374 |
| AUD-v0.03-077 | SUP.8 | SUP.8.BP6 Manage the storage of configuration items and baselines | P | §10 GitHub and clones; recovery procedure in CLAUDE.md. | No backup or restore check recorded. | A recorded recovery check. | #374 |
| AUD-v0.03-078 | SUP.9 | SUP.9.BP1 Identify and record the problem | L | 39 issues labelled `bug`, all closed. | Not on the ETB-PR-nnn record of ETB-SUP9-001 §6; `docs/aspice/problems/` absent though ETB-SUP1-001 §9 cites it. | Records as the plan defines, or the plan changed to the practice. | #375 |
| AUD-v0.03-079 | SUP.9 | SUP.9.BP2 Determine the cause and the impact of the problem | P | Cause analysed in 20 of 39 bug issues. | Severity S1 to S4 stated in 5 of 39. | Severity and cause on every problem. | #375 |
| AUD-v0.03-080 | SUP.9 | SUP.9.BP3 Authorize urgent resolution action | P | §5 S1 "stop other work". | Never invoked; no record. | Rule recorded as applied when an S1 occurs. | #375 |
| AUD-v0.03-081 | SUP.9 | SUP.9.BP4 Raise alert notifications | N | None defined. | No alert mechanism. | Alert rule defined and used. | #375 |
| AUD-v0.03-082 | SUP.9 | SUP.9.BP5 Initiate problem resolution | L | Fix by PR; ETB-SVD-001 §4 maps issue to PR. | Not per the plan's states. | As BP1. | #375 |
| AUD-v0.03-083 | SUP.9 | SUP.9.BP6 Track problems to closure | L | Issues closed after merge with a regression test (§7). | States beyond open/closed not recorded. | As BP1. | #375 |
| AUD-v0.03-084 | SUP.9 | SUP.9.BP7 Report the status of problem resolution activities | P | ETB-SVD-001 §7 known problems. | No trend analysis (§9). | Trend analysis per milestone or release. | #375 |
| AUD-v0.03-085 | SUP.10 | SUP.10.BP1 Identify and record the change requests | P | `enhancement` issues (48 closed, 7 open). | ETB-SUP10-001 §6 `change-request` label does not exist; no ETB-CR-nnn ID used. | Records as the plan defines, or the plan changed to the practice. | #375 |
| AUD-v0.03-086 | SUP.10 | SUP.10.BP2 Analyze and assess change requests | P | Issue and PR prose. | No structured impact analysis through ETB-RTM-001 (§5 step 2). | Impact analysis recorded per change request. | #375 |
| AUD-v0.03-087 | SUP.10 | SUP.10.BP3 Approve change requests before implementation | P | CLAUDE.md: work starts on the owner's request. | Approval before implementation not recorded per ticket; effectively the merge, after implementation. | Approval recorded before work starts. | #375 |
| AUD-v0.03-088 | SUP.10 | SUP.10.BP4 Establish bidirectional traceability | L | Issue, PR, merge commit; ETB-RTM-001. | No CR ID to trace by. | As BP1. | #375 |
| AUD-v0.03-089 | SUP.10 | SUP.10.BP5 Confirm the implementation of change requests | L | Required checks; ETB-SVD-001 §6. | Confirmation not recorded on the request. | Confirmation recorded on closure. | #375 |
| AUD-v0.03-090 | SUP.10 | SUP.10.BP6 Track change requests to closure | L | Issues closed after merge (e.g. #325). | As BP1. | As BP1. | #375 |
| AUD-v0.03-091 | ACQ.4 | ACQ.4.BP1 Agree on and maintain joint activities, interfaces and information exchanged | P | ETB-ACQ4-001 §9 "Not applicable: no agreements". | The AI model supplier (author of every work product, ETB-DEV-001) is not listed as a supplier. | Every supplier listed, with what is agreed or why nothing is. | #376 |
| AUD-v0.03-092 | ACQ.4 | ACQ.4.BP2 Exchange all agreed information | L | Upstream defects CStyleCheck#439, #447; Dependabot PRs declined with reasons (#219, #222 to #224, #248, #250). | §9 says there is no corrective-action mechanism, contradicted by the upstream reports. | Plan consistent with the practice. | #376 |
| AUD-v0.03-093 | ACQ.4 | ACQ.4.BP3 Review development work products with the supplier | L | CStyleCheck v1.6.0 (2026-10-05) and v1.6.1 (2026-10-06) re-checked (§7); ps3000a library 2026-11-13 (§4.4). | §4.3 "CPython 3.10 in CI" (CI runs 3.8, 3.9, 3.12). | Supplier facts current. | #376 |
| AUD-v0.03-094 | ACQ.4 | ACQ.4.BP4 Review progress of the supplier | L | Dependabot; weekly constraints refresh (§6). | Dependabot pip PRs #355 to #359 open on `develop` although §6 says pip updates were removed (unverified which path opened them). | Plan consistent with what opens update PRs. | #376 |
| AUD-v0.03-095 | ACQ.4 | ACQ.4.BP5 Act to correct deviations | L | Pin away from defects (§7). | Pico licence review open (§4.4). | Open supplier actions tracked to closure. | #376 |
| AUD-v0.03-096 | SWE.4, SUP.1 | GP 2.1.1 Identify the objectives and define a strategy for the performance of the process | L | Measurable objectives: ETB-SUP1-001 §4 ETB-QA-001 to -008; ETB-SWE4-001 §4.7 PC-1 to PC-12 (coverage gate 90 %). | Objectives carry no dates or per-release targets. | Per-process objectives with targets per release. | #372 |
| AUD-v0.03-097 | SYS.2, SYS.3, SYS.4, SYS.5, SWE.1, SWE.2, SWE.3, SWE.5, SWE.6, MAN.3, MAN.5, SUP.8, SUP.9, SUP.10, ACQ.4 | GP 2.1.1 Identify the objectives and define a strategy for the performance of the process | P | Product objectives only: ETB-MAN3-001 §4 ETB-OBJ-001 to -005. | No performance objectives or strategy stated for the process itself. | Objectives and a strategy stated for each process. | #372 |
| AUD-v0.03-098 | SYS.4, MAN.3 | GP 2.1.2 Plan the performance of the process | P | ETB-MAN3-001 §6, §7; ETB-SYS4-001 §4. | No schedule (ETB-MAN3-001 §7); SYS.4 performance not planned to happen. | Planned performance with dates or release targets. | #372 |
| AUD-v0.03-099 | SYS.2, SYS.3, SYS.5, SWE.1, SWE.2, SWE.3, SWE.4, SWE.5, SWE.6, MAN.5, SUP.1, SUP.8, SUP.9, SUP.10, ACQ.4 | GP 2.1.2 Plan the performance of the process | L | Work packages, life cycle and the support plans (ETB-SUP1-001, ETB-SUP8-001, ETB-SUP9-001, ETB-SUP10-001, ETB-MAN5-001, ETB-ACQ4-001); CI workflows run the SWE processes on every change. | No schedule (ETB-MAN3-001 §7). | As above. | #372 |
| AUD-v0.03-100 | SYS.4 | GP 2.1.3 Determine resource needs | P | ETB-SYS4-001 §6 entry criteria E3, E4. | Bench resources for integration not determined per case. | Resource needs stated per integration case. | #362 |
| AUD-v0.03-101 | SYS.2, SYS.3, SYS.5, SWE.1, SWE.2, SWE.3, SWE.4, SWE.5, SWE.6, MAN.3, MAN.5, SUP.1, SUP.8, SUP.9, SUP.10, ACQ.4 | GP 2.1.3 Determine resource needs | L | Tools pinned (ETB-SVD-001 §5.5); bench PC described (`benches/bench_pc.yaml`); roles (ETB-MAN3-001 §5). | Human effort not estimated (ETB-MAN3-001 §8). | Resource needs including effort recorded. | #372 |
| AUD-v0.03-102 | SYS.4 | GP 2.1.4 Identify and make available resources | P | Bench PC qualified 2026-10-04 and used through 2026-11-16 (`docs/aspice/qualification/`). | Resources exist but were not made available to SYS.4; ETB-PA2-001 GP 2.1.4 still says no instrument has been attached. | Bench time allocated to the integration cases. | #362 |
| AUD-v0.03-103 | SYS.2, SYS.3, SYS.5, SWE.1, SWE.2, SWE.3, SWE.4, SWE.5, SWE.6, MAN.3, MAN.5, SUP.1, SUP.8, SUP.9, SUP.10, ACQ.4 | GP 2.1.4 Identify and make available resources | L | Software resources pinned; bench PC with J-Link, dongle, S2-LP kit, GPD-3303D, TTi 1604, Pico 2 in use. | PicoScope 3000D, PPK2 and serial capture not yet available on the bench (ETB-SVD-001 §7 item 4). | Every instrument the release supports available on the bench. | #363 |
| AUD-v0.03-104 | SWE.1, SWE.2, SWE.3, SWE.4, SUP.8, ACQ.4 | GP 2.1.5 Monitor and adjust the performance of the process | L | Monitored mechanically on every change (required checks, ETB-SUP8-001 §5.5); documents revised in the same change (e.g. ETB-SWE4-002 1.87, #352). | No milestone review (ETB-PA2-001 GP 2.1.5); adjustment missed in parts (stale figures above). | Recorded monitoring against the objectives, with adjustment. | #372 |
| AUD-v0.03-105 | SYS.2, SYS.3, SYS.4, SYS.5, SWE.5, SWE.6, MAN.3, MAN.5, SUP.1, SUP.9, SUP.10 | GP 2.1.5 Monitor and adjust the performance of the process | P | Plans and specifications exist. | Work products not adjusted as the project moved: ETB-SYS4-001, ETB-SWE5-001, ETB-SWE6-001, ETB-MAN3-001, ETB-MAN5-001, ETB-SUP1-001, ETB-SUP9-001, ETB-SUP10-001 unchanged in substance since 2026-09 or 2026-10-05; no milestone or risk review. | As above. | #372 |
| AUD-v0.03-106 | SUP.1, ACQ.4 | GP 2.1.6 Manage the interfaces between involved parties | P | ETB-MAN3-001 §5 roles; ETB-ACQ4-001 suppliers. | AI supplier not managed as an interface (ACQ.4); QA has no party separate from the work (SUP.1). | Interfaces to every involved party defined and managed. | #376 |
| AUD-v0.03-107 | SYS.2, SYS.3, SYS.4, SYS.5, SWE.1, SWE.2, SWE.3, SWE.4, SWE.5, SWE.6, MAN.3, MAN.5, SUP.8, SUP.9, SUP.10 | GP 2.1.6 Manage the interfaces between involved parties | L | ETB-MAN3-001 §5, §9, §11; owner instructions and decisions recorded on issues (e.g. #300). | One human party; communication outside the repository not recorded (ETB-PA2-001 GP 2.1.6). | Interfaces managed with records of decisions. | #372 |
| AUD-v0.03-108 | SYS.2, SYS.3, SYS.4, SYS.5, SWE.1, SWE.2, SWE.3, SWE.4, SWE.5, SWE.6, MAN.3, MAN.5, SUP.1, SUP.8, SUP.9, SUP.10, ACQ.4 | GP 2.2.1 Define the requirements for the work products | L | Uniform document layout; ETB-SUP1-001 §5; ETB-TMPL-001 §6 C1 to C6; ETB-TMPL-002. | No content requirements per work product type beyond the layout and review checklist. | Content requirements stated per work product type. | #371 |
| AUD-v0.03-109 | SYS.2, SYS.3, SYS.4, SYS.5, SWE.1, SWE.2, SWE.3, SWE.4, SWE.5, SWE.6, MAN.3, MAN.5, SUP.1, SUP.8, SUP.9, SUP.10, ACQ.4 | GP 2.2.3 Identify, store and control the work products | L | Git, document IDs, revision histories checked by `scripts/doc_versions.py check` (exit 0 at the tag); annotated tag v0.03.0000; ETB-SVD-001 §5.3. | Status not controlled: every document is Draft (ETB-SVD-001 §7 item 9) although ETB-SUP1-001 §6.3 defines when it leaves Draft; ETB-SYS2-001 §2 table broken by a blank line (rows 0.8 to 0.10 outside it); Referenced Documents tables cite 0.1 throughout. | Status maintained; references current; tables intact. | #377 |
| AUD-v0.03-110 | SWE.1, SWE.2, SWE.3, SWE.4 | GP 2.2.4 Review and adjust work products | L | Changes reviewed in rounds on the PR (e.g. #352 review rounds 1 and 2) and merged by or on the instruction of the owner (ETB-SUP8-001 §5.7). | The reviews on the last 15 merged PRs are `claude-auto-review` comments; no record shows the owner applied C1 to C6 (ETB-SUP1-001 §6.5); stale sections not adjusted (see SWE BPs). | A record of the Reviewer's review against C1 to C6 per PR, and work products adjusted. | #371 |
| AUD-v0.03-111 | SYS.2, SYS.3, SYS.4, SYS.5, SWE.5, SWE.6, MAN.3, MAN.5, SUP.1, SUP.8, SUP.9, SUP.10, ACQ.4 | GP 2.2.4 Review and adjust work products | P | Merge of the PR is the review (ETB-SUP8-001 §5.7, ETB-DEV-002 §4). | As above, and these work products were not adjusted when the facts changed; ETB-PA2-001 and ETB-ANA-001 §6.5 still say no review exists, which conflicts with #204; ETB-DEV-002 cites GP 2.2.3 for review where ETB-PA2-001 uses GP 2.2.4. | As above. | #371 |
| AUD-v0.03-112 | SWE.3 | SWE.3.BP3 Develop software units | L | 146 Python modules under `benchtools/`; three firmware trees; CStyleCheck v1.6.1 (`style.yml`) against ETB-STD-002; pylint (`lint.yml`); both green on 4b71a51 (CI run 44057131775, 44057131989). | Both checks pass against baselines of known violations: pylint 436 findings, CStyleCheck 107 (ETB-SVD-001 §5.5, §7 items 12, 13). No MISRA checker runs (§7 item 10); the dongle build sets no `-std` and no `-Wextra` (§7 item 11). | Units conform to ETB-STD-002 and the Python rules without a baseline, or each baselined violation dispositioned; MISRA and compiler flags in force. | #379 |

112 findings.

---

## 9. Follow-up

Each issue in §5.3 carries the `aspice` label, names its findings, and links
#198 and this report. Findings are grouped on one issue only where the same
work fixes them. When the findings are worked, a re-audit of a later release
is recorded as a new revision of this document or as a new report, and
ETB-PA2-001 is updated with the final ratings (#198, steps 8 and 9).

ETB-PA2-001 0.5 rates the generic practices once for the project, not per
process, and its text predates #204 and the hardware runs from 2026-10-04. It
is not changed by this audit; its update is #198 step 9.

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
