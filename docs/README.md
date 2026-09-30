# Documentation index

Work products follow Automotive SPICE V4.0, SWE.1 to SWE.4. The software item is
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

| Document | Contents |
|---|---|
| [SWE.1 Software Requirements](SWE1_Software_Requirements_Specification.md) | What the tooling must do, per element |
| [SWE.2 Software Architecture](SWE2_Software_Architecture.md) | Layering, elements, and the architectural decisions |
| [SWE.3 Detailed Design](SWE3_Software_Detailed_Design.md) | Per-module design units |
| [SWE.4 Test Specification](SWE4_Unit_Test_Specification.md) | Verification strategy, test groups, pass criteria |
| [SWE.4 Test Report](SWE4_Unit_Test_Report.md) | Results, coverage, measured accuracy, defects found |
| [Traceability Matrix](Traceability_Matrix.md) | Bidirectional trace, stakeholder need to test |
| [Bench Runner Guide](Bench_Runner_Guide.md) | How to write a test specification and a bench configuration |

## Instrument-specific

| Document | Contents |
|---|---|
| [TDS3014B VISA Determination Report](tek3014b/VISA_Determination_Report.md) | Whether VISA is required to drive the oscilloscope over Ethernet, with evidence and bench confirmation items |
| [J-Link Integration Notes](jlink/JLink_Integration_Notes.md) | Why the GDB Server rather than the DLL, running it on Windows and in Docker, choosing a timing method, and the probe's bench confirmation items |
| [BLE Dongle Notes](ble/BLE_Dongle_Notes.md) | Why the dongle needs firmware of its own, the line protocol, building and flashing it, how to read an advertising profile and a response time, and the firmware's bench confirmation items |
| [S2-LP Devkit Notes](s2lp/S2LP_Devkit_Notes.md) | The ST S2-LP kit: why the vendor's firmware is used unchanged and what that decision costs, its CLI protocol and the two reply traps in it, the register map and what may be kept of it, and the kit's bench confirmation items |
| [GPD-3303D Notes](psu/GPD3303D_Notes.md) | The GW Instek bench supply: why it clamps, why constant current matters to every other measurement on the bench, why per-channel output is emulated and what that does not promise, why a channel it is slaving to another is refused rather than reported, and its bench confirmation items |

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
same seam the BLE dongle uses and the RS-232 multimeter (STK-18) will. The
GPD-3303D supply is the intermediate case: it answers `*IDN?` and nothing else
from IEEE 488.2, so it takes the transport and lifecycle from `ScpiInstrument`
and replaces the SCPI-specific parts explicitly. Adding one should not require touching `benchtools.core`; if it does,
that is a finding about the core, not about the instrument.
