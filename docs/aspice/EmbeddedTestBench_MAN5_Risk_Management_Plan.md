<img src="../../assets/brand/svg/logos/embeddedtestbench-logo-compact.svg" alt="Embedded Test Bench" width="240">

# Risk Management Plan

*Automotive SPICE® PAM v4.0 | MAN.5 — Risk Management*

---

## 1. Document Identification & Control

| Field | Value | Field | Value |
|---|---|---|---|
| **Document ID** | ETB-MAN5-001 | **Version** | 0.4 |
| **Project** | Embedded Test Bench | **Date** | 2026-10-05 |
| **Status** | Draft | **Classification** | Internal |
| **Author** | Claude | **Reviewer** | Dermot Murphy |
| **Approver** | Dermot Murphy | **Related Process** | MAN.5 |

> Reviewer and Approver are the same person; see ETB-DEV-002.

---

## 2. Revision History

| Version | Date | Author | Description of Change |
|---|---|---|---|
| 0.1 | 2026-09-19 | Claude | Initial |
| 0.2 | 2026-10-03 | Claude | #141: TB-RISK-013 added - the test run viewer opened to the network. |
| 0.3 | 2026-10-04 | Claude | #183: product renamed to Embedded Test Bench - document file name prefix `EmbeddedTestBench_`, identifier prefix `ETB-` (was `TB-`), product name in prose. Earlier revision rows keep the names in use when they were written. |
| 0.4 | 2026-10-05 | Claude | #194: the compact brand logo added above the title, the same line in every controlled document (ETB-SUP8-001 §6.3). |

---

## 3. Purpose & Scope

### 3.1 Purpose

This plan says how Embedded Test Bench identifies, judges, treats and watches risk, and
records the risks currently carried.

The central risk of a test tool is not that it fails — a tool that fails is
noticed. It is that it succeeds in a way that produces a measurement nobody can
challenge and nobody should believe. Most of the register below is about that.

### 3.2 Referenced Documents

| Document ID | Title | Version |
|---|---|---|
| ETB-MAN3-001 | Embedded Test Bench Project Management Plan | 0.1 |
| ETB-SUP1-001 | Embedded Test Bench Quality Assurance Plan | 0.1 |
| ETB-SUP9-001 | Embedded Test Bench Problem Resolution Management Plan | 0.1 |
| ETB-ACQ4-001 | Embedded Test Bench Supplier Monitoring Plan | 0.1 |
| ETB-SYS2-001 | Embedded Test Bench System Requirements Specification | 0.1 |
| ETB-DEV-001 | Embedded Test Bench AI Authorship Deviation | 0.1 |

### 3.3 Scope

Technical, process and supply risks to Embedded Test Bench itself. Risks in the products
that Embedded Test Bench is used to test belong to those products' projects, except where
Embedded Test Bench could cause such a risk to be missed — that case is ETB-RISK-001.

---

## 4. Risk Management Process

| Step | What happens |
|---|---|
| Identify | A risk is raised by anyone at any time: while writing a requirement, while reviewing, when a test fails for an unexpected reason, or when a supplier changes something. Risks arising from a problem are raised from ETB-SUP9-001 |
| Analyse | Probability and impact are assigned per §5, and the exposure computed |
| Treat | One of: avoid, mitigate, transfer, accept. A treatment names the action and who does it |
| Monitor | Each risk has a **trigger** — an observable event meaning the risk is materialising. Triggers are checked at each milestone review |
| Close | A risk is closed when its trigger can no longer fire, or when it has materialised and become a problem under ETB-SUP9-001 |

A risk that materialises stops being a risk. It is raised as a problem and
tracked there; the risk entry records which problem it became.

---

## 5. Risk Classification

**Probability**

| Level | Meaning |
|---|---|
| P1 Low | No reason to expect it in the project's lifetime |
| P2 Medium | Plausible; has happened in similar work |
| P3 High | Expected unless something is done |

**Impact**

| Level | Meaning |
|---|---|
| I1 Low | Local rework; nothing outside Embedded Test Bench is affected |
| I2 Medium | A capability is unavailable, or work has to be redone across a work package |
| I3 High | A measurement made through Embedded Test Bench could be believed and be wrong |

**Exposure** = probability × impact.

| Exposure | Response |
|---|---|
| 6–9 | Treat now; a mitigation is required before the affected capability is used |
| 3–4 | Treat, with the action scheduled against a milestone |
| 1–2 | Accept and monitor |

---

## 6. Risk Register

| ID | Risk | P | I | Exp | Treatment | Trigger | Status |
|---|---|---|---|---|---|---|---|
| ETB-RISK-001 | A driver is confirmed only against its simulator, so both share a misunderstanding of the instrument and a wrong measurement looks right | P3 | I3 | 9 | **Mitigate.** Every element carries explicit bench-confirmation items; a simulated run is labelled as simulated in every report format; simulators model instrument behaviour (state machines, refusals, silent discard) rather than echoing expected replies | A bench-confirmation item is closed without a recorded hardware run | Open |
| ETB-RISK-002 | A vendor changes an instrument's command set or response format in a firmware revision, and the driver silently misparses | P2 | I3 | 6 | **Mitigate.** Instrument identity is queried and recorded in every report; ETB-ACQ4-001 §5 requires the tested firmware revision to be recorded per instrument | A report shows an instrument revision not previously recorded | Open |
| ETB-RISK-003 | Documents and code drift apart, so the documents describe a system that no longer exists | P3 | I2 | 6 | **Mitigate.** `tests/test_traceability.py` fails the build if code cites an undeclared requirement or a declared requirement is untested or absent from ETB-RTM-001 | The traceability check is skipped, marked xfail, or weakened | Open |
| ETB-RISK-004 | The author is a model with no memory between sessions; knowledge not written down is lost | P3 | I2 | 6 | **Mitigate.** ETB-DEV-001 §5; every decision that matters is written into a document in the change that acts on it | A change is made whose reason exists only in conversation | Open |
| ETB-RISK-005 | Vendor licence terms (e.g. ST SLA0072) are breached by vendoring source or reproducing vendor prose | P2 | I3 | 6 | **Avoid.** No vendor source is vendored. The S2-LP register map records facts — addresses, widths, reset values — not vendor text (S2LP-NFR-002). ETB-ACQ4-001 §4 lists each supplier's terms | A file appears containing vendor-supplied source or documentation text | Open |
| ETB-RISK-006 | An unpinned Python or toolchain dependency resolves to an incompatible version and the build breaks or, worse, behaves differently | P3 | I2 | 6 | **Mitigate.** Build-critical tools are pinned (`nrfutil==6.1.7`); CI pins the Python version; a resolver surprise is a problem under ETB-SUP9-001 | CI fails on a revision that previously passed, with no source change | Mitigated |
| ETB-RISK-007 | A test asserts the simulator's behaviour rather than the driver's, so it passes whatever the driver does | P2 | I3 | 6 | **Mitigate.** ETB-TMPL-001 §6.4 check T5; simulators are written from instrument documentation, tests from the requirements | A test fails when the simulator changes but the driver does not | Open |
| ETB-RISK-008 | A power supply setpoint is accepted by the driver but silently discarded by the instrument (tracking modes on the GPD-3303D) and the operator believes the rail is set | P3 | I3 | 9 | **Mitigate.** Per-channel writes are refused while tracking is active; `read` reports tracking state and a warning | A report shows a channel setpoint with tracking active | Mitigated |
| ETB-RISK-009 | Firmware flashed to a target differs from the firmware the report names | P2 | I3 | 6 | **Mitigate.** A firmware manifest beside the image records version and build date; the runner compares the version the device reports against the manifest | A run reports a version mismatch, or a manifest is missing | Mitigated |
| ETB-RISK-010 | The single J-Link, dongle or supply is unavailable, blocking all hardware confirmation | P2 | I2 | 4 | **Accept and monitor.** Every capability can be exercised against the simulated bench, so work continues; only confirmation is blocked | An instrument is unavailable for longer than a milestone | Open |
| ETB-RISK-011 | The coding-standard checker is an external repository that may change or become unavailable | P2 | I1 | 2 | **Accept and monitor.** The workflow pins `dermot-murphy/CStyleCheck@v1.5.1`; a failure blocks the style job only, not the build | The style workflow fails for a reason unrelated to the firmware source | **Trigger fired** — v1.6.0's action could not parse its own output; pinned to v1.5.1 (ETB-ACQ4-001 §7) |
| ETB-RISK-012 | One person holds all project knowledge and all roles | P2 | I2 | 4 | **Mitigate.** Everything of record is in the repository (ETB-MAN3-001 §11); reviewer independence is recorded as a deviation rather than assumed away (ETB-DEV-002) | A question about the project cannot be answered from the repository | Open |
| ETB-RISK-013 | The test run viewer, opened to the network so a run can be watched from another PC (#141), lets someone else on that network watch or steer a run that drives the bench's supply | P2 | I3 | 6 | **Mitigate.** The viewer listens on 127.0.0.1 unless told otherwise; another address needs an access token, generated at start, compared in constant time, on every request; `--read-only` removes control altogether; `--tls-cert`/`--tls-key` keep the token off the wire in clear, and the viewer warns when they are not used; the runner's control channel never leaves 127.0.0.1, and teardown cannot be interrupted (VIEW-FR-025 … -027, RUN-FR-061, -065) | The viewer is run with `--bind` on a network the bench does not trust, or the printed address is shared | Open |

---

## 7. Monitoring

Risks are reviewed at each milestone in ETB-MAN3-001 §7, and whenever a trigger
in §6 fires. A review records, per risk: whether the trigger has fired, whether
probability or impact has changed, and whether the treatment is still the right
one.

Review records are stored under `docs/aspice/reviews/` on the form in
ETB-TMPL-001. No review records are shipped with this baseline; none have been
held.

---

## 8. Review & Approval

| Role | Name | Signature / Electronic Approval | Date |
|---|---|---|---|
| Author | Claude | Approved | 2026-09-19 |
| Reviewer | Dermot Murphy | — | *pending* |
| Approver | Dermot Murphy | — | *pending* |
