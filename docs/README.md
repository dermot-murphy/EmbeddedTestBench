# Documentation index

Work products follow Automotive SPICE V4.0, SWE.1 to SWE.4. The software item is
**BenchTools**: the bench test tooling as a whole. Its four elements - the shared
core, the analysis library, the instrument drivers and the test runner - are
units within that item, so there is one coherent doc set rather than four
partial ones.

Requirement identifiers are namespaced by element, so they stay unique as
instruments are added:

| Prefix | Element | Package |
|---|---|---|
| `CORE-` | Instrument-agnostic foundations | `benchtools.core` |
| `ANA-` | Analysis of captured records | `benchtools.analysis` |
| `INST-` | Instrument drivers, common requirements | `benchtools.instruments` |
| `SCOPE-` | Tektronix TDS3014B driver | `benchtools.instruments.tek3014b` |
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

## Adding an instrument

A new driver needs its own requirements section in SWE.1 (prefix it, e.g.
`PSU-`), a design unit in SWE.3, a test group in SWE.4, and rows in the
traceability matrix. It does **not** need its own copy of the doc set. If it
raises an instrument-specific engineering question - as the VISA question did for
the oscilloscope - that gets its own report under `docs/<instrument>/`.
