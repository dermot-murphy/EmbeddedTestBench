<img src="../../assets/brand/svg/logos/embeddedtestbench-logo-compact.svg" alt="Embedded Test Bench" width="240">

# Deviation Record — Independence of Quality Assurance

*Automotive SPICE® PAM v4.0 | SUP.1.BP1, SUP.1.BP7 — Quality Assurance*

---

## 1. Document Identification & Control

| Field | Value | Field | Value |
|---|---|---|---|
| **Document ID** | ETB-DEV-003 | **Version** | [latest, §2](#2-revision-history) |
| **Project** | Embedded Test Bench | **Date** | [latest, §2](#2-revision-history) |
| **Status** | [by location, ETB-SUP1-001 §6.3](EmbeddedTestBench_SUP1_Quality_Assurance_Plan.md#63-document-status) | **Classification** | Internal |
| **Author** | Claude | **Reviewer** | Dermot Murphy |
| **Approver** | Dermot Murphy | **Related Process** | SUP.1 |

> Reviewer and Approver are the same person; see ETB-DEV-002.

---

## 2. Revision History

| Version | Date | Author | Description of Change |
|---|---|---|---|
| 0.1 | 2026-11-17 | Claude | #373: initial. QA is performed by a session separate from the authoring session, not by a party organisationally independent of the work; escalation ends at the project lead. Accepted with justification on the owner's decision of 2026-11-17. |
| next | 2026-11-17 | Claude | #373, review round 1 (PR #390): §4 states the four limits of the QA session's role. |

---

## 3. Deviation Summary

| Field | Value |
|---|---|
| **Deviation ID** | ETB-DEV-003 |
| **Severity** | SEV-3 Minor |
| **Standard Clause** | ASPICE PAM v4.0, SUP.1.BP1 Ensure independence of quality assurance; SUP.1.BP7 Escalate non-conformances |
| **Affected Work Products** | ETB-SUP1-001; the QA records it defines (the QA review on each pull request, ETB-SUP1-003) |
| **Disposition** | **Accepted with justification** (owner's decision, 2026-11-17, recorded on #380) |

---

## 4. Non-Conformance Description

**SUP.1.BP1** expects quality assurance to be performed by a party independent
of the work it assures, with the authority to raise and escalate what it finds.

In this project:

- the work products are written by Claude, in a Claude Code session working on
  the owner's instructions (ETB-DEV-001);
- the QA review on each pull request (ETB-SUP1-001 §6.5) and the process QA
  audits (ETB-SUP1-001 §6.7) are performed by the *PR Review* session, a
  separate Claude Code session that does no authoring on the work it reviews;
- the project has one human member, Dermot Murphy, who is the Reviewer, the
  Approver and the project lead (ETB-DEV-002).

The QA session's role has these limits, set by the owner:

1. it reviews only when the authoring session asks, and only what that session
   sends: the authoring session chooses when to ask and what to put in front of
   it;
2. it reviews a pull request for at most four rounds; findings still open after
   the fourth go to the owner;
3. it never approves and never merges, even when asked (the owner's rule,
   2026-11-17);
4. its reviews are posted through the owner's GitHub account. A QA review is
   therefore identified by its first line, `claude-auto-review head=<sha>`, not
   by the GitHub author.

QA is therefore separate from the authoring session, but it is not independent
of the AI supplier (ETB-ACQ4-001 §4.5): both sessions run the same product. Nor
is it independent of the project lead, who instructs both sessions and decides
on every finding.

**SUP.1.BP7** expects non-conformances that cannot be resolved at project level
to be escalated to a higher authority. ETB-SUP1-001 §8 ends escalation at the
project lead. There is no higher authority in the project.

---

## 5. Justification for Acceptance

**Separation that exists is used.** The QA session reviews only what it is given,
in the form ETB-SUP1-001 §6.5 sets, and does not change the work. Its findings
are posted on the pull request, where the author must answer each one, and they
stay there. The reviews of #381 and #383 show it finding defects the author's
session missed, including one that failed a required check.

**The checks that matter most do not depend on who runs them.** The required
status checks (ETB-SUP8-001 §5.5), the traceability test, the versioning check
and the status-cell test fail the build whoever wrote the change.

**Independence of the supplier is not available.** A second AI product would
remove the shared-supplier weakness, but no second supplier is used, and
inventing an independent reviewer would corrupt the record (ETB-DEV-002 §5).

**Escalation beyond the lead would be a fiction.** The project lead is the owner
of the repository and the only person in the project. An escalation path naming
anyone else would describe something that cannot happen. What the plan does
instead is keep every unresolved non-conformance open, as an issue, until the
lead closes it with a reason (ETB-SUP1-001 §6.7, step 4).

---

## 6. Compensating Measures

1. The QA review is required on every pull request. A merge without one is itself
   a non-conformance (ETB-SUP1-001 §6.5).
2. A process QA audit is held before each release, and its result is recorded
   per release in ETB-SUP1-003 (ETB-SUP1-001 §6.7).
3. Every non-conformance found by QA that is not fixed in the pull request is
   raised as an issue and tracked to closure (ETB-SUP9-001).
4. The internal audit (ETB-SUP1-002) is repeated for each capability claim
   (#380).

---

## 7. Corrective Action

None while the project has one human member and one AI supplier. This deviation
is closed when either of these happens:

1. a second person, outside the work, performs or reviews QA. That person then
   becomes the escalation point beyond the lead;
2. QA is performed with a product from a different supplier from the one that
   authors the work.

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
| ETB-DEV-001 | Embedded Test Bench AI Authorship Deviation | 0.5 |
| ETB-DEV-002 | Embedded Test Bench Independent Review Deviation | 0.5 |
| ETB-SUP1-001 | Embedded Test Bench Quality Assurance Plan | 0.5 |
| ETB-ACQ4-001 | Embedded Test Bench Supplier Monitoring Plan | 0.11 |
