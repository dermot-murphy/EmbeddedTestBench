<img src="../../assets/brand/svg/logos/embeddedtestbench-logo-compact.svg" alt="Embedded Test Bench" width="240">

# Software Version Description

*Automotive SPICE® PAM v4.0 | SUP.8 — Configuration Management*

---

## 1. Document Identification & Control

| Field | Value | Field | Value |
|---|---|---|---|
| **Document ID** | ETB-SVD-001 | **Version** | 0.9 |
| **Project** | Embedded Test Bench | **Date** | 2026-10-23 |
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
| 0.6 | 2026-10-05 | Claude | #215: revised for the release baseline `v0.01.0001`. §4 identifies the new tag and lists the changes since `v0.01.0000`; §5 brought up to date (package 0.01.0001, document versions, publish workflows, action and runner pins); §6 brought up to the CI run on `develop` at f1eac09 and the J-Link fixes confirmed on hardware; §7 drops #177 and #178 (fixed) and adds the CStyleCheck pin and the Windows timing test. The brand logo (ETB-SUP8-001 §6.3) and the Review & Approval table that points to the merge (§5.7), both held back from the `v0.01.0000` baseline, are applied. |
| 0.7 | 2026-10-23 | Claude | #268: revised for the release baseline `v0.02.0000`, a minor release. §4 identifies the new tag and lists the changes since `v0.01.0001`; §5 brought up to date (package 0.02.0000, dongle firmware 1.7.0 and protocol 1.7, document versions, CStyleCheck v1.6.1, both baselines); §6 brought up to the CI run on `develop` at 7507bda and the dongle and J-Link changes confirmed on hardware; §7 drops #180, #214, the CStyleCheck hold and the first wiki publication (all resolved), restates the simulated Kepler limitation now that #121 is done, and adds the limits of the DFU client. |
| 0.8 | 2026-10-23 | Claude | #271: revised for the release baseline `v0.02.0001`, a hotfix. §4 identifies the new tag, branched from `main` at 213fe0a, and its one change; §5 brought up to date (package 0.02.0001, document versions); §6 records the tests on the hotfix branch and the DFU retry on hardware; §7 item 14 restated for the SDK 15.2 bootloader. |
| 0.9 | 2026-10-23 | Claude | #275: revised for the release baseline `v0.02.0002`, a hotfix. §4 identifies the new tag, branched from `main` at 677f681, and its one change; §5 brought up to date (package 0.02.0002, document versions); §6 records the tests on the hotfix branch and the bench run; §7 item 14 notes the bootloader link retry. |

---

## 3. Purpose & Scope

### 3.1 Purpose

This document describes exactly what an Embedded Test Bench baseline contains, so
that the baseline can be rebuilt and a result produced by it can be attributed to
a known configuration.

### 3.2 Referenced Documents

| Document ID | Title | Version |
|---|---|---|
| ETB-SUP8-001 | Embedded Test Bench Configuration Management Plan | 0.14 |
| ETB-SUP9-001 | Embedded Test Bench Problem Resolution Management Plan | 0.4 |
| ETB-SYS5-001 | Embedded Test Bench System Qualification Test | 0.6 |
| ETB-SYS5-002 | Embedded Test Bench System Qualification Test Report | 1.3 |
| ETB-SWE4-002 | Embedded Test Bench Unit Verification Report | 1.31 |
| ETB-ACQ4-001 | Embedded Test Bench Supplier Monitoring Plan | 0.7 |
| ETB-PA2-001 | Embedded Test Bench Process Capability Records | 0.4 |

### 3.3 Scope

The software, firmware, documents and tools that make up the baseline described
in §4. Physical instruments are identified per run, in the run's own report,
not here.

---

## 4. Baseline Identification

| Field | Value |
|---|---|
| **Baseline** | Release baseline `v0.02.0002`, a hotfix release after `v0.02.0001` |
| **Tag** | `v0.02.0002`, annotated, on the merge commit of `hotfix/v0.02.0002` into `main` (ETB-SUP8-001 §5.6) |
| **Revision** | The commit the tag points to; the tag is the identifier (`git rev-parse v0.02.0002^{commit}`) |
| **Repository** | `dermot-murphy/EmbeddedTestBench` (formerly `dermot-murphy/TestTools`) |
| **Prepared on** | Branch `hotfix/v0.02.0002`, taken from `main` at 677f681 (the `v0.02.0001` merge) |
| **Date** | 2026-10-23 |
| **Issue** | #275 |
| **Previous baseline** | `v0.02.0001` (ETB-SVD-001 0.8, #271) |

The tag and this document together are the baseline (ETB-SUP8-001 §7). The
baseline is not edited after the tag is created. A correction is a new release
with its own tag and a new revision of this document.

It is a hotfix, not a minor release, because it carries one fix to a released
feature and nothing else. Kepler (innovateuk-sensor TX-1184) uses Embedded Test
Bench releases from `main` only, and its field-upgrade test V10-F-01 errored on
`v0.02.0001` when both bootloader links in a run failed to establish.

**Changes since `v0.02.0001`:**

| Change | Issue / PR |
|---|---|
| BLE dongle DFU client: a bootloader link that fails to establish (HCI 0x3E) is tried again, as `open_link` tries a UART link (#180): up to `connect_attempts` (3), each failed attempt logged. Host only; dongle firmware unchanged at 1.7.0 | #275 |

**In `v0.02.0001` (#271):** the DFU client checks each Packet Receipt
Notification and sends an image again from its init packet when data is lost,
waiting after each data create.

---

## 5. Contents

### 5.1 Software

| Item | Version | Notes |
|---|---|---|
| `benchtools` (Python package) | **0.02.0002** | `__version__` in `benchtools/__init__.py` and `version` in `pyproject.toml`; requires Python ≥ 3.8; no mandatory runtime dependencies |
| Optional extras | `spec` (PyYAML ≥ 6.0.3), `plot` (matplotlib ≥ 3.3), `visa` (pyvisa ≥ 1.11, pyvisa-py ≥ 0.5), `serial` (pyserial ≥ 3.5), `test` | A driver works on a bare Python install; extras add file formats, plots and transports |

> **Version as packaged.** Python packaging normalises versions under PEP 440,
> so `0.02.0002` is recorded in the built wheel's metadata as `0.2.2`: the wheel
> is `benchtools-0.2.2-py3-none-any.whl`, and `pip show benchtools` reports
> `0.2.2`. Both strings name the same version. The tag, `__version__` and every
> `--version` option give the project's form, `0.02.0002`. Checked on
> 2026-10-23 by building the wheel from `hotfix/v0.02.0002`.
>
> Earlier revisions of this document gave the package as 4.0.0, a number carried
> over from before the project's version scheme was set. No release was ever
> made under it, so nothing is lost by renumbering.

### 5.2 Firmware

| Item | Version | Notes |
|---|---|---|
| Nordic dongle application | 1.7.0 | `firmware/nordic_dongle/include/firmware_version.h`; host protocol 1.7. `send_package` needs 1.7.0 on the dongle |
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
| ETB-SYS2-001 | System Requirements Specification | 0.6 | Draft |
| ETB-SYS3-001 | System Architecture | 0.5 | Draft |
| ETB-SYS4-001 | System Integration & Integration Test | 0.5 | Draft |
| ETB-SYS5-001 | System Qualification Test | 0.6 | Draft |
| ETB-SYS5-002 | System Qualification Test Report | 1.3 | Draft — for review |
| ETB-SWE1-001 | Software Requirements Specification | 1.32 | Draft |
| ETB-SWE2-001 | Software Architecture Description | 0.16 | Draft |
| ETB-SWE3-001 | Software Detailed Design | 1.34 | Draft |
| ETB-SWE3-002 | GPD-3303D Driver Design and Lessons Learned | 0.3 | Draft |
| ETB-SWE4-001 | Software Unit Verification Specification | 1.35 | Draft |
| ETB-SWE4-002 | Software Unit Verification Report | 1.31 | Draft |
| ETB-SWE5-001 | Software Integration & Integration Test | 0.4 | Draft |
| ETB-SWE6-001 | Software Qualification Test | 0.6 | Draft |
| ETB-IF-001 | GPD-3303D Remote Control Interface Specification | 0.3 | Draft |
| ETB-RTM-001 | Requirements Traceability Matrix | 1.34 | Draft |
| ETB-MAN3-001 | Project Management Plan | 0.4 | Draft |
| ETB-MAN5-001 | Risk Management Plan | 0.6 | Draft |
| ETB-SUP1-001 | Quality Assurance Plan | 0.4 | Draft |
| ETB-SUP8-001 | Configuration Management Plan | 0.14 | Draft |
| ETB-SUP9-001 | Problem Resolution Management Plan | 0.4 | Draft |
| ETB-SUP10-001 | Change Request Management Plan | 0.4 | Draft |
| ETB-ACQ4-001 | Supplier Monitoring Plan | 0.7 | Draft |
| ETB-SVD-001 | Software Version Description *(this document)* | 0.9 | Draft |
| ETB-PA2-001 | Process Capability Records — Level 2 | 0.4 | Draft |
| ETB-STD-001 | Industry C Coding Standards — Applicability | 0.5 | Draft |
| ETB-STD-002 | Embedded C Coding Standard | 0.6 | Draft |
| ETB-STY-001 | Embedded C Style Guide | 0.6 | Draft |
| ETB-ANA-001 | Repository Analysis Report | 0.5 | Draft |
| ETB-DEV-001 | Deviation Record — AI Authorship of Work Products | 0.4 | Draft |
| ETB-DEV-002 | Deviation Record — Reviewer Independence | 0.4 | Draft |
| ETB-TMPL-001 | Work Product Review Record — Template | 0.5 | Draft |
| ETB-TMPL-002 | Test Case Specification — Template | 0.4 | Draft |

Every document in this baseline is **Draft**. Since #204, review and approval of
a change are given by the merge of its pull request (ETB-SUP8-001 §5.7), so each
document version in this table was merged into `develop` by, or on the
instruction of, the Reviewer and Approver. No document has yet been moved out
of Draft status.

### 5.4 Specifications and Bench Descriptions

| Item | Purpose |
|---|---|
| `action.yml` | The bench-runner composite action this repository publishes, used as `dermot-murphy/EmbeddedTestBench@v0.02.0002` |
| `.github/workflows/bench.yml` | Runs the simulated-bench specifications through that action |
| `.github/workflows/tests.yml` | Runs the Python suite with coverage on Python 3.8, 3.9 and 3.12, gated at 90% |
| `.github/workflows/lint.yml` | Runs pylint over `benchtools/`, `tests/` and `scripts/` against its baseline |
| `.github/workflows/style.yml` | Runs CStyleCheck over the firmware against its baseline |
| `.github/workflows/firmware.yml` | Builds and unit-tests the dongle and Pico firmware (path-filtered) |
| `scripts/lint.py` | The pylint runner and baseline comparison |
| `.github/workflows/wiki_publish.yml`, `.github/workflows/pages_publish.yml`, `scripts/publish_docs.py` | Generate and publish the wiki and the `gh-pages` home page from `main` (ETB-SUP8-001 §5.8) |
| `.github/dependabot.yml` | Weekly version updates for GitHub Actions and pip, targeting `develop` |
| `benches/simulated_bench.yaml`, `benches/simulated.yaml` | The fully simulated bench |
| `benches/bench_pc.yaml`, `benches/lab1.yaml` | The Windows bench PC as qualified on 2026-10-04, and the lab bench |
| `benches/simulated/sensor/firmware_manifest.json` | Simulated sensor image, version 1.4.2 |
| `benches/simulated/dongle/firmware_manifest.json` | Simulated dongle image, version 1.7.0, protocol 1.7 |
| `specs/*.yaml`, `specs/sensor_commands.md` | Bench specifications, including bring-up (QS-01) and the BLE command set |
| `specs/qualification/` | The hardware qualification scenarios run for ETB-SYS5-002 |

### 5.5 Build and Check Tools

| Tool | Version | Where pinned |
|---|---|---|
| Python (CI, test matrix) | 3.8, 3.9, 3.12 | `.github/workflows/tests.yml`; 3.8 is the floor `pyproject.toml` declares |
| Python (CI, lint) | 3.12 | `.github/workflows/lint.yml` |
| Python (CI, dongle DFU packaging) | 3.10 | `.github/workflows/firmware.yml` |
| Python (CI, wiki and home page publishing) | 3.12 | `.github/workflows/wiki_publish.yml`, `pages_publish.yml` |
| GitHub Actions | `actions/checkout@v7`, `actions/setup-python@v7`, `actions/upload-artifact@v7`, `actions/cache@v6` | All workflows (#203) |
| Runner images | `ubuntu-24.04`; the Python 3.8 test leg on `ubuntu-22.04` | All workflows (#203) |
| `nrfutil` | 6.1.7 | `.github/workflows/firmware.yml`; exact pin, see ETB-ACQ4-001 §4.3 |
| GNU Arm Embedded toolchain, dongle | 10.3-2021.10 | `.github/workflows/firmware.yml` |
| Arm GNU toolchain, Pico | 14.2.Rel1 | `.github/workflows/firmware.yml` |
| Pico SDK | 2.1.1 | `.github/workflows/firmware.yml` |
| `dermot-murphy/CStyleCheck` | `@v1.6.1` | `.github/workflows/style.yml` (#229) |
| C rule configuration | `.cstylecheck.yml` with `.cstylecheck-baseline.json` (107 baselined violations) | Repository root |
| Python rule configuration | `[tool.pylint]` in `pyproject.toml` with `.pylint-baseline.json` (418 baselined findings) | Repository root |
| `pytest`, `pytest-cov` | As declared in the `test` extra (`pytest-cov` ≥ 4.0) | `pyproject.toml` |
| `pylint` | **4.0.8** | `.github/workflows/lint.yml`; exact pin, because its rule set decides what a green lint means |

---

## 6. Verification Status

| Measure | Value |
|---|---|
| Tests passing | **3 320**, none failing (`hotfix/v0.02.0002`, locally on Windows, Python 3.14; CI on Python 3.8, 3.9 and 3.12 runs on the pull request into `main`) |
| Statement coverage | Gate 90%, checked by CI on the pull request; 95% at `v0.02.0000` |
| Requirements without a covering test | 0, enforced by `tests/test_traceability.py` |
| Firmware build and unit tests | Green in CI; flash and RAM recorded |
| C coding-standard check | Green in CI against its baseline |
| Python lint | Green in CI against its baseline |
| System qualification on hardware | **44 of 64** system requirements qualified, 3 partially qualified, 10 not qualified, 2 not performed and 5 out of scope (ETB-SYS5-002 §7.1, run 2026-10-04). Not rerun for this release |
| Dongle changes on hardware | Dongle on COM10 (PCA10059) with sensor 5C1712. #251: the fault was reproduced, and 10 of 10 driver checks passed on the fixed image (2026-10-22); the #180 retry was exercised in the same runs. #241: an active scan read the full name and manufacturer ID 0x0F55. #244: a V4X application package was accepted (298 520 bytes in 108.8 s), a V5 package was refused with HwVersionFailure, and the sensor was restored from its backup (2026-10-23; ETB-SWE4-002 §10.6) |
| J-Link changes on hardware | Probe on sensor 5C1712 (2026-10-23). #259: the reported `monitor reset` error was reproduced on `develop` and was gone with the fix. #253: the GDB hang was reproduced in 3 runs of 4; with the fix, 3 of 3 flashed and verified. #264: DEBUG, then RELEASE, then the normal image through `restore`, with the 784-byte UICR page identical at the end. #254 is covered by unit tests only |
| DFU retry on hardware (#271) | Dongle on COM10 (firmware 1.7.0) with sensor 5C1712 on Kepler V10.00.0000 and bootloader V1.01.0000 (SDK 15.2), 2026-10-23. On `v0.02.0000` the SoftDevice and bootloader package failed (4076 of 4096 bytes). With the fix, Kepler's V10-F-01 passed, 3 of 3, with `scan_seconds: 30.0` on its second package: each package lost data once and succeeded on retry 1 (178 510 bytes in 53.6 s; 299 136 bytes in 111.6 s), and a V5 package was refused with HwVersionFailure (ETB-SWE4-002 §10.7) |
| Bootloader link retry on hardware (#275) | The same bench, 2026-10-23, `benchtools` 0.02.0002. Kepler's V10-F-01 passed, 3 of 3. No bootloader link failed to establish in that run, so it is a regression run; the retry is verified by unit tests (ETB-SWE4-002 §10.8) |

The hotfix branch changes only how the DFU client of `v0.02.0001` opens a
bootloader's link, its tests and documents, the version and the usage examples.

---

## 7. Known Problems and Limitations

| # | Limitation | Reference |
|---|---|---|
| 1 | S2-LP: receive refused after a transmit in the same session (Major) | #179; ETB-SYS2-046 not qualified |
| 2 | TTi 1604: frequency mode not recognised, and the meter is lost afterwards; an open input on ohms is not reported as overrange (Major). DC volts are qualified; the other functions are not | #181; ETB-SYS2-051, -053 not qualified |
| 3 | The J-Link fixes are confirmed on hardware, but QS-01b has not been rerun, so ETB-SYS2-004 and -031 are still recorded as not qualified | ETB-SYS5-002 §7.1, §11 |
| 4 | System qualification is incomplete: 20 of 64 requirements are not fully qualified. The oscilloscope and the SHT30 measurement were out of scope, because they are not yet live on the bench. The features added in this release are verified by unit tests and the hardware runs in §6, not by a qualification run | ETB-SYS5-002 §3.3, §7.1, §11 |
| 5 | Qualification has not been reproduced by an independent engineer (QS-05) | ETB-SYS5-002 §11 |
| 6 | The system integration cases in ETB-SYS4-001 are recorded as not formally performed | ETB-SYS4-001 §5 |
| 7 | No document in this baseline has left Draft status | §5.3 |
| 8 | No MISRA checker runs in CI; those rules rest on review | ETB-STD-001 §7.1 |
| 9 | The dongle firmware build (`firmware/nordic_dongle/Makefile`) sets no explicit `-std` and does not enable `-Wextra`; only the separate compile check does | ETB-STD-002 §7.1, §7.2 |
| 10 | The Python lint check is baselined at 418 existing findings and fails only on new ones; `duplicate-code` is disabled because its output is not reproducible across machines | ETB-ANA-001 §6.13 |
| 11 | The C standard check is baselined at 107 existing violations and fails only on new ones | ETB-ANA-001 §6.12 |
| 12 | Python 3.8 is end-of-life upstream. It is tested because `pyproject.toml` declares it as the floor; when supporting it stops being tenable, the floor should be raised rather than the leg dropped | ETB-ANA-001 §6.1 |
| 13 | The Kepler specifications cannot all run on the simulated bench. The simulated Kepler sensor exists (#121), but the simulated S2-LP kit transmits no Kepler frames | #119, #122 |
| 14 | The DFU client has been run against two bootloaders on one sensor, 5C1712: Kepler V1.01.0000 (SDK 15.2) and V2.00.0000. On both, at a 30 ms interval with 20-byte pieces, the first data object of an image loses data unless the client waits after its create; the client finds the loss in a receipt and sends the image again with a 0.15 s pause, so each such transfer takes one retry. Why the data is lost is inferred (the flash page erase), not traced. A bootloader link that fails to establish (0x3E) is tried again, as a UART link is (#275); hardware cannot force one, so that retry is shown by unit tests only. The client needs dongle firmware 1.7.0; an older dongle refuses `dfucp` as an unknown command | #244, #271, #275; ETB-SWE4-002 §10.6 to §10.8 |
| 15 | The J-Link driver has no configuration switch between the GDB backend and the local SEGGER tools | #71 |

Items 1 and 2 are open defects against stated requirements. #179 and #181 block
requirements that ETB-SYS5-002 records as not qualified; once they are fixed,
QS-01b, QS-07 and QS-09 are rerun to close those requirements. The other items
are the distance between what Embedded Test Bench is shown to do and what it will
eventually be shown to do, recorded so that the distance is visible.

---

## 8. Installation

From a clone, at the release:

```
git checkout v0.02.0002
pip install -e .[spec,serial,test]
pytest
```

Without cloning:

```
pip install "benchtools @ git+https://github.com/dermot-murphy/EmbeddedTestBench@v0.02.0002"
```

The firmware is built with `make` under `firmware/nordic_dongle` and with CMake
under `firmware/pico_sht30`, with the tool versions of §5.5.

---

## 9. Review & Approval

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
