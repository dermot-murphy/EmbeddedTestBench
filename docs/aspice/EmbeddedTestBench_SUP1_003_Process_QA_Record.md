<img src="../../assets/brand/svg/logos/embeddedtestbench-logo-compact.svg" alt="Embedded Test Bench" width="240">

# Process Quality Assurance Record

*Automotive SPICE® PAM v4.0 | SUP.1 — Quality Assurance*

---

## 1. Document Identification & Control

| Field | Value | Field | Value |
|---|---|---|---|
| **Document ID** | ETB-SUP1-003 | **Version** | [latest, §2](#2-revision-history) |
| **Project** | Embedded Test Bench | **Date** | [latest, §2](#2-revision-history) |
| **Status** | [by location, ETB-SUP1-001 §6.3](EmbeddedTestBench_SUP1_Quality_Assurance_Plan.md#63-document-status) | **Classification** | Internal |
| **Author** | Claude | **Reviewer** | Dermot Murphy |
| **Approver** | Dermot Murphy | **Related Process** | SUP.1 |

> Reviewer and Approver are the same person; see ETB-DEV-002.

---

## 2. Revision History

| Version | Date | Author | Description of Change |
|---|---|---|---|
| 0.1 | 2026-11-17 | Claude | #373: initial. The first process QA audit (ETB-SUP1-001 §6.7): the 15 pull requests merged into `develop` from 2026-11-14 to 2026-11-17, and the QA summary for `v0.03.0000`. |
| next | 2026-11-17 | Claude | #373, review round 1 (PR #390): §4 states the sample's cutoff, the merge of #381 (`83443f7`), and that later pull requests belong to the next audit. |
| next | 2026-11-17 | Claude | #373, review round 2 (PR #390): §3.1 names PQ1 to PQ9. Audit 1 predates PQ9, which is n/a for it. |

---

## 3. Purpose & Scope

### 3.1 Purpose

The record of process QA (ETB-SUP1-001 §6.7): one entry per release, each giving
the pull requests checked against criteria PQ1 to PQ9, the failures and what was
done about them, and the QA summary for the release (SUP.1.BP5). Entries are
appended, oldest first, and are not edited afterwards.

### 3.2 Referenced Documents

| Document ID | Title | Version |
|---|---|---|
| ETB-SUP1-001 | Embedded Test Bench Quality Assurance Plan | 0.5 |
| ETB-SUP1-002 | Internal Audit Report, `v0.03.0000` | 0.1 |
| ETB-DEV-003 | Embedded Test Bench QA Independence Deviation | 0.1 |

### 3.3 Scope

Pull requests merged into `develop` or `main`.

---

## 4. Audit 1: The 15 Pull Requests Merged up to #381

Performed 2026-11-17 by Claude, in the session working #373. It was not
performed by the PR Review session, as §6.7 now requires, because §6.7 did not
exist yet. The PR Review session's QA review of the pull request that adds this
record is the independent check on it.

**Sample.** The 15 pull requests merged into `develop` up to and including the
merge of #381 (`83443f7`, 2026-11-17 15:36:51Z), from #337 on. It covers
the period of the gap ETB-SUP1-002 found under GP 2.2.4 (AUD-v0.03-110), and
ends with #381, the first pull request under the QA review of §6.5.
Pull requests merged after `83443f7` (#383 and later) belong to the next
audit. This is not every pull
request since `v0.02.0002`: the first audit is not a release audit, because
`v0.03.0000` was released before §6.7 existed.

**Evidence.** For each pull request:

- `gh pr view <n> --json baseRefName,mergeCommit,reviews,statusCheckRollup,title`;
- `git rev-list --parents -n1` and `git log -1 --format=%b` on the merge commit;
- `gh issue view` for the issue named in the title.

### 4.1 Results

| PR | Merged | Issue | PQ1 base | PQ2 merge | PQ3 checks | PQ4 QA review | PQ5 issue | PQ6 rows | PQ7 labels | PQ8 release |
|---|---|---|---|---|---|---|---|---|---|---|
| #381 | 2026-11-17 | #371 | Pass | Pass, note | Pass | Pass, 4 rounds | Pass | Pass | n/a | n/a |
| #378 | 2026-11-17 | #198 | Pass | Pass, note | Pass | n/a | Pass | Pass | n/a | n/a |
| #361 | 2026-11-17 | #325 | Pass, back-merge | Pass, note | Pass | n/a | Pass | Pass | n/a | n/a |
| #354 | 2026-11-15 | #349 | Pass | Pass, note | Pass | n/a | Pass | Pass | n/a | n/a |
| #353 | 2026-11-15 | #352 | Pass | Pass, note | Pass | n/a | Pass | Pass | n/a | n/a |
| #351 | 2026-11-15 | #349 | Pass | Pass, note | Pass | n/a | Pass | Pass | n/a | n/a |
| #350 | 2026-11-15 | #70 | Pass | Pass, note | Pass | n/a | Pass | Pass | n/a | n/a |
| #348 | 2026-11-15 | #84 | Pass | Pass, note | Pass | n/a | Pass | Pass | n/a | n/a |
| #347 | 2026-11-14 | #195 | Pass | Pass, note | Pass | n/a | Pass | Pass | n/a | n/a |
| #346 | 2026-11-14 | #335 | Pass | Pass, note | Pass | n/a | Pass | Pass | n/a | n/a |
| #345 | 2026-11-14 | #340 | Pass | Pass, note | Pass | n/a | Pass | Pass | n/a | n/a |
| #343 | 2026-11-14 | #342 | Pass | Pass, note | Pass | n/a | Pass | Pass | n/a | n/a |
| #339 | 2026-11-14 | #303 | Pass | Pass, note | Pass | n/a | Pass | Pass | n/a | n/a |
| #338 | 2026-11-14 | #70 | Pass | Pass, note | Pass | n/a | Pass | Pass | n/a | n/a |
| #337 | 2026-11-14 | #71 | Pass | Pass, note | Pass | n/a | Pass | Pass | n/a | n/a |

How to read the columns:

- **PQ2:** every merge commit has two parents, and every one carries the note "Merged by Claude Code on the owner's instruction". So all 15 merges in the sample were Claude's, made on instruction, and none was the owner's own.
- **PQ3:** no check run on any of the 15 ended in a conclusion other than success, skipped or neutral.
- **PQ4:** the criterion applies from #371 on. Of the 14 earlier pull requests, 13 carry COMMENTED reviews posted through the owner's account, which are the automated review comments ETB-SUP1-002 found (AUD-v0.03-110). Nine of them mention C1 somewhere, but none uses the §6.5 form. #361, the back-merge, has no review.
- **PQ5:** each issue named in a title is closed, on the day of the merge or the day after.
- **PQ6:** `scripts/doc_versions.py check` passes on `develop` at `83443f7`, the merge of #381. It fails on any document whose history is not numbered in order. The diffs were not read to confirm that every changed document gained a row.
- **PQ7:** the criterion applies from #375 on.
- **PQ8:** the criterion applies from #374 on. The configuration audit of `v0.03.0000` was made afterwards and is in ETB-SUP8-002 §4.

### 4.2 Non-conformances

None open against the criteria in force when each pull request merged.

Three observations are recorded, but no issue is raised for them:

1. **QA review before #371.** Reviews before #371 were not in a fixed form. That
   is the gap AUD-v0.03-110 recorded. #371 closed it from #381 on.
2. **Merges.** All 15 merges in the sample were made by Claude on instruction.
   That is allowed (ETB-SUP8-001 §5.7), but it means the merge record names the
   owner's instruction, not the owner's own act. The re-audit (#380) should
   sample the owner's own merges too, if there are any.
3. **PQ6 method.** PQ6 was checked with the versioning check, not by reading
   each diff. A change that adds no row passes the check. The next audit reads
   the diffs.

### 4.3 QA Summary: `v0.03.0000`

The QA summary for the release, which is the summary ETB-ANA-001 used to stand
in for (SUP.1.BP5).

| Objective (ETB-SUP1-001 §4) | Target | Result | Evidence |
|---|---|---|---|
| ETB-QA-001 The suite passes | Every change | Pass: 4 555 passed, 2 skipped | CI on `4b71a51`, run 44057132180 (ETB-SUP1-002 SWE.4.BP3) |
| ETB-QA-002 Statement coverage | ≥ 90 % | 95.3 % | As above |
| ETB-QA-003 Documents and code agree | Every change | Pass | `tests/test_traceability.py` in the same run |
| ETB-QA-004 Every requirement verified | No requirement without a test | Pass for the software requirements; system requirements not qualified on hardware for this release (#363) | `tests/test_traceability.py`; ETB-SUP1-002 SYS.5 |
| ETB-QA-005 Firmware builds | Every push | Pass | `firmware.yml` run 44057131868 |
| ETB-QA-006 C conforms to the standard | Every push | Pass, against a baseline of 107 known violations | `style.yml`; ETB-SVD-001 §5.5. Closing the baseline is #379 |
| ETB-QA-007 Nothing unconfirmed presented as confirmed | No exceptions | Not met in full: stale figures and statements in ETB-SWE4-002, ETB-SWE5-001, ETB-SWE6-001, ETB-SYS4-001 and ETB-SYS5-002 | ETB-SUP1-002 §8; #362, #363, #369, #370 |
| ETB-QA-008 Suite and lint where they block a merge | Every push | Pass; pylint against a baseline of 436 | `tests.yml`, `lint.yml`; #379 |

**Open non-conformances carried forward.** Each is tracked to closure on its issue:

- the MISRA checker and the dongle `-std` and `-Wextra` flags, ETB-ANA-001 §6.3 and §6.4 (#379);
- the pylint and CStyleCheck baselines (#379);
- every finding of ETB-SUP1-002 not yet closed (#362 to #379, under #380).

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
