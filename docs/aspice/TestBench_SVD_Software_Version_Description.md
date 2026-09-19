# Software Version Description

*Automotive SPICE® PAM v4.0 | SUP.8 — Configuration Management*

---

## 1. Document Identification & Control

| Field | Value | Field | Value |
|---|---|---|---|
| **Document ID** | TB-SVD-001 | **Version** | 0.1 |
| **Project** | TestBench | **Date** | 2026-09-19 |
| **Status** | Draft | **Classification** | Internal |
| **Author** | Claude | **Reviewer** | Dermot Murphy |
| **Approver** | Dermot Murphy | **Related Process** | SUP.8 |

> Reviewer and Approver are the same person; see TB-DEV-002.

---

## 2. Revision History

| Version | Date | Author | Description of Change |
|---|---|---|---|
| 0.1 | 2026-09-19 | Claude | Initial |

---

## 3. Purpose & Scope

### 3.1 Purpose

This document describes exactly what a TestBench baseline contains, so that the
baseline can be rebuilt and a result produced by it can be attributed to a known
configuration.

### 3.2 Referenced Documents

| Document ID | Title | Version |
|---|---|---|
| TB-SUP8-001 | TestBench Configuration Management Plan | 0.1 |
| TB-SUP9-001 | TestBench Problem Resolution Management Plan | 0.1 |
| TB-SYS5-001 | TestBench System Qualification Test | 0.1 |
| TB-ACQ4-001 | TestBench Supplier Monitoring Plan | 0.1 |
| TB-PA2-001 | TestBench Process Capability Records | 0.1 |

### 3.3 Scope

The software, firmware, documents and tools that make up the baseline described
in §4. Physical instruments are identified per run, in the run's own report,
not here.

---

## 4. Baseline Identification

| Field | Value |
|---|---|
| **Baseline** | Document baseline — the first TestBench ASPICE set |
| **Status** | **Draft.** Not yet tagged; this SVD describes the state on the working branch |
| **Repository** | `dermot-murphy/TestTools` |
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
> as the first TestBench-named baseline. Aligning them by renumbering the package
> would have thrown away a real history to make a table look tidy.

### 5.2 Firmware

| Item | Version | Notes |
|---|---|---|
| Nordic dongle application | 1.1.0 | `firmware/nordic_dongle/include/firmware_version.h`; host protocol 1.1 |
| Target | nRF52840, board PCA10059 | |
| Platform | nRF5 SDK 17.1.0, S140 SoftDevice 7.2.0 | Vendor-supplied, not redistributed |
| Flash and RAM usage | Recorded by each CI build | TB-SWE4-002 §4.6 |
| DFU package | Produced by `make … dfu` | |

### 5.3 Documents

| Document ID | Title | Version | Status |
|---|---|---|---|
| TB-SYS2-001 | System Requirements Specification | 0.1 | Draft |
| TB-SYS3-001 | System Architecture | 0.1 | Draft |
| TB-SYS4-001 | System Integration & Integration Test | 0.1 | Draft |
| TB-SYS5-001 | System Qualification Test | 0.1 | Draft |
| TB-SWE1-001 | Software Requirements Specification | 0.1 | Draft |
| TB-SWE2-001 | Software Architecture | 0.1 | Draft |
| TB-SWE3-001 | Software Detailed Design | 0.1 | Draft |
| TB-SWE4-001 | Unit Verification Specification | 0.1 | Draft |
| TB-SWE4-002 | Unit Verification Report | 0.1 | Draft |
| TB-SWE5-001 | Software Integration & Integration Test | 0.1 | Draft |
| TB-SWE6-001 | Software Qualification Test | 0.1 | Draft |
| TB-RTM-001 | Traceability Matrix | 0.1 | Draft |
| TB-MAN3-001 | Project Management Plan | 0.1 | Draft |
| TB-MAN5-001 | Risk Management Plan | 0.1 | Draft |
| TB-SUP1-001 | Quality Assurance Plan | 0.1 | Draft |
| TB-SUP8-001 | Configuration Management Plan | 0.1 | Draft |
| TB-SUP9-001 | Problem Resolution Management Plan | 0.1 | Draft |
| TB-SUP10-001 | Change Request Management Plan | 0.1 | Draft |
| TB-ACQ4-001 | Supplier Monitoring Plan | 0.1 | Draft |
| TB-SVD-001 | Software Version Description *(this document)* | 0.1 | Draft |
| TB-PA2-001 | Process Capability Records | 0.1 | Draft |
| TB-STD-001 | Industry C Coding Standards — Applicability | 0.1 | Draft |
| TB-STD-002 | Embedded C Coding Standard | 0.1 | Draft |
| TB-STY-001 | Embedded C Style Guide | 0.1 | Draft |
| TB-ANA-001 | Repository Analysis Report | 0.1 | Draft |
| TB-DEV-001 | AI Authorship Deviation | 0.1 | Draft |
| TB-DEV-002 | Independent Review Deviation | 0.1 | Draft |
| TB-TMPL-001 | Work Product Review Record — Template | 0.1 | Draft |
| TB-TMPL-002 | Test Case Specification — Template | 0.1 | Draft |

Every document in this baseline is **Draft**. None has been through the review
recorded on TB-TMPL-001, because no such review has been held.

### 5.4 Specifications and Bench Descriptions

| Item | Purpose |
|---|---|
| `action.yml` | The bench-runner composite action this repository publishes |
| `.github/workflows/bench.yml` | Runs the specifications below through that action against the simulated bench |
| `.github/workflows/style.yml` | Runs CStyleCheck over `firmware/nordic_dongle` |
| `benches/simulated_bench.yaml` | The fully simulated bench |
| `benches/simulated/sensor/firmware_manifest.json` | Simulated sensor image, version 1.4.2 |
| `benches/simulated/dongle/firmware_manifest.json` | Simulated dongle image, version 1.1.0, protocol 1.1 |
| `specs/sensor_bringup.yaml` | The bring-up scenario QS-01 |
| `specs/sensor_commands.md` | The BLE command set, and the test of it |
| `specs/sensor_commands.yaml` | The suite that runs that document |

### 5.5 Build and Check Tools

| Tool | Version | Where pinned |
|---|---|---|
| Python (CI) | 3.10 | `.github/workflows/firmware.yml` |
| `nrfutil` | 6.1.7 | `.github/workflows/firmware.yml` — exact pin, see TB-ACQ4-001 §4.3 |
| GNU Arm Embedded toolchain | As pinned in the firmware workflow | `.github/workflows/firmware.yml` |
| `dermot-murphy/CStyleCheck` | `@v1.6.0` | `.github/workflows/style.yml` |
| C rule configuration | `.cstylecheck.yml` with `.cstylecheck-baseline.json` (113 baselined violations) | Repository root |
| `pytest` | As declared in the `test` extra | `pyproject.toml` |

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
| 1 | No system requirement is qualified against real instruments | TB-SYS5-001 §6 |
| 2 | Sixteen system integration cases are not performed | TB-SYS4-001 §5 |
| 3 | Bench-confirmation items remain open for the scope, probe, dongle, supply and S2-LP kit | TB-SYS5-001 §7 |
| 4 | No MISRA checker runs in CI; those rules rest on review | TB-STD-001 §7.1 |
| 5 | The firmware build sets no explicit `-std` and does not enable `-Wextra` | TB-STD-002 §7.1, §7.2 |
| 6 | The RS-232 multimeter (STK-18) is deferred; no requirements exist for it | TB-SYS2-104 |
| 7 | No document in this baseline has been reviewed | §5.3 |
| 8 | No CI workflow runs the Python suite; it is run before every commit. `firmware.yml` runs the firmware's Unity/CTest tests, `bench.yml` the specifications, `style.yml` the C standard check | TB-ANA-001 §6.1 |
| 9 | The C standard check is baselined at 113 existing violations and fails only on new ones | TB-ANA-001 §6.12 |

None of these is a defect against a stated requirement. They are the distance
between what TestBench is shown to do and what it will eventually be shown to
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
