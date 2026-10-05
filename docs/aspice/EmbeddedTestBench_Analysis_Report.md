# Repository Analysis Report

*Automotive SPICE® PAM v4.0 | SUP.1 Quality Assurance — Technical Study*

---

## 1. Document Identification & Control

| Field | Value | Field | Value |
|---|---|---|---|
| **Document ID** | ETB-ANA-001 | **Version** | 0.3 |
| **Project** | Embedded Test Bench | **Date** | 2026-10-05 |
| **Status** | Draft | **Classification** | Internal |
| **Author** | Claude | **Reviewer** | Dermot Murphy |
| **Approver** | Dermot Murphy | **Related Process** | SUP.1 |

> Reviewer and Approver are the same person; see ETB-DEV-002.

---

## 2. Revision History

| Version | Date | Author | Description of Change |
|---|---|---|---|
| 0.1 | 2026-09-19 | Claude | Initial |
| 0.2 | 2026-10-04 | Claude | #183: product renamed to Embedded Test Bench - document file name prefix `EmbeddedTestBench_`, identifier prefix `ETB-` (was `TB-`), product name in prose. Earlier revision rows keep the names in use when they were written. |
| 0.3 | 2026-10-05 | Claude | #203: §6.1 - the 3.9 and 3.12 legs, and every other job, now pin `ubuntu-24.04` instead of `ubuntu-latest`, which moves to Ubuntu 26 from 2026-10-19. The 3.8 leg stays on `ubuntu-22.04`. |

---

## 3. Purpose & Scope

### 3.1 Purpose

An analysis of the Embedded Test Bench repository as it stands: what is built, what is
checked, what the checks do not reach, and what should be done about it in what
order.

Every number below was measured on the revision this document was written
against, not estimated.

### 3.2 Referenced Documents

| Document ID | Title | Version |
|---|---|---|
| ETB-PA2-001 | Embedded Test Bench Process Capability Records | 0.1 |
| ETB-SVD-001 | Embedded Test Bench Software Version Description | 0.1 |
| ETB-SYS5-001 | Embedded Test Bench System Qualification Test | 0.1 |
| ETB-STD-001 | Industry C Coding Standards — Applicability | 0.1 |
| ETB-SUP1-001 | Embedded Test Bench Quality Assurance Plan | 0.1 |
| ETB-MAN5-001 | Embedded Test Bench Risk Management Plan | 0.1 |

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
| CI workflows | 5 — `firmware.yml`, `style.yml`, `bench.yml`, `tests.yml`, `lint.yml` |
| Python versions tested | 3 — 3.8 (the declared floor), 3.9, 3.12 |
| Tests passing | 1 878 |
| Statement coverage | 94% (577 of 10 374 statements uncovered) |

A test-to-source line ratio of 0.58 is high for a tool of this kind, and the
1:1 ratio of test files to source files reflects a deliberate structure: each
module has a test module beside it.

---

## 5. Scorecard

| Severity | Count |
|---|---|
| 🔴 Critical | 1 (1 resolved) |
| 🟡 Warning | 7 |
| 🔵 Improvement | 4 |
| ✅ Well handled | 6 |

---

## 6. Findings

### 6.1 ✅ Resolved — The Python suite is now run by CI

*Raised 2026-09-19 as this report's first critical finding; resolved the same
day.*

**What it was.** Three workflows existed — `firmware.yml` (the firmware's own
Unity/CTest tests and the cross-compile), `style.yml` (the C coding-standard
check) and `bench.yml` (the bench specifications). None ran `pytest`, so the
1 878 tests carrying nearly all of this project's evidence ran only when
someone remembered to run them locally. Everything the quality plan relies on —
the traceability check binding documents to code, the layering test enforcing
the architecture — was unenforced on a pull request, and the four quality
objectives ETB-QA-001 … ETB-QA-004 were measured automatically nowhere.

**What closed it.** `.github/workflows/tests.yml` runs the suite on every push
and pull request, on two Python versions, and fails the build below the
ETB-QA-002 coverage target of 90%. The traceability and layering checks are
part of that suite, so they are now enforced where they can block a merge.

**What it exposed, and what happened to it.** The workflow first tested 3.9
and 3.12 while `pyproject.toml` declared `requires-python = ">=3.8"`, so the
package claimed a floor nothing verified. 3.8 joined the matrix rather than the
claim being lowered: the floor is not decoration for a package whose whole
point is having no mandatory runtime dependencies, and the bench PC that design
serves is the one least likely to have been rebuilt lately.

The suite passed on 3.8.20 unchanged — 1 879 tests, 94.37% coverage — so
nothing in the source needed fixing. The 3.8 leg runs on `ubuntu-22.04`,
because 3.8 is end-of-life and is not in the tool cache for the 24.04 image.
The other legs, and every other job, pin `ubuntu-24.04` by name rather than
`ubuntu-latest`, which moves to Ubuntu 26 from 2026-10-19 (#203): a runner
image change is then a change someone makes, not one that happens to the
suite.

### 6.2 🔴 Critical — No driver has met its instrument

Every one of the seven drivers is confirmed only against a simulator written by
the same author from the same reading of the same documentation. Where that
reading is wrong, driver and simulator are wrong together and the tests pass.

This is ETB-RISK-001, rated exposure 9, and it is the project's central
technical risk rather than an oversight: ETB-SYS4-001 §5 records sixteen
integration cases as not performed, and ETB-SYS5-001 §6 shows one hardware pass
out of eight qualification scenarios — the build.

The architecture mitigates it as far as architecture can: simulators model
instrument state rather than echo expected replies, every simulated run is
labelled, and each element carries its open bench-confirmation items. None of
that substitutes for attaching an instrument.

**Action:** milestone M6. Work the stages of ETB-SYS4-001 §4 in order.

### 6.3 🟡 Warning — No MISRA checker in CI

The style workflow runs CStyleCheck, which enforces naming, structure and
formatting. The rules of ETB-STD-002 that need a type system or control-flow
analysis are enforced by review alone. ETB-STD-001 §7.1 states this; it is
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

All 27 documents are Draft. ETB-TMPL-001 and ETB-TMPL-002 ship blank. This is
GP 2.2.4 rated P in ETB-PA2-001 §6, and it is deliberate — no review record is
filed for a review that did not happen — but it remains a real weakness, not
merely a bookkeeping state.

**Action:** hold reviews and file the records. The order that gets most value
first: ETB-SYS2-001, ETB-SWE1-001, then the architecture and design documents.

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

**Action:** revisit it at each milestone review, per ETB-MAN3-001 §10.

### 6.11 🔵 Improvement — The deviation register directory does not exist

ETB-STD-002 §72 points at `docs/aspice/deviations/`, which is currently empty of
any register. No C deviation has been raised, so nothing is missing — but the
first person to need one will find no file to add to.

**Action:** create the register with its header and no entries when the first
deviation is raised, not before.

### 6.12 🟡 Warning — The C standard check runs against a baseline of 113 violations

`.cstylecheck-baseline.json` records 113 violations present when the check was
introduced, so `style.yml` fails only on new ones. The baseline is real debt,
and what is in it is worth naming:

| Rule | Count | What it is |
|---|---|---|
| `function.prefix` | 43 | Static helper functions carry no module prefix. The checker cannot distinguish internal linkage, so every one is reported |
| `constant.prefix` | 30 | File-scope constants use a short uppercase prefix (`CMD_`) rather than the full module name |
| `misc.unsigned_suffix` | 27 | Unsigned literals written without a `U` suffix |
| `misc.magic_number` | 5 | Literals that should be named |
| `macro.prefix` | 3 | X-macros named `X` |
| `misc.function_length` | 2 | Two long functions |
| `variable.global.g_prefix` | 2 | Globals without the `g_` prefix |
| `macro.trailing_semicolon` | 1 | CERT PRE11-C |

The rules that Embedded Test Bench's firmware genuinely does not adopt — Barr-C's `p_`
pointer prefix and Yoda conditions — are **disabled** in `.cstylecheck.yml`
rather than baselined, because a rule the project has decided against should be
switched off and said so, not silently suppressed. The statics prefix is
configured to the `m_` this firmware actually uses.

The distinction matters: the disabled rules are decisions, the baselined ones
are debt.

**Action:** the `misc.unsigned_suffix` and `misc.magic_number` entries are worth
fixing outright — they are MISRA-adjacent and the fixes are local. The prefix
findings need a decision recorded in ETB-STY-001 first: either adopt the module
prefix on internal functions, or exempt internal linkage as a stated
convention.

### 6.13 🟡 Warning — The Python lint check runs against a baseline of 436 findings

`pylint` at its defaults reported **3 282** findings over `benchtools/` and
`tests/`, scoring 8.23/10. That came down in three steps, and the difference
between them is the point:

| Step | Findings removed | What it was |
|---|---|---|
| Rules the project has decided against | 954 | Disabled in `pyproject.toml` with the reason written beside each |
| Rules that do not apply to a test suite | 1 816 | Disabled for `tests/` only, in `scripts/lint.py`, with the reason |
| **Defects actually fixed** | **76** | 57 unused imports, 8 unused variables, 4 missing `raise ... from`, 7 packed statements |
| Remaining, baselined | 436 | Debt |

The five project decisions are: `duplicate-code` (22 — see below),
`consider-using-f-string` (645 — the package
uses %-formatting consistently, and converting it buys a reader nothing),
`import-outside-toplevel` (63 — optional dependencies are imported where they
are used *on purpose*, so a driver works on a bare Python install),
`attribute-defined-outside-init` (79 — simulator state is established in
`reset()`, which pylint does not follow), and two naming regexes that permit
`_cmd_ALLEV_Q` (a method named for the SCPI header it handles — renaming it
would hide the thing it exists to match).

What is in the baseline:

| Rule | Count | What it is |
|---|---|---|
| `missing-function-docstring` | 98 | Undocumented functions in the package |
| `line-too-long` | 47 | Lines over 100 characters |
| `useless-return` | 41 | Trailing `return None` |
| `consider-using-with` | 36 | Resources opened without a context manager |
| `unused-argument` | 35 | Mostly callback signatures required by an API |
| `too-many-*` | 124 | Design metrics — instance attributes, arguments, locals, branches |
| `broad-exception-caught` | 13 | The runner turns any driver exception into a recorded step error |
| others | 42 | |

**`duplicate-code` is disabled because it cannot be enforced, and that hides
something real.** The rule compares files against each other, and which pairs
it reports depends on the order the files are walked in: the same tree, linted
locally and on a GitHub runner, produced the same *number* of similarities and
named *different pairs*. A rule whose output is not reproducible cannot gate a
build, and baselining it only moves the flapping into the baseline.

What it was pointing at is real, so it is recorded here rather than silenced:
five driver command-line modules — `gpd3303d`, `jlink`, `s2lp`, `tek3014b` and
the runner — carry the same `main()` boilerplate, parsing arguments, setting
the logging level from `-v` and dispatching inside a `try`. Three of them also
share an identical `_emit()` that dumps JSON to stdout and optionally to a
file. That belongs in one helper in `core`. It is a real piece of debt with a
real fix, and it is its own change rather than a CI ticket's.

`broad-exception-caught` is worth a second look rather than a permanent
baseline entry: catching `Exception` at the runner boundary is deliberate and
implements ETB-SYS2-003, so those thirteen are arguably a decision rather than
debt. They are baselined rather than disabled because a blanket disable would
also hide the careless catches nobody has written yet.

**Action:** the 98 missing docstrings and the 47 long lines are the tractable
half and would come out in ordinary work on those files. The design metrics
should be left alone until a module is being changed for another reason.

---

## 7. Well Handled

| # | What | Why it counts |
|---|---|---|
| ✅1 | **Mechanical traceability.** `tests/test_traceability.py` fails the build if code cites an undeclared requirement, if a declared requirement has no test, or if the matrix omits either | This is the control that makes the document set trustworthy rather than decorative, and it cannot be satisfied by writing prose |
| ✅2 | **The layering test.** `tests/test_layering.py` enforces the architecture's one-way dependencies | An architecture that is checked is an architecture; one that is only drawn is a diagram |
| ✅3 | **Simulators model behaviour.** The supply's tracking modes and its silent discard of slaved-channel setpoints, the probe's run states, the dongle's connection states | The alternative — replaying expected replies — would make the whole suite worthless, and is the most common way test doubles fail |
| ✅4 | **Simulation is disclosed.** Every report format states when a run was simulated | Prevents the most dangerous possible misreading of this tool's output |
| ✅5 | **Deviations are recorded, not hidden.** ETB-DEV-001 names the authorship problem; ETB-DEV-002 names the reviewer problem; ETB-PA2-001 rates three practices P and states CL2 is not achieved | A self-assessment that rates itself F throughout tells a reader nothing |
| ✅6 | **Build tooling is pinned where it bites.** `nrfutil==6.1.7` with Python 3.10, after an unpinned install resolved backwards to a Python 2 release | Pinned for a reason that was discovered, with the reason recorded (ETB-RISK-006) |

---

## 8. Prioritised Actions

| # | Action | Finding | Effort | Value |
|---|---|---|---|---|
| ~~1~~ | ~~Add a CI workflow running `pytest`~~ — **done**, `tests.yml` | 6.1 | Low | Highest; it makes every other control enforcing |
| 2 | Attach instruments; work ETB-SYS4-001 §4 stages in order | 6.2 | High | Highest — it is the only thing that can qualify the system |
| 3 | Set `-std` explicitly and enable `-Wextra` | 6.4 | Low | Medium |
| 4 | Hold and record reviews, starting with the requirements documents | 6.5 | Medium | Medium |
| 5 | Add a MISRA checker to the style workflow | 6.3 | Low | Medium |
| 6 | Cover the transport error paths and `visa_backend.py` | 6.7, 6.8 | Medium | Medium |
| 7 | Fix the U-suffix and magic-number entries in the style baseline | 6.12 | Low | Medium |
| 8 | Smoke-test `__main__.py` | 6.9 | Trivial | Low |
| 9 | Split `probe.py` when next substantially changed | 6.6 | Medium | Low |

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
