# Repository Analysis Report

*Automotive SPICE® PAM v4.0 | SUP.1 Quality Assurance — Technical Study*

---

## 1. Document Identification & Control

| Field | Value | Field | Value |
|---|---|---|---|
| **Document ID** | TB-ANA-001 | **Version** | 0.1 |
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

An analysis of the TestBench repository as it stands: what is built, what is
checked, what the checks do not reach, and what should be done about it in what
order.

Every number below was measured on the revision this document was written
against, not estimated.

### 3.2 Referenced Documents

| Document ID | Title | Version |
|---|---|---|
| TB-PA2-001 | TestBench Process Capability Records | 0.1 |
| TB-SVD-001 | TestBench Software Version Description | 0.1 |
| TB-SYS5-001 | TestBench System Qualification Test | 0.1 |
| TB-STD-001 | Industry C Coding Standards — Applicability | 0.1 |
| TB-SUP1-001 | TestBench Quality Assurance Plan | 0.1 |
| TB-MAN5-001 | TestBench Risk Management Plan | 0.1 |

### 3.3 Scope

The whole repository: Python package, firmware, specifications, documents and
CI. It is a snapshot; it is not maintained as the repository changes, and its
date says which revision it describes.

---

## 4. Metrics

| Metric | Value |
|---|---|
| Python source files | 78 |
| Python source lines | 23 611 |
| Test files | 77 |
| Test lines | 13 615 |
| Firmware C files (project-owned) | 47 |
| Firmware C lines | 2 856 |
| ASPICE documents | 27 |
| CI workflows | 1 |
| Tests passing | 1 878 |
| Statement coverage | 94% (577 of 10 374 statements uncovered) |

A test-to-source line ratio of 0.58 is high for a tool of this kind, and the
1:1 ratio of test files to source files reflects a deliberate structure: each
module has a test module beside it.

---

## 5. Scorecard

| Severity | Count |
|---|---|
| 🔴 Critical | 2 |
| 🟡 Warning | 5 |
| 🔵 Improvement | 4 |
| ✅ Well handled | 6 |

---

## 6. Findings

### 6.1 🔴 Critical — The Python suite is not run by CI

`.github/workflows/` contains **one** workflow, `firmware.yml`. The 1 878 tests
that constitute nearly all of this project's evidence run only when someone runs
them locally before committing.

Everything the quality plan relies on — the traceability check that binds
documents to code, the layering test that enforces the architecture, the driver
tests — is therefore unenforced on a pull request. A change that breaks them can
be merged by anyone who does not run them, and TB-SUP1-001 §4 lists four quality
objectives (TB-QA-001 through TB-QA-004) whose measurement is not automated
anywhere.

**Action:** add a workflow running `pytest` on every push and pull request, with
the extras installed. This is the single highest-value change in this report and
the cheapest.

### 6.2 🔴 Critical — No driver has met its instrument

Every one of the seven drivers is confirmed only against a simulator written by
the same author from the same reading of the same documentation. Where that
reading is wrong, driver and simulator are wrong together and the tests pass.

This is TB-RISK-001, rated exposure 9, and it is the project's central
technical risk rather than an oversight: TB-SYS4-001 §5 records sixteen
integration cases as not performed, and TB-SYS5-001 §6 shows one hardware pass
out of eight qualification scenarios — the build.

The architecture mitigates it as far as architecture can: simulators model
instrument state rather than echo expected replies, every simulated run is
labelled, and each element carries its open bench-confirmation items. None of
that substitutes for attaching an instrument.

**Action:** milestone M6. Work the stages of TB-SYS4-001 §4 in order.

### 6.3 🟡 Warning — No MISRA checker in CI

The style workflow runs CStyleCheck, which enforces naming, structure and
formatting. The rules of TB-STD-002 that need a type system or control-flow
analysis are enforced by review alone. TB-STD-001 §7.1 states this; it is
repeated here because it is a gap a reader might otherwise assume closed by the
presence of a green style badge.

**Action:** add Cppcheck `--misra` to the style workflow, or accept the gap
explicitly as a change request decision.

### 6.4 🟡 Warning — Firmware compiled with an unstated language standard

`firmware/nordic_dongle/Makefile` sets `-Wall -Werror` but no `-std`, so the
language the firmware is compiled as is whatever the pinned toolchain defaults
to. A toolchain upgrade can change it silently. `-Wextra` is also not enabled.

**Action:** set `-std=gnu11` (or the dialect the SDK requires) explicitly, and
enable `-Wextra`, fixing what it finds in project-owned files.

### 6.5 🟡 Warning — No work product has been reviewed

All 27 documents are Draft. TB-TMPL-001 and TB-TMPL-002 ship blank. This is
GP 2.2.4 rated P in TB-PA2-001 §6, and it is deliberate — no review record is
filed for a review that did not happen — but it remains a real weakness, not
merely a bookkeeping state.

**Action:** hold reviews and file the records. The order that gets most value
first: TB-SYS2-001, TB-SWE1-001, then the architecture and design documents.

### 6.6 🟡 Warning — `probe.py` is 1 499 lines

`benchtools/instruments/jlink/probe.py` is the largest module by a wide margin,
followed by `dongle.py` at 1 033 and `scope.py` at 964. The J-Link driver does
several distinct jobs — GDB/MI session management, flash programming, memory
access, RTT, four timing methods — and their being in one file is why it is
that size.

Its coverage is good and its structure is documented, so this is a
maintainability observation rather than a defect.

**Action:** consider splitting the timing methods and the RTT transport into
their own modules when that file is next substantially changed. Not worth doing
for its own sake.

### 6.7 🟡 Warning — `visa_backend.py` at 77% coverage

The lowest-covered module in the package. It is the optional path — a transport
used only when someone installs the `visa` extra and asks for it — so the
untested lines are the ones that run for users who have configured the thing
that is hardest to test in CI.

**Action:** cover the error paths with a fake VISA library; they are the lines
that matter.

### 6.8 🔵 Improvement — Transport error paths are the uncovered tail

The uncovered 6% concentrates in `vxi11.py` (37 statements), `process.py` (16),
`socket_raw.py` (9) and `s2lp/simulator.py` (26): overwhelmingly error and
timeout branches. These are exactly the paths that run when a bench goes wrong,
and they are what stands between a clear error and a mysterious one.

**Action:** fault-injection tests on the transports.

### 6.9 🔵 Improvement — `__main__.py` has no test

Four statements, 0% covered. The entry point is trivial but it is the first
thing a new user executes.

**Action:** one smoke test invoking the module.

### 6.10 🔵 Improvement — The analysis snapshot has no refresh trigger

This document goes stale by design. Nothing causes it to be revisited.

**Action:** revisit it at each milestone review, per TB-MAN3-001 §10.

### 6.11 🔵 Improvement — The deviation register directory does not exist

TB-STD-002 §72 points at `docs/aspice/deviations/`, which is currently empty of
any register. No C deviation has been raised, so nothing is missing — but the
first person to need one will find no file to add to.

**Action:** create the register with its header and no entries when the first
deviation is raised, not before.

---

## 7. Well Handled

| # | What | Why it counts |
|---|---|---|
| ✅1 | **Mechanical traceability.** `tests/test_traceability.py` fails the build if code cites an undeclared requirement, if a declared requirement has no test, or if the matrix omits either | This is the control that makes the document set trustworthy rather than decorative, and it cannot be satisfied by writing prose |
| ✅2 | **The layering test.** `tests/test_layering.py` enforces the architecture's one-way dependencies | An architecture that is checked is an architecture; one that is only drawn is a diagram |
| ✅3 | **Simulators model behaviour.** The supply's tracking modes and its silent discard of slaved-channel setpoints, the probe's run states, the dongle's connection states | The alternative — replaying expected replies — would make the whole suite worthless, and is the most common way test doubles fail |
| ✅4 | **Simulation is disclosed.** Every report format states when a run was simulated | Prevents the most dangerous possible misreading of this tool's output |
| ✅5 | **Deviations are recorded, not hidden.** TB-DEV-001 names the authorship problem; TB-DEV-002 names the reviewer problem; TB-PA2-001 rates three practices P and states CL2 is not achieved | A self-assessment that rates itself F throughout tells a reader nothing |
| ✅6 | **Build tooling is pinned where it bites.** `nrfutil==6.1.7` with Python 3.10, after an unpinned install resolved backwards to a Python 2 release | Pinned for a reason that was discovered, with the reason recorded (TB-RISK-006) |

---

## 8. Prioritised Actions

| # | Action | Finding | Effort | Value |
|---|---|---|---|---|
| 1 | Add a CI workflow running `pytest` | 6.1 | Low | **Highest.** It makes every other control enforcing |
| 2 | Attach instruments; work TB-SYS4-001 §4 stages in order | 6.2 | High | Highest — it is the only thing that can qualify the system |
| 3 | Set `-std` explicitly and enable `-Wextra` | 6.4 | Low | Medium |
| 4 | Hold and record reviews, starting with the requirements documents | 6.5 | Medium | Medium |
| 5 | Add a MISRA checker to the style workflow | 6.3 | Low | Medium |
| 6 | Cover the transport error paths and `visa_backend.py` | 6.7, 6.8 | Medium | Medium |
| 7 | Smoke-test `__main__.py` | 6.9 | Trivial | Low |
| 8 | Split `probe.py` when next substantially changed | 6.6 | Medium | Low |

Actions 1 and 3 together cost an afternoon and close a critical finding and a
warning. Action 2 is the project.

---

## 9. Conclusion

The repository is in better shape than its ASPICE ratings suggest, and its
ASPICE ratings are honest about why. The engineering controls that are hard to
fake — mechanical traceability, an enforced architecture, simulators that model
rather than echo, disclosure of simulated runs — are in place and working. The
two critical findings are both about reach rather than quality: the checks exist
but CI does not run them, and the drivers are correct as far as anything without
an instrument can be.

Neither is fixed by writing a document. One is fixed by a twenty-line workflow
file; the other by plugging something in.

---

## 10. Review & Approval

| Role | Name | Signature / Electronic Approval | Date |
|---|---|---|---|
| Author | Claude | Approved | 2026-09-19 |
| Reviewer | Dermot Murphy | — | *pending* |
| Approver | Dermot Murphy | — | *pending* |
