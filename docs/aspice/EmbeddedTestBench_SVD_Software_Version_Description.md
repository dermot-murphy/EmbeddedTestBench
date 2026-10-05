# Software Version Description

*Automotive SPICE® PAM v4.0 | SUP.8 — Configuration Management*

---

## 1. Document Identification & Control

| Field | Value | Field | Value |
|---|---|---|---|
| **Document ID** | ETB-SVD-001 | **Version** | 0.5 |
| **Project** | Embedded Test Bench | **Date** | 2026-10-05 |
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
| 0.5 | 2026-10-05 | Claude | #188: rewritten for the first release, `v0.01.0000`. §4 identifies the release baseline and its tag; §5 restated for the current software, firmware, documents, specifications and tools; §6 brought up to the CI run on `develop` at cddb106 and the hardware qualification in ETB-SYS5-002; §7 lists the open defects #177 to #181 and drops limitations that no longer hold. The package version note in §5.1 is replaced: the package is renumbered to the project's version scheme. |

---

## 3. Purpose & Scope

### 3.1 Purpose

This document describes exactly what an Embedded Test Bench baseline contains, so
that the baseline can be rebuilt and a result produced by it can be attributed to
a known configuration.

### 3.2 Referenced Documents

| Document ID | Title | Version |
|---|---|---|
| ETB-SUP8-001 | Embedded Test Bench Configuration Management Plan | 0.9 |
| ETB-SUP9-001 | Embedded Test Bench Problem Resolution Management Plan | 0.2 |
| ETB-SYS5-001 | Embedded Test Bench System Qualification Test | 0.4 |
| ETB-SYS5-002 | Embedded Test Bench System Qualification Test Report | 1.1 |
| ETB-SWE4-002 | Embedded Test Bench Unit Verification Report | 1.20 |
| ETB-ACQ4-001 | Embedded Test Bench Supplier Monitoring Plan | 0.2 |
| ETB-PA2-001 | Embedded Test Bench Process Capability Records | 0.2 |

### 3.3 Scope

The software, firmware, documents and tools that make up the baseline described
in §4. Physical instruments are identified per run, in the run's own report,
not here.

---

## 4. Baseline Identification

| Field | Value |
|---|---|
| **Baseline** | Release baseline `v0.01.0000`, the first release of Embedded Test Bench |
| **Tag** | `v0.01.0000`, annotated, on the merge commit of `release/v0.01.0000` into `main` (ETB-SUP8-001 §5.6) |
| **Revision** | The commit the tag points to; the tag is the identifier (`git rev-parse v0.01.0000^{commit}`) |
| **Repository** | `dermot-murphy/EmbeddedTestBench` (formerly `dermot-murphy/TestTools`) |
| **Prepared on** | Branch `release/v0.01.0000`, taken from `develop` at cddb106 |
| **Date** | 2026-10-05 |
| **Issue** | #188 |

The tag and this document together are the baseline (ETB-SUP8-001 §7). The
baseline is not edited after the tag is created. A correction is a new release
with its own tag and a new revision of this document.

---

## 5. Contents

### 5.1 Software

| Item | Version | Notes |
|---|---|---|
| `benchtools` (Python package) | **0.01.0000** | `__version__` in `benchtools/__init__.py` and `version` in `pyproject.toml`; requires Python ≥ 3.8; no mandatory runtime dependencies |
| Optional extras | `spec` (PyYAML ≥ 5.1), `plot` (matplotlib ≥ 3.3), `visa` (pyvisa ≥ 1.11, pyvisa-py ≥ 0.5), `serial` (pyserial ≥ 3.4), `test` | A driver works on a bare Python install; extras add file formats, plots and transports |

> **Version as packaged.** Python packaging normalises versions under PEP 440,
> so `0.01.0000` is recorded in the built wheel's metadata as `0.1.0`: the wheel
> is `benchtools-0.1.0-py3-none-any.whl`, and `pip show benchtools` reports
> `0.1.0`. Both strings name the same version. The tag, `__version__` and every
> `--version` option give the project's form, `0.01.0000`. Checked on
> 2026-10-05 by building the wheel from `release/v0.01.0000`.
>
> Earlier revisions of this document gave the package as 4.0.0, a number carried
> over from before the project's version scheme was set. No release was ever
> made under it, so nothing is lost by renumbering.

### 5.2 Firmware

| Item | Version | Notes |
|---|---|---|
| Nordic dongle application | 1.4.0 | `firmware/nordic_dongle/include/firmware_version.h`; host protocol 1.4 |
| Dongle target | nRF52840, board PCA10059 | |
| Dongle platform | nRF5 SDK 17.1.0, S140 SoftDevice 7.2.0 | Vendor-supplied, not redistributed |
| Pico thermometer application | V1.00.0000 | `firmware/pico_sht30/include/firmware_version.h`; versioned on its own scheme |
| Pico target and platform | Raspberry Pi Pico 2 (RP2350), Pico SDK 2.1.1 | `.github/workflows/firmware.yml` |
| Flash and RAM usage | Recorded by each CI build | ETB-SWE4-002 §4.6 |
| Dongle DFU package, Pico UF2 | Produced by the firmware workflow | |

The Kepler sensor firmware used during qualification is not part of this
baseline. Its manifests are under `specs/qualification/firmware/`.

### 5.3 Documents

| Document ID | Title | Version | Status |
|---|---|---|---|
| ETB-SYS2-001 | System Requirements Specification | 0.4 | Draft |
| ETB-SYS3-001 | System Architecture | 0.3 | Draft |
| ETB-SYS4-001 | System Integration & Integration Test | 0.3 | Draft |
| ETB-SYS5-001 | System Qualification Test | 0.4 | Draft |
| ETB-SYS5-002 | System Qualification Test Report | 1.1 | Draft — for review |
| ETB-SWE1-001 | Software Requirements Specification | 1.23 | Draft |
| ETB-SWE2-001 | Software Architecture Description | 0.13 | Draft |
| ETB-SWE3-001 | Software Detailed Design | 1.19 | Draft |
| ETB-SWE3-002 | GPD-3303D Driver Design and Lessons Learned | 0.2 | Draft |
| ETB-SWE4-001 | Software Unit Verification Specification | 1.22 | Draft |
| ETB-SWE4-002 | Software Unit Verification Report | 1.20 | Draft |
| ETB-SWE5-001 | Software Integration & Integration Test | 0.2 | Draft |
| ETB-SWE6-001 | Software Qualification Test | 0.4 | Draft |
| ETB-IF-001 | GPD-3303D Remote Control Interface Specification | 0.2 | Draft |
| ETB-RTM-001 | Requirements Traceability Matrix | 1.22 | Draft |
| ETB-MAN3-001 | Project Management Plan | 0.2 | Draft |
| ETB-MAN5-001 | Risk Management Plan | 0.3 | Draft |
| ETB-SUP1-001 | Quality Assurance Plan | 0.2 | Draft |
| ETB-SUP8-001 | Configuration Management Plan | 0.9 | Draft |
| ETB-SUP9-001 | Problem Resolution Management Plan | 0.2 | Draft |
| ETB-SUP10-001 | Change Request Management Plan | 0.2 | Draft |
| ETB-ACQ4-001 | Supplier Monitoring Plan | 0.2 | Draft |
| ETB-SVD-001 | Software Version Description *(this document)* | 0.5 | Draft |
| ETB-PA2-001 | Process Capability Records — Level 2 | 0.2 | Draft |
| ETB-STD-001 | Industry C Coding Standards — Applicability | 0.2 | Draft |
| ETB-STD-002 | Embedded C Coding Standard | 0.4 | Draft |
| ETB-STY-001 | Embedded C Style Guide | 0.4 | Draft |
| ETB-ANA-001 | Repository Analysis Report | 0.2 | Draft |
| ETB-DEV-001 | Deviation Record — AI Authorship of Work Products | 0.2 | Draft |
| ETB-DEV-002 | Deviation Record — Reviewer Independence | 0.2 | Draft |
| ETB-TMPL-001 | Work Product Review Record — Template | 0.3 | Draft |
| ETB-TMPL-002 | Test Case Specification — Template | 0.2 | Draft |

Every document in this baseline is **Draft**. None has been through the review
recorded on ETB-TMPL-001, because no such review has been held. The release is
therefore a configuration baseline, not an approved one.

### 5.4 Specifications and Bench Descriptions

| Item | Purpose |
|---|---|
| `action.yml` | The bench-runner composite action this repository publishes, used as `dermot-murphy/EmbeddedTestBench@v0.01.0000` |
| `.github/workflows/bench.yml` | Runs the simulated-bench specifications through that action |
| `.github/workflows/tests.yml` | Runs the Python suite with coverage on Python 3.8, 3.9 and 3.12, gated at 90% |
| `.github/workflows/lint.yml` | Runs pylint over `benchtools/`, `tests/` and `scripts/` against its baseline |
| `.github/workflows/style.yml` | Runs CStyleCheck over the firmware against its baseline |
| `.github/workflows/firmware.yml` | Builds and unit-tests the dongle and Pico firmware (path-filtered) |
| `scripts/lint.py` | The pylint runner and baseline comparison |
| `benches/simulated_bench.yaml`, `benches/simulated.yaml` | The fully simulated bench |
| `benches/bench_pc.yaml`, `benches/lab1.yaml` | The Windows bench PC as qualified on 2026-10-04, and the lab bench |
| `benches/simulated/sensor/firmware_manifest.json` | Simulated sensor image, version 1.4.2 |
| `benches/simulated/dongle/firmware_manifest.json` | Simulated dongle image, version 1.4.0, protocol 1.4 |
| `specs/*.yaml`, `specs/sensor_commands.md` | Bench specifications, including bring-up (QS-01) and the BLE command set |
| `specs/qualification/` | The hardware qualification scenarios run for ETB-SYS5-002 |

### 5.5 Build and Check Tools

| Tool | Version | Where pinned |
|---|---|---|
| Python (CI, test matrix) | 3.8, 3.9, 3.12 | `.github/workflows/tests.yml`; 3.8 is the floor `pyproject.toml` declares |
| Python (CI, lint) | 3.12 | `.github/workflows/lint.yml` |
| Python (CI, dongle DFU packaging) | 3.10 | `.github/workflows/firmware.yml` |
| `nrfutil` | 6.1.7 | `.github/workflows/firmware.yml`; exact pin, see ETB-ACQ4-001 §4.3 |
| GNU Arm Embedded toolchain, dongle | 10.3-2021.10 | `.github/workflows/firmware.yml` |
| Arm GNU toolchain, Pico | 14.2.Rel1 | `.github/workflows/firmware.yml` |
| Pico SDK | 2.1.1 | `.github/workflows/firmware.yml` |
| `dermot-murphy/CStyleCheck` | `@v1.5.1` | `.github/workflows/style.yml` |
| C rule configuration | `.cstylecheck.yml` with `.cstylecheck-baseline.json` (110 baselined violations) | Repository root |
| Python rule configuration | `[tool.pylint]` in `pyproject.toml` with `.pylint-baseline.json` (436 baselined findings) | Repository root |
| `pytest`, `pytest-cov` | As declared in the `test` extra (`pytest-cov` ≥ 4.0) | `pyproject.toml` |
| `pylint` | **4.0.8** | `.github/workflows/lint.yml`; exact pin, because its rule set decides what a green lint means |

---

## 6. Verification Status

| Measure | Value |
|---|---|
| Tests passing | **3 129**, none failing, on Python 3.8, 3.9 and 3.12 (CI, `develop` at cddb106) |
| Statement coverage | 95% (94.98% to 95.06% across the three Python versions; gate 90%) |
| Requirements without a covering test | 0, enforced by `tests/test_traceability.py` |
| Firmware build and unit tests | Green in CI; flash and RAM recorded |
| C coding-standard check | Green in CI against its baseline |
| Python lint | Green in CI against its baseline |
| System qualification on hardware | **44 of 64** system requirements qualified, 3 partially qualified, 10 not qualified, 2 not performed and 5 out of scope (ETB-SYS5-002 §7.1, run 2026-10-04) |

The release branch adds no functional change to cddb106. It changes only the
version, the usage examples and documents, and its own CI run checks that.

---

## 7. Known Problems and Limitations

| # | Limitation | Reference |
|---|---|---|
| 1 | J-Link: `reset(halt=False)` leaves the target halted on a real probe (Major) | #177; ETB-SYS2-031 not qualified |
| 2 | J-Link: registers read just after `reset(halt=True)` are stale, PC reads 0 (Major) | #178; ETB-SYS2-004, -031 not qualified |
| 3 | S2-LP: receive refused after a transmit in the same session (Major) | #179; ETB-SYS2-046 not qualified |
| 4 | BLE dongle: `open_link` makes a single attempt and does not retry a link that fails to establish (0x3E) | #180 |
| 5 | TTi 1604: frequency mode not recognised, and the meter is lost afterwards; an open input on ohms is not reported as overrange (Major). DC volts are qualified; the other functions are not | #181; ETB-SYS2-051, -053 not qualified |
| 6 | System qualification is incomplete: 20 of 64 requirements are not fully qualified. The oscilloscope and the SHT30 measurement were out of scope, because they are not yet live on the bench | ETB-SYS5-002 §3.3, §7.1, §11 |
| 7 | Qualification has not been reproduced by an independent engineer (QS-05) | ETB-SYS5-002 §11 |
| 8 | The system integration cases in ETB-SYS4-001 are recorded as not formally performed | ETB-SYS4-001 §5 |
| 9 | No document in this baseline has been reviewed | §5.3 |
| 10 | No MISRA checker runs in CI; those rules rest on review | ETB-STD-001 §7.1 |
| 11 | The dongle firmware build (`firmware/nordic_dongle/Makefile`) sets no explicit `-std` and does not enable `-Wextra`; only the separate compile check does | ETB-STD-002 §7.1, §7.2 |
| 12 | The Python lint check is baselined at 436 existing findings and fails only on new ones; `duplicate-code` is disabled because its output is not reproducible across machines | ETB-ANA-001 §6.13 |
| 13 | The C standard check is baselined at 110 existing violations and fails only on new ones | ETB-ANA-001 §6.12 |
| 14 | Python 3.8 is end-of-life upstream. It is tested because `pyproject.toml` declares it as the floor; when supporting it stops being tenable, the floor should be raised rather than the leg dropped | ETB-ANA-001 §6.1 |
| 15 | The Kepler specifications cannot run on the simulated bench: there is no simulated Kepler sensor and no `rtt` instrument | #119, #121, #122 |

Items 1 to 5 are open defects against stated requirements, and four of them
(#177, #178, #179, #181) block requirements that ETB-SYS5-002 records as not
qualified. Once those four are fixed, QS-01b, QS-07 and QS-09 are rerun to close
the requirements. The other items are the distance between what Embedded Test
Bench is shown to do and what it will eventually be shown to do, recorded so
that the distance is visible.

---

## 8. Installation

From a clone, at the release:

```
git checkout v0.01.0000
pip install -e .[spec,serial,test]
pytest
```

Without cloning:

```
pip install "benchtools @ git+https://github.com/dermot-murphy/EmbeddedTestBench@v0.01.0000"
```

The firmware is built with `make` under `firmware/nordic_dongle` and with CMake
under `firmware/pico_sht30`, with the tool versions of §5.5.

---

## 9. Review & Approval

| Role | Name | Signature / Electronic Approval | Date |
|---|---|---|---|
| Author | Claude | Approved | 2026-10-05 |
| Reviewer | Dermot Murphy | — | *pending* |
| Approver | Dermot Murphy | — | *pending* |
