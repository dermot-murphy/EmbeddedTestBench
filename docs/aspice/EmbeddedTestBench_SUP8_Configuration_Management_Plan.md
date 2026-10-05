<img src="../../assets/brand/svg/logos/embeddedtestbench-logo-compact.svg" alt="Embedded Test Bench" width="240">

# Configuration Management Plan

*Automotive SPICE® PAM v4.0 | SUP.8 — Configuration Management*

---

## 1. Document Identification & Control

| Field | Value | Field | Value |
|---|---|---|---|
| **Document ID** | ETB-SUP8-001 | **Version** | 0.11 |
| **Project** | Embedded Test Bench | **Date** | 2026-10-05 |
| **Status** | Draft | **Classification** | Internal |
| **Author** | Claude | **Reviewer** | Dermot Murphy |
| **Approver** | Dermot Murphy | **Related Process** | SUP.8 |

> Reviewer and Approver are the same person; see ETB-DEV-002.

---

## 2. Revision History

| Version | Date | Author | Description of Change |
|---|---|---|---|
| 0.1 | 2026-09-19 | Claude | Initial |
| 0.2 | 2026-09-20 | Claude | Section 5 rewritten: `develop` recorded as the integration branch, stacked pull request procedure and the 2026-09-20 retargeting observation added, section 9 corrected to match |
| 0.3 | 2026-09-30 | Claude | §5.1: a pull request targets `develop`; any other base only on explicit instruction for that pull request. §5.2: a stack is built only on instruction. Changed together with `CLAUDE.md` (#113). |
| 0.4 | 2026-10-04 | Claude | #170: §5 repository identifier updated - the repository was renamed from `dermot-murphy/TestTools` to `dermot-murphy/EmbeddedTestBench`. The procedure is unchanged, and `CLAUDE.md` names no repository, so it needed no matching change. |
| 0.5 | 2026-10-04 | Claude | #183: product renamed to Embedded Test Bench - document file name prefix `EmbeddedTestBench_`, identifier prefix `ETB-` (was `TB-`), product name in prose. Earlier revision rows keep the names in use when they were written. |
| 0.6 | 2026-10-04 | Claude | #187: §6.2 added - a revision history lists entries oldest first, a new entry is appended as the last row, and earlier rows are not edited. |
| 0.7 | 2026-10-05 | Claude | #185: §5.5 added - the repository settings baseline (ruleset, merge, security, actions), with the enforcement observed on 2026-10-05. Changed together with CLAUDE.md. |
| 0.8 | 2026-10-05 | Claude | #190: gitflow adopted. §5.1 adds `release/` and `hotfix/` branches, and their pull requests into `main` and the back-merge into `develop` are allowed by procedure; §5.6 added - release and hotfix procedure, tag on the merge commit in `main`. Changed together with CLAUDE.md. |
| 0.9 | 2026-10-05 | Claude | #188: §6 states the version and tag format (`0.01.0000`, tag `v0.01.0000`) and the PEP 440 normalisation of the packaged version; §5.5 adds the tag ruleset protecting `v*` tags. Changed together with CLAUDE.md. |
| 0.10 | 2026-10-05 | Claude | #184: §5.7 added - the GitHub wiki and the `gh-pages` home page are generated outputs, published from `main` by workflow and never edited by hand; §4 lists them as configuration items; §5.5 adds the Pages source, the repository homepage and the `WIKI_TOKEN` secret. Changed together with CLAUDE.md. |
| 0.11 | 2026-10-05 | Claude | #194: §6.3 records where the brand logo appears - above the title of every controlled document in `docs/aspice/` and `docs/templates/`, in the documents themselves - and that the wiki and home page take it from their generators. The compact logo added above this document's title. |

---

## 3. Purpose & Scope

### 3.1 Purpose

This plan says what is under configuration control, how items are identified and
versioned, how baselines are made, and how the state of any Embedded Test Bench result can
be reconstructed later.

The requirement that drives all of it: **a report produced by Embedded Test Bench must be
reproducible from what the report itself records.** That is only true if every
input to the run is an identified configuration item.

### 3.2 Referenced Documents

| Document ID | Title | Version |
|---|---|---|
| ETB-MAN3-001 | Embedded Test Bench Project Management Plan | 0.1 |
| ETB-SUP1-001 | Embedded Test Bench Quality Assurance Plan | 0.1 |
| ETB-SUP10-001 | Embedded Test Bench Change Request Management Plan | 0.1 |
| ETB-ACQ4-001 | Embedded Test Bench Supplier Monitoring Plan | 0.1 |
| ETB-SVD-001 | Embedded Test Bench Software Version Description | 0.1 |

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
| Generated outputs | GitHub wiki; `gh-pages` branch (home page) | Wiki page name; file path | Regenerated from `main` by `wiki_publish.yml` and `pages_publish.yml`; never edited by hand (§5.7) |
| C rule configuration | `.cstylecheck.yml`, `.cstylecheck-baseline.json` | Filename | git — the baseline changes only with a recorded reason |
| Python rule configuration | `[tool.pylint]` in `pyproject.toml`, `.pylint-baseline.json` | Filename | git — as above |
| Build tools | Python, `nrfutil`, GNU Arm toolchain, nRF5 SDK | Name + exact version | Pinned in the workflow; recorded in ETB-SVD-001 |
| External actions | `dermot-murphy/CStyleCheck@v1.5.1` | Repository + tag | Pinned in the workflow |
| Bench instruments | Scope, supply, J-Link, dongle | Model + serial + firmware revision | Queried at run time and written into every report |

### 4.1 Instruments Are Configuration Items

An instrument's firmware revision changes what its commands mean. Embedded Test Bench
therefore queries each instrument's identity at connection and records it in the
report, so that a result can be attributed to the instrument that produced it
rather than to the model name (ETB-RISK-002).

---

## 5. Repository and Branching

### 5.1 Branches

| Branch | Purpose |
|---|---|
| `main` | Released state. Changes arrive only from `release/` and `hotfix/` branches (§5.6), and each merge is tagged. Nothing is committed here directly. |
| `develop` | Integration branch. Every other change merges here first. |
| `feature/<topic>`, `docs/<topic>`, `fix/<topic>` | One branch per ticket, branched from `develop`. |
| `release/v<version>` | Branched from `develop` to prepare a release; merged into `main`, then back into `develop` (§5.6). |
| `hotfix/v<version>` | Branched from `main` for an urgent fix to a release; merged into `main`, then back into `develop` (§5.6). |

The branching model is gitflow (#190).

| Item | Convention |
|---|---|
| Repository | `dermot-murphy/EmbeddedTestBench` |
| Direct pushes to `main` or `develop` | Not made; changes arrive through pull requests |
| Ticket | Every change starts from an issue, referenced in the commit message |
| History | Never rewritten on a branch someone else may have checked out |

**A pull request targets `develop`.** Gitflow defines two exceptions that need
no further instruction: a pull request from a `release/` or `hotfix/` branch
targets `main`, and the back-merge after a release or hotfix has head `main` and
base `develop` (§5.6). Any other base — `main`, a predecessor's
branch in a stack, or any other branch — is used only when the repository owner
explicitly instructs it for that pull request, and the pull request's
description says so. Being asked to open a pull request is not an instruction
about its base. Example of an instructed exception: #110, which reverts #106 on
`main` because that is where #106 landed (#109). #106 itself, merged into `main`
without passing through `develop`, is the failure this rule prevents (#113).

A pull request is merged only when CI is green. A red build is fixed or the
change is withdrawn; it is not merged with a note to fix it afterwards. Where no
workflow applies to a change, that is stated explicitly rather than implied by
the absence of a failure.

### 5.2 Stacked Pull Requests

A stack is built **only on explicit instruction** (§5.1), because each pull
request in it is based on its predecessor's branch rather than on `develop`.

When so instructed and one body of work splits into several tickets that build
on each other, each branch is based on its predecessor, so that each pull request's diff shows only
its own work and review stays honest.

A stack is merged in dependency order, and each pull request is **retargeted to
`develop` before it is merged**. This is not a precaution. A pull request based
on its predecessor's branch merges *into that branch*, not into `develop`.

A branch is deleted only after confirming that no open pull request is based on
it. Deleting a base branch closes the pull requests that target it.

A stacked chain is merged with merge commits, not squashed. Each branch contains
its predecessors' commits; squashing replaces them with a commit that is not an
ancestor of the next branch, and every later merge in the chain is made harder
for it.

### 5.3 Recorded Observation: Retargeting

**2026-09-20, this repository.** PR #3 merged into `develop` at 16:15:31 and its
head branch was deleted. PR #5, whose base was that branch, was **closed** at
16:15:37 — not retargeted to `develop`.

Recovery required restoring the deleted branch at its original commit, because a
pull request whose base branch has been deleted cannot be reopened, and a closed
pull request's base branch cannot be changed. The order that works is: restore
the branch, reopen the pull request, change its base, then delete the restored
branch.

This is recorded as an observation of this repository on that date, not as a
general statement about how GitHub behaves under every configuration. The
distinction matters: treating the unverified general case as fact is what caused
the failure it describes (ETB-RISK-004).

### 5.4 Relationship to CLAUDE.md

`CLAUDE.md` at the repository root carries the same procedure in working form,
for contributors and for Claude Code. It and this section are one configuration
item in two places and are changed together; neither is updated alone.


### 5.5 Repository Settings Baseline

The settings below are part of this configuration item. They were applied and
read back through the GitHub API on 2026-10-05 (#185), and are re-checked
against the API rather than assumed (ETB-RISK-004).

| Area | Setting | Value |
|---|---|---|
| Ruleset | Name, enforcement, bypass | "Protect main and develop", active, no bypass actors |
| Ruleset | Target branches | `refs/heads/main`, `refs/heads/develop` (two patterns) |
| Ruleset | Deletion, force push | Both blocked |
| Ruleset | Pull request | Required; 0 approvals (single maintainer, who cannot approve their own pull request); merge method **merge** only |
| Ruleset | Required status checks | `pytest (3.8)`, `pytest (3.9)`, `pytest (3.12)`, `pylint`, `Embedded C standard`, `Simulated bench`; branch need not be up to date |
| Ruleset | Linear history | Not required: it would block the merge commits §5.2 requires |
| Tag ruleset | "Protect release tags" | Active, no bypass actors, on `refs/tags/v*`: deletion and update blocked, so a published release tag cannot be moved (#188) |
| Merge | Merge commits / squash / rebase | On / off / off |
| Merge | Automatically delete head branches | On (see below) |
| Merge | Auto-merge | Off: a pull request is merged on instruction |
| Security | Secret scanning, push protection | On |
| Security | Dependabot alerts, security updates | On |
| Actions | Allowed actions | GitHub-owned, plus `carlosperate/arm-none-eabi-gcc-action@*` and `dermot-murphy/*` |
| Actions | Default `GITHUB_TOKEN` permission | Read; Actions may not approve pull requests |
| Repository | Description, topics | Set; Discussions off; Wiki on (#184) |
| Repository | Homepage | `https://dermot-murphy.github.io/EmbeddedTestBench/` (#184) |
| Pages | Source, build | Branch `gh-pages`, path `/`, legacy (branch) build; HTTPS enforced (#184) |
| Actions | Repository secrets | `WIKI_TOKEN`: a personal access token of the owner's account, used only by `wiki_publish.yml` to push the wiki (#184) |

The required checks are the jobs that run on every push and pull request. The
firmware workflow's jobs are path-filtered and are therefore not required: a
pull request that does not touch firmware would wait for them indefinitely.

**Enforcement observed, 2026-10-05.** With the ruleset temporarily extended to
a probe branch, a direct push, a force push and a deletion were each rejected
(`GH013`: "Changes must be made through a pull request", "Cannot force-push to
this branch", "Cannot delete this branch"). The ruleset was then restored to
`main` and `develop` and the probe branch deleted.

**Automatic head-branch deletion.** Merging a pull request deletes its branch.
That is safe only because §5.2 already requires a stacked pull request to be
retargeted to `develop` before its predecessor merges. Whether automatic
deletion closes dependent pull requests the way the manual deletion in §5.3 did
has not been verified, so the procedure assumes it does.

**Dependabot.** Whether `target-branch` in `dependabot.yml` redirects security
updates has not been verified. Until it is, a Dependabot pull request is assumed
to open against `main` and is retargeted to `develop` before it is merged (§5.1).

**Pages, observed 2026-10-05 (#184).** Pushing the new `gh-pages` branch enabled
GitHub Pages by itself: a read of the Pages API straight after the push already
showed source `gh-pages`, path `/`, legacy build, and the explicit request to
enable it was refused as already done (HTTP 409). The site was built from the
pushed commit and answered HTTP 200.


### 5.6 Releases and Hotfixes

A release is made only on the repository owner's instruction.

| Step | Release | Hotfix |
|---|---|---|
| 1. Branch | `release/v<version>` from `develop` | `hotfix/v<version>` from `main` |
| 2. Content | Version bump, ETB-SVD-001 and other release documents, and fixes only; no new features | The fix only, with its version bump and SVD update |
| 3. Merge | Pull request into `main`, merge commit, CI green | Same |
| 4. Tag | Annotated tag `v<version>` on the merge commit in `main` | Same |
| 5. Back-merge | Pull request from `main` into `develop`, merge commit | Same |
| 6. Clean up | Release branch deleted once steps 3 and 5 are done | Hotfix branch deleted likewise |

The version is semantic and the tag always has a lowercase `v` (#188). The tag
together with the SVD is the release baseline (§7).

The back-merge keeps `develop` a descendant of every release, so the two
branches do not diverge. Before gitflow, `main` gained commits that `develop`
lacked: #106, its revert (#109, #110), and the merge commits of #169 and #189.

Head branches are deleted automatically on merge (§5.5). That is intended for
`release/` and `hotfix/` branches. When the head is `main` (the back-merge) or
`develop`, the ruleset blocks the deletion. This is checked after each such merge
rather than assumed.

### 5.7 Generated Outputs: Wiki and Home Page

The GitHub wiki and the `gh-pages` branch are generated outputs of the
repository (#184). Neither is edited by hand, and neither is pushed to from a
working session: a hand edit is overwritten by the next run, and an unreleased
change published there would describe something that is not in `main`.

| Output | Generated by | Published by | Trigger | Authentication |
|---|---|---|---|---|
| Wiki: `Home`, one page per user guide and instrument note in `docs/`, one `ASPICE-<name>` page per ASPICE document, `ASPICE-Index`, `_Sidebar` | `scripts/publish_docs.py wiki` | `.github/workflows/wiki_publish.yml` | Push to `main` touching `README.md`, `docs/**`, the generator or the workflow; `workflow_dispatch` | `WIKI_TOKEN` (§5.5); the default `GITHUB_TOKEN` cannot push to a wiki |
| Home page: `README.md`, `_config.yml` and the logo on `gh-pages`, served by GitHub Pages | `scripts/publish_docs.py home` | `.github/workflows/pages_publish.yml` | Push to `main` touching `README.md`, the brand assets, the generator or the workflow; `workflow_dispatch` | `GITHUB_TOKEN` with `contents: write` for that job |

Both are published from `main` because under gitflow `main` is the released
state (§5.1): the wiki describes the latest release, not work in progress on
`develop`. Links from a published page to a repository file point at that file
on `main`. A run pushes only when the generated content differs from what is
published, and the generated content carries no timestamp, so a run over
unchanged documents pushes nothing. Each workflow has a `dry_run` input that
generates and reports the change without pushing.

The wiki generator removes the existing pages before writing, so a renamed or
deleted document leaves no stale page. Qualification run records under
`docs/aspice/qualification/` are not given pages; a link to one points at the
file in the repository. The generator is verified by
`tests/test_publish_docs.py` (SWE4-UT-PUBLISH).

The ASPICE pages were first published by hand on 2026-10-05 from `develop`
(393d310), before these workflows existed; the generator keeps those page
names, so its first run replaces those pages rather than duplicating them.

---

## 6. Versioning

| Item | Scheme |
|---|---|
| Documents | `major.minor`, starting at 0.1; 0.x while Draft, 1.0 at first approval |
| Python package and releases | Semantic versioning, written `MAJOR.MINOR.PATCH` as `0.01.0000`, in `pyproject.toml` and `benchtools/__init__.py`. A release is tagged `v<version>` with a lowercase `v`, e.g. `v0.01.0000`. Python packaging normalises the version under PEP 440, so the wheel's metadata reads `0.1.0` for `0.01.0000`; the tag and `__version__` keep the project's form (ETB-SVD-001 §5.1) |
| Firmware | `major.minor.patch`, reported by the `rd version` command and recorded in the firmware manifest |
| Baselines | Annotated git tags |

### 6.1 Firmware Manifests

Every firmware image carries a `firmware_manifest.json` beside it giving its
version and build date. The runner compares the version a device reports with
the manifest for the image that was flashed, so an image that is not what the
report says it is fails the run rather than passing quietly (ETB-RISK-009).

---

### 6.2 Revision History Order

Every revision history, and every other change-history table in a document,
lists its entries **oldest first**. A new entry is appended as the last row, so
the most recent change is at the bottom of the table and the version in the
last row is the version in the identification block. Earlier rows are not
edited: they record what was true when they were written.

The order is checked by `tests/test_traceability.py` (SWE4-UT-TRACE), which
fails if a history table's version column decreases from one row to the next.

### 6.3 Brand Logo in Controlled Documents

Every controlled document in `docs/aspice/` and `docs/templates/` starts with
the compact brand logo, above its title, as the same line in each:

```html
<img src="../../assets/brand/svg/logos/embeddedtestbench-logo-compact.svg" alt="Embedded Test Bench" width="240">
```

- **In the documents themselves**, not only in their rendered copies, so the
  document read on GitHub, in a clone or in a review is the document that is
  controlled. The line sits above the title and outside the identification
  block, which still carries the Document ID and version.
- **The SVG master, by relative path.** GitHub renders an SVG from the
  repository in a Markdown image, and a relative path resolves at any branch or
  tag and in a local clone. A rendered copy that cannot show SVG uses the PNG
  render of the same logo, `assets/brand/png/logos/logo_compact.png`.
- **The wiki and the home page take the logo and banners from their
  generators**, not from hand edits (#194, #184).
- **A baseline is not re-issued for the logo.** ETB-SVD-001 describes the tagged
  baseline `v0.01.0000` and is not edited for it (§7); it takes the logo at its
  next revision.
- **The templates carry the line**, so a document started from one in
  `docs/templates/` has it from the first draft.

The logo's wordmark is dark on a transparent background, so it has low contrast
on a dark GitHub theme. There is no compact logo for dark backgrounds yet.

## 7. Baselines

A baseline is an annotated git tag plus a Software Version Description
(ETB-SVD-001) naming exactly what the baseline contains — source revision,
document versions, firmware versions, tool versions and known problems.

| Baseline | When | Contents |
|---|---|---|
| Document baseline | When this document set is approved | All `docs/aspice/` documents at their approved versions |
| Release baseline | When a version of `benchtools` or the firmware is released | Source revision, images, manifests, tool versions, ETB-SVD-001 |

A baseline is never edited. A correction produces a new baseline with a new
SVD, and the reason is recorded in the SVD's revision history.

---

## 8. Change Control

Changes to a baselined item follow ETB-SUP10-001. Changes to items not yet
baselined follow ordinary development: branch, change, test, review, merge.

Every change, baselined or not, satisfies ETB-SUP1-001 §6.1 — the documents move
with the code.

---

## 9. Status Accounting

The state of any configuration item is answered from the repository:

| Question | Answered by |
|---|---|
| What is in this release? | ETB-SVD-001 for that baseline |
| What changed since the last baseline? | `git log <previous-tag>..<tag>` |
| Which document version is current? | The Version field in the document, on `develop`; on `main` for a released baseline |
| What produced this report? | The report's own header: spec revision, bench, instrument identities, simulated or not |
| What tool versions built this firmware? | The workflow file at that revision, plus ETB-SVD-001 |

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
