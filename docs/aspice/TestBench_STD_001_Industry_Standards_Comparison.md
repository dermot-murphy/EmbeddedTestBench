# Industry C Coding Standards — Applicability to TestBench

*Automotive SPICE® PAM v4.0 | SUP.1 Quality Assurance — Technical Study*

---

## 1. Document Identification & Control

| Field | Value | Field | Value |
|---|---|---|---|
| **Document ID** | TB-STD-001 | **Version** | 0.1 |
| **Project** | TestBench | **Date** | 2026-09-19 |
| **Status** | Draft | **Classification** | Internal |
| **Author** | Claude | **Reviewer** | Dermot Murphy |
| **Approver** | Dermot Murphy | **Related Process** | SUP.1 |

> Reviewer and Approver are the same person; see TB-DEV-002.

---

## 2. Revision History

| Version | Date | Author | Description of Change |
|---|---|---|---|
| 0.1 | 2026-09-19 | Claude | Initial |

---

## 3. Purpose & Scope

### 3.1 Purpose

TB-STD-002 and TB-STY-001 state the rules TestBench's C obeys. This document
says **where those rules come from**, which published standards were considered,
which were adopted and to what depth, and — the part that is easiest to skip and
most worth writing — which were *not* adopted, with the reason.

A coding standard whose provenance is unstated invites two bad readings: that
every rule is somebody's taste, or that the whole of MISRA is being claimed.
Neither is true here.

### 3.2 Referenced Documents

| Document ID | Title | Version |
|---|---|---|
| TB-STD-002 | TestBench Embedded C Coding Standard | 0.1 |
| TB-STY-001 | TestBench Embedded C Style Guide | 0.1 |
| TB-SYS2-001 | TestBench System Requirements Specification | 0.1 |
| TB-SUP1-001 | TestBench Quality Assurance Plan | 0.1 |
| TB-ACQ4-001 | TestBench Supplier Monitoring Plan | 0.1 |
| CSC-STD-001 | CStyleCheck — Industry C Coding Standards Comparative Analysis | 1.2 |

CSC-STD-001 holds the rule-by-rule coverage matrix for the checker used here.
It is cited rather than copied: which rules CStyleCheck implements is a property
of CStyleCheck, and restating it in this repository would create a second copy
free to go stale.

### 3.3 Scope

The C source owned by this project — `firmware/nordic_dongle/src/` and its
headers. Vendor SDK sources are out of scope (TB-STD-002 §1.3).

---

## 4. What TestBench's C Actually Is

The scope matters to which standards make sense, so it is stated first:

| Property | Value |
|---|---|
| Size | One firmware application: a BLE bench dongle |
| Target | nRF52840, Cortex-M4F, single core |
| Platform | nRF5 SDK 17.1.0 with the S140 SoftDevice — an event-driven callback architecture, no RTOS scheduler of this project's own |
| Concurrency | Interrupt and SoftDevice callback context against main context; no threads |
| Allocation | Static; no `malloc` |
| Safety classification | **None.** A test tool; carries no ASIL and ships in no product (TB-SYS2-102) |
| Lifetime | Long — a bench tool outlives the products it tests |

Two consequences run through everything below. First, the standards written for
*delivered* safety-related software apply as **engineering guidance**, not as
compliance obligations: there is no safety case to support and no assessor to
satisfy. Second, the SDK's own idioms are in the file next to ours, so a rule
that the vendor's code cannot follow is a rule about our code only, and is
written that way.

---

## 5. Standards Surveyed

| # | Standard | Publisher | Availability | Stance for TestBench |
|---|---|---|---|---|
| S1 | **MISRA C:2012 (+AMD2/2023)** | MISRA Consortium | Paid | **Primary normative source.** Adopted as a subset — §6 |
| S2 | **Barr-C:2018** | Barr Group | Free | **Adopted for style.** TB-STY-001's naming, layout and comment rules follow it where it and MISRA do not conflict |
| S3 | **SEI CERT C** | CMU SEI | Free | **Adopted selectively** — the rules about undefined behaviour and integer handling, which are the ones a bench tool gets wrong quietly |
| S4 | **NASA/JPL Power of Ten** | NASA/JPL | Free | **Adopted in spirit.** Static allocation, bounded loops, checked returns, assertion density — all already true of this firmware |
| S5 | ESA BSSC 2000-1 | ESA | Free | **Not adopted.** Its distinctive content is about space-system process and C++; its C rules are a subset of MISRA's |
| S6 | JSF AV C++ | Lockheed Martin | Free | **Not applicable.** C++ |
| S7 | Linux kernel style | Linux community | Free | **Partially adopted, deliberately:** tabs at eight columns, braces mandatory, functions that fit on a screen. The kernel's naming and its `goto`-based cleanup are not adopted |
| S8 | AUTOSAR C++14 | AUTOSAR | Partial | **Not applicable.** C++; its C-applicable content is in MISRA C |
| S9 | IEC 61508-3 | IEC | Paid | **Not applicable.** No SIL claim. Defers to MISRA for C in any case |
| S10 | DO-178C | RTCA | Paid | **Not applicable.** No airborne software. Requires *a* documented standard, which TB-STD-002 is |
| S11 | ISO 26262 | ISO | Paid | **Not applicable as a compliance obligation** — no ASIL (TB-SYS2-102). Its §6.4.5 recommendation that a project *have* naming conventions and a style guide is met |
| S12 | FACE Technical Standard | The Open Group | Members | **Not applicable.** API portability capability sets; no style rules |
| S13 | CWE Top 25 | MITRE | Free | **Consulted, not adopted as rules.** A weakness taxonomy; the C-relevant entries map onto CERT C |

### 5.1 Standards That Mandate a Standard

S9, S10 and S11 share a shape worth naming: each requires that a project have a
documented coding standard and none defines one. Citing them as "standards
TestBench follows" would be close to meaningless. What TestBench takes from them
is the obligation itself — have a written standard, enforce it, record
deviations — which TB-STD-002, `.github/workflows/style.yml` and §72 of that
document discharge.

---

## 6. MISRA C:2012 — Depth of Adoption

TestBench adopts a **subset**, and says which, because claiming MISRA compliance
without a compliance matrix and a deviation register is the single most common
untruth told about embedded C.

| Category | Stance |
|---|---|
| **Mandatory** rules | Adopted in full. No deviation is permitted |
| **Required** rules | Adopted, with deviations permitted only through TB-STD-002 §72 and recorded in the deviation register |
| **Advisory** rules | Adopted where mechanically checkable or cheap at review; not claimed otherwise |
| Directives | Adopted where they concern documented behaviour and traceability; the ones requiring a full development-environment argument are not claimed |

### 6.1 What Is Not Claimed

| Not claimed | Why |
|---|---|
| Full MISRA C:2012 compliance | No certified MISRA checker is run over this source; the checks in CI are CStyleCheck's subset plus the compiler's |
| A complete compliance matrix | Rule-by-rule status has not been established for every rule; §7 says what *is* established |
| Compliance of SDK and SoftDevice sources | Vendor code, out of scope (TB-STD-002 §1.3), and it would not pass |
| Tool qualification of the compiler | Not applicable (TB-STD-002 §7.5) |

Stating this plainly costs nothing here and prevents a reader downstream from
inheriting a claim TestBench never made.

---

## 7. Enforcement — Who Checks What

| Layer | Enforces | Runs |
|---|---|---|
| Compiler (`-Wall -Werror`) | The overlap between MISRA's type and control-flow rules and what GCC diagnoses | Every build, locally and in CI |
| **CStyleCheck** `@v1` | The mechanically checkable subset of TB-STY-001 and the naming, structure and sign-compatibility rules of TB-STD-002 — see CSC-STD-001 for its matrix | Every push, `.github/workflows/style.yml` |
| AStyle configuration | Formatting, where a file is reformatted | On demand |
| Review | Everything the tools cannot see: whether a rule was followed in substance, and whether a deviation is justified | TB-TMPL-001 §6.5 |

### 7.1 The Honest Gap

No MISRA checker runs in this project's CI. The rules of TB-STD-002 that only a
MISRA checker or a full static analyser could verify are therefore enforced by
review alone, which is weaker, and is recorded here as weaker. Closing it would
mean adding Cppcheck `--misra` or a commercial analyser to the style workflow;
that is a candidate change request, not a claim.

---

## 8. Rules Adopted From Outside MISRA

The rules in TB-STD-002 and TB-STY-001 that do **not** come from MISRA, with
their source, so that a reader can tell taste from citation:

| Rule area | Source | Note |
|---|---|---|
| Tabs at eight columns | S7 Linux kernel style | A project convention; either choice is defensible, and having one is what matters |
| Module prefix on public identifiers | S2 Barr-C | Makes the owning module visible at the call site |
| File header content and ordering | S2 Barr-C | |
| Function length and nesting depth limits | S4 Power of Ten, S2 Barr-C | |
| Assertion density and checked returns | S4 Power of Ten | Fits this project's own rule that code fails loudly rather than continuing |
| Explicit parentheses beyond precedence | S2 Barr-C, S1 MISRA advisory | |
| `volatile` and shared-data discipline | S3 CERT C, S1 MISRA | The rules that matter most in SoftDevice callback context |

---

## 9. Conclusions

1. **MISRA C:2012 is the normative source**, adopted as a subset that is stated
   rather than implied.
2. **Barr-C:2018 supplies the style layer**, with the Linux kernel's
   indentation convention and Power of Ten's structural limits.
3. **The functional-safety standards do not apply to this project** and are
   recorded as not applicable with reasons, rather than cited for weight.
4. **Enforcement is partial and the gap is named** (§7.1). A MISRA checker in
   CI is the one change that would most improve the strength of what TB-STD-002
   claims.
5. **No compliance claim is made that this project cannot evidence**, which is
   the same rule the rest of this document set runs on.

---

## 10. Review & Approval

| Role | Name | Signature / Electronic Approval | Date |
|---|---|---|---|
| Author | Claude | Approved | 2026-09-19 |
| Reviewer | Dermot Murphy | — | *pending* |
| Approver | Dermot Murphy | — | *pending* |
