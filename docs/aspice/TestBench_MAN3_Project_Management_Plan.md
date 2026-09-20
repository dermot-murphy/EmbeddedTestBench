# Project Management Plan

*Automotive SPICE® PAM v4.0 | MAN.3 — Project Management*

---

## 1. Document Identification & Control

| Field | Value | Field | Value |
|---|---|---|---|
| **Document ID** | TB-MAN3-001 | **Version** | 0.1 |
| **Project** | TestBench | **Date** | 2026-09-19 |
| **Status** | Draft | **Classification** | Internal |
| **Author** | Claude | **Reviewer** | Dermot Murphy |
| **Approver** | Dermot Murphy | **Related Process** | MAN.3 |

> Reviewer and Approver are the same person; see TB-DEV-002.

---

## 2. Revision History

| Version | Date | Author | Description of Change |
|---|---|---|---|
| 0.1 | 2026-09-19 | Claude | Initial |

---

## 3. Purpose & Scope

### 3.1 Purpose

This plan says how TestBench is run: what it is for, who does what, how work is
broken down and sequenced, how progress is judged, and what is done when the
plan and reality disagree.

It is a small project's plan and is written as one. A plan that describes
ceremonies nobody performs is worse than no plan, because it invites the reader
to believe them.

### 3.2 Referenced Documents

| Document ID | Title | Version |
|---|---|---|
| TB-MAN5-001 | TestBench Risk Management Plan | 0.1 |
| TB-SUP1-001 | TestBench Quality Assurance Plan | 0.1 |
| TB-SUP8-001 | TestBench Configuration Management Plan | 0.1 |
| TB-SUP9-001 | TestBench Problem Resolution Management Plan | 0.1 |
| TB-SUP10-001 | TestBench Change Request Management Plan | 0.1 |
| TB-ACQ4-001 | TestBench Supplier Monitoring Plan | 0.1 |
| TB-SYS2-001 | TestBench System Requirements Specification | 0.1 |
| TB-DEV-001 | TestBench AI Authorship Deviation | 0.1 |
| TB-DEV-002 | TestBench Independent Review Deviation | 0.1 |

### 3.3 Scope

Covers all TestBench work: the `benchtools` Python package, the nRF52840 dongle
firmware under `firmware/`, the bench specifications under `specs/`, the GitHub
Actions workflows, and this document set. It does not cover the sensor products
that TestBench is used to test — those are separate projects that consume
TestBench as a tool.

---

## 4. Project Objectives

| ID | Objective | How it is judged |
|---|---|---|
| TB-OBJ-001 | A bench measurement made through TestBench can be reproduced by someone else from what TestBench recorded | A report names the spec revision, the bench, every instrument identity, and whether the run was simulated |
| TB-OBJ-002 | Instrument drivers refuse what the instrument cannot do rather than appearing to succeed | Every driver has negative tests for its refusals; see TB-SWE4-002 |
| TB-OBJ-003 | A test can be written by someone who is not a programmer | Bench specifications are YAML; BLE command sets are markdown tables |
| TB-OBJ-004 | The documents and the code cannot drift apart unnoticed | `tests/test_traceability.py` fails the build when they do |
| TB-OBJ-005 | Nothing is claimed about hardware that has not been measured on hardware | Unconfirmed items are listed as open bench-confirmation items in each element's notes |

---

## 5. Organisation & Responsibilities

| Role | Holder | Responsibility |
|---|---|---|
| Project lead | Dermot Murphy | Scope, priorities, acceptance of every work product, final say on all decisions |
| Reviewer | Dermot Murphy | Review of work products against TB-TMPL-001 |
| Approver | Dermot Murphy | Approval and release |
| Author / implementer | Claude | Drafts documents, writes code and tests, runs the suite, raises what it cannot resolve |
| Quality assurance | Dermot Murphy | TB-SUP1-001 |
| Configuration management | Dermot Murphy | TB-SUP8-001, in practice delegated to git and the CI workflows |

The team is one person plus a model. Both deviations from what ASPICE assumes
about staffing — authorship (TB-DEV-001) and reviewer independence
(TB-DEV-002) — are recorded rather than glossed over.

### 5.1 Competence

There is no competence record for the author (TB-DEV-001 §4). The compensating
controls are in TB-DEV-001 §5.3: mechanical traceability, a large automated
suite, simulators that model instrument behaviour rather than echo expected
replies, and explicit disclosure of what has not been confirmed on hardware.

---

## 6. Work Breakdown

Work is organised by the thing being built, not by phase; each item carries its
own requirements, design, tests and documentation through to completion.

| WP | Work package | Principal work products |
|---|---|---|
| WP1 | Core framework — bench model, instrument registry, reports, firmware manifests | `benchtools/core/`, TB-SWE2-001 §5 |
| WP2 | Instrument drivers — scope, PSU, J-Link, dongle, S2-LP | `benchtools/instruments/` |
| WP3 | Bench runner — spec language, limits, references, execution, reporting | `benchtools/runner/` |
| WP4 | Firmware — nRF52840 dongle application, DFU packaging | `firmware/nordic_dongle/` |
| WP5 | Bench specifications — sensor bring-up, BLE command scripts | `specs/`, `benches/` |
| WP6 | Process documentation — this document set | `docs/aspice/` |
| WP7 | Continuous integration — firmware build, coding-standard check, bench-runner action | `.github/workflows/`, `action.yml` |

### 6.1 Dependencies

WP3 depends on WP1 and WP2. WP5 depends on WP2, WP3 and WP4. WP7 depends on
WP3 and WP4. WP6 tracks all of them and is updated in the same change as the
thing it documents — never afterwards as a catch-up (TB-SUP1-001 §6).

---

## 7. Life Cycle & Milestones

TestBench uses an incremental life cycle. Each increment delivers a capability
that can be exercised end to end, with its documents updated in the same change.

| Milestone | Definition of done |
|---|---|
| M1 Framework usable | A bench description loads, an instrument opens, a report is written |
| M2 Instruments covered | Each instrument in TB-SYS2-001 §6 has a driver, a simulator and unit tests |
| M3 Specifications run | A YAML bench specification runs end to end against the simulated bench |
| M4 Firmware releasable | The dongle firmware builds in CI and produces a DFU package |
| M5 Process baseline | This document set is complete, reviewed and approved |
| M6 Hardware confirmed | Every open bench-confirmation item is closed against real instruments |

M1–M4 are met. M5 is in progress — this document is part of it. M6 is open and
is the largest remaining body of work; the open items are listed per element in
TB-SWE3-001 and summarised in TB-SYS5-001 §7.

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
| Requirements declared | see TB-RTM-001 §3 | traceability check |
| Requirements without a test | 0 | `tests/test_traceability.py` |
| Open bench-confirmation items | see TB-SYS5-001 §7 | element notes |

A change that reduces the first two, or increases the fourth, is a regression
regardless of what it adds.

---

## 9. Interfaces

| Interface | Counterpart | Managed by |
|---|---|---|
| Instrument vendors — documentation, firmware, licence terms | Tektronix, GW Instek, SEGGER, Nordic, STMicroelectronics | TB-ACQ4-001 |
| Open-source dependencies | PyPI packages, nRF5 SDK, GNU Arm toolchain | TB-ACQ4-001 §6 |
| Coding-standard checker | `dermot-murphy/CStyleCheck` | TB-ACQ4-001 §7, `.github/workflows/style.yml` |
| Users of TestBench | Sensor product projects | Bench specifications and the documents in `docs/` |

---

## 10. Monitoring & Control

| Activity | Frequency | Evidence |
|---|---|---|
| Full test suite | Every change, before commit | `pytest` output |
| Traceability check | Every change (part of the suite) | `tests/test_traceability.py` |
| Firmware build | Every push | `.github/workflows/firmware.yml` |
| C coding-standard check | Every push | `.github/workflows/style.yml` |
| Work product review | Before a document's status moves past Draft | TB-TMPL-001 record |
| Risk review | At each milestone, and whenever a risk's trigger fires | TB-MAN5-001 §7 |

### 10.1 Deviation Handling

A deviation from this plan is handled in the open: the plan is changed, or the
deviation is recorded as one (TB-DEV-001, TB-DEV-002 are the two standing
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

| Role | Name | Signature / Electronic Approval | Date |
|---|---|---|---|
| Author | Claude | Approved | 2026-09-19 |
| Reviewer | Dermot Murphy | — | *pending* |
| Approver | Dermot Murphy | — | *pending* |
