# Configuration Management Plan

*Automotive SPICE® PAM v4.0 | SUP.8 — Configuration Management*

---

## 1. Document Identification & Control

| Field | Value | Field | Value |
|---|---|---|---|
| **Document ID** | TB-SUP8-001 | **Version** | 0.1 |
| **Project** | TestBench | **Date** | 2026-09-19 |
| **Status** | Draft | **Classification** | Internal |
| **Author** | Claude | **Reviewer** | Dermot Murphy |
| **Approver** | Dermot Murphy | **Related Process** | SUP.8 |

> Reviewer and Approver are the same person; see TB-DEV-002.

---

## 2. Revision History

| Version | Date | Author | Description of Change |
|---|---|---|---|
| 0.1 | 2026-09-19 | Claude | Initial |

---

## 3. Purpose & Scope

### 3.1 Purpose

This plan says what is under configuration control, how items are identified and
versioned, how baselines are made, and how the state of any TestBench result can
be reconstructed later.

The requirement that drives all of it: **a report produced by TestBench must be
reproducible from what the report itself records.** That is only true if every
input to the run is an identified configuration item.

### 3.2 Referenced Documents

| Document ID | Title | Version |
|---|---|---|
| TB-MAN3-001 | TestBench Project Management Plan | 0.1 |
| TB-SUP1-001 | TestBench Quality Assurance Plan | 0.1 |
| TB-SUP10-001 | TestBench Change Request Management Plan | 0.1 |
| TB-ACQ4-001 | TestBench Supplier Monitoring Plan | 0.1 |
| TB-SVD-001 | TestBench Software Version Description | 0.1 |

### 3.3 Scope

Everything in the repository, the external tools the build depends on, and the
physical bench instruments whose identity affects a result.

---

## 4. Configuration Items

| Class | Items | Identification | Versioned by |
|---|---|---|---|
| Documents | `docs/aspice/*.md`, `docs/templates/*.md`, guides in `docs/` | Document ID (TB-…) | Version field + git |
| Python source | `benchtools/**` | Module path | git |
| Tests | `tests/**` | pytest node ID | git |
| Firmware source | `firmware/nordic_dongle/**` | Path | git |
| Firmware images | `.hex`, `.zip` DFU packages | Filename + manifest | `firmware_manifest.json` beside the image |
| Bench descriptions | `benches/**` | Bench name | git |
| Bench specifications | `specs/**` | Spec filename | git |
| CI workflows and actions | `.github/workflows/*.yml`, `action.yml` | Filename | git |
| C rule configuration | `.cstylecheck.yml`, `.cstylecheck-baseline.json` | Filename | git — the baseline changes only with a recorded reason |
| Build tools | Python, `nrfutil`, GNU Arm toolchain, nRF5 SDK | Name + exact version | Pinned in the workflow; recorded in TB-SVD-001 |
| External actions | `dermot-murphy/CStyleCheck@v1` | Repository + tag | Pinned in the workflow |
| Bench instruments | Scope, supply, J-Link, dongle | Model + serial + firmware revision | Queried at run time and written into every report |

### 4.1 Instruments Are Configuration Items

An instrument's firmware revision changes what its commands mean. TestBench
therefore queries each instrument's identity at connection and records it in the
report, so that a result can be attributed to the instrument that produced it
rather than to the model name (TB-RISK-002).

---

## 5. Repository and Branching

| Item | Convention |
|---|---|
| Repository | `dermot-murphy/TestTools` |
| Default branch | `main` — always buildable; the suite passes on every commit |
| Work branches | One branch per piece of work, merged by pull request |
| Direct pushes to `main` | Not made; changes arrive through pull requests |
| History | Never rewritten on a branch someone else may have checked out |

A pull request is merged only when CI is green. A red build is fixed or the
change is withdrawn; it is not merged with a note to fix it afterwards.

---

## 6. Versioning

| Item | Scheme |
|---|---|
| Documents | `major.minor`, starting at 0.1; 0.x while Draft, 1.0 at first approval |
| Python package | Semantic versioning in `pyproject.toml` |
| Firmware | `major.minor.patch`, reported by the `rd version` command and recorded in the firmware manifest |
| Baselines | Annotated git tags |

### 6.1 Firmware Manifests

Every firmware image carries a `firmware_manifest.json` beside it giving its
version and build date. The runner compares the version a device reports with
the manifest for the image that was flashed, so an image that is not what the
report says it is fails the run rather than passing quietly (TB-RISK-009).

---

## 7. Baselines

A baseline is an annotated git tag plus a Software Version Description
(TB-SVD-001) naming exactly what the baseline contains — source revision,
document versions, firmware versions, tool versions and known problems.

| Baseline | When | Contents |
|---|---|---|
| Document baseline | When this document set is approved | All `docs/aspice/` documents at their approved versions |
| Release baseline | When a version of `benchtools` or the firmware is released | Source revision, images, manifests, tool versions, TB-SVD-001 |

A baseline is never edited. A correction produces a new baseline with a new
SVD, and the reason is recorded in the SVD's revision history.

---

## 8. Change Control

Changes to a baselined item follow TB-SUP10-001. Changes to items not yet
baselined follow ordinary development: branch, change, test, review, merge.

Every change, baselined or not, satisfies TB-SUP1-001 §6.1 — the documents move
with the code.

---

## 9. Status Accounting

The state of any configuration item is answered from the repository:

| Question | Answered by |
|---|---|
| What is in this release? | TB-SVD-001 for that baseline |
| What changed since the last baseline? | `git log <previous-tag>..<tag>` |
| Which document version is current? | The Version field in the document, on `main` |
| What produced this report? | The report's own header: spec revision, bench, instrument identities, simulated or not |
| What tool versions built this firmware? | The workflow file at that revision, plus TB-SVD-001 |

---

## 10. Backup and Retention

The authoritative copy is the GitHub repository. Every developer checkout is a
full clone and therefore a copy of the history. Build artefacts are reproducible
from a tagged revision and are not separately archived, with one exception:
firmware images that were flashed to a device during a recorded test run are
kept with that run's records, because the run cannot otherwise be reproduced.

---

## 11. Review & Approval

| Role | Name | Signature / Electronic Approval | Date |
|---|---|---|---|
| Author | Claude | Approved | 2026-09-19 |
| Reviewer | Dermot Murphy | — | *pending* |
| Approver | Dermot Murphy | — | *pending* |
