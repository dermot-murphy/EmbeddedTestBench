<img src="../../assets/brand/svg/logos/embeddedtestbench-logo-compact.svg" alt="Embedded Test Bench" width="240">

# Configuration Audit and Recovery Check Record

*Automotive SPICE® PAM v4.0 | SUP.8 — Configuration Management*

---

## 1. Document Identification & Control

| Field | Value | Field | Value |
|---|---|---|---|
| **Document ID** | ETB-SUP8-002 | **Version** | [latest, §2](#2-revision-history) |
| **Project** | Embedded Test Bench | **Date** | [latest, §2](#2-revision-history) |
| **Status** | [by location, ETB-SUP1-001 §6.3](EmbeddedTestBench_SUP1_Quality_Assurance_Plan.md#63-document-status) | **Classification** | Internal |
| **Author** | Claude | **Reviewer** | Dermot Murphy |
| **Approver** | Dermot Murphy | **Related Process** | SUP.8 |

> Reviewer and Approver are the same person; see ETB-DEV-002.

---

## 2. Revision History

| Version | Date | Author | Description of Change |
|---|---|---|---|
| 0.1 | 2026-11-17 | Claude | #374: initial. Configuration audit CA1 to CA7 of `v0.03.0000` (ETB-SUP8-001 §7.1) and the first recovery check (ETB-SUP8-001 §10). |

---

## 3. Purpose & Scope

### 3.1 Purpose

This record holds one entry per release baseline. Each entry has the
configuration audit of ETB-SUP8-001 §7.1 and the recovery check of
ETB-SUP8-001 §10, with the commands that were run and what they returned, so
that someone else can repeat them. Entries are appended, oldest first, and are
not edited afterwards.

### 3.2 Referenced Documents

| Document ID | Title | Version |
|---|---|---|
| ETB-SUP8-001 | Embedded Test Bench Configuration Management Plan | 0.21 |
| ETB-SVD-001 | Embedded Test Bench Software Version Description | 0.10 |
| ETB-SUP1-002 | Internal Audit Report, `v0.03.0000` | 0.1 |

### 3.3 Scope

Release baselines, which are the tags `v<version>` on `main`, from `v0.03.0000` on.
Earlier tags are covered by the recovery check (§4.2, R2) but were not audited
against their SVDs.

---

## 4. Baseline `v0.03.0000`

Performed 2026-11-17 by Claude, during #374. The audit ran after the release,
not on the release branch as ETB-SUP8-001 §7.1 now requires; this first
audit is late because §7.1 did not exist at the release (ETB-SUP1-002,
AUD-v0.03-076).

### 4.1 Configuration Audit

| # | Check | Result | Evidence |
|---|---|---|---|
| CA1 | Tag annotated, on the release merge commit | Pass | `git cat-file -t v0.03.0000` is `tag`; `v0.03.0000^{commit}` is `4b71a519179105657c50b69be9f7e29dd3764192`, "Release v0.03.0000 (#325) (#360)", the merge commit of PR #360 into `main` |
| CA2 | Package version is the tag's | Pass | `pyproject.toml` `version = "0.03.0000"`; `benchtools/__init__.py` `__version__ = "0.03.0000"` |
| CA3 | ETB-SVD-001 §5.3 lists every controlled document at its version, and no other | Pass | 35 controlled documents at the tag, 35 rows in §5.3, no version mismatch, no document missing |
| CA4 | `scripts/doc_versions.py check` passes at the tag | Pass | Exit 0 on a working tree restored at the tag (§4.2, R4) |
| CA5 | Firmware manifests present | Pass | `firmware_manifest.json` under `benches/simulated/dongle/`, `benches/simulated/sensor/`, `specs/qualification/firmware/v10.01.2000/`, `.../v11.00.0000-96/` and `.../wrong_version/` |
| CA6 | Required checks passed on the release pull request | Pass | PR #360, merged 2026-11-17T09:36:13Z into `main`: 19 check runs, all `SUCCESS` |
| CA7 | Repository settings as ETB-SUP8-001 §5.5 | Pass | Ruleset 24468152 "Protect main and develop", active, on `refs/heads/main` and `refs/heads/develop`: deletion, non-fast-forward, pull request with 0 approvals, required checks `pytest (3.8)`, `pytest (3.9)`, `pytest (3.12)`, `pylint`, `Embedded C standard`, `Simulated bench`. Ruleset 24492273 "Protect release tags", active, on `refs/tags/v*`: deletion and update. Merge commits on, squash and rebase off, head branches deleted on merge |

Inconsistency found and fixed with this audit (#374): `scripts/doc_versions.py`
held ETB-SVD-001 in `HELD_BACK` although ETB-SVD-001 0.10 already uses the
links. The set is now empty.

### 4.2 Recovery Check

Started 2026-11-17T15:24:52Z, on the bench PC, in an empty directory.

| # | Check | Result | Evidence |
|---|---|---|---|
| R1 | A fresh mirror clones and is complete | Pass | `git clone --mirror https://github.com/dermot-murphy/EmbeddedTestBench.git`; `git fsck --full` exit 0; pack 15.31 MiB |
| R2 | Every release tag's tree is the same as in the working clone | Pass | `v0.01.0000`, `v0.01.0001`, `v0.02.0000`, `v0.02.0001`, `v0.02.0002`, `v0.03.0000`: `<tag>^{tree}` identical in both |
| R3 | `develop` and `main` at the commits GitHub shows | Pass | `develop` `1c514d5195389f5a142e4cda340cc8731234dfcd`, `main` `4b71a519179105657c50b69be9f7e29dd3764192`, in the mirror and in `origin/` |
| R4 | A working tree restored from the mirror is usable | Pass | `git clone` from the mirror, `git checkout v0.03.0000`, `python scripts/doc_versions.py check` exit 0, `git status` clean |
| R5 | Generated outputs can be fetched | Pass | Wiki: 54 files, last commit `32f8ea6` 2026-11-17T09:36:28Z "Regenerate the wiki from main at 4b71a51". `refs/heads/gh-pages` at `5916ac7f5ffbcea0b60bec690e506d6516d48a1c` |

Not covered: the issue tracker, pull request records and CI logs are held by
GitHub only and are not in a git clone. Their loss would remove the review and
approval records (ETB-SUP8-001 §5.7). This is recorded as a gap, not fixed here.

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
