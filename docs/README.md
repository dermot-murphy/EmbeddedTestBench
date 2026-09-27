# Documentation index

Work products follow Automotive SPICE V4.0 at Capability Level 2. The software item is
**BenchTools**: the bench test tooling as a whole. Its elements - the shared core,
the analysis library, the instrument and debug-probe drivers, and the test runner -
are units within that item, so there is one coherent doc set rather than one per
driver.

Requirement identifiers are namespaced by element, so they stay unique as
instruments are added:

| Prefix | Element | Package |
|---|---|---|
| `CORE-` | Instrument-agnostic foundations | `benchtools.core` |
| `ANA-` | Analysis of captured records | `benchtools.analysis` |
| `INST-` | Instrument drivers, common requirements | `benchtools.instruments` |
| `SCOPE-` | Tektronix TDS3014B driver | `benchtools.instruments.tek3014b` |
| `JLINK-` | SEGGER J-Link debug probe driver | `benchtools.instruments.jlink` |
| `BLE-` | Nordic BLE bench dongle: host driver **and** dongle firmware | `benchtools.instruments.nordic_dongle`, `firmware/nordic_dongle` |
| `RUN-` | Bench test runner | `benchtools.runner` |

## Documents

All ASPICE work products live in [`aspice/`](aspice/). Every one is at version
0.1 and status Draft: none has been through the review its own process requires
(TB-PA2-001 §6, GP 2.2.4).

### System level

| Document | Contents |
|---|---|
| [SYS.2 System Requirements](aspice/TestBench_SYS2_System_Requirements.md) | What the bench must do, including the parts that are not software |
| [SYS.3 System Architecture](aspice/TestBench_SYS3_System_Architecture.md) | Physical and logical elements, and the eleven interfaces between them |
| [SYS.4 System Integration & Integration Test](aspice/TestBench_SYS4_System_Integration_Test.md) | How the bench is assembled, and the sixteen cases that need hardware |
| [SYS.5 System Qualification Test](aspice/TestBench_SYS5_System_Qualification_Test.md) | Eight end-to-end scenarios, simulated and on hardware, and the open bench-confirmation items |

### Software level

| Document | Contents |
|---|---|
| [SWE.1 Software Requirements](aspice/TestBench_SWE1_SW_Requirements.md) | What the tooling must do, per element |
| [SWE.2 Software Architecture](aspice/TestBench_SWE2_SW_Architecture.md) | Layering, elements, and the architectural decisions |
| [SWE.3 Detailed Design](aspice/TestBench_SWE3_Detailed_Design.md) | Per-module design units |
| [SWE.3 GPD-3303D Driver Design](aspice/TestBench_SWE3_002_GPD3303D_Driver_Design.md) | The supply's driver as one component: structure, decisions, and the lessons learned bringing it up on hardware |
| [GPD-3303D Remote Control Interface](aspice/TestBench_IF001_GPD3303D_Remote_Control_Interface.md) | The supply's protocol as the instrument implements it, command by command, with captured replies |
| [SWE.4 Unit Verification](aspice/TestBench_SWE4_Unit_Verification.md) | Verification strategy, test groups, pass criteria |
| [SWE.4 Unit Verification Report](aspice/TestBench_SWE4_Unit_Verification_Report.md) | Results, coverage, measured accuracy, defects found |
| [SWE.5 Integration & Integration Test](aspice/TestBench_SWE5_SW_Integration_Test.md) | How the units are joined, and the interface properties no unit test can show |
| [SWE.6 Qualification Test](aspice/TestBench_SWE6_SW_Qualification_Test.md) | Twenty qualification cases against the software requirements |
| [Traceability Matrix](aspice/TestBench_Traceability_Matrix.md) | Bidirectional trace, stakeholder need to test |

### Management and support

| Document | Contents |
|---|---|
| [MAN.3 Project Management Plan](aspice/TestBench_MAN3_Project_Management_Plan.md) | Objectives, roles, work packages, milestones, what is monitored |
| [MAN.5 Risk Management Plan](aspice/TestBench_MAN5_Risk_Management_Plan.md) | The process and the twelve risks currently carried |
| [SUP.1 Quality Assurance Plan](aspice/TestBench_SUP1_Quality_Assurance_Plan.md) | What is checked, by what, and the five rules this project will break a schedule over |
| [SUP.8 Configuration Management Plan](aspice/TestBench_SUP8_Configuration_Management_Plan.md) | Configuration items, versioning, baselines, status accounting |
| [SUP.9 Problem Resolution Plan](aspice/TestBench_SUP9_Problem_Resolution_Management_Plan.md) | What counts as a problem, and what may never close one |
| [SUP.10 Change Request Plan](aspice/TestBench_SUP10_Change_Request_Management_Plan.md) | When a change needs a request, and how its impact is analysed |
| [ACQ.4 Supplier Monitoring Plan](aspice/TestBench_ACQ4_Supplier_Monitoring_Plan.md) | What is depended on, what each dependency is trusted to do, and how a change would be noticed |
| [Software Version Description](aspice/TestBench_SVD_Software_Version_Description.md) | What the current baseline contains, and its known limitations |
| [Process Capability Records](aspice/TestBench_PA2_Capability_Records.md) | Level 2 generic practices, rated honestly |
| [Repository Analysis Report](aspice/TestBench_Analysis_Report.md) | A measured analysis of this repository, with prioritised actions |

### C coding standards

| Document | Contents |
|---|---|
| [Embedded C Coding Standard](aspice/TestBench_Embedded_C_Coding_Standard.md) | Behavioural rules for the firmware's C |
| [Embedded C Style Guide](aspice/TestBench_Embedded_C_Style_Guide.md) | Formatting, naming and layout, including which conventions are deliberately not adopted |
| [Industry Standards — Applicability](aspice/TestBench_STD_001_Industry_Standards_Comparison.md) | Where the rules come from, how deep the MISRA subset goes, and what is not claimed |

### Deviations and templates

| Document | Contents |
|---|---|
| [DEV-001 AI Authorship](aspice/TestBench_DEV001_AI_Authorship_Deviation.md) | The author is a model; what compensates for that |
| [DEV-002 Reviewer Independence](aspice/TestBench_DEV002_Independent_Review_Deviation.md) | Reviewer and approver are the same person |
| [Review Record Template](aspice/TestBench_Review_Template.md) | The form a work product review is recorded on |
| [Test Case Template](templates/ASPICE_CL2_Test_Case_Template_1.md) | The form a manually performed test case is written on |

### Guides

| Document | Contents |
|---|---|
| [Bench Runner Guide](Bench_Runner_Guide.md) | How to write a test specification and a bench configuration |
| [Bench Self-Check Setup](Bench_Self_Check_Setup.md) | Setting up a Windows or Linux machine to run the bench self-check against real instruments |
| [Robot Framework Keyword Catalogue](robot/Robot_Keyword_Catalogue.md) | Proposed keywords for the BLE dongle, the J-Link and the GPD-3303D, with the hardware behaviour that set each one's defaults. Nothing is implemented |

## Instrument-specific

| Document | Contents |
|---|---|
| [TDS3014B VISA Determination Report](tek3014b/VISA_Determination_Report.md) | Whether VISA is required to drive the oscilloscope over Ethernet, with evidence and bench confirmation items |
| [J-Link Integration Notes](jlink/JLink_Integration_Notes.md) | Why the GDB Server rather than the DLL, running it on Windows and in Docker, choosing a timing method, and the probe's bench confirmation items |
| [BLE Dongle Notes](ble/BLE_Dongle_Notes.md) | Why the dongle needs firmware of its own, the line protocol, building and flashing it, how to read an advertising profile and a response time, and the firmware's bench confirmation items |
| [S2-LP Devkit Notes](s2lp/S2LP_Devkit_Notes.md) | The ST S2-LP kit: why the vendor's firmware is used unchanged and what that decision costs, its CLI protocol and the two reply traps in it, the register map and what may be kept of it, and the kit's bench confirmation items |
| [GPD-3303D Notes](psu/GPD3303D_Notes.md) | The GW Instek bench supply: why it rejects an out-of-range setting silently, why constant current matters to every other measurement on the bench, why per-channel output is emulated and what that does not promise, why a channel it is slaving to another is refused rather than reported, and its bench confirmation items |

## Adding an instrument

A new driver needs its own requirements section in SWE.1 (prefix it, e.g.
`PSU-`), a design unit in SWE.3, a test group in SWE.4, and rows in the
traceability matrix. It does **not** need its own copy of the doc set. If it
raises an instrument-specific engineering question - as the VISA question did for
the oscilloscope, and the DLL-versus-GDB question did for the probe - that gets
its own report under `docs/<instrument>/`.

An instrument that needs firmware of its own is an element spanning two
languages, as the BLE dongle does. It stays **one** element with one interface
artefact that both halves are built from and a test compares them against - see
AD-16 - rather than a separate `FW-` element with its own document set.

The J-Link is the worked example of a driver that is **not** a SCPI instrument: it
implements `core.instrument.Instrument` rather than `ScpiInstrument`, which is the
same seam the BLE dongle and the RS-232 multimeter (STK-18) use. The
GPD-3303D supply is the intermediate case: it answers `*IDN?` and nothing else
from IEEE 488.2, so it takes the transport and lifecycle from `ScpiInstrument`
and replaces the SCPI-specific parts explicitly. Adding one should not require touching `benchtools.core`; if it does,
that is a finding about the core, not about the instrument.
