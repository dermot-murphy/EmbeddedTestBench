<img src="../../assets/brand/svg/logos/embeddedtestbench-logo-compact.svg" alt="Embedded Test Bench" width="240">

# Change Request Management Plan

*Automotive SPICE® PAM v4.0 | SUP.10 — Change Request Management*

---

## 1. Document Identification & Control

| Field | Value | Field | Value |
|---|---|---|---|
| **Document ID** | ETB-SUP10-001 | **Version** | [latest, §2](#2-revision-history) |
| **Project** | Embedded Test Bench | **Date** | [latest, §2](#2-revision-history) |
| **Status** | Draft | **Classification** | Internal |
| **Author** | Claude | **Reviewer** | Dermot Murphy |
| **Approver** | Dermot Murphy | **Related Process** | SUP.10 |

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
| next | 2026-11-17 | Claude | #375: the plan follows the practice. §5 says where each step is recorded on the issue, and that approval is on the issue before work starts. §5 step 3 - one instruction covering several issues is quoted once on their umbrella issue. §6 - the ID is the issue number, the `change-request` label exists, and the issue headings map to the record's fields. |

---

## 3. Purpose & Scope

### 3.1 Purpose

This plan says how a change to something already agreed is proposed, judged for
impact, decided, implemented and confirmed.

### 3.2 Referenced Documents

| Document ID | Title | Version |
|---|---|---|
| ETB-SUP8-001 | Embedded Test Bench Configuration Management Plan | 0.1 |
| ETB-SUP9-001 | Embedded Test Bench Problem Resolution Management Plan | 0.1 |
| ETB-SUP1-001 | Embedded Test Bench Quality Assurance Plan | 0.1 |
| ETB-RTM-001 | Embedded Test Bench Traceability Matrix | 0.1 |

### 3.3 Scope

A change request is required for a change to:

- a requirement in ETB-SYS2-001 or ETB-SWE1-001;
- an architectural or design decision recorded in ETB-SYS3-001, ETB-SWE2-001 or
  ETB-SWE3-001;
- any baselined item (ETB-SUP8-001 §7);
- a public interface of `benchtools` or the firmware command set, where existing
  bench specifications would stop working;
- this document set's processes.

A change request is **not** required for ordinary development of items that are
not yet baselined, for fixing a problem within an agreed requirement
(ETB-SUP9-001 handles that), or for wording and formatting.

---

## 4. Sources of Change

| Source | Typical trigger |
|---|---|
| New capability requested by the project lead | A new instrument, a new kind of bench test |
| A problem whose correct fix changes a requirement | ETB-SUP9-001 §8 item 5 |
| Supplier change | A vendor alters a command set or withdraws a tool (ETB-ACQ4-001) |
| Review finding | A requirement found unverifiable during review |
| Risk treatment | A mitigation in ETB-MAN5-001 §6 that needs a design change |

---

## 5. Process

| Step | What happens | Who | Recorded on the issue as |
|---|---|---|---|
| 1. Raise | A change request record (§6) is created with the proposal and its reason | Anyone | The issue, labelled `change-request` |
| 2. Impact analysis | The affected requirements, design elements, tests, documents and bench specifications are listed, using ETB-RTM-001 to find them. Effort and risk are stated | Author | An "Impact" section in the body, or a comment headed "Impact analysis", before work starts |
| 3. Decide | Approved, rejected or deferred, with the reason recorded | Project lead | Approved: the owner's comment on the issue, or the owner's instruction to work it, quoted on the issue with its date by the session that works it, or once on the umbrella issue when one instruction covers the issues it lists (for #362 to #379: #380, 2026-11-17). Rejected: closed as not planned with the reason. Deferred: labelled `blocked` with the reason |
| 4. Implement | On a branch; code, tests and documents change together | Author | The linked pull request |
| 5. Verify | Suite green including the traceability check; the change's own tests fail without it | Author | The pull request's CI result and its QA review (ETB-SUP1-001 §6.5) |
| 6. Close | Merged; the change request records the merge revision | Project lead | A closing comment naming the merged pull request, its merge commit and the tests that cover the change |

Step 3 comes before step 4: no branch is pushed for a change request until its
approval is on the issue. Quoting the owner's instruction records the
instruction and its date. It is not an approval written on the owner's behalf:
the instruction is the approval, as a merge instruction is for a pull request
(ETB-SUP8-001 §5.7).

### 5.1 Impact Analysis Is the Point

The step that earns this process its place is step 2. Embedded Test Bench's traceability
matrix exists so that "what else does this touch" is answerable rather than
guessed: a requirement's row names the design elements and tests that depend on
it, and the traceability check will fail the build if the answer was incomplete.

---

## 6. Change Request Record

Change requests are recorded as repository issues labelled `change-request`, and
referenced from the pull request that implements them. The ID is the issue
number, `#n`; there is no separate ETB-CR-nnn number. Traceability runs through
it: the revision history row of each document the change touches names the
issue, the commits and pull request name it, and the issue names the affected
IDs. Most issues use the headings Problem, Fix and Acceptance; Problem holds the
Description and Reason, Fix the proposal, and the fields below that those
headings do not hold are added as their own sections.

| Field | Content |
|---|---|
| **Change Request ID** | The issue number, `#n` |
| **Raised by / date** | |
| **Title** | One line |
| **Type** | New capability / Requirement change / Design change / Process change / Supplier-driven |
| **Description** | What is proposed |
| **Reason** | Why, including what goes wrong if nothing changes |
| **Affected items** | Requirement IDs, design element IDs, test groups, documents, bench specifications |
| **Impact** | Effort, risk, backwards compatibility of existing bench specifications |
| **Alternatives considered** | Including doing nothing |
| **Decision / date / by** | Approved / Rejected / Deferred, with the reason |
| **Implementation** | Branch and merge revision |
| **Verification** | The tests that cover it |
| **Related** | Problem IDs, risk IDs |

---

## 7. Backwards Compatibility

A change that would stop an existing bench specification from running is
treated as a breaking change: it names the affected specifications in its impact
analysis, updates them in the same change, and says so in ETB-SVD-001 for the
release that carries it. A bench specification that silently changes meaning is
worse than one that fails to load, because the first produces a plausible wrong
answer and the second produces an error message.

---

## 8. Review & Approval

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
