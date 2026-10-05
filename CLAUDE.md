# CLAUDE.md

Guidance for Claude Code working in this repository.

This file covers the branching and pull request procedure. It exists because that
procedure was assumed rather than written down, and the assumption was wrong — see
[Never assume GitHub retargets a pull request](#never-assume-github-retargets-a-pull-request).

## Branching model

The repository uses **gitflow** (#190).

| Branch | Purpose |
| --- | --- |
| `main` | Released state. Changes arrive only from `release/` and `hotfix/` branches, and each merge is tagged. Nothing is committed here directly. |
| `develop` | Integration branch. All other work merges here first. |
| `feature/<topic>` | One branch per ticket, branched from `develop`. |
| `docs/<topic>`, `fix/<topic>` | Same rule, different kind of work. |
| `release/v<version>` | Branched from `develop` to prepare a release; merged into `main`, then back into `develop`. |
| `hotfix/v<version>` | Branched from `main` for an urgent fix to a release; merged into `main`, then back into `develop`. |

Never commit directly to `main` or `develop`. Never push to a branch you were not
asked to work on.

## Every change starts with a ticket

1. Open the issue, describing the problem before the fix.
2. Branch from `develop`.
3. Commit, with the issue number in the message.
4. Push with `git push -u origin <branch-name>`.
5. Open the pull request **only if asked**, based on `develop`. See
   [A pull request targets `develop`](#a-pull-request-targets-develop).
6. Update the ticket with what was done.
7. Close the ticket once CI is green — or, if no workflow applies to the change,
   say so explicitly rather than implying checks passed.

## A pull request targets `develop`

**Never open a pull request into any branch other than `develop` unless
explicitly told to** — for that pull request, by the repository owner. This
covers `main`, a predecessor's branch in a stack, and any other branch alike.
Being asked to open a pull request is not an instruction about its base; the
base is `develop`.

**Gitflow's own exceptions** need no further instruction, because the procedure
defines them (see [Releases and hotfixes](#releases-and-hotfixes)):

- a pull request from `release/v<version>` or `hotfix/v<version>` targets `main`;
- the back-merge pull request after a release or hotfix has head `main` and base
  `develop`.

Any other instructed exception is stated in the pull request's description, so a
reviewer can see why it does not target `develop`. Example: #110 reverts #106
on `main`, on explicit instruction, because `main` is where #106 landed (#109).

Background: #106 was merged into `main` although work merges to `develop` first,
and had to be reverted (#109, #110). This rule was added by #113.

## Releases and hotfixes

A release is made only when the repository owner says so.

1. Branch `release/v<version>` from `develop`. The version is semantic,
   written `0.01.0000`, and the tag always has a lowercase `v` (#188).
2. On that branch: the version bump, the Software Version Description
   (ETB-SVD-001) and other release documents, and fixes only. No new features.
3. Open a pull request into `main`. Merge it with a merge commit once CI is green.
4. Create the annotated tag `v<version>` on that merge commit in `main`.
5. Open a pull request from `main` into `develop` (the back-merge) and merge it,
   so `develop` contains the release commits and the tagged history.
6. Delete the release branch once both merges are done.

A hotfix is the same, except that it is branched from `main` as
`hotfix/v<version>` and carries only the fix.

Merging a pull request deletes its head branch automatically (`ETB-SUP8-001 §5.5`).
That is wanted for `release/` and `hotfix/` branches. When the head is `main`
(the back-merge) or `develop`, the ruleset blocks the deletion, so both survive.
Check that they do after the merge rather than assuming it.

## Stacked pull requests

A stack is built **only when explicitly told to**, because each pull request in
it is based on its predecessor's branch rather than on `develop` (see above).
Without that instruction, each ticket's branch is taken from `develop` and its
pull request targets `develop`.

When one body of work splits into several tickets that build on each other, each
branch is based on its predecessor so that each pull request's diff shows only its
own work. This keeps review honest, and it carries one trap that has already cost
this repository a broken merge.

### Never assume GitHub retargets a pull request

**Observed 2026-09-20, in this repository.** PR #3 merged into `develop` at
16:15:31 and its head branch `feature/aspice-migrate-work-products` was deleted.
PR #5, whose base was that branch, was **closed** at 16:15:37 — six seconds later.
It was not retargeted to `develop`.

Do not reason about this from memory or from documentation describing a different
configuration. Before and after every merge or branch deletion, read the base back
through the API and confirm it is what you expect.

### The procedure that follows from it

1. **Set the base explicitly when the pull request is created.** Never rely on the
   default and never rely on it being corrected later.
2. **Retarget each stacked pull request to `develop` yourself before merging it.**
   This is not a safety net; it is required. A pull request based on its
   predecessor's branch merges *into that branch*, not into `develop`.
3. **Merge in dependency order**, lowest number first.
4. **Delete a branch only after confirming no open pull request is based on it.**
   List the open pull requests and check their bases. Deleting a base branch closes
   the pull requests that point at it.
5. **Use a merge commit, not a squash.** Each branch in a stack contains its
   predecessors' commits. Squashing replaces them with a new commit that is not an
   ancestor of the next branch, and every later merge in the chain gets messier for
   it.

### Recovering a pull request closed by a deleted base branch

Two GitHub restrictions compose badly here:

- a pull request whose base branch has been deleted **cannot be reopened**;
- a **closed** pull request's base branch **cannot be changed**.

So neither half of the obvious fix works on its own. The order that does work:

```sh
# 1. Restore the deleted branch at its original commit.
git push origin <original-sha>:refs/heads/<deleted-branch>

# 2. Reopen the pull request — now possible, its base exists again.
# 3. Change its base to develop.
# 4. Delete the restored branch. Nothing targets it now, so this is harmless.
```

Steps 2 and 3 must be separate calls. A single call that both reopens and
retargets is rejected, because the base change is validated while the pull request
is still closed.

The original commit SHA is recoverable from the merged pull request's head, from
the local clone, or from the repository's events — check before deleting a branch,
not after.

## Repository settings

The repository's GitHub settings enforce part of this procedure, and are
recorded in `ETB-SUP8-001 §5.5`:

- `main` and `develop` reject direct pushes, force pushes and deletion. A
  change reaches them only through a pull request whose required checks pass:
  `pytest (3.8)`, `pytest (3.9)`, `pytest (3.12)`, `pylint`,
  `Embedded C standard` and `Simulated bench`.
- Merge commits are the only merge method. Squash and rebase are switched off.
- **Merging a pull request deletes its head branch automatically.** In a stack,
  retarget the next pull request to `develop` *before* merging its predecessor,
  as step 2 above already requires, or the deletion may close it.
- A Dependabot pull request may open against `main`. Retarget it to `develop`
  before merging.

Read the settings back through the API before relying on them. If a setting is
changed, change `ETB-SUP8-001 §5.5` with it.

## Verify, don't assert

The retarget trap above is one instance of a general failure this project has
recorded as **ETB-RISK-004**: stating how a tool behaves from memory instead of
checking it.

State platform behaviour only after verifying it in the current session, against
the API or the live configuration. If something cannot be verified, say that it is
unverified. A confident wrong answer about tooling costs more than an admitted gap,
because it gets acted on.

## Related

- `ETB-SUP8-001 §5` — Configuration Management Plan. Carries this procedure in
  ASPICE form, including the 2026-09-20 retargeting observation. That section and
  this file are one configuration item in two places: change them together,
  never one alone.
- `ETB-RISK-004` — the risk this file's last section mitigates.
