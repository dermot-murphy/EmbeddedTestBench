<img src="../../assets/brand/svg/logos/embeddedtestbench-logo-compact.svg" alt="Embedded Test Bench" width="240">

# Software Version Description

*Automotive SPICE® PAM v4.0 | SUP.8 — Configuration Management*

---

## 1. Document Identification & Control

| Field | Value | Field | Value |
|---|---|---|---|
| **Document ID** | ETB-SVD-001 | **Version** | [latest, §2](#2-revision-history) |
| **Project** | Embedded Test Bench | **Date** | [latest, §2](#2-revision-history) |
| **Status** | [by location, ETB-SUP1-001 §6.3](EmbeddedTestBench_SUP1_Quality_Assurance_Plan.md#63-document-status) | **Classification** | Internal |
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
| 0.10 | 2026-11-17 | Claude | #325: revised for the release baseline `v0.03.0000`, a minor release of `develop` at a274967. §1 Version and Date link to the revision history (#210, held back from this document until now). §4 identifies the new tag and lists the changes since `v0.02.0002`; §5 brought up to date (package 0.03.0000, dongle firmware 1.8.0 and protocol 1.8, the PICO2 Test Board and S2-LP kit firmware, document versions, the Kepler plugin, workflows and pins); §6 records the tests on the release branch, CI on `develop`, and the regression run of Kepler's bench specifications on Kepler V11.03.0000 (2026-11-15 to 2026-11-16), the firmware this release is qualified against; §7 drops #179, #181 and the J-Link backend switch (#71), all fixed, restates the simulated Kepler limitation now that #122 is done, and adds the Kepler plugin interface still in transition (#238, #240, #243) and the instruments verified by unit tests only. |
| next | 2026-11-17 | Claude | #371: the Status cell links to the status rule, ETB-SUP1-001 §6.3. A document's status follows from where it is in the repository (Released, Agreed, In review, In work) and is not written in by hand. |

---

## 3. Purpose & Scope

### 3.1 Purpose

This document describes exactly what an Embedded Test Bench baseline contains, so
that the baseline can be rebuilt and a result produced by it can be attributed to
a known configuration.

### 3.2 Referenced Documents

| Document ID | Title | Version |
|---|---|---|
| ETB-SUP8-001 | Embedded Test Bench Configuration Management Plan | 0.21 |
| ETB-SUP9-001 | Embedded Test Bench Problem Resolution Management Plan | 0.5 |
| ETB-SYS5-001 | Embedded Test Bench System Qualification Test | 0.7 |
| ETB-SYS5-002 | Embedded Test Bench System Qualification Test Report | 1.4 |
| ETB-SWE4-002 | Embedded Test Bench Unit Verification Report | 1.87 |
| ETB-ACQ4-001 | Embedded Test Bench Supplier Monitoring Plan | 0.11 |
| ETB-PA2-001 | Embedded Test Bench Process Capability Records | 0.5 |

### 3.3 Scope

The software, firmware, documents and tools that make up the baseline described
in §4. Physical instruments are identified per run, in the run's own report,
not here.

---

## 4. Baseline Identification

| Field | Value |
|---|---|
| **Baseline** | Release baseline `v0.03.0000`, a minor release after `v0.02.0002` |
| **Tag** | `v0.03.0000`, annotated, on the merge commit of `release/v0.03.0000` into `main` (ETB-SUP8-001 §5.6) |
| **Revision** | The commit the tag points to; the tag is the identifier (`git rev-parse v0.03.0000^{commit}`) |
| **Repository** | `dermot-murphy/EmbeddedTestBench` (formerly `dermot-murphy/TestTools`) |
| **Prepared on** | Branch `release/v0.03.0000`, taken from `develop` at a274967 |
| **Date** | 2026-11-17 |
| **Issue** | #325 |
| **Previous baseline** | `v0.02.0002` (ETB-SVD-001 0.9, #275) |

The tag and this document together are the baseline (ETB-SUP8-001 §7). The
baseline is not edited after the tag is created. A correction is a new release
with its own tag and a new revision of this document.

It is a minor release: it adds instruments, runner features and a device plugin
interface, and nothing in it breaks a specification written for `v0.02.0002`.
Kepler (innovateuk-sensor) uses Embedded Test Bench releases from `main` only;
its re-pin to this release is Kepler's TX-1269. The legacy Kepler names
(`s2lp.kepler_frame`, `s2lp.kepler_samples`, `configs/s2lp_kepler_433_rx.regs`)
still load in this release, with a deprecation warning (#238). #240, which
removes them, is not in this release.

**Changes since `v0.02.0002`:**

| Area | Change | Issue / PR |
|---|---|---|
| Device plugins | Kepler's decoder, register file and viewer panel load by path through a plugin interface; the viewer's Kepler analyses moved behind it; the `rf_packet` record names its decoder | #238 / #304; #303 / #339; #340 / #345 |
| Kepler decoder | Each frame's layout is chosen by its type version; FFT2 type version 2; V10.00's 96-byte and V10.01.x's 99-byte TWF frames decode | #287 / #289; #255 / #288; #313 / #333; #335 / #346 |
| S2-LP | The interrupt is routed again after a defaults reset, so a receive after a transmit works; frames a stopping receive reports are kept, and `kepler_frame` takes `since_last`; only what re-arming needs is sent between two receives; frame measures (intervals, copies, census, field filters) | #179 / #278; #293 / #298; #299 / #307, #308 / #309; #243 / #312 |
| S2-LP kit firmware | The project's own firmware for the NUCLEO-L053R8 kit: it receives on the interrupt and queues frames on the board | #84 / #348 |
| Kepler specifications | The shipped Kepler specifications read V11.02's reply forms: a space before mV and mC, the `ecureset` and `alive-period` replies, and upper-case `RD VERSION` and `RD SHA`; the bench file gives `rtt` its GDB | #314 / #315 |
| Simulation | The simulated S2-LP kit receives the simulated Kepler sensor's frames | #122 / #311 |
| BLE dongle | Firmware 1.8.0, protocol 1.8: the dongle reports the DFU piece size and ATT MTU it uses. The link code is unchanged from 1.7.0 | #274 / #316 |
| J-Link | A `segger` backend (JLink.exe command files, RTT Logger) beside `gdb`; the core is halted on attach; a variable GDB places at address 0 is refused | #71 / #336, #337; #349 / #351; #352 / #353 |
| Runner | Text limits `one_of`, `matches` and `ignore_case`; saved bounds; a `compute` step; `poll_states` | #242 / #306 |
| New instruments | Serial capture (RD, WR and ROUTINE command lines); PicoScope 3000D MSO, with ETB-IF-002; Nordic PPK2 current profiler | #247 / #318; #200 / #331; #342 / #343 |
| PICO2 Test Board | The Pico 2 thermometer is renamed PICO2 Test Board, firmware V1.00.0000; red, yellow and green LEDs; a UDA1334A frequency generator | #330; #328 / #329; #202 / #326, #327 |
| TTi 1604 | Frequency with no signal, and ranging blanks | #181 / #317 |
| Transports | The TCP port of a `socket://` URL is kept whatever the host | #319 / #332 |
| Viewer | Click a test step to see the events recorded during it; a client that went away is logged as one line | #201 / #334; #294 / #296 |
| Documents | Version and Date are derived from each document's revision history, with a merge driver for the history rows; the home pages say what the product is for; every SWE.4 test group has a result and names its test files | #210 / #301, #302, #305 / #310; #195 / #347; #286 / #291, #292 / #297 |
| Docker | The bench tools investigated in a container, with a prototype, and the J-Link half of its test plan run from it (ETB-DOCK-001) | #70 / #338, #350; #349 / #354 |
| CI | A CI image that runs CI's Python legs locally with pinned libraries; Dependabot pip updates replaced by a weekly constraints refresh | #282 / #283; #284 / #285 |

The full list is the merge commits on `develop` between `v0.02.0002` and
a274967 (`git log --first-parent v0.02.0002..a274967`).

---

## 5. Contents

### 5.1 Software

| Item | Version | Notes |
|---|---|---|
| `benchtools` (Python package) | **0.03.0000** | `__version__` in `benchtools/__init__.py` and `version` in `pyproject.toml`; requires Python ≥ 3.8; no mandatory runtime dependencies |
| Optional extras | `spec` (PyYAML ≥ 6.0.3), `plot` (matplotlib ≥ 3.3), `visa` (pyvisa ≥ 1.11, pyvisa-py ≥ 0.5), `serial` (pyserial ≥ 3.5), `test` | A driver works on a bare Python install; extras add file formats, plots and transports |

> **Version as packaged.** Python packaging normalises versions under PEP 440,
> so `0.03.0000` is recorded in the built wheel's metadata as `0.3.0`: the wheel
> is `benchtools-0.3.0-py3-none-any.whl`, and `pip show benchtools` reports
> `0.3.0`. Both strings name the same version. The tag, `__version__` and every
> `--version` option give the project's form, `0.03.0000`. Checked on
> 2026-11-17 by building the wheel from `release/v0.03.0000`.
>
> Earlier revisions of this document gave the package as 4.0.0, a number carried
> over from before the project's version scheme was set. No release was ever
> made under it, so nothing is lost by renumbering.

### 5.2 Firmware

| Item | Version | Notes |
|---|---|---|
| Nordic dongle application | 1.8.0 | `firmware/nordic_dongle/include/firmware_version.h`; host protocol 1.8. `send_package` needs 1.7.0 or later on the dongle; 1.8.0 also reports the DFU piece size and ATT MTU (#274) |
| Dongle target | nRF52840, board PCA10059 | |
| Dongle platform | nRF5 SDK 17.1.0, S140 SoftDevice 7.2.0 | Vendor-supplied, not redistributed |
| PICO2 Test Board application | V1.00.0000 | `firmware/pico2_test_board/include/firmware_version.h`; versioned on its own scheme; renamed from the Pico 2 thermometer and reset to V1.00.0000 by #330 |
| Pico target and platform | Raspberry Pi Pico 2 (RP2350), Pico SDK 2.1.1 | `.github/workflows/firmware.yml` |
| S2-LP kit application | V1.00.0000 | `firmware/s2lp_kit/include/firmware_version.h`; NUCLEO-L053R8 (STM32L053R8, Cortex-M0+) with STEVAL-FKI433V2; no vendor SDK (#84) |
| Flash and RAM usage | Recorded by each CI build | ETB-SWE4-002 §4.6 |
| Dongle DFU package, Pico UF2, S2-LP kit image | Produced by the firmware workflow, kept 90 days | |

The Kepler sensor firmware used during qualification is not part of this
baseline. Its manifests are under `specs/qualification/firmware/`.

### 5.3 Documents

| Document ID | Title | Version | Status |
|---|---|---|---|
| ETB-SYS2-001 | System Requirements Specification | 0.10 | Draft |
| ETB-SYS3-001 | System Architecture | 0.8 | Draft |
| ETB-SYS4-001 | System Integration & Integration Test | 0.6 | Draft |
| ETB-SYS5-001 | System Qualification Test | 0.7 | Draft |
| ETB-SYS5-002 | System Qualification Test Report | 1.4 | Draft — for review |
| ETB-SWE1-001 | Software Requirements Specification | 1.70 | Draft |
| ETB-SWE2-001 | Software Architecture Description | 0.33 | Draft |
| ETB-SWE3-001 | Software Detailed Design | 1.90 | Draft |
| ETB-SWE3-002 | GPD-3303D Driver Design and Lessons Learned | 0.4 | Draft |
| ETB-SWE4-001 | Software Unit Verification Specification | 1.92 | Draft |
| ETB-SWE4-002 | Software Unit Verification Report | 1.87 | Draft |
| ETB-SWE5-001 | Software Integration & Integration Test | 0.5 | Draft |
| ETB-SWE6-001 | Software Qualification Test | 0.7 | Draft |
| ETB-IF-001 | GPD-3303D Remote Control Interface Specification | 0.4 | Draft |
| ETB-IF-002 | PicoScope 3000D Driver Interface and Dependencies | 0.1 | Draft |
| ETB-RTM-001 | Requirements Traceability Matrix | 1.83 | Draft |
| ETB-MAN3-001 | Project Management Plan | 0.5 | Draft |
| ETB-MAN5-001 | Risk Management Plan | 0.7 | Draft |
| ETB-SUP1-001 | Quality Assurance Plan | 0.5 | Draft |
| ETB-SUP8-001 | Configuration Management Plan | 0.21 | Draft |
| ETB-SUP9-001 | Problem Resolution Management Plan | 0.5 | Draft |
| ETB-SUP10-001 | Change Request Management Plan | 0.5 | Draft |
| ETB-ACQ4-001 | Supplier Monitoring Plan | 0.11 | Draft |
| ETB-SVD-001 | Software Version Description *(this document)* | 0.10 | Draft |
| ETB-PA2-001 | Process Capability Records — Level 2 | 0.5 | Draft |
| ETB-STD-001 | Industry C Coding Standards — Applicability | 0.6 | Draft |
| ETB-STD-002 | Embedded C Coding Standard | 0.7 | Draft |
| ETB-STY-001 | Embedded C Style Guide | 0.7 | Draft |
| ETB-ANA-001 | Repository Analysis Report | 0.6 | Draft |
| ETB-DEV-001 | Deviation Record — AI Authorship of Work Products | 0.5 | Draft |
| ETB-DEV-002 | Deviation Record — Reviewer Independence | 0.5 | Draft |
| ETB-TMPL-001 | Work Product Review Record — Template | 0.6 | Draft |
| ETB-TMPL-002 | Test Case Specification — Template | 0.5 | Draft |
| ETB-DOCK-001 | Bench Tools in a Container: Investigation and Recommendation | 0.6 | Draft |
| ETB-PICO-002 | PICO2 Test Board User Manual | 0.2 | Draft |

Every document in this baseline is **Draft**. Since #204, review and approval of
a change are given by the merge of its pull request (ETB-SUP8-001 §5.7), so each
document version in this table was merged into `develop` by, or on the
instruction of, the Reviewer and Approver. No document has yet been moved out
of Draft status.

### 5.4 Specifications and Bench Descriptions

| Item | Purpose |
|---|---|
| `action.yml` | The bench-runner composite action this repository publishes, used as `dermot-murphy/EmbeddedTestBench@v0.03.0000` |
| `.github/workflows/bench.yml` | Runs the simulated-bench specifications through that action |
| `.github/workflows/tests.yml` | Runs the Python suite with coverage on Python 3.8, 3.9 and 3.12, gated at 90% |
| `.github/workflows/lint.yml` | Runs pylint over `benchtools/`, `tests/` and `scripts/` against its baseline |
| `.github/workflows/style.yml` | Runs CStyleCheck over the firmware against its baseline |
| `.github/workflows/firmware.yml` | Builds and unit-tests the dongle, PICO2 Test Board and S2-LP kit firmware (path-filtered) |
| `scripts/lint.py` | The pylint runner and baseline comparison |
| `.github/workflows/wiki_publish.yml`, `.github/workflows/pages_publish.yml`, `scripts/publish_docs.py` | Generate and publish the wiki and the `gh-pages` home page from `main` (ETB-SUP8-001 §5.8) |
| `.github/dependabot.yml` | Weekly version updates, targeting `develop` |
| `.github/workflows/constraints_refresh.yml`, `constraints/` | The exact Python libraries CI installs, refreshed weekly (#284) |
| `.github/workflows/ci_image.yml` | Builds the CI image that runs CI's Python legs locally (#282) |
| `benches/simulated_bench.yaml`, `benches/simulated.yaml` | The fully simulated bench |
| `benches/bench_pc.yaml`, `benches/lab1.yaml` | The Windows bench PC as qualified on 2026-10-04, and the lab bench |
| `benches/simulated/sensor/firmware_manifest.json` | Simulated sensor image, version 1.4.2 |
| `benches/simulated/dongle/firmware_manifest.json` | Simulated dongle image, version 1.8.0, protocol 1.8 |
| `specs/*.yaml`, `specs/sensor_commands.md` | Bench specifications, including bring-up (QS-01) and the BLE command set |
| `specs/qualification/` | The hardware qualification scenarios run for ETB-SYS5-002 |
| `plugins/kepler/` | The Kepler device plugin: decoder, register files and viewer panel, loaded through the plugin interface (#238) |

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
| Arm GNU toolchain, Pico and S2-LP kit | 14.2.Rel1 | `.github/workflows/firmware.yml` |
| Pico SDK | 2.1.1 | `.github/workflows/firmware.yml` |
| `dermot-murphy/CStyleCheck` | `@v1.6.1` | `.github/workflows/style.yml` (#229) |
| C rule configuration | `.cstylecheck.yml` with `.cstylecheck-baseline.json` (107 baselined violations) | Repository root |
| Python rule configuration | `[tool.pylint]` in `pyproject.toml` with `.pylint-baseline.json` (436 baselined findings) | Repository root |
| `pytest`, `pytest-cov` | As declared in the `test` extra (`pytest-cov` ≥ 4.0); CI installs exact versions | `pyproject.toml`; `constraints/py3.8.txt`, `py3.9.txt`, `py3.12.txt` (#284) |
| `pylint` | **4.0.8** | `constraints/lint.txt`; exact pin, because its rule set decides what a green lint means |

---

## 6. Verification Status

| Measure | Value |
|---|---|
| Tests passing | **4 557**, none failing (`release/v0.03.0000`, locally on Windows, Python 3.14; CI on Python 3.8, 3.9 and 3.12 runs on the pull request into `main`) |
| Continuous integration on `develop` | `tests`, `lint`, `style` and `bench` green on a274967, the commit the release branch was taken from |
| Statement coverage | Gate 90%, checked by CI on the pull request |
| Requirements without a covering test | 0, enforced by `tests/test_traceability.py` |
| Firmware build and unit tests | Green in CI for the dongle, the PICO2 Test Board and the S2-LP kit; flash and RAM recorded |
| C coding-standard check | Green in CI against its baseline |
| Python lint | Green in CI against its baseline |
| System qualification on hardware | **44 of 64** system requirements qualified, 3 partially qualified, 10 not qualified, 2 not performed and 5 out of scope (ETB-SYS5-002 §7.1, run 2026-10-04). Not rerun for this release |
| Kepler regression run (#325, #239) | The bench PC with sensor 5C1712 on **Kepler V11.03.0000** (the V4X DEBUG image), 2026-11-15 to 2026-11-16: Kepler's TX-1266 automated set, from innovateuk-sensor b1276eba on Kepler's TX-1269 branch, 66 run folders, against the same set on `v0.02.0002`. 60 had the same verdict, 4 did better, and 2 did worse for reasons outside the bench: a sensor watchdog reset during SYNC, which did not happen again on a re-run (the re-run's own verdict is FAIL, for a battery reading below its limit and a case-order dependency, recorded in the qualification folder, not for SYNC), and a missing Kepler package, after which the case passed. The 13-hour soak passed. The RF logs show one unexpected sensor reset, that watchdog reset. This is the Kepler firmware this release is qualified against (`docs/aspice/qualification/2026-11-16/325_kepler_v11_03/`) |
| Hardware runs of changes since `v0.02.0002` | #293, #299 (S2-LP receive gaps, 2026-10-25, 2026-10-27); #181 (TTi 1604), #274 (DFU piece size and MTU) (2026-10-28); #335, #340 (V10 TWF decoding), #84 (S2-LP kit firmware and driver) (2026-11-14); #349, #352, #70 (J-Link) (2026-11-15). The folders are under `docs/aspice/qualification/`. The PICO2 Test Board firmware ran on the bench Pico 2 (ETB-SWE4-002 §13A) |

The release branch changes only the version, the usage examples, the document
version numbers and this document.

---

## 7. Known Problems and Limitations

| # | Limitation | Reference |
|---|---|---|
| 1 | #179 (S2-LP receive after a transmit) and #181 (TTi 1604 frequency and ohms) are fixed in this release, but QS-01b, QS-07 and QS-09 have not been rerun, so ETB-SYS2-046, -051 and -053 are still recorded as not qualified | #179, #181; ETB-SYS5-002 §7.1 |
| 2 | The J-Link fixes are confirmed on hardware, but QS-01b has not been rerun, so ETB-SYS2-004 and -031 are still recorded as not qualified | ETB-SYS5-002 §7.1, §11 |
| 3 | System qualification is incomplete: 20 of 64 requirements are not fully qualified. The features added since `v0.01.0000` are verified by unit tests and the hardware runs in §6, not by a qualification run | ETB-SYS5-002 §3.3, §7.1, §11 |
| 4 | The PicoScope 3000D MSO (#200), the Nordic PPK2 (#342) and the serial capture instrument (#247) are verified by unit tests against simulators only. None has been run against the real instrument | ETB-SWE4-002 §13C, §13D |
| 5 | The Kepler plugin interface is in transition. The plugin loads from this repository's `plugins/kepler`; loading it from an innovateuk-sensor checkout is not yet shown on the bench (#238). The legacy Kepler names still load, with a deprecation warning, until #240 removes them. Kepler's specifications do not yet use the frame measures of #243 | #238, #240, #243 |
| 6 | The Kepler regression run used one sensor, 5C1712, on one firmware version, V11.03.0000. Bench qualification against Kepler is recorded per release in §6, not against V11.00.0000 as #239 first proposed | #239, §6 |
| 7 | Qualification has not been reproduced by an independent engineer (QS-05) | ETB-SYS5-002 §11 |
| 8 | The system integration cases in ETB-SYS4-001 are recorded as not formally performed | ETB-SYS4-001 §5 |
| 9 | No document in this baseline has left Draft status | §5.3 |
| 10 | No MISRA checker runs in CI; those rules rest on review | ETB-STD-001 §7.1 |
| 11 | The dongle firmware build (`firmware/nordic_dongle/Makefile`) sets no explicit `-std` and does not enable `-Wextra`; only the separate compile check does | ETB-STD-002 §7.1, §7.2 |
| 12 | The Python lint check is baselined at 436 existing findings and fails only on new ones; `duplicate-code` is disabled because its output is not reproducible across machines | ETB-ANA-001 §6.13 |
| 13 | The C standard check is baselined at 107 existing violations and fails only on new ones | ETB-ANA-001 §6.12 |
| 14 | Python 3.8 is end-of-life upstream. It is tested because `pyproject.toml` declares it as the floor; when supporting it stops being tenable, the floor should be raised rather than the leg dropped | ETB-ANA-001 §6.1 |
| 15 | The simulated S2-LP kit receives the simulated Kepler sensor's frames (#122), but Kepler's specifications are written for the real bench and are not run on the simulated one | #119 |
| 16 | The DFU client has been run against two bootloaders on one sensor, 5C1712: Kepler V1.01.0000 (SDK 15.2) and V2.00.0000. On both, at a 30 ms interval with 20-byte pieces, the first data object of an image loses data unless the client waits after its create; the client finds the loss in a receipt and sends the image again with a 0.15 s pause, so each such transfer takes one retry. Why the data is lost is inferred (the flash page erase), not traced. A bootloader link that fails to establish (0x3E) is tried again (#275); hardware cannot force one, so that retry is shown by unit tests only. The client needs dongle firmware 1.7.0 or later; an older dongle refuses `dfucp` as an unknown command | #244, #271, #275; ETB-SWE4-002 §10.6 to §10.8 |

Items 1 and 2 are fixes waiting for their qualification scenarios to be rerun.
The other items are the distance between what Embedded Test Bench is shown to
do and what it will eventually be shown to do, recorded so that the distance is
visible.

---

## 8. Installation

From a clone, at the release:

```
git checkout v0.03.0000
pip install -e .[spec,serial,test]
pytest
```

Without cloning:

```
pip install "benchtools @ git+https://github.com/dermot-murphy/EmbeddedTestBench@v0.03.0000"
```

The firmware is built with `make` under `firmware/nordic_dongle` and with CMake
under `firmware/pico2_test_board`, and with `make` under
`firmware/s2lp_kit`, with the tool versions of §5.5.

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
