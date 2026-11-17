<img src="../../assets/brand/svg/logos/embeddedtestbench-logo-compact.svg" alt="Embedded Test Bench" width="240">

# Project Management Plan

*Automotive SPICE® PAM v4.0 | MAN.3 — Project Management*

---

## 1. Document Identification & Control

| Field | Value | Field | Value |
|---|---|---|---|
| **Document ID** | ETB-MAN3-001 | **Version** | [latest, §2](#2-revision-history) |
| **Project** | Embedded Test Bench | **Date** | [latest, §2](#2-revision-history) |
| **Status** | [by location, ETB-SUP1-001 §6.3](EmbeddedTestBench_SUP1_Quality_Assurance_Plan.md#63-document-status) | **Classification** | Internal |
| **Author** | Claude | **Reviewer** | Dermot Murphy |
| **Approver** | Dermot Murphy | **Related Process** | MAN.3 |

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
| next | 2026-11-17 | Claude | #371: the Status cell links to the status rule, ETB-SUP1-001 §6.3. A document's status follows from where it is in the repository (Released, Agreed, In review, In work) and is not written in by hand. §10: the work product review is the QA review on every pull request and the approval by its merge, not a step out of Draft. |
| next | 2026-11-17 | Claude | #377: Referenced Documents cite each controlled document at the version of its last numbered revision row, kept by `scripts/doc_versions.py` (ETB-SUP8-001 §6.2). |
| next | 2026-11-17 | Claude | #372: §4 adds ETB-OBJ-006, and §4.1 the process performance objectives and strategy for each process. §5 names the QA reviewer; §5.1 adds the skills and how they are monitored. §6 adds WP8 to WP12 and their monitoring. §7 maps the releases to milestones and restates M5; §7.1 adds the schedule, with GitHub milestones 1 and 2; §7.2 adds the feasibility evaluation. §8 gives the figures at `v0.03.0000`, and §8.1 adds the resource and effort estimates. §9 adds Pico Technology, Aim-TTi, Raspberry Pi and the AI supplier, and §9.1 the agreed commitments. §10.2 adds the release progress review, recorded in ETB-MAN3-002. |
| next | 2026-11-17 | Claude | #365, review of PR #393: §7 - what each release added, corrected against the tags. |

---

## 3. Purpose & Scope

### 3.1 Purpose

This plan says how Embedded Test Bench is run: what it is for, who does what, how work is
broken down and sequenced, how progress is judged, and what is done when the
plan and reality disagree.

It is a small project's plan and is written as one. A plan that describes
ceremonies nobody performs is worse than no plan, because it invites the reader
to believe them.

### 3.2 Referenced Documents

| Document ID | Title | Version |
|---|---|---|
| ETB-MAN5-001 | Embedded Test Bench Risk Management Plan | 0.7 |
| ETB-SUP1-001 | Embedded Test Bench Quality Assurance Plan | 0.5 |
| ETB-SUP8-001 | Embedded Test Bench Configuration Management Plan | 0.21 |
| ETB-SUP9-001 | Embedded Test Bench Problem Resolution Management Plan | 0.5 |
| ETB-SUP10-001 | Embedded Test Bench Change Request Management Plan | 0.5 |
| ETB-ACQ4-001 | Embedded Test Bench Supplier Monitoring Plan | 0.11 |
| ETB-SYS2-001 | Embedded Test Bench System Requirements Specification | 0.10 |
| ETB-DEV-001 | Embedded Test Bench AI Authorship Deviation | 0.5 |
| ETB-DEV-002 | Embedded Test Bench Independent Review Deviation | 0.5 |

### 3.3 Scope

Covers all Embedded Test Bench work: the `benchtools` Python package, the nRF52840 dongle
firmware under `firmware/`, the bench specifications under `specs/`, the GitHub
Actions workflows, and this document set. It does not cover the sensor products
that Embedded Test Bench is used to test — those are separate projects that consume
Embedded Test Bench as a tool.

---

## 4. Project Objectives

| ID | Objective | How it is judged |
|---|---|---|
| ETB-OBJ-001 | A bench measurement made through Embedded Test Bench can be reproduced by someone else from what Embedded Test Bench recorded | A report names the spec revision, the bench, every instrument identity, and whether the run was simulated |
| ETB-OBJ-002 | Instrument drivers refuse what the instrument cannot do rather than appearing to succeed | Every driver has negative tests for its refusals; see ETB-SWE4-002 |
| ETB-OBJ-003 | A test can be written by someone who is not a programmer | Bench specifications are YAML; BLE command sets are markdown tables |
| ETB-OBJ-004 | The documents and the code cannot drift apart unnoticed | `tests/test_traceability.py` fails the build when they do |
| ETB-OBJ-005 | Nothing is claimed about hardware that has not been measured on hardware | Unconfirmed items are listed as open bench-confirmation items in each element's notes |
| ETB-OBJ-006 | The processes in scope reach Capability Level 2, with PA 1.1, PA 2.1 and PA 2.2 Fully achieved | The re-audit of `v0.04.0000` (#380), by the method of ETB-SUP1-002 |

### 4.1 Process Performance Objectives and Strategy (GP 2.1.1)

Each process in scope has an objective for its own performance, a target for
each of the next two releases, and a strategy for reaching it. The targets are
measured at each release review (§10.2) and recorded in ETB-MAN3-002.

| Process | Objective | Target, `v0.04.0000` | Target, `v0.05.0000` | Strategy |
|---|---|---|---|---|
| SYS.2 | Every system requirement current, analysed and traced both ways | All 67 requirements carry priority, release and analysis; trace in ETB-RTM-001, checked by a test (#364, #365) | Requirements stay current | Requirement changes go through ETB-SUP10-001 with an impact statement |
| SYS.3 | Every system element in the architecture, with dynamic views and recorded decisions | An element for every instrument in the release (#365) | As `v0.04.0000` | Architecture changes in the same pull request as the element |
| SYS.4 | Integration cases for every interface, performed on the bench | Cases and traces written; execution deviated (#362) | Every case performed on the bench, with a dated report | Bench time planned per case (§8.1) |
| SYS.5 | Every system requirement qualified on hardware for the release | Scenarios cover all 67 requirements; execution deviated (#363) | All 67 qualified on hardware | As SYS.4 |
| SWE.1 | Every software requirement with a verification criterion, priority and release | Every requirement (#366) | Maintained | Attribute checks added to the traceability test |
| SWE.2, SWE.3 | Views, catalogue and dynamic design current with the code | Current at `v0.04.0000` (#367, #368) | Maintained | Design updated in the same change as the code (ETB-SUP1-001 §6.1) |
| SWE.4 | Results recorded per release, with consistent totals | ETB-SWE4-002 current (#369) | Maintained | Results taken from the release's CI run |
| SWE.5, SWE.6 | Cases traced to tests and results, per release | Per-case results (#370) | Maintained | As SWE.4 |
| MAN.3 | Plan current; progress reviewed at each release | Release review held and recorded (§10.2) | As `v0.04.0000` | This plan, revised at each review |
| MAN.5 | Risks reviewed at each release | Risk review held and recorded | As `v0.04.0000` | ETB-MAN5-001 §7 |
| SUP.1 | QA review on every pull request; process QA per release | Every pull request (ETB-SUP1-001 §6.5, §6.7) | As `v0.04.0000` | The PR Review session |
| SUP.8 | Configuration audit and recovery check per release | Recorded in ETB-SUP8-002 | As `v0.04.0000` | ETB-SUP8-001 §7.1, §10 |
| SUP.9, SUP.10 | Every problem with a severity and a cause; every change request approved before work | Every one from #375 on | As `v0.04.0000` | ETB-SUP9-001 §5, ETB-SUP10-001 §5 |
| ACQ.4 | Every supplier listed and monitored; open supplier actions tracked | #382 closed | As `v0.04.0000` | ETB-ACQ4-001 §6 |

---

## 5. Organisation & Responsibilities

| Role | Holder | Responsibility |
|---|---|---|
| Project lead | Dermot Murphy | Scope, priorities, acceptance of every work product, final say on all decisions |
| Reviewer | Dermot Murphy | Review of work products against ETB-TMPL-001 |
| Approver | Dermot Murphy | Approval and release |
| Author / implementer | Claude | Drafts documents, writes code and tests, runs the suite, raises what it cannot resolve |
| Quality assurance | PR Review session (Claude), separate from the authoring session | QA review on every pull request, and process QA per release (ETB-SUP1-001 §6.5, §6.7; ETB-DEV-003) |
| Configuration management | Dermot Murphy | ETB-SUP8-001, in practice delegated to git and the CI workflows |

The team is one person plus a model. Both deviations from what ASPICE assumes
about staffing — authorship (ETB-DEV-001) and reviewer independence
(ETB-DEV-002) — are recorded rather than glossed over.

### 5.1 Competence

There is no competence record for the author (ETB-DEV-001 §4). The compensating
controls are in ETB-DEV-001 §5.3: mechanical traceability, a large automated
suite, simulators that model instrument behaviour rather than echo expected
replies, and explicit disclosure of what has not been confirmed on hardware.

The skills the project needs, who holds each, and how it is monitored:

| Skill | Held by | Monitored by |
|---|---|---|
| Embedded hardware, the bench instruments, and their safe use | Dermot Murphy | Bench runs; the rules for sessions in `docs/User_Manual.md` §8 |
| Python, C for the dongle, Pico and S2-LP firmware, CI | Claude, under ETB-DEV-001 | The required checks; the QA review; the trend analysis (ETB-SUP9-001 §9) |
| Automotive SPICE work products | Claude, with Dermot Murphy deciding | The internal audit (ETB-SUP1-002) and its re-audit (#380) |
| Review and approval | Dermot Murphy | The merge record (ETB-SUP8-001 §5.7) |

The deviation (ETB-DEV-001) is confirmed again at each release review (§10.2).
The review records whether the skills table still holds, and whether the trend
analysis shows a pattern that a missing skill would explain.

---

## 6. Work Breakdown

Work is organised by the thing being built, not by phase; each item carries its
own requirements, design, tests and documentation through to completion.

| WP | Work package | Principal work products |
|---|---|---|
| WP1 | Core framework — bench model, instrument registry, reports, firmware manifests | `benchtools/core/`, ETB-SWE2-001 §5 |
| WP2 | Instrument drivers — scope, PSU, J-Link, dongle, S2-LP | `benchtools/instruments/` |
| WP3 | Bench runner — spec language, limits, references, execution, reporting | `benchtools/runner/` |
| WP4 | Firmware — nRF52840 dongle application, DFU packaging | `firmware/nordic_dongle/` |
| WP5 | Bench specifications — sensor bring-up, BLE command scripts | `specs/`, `benches/` |
| WP6 | Process documentation — this document set | `docs/aspice/` |
| WP7 | Continuous integration — firmware build, coding-standard check, bench-runner action | `.github/workflows/`, `action.yml` |
| WP8 | PICO2 Test Board — firmware and driver | `firmware/pico2_test_board/`, `benchtools/instruments/pico2_test_board/` |
| WP9 | The project's own S2-LP kit firmware (#84) | `firmware/s2lp_kit/` |
| WP10 | Plugins — the device-under-test plugin interface and the Kepler plugin (#238, #303) | `plugins/` |
| WP11 | Test run viewer | `benchtools/viewer/` |
| WP12 | Process improvement to Capability Level 2 (#380) | `docs/aspice/`; the audit finding issues #362 to #379 |

The status of each work package is monitored at each release review (§10.2)
against its milestone, and recorded in ETB-MAN3-002.

### 6.1 Dependencies

WP3 depends on WP1 and WP2. WP5 depends on WP2, WP3 and WP4. WP7 depends on
WP3 and WP4. WP6 tracks all of them and is updated in the same change as the
thing it documents — never afterwards as a catch-up (ETB-SUP1-001 §6).

---

## 7. Life Cycle & Milestones

Embedded Test Bench uses an incremental life cycle. Each increment delivers a capability
that can be exercised end to end, with its documents updated in the same change.

| Milestone | Definition of done |
|---|---|
| M1 Framework usable | A bench description loads, an instrument opens, a report is written |
| M2 Instruments covered | Each instrument in ETB-SYS2-001 §6 has a driver, a simulator and unit tests |
| M3 Specifications run | A YAML bench specification runs end to end against the simulated bench |
| M4 Firmware releasable | The dongle firmware builds in CI and produces a DFU package |
| M5 Process baseline | This document set is complete, reviewed and approved |
| M6 Hardware confirmed | Every open bench-confirmation item is closed against real instruments |

Releases map to milestones as below. Each release is a baseline
(ETB-SUP8-001 §7).

| Release | Date | Milestones it meets |
|---|---|---|
| `v0.01.0000` | 2026-10-05 | M1, M2, M3, M4: oscilloscope, supply, J-Link, BLE dongle, S2-LP kit (ST firmware), TTi 1604 and the Pico 2 thermometer |
| `v0.01.0001` | 2026-10-05 | Hotfix |
| `v0.02.0000` | 2026-10-23 | M2 and M3 extended: firmware update over BLE (DFU), the simulated Kepler sensor, dongle fixes, default timeouts in command documents |
| `v0.02.0001`, `v0.02.0002` | 2026-10-23 | Hotfixes |
| `v0.03.0000` | 2026-11-17 | M2 extended: PicoScope 3000D, PPK2, serial capture, the S2-LP kit's own firmware, the PICO2 Test Board (renamed from the thermometer); the first internal audit (ETB-SUP1-002) |

M1 to M4 are met. #371 redefined M5. There is no Draft status to leave, and the
baseline is reviewed and approved by the merge of each change. M5 is therefore
met when the audit findings are closed and the re-audit rates every process at
Capability Level 2 (#380). M6 is open: it is the hardware execution of SYS.4
and SYS.5 (#362, #363).

### 7.1 Schedule

A coarse schedule, drafted from the pace of the work so far. From 2026-10-24 to
the `v0.03.0000` tag (2026-11-17T09:36:13Z), 47 pull requests were merged and
39 issues closed: about two pull requests a day. The dates are targets, not commitments. Each target is a GitHub
milestone, and the issues it needs are assigned to it.

| Target | Date | Contents | GitHub milestone |
|---|---|---|---|
| `v0.04.0000` | 2026-12-08 | Audit findings #362 to #379 closed; #382, #384, #385; the re-audit (#380); M5 | 1, "v0.04.0000 — audit findings closed" |
| `v0.05.0000` | 2027-01-19 | SYS.4 integration cases and SYS.5 qualification performed on the bench; M6 | 2, "v0.05.0000 — hardware qualification" |

Progress against the schedule is checked at each release review (§10.2). A slip
of more than a week is recorded there with its cause, and the schedule in this
section is revised.

### 7.2 Feasibility (MAN.3.BP3)

Evaluated on 2026-11-17 for the two targets above. It is evaluated again at each
release review.

| Aspect | `v0.04.0000` | `v0.05.0000` |
|---|---|---|
| Technical | Feasible. The findings need documents, traces, checks and lint fixes, all of which the project has done before. #379 (lint and C to zero, MISRA) is the largest and least certain | Feasible with the instruments on the bench; ETB-SVD-001 §7 item 4 lists those not yet attached. Needs the PicoScope, the PPK2 and a serial target wired as SYS.4 requires |
| Resources | The owner's review of about 20 pull requests; two Claude Code sessions, one authoring and one for QA | About 4 bench days (§8.1), with the owner on the bench for the safety rules |
| Schedule | About 15 working days at the pace above | About 4 weeks, depending on whether the bench is available (ETB-RISK-010) |
| Risks | ETB-RISK-004, ETB-RISK-014 | ETB-RISK-001, ETB-RISK-010 |
| Verdict | Feasible | Feasible if the bench is available; evaluated again at `v0.04.0000` |

---

## 8. Estimates & Effort

Effort is not tracked in hours. These measurable quantities are used instead,
at `v0.03.0000`:

| Measure | Value at `v0.03.0000` | Source |
|---|---|---|
| Automated tests passing | 4 555 (2 skipped) | CI run 44057132180 on `4b71a51` |
| Statement coverage | 95.3 % | As above |
| Requirements declared | see ETB-RTM-001 §3 | traceability check |
| Requirements without a test | 0 | `tests/test_traceability.py` |
| Open bench-confirmation items | see ETB-SYS5-001 §7 | element notes |

A change that reduces the first two, or increases the fourth, is a regression
regardless of what it adds. The values are taken again at each release review
(§10.2).

### 8.1 Resource and Effort Estimates (MAN.3.BP5, GP 2.1.3)

Estimated on 2026-11-17. Each release review records the actuals beside the
estimates.

| Resource | `v0.04.0000` estimate | `v0.05.0000` estimate | Basis |
|---|---|---|---|
| Owner: review and merge decisions | About 20 pull requests at about 15 minutes each: 5 hours | About 10 pull requests: 3 hours | The owner reviews from the QA review and the diff |
| Owner: bench time | None | 4 bench days. SYS.4: 16 cases at about 30 minutes each, 1 day. SYS.5: 67 requirements in 11 scenarios (QS-01, -01b, -02 to -10), 3 days | ETB-SYS4-001 §5; ETB-SYS5-001 §5 |
| Claude: authoring sessions | About 20 pull requests | About 10 pull requests, and the records of the bench runs | The pace in §7.1 |
| Claude: QA sessions | One review per pull request, of 1 to 4 rounds | As `v0.04.0000` | The reviews of #381 and #383 |
| Instruments | None | Every instrument in ETB-SVD-001 §5, on the bench at once | The SYS.4 cases |
| CI | GitHub-hosted runners | As `v0.04.0000` | `.github/workflows/` |

---

## 9. Interfaces

| Interface | Counterpart | Managed by |
|---|---|---|
| Instrument vendors — documentation, firmware, licence terms | Tektronix, GW Instek, SEGGER, Nordic (dongle, SDK, PPK2), STMicroelectronics, Pico Technology, Aim-TTi, Raspberry Pi | ETB-ACQ4-001 §4.1 |
| AI model supplier | Anthropic (Claude Code) | ETB-ACQ4-001 §4.5 |
| Open-source dependencies | PyPI packages, nRF5 SDK, GNU Arm toolchain | ETB-ACQ4-001 §6 |
| Coding-standard checker | `dermot-murphy/CStyleCheck` | ETB-ACQ4-001 §7, `.github/workflows/style.yml` |
| Users of Embedded Test Bench | Sensor product projects | Bench specifications and the documents in `docs/` |

### 9.1 Agreed Commitments (MAN.3.BP7)

The commitments made to other parties, and where each is recorded. A new
commitment is added here in the change that makes it.

| Commitment | To | Recorded on |
|---|---|---|
| A product project uses the bench only from a release on `main`, never from `develop` | The Kepler project (innovateuk-sensor) | `CLAUDE.md`, Releases and hotfixes; ETB-SUP8-001 §5.6 |
| The Kepler plugin and the simulated Kepler sensor stay in this repository while the move is paused | The Kepler project | #197, comment of 2026-11-15; #240 |
| No vendor source or documentation prose is reproduced | Every vendor | ETB-ACQ4-001 §4.2; ETB-RISK-005 |

Decisions between the owner and the sessions are recorded where they are acted
on: on the issue (ETB-SUP10-001 §5, step 3), or in the pull request (GP 2.1.6).

---

## 10. Monitoring & Control

| Activity | Frequency | Evidence |
|---|---|---|
| Full test suite | Every change, before commit | `pytest` output |
| Traceability check | Every change (part of the suite) | `tests/test_traceability.py` |
| Firmware build | Every push | `.github/workflows/firmware.yml` |
| C coding-standard check | Every push | `.github/workflows/style.yml` |
| QA review | Every pull request, before the merge | The QA review on the pull request (ETB-SUP1-001 §6.5) |
| Work product review and approval | Every pull request | The merge of the pull request (ETB-SUP1-001 §6.5, ETB-SUP8-001 §5.7) |
| Risk review | At each release review, and whenever a risk's trigger fires | ETB-MAN5-001 §7; ETB-MAN3-002 |
| Release progress review | At each release, before the release pull request into `main` | ETB-MAN3-002 (§10.2) |
| Process QA | At each release | ETB-SUP1-003 (ETB-SUP1-001 §6.7) |

### 10.1 Deviation Handling

A deviation from this plan is handled in the open: the plan is changed, or the
deviation is recorded as one (ETB-DEV-001, ETB-DEV-002 are the two standing
examples). Work is not recorded as conforming when it did not.

### 10.2 Release Progress Review (MAN.3.BP10, GP 2.1.5)

The review is held at each release, on the release branch, and recorded as a new
entry in ETB-MAN3-002. It covers:

1. milestones and schedule: what the release met, against §7.1, with any slip
   and its cause;
2. work packages: the status of each (§6);
3. measures: the §8 values, and the actual effort against the §8.1 estimates;
4. process objectives: each target in §4.1, met or not;
5. feasibility: §7.2 evaluated again for the next target;
6. skills: §5.1 confirmed again;
7. risks: the risk review of ETB-MAN5-001 §7;
8. actions: each corrective action, with the issue that tracks it.

When the review finds that the plan no longer describes the project, the plan
is revised in the same pull request (MAN.3.BP9).

---

## 11. Communication & Reporting

Everything of record is in the repository. Day to day, the commit history is the
progress report, the test output is the status, and the documents in
`docs/aspice/` are the baseline. At each release, the progress review (§10.2)
is the report, recorded in ETB-MAN3-002. A decision made in
conversation that matters to the project is written into a document in the same
change that acts on it, because a conversation is not a work product.

---

## 12. Review & Approval

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
