# Software Version Description

*Automotive SPICE® PAM v4.0 | SUP.8 — Configuration Management*

---

## 1. Document Identification & Control

| Field | Value | Field | Value |
|---|---|---|---|
| **Document ID** | ETB-SVD-001 | **Version** | 0.4 |
| **Project** | Embedded Test Bench | **Date** | 2026-10-04 |
| **Status** | Draft | **Classification** | Internal |
| **Author** | Claude | **Reviewer** | Dermot Murphy |
| **Approver** | Dermot Murphy | **Related Process** | SUP.8 |

> Reviewer and Approver are the same person; see ETB-DEV-002.

---

## 2. Revision History

| Version | Date | Author | Description of Change |
|---|---|---|---|
| 0.1 | 2026-09-19 | Claude | Initial |
| 0.2 | 2026-09-23 | Claude | Known problem 6 restated: the multimeter is implemented but unconfirmed against hardware, rather than deferred. |
| 0.3 | 2026-10-04 | Claude | #170: §4 repository identifier updated for the rename from `dermot-murphy/TestTools` to `dermot-murphy/EmbeddedTestBench`; the former name is kept beside it. |
| 0.4 | 2026-10-04 | Claude | #183: product renamed to Embedded Test Bench - document file name prefix `EmbeddedTestBench_`, identifier prefix `ETB-` (was `TB-`), product name in prose. Earlier revision rows keep the names in use when they were written. |

---

## 3. Purpose & Scope

### 3.1 Purpose

This document describes exactly what a Embedded Test Bench baseline contains, so that the
baseline can be rebuilt and a result produced by it can be attributed to a known
configuration.

### 3.2 Referenced Documents

| Document ID | Title | Version |
|---|---|---|
| ETB-SUP8-001 | Embedded Test Bench Configuration Management Plan | 0.1 |
| ETB-SUP9-001 | Embedded Test Bench Problem Resolution Management Plan | 0.1 |
| ETB-SYS5-001 | Embedded Test Bench System Qualification Test | 0.1 |
| ETB-ACQ4-001 | Embedded Test Bench Supplier Monitoring Plan | 0.1 |
| ETB-PA2-001 | Embedded Test Bench Process Capability Records | 0.1 |

### 3.3 Scope

The software, firmware, documents and tools that make up the baseline described
in §4. Physical instruments are identified per run, in the run's own report,
not here.

---

## 4. Baseline Identification

| Field | Value |
|---|---|
| **Baseline** | Document baseline — the first Embedded Test Bench ASPICE set |
| **Status** | **Draft.** Not yet tagged; this SVD describes the state on the working branch |
| **Repository** | `dermot-murphy/EmbeddedTestBench` (formerly `dermot-murphy/TestTools`) |
| **Branch** | `claude/tek-3014b-scope-driver-b9ikvm` |
| **Date** | 2026-09-19 |

When this baseline is approved, an annotated tag is created and this document
records the tag and the exact revision. Until then the fields above say what is
true, which is that no tag exists yet.

---

## 5. Contents

### 5.1 Software

| Item | Version | Notes |
|---|---|---|
| `benchtools` (Python package) | 4.0.0 | `pyproject.toml`; requires Python ≥ 3.8; no mandatory runtime dependencies |
| Optional extras | `spec` (PyYAML ≥ 5.1), `plot` (matplotlib ≥ 3.3), `visa` (pyvisa ≥ 1.11, pyvisa-py ≥ 0.5), `serial` (pyserial ≥ 3.4), `test` | A driver works on a bare Python install; extras add file formats, plots and transports |

> The package version and the document versions differ deliberately. `benchtools`
> keeps its own release history at 4.0.0; the document set is renumbered to 0.1
> as the first Embedded Test Bench-named baseline. Aligning them by renumbering the package
> would have thrown away a real history to make a table look tidy.

### 5.2 Firmware

| Item | Version | Notes |
|---|---|---|
| Nordic dongle application | 1.4.0 | `firmware/nordic_dongle/include/firmware_version.h`; host protocol 1.4 |
| Target | nRF52840, board PCA10059 | |
| Platform | nRF5 SDK 17.1.0, S140 SoftDevice 7.2.0 | Vendor-supplied, not redistributed |
| Flash and RAM usage | Recorded by each CI build | ETB-SWE4-002 §4.6 |
| DFU package | Produced by `make … dfu` | |

### 5.3 Documents

| Document ID | Title | Version | Status |
|---|---|---|---|
| ETB-SYS2-001 | System Requirements Specification | 0.1 | Draft |
| ETB-SYS3-001 | System Architecture | 0.1 | Draft |
| ETB-SYS4-001 | System Integration & Integration Test | 0.1 | Draft |
| ETB-SYS5-001 | System Qualification Test | 0.1 | Draft |
| ETB-SWE1-001 | Software Requirements Specification | 0.1 | Draft |
| ETB-SWE2-001 | Software Architecture | 0.1 | Draft |
| ETB-SWE3-001 | Software Detailed Design | 0.1 | Draft |
| ETB-SWE4-001 | Unit Verification Specification | 0.1 | Draft |
| ETB-SWE4-002 | Unit Verification Report | 0.1 | Draft |
| ETB-SWE5-001 | Software Integration & Integration Test | 0.1 | Draft |
| ETB-SWE6-001 | Software Qualification Test | 0.1 | Draft |
| ETB-RTM-001 | Traceability Matrix | 0.1 | Draft |
| ETB-MAN3-001 | Project Management Plan | 0.1 | Draft |
| ETB-MAN5-001 | Risk Management Plan | 0.1 | Draft |
| ETB-SUP1-001 | Quality Assurance Plan | 0.1 | Draft |
| ETB-SUP8-001 | Configuration Management Plan | 0.1 | Draft |
| ETB-SUP9-001 | Problem Resolution Management Plan | 0.1 | Draft |
| ETB-SUP10-001 | Change Request Management Plan | 0.1 | Draft |
| ETB-ACQ4-001 | Supplier Monitoring Plan | 0.1 | Draft |
| ETB-SVD-001 | Software Version Description *(this document)* | 0.1 | Draft |
| ETB-PA2-001 | Process Capability Records | 0.1 | Draft |
| ETB-STD-001 | Industry C Coding Standards — Applicability | 0.1 | Draft |
| ETB-STD-002 | Embedded C Coding Standard | 0.1 | Draft |
| ETB-STY-001 | Embedded C Style Guide | 0.1 | Draft |
| ETB-ANA-001 | Repository Analysis Report | 0.1 | Draft |
| ETB-DEV-001 | AI Authorship Deviation | 0.1 | Draft |
| ETB-DEV-002 | Independent Review Deviation | 0.1 | Draft |
| ETB-TMPL-001 | Work Product Review Record — Template | 0.1 | Draft |
| ETB-TMPL-002 | Test Case Specification — Template | 0.1 | Draft |

Every document in this baseline is **Draft**. None has been through the review
recorded on ETB-TMPL-001, because no such review has been held.

### 5.4 Specifications and Bench Descriptions

| Item | Purpose |
|---|---|
| `action.yml` | The bench-runner composite action this repository publishes |
| `.github/workflows/bench.yml` | Runs the specifications below through that action against the simulated bench |
| `.github/workflows/style.yml` | Runs CStyleCheck over `firmware/nordic_dongle` |
| `.github/workflows/tests.yml` | Runs the Python suite with coverage, on Python 3.8, 3.9 and 3.12 |
| `.github/workflows/lint.yml` | Runs pylint over `benchtools/`, `tests/` and `scripts/` against its baseline |
| `scripts/lint.py` | The pylint runner and baseline comparison |
| `benches/simulated_bench.yaml` | The fully simulated bench |
| `benches/simulated/sensor/firmware_manifest.json` | Simulated sensor image, version 1.4.2 |
| `benches/simulated/dongle/firmware_manifest.json` | Simulated dongle image, version 1.4.0, protocol 1.4 |
| `specs/sensor_bringup.yaml` | The bring-up scenario QS-01 |
| `specs/sensor_commands.md` | The BLE command set, and the test of it |
| `specs/sensor_commands.yaml` | The suite that runs that document |

### 5.5 Build and Check Tools

| Tool | Version | Where pinned |
|---|---|---|
| Python (CI, firmware DFU packaging) | 3.10 | `.github/workflows/firmware.yml` |
| Python (CI, test matrix) | 3.8, 3.9, 3.12 | `.github/workflows/tests.yml` — 3.8 is the floor `pyproject.toml` declares |
| `nrfutil` | 6.1.7 | `.github/workflows/firmware.yml` — exact pin, see ETB-ACQ4-001 §4.3 |
| GNU Arm Embedded toolchain | As pinned in the firmware workflow | `.github/workflows/firmware.yml` |
| `dermot-murphy/CStyleCheck` | `@v1.5.1` | `.github/workflows/style.yml` |
| C rule configuration | `.cstylecheck.yml` with `.cstylecheck-baseline.json` (113 baselined violations) | Repository root |
| Python rule configuration | `[tool.pylint]` in `pyproject.toml` with `.pylint-baseline.json` (458 baselined findings) | Repository root |
| `pytest` | As declared in the `test` extra | `pyproject.toml` |
| `pylint` | **4.0.8** | `.github/workflows/lint.yml` — exact pin; its rule set decides what a green lint means |

---

## 6. Verification Status

| Measure | Value |
|---|---|
| Tests passing | 1 878 |
| Statement coverage | 94% |
| Requirements without a covering test | 0 |
| Firmware build | Green in CI; flash and RAM recorded |
| C coding-standard check | Green in CI |
| System qualification on hardware | **Not performed**, except the build scenario QS-08 |

---

## 7. Known Problems and Limitations

| # | Limitation | Reference |
|---|---|---|
| 1 | No system requirement is qualified against real instruments | ETB-SYS5-001 §6 |
| 2 | Sixteen system integration cases are not performed | ETB-SYS4-001 §5 |
| 3 | Bench-confirmation items remain open for the scope, probe, dongle, supply and S2-LP kit | ETB-SYS5-001 §7 |
| 4 | No MISRA checker runs in CI; those rules rest on review | ETB-STD-001 §7.1 |
| 5 | The firmware build sets no explicit `-std` and does not enable `-Wextra` | ETB-STD-002 §7.1, §7.2 |
| 6 | The TTi 1604 multimeter driver is written from cited documentation and has not been run against a physical meter | `docs/dmm/TTi1604_Notes.md` §5, ETB-SYS2-104 |
| 7 | No document in this baseline has been reviewed | §5.3 |
| 8 | The Python lint check is baselined at 436 existing findings and fails only on new ones; `duplicate-code` is disabled because its output is not reproducible across machines | ETB-ANA-001 §6.13 |
| 9 | The C standard check is baselined at 113 existing violations and fails only on new ones | ETB-ANA-001 §6.12 |
| 10 | Python 3.8 is end-of-life upstream. It is tested because `pyproject.toml` declares it as the floor; when supporting it stops being tenable the floor should be raised rather than the leg dropped | ETB-ANA-001 §6.1 |

None of these is a defect against a stated requirement. They are the distance
between what Embedded Test Bench is shown to do and what it will eventually be shown to
do, recorded so that the distance is visible.

---

## 8. Installation

```
pip install -e .[spec,serial,test]
pytest
```

The firmware is built with `make` under `firmware/nordic_dongle`, with the
toolchain and `nrfutil` versions of §5.5; `make … dfu` produces the DFU package.

---

## 9. Review & Approval

| Role | Name | Signature / Electronic Approval | Date |
|---|---|---|---|
| Author | Claude | Approved | 2026-09-19 |
| Reviewer | Dermot Murphy | — | *pending* |
| Approver | Dermot Murphy | — | *pending* |
