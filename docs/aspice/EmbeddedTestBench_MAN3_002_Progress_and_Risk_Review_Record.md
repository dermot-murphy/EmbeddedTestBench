<img src="../../assets/brand/svg/logos/embeddedtestbench-logo-compact.svg" alt="Embedded Test Bench" width="240">

# Release Progress and Risk Review Record

*Automotive SPICE® PAM v4.0 | MAN.3 — Project Management, MAN.5 — Risk Management*

---

## 1. Document Identification & Control

| Field | Value | Field | Value |
|---|---|---|---|
| **Document ID** | ETB-MAN3-002 | **Version** | [latest, §2](#2-revision-history) |
| **Project** | Embedded Test Bench | **Date** | [latest, §2](#2-revision-history) |
| **Status** | [by location, ETB-SUP1-001 §6.3](EmbeddedTestBench_SUP1_Quality_Assurance_Plan.md#63-document-status) | **Classification** | Internal |
| **Author** | Claude | **Reviewer** | Dermot Murphy |
| **Approver** | Dermot Murphy | **Related Process** | MAN.3, MAN.5 |

> Reviewer and Approver are the same person; see ETB-DEV-002.

---

## 2. Revision History

| Version | Date | Author | Description of Change |
|---|---|---|---|
| 0.1 | 2026-11-17 | Claude | #372: initial. The first release progress review and risk review, for `v0.03.0000` (ETB-MAN3-001 §10.2, ETB-MAN5-001 §7). |

---

## 3. Purpose & Scope

### 3.1 Purpose

The record of each release progress review (ETB-MAN3-001 §10.2), including its
risk review (ETB-MAN5-001 §7). There is one entry per release. Entries are
appended, oldest first, and are not edited afterwards. A later finding is
recorded in a later entry.

### 3.2 Referenced Documents

| Document ID | Title | Version |
|---|---|---|
| ETB-MAN3-001 | Embedded Test Bench Project Management Plan | 0.5 |
| ETB-MAN5-001 | Embedded Test Bench Risk Management Plan | 0.7 |
| ETB-SUP1-002 | Internal Audit Report, `v0.03.0000` | 0.1 |

### 3.3 Scope

Releases from `v0.03.0000` on. The earlier releases were not reviewed. Their
mapping to milestones is in ETB-MAN3-001 §7.

---

## 4. Review: `v0.03.0000`

Held on 2026-11-17 by Claude, in the session working #372. It was held after the
release, not on the release branch as ETB-MAN3-001 §10.2 now requires, because
§10.2 did not exist at the release. The owner's review of it is the merge of the
pull request that adds this record.

### 4.1 Milestones and Schedule

| Milestone | Status at `v0.03.0000` |
|---|---|
| M1 to M4 | Met at `v0.01.0000` |
| M5 Process baseline | Not met. The audit rated 0 of 17 processes at Capability Level 2 (ETB-SUP1-002). Redefined by #371 (ETB-MAN3-001 §7), and targeted for `v0.04.0000` |
| M6 Hardware confirmed | Not met. Hardware runs from 2026-10-04 to 2026-11-16 cover part of it (ETB-SYS5-002); the full qualification is targeted for `v0.05.0000` |

There was no schedule before this review, so there is no slip to measure. The
schedule starts now, in ETB-MAN3-001 §7.1.

### 4.2 Work Packages

| WP | Status at `v0.03.0000` |
|---|---|
| WP1 Core framework | Done; maintained |
| WP2 Instrument drivers | Ten drivers; PicoScope 3000D, PPK2 and serial capture added since `v0.02.0002`. Hardware confirmation partial (ETB-SVD-001 §7) |
| WP3 Bench runner | Done; maintained |
| WP4 Dongle firmware | Done; `-std` and `-Wextra` open (#379) |
| WP5 Bench specifications | Kepler specifications held in innovateuk-sensor (#197, 2026-11-15) |
| WP6 Process documentation | Audited; 112 findings (ETB-SUP1-002) |
| WP7 CI | Done; Windows leg proposed (#385) |
| WP8 PICO2 Test Board | V1.00.0000 (ETB-SVD-001 §5.2) |
| WP9 S2-LP kit firmware | Merged (#84, PR #348) |
| WP10 Plugins | Interface and Kepler plugin merged (#238, #303); the move out is paused (#240) |
| WP11 Viewer | Done; maintained |
| WP12 Capability Level 2 | Started 2026-11-17: #371 and #377 merged |

### 4.3 Measures and Effort

| Measure | Value | Source |
|---|---|---|
| Tests passing | 4 555, 2 skipped | CI run 44057132180 on `4b71a51` |
| Statement coverage | 95.3 % | As above |
| Pull requests merged, 2026-10-24 to 2026-11-17 | 51 | `gh pr list --state merged` |
| Issues closed in the same period | 44, of which 9 labelled `bug` | `gh issue list --state closed` |
| Open issues at the review | 30 | `gh issue list --state open` |
| Effort | Not estimated before this review, so there is no comparison. Estimates start in ETB-MAN3-001 §8.1 | — |

### 4.4 Process Objectives

The objectives in ETB-MAN3-001 §4.1 were set at this review. There is no earlier
target to compare against. The baseline they start from is the audit's rating:
9 processes at CL1 and 8 at CL0 (ETB-SUP1-002).

### 4.5 Feasibility

Evaluated in ETB-MAN3-001 §7.2: both targets are feasible, `v0.05.0000` on the
condition that the bench is available.

### 4.6 Skills

The skills table in ETB-MAN3-001 §5.1 was written at this review. ETB-DEV-001 is
confirmed again. The trend analysis (ETB-SUP9-001 §9.1) shows that the largest
group of problems came from drivers built against assumptions about hardware.
That points to a missing check, a hardware run, rather than a missing skill.

### 4.7 Risk Review

The first risk review (ETB-MAN5-001 §7). P, I and Exp are the values after the
review.

| Risk | Trigger fired? | P | I | Exp | Change | Treatment still right? | Action |
|---|---|---|---|---|---|---|---|
| ETB-RISK-001 | Yes, repeatedly: #61, #64, #69, #76, #177 and others were found at first contact with hardware (ETB-SUP9-001 §9.1) | P3 | I3 | 9 | None | Yes. The hardware runs are the treatment that finds these | Requalify on hardware (#363) and run the integration cases (#362) for `v0.05.0000` |
| ETB-RISK-002 | No new instrument revision seen without its commands being confirmed | P2 | I3 | 6 | None | Yes | None |
| ETB-RISK-003 | No; the traceability check ran on every change | P3 | I2 | 6 | None | Yes, but the audit found blind spots in the check (#368) | Close the blind spots (#368) |
| ETB-RISK-004 | Yes, once: the pip pull requests after #284 were explained only by checking which branch Dependabot reads (ETB-ACQ4-001 §6) | P3 | I2 | 6 | None | Yes | None beyond `CLAUDE.md`'s "verify, don't assert" |
| ETB-RISK-005 | No | P2 | I3 | 6 | None | Yes | Pico licence review (#382) |
| ETB-RISK-006 | No | P3 | I2 | 6 | None | Yes; CI now installs exact pins (#282) | None |
| ETB-RISK-007 | Not observed | P2 | I3 | 6 | None | Yes | None |
| ETB-RISK-008 | No | P3 | I3 | 9 | None | Yes, mitigated | None |
| ETB-RISK-009 | No | P2 | I3 | 6 | None | Yes, mitigated | None |
| ETB-RISK-010 | No | P2 | I2 | 4 | None | Yes | Plan bench time for `v0.05.0000` (ETB-MAN3-001 §8.1) |
| ETB-RISK-011 | Earlier (v1.6.0, 2026-10-06); not since | P2 | I1 | 2 | None | Yes | None |
| ETB-RISK-012 | No | P2 | I2 | 4 | None | Yes | None |
| ETB-RISK-013 | No | P2 | I3 | 6 | None | Yes | None |
| ETB-RISK-014 | New: identified at this review | P2 | I2 | 4 | Raised | — | Revisit when #240 resumes |
| ETB-RISK-015 | New: identified at this review | P2 | I2 | 4 | Raised | — | None |
| ETB-RISK-016 | New: identified by the recovery check (ETB-SUP8-002) | P1 | I3 | 3 | Raised | — | Export the GitHub records (#387) |
| ETB-RISK-017 | New, and already fired: five Windows-only problems | P3 | I2 | 6 | Raised | — | Windows leg in CI (#385) |

New risks were looked for in the release's changes: three new instruments, the
plugin interface, the AI supplier as a listed supplier, and the GitHub records.
The four above were raised from them. The new instruments add no new risk: they
fall under ETB-RISK-001 and ETB-RISK-002.

### 4.8 Actions

| Action | Tracked on |
|---|---|
| Close the audit findings and re-audit | #362 to #379, #380 |
| Windows leg in CI | #385 |
| Export the GitHub-only records | #387 |
| Pico licence review | #382 |
| Intermittent `serial_capture` CLI test | #384 |

---

## 5. Review & Approval

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
