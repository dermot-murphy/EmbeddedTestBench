# Change Request Management Plan

*Automotive SPICE® PAM v4.0 | SUP.10 — Change Request Management*

---

## 1. Document Identification & Control

| Field | Value | Field | Value |
|---|---|---|---|
| **Document ID** | TB-SUP10-001 | **Version** | 0.1 |
| **Project** | TestBench | **Date** | 2026-09-19 |
| **Status** | Draft | **Classification** | Internal |
| **Author** | Claude | **Reviewer** | Dermot Murphy |
| **Approver** | Dermot Murphy | **Related Process** | SUP.10 |

> Reviewer and Approver are the same person; see TB-DEV-002.

---

## 2. Revision History

| Version | Date | Author | Description of Change |
|---|---|---|---|
| 0.1 | 2026-09-19 | Claude | Initial |

---

## 3. Purpose & Scope

### 3.1 Purpose

This plan says how a change to something already agreed is proposed, judged for
impact, decided, implemented and confirmed.

### 3.2 Referenced Documents

| Document ID | Title | Version |
|---|---|---|
| TB-SUP8-001 | TestBench Configuration Management Plan | 0.1 |
| TB-SUP9-001 | TestBench Problem Resolution Management Plan | 0.1 |
| TB-SUP1-001 | TestBench Quality Assurance Plan | 0.1 |
| TB-RTM-001 | TestBench Traceability Matrix | 0.1 |

### 3.3 Scope

A change request is required for a change to:

- a requirement in TB-SYS2-001 or TB-SWE1-001;
- an architectural or design decision recorded in TB-SYS3-001, TB-SWE2-001 or
  TB-SWE3-001;
- any baselined item (TB-SUP8-001 §7);
- a public interface of `benchtools` or the firmware command set, where existing
  bench specifications would stop working;
- this document set's processes.

A change request is **not** required for ordinary development of items that are
not yet baselined, for fixing a problem within an agreed requirement
(TB-SUP9-001 handles that), or for wording and formatting.

---

## 4. Sources of Change

| Source | Typical trigger |
|---|---|
| New capability requested by the project lead | A new instrument, a new kind of bench test |
| A problem whose correct fix changes a requirement | TB-SUP9-001 §8 item 5 |
| Supplier change | A vendor alters a command set or withdraws a tool (TB-ACQ4-001) |
| Review finding | A requirement found unverifiable during review |
| Risk treatment | A mitigation in TB-MAN5-001 §6 that needs a design change |

---

## 5. Process

| Step | What happens | Who |
|---|---|---|
| 1. Raise | A change request record (§6) is created with the proposal and its reason | Anyone |
| 2. Impact analysis | The affected requirements, design elements, tests, documents and bench specifications are listed, using TB-RTM-001 to find them. Effort and risk are stated | Author |
| 3. Decide | Approved, rejected or deferred, with the reason recorded | Project lead |
| 4. Implement | On a branch; code, tests and documents change together | Author |
| 5. Verify | Suite green including the traceability check; the change's own tests fail without it | Author |
| 6. Close | Merged; the change request records the merge revision | Project lead |

### 5.1 Impact Analysis Is the Point

The step that earns this process its place is step 2. TestBench's traceability
matrix exists so that "what else does this touch" is answerable rather than
guessed: a requirement's row names the design elements and tests that depend on
it, and the traceability check will fail the build if the answer was incomplete.

---

## 6. Change Request Record

Change requests are recorded as repository issues labelled `change-request`, and
referenced from the pull request that implements them.

| Field | Content |
|---|---|
| **Change Request ID** | TB-CR-nnn |
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
analysis, updates them in the same change, and says so in TB-SVD-001 for the
release that carries it. A bench specification that silently changes meaning is
worse than one that fails to load, because the first produces a plausible wrong
answer and the second produces an error message.

---

## 8. Review & Approval

| Role | Name | Signature / Electronic Approval | Date |
|---|---|---|---|
| Author | Claude | Approved | 2026-09-19 |
| Reviewer | Dermot Murphy | — | *pending* |
| Approver | Dermot Murphy | — | *pending* |
