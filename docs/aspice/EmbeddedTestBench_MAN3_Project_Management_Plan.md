# Project Management Plan

*Automotive SPICE® PAM v4.0 | MAN.3 — Project Management*

---

## 1. Document Identification & Control

| Field | Value | Field | Value |
|---|---|---|---|
| **Document ID** | ETB-MAN3-001 | **Version** | 0.3 |
| **Project** | Embedded Test Bench | **Date** | 2026-10-05 |
| **Status** | Draft | **Classification** | Internal |
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
| ETB-MAN5-001 | Embedded Test Bench Risk Management Plan | 0.1 |
| ETB-SUP1-001 | Embedded Test Bench Quality Assurance Plan | 0.1 |
| ETB-SUP8-001 | Embedded Test Bench Configuration Management Plan | 0.1 |
| ETB-SUP9-001 | Embedded Test Bench Problem Resolution Management Plan | 0.1 |
| ETB-SUP10-001 | Embedded Test Bench Change Request Management Plan | 0.1 |
| ETB-ACQ4-001 | Embedded Test Bench Supplier Monitoring Plan | 0.1 |
| ETB-SYS2-001 | Embedded Test Bench System Requirements Specification | 0.1 |
| ETB-DEV-001 | Embedded Test Bench AI Authorship Deviation | 0.1 |
| ETB-DEV-002 | Embedded Test Bench Independent Review Deviation | 0.1 |

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

---

## 5. Organisation & Responsibilities

| Role | Holder | Responsibility |
|---|---|---|
| Project lead | Dermot Murphy | Scope, priorities, acceptance of every work product, final say on all decisions |
| Reviewer | Dermot Murphy | Review of work products against ETB-TMPL-001 |
| Approver | Dermot Murphy | Approval and release |
| Author / implementer | Claude | Drafts documents, writes code and tests, runs the suite, raises what it cannot resolve |
| Quality assurance | Dermot Murphy | ETB-SUP1-001 |
| Configuration management | Dermot Murphy | ETB-SUP8-001, in practice delegated to git and the CI workflows |

The team is one person plus a model. Both deviations from what ASPICE assumes
about staffing — authorship (ETB-DEV-001) and reviewer independence
(ETB-DEV-002) — are recorded rather than glossed over.

### 5.1 Competence

There is no competence record for the author (ETB-DEV-001 §4). The compensating
controls are in ETB-DEV-001 §5.3: mechanical traceability, a large automated
suite, simulators that model instrument behaviour rather than echo expected
replies, and explicit disclosure of what has not been confirmed on hardware.

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

M1–M4 are met. M5 is in progress — this document is part of it. M6 is open and
is the largest remaining body of work; the open items are listed per element in
ETB-SWE3-001 and summarised in ETB-SYS5-001 §7.

No dates are given. A one-person project's schedule is set by when that person
is working on it, and a fabricated date is a worse plan than an honest absence
of one.

---

## 8. Estimates & Effort

Effort is not tracked in hours. The measurable quantities used instead:

| Measure | Current value | Source |
|---|---|---|
| Automated tests passing | 1 878 | `pytest` |
| Statement coverage | 94% | `pytest --cov=benchtools` |
| Requirements declared | see ETB-RTM-001 §3 | traceability check |
| Requirements without a test | 0 | `tests/test_traceability.py` |
| Open bench-confirmation items | see ETB-SYS5-001 §7 | element notes |

A change that reduces the first two, or increases the fourth, is a regression
regardless of what it adds.

---

## 9. Interfaces

| Interface | Counterpart | Managed by |
|---|---|---|
| Instrument vendors — documentation, firmware, licence terms | Tektronix, GW Instek, SEGGER, Nordic, STMicroelectronics | ETB-ACQ4-001 |
| Open-source dependencies | PyPI packages, nRF5 SDK, GNU Arm toolchain | ETB-ACQ4-001 §6 |
| Coding-standard checker | `dermot-murphy/CStyleCheck` | ETB-ACQ4-001 §7, `.github/workflows/style.yml` |
| Users of Embedded Test Bench | Sensor product projects | Bench specifications and the documents in `docs/` |

---

## 10. Monitoring & Control

| Activity | Frequency | Evidence |
|---|---|---|
| Full test suite | Every change, before commit | `pytest` output |
| Traceability check | Every change (part of the suite) | `tests/test_traceability.py` |
| Firmware build | Every push | `.github/workflows/firmware.yml` |
| C coding-standard check | Every push | `.github/workflows/style.yml` |
| Work product review | Before a document's status moves past Draft | ETB-TMPL-001 record |
| Risk review | At each milestone, and whenever a risk's trigger fires | ETB-MAN5-001 §7 |

### 10.1 Deviation Handling

A deviation from this plan is handled in the open: the plan is changed, or the
deviation is recorded as one (ETB-DEV-001, ETB-DEV-002 are the two standing
examples). Work is not recorded as conforming when it did not.

---

## 11. Communication & Reporting

Everything of record is in the repository. There is no separate project
reporting: the commit history is the progress report, the test output is the
status, and the documents in `docs/aspice/` are the baseline. A decision made in
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
