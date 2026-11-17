<img src="../../assets/brand/svg/logos/embeddedtestbench-logo-compact.svg" alt="Embedded Test Bench" width="240">

# Deviation Record — System Integration and Qualification on Hardware

*Automotive SPICE® PAM v4.0 | SYS.4.BP3, SYS.4.BP5, SYS.5.BP3, SYS.5.BP5*

---

## 1. Document Identification & Control

| Field | Value | Field | Value |
|---|---|---|---|
| **Document ID** | ETB-DEV-004 | **Version** | [latest, §2](#2-revision-history) |
| **Project** | Embedded Test Bench | **Date** | [latest, §2](#2-revision-history) |
| **Status** | [by location, ETB-SUP1-001 §6.3](EmbeddedTestBench_SUP1_Quality_Assurance_Plan.md#63-document-status) | **Classification** | Internal |
| **Author** | Claude | **Reviewer** | Dermot Murphy |
| **Approver** | Dermot Murphy | **Related Process** | SYS.4, SYS.5 |

> Reviewer and Approver are the same person; see ETB-DEV-002.

---

## 2. Revision History

| Version | Date | Author | Description of Change |
|---|---|---|---|
| 0.1 | 2026-11-17 | Claude | #362: initial. The SYS.4 integration cases and the SYS.5 qualification of all system requirements on hardware are deferred to `v0.05.0000`, on the owner's decision of 2026-11-17. |

---

## 3. Deviation Summary

| Field | Value |
|---|---|
| **Deviation ID** | ETB-DEV-004 |
| **Severity** | SEV-2 Major, because a system requirement may be released without a hardware result |
| **Standard Clause** | ASPICE PAM v4.0: SYS.4.BP3 (integrate and perform integration verification), SYS.4.BP5 (summarise and communicate results), SYS.5.BP3 (perform verification of the integrated system), SYS.5.BP5 (summarise and communicate results) |
| **Affected Work Products** | ETB-SYS4-001, ETB-SYS5-001, ETB-SYS5-002 |
| **Disposition** | **Accepted, time-limited**: until the release `v0.05.0000`, planned for 2027-01-19 (ETB-MAN3-001 §7.1) |
| **Decided by** | The owner, 2026-11-17, recorded on #380 |

---

## 4. Non-Conformance Description

For the release after `v0.03.0000` (`v0.04.0000`):

- **SYS.4:** the integration cases of ETB-SYS4-001 §5 (ETB-SIT-01 to -24) are
  specified, traced and resourced, but none is performed as an integration
  case.
- **SYS.5:** the qualification scenarios of ETB-SYS5-001 cover every system
  requirement (#363), but they are not rerun on hardware against the current
  67 requirements. The hardware campaign of record stays the one of
  2026-10-04 (ETB-SYS5-002), which assessed 64 requirements.

What is done instead is the documentation that lets the hardware execution be
done and recorded properly: cases, traces, resources, selection rules, and a
report per release that states plainly what was not performed.

---

## 5. Justification

**The documents were the larger gap.** The audit (ETB-SUP1-002) found the
cases incomplete, untraced and unplanned. Running them on the bench before
that is fixed would have produced results that trace to nothing.

**Much of the behaviour has hardware evidence already.** The qualification
campaign of 2026-10-04 and the bench runs since then exercised 17 of the 24
integration cases' interfaces (ETB-SYS4-001 §5, last column), and qualified or
partly qualified most system requirements (ETB-SYS5-002 §7). That evidence is
not a substitute for the cases. It is why deferring them does not leave the
bench unverified.

**The deferral is bounded.** It ends at `v0.05.0000`, which has the hardware
execution as its whole content (ETB-MAN3-001 §7.1, milestone 2). Bench time is
estimated in ETB-MAN3-001 §8.1.

---

## 6. Compensating Measures

1. Every report of a release under this deviation states which cases and
   requirements have no hardware result for that release (ETB-SYS4-001 §8,
   ETB-SYS5-002).
2. A result of the bench used as evidence is cited with its date and run, never
   presented as an integration or qualification case performed.
3. The simulated qualification (ETB-SWE6-001) and the unit verification
   (ETB-SWE4-002) run on every change.
4. ETB-RISK-001 stays open, and is reviewed at each release (ETB-MAN5-001 §7).

---

## 7. Corrective Action and Closure

This deviation is closed when, for one release:

1. every case in ETB-SYS4-001 §5 that its instruments allow has been performed
   on the bench, with an execution record;
2. every system requirement has been qualified on hardware for that release,
   with its records in this repository;
3. both are summarised in that release's reports.

If `v0.05.0000` slips, this deviation is reviewed at the release review
(ETB-MAN3-001 §10.2), and either extended with a new date or the gap raised as
a problem.

---

## 8. Approval

Review and approval of this document are not entered in this table. They are
given by the merge of the pull request that last changed the document, and that
merge is the record (ETB-SUP8-001 §5.7). The evidence is the pull request, its
CI result and its merge record: who merged it, when, and the merge commit. The
last row of the revision history names the issue, and the issue links the pull
request.

| Role | Name | Recorded by |
|---|---|---|
| Raised by | Claude | The commits in the pull request |
| Quality Assurance | PR Review session | Its QA review on the pull request |
| Approver | Dermot Murphy | The merge of the pull request that last changed this document |

---

## 9. Referenced Documents

| Document ID | Title | Version |
|---|---|---|
| ETB-SYS4-001 | Embedded Test Bench System Integration & Integration Test | 0.6 |
| ETB-SYS5-001 | Embedded Test Bench System Qualification Test | 0.7 |
| ETB-SYS5-002 | Embedded Test Bench System Qualification Test Report | 1.4 |
| ETB-MAN3-001 | Embedded Test Bench Project Management Plan | 0.5 |
