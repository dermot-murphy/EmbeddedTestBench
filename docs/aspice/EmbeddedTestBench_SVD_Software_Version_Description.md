<img src="../../assets/brand/svg/logos/embeddedtestbench-logo-compact.svg" alt="Embedded Test Bench" width="240">

# Software Version Description

*Automotive SPICE® PAM v4.0 | SUP.8 — Configuration Management*

---

## 1. Document Identification & Control

| Field | Value | Field | Value |
|---|---|---|---|
| **Document ID** | ETB-SVD-001 | **Version** | 0.6 |
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
| 0.6 | 2026-10-05 | Claude | #215: revised for the release baseline `v0.01.0001`. §4 identifies the new tag and lists the changes since `v0.01.0000`; §5 brought up to date (package 0.01.0001, document versions, publish workflows, action and runner pins); §6 brought up to the CI run on `develop` at f1eac09 and the J-Link fixes confirmed on hardware; §7 drops #177 and #178 (fixed) and adds the CStyleCheck pin and the Windows timing test. The brand logo (ETB-SUP8-001 §6.3) and the Review & Approval table that points to the merge (§5.7), both held back from the `v0.01.0000` baseline, are applied. |

---

## 3. Purpose & Scope

### 3.1 Purpose

This document describes exactly what an Embedded Test Bench baseline contains, so
that the baseline can be rebuilt and a result produced by it can be attributed to
a known configuration.

### 3.2 Referenced Documents

| Document ID | Title | Version |
|---|---|---|
| ETB-SUP8-001 | Embedded Test Bench Configuration Management Plan | 0.13 |
| ETB-SUP9-001 | Embedded Test Bench Problem Resolution Management Plan | 0.4 |
| ETB-SYS5-001 | Embedded Test Bench System Qualification Test | 0.6 |
| ETB-SYS5-002 | Embedded Test Bench System Qualification Test Report | 1.3 |
| ETB-SWE4-002 | Embedded Test Bench Unit Verification Report | 1.24 |
| ETB-ACQ4-001 | Embedded Test Bench Supplier Monitoring Plan | 0.5 |
| ETB-PA2-001 | Embedded Test Bench Process Capability Records | 0.4 |

### 3.3 Scope

The software, firmware, documents and tools that make up the baseline described
in §4. Physical instruments are identified per run, in the run's own report,
not here.

---

## 4. Baseline Identification

| Field | Value |
|---|---|
| **Baseline** | Release baseline `v0.01.0001`, a patch release after `v0.01.0000` |
| **Tag** | `v0.01.0001`, annotated, on the merge commit of `release/v0.01.0001` into `main` (ETB-SUP8-001 §5.6) |
| **Revision** | The commit the tag points to; the tag is the identifier (`git rev-parse v0.01.0001^{commit}`) |
| **Repository** | `dermot-murphy/EmbeddedTestBench` (formerly `dermot-murphy/TestTools`) |
| **Prepared on** | Branch `release/v0.01.0001`, taken from `develop` at f1eac09 |
| **Date** | 2026-10-05 |
| **Issue** | #215 |
| **Previous baseline** | `v0.01.0000` (ETB-SVD-001 0.5, #188) |

The tag and this document together are the baseline (ETB-SUP8-001 §7). The
baseline is not edited after the tag is created. A correction is a new release
with its own tag and a new revision of this document.

**Changes since `v0.01.0000`:**

| Change | Issue / PR |
|---|---|
| J-Link: `reset(halt=False)` now resumes the core; it was left halted | #177 / #212 |
| J-Link: GDB's register cache is flushed after every reset, so the first register read after a reset is the core's real state | #178 / #213 |
| Wiki and home page generated from `main` by workflow (`scripts/publish_docs.py`, `wiki_publish.yml`, `pages_publish.yml`) | #184 / #211 |
| Brand logo and banners in the README, the controlled documents, the wiki and the home page | #194 / #209 |
| User manual, `docs/User_Manual.md`, with a section for Claude Code sessions | #196 / #207 |
| Review and approval recorded as the merge of the pull request | #204 / #208 |
| GitHub Actions at current majors, runners pinned, Dependabot; CStyleCheck held at v1.5.1 | #203 / #206 |
| Where the Kepler bench test setup lives | #199 / #205 |
| On the release branch: the two publish workflows brought to the #203 action pins and `ubuntu-24.04` | #215 |

---

## 5. Contents

### 5.1 Software

| Item | Version | Notes |
|---|---|---|
| `benchtools` (Python package) | **0.01.0001** | `__version__` in `benchtools/__init__.py` and `version` in `pyproject.toml`; requires Python ≥ 3.8; no mandatory runtime dependencies |
| Optional extras | `spec` (PyYAML ≥ 5.1), `plot` (matplotlib ≥ 3.3), `visa` (pyvisa ≥ 1.11, pyvisa-py ≥ 0.5), `serial` (pyserial ≥ 3.4), `test` | A driver works on a bare Python install; extras add file formats, plots and transports |

> **Version as packaged.** Python packaging normalises versions under PEP 440,
> so `0.01.0001` is recorded in the built wheel's metadata as `0.1.1`: the wheel
> is `benchtools-0.1.1-py3-none-any.whl`, and `pip show benchtools` reports
> `0.1.1`. Both strings name the same version. The tag, `__version__` and every
> `--version` option give the project's form, `0.01.0000`. Checked on
> 2026-10-05 by building the wheel from `release/v0.01.0001`.
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
| ETB-SYS2-001 | System Requirements Specification | 0.6 | Draft |
| ETB-SYS3-001 | System Architecture | 0.5 | Draft |
| ETB-SYS4-001 | System Integration & Integration Test | 0.5 | Draft |
| ETB-SYS5-001 | System Qualification Test | 0.6 | Draft |
| ETB-SYS5-002 | System Qualification Test Report | 1.3 | Draft — for review |
| ETB-SWE1-001 | Software Requirements Specification | 1.25 | Draft |
| ETB-SWE2-001 | Software Architecture Description | 0.15 | Draft |
| ETB-SWE3-001 | Software Detailed Design | 1.23 | Draft |
| ETB-SWE3-002 | GPD-3303D Driver Design and Lessons Learned | 0.3 | Draft |
| ETB-SWE4-001 | Software Unit Verification Specification | 1.28 | Draft |
| ETB-SWE4-002 | Software Unit Verification Report | 1.24 | Draft |
| ETB-SWE5-001 | Software Integration & Integration Test | 0.4 | Draft |
| ETB-SWE6-001 | Software Qualification Test | 0.6 | Draft |
| ETB-IF-001 | GPD-3303D Remote Control Interface Specification | 0.3 | Draft |
| ETB-RTM-001 | Requirements Traceability Matrix | 1.26 | Draft |
| ETB-MAN3-001 | Project Management Plan | 0.4 | Draft |
| ETB-MAN5-001 | Risk Management Plan | 0.5 | Draft |
| ETB-SUP1-001 | Quality Assurance Plan | 0.4 | Draft |
| ETB-SUP8-001 | Configuration Management Plan | 0.13 | Draft |
| ETB-SUP9-001 | Problem Resolution Management Plan | 0.4 | Draft |
| ETB-SUP10-001 | Change Request Management Plan | 0.4 | Draft |
| ETB-ACQ4-001 | Supplier Monitoring Plan | 0.5 | Draft |
| ETB-SVD-001 | Software Version Description *(this document)* | 0.6 | Draft |
| ETB-PA2-001 | Process Capability Records — Level 2 | 0.4 | Draft |
| ETB-STD-001 | Industry C Coding Standards — Applicability | 0.4 | Draft |
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
| `action.yml` | The bench-runner composite action this repository publishes, used as `dermot-murphy/EmbeddedTestBench@v0.01.0001` |
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
| `benches/simulated/dongle/firmware_manifest.json` | Simulated dongle image, version 1.4.0, protocol 1.4 |
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
| `dermot-murphy/CStyleCheck` | `@v1.5.1` (v1.6.0 blocked by CStyleCheck#439) | `.github/workflows/style.yml` |
| C rule configuration | `.cstylecheck.yml` with `.cstylecheck-baseline.json` (110 baselined violations) | Repository root |
| Python rule configuration | `[tool.pylint]` in `pyproject.toml` with `.pylint-baseline.json` (436 baselined findings) | Repository root |
| `pytest`, `pytest-cov` | As declared in the `test` extra (`pytest-cov` ≥ 4.0) | `pyproject.toml` |
| `pylint` | **4.0.8** | `.github/workflows/lint.yml`; exact pin, because its rule set decides what a green lint means |

---

## 6. Verification Status

| Measure | Value |
|---|---|
| Tests passing | **3 179**, none failing, on Python 3.8, 3.9 and 3.12 (CI, `develop` at f1eac09) |
| Statement coverage | 95% (94.99% to 95.06% across the three Python versions; gate 90%) |
| Requirements without a covering test | 0, enforced by `tests/test_traceability.py` |
| Firmware build and unit tests | Green in CI; flash and RAM recorded |
| C coding-standard check | Green in CI against its baseline |
| Python lint | Green in CI against its baseline |
| System qualification on hardware | **44 of 64** system requirements qualified, 3 partially qualified, 10 not qualified, 2 not performed and 5 out of scope (ETB-SYS5-002 §7.1, run 2026-10-04) |
| J-Link fixes on hardware | #177 and #178 each reproduced, then confirmed fixed, on the real probe and sensor 5C1712 (2026-10-05). QS-01b has not been rerun, so ETB-SYS2-004 and -031 stay as ETB-SYS5-002 records them |

The release branch adds no functional change to f1eac09. It changes the version,
the usage examples, documents and the action pins of the two publish workflows,
and its own CI run checks that.

---

## 7. Known Problems and Limitations

| # | Limitation | Reference |
|---|---|---|
| 1 | S2-LP: receive refused after a transmit in the same session (Major) | #179; ETB-SYS2-046 not qualified |
| 2 | BLE dongle: `open_link` makes a single attempt and does not retry a link that fails to establish (0x3E) | #180 |
| 3 | TTi 1604: frequency mode not recognised, and the meter is lost afterwards; an open input on ohms is not reported as overrange (Major). DC volts are qualified; the other functions are not | #181; ETB-SYS2-051, -053 not qualified |
| 4 | The J-Link fixes (#177, #178) are confirmed on hardware, but QS-01b has not been rerun, so ETB-SYS2-004 and -031 are still recorded as not qualified | ETB-SYS5-002 §7.1, §11 |
| 5 | System qualification is incomplete: 20 of 64 requirements are not fully qualified. The oscilloscope and the SHT30 measurement were out of scope, because they are not yet live on the bench | ETB-SYS5-002 §3.3, §7.1, §11 |
| 6 | Qualification has not been reproduced by an independent engineer (QS-05) | ETB-SYS5-002 §11 |
| 7 | The system integration cases in ETB-SYS4-001 are recorded as not formally performed | ETB-SYS4-001 §5 |
| 8 | No document in this baseline has left Draft status | §5.3 |
| 9 | No MISRA checker runs in CI; those rules rest on review | ETB-STD-001 §7.1 |
| 10 | The dongle firmware build (`firmware/nordic_dongle/Makefile`) sets no explicit `-std` and does not enable `-Wextra`; only the separate compile check does | ETB-STD-002 §7.1, §7.2 |
| 11 | The Python lint check is baselined at 436 existing findings and fails only on new ones; `duplicate-code` is disabled because its output is not reproducible across machines | ETB-ANA-001 §6.13 |
| 12 | The C standard check is baselined at 110 existing violations and fails only on new ones | ETB-ANA-001 §6.12 |
| 13 | CStyleCheck is held at v1.5.1, because the v1.6.0 action fails on every run | #203; CStyleCheck#439; ETB-ACQ4-001 §7 |
| 14 | Python 3.8 is end-of-life upstream. It is tested because `pyproject.toml` declares it as the floor; when supporting it stops being tenable, the floor should be raised rather than the leg dropped | ETB-ANA-001 §6.1 |
| 15 | The Kepler specifications cannot run on the simulated bench, because there is no simulated Kepler sensor | #119, #121, #122 |
| 16 | One dongle sampling test is timing-sensitive on Windows, where the clock ticks every 15.6 ms, and can fail intermittently there; CI on Linux is unaffected | #214 |
| 17 | The wiki and home page are first published by the workflows at this release; before it they showed hand-published content | #184, #194 |

Items 1 to 3 are open defects against stated requirements. #179 and #181 block
requirements that ETB-SYS5-002 records as not qualified; once they are fixed,
QS-01b, QS-07 and QS-09 are rerun to close those requirements. The other items
are the distance between what Embedded Test Bench is shown to do and what it will
eventually be shown to do, recorded so that the distance is visible.

---

## 8. Installation

From a clone, at the release:

```
git checkout v0.01.0001
pip install -e .[spec,serial,test]
pytest
```

Without cloning:

```
pip install "benchtools @ git+https://github.com/dermot-murphy/EmbeddedTestBench@v0.01.0001"
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
