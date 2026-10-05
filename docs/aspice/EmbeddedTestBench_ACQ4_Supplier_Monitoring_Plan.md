# Supplier Monitoring Plan

*Automotive SPICE® PAM v4.0 | ACQ.4 — Supplier Monitoring*

---

## 1. Document Identification & Control

| Field | Value | Field | Value |
|---|---|---|---|
| **Document ID** | ETB-ACQ4-001 | **Version** | 0.2 |
| **Project** | Embedded Test Bench | **Date** | 2026-10-04 |
| **Status** | Draft | **Classification** | Internal |
| **Author** | Claude | **Reviewer** | Dermot Murphy |
| **Approver** | Dermot Murphy | **Related Process** | ACQ.4 |

> Reviewer and Approver are the same person; see ETB-DEV-002.

---

## 2. Revision History

| Version | Date | Author | Description of Change |
|---|---|---|---|
| 0.1 | 2026-09-19 | Claude | Initial |
| 0.2 | 2026-10-04 | Claude | #183: product renamed to Embedded Test Bench - document file name prefix `EmbeddedTestBench_`, identifier prefix `ETB-` (was `TB-`), product name in prose. Earlier revision rows keep the names in use when they were written. |

---

## 3. Purpose & Scope

### 3.1 Purpose

Embedded Test Bench has no suppliers in the contractual sense — nothing is subcontracted
and no supplier agreement exists. What it does have is a set of parties whose
products it depends on and cannot influence: instrument manufacturers,
toolchain vendors, and open-source maintainers.

This plan says what is depended upon, what each dependency is trusted to do,
how a change in it would be noticed, and what happens then. That is the part of
ACQ.4 that has meaning here; the acquisition, tendering and agreement parts do
not apply and are recorded as not applicable in §9 rather than invented.

### 3.2 Referenced Documents

| Document ID | Title | Version |
|---|---|---|
| ETB-MAN3-001 | Embedded Test Bench Project Management Plan | 0.1 |
| ETB-MAN5-001 | Embedded Test Bench Risk Management Plan | 0.1 |
| ETB-SUP8-001 | Embedded Test Bench Configuration Management Plan | 0.1 |
| ETB-SUP9-001 | Embedded Test Bench Problem Resolution Management Plan | 0.1 |
| ETB-SVD-001 | Embedded Test Bench Software Version Description | 0.1 |

### 3.3 Scope

Every external product Embedded Test Bench depends on at build time or run time, and the
bench instruments themselves.

---

## 4. Dependencies

### 4.1 Instruments

| Supplier | Product | Depended upon for | Licence / terms |
|---|---|---|---|
| Tektronix | TDS3014B oscilloscope | Programmer-manual command set and response formats over VISA | Documentation used as reference only |
| GW Instek | GPD-3303D power supply | Programming-manual command set, tracking-mode behaviour, status byte encoding | Documentation used as reference only |
| SEGGER | J-Link probe, J-Link Commander, RTT | Flash programming, memory read, RTT transport | SEGGER licence terms; tools used, not redistributed |
| Nordic Semiconductor | nRF52840 dongle (PCA10059), nRF5 SDK 17.1.0, S140 SoftDevice 7.2.0, `nrfutil` | Firmware platform, BLE stack, DFU packaging | Nordic 5-clause licence for SDK; SoftDevice binary not redistributed |
| STMicroelectronics | S2-LP sub-GHz transceiver | Register map — addresses, widths, reset values | **SLA0072** |

### 4.2 Licence Constraint — SLA0072

ST's package is licensed under SLA0072. No ST source is vendored into this
repository and no ST documentation prose is reproduced. The S2-LP register map
in `benchtools/instruments/s2lp/` records facts about the device — register
addresses, field widths and reset values — written independently
(S2LP-NFR-002). This is the treatment of ETB-RISK-005 and is checked at review
(ETB-TMPL-001 §6.1 C2).

### 4.3 Tools and Libraries

| Supplier | Product | Version | Why pinned |
|---|---|---|---|
| Python Software Foundation | CPython | 3.10 in CI | `nrfutil` 6.1.7 requires it |
| Nordic Semiconductor | `nrfutil` | **6.1.7** | The last Python release packaging for the SDK 17 bootloader; unpinned installs resolve backwards to a Python 2 release that fails on `dict.iteritems` (ETB-RISK-006) |
| Arm | GNU Arm Embedded toolchain | As pinned in `.github/workflows/firmware.yml` | Flash and RAM figures are toolchain-dependent |
| PyPI maintainers | `pyvisa`, `pyserial`, `bleak`, `pytest`, `PyYAML` | As declared in `pyproject.toml` | Interface stability |
| `dermot-murphy` | `CStyleCheck` GitHub Action | `@v1.5.1` | Coding-standard enforcement (ETB-RISK-011) |

---

## 5. What Each Dependency Is Trusted To Do

Trust is stated so that it can be checked rather than assumed.

| Dependency | Trusted to | Not trusted to | How Embedded Test Bench copes |
|---|---|---|---|
| Instrument firmware | Implement the documented command set of its revision | Behave identically across revisions | Identity queried at connection and recorded in every report |
| Instrument documentation | Describe the common cases correctly | Describe every edge case | Undocumented behaviour observed on the bench is recorded in the element's notes and modelled in the simulator |
| SEGGER tools | Programme and read the target faithfully | Have a stable command-line output format | Output parsing is tested; a parse failure is an error, never a default value |
| `nrfutil` | Produce a valid DFU package for a given SDK | Remain compatible across versions | Pinned exactly |
| PyPI packages | Honour semantic versioning | Never regress | Version ranges declared; the suite is the check |
| CStyleCheck | Report violations of ETB-STD-002 and ETB-STY-001 | Be available forever | Pinned tag; failure blocks the style job only |

---

## 6. Monitoring

| What is watched | How | Trigger for action |
|---|---|---|
| Instrument firmware revision | Recorded in every report | A revision not seen before appears → confirm the affected commands on the bench before the result is used |
| Toolchain and library versions | Pinned in CI, recorded in ETB-SVD-001 | CI fails on a revision that previously passed with no source change → problem under ETB-SUP9-001 |
| Vendor documentation changes | Checked when a driver is next worked on | A documented behaviour differs from what the driver assumes → problem, and the simulator is corrected |
| Licence terms | Reviewed when a vendor product is added or upgraded | Terms that would require vendoring source → the dependency is not taken |
| CStyleCheck | The style workflow's result | A failure unrelated to the firmware source → problem under ETB-SUP9-001 |

There is no supplier audit, no supplier scorecard and no escalation path to any
of these parties. Where a vendor's product misbehaves, the only available
responses are to work around it, pin away from it, or stop using it — and to
record which was chosen.

---

## 7. Coding-Standard Checker

`dermot-murphy/CStyleCheck@v1.5.1` is run by `.github/workflows/style.yml` against
`firmware/nordic_dongle`. It is the mechanical enforcement of ETB-STD-002 and
ETB-STY-001. It is a dependency like any other: pinned by tag, its failures
treated as findings against the firmware source, and its unavailability treated
as a problem with the style job rather than a licence to merge unchecked C.

The pin is the **exact** version, `@v1.5.1`, not a floating `@v1` and not the
newest release. Three things are recorded here, all of them found by running it
rather than by reading about it:

1. **`@v1` does not resolve.** The repository publishes exact version tags only,
   so a workflow referring to `@v1` fails to start. The `@v1` form came from the
   action's own usage example, which is not a tag list.
2. **v1.6.0 is skipped because its action is broken.** The checker runs
   correctly — 17 files, 0 violations — and the action then fails with
   `could not read results JSON`, because v1.6.0 writes its version banner into
   the results file the action parses as JSON. v1.5.1, v1.5.0 and v1.4.1 write
   the file cleanly. This is a defect in the supplier's product, of the kind
   §6 exists to notice; the response available to this project is to pin away
   from it, which is what §5 says about a dependency that misbehaves.
3. **An exact pin is what ETB-SUP8-001 §4 asks for anyway**, because a checker
   that silently changes its rule set changes what a green build means.

The baseline file is written by the pinned version and is not portable across
versions: the same 113 violations recorded by v1.6.0 were not matched by v1.5.1.
Moving the pin therefore means regenerating the baseline in the same change, and
dealing with whatever new findings the newer version brings.

---

## 8. Acceptance of Supplied Items

A supplied item is accepted when it has been used successfully in a green CI
run or a recorded bench run, and its version is recorded in ETB-SVD-001. There is
no separate incoming inspection: for software dependencies, the build and the
suite *are* the inspection; for instruments, the first recorded run against real
hardware is.

---

## 9. Not Applicable

| ACQ.4 expectation | Status | Reason |
|---|---|---|
| Supplier agreements and their monitoring | Not applicable | No agreements exist; all dependencies are commercially or openly available products used under their published terms |
| Joint progress reviews with suppliers | Not applicable | No supplier relationship exists to review |
| Supplier corrective action requests | Not applicable | No mechanism to raise one |
| Acceptance against contractual criteria | Replaced | §8 — acceptance against use in a green build or a recorded run |

These are recorded as not applicable, with the reason, rather than described as
performed.

---

## 10. Review & Approval

| Role | Name | Signature / Electronic Approval | Date |
|---|---|---|---|
| Author | Claude | Approved | 2026-09-19 |
| Reviewer | Dermot Murphy | — | *pending* |
| Approver | Dermot Murphy | — | *pending* |
