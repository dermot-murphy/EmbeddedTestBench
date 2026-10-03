# Software Unit Verification Specification

*Automotive SPICE® PAM v4.0 | SWE.4 Software Unit Verification*

---

## 1. Document Identification & Control

| Field | Value | Field | Value |
|---|---|---|---|
| **Document ID** | TB-SWE4-001 | **Version** | 1.18 |
| **Project** | TestBench | **Date** | 2026-10-03 |
| **Status** | Draft | **Classification** | Internal |
| **Author** | Claude | **Reviewer** | Dermot Murphy |
| **Approver** | Dermot Murphy | **Related Process** | SWE.4 |

> **Note — Reviewer independence (TB-DEV-002):** The Reviewer and Approver are the same person (Dermot Murphy). This is accepted under deviation record **TB-DEV-002** (`docs/aspice/TestBench_DEV002_Independent_Review_Deviation.md`) on the basis that TestBench has a single human team member.

---

## 2. Revision History

| Version | Date | Author | Description of Change |
|---|---|---|---|
| 0.1 | 2026-09-19 | Claude | Initial |
| 0.2 | 2026-09-23 | Claude | Test groups added for the TTi 1604: SWE4-UT-DMMPROTO, SWE4-UT-DMM, SWE4-UT-DMMSIM, SWE4-UT-DMMCLI. |
| 0.3 | 2026-09-25 | Claude | SWE4-UT-BLESCRIPT extended to the new command-document behaviour (BLE-FR-109…116); firmware unit cases now 148 (#46, #48). |
| 0.4 | 2026-09-26 | Claude | SWE4-UT-PSUPANEL added for the GPD-3303D front-panel check (#67). Header version brought into line with this history. |
| 0.5 | 2026-09-30 | Claude | Thermometer firmware verification strategy (§1.4b) and test groups SWE4-UT-PICO, -PICOSIM, -PICOCLI, -PICOFWPROTO and -PICOFW added; item not covered on silicon added (#104). |
| 0.6 | 2026-10-02 | Claude | #115: SWE4-UT-DMMPANEL (the 1604 front-panel check) and SWE4-UT-DMMBENCH (the opt-in bench test, §4.6a) added; SWE4-UT-DMM, -DMMPROTO, -DMMSIM, -TRANSPORT and -SERIAL extended. Oracle independence item added for frames built from the manufacturer's note. |
| 0.7 | 2026-10-02 | Claude | §1.4a: the firmware unit tests are themselves checked against the C coding standard (#111). SWE4-UT-FWUNIT case count corrected to 149, the number the suite runs. Renumbered from 0.6 on merging `develop`, where #115 took 0.6. |
| 0.8 | 2026-10-02 | Claude | #116: SWE4-UT-PATHS added (70 cases): the input-path search order and its error, the per-driver declarations, and every shipped specification run from outside the checkout. |
| 0.9 | 2026-10-02 | Claude | #120: SWE4-UT-BENCH also covers `runner/test_shipped_benches.py`, which now checks that the simulated bench provides every instrument and driver each shipped specification uses (RUN-FR-035). |
| 1.0 | 2026-10-02 | Claude | #124: SWE4-UT-BLECLI covers choosing a sensor on the command line (16 cases, BLE-FR-071). |
| 1.1 | 2026-10-02 | Claude | #126: SWE4-UT-EVENTNAMES added (21 cases); SWE4-UT-EVENTS covers per-instrument names (54 cases); SWE4-UT-TESTBENCH covers declared names and lower-case logs in the monitor. |
| 1.2 | 2026-10-03 | Claude | #127: SWE4-UT-PICOFLASH added (34 cases, including two for an error from the 1200-baud reset kept as a note) for reflashing the Pico 2 thermometer with no BOOTSEL press (PICO-FR-070 … -076); §1.4b and the item not covered on silicon extended to PICO-OPEN-05, then narrowed after PICO-OPEN-01 and -05 were confirmed on a real Pico 2 on Windows. |
| 1.3 | 2026-10-03 | Claude | #131: SWE4-UT-PICO, -PICOSIM, -PICOCLI, -PICOFWPROTO and -PICOFW rewritten for the `rd` command set, `ecureset`, `NoReadingError` and the two-place temperature (PICO-FR-006, -007, -027, -047, -061); the raw-word cross-check is no longer tested (PICO-FR-044 withdrawn). Firmware unit cases now 83. §1.4b: the shared vectors now include the two-place rounding, and the host unit tests are run with clang on Windows. §8: the Pico 2 not-covered row narrowed to what still needs the SHT30-D module, after the first run on a real Pico 2 (TB-SWE4-002 §13A.7). With #127 merged, SWE4-UT-PICOFLASH revised for `flash` confirming the build by `rd` (name, version and commit SHA read from the image in place of the title and build date): now 35 cases, the ambiguous build-date case replaced by an ambiguous-SHA case and a missing-version case added. |
| 1.4 | 2026-10-03 | Claude | #134: SWE4-UT-SELECT added (14 cases) for running a selected subset of test cases (RUN-FR-059). |
| 1.5 | 2026-10-03 | Claude | #135: SWE4-UT-RUNEVENTS added (21 cases) for the structured event-log records (CORE-FR-064, RUN-FR-060). |
| 1.6 | 2026-10-03 | Claude | #136: SWE4-UT-CONTROL added (33 cases) for the run control channel (RUN-FR-061 … -065). |
| 1.7 | 2026-10-03 | Claude | #137: SWE4-UT-VIEWSTATE (14 cases) and SWE4-UT-VIEWSERVER (25 cases) added for the test run viewer (VIEW-FR-001 … -009); SWE4-UT-LAYERING includes the viewer layer. |
| 1.8 | 2026-10-03 | Claude | #138: SWE4-UT-VIEWTRAFFIC added (26 cases); SWE4-UT-VIEWSERVER 25 → 29 for `/api/instruments` (VIEW-FR-010 … -012). |
| 1.9 | 2026-10-03 | Claude | #139: SWE4-UT-VIEWRADIO added (14 cases; S2LP-FR-080, VIEW-FR-013 … -015). |
| 1.10 | 2026-10-03 | Claude | #140: SWE4-UT-VIEWGRAPHS added (16 cases). |
| 1.11 | 2026-10-03 | Claude | #148: SWE4-UT-VIEWTAGS added (19 cases). |
| 1.12 | 2026-10-03 | Claude | #149: SWE4-UT-VIEWSTATUS added (10 cases). |
| 1.13 | 2026-10-03 | Claude | #141: SWE4-UT-VIEWREMOTE added (22 cases). |
| 1.14 | 2026-10-03 | Claude | #151: SWE4-UT-S2LPTABLES added (19 cases); SWE4-UT-S2LPKEPLER's RESPONSE case rewritten to the firmware's layout and three added. |
| 1.15 | 2026-10-03 | Claude | #152: SWE4-UT-VIEWKEPLER added (12 cases). |
| 1.16 | 2026-10-03 | Claude | #153: SWE4-UT-VIEWSENSOR added (16 cases). |
| 1.17 | 2026-10-03 | Claude | #154: SWE4-UT-VIEWTWF added (15 cases). |
| 1.18 | 2026-10-03 | Claude | #155: SWE4-UT-VIEWDIAG added (14 cases). |

---

## 3. Purpose & Scope

### 3.1 Purpose

This document states how the units of **TestBench** are verified: the strategy, the test groups, the notable individual cases and the pass criteria. Results are recorded separately in TB-SWE4-002, which this project keeps apart from the specification so that what was intended and what happened cannot be edited into agreement.

This document satisfies **Automotive SPICE® PAM v4.0, SWE.4 — Software Unit Verification**.

### 3.2 Referenced Documents

| Document ID | Title | Version |
|---|---|---|
| TB-SYS2-001 | TestBench System Requirements Specification | 0.1 |
| TB-SWE1-001 | TestBench Software Requirements Specification | 0.1 |
| TB-SWE2-001 | TestBench Software Architecture Description | 0.1 |
| TB-SWE3-001 | TestBench Software Detailed Design | 0.1 |
| TB-RTM-001 | TestBench Requirements Traceability Matrix | 0.1 |
| TB-SWE4-002 | TestBench Software Unit Verification Report | 0.1 |

---

## 4. Verification strategy

### 4.1 Method

Automated unit and integration tests executed with `pytest`. Every test runs
without instrument hardware; no test is skipped for lack of it. Tests skip only
when an optional dependency is absent (`matplotlib`, `pyvisa`, `pyyaml`), which is
the correct behaviour for an optional extra.

### 4.2 Test environment

| Item | Value |
|---|---|
| Language / runtime | CPython 3.11.15 (minimum supported: 3.8) |
| Framework | `pytest` with `pytest-cov` |
| Instrument substitute | `benchtools.core.simulator.SimulatedInstrument` and its subclasses, behind `MockTransport` |
| VXI-11 substitute | `tests/core/transport/vxi11_server.py` — an ONC-RPC server on a loopback socket |
| Socket substitute | `tests/core/transport/scpi_socket_server.py` — line-oriented SCPI over loopback TCP |
| BLE dongle substitute | `benchtools.instruments.nordic_dongle.SimulatedDongle` - answers the dongle's line protocol over `MockTransport`, with a deterministic sensor population on a virtual microsecond clock |
| Serial-port substitute | pyserial's `loop://` URL handler, which provides a real serial object with no hardware |
| RTT and SWO substitute | `tests/instruments/jlink/test_sockets.py::LoopbackServer` — a TCP server on loopback standing in for the GDB Server's RTT and SWO ports |
| Firmware SDK substitute | `firmware/nordic_dongle/test/support/` — fake SDK headers at the SDK boundary, so the firmware's own sources compile and run on the host |
| Debug probe substitute | `benchtools.instruments.jlink.SimulatedJLink` — answers the GDB/MI dialogue over `MockTransport`, with a deterministic simulated target (symbols, memory, stacks, RTT, ITM, timing) |
| Child-process substitute | The host's own Python interpreter, driven as a child through `ProcessTransport`, so pipe framing and child death are exercised without a debugger installed |
| Optional extras exercised | `matplotlib`, `pyvisa` + `pyvisa-py`, `pyyaml` |

### 4.3 Independence of the oracle

Three measures ensure tests do not merely confirm the code agrees with itself:

1. **The RPC test server is an independent implementation.** It encodes and
   decodes the wire format with its own `struct` calls and does not import the
   client's codec. A passing test means two independent implementations agree on
   bytes.
2. **Simulators compute measurements analytically.** Values returned by a
   simulated measurement subsystem are derived from the signal model parameters,
   not from the sampled record, so host-side analysis is checked against an
   independent reference.
3. **Timing is checked against an independently injected interval.** The
   simulated firmware places two locations 64 000 cycles apart, which at the
   simulated 64 MHz core is exactly 1.000 ms. Three of the four timing methods —
   cycle counter, target timer and SWO/ITM — reach that figure by different routes
   (a DWT register read, two firmware variables, and a decoded ITM timestamp
   stream), so agreement between them is agreement between three implementations,
   not self-confirmation. The fourth, the host clock, is expected *not* to reach it,
   and the test asserts that it is flagged untrustworthy rather than that it is
   accurate.
4. **The firmware is checked against the driver, not against itself.**
   `test_firmware_protocol.py` parses `firmware/nordic_dongle/include/protocol.h`
   - the artefact the C is compiled from - and compares its command table, event
   table, error codes and size limits against the driver's constants. Neither
   side can be made to agree by editing the other's tests.
5. **ITM streams are built by an independent encoder.** `test_swo.py` assembles
   packet bytes with the architecture manual's framing, rather than comparing the
   decoder against itself.
6. **Cross-validation between computation paths.** Host-side analysis is compared
   against the simulated instrument's own measurement engine
   (`test_spread_skews_match_the_instrument_delay_measurement`), and the built-in
   VXI-11 transport is compared against PyVISA's independent implementation over
   the same server.
7. **The 1604's frames are built from the manufacturer's note, and its driver is
   run over a real serial object.** `test_protocol.py` assembles frames byte by
   byte from the published format - starting with the note's own worked example,
   12.345 as `96 219 242 102 182` - rather than only from the simulator's
   encoder. `TestTheSerialLink` runs the driver over pyserial's `loop://`, which
   never signals end-of-message, so a reader that depends on one (#115) fails
   there as it fails on hardware.

### 4.4 Work-product verification

Traceability documents rot silently: a requirement is added and never traced, a
design unit is renamed and the docstring pointing at it goes stale, an element is
deleted and its rows linger. None of that breaks a build, so none of it is noticed
until an assessment. `test_traceability.py` therefore makes the documents part of
the build, checking that:

- every requirement declared in SWE.1 appears in the traceability matrix;
- the matrix contains no row naming a requirement SWE.1 does not define;
- every requirement, design unit, architectural element and test group cited in a
  docstring is actually defined in the corresponding document;
- every source and test module carries a ``Traces to`` line;
- every architectural decision in SWE.2 is accounted for in the matrix.

These check consistency, not content: whether a requirement is well written is a
review question, but whether it is traced at all is mechanical.

### 1.4a Firmware verification

The dongle firmware is verified three ways, none of which needs a dongle:

1. **Unit tests on the host** (`SWE4-UT-FWUNIT`). The firmware's sources are
   compiled unchanged against fake SDK headers, so the logic under test is the
   logic that runs on the part. This is where behaviour is checked.
   The test sources are themselves held to the C coding standard: CStyleCheck
   checks them in their own step of `.github/workflows/style.yml`, with no
   baseline, and fails on any finding (#111).
2. **Agreement with the host driver** (`SWE4-UT-BLEFW`). The protocol header is
   parsed and compared against the driver's constants.
3. **Cross-compilation** (`compile_check.sh`). The whole firmware is compiled for
   Cortex-M4 against real SDK headers.

4. **The real build** (`.github/workflows/firmware.yml`). The firmware is
   cross-compiled against nRF5 SDK 17.1.0, linked, sized and packaged for DFU on
   every push that touches `firmware/**`.

Between them these catch behaviour, interface drift, compilation and the link.
What no amount of them establishes is that the firmware *runs*: see the report's
§4.6 and BLE-OPEN-02 to -04.

### 1.4b Thermometer firmware verification

The Pico 2 thermometer firmware (`firmware/pico_sht30`) is verified the same
way, and none of it needs a Pico:

1. **Unit tests on the host** (`SWE4-UT-PICOFW`). `cmd_parser.c`, `sht30.c`,
   `text.c` and `firmware_version.c` are compiled unchanged against a scripted
   fake of `hal.h`, with the target's warnings as errors and under
   AddressSanitizer and UndefinedBehaviorSanitizer:

   ```
   cmake -S firmware/pico_sht30/test -B build/pico-tests
   cmake --build build/pico-tests && ctest --test-dir build/pico-tests --output-on-failure
   ```

   On the Windows bench PC, configure with clang: the MinGW GCC 6.3 there
   fails with an internal compiler error on `-fsanitize=address`, a fault of
   that compiler that predates #131. With clang the Microsoft C runtime's
   deprecation of `strncpy` (used by the fake HAL) must be silenced, and the
   AddressSanitizer runtime DLL must be on `PATH` when CTest runs:

   ```
   cmake -S firmware/pico_sht30/test -B build/pico-tests -G Ninja -DCMAKE_C_COMPILER=clang -DCMAKE_C_FLAGS=-D_CRT_SECURE_NO_WARNINGS
   cmake --build build/pico-tests
   PATH="<llvm>/lib/clang/<version>/lib/windows:$PATH" ctest --test-dir build/pico-tests --output-on-failure
   ```

2. **Agreement with the host driver** (`SWE4-UT-PICOFWPROTO`). `protocol.h`,
   `firmware_version.h` and `board_config.h` are parsed and compared with the
   driver's constants; tab indentation and the absence of printf-family calls
   are checked on every firmware source.
3. **The C coding standard** (PICO-NFR-006). CStyleCheck runs over all of
   `firmware/pico_sht30`, tests included, with no baseline, and fails on any
   finding (`.github/workflows/style.yml`).
4. **The real build** (PICO-FR-031). The firmware is compiled and linked
   against Pico SDK 2.1.1 with the Arm GNU toolchain, and `pico_sht30.uf2` is
   produced.

Reference vectors are shared: `test_sht30.c` and `test_simulator.py` assert
the same raw-word-to-value pairs, and `test_text.c` and `test_simulator.py` the
same milli-degree-to-two-places pairs (`text_centi` and `milli_to_centi_text`,
PICO-FR-027), so the C and Python conversions cannot drift apart silently. What none of this establishes
is behaviour on silicon with a sensor attached: PICO-OPEN-02 to -04 and -06.
USB enumeration and identity on a real Pico 2 (PICO-OPEN-01) were confirmed on
2026-10-03.

The host-side `flash` command (PICO-FR-070 … -076, `SWE4-UT-PICOFLASH`) is
verified the same way: every operating-system interaction - drive discovery,
the copy, the 1200-baud reset, opening the port, the clock - is a seam, and a
simulated board stands in for the Pico. That a real Pico 2 reboots into its
bootloader on `bootsel` and on the 1200-baud reset, takes the image, and comes
back reporting the copied build was confirmed on Windows on 2026-10-03
(PICO-OPEN-05, closed), and again the same day for the `rd` firmware of #131,
whose name, version and commit SHA `flash` confirmed by `rd`; drive discovery
on Linux and macOS is untested on hardware.

### 4.5 Architectural verification

The layering that makes the shared core reusable is easy to state and easy to
lose: one convenient import and the core stops being shareable. `test_layering.py`
therefore enforces it mechanically rather than by review, by parsing every
module's imports:

- Dependencies point one way only: core, analysis, instruments, runner.
- `benchtools.core` contains no reference to any instrument, checked over code
  identifiers rather than raw text (prose in a docstring may legitimately name an
  instrument).
- `benchtools.core` is importable in a subprocess without importing any other
  element, and `benchtools.analysis` without importing instruments or the runner.
- No module imports a third-party package at module level, so no dependency can
  become mandatory by accident (CORE-NFR-001, JLINK-NFR-001). Optional extras are
  imported inside the function that needs them, which is also what allows the
  named diagnostic of CORE-NFR-003.

### 4.6 Test selection rationale

| Technique | Where applied |
|---|---|
| Equivalence partitioning | Channel numbers, encodings, transfer widths, resource-string forms, limit forms, result path forms |
| Boundary value analysis | Volts/div, position, time/div, record length, XDR payload lengths mod 4, limit bounds (inclusive), sequence indices |
| Error guessing / negative testing | Malformed blocks, truncated XDR, refused device names, unreachable portmapper, silent instrument, malformed specifications, unknown drivers, unresolvable paths |
| Known-answer testing | Synthesised signals with exactly known period and skew; measured values compared against the injected values |
| Interface testing | Assertions on the exact SCPI emitted, because a misspelled command is silently ignored by real hardware |
| Architectural testing | Import-graph and layering constraints (§1.5) |
| Work-product testing | Traceability consistency between code and documents (§1.4) |
| Regression testing | One test per defect found during development (§4) |
| Round-trip testing | 488.2 block encode/decode, binary versus ASCII curve decoding, JSON report write/read, ITM encode/decode, GDB/MI escape/unescape |
| Protocol grammar testing | GDB/MI records: nesting, repeated names, uniformly named lists, escapes, non-MI lines (`SWE4-UT-GDBMI`) |
| Resource-limit testing | Hardware breakpoint and watchpoint envelopes, memory chunk boundaries, the 32-bit cycle-counter wrap |

### 4.6a Bench tests (opt-in)

`tests/bench/` holds tests that exercise a real instrument. They are **not**
unit verification and are not part of the default run: the directory is
excluded from collection (`norecursedirs` in `pyproject.toml`), and each test
skips unless the operator names the instrument in the environment. They are run
by hand at the bench, and write a markdown record of what the instrument did,
which is the evidence that discharges bench confirmation items.

Each can also be run against the driver's simulator (`sim://`) as a dry run of
the test itself, with the reference the operator names applied to the
simulated input. A dry run shows the bench test is sound; it is never evidence
about an instrument, and its record says so on its first lines.

| Test ID | File | Purpose | Requirements verified |
|---|---|---|---|
| SWE4-UT-DMMBENCH | `bench/tti1604/test_bench.py` | A real TTi 1604 named by `BENCHTOOLS_TTI1604`: the link and remote mode, key echo, the raw stream and reading rate, every frame decoding, a tour of the functions safe on an open input, every DC voltage range, the frequency gate, local and remote; against a wired reference, DC volts, resistance, frequency and - only when a current reference is named - DC current; OFL on an open input | DMM-FR-001 .. -033, -080 |

The front-panel checks (`examples/10_psu_front_panel_check.py`,
`examples/12_dmm_front_panel_check.py`) are the interactive counterpart: the
operator confirms each step on the instrument's own display. They are tested
against the simulator in the default run (SWE4-UT-PSUPANEL, SWE4-UT-DMMPANEL).

### 4.7 Pass criteria

| ID | Criterion |
|---|---|
| PC-1 | All tests pass. |
| PC-2 | Statement coverage ≥ 90% (CORE-NFR-007). |
| PC-3 | Every requirement is covered by at least one test, or by a recorded inspection where a test is not the appropriate method. |
| PC-4 | Timing measurements recover injected skews to better than one tenth of a sample interval. |
| PC-5 | The layering constraints of §1.5 hold. |
| PC-6 | The work-product consistency checks of §1.4 hold. |
| PC-7 | Every timing method recovers the injected 1.000 ms interval exactly, except the host clock, which is required to flag itself as not trustworthy. |
| PC-8 | No test requires a J-Link, a target, a debugger or a GDB server to be installed. |
| PC-9 | No module imports a third-party package at module level. |
| PC-10 | The firmware's command set, events, error codes and limits agree with the driver's, and every firmware source carries its trace, allocates nothing dynamically, and holds the house indentation. |
| PC-11 | A simulated 100 ms sensor reads as a mean interval of exactly 105 ms with a spread of exactly 10 ms, and a sensor that skips beacons is reported as missing them rather than as advertising slowly. |
| PC-12 | Every firmware unit test passes, and the firmware compiles for the target after any change they prompt. |

## 5. Test groups

| Test ID | File | Purpose | Requirements verified |
|---|---|---|---|
| SWE4-UT-LAYERING | `test_layering.py` | Import graph and element isolation, the viewer above the runner | CORE-NFR-001, -008, -009 |
| SWE4-UT-LINT | `test_lint_script.py` | The pylint baseline gate (`scripts/lint.py`): a finding keyed by file and rule matches its baseline entry whatever path separator pylint reports | — |
| SWE4-UT-TRACE | `test_traceability.py` | Consistency between the code and the SWE.1 to SWE.4 work products: every requirement traced, no orphan rows, every cited identifier defined, every module carrying its own trace | All (traceability base practices) |
| SWE4-UT-SCPI | `core/test_scpi.py` | `ScpiInstrument`: lifecycle, primitives, identity, error queue, 488.2 blocks, simulator injection | CORE-FR-020 .. -028, INST-FR-001, -002 |
| SWE4-UT-INSTRUMENT | `core/test_instrument.py` | `Instrument`: lifecycle template and hooks, identity caching, a close that cannot raise, simulator declaration, default empty event queue | CORE-FR-012 .. -016 |
| SWE4-UT-PROCESS | `core/transport/test_process.py` | `ProcessTransport`: pipe framing, reader threads, bounded stderr retention, a child that exits immediately, retained exit status | CORE-FR-009, CORE-NFR-005, -006 |
| SWE4-UT-SIMBASE | `core/test_simulator.py` | Shared simulator harness: dispatch, compound messages, event queue, binary replies, subclassing | CORE-FR-040, -041 |
| SWE4-UT-VALIDATE | `core/test_validation.py` | Range, channel and choice validation; the enumeration base | CORE-FR-030, -031, CORE-NFR-004 |
| SWE4-UT-TRANSPORT | `core/transport/test_base.py` | Message framing, buffering, stale-response discard, lifecycle, timeouts; stream reading past an end-of-message, the `read_raw` failure that motivated it, discarding unread input, and a virtual-clock simulator given the read timeout | CORE-FR-005, -007, -061, -062, CORE-NFR-005, -006 |
| SWE4-UT-VXI11 | `core/transport/test_vxi11.py` | VXI-11 client at wire level against an independent RPC server | CORE-FR-001, -002, -007, -008 |
| SWE4-UT-SOCKET | `core/transport/test_socket.py` | Raw socket transport; length-bounded and idle-bounded reads | CORE-FR-003 |
| SWE4-UT-VISA | `core/transport/test_visa.py` | PyVISA transport against the same RPC server | CORE-FR-006, CORE-NFR-003 |
| SWE4-UT-FACTORY | `core/transport/test_factory.py` | Resource parsing; VXI-11 is the default; VISA is opt-in; backend registry | CORE-FR-010, -011 |
| SWE4-UT-WAVEFORM | `analysis/test_waveform.py` | Code decoding, scaling, clipping, CSV export, the four constructors | ANA-FR-001 .. -005 |
| SWE4-UT-MEASURE | `analysis/test_measure.py` | Levels, edges, interpolation, hysteresis, period, width, rise time, N-channel spread | ANA-FR-010 .. -017 |
| SWE4-UT-PLOT | `analysis/test_plotting.py` | Rendering, spread annotation, missing-dependency diagnostic | ANA-FR-020, -021, CORE-NFR-003 |
| SWE4-UT-SAMPLES | `analysis/test_samples.py` | Numbers taken from text by a pattern; the statistics of a set; a short set and an empty one | ANA-FR-022 |
| SWE4-UT-SCOPE | `instruments/tek3014b/test_scope.py` | Driver behaviour and emitted SCPI; validation; acquisition; capture; measurement; hardcopy; errors | SCOPE-FR-010 .. -101, INST-FR-003 |
| SWE4-UT-ENV | `instruments/tek3014b/test_simulator.py` | Self-checks on the oscilloscope simulator | SCOPE-FR-090 |
| SWE4-UT-CLI | `instruments/tek3014b/test_cli.py` | Scope sub-commands end to end; argument expansion; exit statuses | SCOPE-FR-100 |
| SWE4-UT-GDBMI | `instruments/jlink/test_gdbmi.py` | The GDB/MI grammar: all record kinds, nested tuples and lists, uniformly named lists, repeated names, C-string escapes, non-MI lines, GDB's unnamed download-progress tuple | JLINK-FR-001 |
| SWE4-UT-GDBSESSION | `instruments/jlink/test_session.py` | Token correlation, MI errors as typed exceptions, draining asynchronous records before a write, waiting for `*stopped`, console command escaping, a dead GDB distinguished from a timeout | JLINK-FR-002 |
| SWE4-UT-JLINK | `instruments/jlink/test_probe.py` | The probe driver: resource forms, symbols, attach, flash and per-section verification, erase, reset/run/halt/step, breakpoints and their envelope, watchpoints, memory and word access with chunking, variables, call stack, RTT delegation, all four timing methods, loading a named image before reading it, preserved ranges written back and checked, structures holding strings, erasing from reset and refusing an erase that did not happen, leaving the target running on close unless asked, identity from the server banner | JLINK-FR-003 .. -006, -010 .. -011, -020 .. -023, -030 .. -036, -040 .. -045, -050 .. -055, -060 .. -067, -080, -081 |
| SWE4-UT-RTT | `instruments/jlink/test_rtt.py` | RTT: line assembly from fragments, retained partial lines, history independent of consumption, pattern matching with timeout, the timeout diagnostic, per-line flushed logging | JLINK-FR-050 .. -055 |
| SWE4-UT-SWO | `instruments/jlink/test_swo.py` | ITM decoding: 1-, 2- and 4-byte source packets, sync, overflow, both local timestamp formats, extension and global timestamps, fragmented feeds, prescaler scaling | JLINK-FR-064 |
| SWE4-UT-TIMING | `instruments/jlink/test_timing.py` | `TimingResult`: statistics over repetitions, resolution per method, the trustworthiness rule, halting declaration, empty samples raising, `as_dict` | JLINK-FR-060, -065 .. -067, JLINK-NFR-004 |
| SWE4-UT-JLINKSERVER | `instruments/jlink/test_server.py` | Server and GDB discovery with Windows names first, then install directories newest first, a host GDB refused unless it can debug ARM, the command line and its unattended flags with no `-singlerun`, draining the server's output and reading the probe from its banner, an already-listening port, a server that cannot be spawned remotely, one that exits during start-up, one that never listens, and stopping only what was started | JLINK-FR-003 .. -005, JLINK-NFR-002 |
| SWE4-UT-JLINKSOCKETS | `instruments/jlink/test_sockets.py` | The RTT and SWO TCP links against a loopback server: fragmented arrival, writes reaching the server, collection with a timeout, an unreachable port, and the host as an argument | JLINK-FR-050, -051, -064, JLINK-NFR-002, -003 |
| SWE4-UT-JLINKSIM | `instruments/jlink/test_simulator.py` | Self-checks on the simulated probe and target: the MI dialogue, the exact 64 000-cycle interval, symbols, stacks, RTT, sections, the hardware-breakpoint type | JLINK-FR-090 |
| SWE4-UT-JLINKCLI | `instruments/jlink/test_cli.py` | Every probe sub-command end to end, including erase; JSON output; the untrustworthy-measurement warning; exit statuses; which sub-commands leave the target halted | JLINK-FR-006, JLINK-FR-100 |
| SWE4-UT-JLINKRTTONLY | `instruments/jlink/test_rtt_only.py` | Numbers from matching RTT lines, lines already waiting ignored, a quiet target; opening without attaching, and the GDB Server told `-nohalt` only when asked | JLINK-FR-101, JLINK-FR-102 |
| SWE4-UT-SERIAL | `core/transport/test_serial.py` | Serial transport: port and rate parsing, a TCP port not mistaken for a line rate, scheme registration, framing over `loop://`, a write the far end will not take; reading a stream without framing, and discarding what the port holds | CORE-FR-017, -061, CORE-NFR-003, -006 |
| SWE4-UT-BLE | `instruments/nordic_dongle/test_dongle.py` | The dongle driver: identity and protocol check, scanning and filtering, selection, connection, UART, response timing, advertising profile, logging | BLE-FR-002 .. -062 |
| SWE4-UT-BLESAMPLE | `instruments/nordic_dongle/test_sampling.py` | One command repeated at an interval, a number from each reply, scaling, and a reply without a number refused | BLE-FR-117 |
| SWE4-UT-BLEPROTO | `instruments/nordic_dongle/test_protocol.py` | The line protocol: replies, errors, events, empty and `=`-bearing values, non-protocol lines, hex, addresses and their types | BLE-FR-001, -002 |
| SWE4-UT-FWUNIT | `firmware/nordic_dongle/test/*.c` | **Firmware unit tests** (Unity, CMake, CTest, 149 cases; the test sources themselves pass CStyleCheck with no baseline): the command dispatcher and every reply shape; the host link's line assembly, bounded queue and drop counting; the sensor table, filters and advertising reports; the UART client's link, writes and round-trip timing; the microsecond clock and its 32-bit wrap | BLE-FR-002 .. -004, -010, -020 .. -030, -040 .. -051, BLE-NFR-001, -002 |
| SWE4-UT-BLEFW | `instruments/nordic_dongle/test_firmware_protocol.py` | Firmware and driver agreement: commands, argument bounds, handlers attached, events, error codes, size limits, protocol version; and firmware hygiene: traces, no dynamic allocation, indentation | BLE-FR-001, -080, -090, BLE-NFR-001, -003 |
| SWE4-UT-BLESESSION | `instruments/nordic_dongle/test_session.py` | Command/reply with events interleaved, early-stopping collection, waiting for an event, drop notices, and session logging | BLE-FR-002, -004, -060 .. -062 |
| SWE4-UT-BLEPROFILE | `instruments/nordic_dongle/test_profile.py` | Advertising statistics: channel coalescing, advDelay, missed events, duty cycle, completeness, exactly nominal intervals | BLE-FR-030 .. -036 |
| SWE4-UT-BLESCRIPT | `instruments/nordic_dongle/test_script.py`, `test_script_links.py` | Command documents: the shapes accepted and every shape refused, exact and pattern matching, variables, connect and disconnect steps, the Timeout and Note columns, results in the order error, skip, fail, pass, `<disconnect>`, the event log, a sensor that does not answer, the times and the clock behind them, the report's columns, the template, and the shipped document run | BLE-FR-100 .. -116 |
| SWE4-UT-BLELATENCY | `instruments/nordic_dongle/test_latency.py` | Round-trip statistics, which clock, resolution, the connection-interval floor, empty samples; the value a reply reports | BLE-FR-050 .. -054, BLE-FR-118, BLE-NFR-005 |
| SWE4-UT-BLESIM | `instruments/nordic_dongle/test_simulator.py` | Self-checks on the simulated dongle: exact intervals, skipped beacons, channel rotation, refusals, drop counters | BLE-FR-080 |
| SWE4-UT-BLECLI | `instruments/nordic_dongle/test_cli.py` | Every dongle sub-command end to end; JSON output; the incomplete-capture and unresolvable-latency warnings; `firmware` check, mismatch exit status and `--update`; `--select` by address, name, part of a name and any case, the strongest of several matches, one scan or two, every sub-command, `cmd --addr`, and `--addr` with `--select` refused | BLE-FR-012 .. -014, BLE-FR-070, BLE-FR-071 |
| SWE4-UT-BLEFIRMWARE | `instruments/nordic_dongle/test_firmware.py` | Build identity and refresh: manifest loading and its errors, build-date parsing, the same-version-rebuilt mismatch, three-valued `is_older`, protocol major versus minor, DFU entry, flashing, and the flash that did not take | BLE-FR-012 .. -014 |
| SWE4-UT-LIMITS | `runner/test_limits.py` | Every limit form, construction validation, rendering; exact comparison against text and against a value an earlier step saved | RUN-FR-016, RUN-FR-020 .. -024 |
| SWE4-UT-RESOLVE | `runner/test_resolve.py` | Result path resolution and its failure messages; how many, for a step returning a collection; references to a value an earlier step saved, their formatting and their failures | RUN-FR-013, RUN-FR-016 |
| SWE4-UT-BRINGUP | `runner/test_sensor_bringup.py` | The shipped sensor bring-up specification run end to end on the simulated bench, and each fact it claims to establish broken in turn to confirm it would fail: a firmware reporting another version, a part with no identifier programmed, a board that says nothing on RTT | RUN-FR-016, RUN-FR-024, RUN-FR-030 .. -037 |
| SWE4-UT-EVENTS | `core/test_events.py` | The bench event log: sources by logger name, one JSON line per record, the console level left alone, following a growing file including a partial last line, and the supply's, the runner's and the radio's records arriving in it; the name rule, each driver's default including `TEMP`, a bound logger, a rename reaching loggers already bound, two instruments of one driver told apart, a transport's lines under its instrument's name, and an instrument named from construction | CORE-FR-060, CORE-FR-063 |
| SWE4-UT-TESTBENCH | `tools/test_test_bench.py` | The Test Bench monitor's sources: a live packet as the log line rf_monitor's parser reads, the ST GUI page's RF setup, register table and register-file export, reading the setup while receiving and resuming, the PSU and J-Link panels rebuilt from event-log records, event formatting and colours, and live reception from a simulated kit; event sources upper case, a log written in lower case before #126 read the same, any declared name shown as itself in a colour of its own | CORE-FR-060 |
| SWE4-UT-EVENTNAMES | `runner/test_event_names.py` | Event-log names allocated in the specification and attached on the bench (21 cases): the entry forms, an invalid or shared name refused in either, the specification's name winning, the bench's and the driver's in turn, a clash of defaults refused before anything connects, an open instrument renamed, the shipped benches naming `temp` and `rtt`, a run whose records carry only the declared names, and the name in the record and the report | RUN-FR-008, CORE-FR-063 |
| SWE4-UT-COREFW | `core/test_firmware.py` | Reading a build manifest: by name, by directory, by build subdirectory; the diagnostics, including that the caller supplies how to produce one; build-date parsing and the date a build did not inject | CORE-FR-050 |
| SWE4-UT-SPEC | `runner/test_spec.py` | Specification parsing and every malformed form | RUN-FR-010 .. -016 |
| SWE4-UT-PARAMS | `runner/test_parameters.py` | Parameters as an argument, a bound and a tolerance, rendered into text, an undefined name refused, and the values used in the record and report | RUN-FR-058 |
| SWE4-UT-SELECT | `runner/test_selection.py` | A selected subset of test cases run, the rest recorded as skipped "not selected" in specification order, setup and teardown still run, the selection in the record, markdown and JUnit, an unknown name refused before the bench opens, and `--test` on the command line | RUN-FR-059 |
| SWE4-UT-RUNEVENTS | `runner/test_run_events.py` | The runner's structured records (21 cases): the sequence of kinds, standard JSON on every line, the plan in `run_start`, the tree and every result rebuilt from the log alone, resolved arguments, result, measurements and error in `step_end`, setup and teardown marked, the verdict in `run_end`, a test case not selected, a refused bench; `jsonable` and `log_event` | CORE-FR-064, RUN-FR-060 |
| SWE4-UT-CONTROL | `runner/test_control.py` | The run control channel (33 cases): abort after the current step with teardown run, in setup, and with test cases not selected; restart of the test case, back to an earlier test case, forward over test cases, from a step using a value saved earlier, refused for a value never saved, a missing or unselected target and during setup; refusals in teardown, with no run, for malformed and unknown requests, a second pause or abort; pause holding the run until resumed or aborted, and ended by a restart; status; requests and actions in the event log; the server on 127.0.0.1 with JSON lines and a run aborted over TCP, a server closed before it started; `--control` on the command line | RUN-FR-061 .. RUN-FR-065 |
| SWE4-UT-VIEWSTATE | `viewer/test_state.py` | The viewer's run state (14 cases): steps in words, the whole tree rebuilt from a run's log and matching its record, saved values, test cases not selected, a run part-way through, a second run in the same log, records without a kind, the control port, pause, resume and refusals, a restart, and the snapshot a copy | VIEW-FR-003, VIEW-FR-004 |
| SWE4-UT-VIEWSERVER | `viewer/test_server.py` | The viewer's server (29 cases): `/api/instruments` with and without a window and a window that is not numbers refused; the page and its files, nothing outside them, nothing from another site, 127.0.0.1; the header and Host guards; attaching to a finished log, the event stream replaying it, no record lost between reads; control passed to a runner, refused without a channel, a runner that does not answer; the catalogue with test cases and warnings; a simulated run started with a selection, requests for anything not offered and an unacknowledged warning refused; the command line | VIEW-FR-001 .. VIEW-FR-009 |
| SWE4-UT-VIEWTRAFFIC | `viewer/test_traffic.py` | Instrument traffic (26 cases): each kind of line classified; a query and its reply with the time between, a command with no reply, events before a reply, a reply with nothing asked, sources kept apart, a time window, the view a copy; the supply's and the probe's panels and choosing one by driver; a simulated run's own log with every supply query and dongle command answered, a step's window holding only its own traffic, the panels built, and a new run starting afresh | VIEW-FR-010 .. VIEW-FR-012 |
| SWE4-UT-VIEWRADIO | `viewer/test_radio.py`, `viewer/radio_log.py` | RF and BLE (14 cases), on a log from a simulated S2-LP kit with two sensors' frames and a bad one, and a simulated dongle's scan and advertising profile: every packet a structured record, a transmitted one counted as sent, frames decoded and listed, each sensor's latest of each type, one sensor only, decoding what the driver did not, a radio error, other records ignored; event fields, devices with advert count, interval and RSSI, other events, the dongle's exchanges, only the dongle's lines, a device heard once | S2LP-FR-080, VIEW-FR-013 .. VIEW-FR-015 |
| SWE4-UT-VIEWGRAPHS | `viewer/test_graphs.py` | Readings and graphs (16 cases): the supply's voltage and current, a channel reading, the thermometer's temperature and the meter's reading each logged as a `reading` record, and `log_reading` as console text; one chart per unit and one series per instrument, quantity and channel, and what is not a reading ignored; advertising interval, delta and RSSI on the dongle's clock, an expected period, the device heard most or the one chosen, nothing heard; step markers in order; the hub serving graphs | CORE-FR-065, PSU-FR-044, PICO-FR-048, DMM-FR-034, VIEW-FR-016 .. VIEW-FR-018 |
| SWE4-UT-VIEWTAGS | `viewer/test_tags.py` | Event-log tags (19 cases): a frame's sensor decoded or not, frames naming none, a BLE name's sensor, other lines; each kind, the tags put on the record; every record of two runs of two test cases tagged with its run and test case, setup and teardown, the list of tests; a test case not selected; nothing before a run; the hub tagging a log of runs, two sensors' frames and BLE | VIEW-FR-019 .. VIEW-FR-021 |
| SWE4-UT-VIEWSTATUS | `viewer/test_status.py` | The status bar (10 cases): open, closed, silent, warning and error instruments with the time since each was heard, one attached after it opened, the runner not an instrument; steps run of total part way through with the test case named, a test case that ended early, test cases not selected, the estimate from the same step, its action and all steps, a restart counting steps again, setup named; the hub serving it | VIEW-FR-022 .. VIEW-FR-024 |
| SWE4-UT-VIEWREMOTE | `viewer/test_remote.py` | The viewer from another PC (22 cases): nothing answered without the token, a bearer token whatever the host name, the printed address setting the cookie, wrong tokens refused, a POST needing the token and the guard header; read-only refusing changes but still needing the token; loopback addresses, another address refused without a token, tokens long and fresh, the options, reached through this machine's own LAN address; HTTPS with a Secure cookie | VIEW-FR-025 .. VIEW-FR-027 |
| SWE4-UT-VIEWKEPLER | `viewer/test_kepler_view.py` | rf_monitor's screens (12 cases): byte roles, header rows, payload rows naming CONFIG parameters and ticks, the latest frames of one sensor, an undecodable frame listed; every parameter's latest value, a later frame replacing one and unseen ones unknown, a polynomial frame placed by its repeat, the summary groups; identification from the last VERSION frame or none; the frames list naming CONFIG parameters | VIEW-FR-028 .. VIEW-FR-030 |
| SWE4-UT-VIEWSENSOR | `viewer/test_sensor_series.py` | rf_monitor's sensor graphs (16 cases): the mg and mm/s scaling and a larger full scale; temperature and battery from ALIVE, TWF and VERSION, each frame once however many copies, a later copy when the first was lost; ALIVE per axis with raw counts, TWF SI values by each SI type, each TWF packet once; ticks from ALIVE only and their delta with a reset as 0; sensors and the axis chosen; frames without a sensor or time ignored | VIEW-FR-031 .. VIEW-FR-033 |
| SWE4-UT-VIEWTWF | `viewer/test_twf.py` | rf_monitor's TWF screen (15 cases): sample for sample under none, distance and the polynomial with one and three repeats; a missing packet a gap, and spread across the waveform under distance; the TWF scale and ODR code; buffer and axis from the frame and the fallback; a new capture after a complete one; other frames ignored; a sine's spectrum peak at its frequency and amplitude; gaps filled; the same numbers without NumPy; a length not a power of two; nothing to transform | VIEW-FR-034 .. VIEW-FR-036 |
| SWE4-UT-VIEWDIAG | `viewer/test_diagnostics.py` | Diagnostics and Sync (14 cases): frames, packets and drops; periods with mean, deviation and extremes with their frames; a lost first copy, a burst closing after a gap, a burst still arriving; types without a counter; the last ten; one sensor at a time and reset; an unknown type counted; a LORES then HIRES handshake, countdowns from the frame's time firing, a NACK and a fresh request, an idle sensor dropped, other frames | VIEW-FR-037 .. VIEW-FR-039 |
| SWE4-UT-S2LP | `instruments/s2lp/test_s2lp.py` | The S2-LP driver: identification without an invented board, the band of a named board and the synthesiser's range otherwise, register and bit-field access, read-only refusals, mis-framed replies, strobes, both resets and the state each leaves, radio and packet configuration and their read-back, RSSI conversion, routing the interrupt, the PN9 TX-source refusal, transmit and its recovery, receive and its stop on timeout, capture with its re-arm count and rejected receptions, streaming with registers read after each frame and decoding, the microsecond board clock, and both logs | S2LP-FR-001 .. -036 |
| SWE4-UT-S2LPREG | `instruments/s2lp/test_registers.py` | The register map as data: unique addresses and names, non-overlapping fields inside their byte, reset values, read-only status registers, field extraction and insertion, lookup and its failures, contiguous runs, and the rendering of a dump | S2LP-FR-010 .. -014 |
| SWE4-UT-S2LPCONFIG | `instruments/s2lp/test_configuration.py` | Register values from a file: the punctuation such files are written with, hexadecimal values, every refusal and the line it names, applying with read-back, the loose and strict checks, and capturing a radio's settings back out; and the reset that makes a partial file deterministic, including that the reset strobe does not do it | S2LP-FR-017 .. -021 |
| SWE4-UT-S2LPPROTO | `instruments/s2lp/test_protocol.py` | ST's CLI protocol: argument formatting against the declared types, signed arguments, byte strings, the brace-delimited reply, replies recorded from a kit, tags written in bare hex, signed decimals and floats, the interpreter's error lines, and lines the driver did not understand | S2LP-FR-001 .. -004 |
| SWE4-UT-S2LPSESSION | `instruments/s2lp/test_session.py` | Reply framing by brace depth, a reply that never completes, output from before a command, an echo run into its reply, interpreter errors failing at once, stale replies skipped, the port timeout set once, the stop character and a stop sent to an idle board, collecting a batch, and the raw session log | S2LP-FR-003, -005, -035 |
| SWE4-UT-S2LPSIM | `instruments/s2lp/test_simulator.py` | Self-checks on the simulated kit: the register file, read-only writes discarded, packet format following its register, replies as the kit sent them, the single-delivery air, a receive that waits until stopped, RSSI and link-quality registers, batches and the stop character, the interrupt line and its GPIO mode, the PN9 TX source, and ST's settings after shutdown | S2LP-FR-050 |
| SWE4-UT-S2LPKEPLER | `instruments/s2lp/test_kepler.py` | Kepler frame decoding (RESPONSE as the firmware builds it: LORES and HIRES timers, slot, CONFIG pairs, a 14-byte empty CONFIG, #151): ALIVE, VERSION, CONFIG and TWF frames received from sensor 5C1712, every frame type built from the reference layouts, and each payload that cannot be decoded | S2LP-FR-070 |
| SWE4-UT-S2LPTABLES | `instruments/s2lp/test_kepler_tables.py` | Kepler names and arithmetic against the firmware (19 cases): sixty parameters in the firmware's order, the slot mapping under none and distance, the polynomial covering every parameter once per version, out of range, values named with units and enumerations; the polynomial a permutation, out of range the identity; waveform order under each method covering every sample once; ODR codes; reset reasons; a CONFIG frame naming its parameters, VERSION naming its reset reason, PCB and product, ALIVE its phase | S2LP-FR-081 .. S2LP-FR-083 |
| SWE4-UT-S2LPPREAMBLE | `instruments/s2lp/test_preamble.py` | Preamble length from PQI: the expected PQI for a length in bit-pairs, the best frame as the measurement, the ceiling, and the pass, fail and unmeasurable verdicts | S2LP-FR-049 |
| SWE4-UT-S2LPSAMPLES | `instruments/s2lp/test_kepler_samples.py` | A field from each transmission, copies counted once even when their bytes differ (5C1712's ALIVE status) and when the first copy is lost; other sensors left out; too few frames; an unknown field | S2LP-FR-072 |
| SWE4-UT-S2LPFRAME | `instruments/s2lp/test_kepler_frame.py` | One whole decoded frame of a type (5C1712's VERSION frame), other sensors left out, no frame an error naming the type and sensor | S2LP-FR-073 |
| SWE4-UT-S2LPEEPROM | `instruments/s2lp/test_eeprom.py` | The RF board's EEPROM: the bench kit's page 0, blank pages, the band and crystal codes, the band taken from it, and a named board that disagrees refused | S2LP-FR-035 |
| SWE4-UT-S2LPCLI | `instruments/s2lp/test_cli.py` | Every S2-LP sub-command end to end; JSON output; the register dump; a named board and the band refusal; `--setup` and the packet handler; the PN9 refusal; the "nothing heard" and "not continuous" warnings | S2LP-FR-060 |
| SWE4-UT-PSU | `instruments/gpd3303d/test_psu.py` | The supply driver: identity, setting and its range refusals, measurement, constant-current detection, per-channel output emulation and what it does not promise, the refusal to program a channel the supply is slaving to another, status decoding, error reporting, command pacing and the safe state | PSU-FR-001 .. -043 |
| SWE4-UT-PSUSIM | `instruments/gpd3303d/test_simulator.py` | Self-checks on the simulated supply: Ohm's law, the constant-current fallback, the single output switch, silent refusals, the three tracking modes and the setpoint a tracking supply discards, and the rejection of an out-of-range setting as the hardware rejects it | PSU-FR-006, PSU-FR-050 |
| SWE4-UT-PSUCLI | `instruments/gpd3303d/test_cli.py` | Every supply sub-command end to end; JSON output; the current-limit and tracking warnings; that `set` does not energise a rail | PSU-FR-060 |
| SWE4-UT-PSUPANEL | `instruments/gpd3303d/test_front_panel_check.py` | The front-panel check (`examples/10_psu_front_panel_check.py`) against the simulator: every step taken and logged with the driver's read-back, and the supply left with its output off and its original settings, after a completed run and after a failure part-way | PSU-FR-030, PSU-FR-040, PSU-FR-043 |
| SWE4-UT-DMMPROTO | `instruments/tti1604/test_protocol.py` | Frame decoding: the segment bitmap and the relationship that identifies it, the decimal point, an unrecognised pattern marked rather than dropped, decoding refused from the wrong offset, frames and echoes separated by structure, a digit byte that equals a key character, SI scaling, overrange as not-a-number, and a held display; the manufacturer's worked example and bit positions; the resistance multiplier derived on every range and under either display convention, and refused when it does not fit; frame validation and resynchronisation past a false start | DMM-FR-010 .. -028 |
| SWE4-UT-DMM | `instruments/tti1604/test_dmm.py` | The driver: the handshake lines driven for a serial port, a bare port name as a port, remote mode entered on connecting, Operate left alone, the driver's own identity, key presses and the resend of a dropped one, the mute meter reported with its likely cause, and the silence that names both states that produce it; connecting and reading over pyserial's `loop://` (#115); resynchronisation; an echo never taken from inside a frame; a measurement taken after the call; every selection confirmed from the readings, and a key the meter ignores reported; ranges by full scale and an idempotent auto range; Hz on AC only, and the 10 s gate waited for | DMM-FR-001 .. -009, -023 .. -033, -045 |
| SWE4-UT-DMMSIM | `instruments/tti1604/test_simulator.py` | Self-checks on the simulated meter: silence in local mode and with Operate off, every command echoed, Operate toggling rather than switching on, ranges bounded, and values round-tripping through the segment encoding to the decoder; the display at each range's resolution; auto-ranging after a change of function; Hz refused on DC; a reading every 0.4 s, and once per gate measuring frequency; a read shorter than the measurement timing out; dropped and ignored keys | DMM-FR-045, -046, CORE-FR-062 |
| SWE4-UT-DMMPANEL | `instruments/tti1604/test_front_panel_check.py` | The front-panel check (`examples/12_dmm_front_panel_check.py`) against the simulator: every step taken and logged with the driver's read-back, the operator's answers and a mismatch recorded, `q` stopping early, and the meter left on DC volts, auto-ranging, in local mode after a completed, stopped or failed run | DMM-FR-029, -030, -033, -081 |
| SWE4-UT-DMMCLI | `instruments/tti1604/test_cli.py` | Every meter sub-command end to end; JSON output; the display text reported beside the value; an unknown key name failing without a traceback | DMM-FR-070 |
| SWE4-UT-PICO | `instruments/pico_sht30/test_thermometer.py` | The thermometer driver: name, copyright, version and SHA from `rd`; another device refused; a reply for another option refused; connecting sends only `rd`; `NAK` raised as `RdRefusedError`, `err` as `SensorError`; readings to two places, below zero, each a new measurement; a value not to two places refused; `Error` from each fault raised as `NoReadingError`, never a stale value; identity with no sensor; status decoding, sensor reset, `ecureset`, bootloader; resource forms | PICO-FR-040 .. -043, -045 .. -047 |
| SWE4-UT-PICOSIM | `instruments/pico_sht30/test_simulator.py` | The simulated thermometer answers with the firmware's reply text: every `rd` option, `NAK`, `rd` with no option or two, `ver`/`temp`/`reset` unknown, `ecureset`, `bootsel`; conversion and two-place rounding vectors shared with the firmware tests; fault injection | PICO-FR-050, PICO-FR-022, PICO-FR-027 |
| SWE4-UT-PICOCLI | `instruments/pico_sht30/test_cli.py` | Every `benchtools thermo` sub-command end to end - `info`, `rd` for each option, an unknown option refused, `temp` and a series, `status`, `sreset`, `ecureset`, `bootsel`; JSON output and file; a failed connection; dispatch from the top-level command | PICO-FR-060, PICO-FR-061 |
| SWE4-UT-PICOFLASH | `instruments/pico_sht30/test_flash.py` | Reflashing with no BOOTSEL press (35 cases), against the simulated board and stand-in seams: UF2 parsing, bad magic, a file that is not whole blocks, a missing file, an RP2040 image refused, an image without the thermometer's name refused without `--any-image`, an image with two commit SHAs or with no version string not compared on that point and noted; success from running firmware and from a board already in its bootloader; the checks `name`, `version` and `sha` by `rd`, the version taken from the image or from `--expect-version`; a version mismatch and a commit SHA mismatch (the old image still running) reported, not raised; the 1200-baud fallback, and an error from the 1200-baud reset kept as a note rather than raised; bootloader timeout, no drive and no port, two drives, copy failure, a drive that never goes, a port that never comes back; the port taken from the port search when none is given; `--no-verify`; the drive recognised by its info file; drive search roots on Windows, Linux and macOS, and an unsupported system; the copy and its tolerated close error; the `flash` command's JSON and exit status | PICO-FR-070 .. -076 |
| SWE4-UT-PICOFWPROTO | `instruments/pico_sht30/test_firmware_protocol.py` | Firmware and driver agreement: commands, argument bounds, error codes, protocol version, sensor, name and copyright, version form `V<n>.<nn>.<nnnn>`, default address; firmware hygiene: tab indentation, no printf family | PICO-FR-001, -002, PICO-NFR-002, -004 |
| SWE4-UT-PICOFW | `firmware/pico_sht30/test/*.c` | **Firmware unit tests** (Unity, CMake, CTest, 83 cases): the text builder and its overflow, including two places rounded half away from zero, no `-0.00` and the `INT32_MIN` extreme; CRC-8 against the datasheet check value; conversion end points, mid-scale, negative values and rounding; frame decoding that never half-writes; measure, status and reset command bytes, waits and every failure path; line assembly, CR handling and over-length lines; every `rd` option, the injected SHA, identity without touching the sensor, `NAK` for unknown, partial and wrongly cased options, `err 2` for no option or two, `rd temperature` rounding and `Error` for an absent sensor, a NACK on the read, a corrupted frame and a bus timeout on either transfer; `ver`, `temp` and `reset` unknown; every other command's reply text, argument refusal, and reboot only after the reply | PICO-FR-001 .. -007, -020 .. -027, -030, PICO-NFR-001, -003 |
| SWE4-UT-BENCH | `runner/test_bench.py`, `runner/test_shipped_benches.py` | Bench configuration, lazy connection, driver registry, simulation detection, instrument identity recorded per run; every shipped bench file loads with registered drivers and no shared port; the simulated bench provides every instrument and driver each shipped specification uses | RUN-FR-001 .. -006, RUN-FR-035, RUN-FR-037 |
| SWE4-UT-ENGINE | `runner/test_runner.py` | Execution, failure versus error, setup abort, skips, roll-up, property steps, instruments in the record | RUN-FR-030 .. -037 |
| SWE4-UT-REPORT | `runner/test_report.py` | JSON, markdown and JUnit output; the instruments table and its identity-failure row | RUN-FR-037, RUN-FR-040 .. -043 |
| SWE4-UT-RUNCLI | `runner/test_cli.py` | Runner command line and top-level dispatch | RUN-FR-050 .. -053 |
| SWE4-UT-PATHS | `core/test_paths.py`, `runner/test_input_paths.py` | Input files named by a relative path (70 cases): search order - declaring file's directory, working directory, checkout - an absolute path and a non-path passed through, the error naming every location; which driver arguments are declared as input files and that outputs and channels are not; step arguments and bench options found from another directory; every shipped specification giving the same outcome on the simulated bench from outside the checkout as from inside it | RUN-FR-007, RUN-FR-017 |

## 6. Notable individual test cases

| Test | What it pins down |
|---|---|
| `test_core_never_references_an_instrument` | The regression that motivated the restructure: the core must not name any instrument. |
| `test_core_is_importable_on_its_own` | Importing `core` in a fresh interpreter pulls in no other element. |
| `test_layer_dependencies_point_one_way` | Every module's imports respect the layering (parametrised over all sources). |
| `test_device_names_are_probed_in_order` | An instrument answering only to the VXI-11.2 name `gpib0,1` still connects. |
| `test_large_transfer_is_reassembled` | A 10 000-point record arrives intact over a link advertising 1 kB. |
| `test_write_discards_a_stale_response` | An unread previous response cannot be returned as the answer to a new query. |
| `test_payload_containing_a_hash_byte_is_not_re_parsed` | Regression for D-01: sample code 35 (`#`) is data, not a block header. |
| `test_ascii_encoding_matches_binary` | Both transfer encodings decode to identical digitiser codes. |
| `test_interpolation_beats_the_sample_interval` | A deliberate 0.35-sample delay is resolved to within 0.5 ps. |
| `test_spread_equals_the_injected_skew` | Measured spread equals the injected skew to within 2 ps. |
| `test_spread_skews_match_the_instrument_delay_measurement` | Host-side analysis agrees with the instrument's own two-source delay. |
| `test_nothing_is_sent_when_validation_fails` | A rejected setting leaves the instrument untouched. |
| `test_no_trigger_times_out_with_a_useful_message` | An absent trigger names the likely cause. |
| `test_bare_sim_resource_uses_the_driver_simulator` | A driver's own simulator is injected without the transport knowing about it. |
| `test_transport_alone_falls_back_to_the_plain_simulator` | `sim://` is meaningful with no instrument named. |
| `test_unknown_header_is_recorded_not_ignored` | A driver that misspells a command fails a test rather than passing quietly. |
| `test_out_of_limit_is_a_failure_not_an_error` / `test_unknown_method_is_an_error_not_a_failure` | The failure/error distinction, from both sides. |
| `test_private_methods_are_unreachable` | A specification is data and cannot call driver internals. |
| `test_setup_failure_aborts_the_suite` | No test runs after an unknown setup. |
| `test_teardown_runs_even_after_a_failure` | Teardown is in a `finally`. |
| `test_failure_and_error_are_distinct_elements` | JUnit XML keeps a broken rig distinguishable from a product defect. |
| `test_all_sim_resources_count_as_simulated` | A report discloses simulation even without `--simulate`. |
| `test_a_mixed_bench_is_not_simulated` | One real instrument makes it a hardware run. |
| `test_shipped_specification_is_valid` / `test_shipped_bench_files_are_valid` | The examples in `specs/` and `benches/` stay loadable as the API changes. |
| `test_a_shipped_specification_runs_the_same_from_outside_the_checkout` | Regression for #116: every specification in `specs/` gives the same outcome when the runner is started outside the checkout. |
| `test_clear_error_when_matplotlib_is_absent` | A missing optional extra produces a named diagnostic, not `ImportError`. |

## 7. Defects found by this verification

| ID | Defect | Detected by | Resolution |
|---|---|---|---|
| D-01 | `Waveform.from_block` re-parsed a payload whose IEEE 488.2 header had already been consumed by the driver. Benign whenever the payload contained no `0x23` byte, but corrupted or failed the transfer when a sample code equalled 35. Data-dependent, therefore intermittent on real hardware. | Running the worked examples, which used a vertical position that produced code 35 on the rising edge. Not caught by the then-current test suite, whose positions happened to avoid that code. | De-framing separated from decoding: `from_payload` (no header parsing) is used by drivers, `from_block` retained for complete blocks, `from_ascii` added for the ASCII encoding, which was also unhandled. Regression tests force the condition deterministically by slowing the edge so every code appears. |
| D-02 | `threshold_for()` took `absolute=` while every public function took `absolute_threshold=`. | Writing `test_absolute_threshold_overrides_percent`. | Parameter renamed for consistency. |
| D-03 | Loopback test servers took 2 s each to shut down: closing a listening socket does not wake a thread blocked in `accept()`. | Profiling with `--durations`. | Listening sockets given a 0.1 s poll timeout; that file's runtime fell from 18.6 s to 1.45 s. |
| D-04 | `benchtools.core.transport.mock` imported the oscilloscope's simulator, so the whole transport package — and any future driver — depended on one oscilloscope. | The restructure; now permanently guarded by `test_core_never_references_an_instrument`. | `MockTransport` accepts any `Responder`; each driver declares `SIMULATOR_CLASS`, and `open_transport` takes a `responder_factory`. |
| D-05 | The TDS3014B simulator's identification string became a module-level constant rather than the class attribute the base class reads, so `sim://` reported the generic identity while behaving as an oscilloscope. | Smoke-testing the restructured driver. | Declared as a class attribute; covered by `test_bare_sim_resource_uses_the_driver_simulator`. |
| D-06 | A run against a bench whose every resource was `sim://` was reported as not simulated, because only the explicit `--simulate` flag was recorded. Simulated numbers would have been presented as hardware measurements. | Writing `test_simulation_is_disclosed`. | `Bench.is_simulated` also returns true when no configured resource is real hardware; a mixed bench remains a hardware run. |

D-01 and D-06 are the significant ones. D-01 is the class of defect this kind of
driver is most prone to — a framing error that is silent for most data and wrong
for some. D-06 is an evidence-integrity defect rather than a functional one, which
is exactly the kind that survives functional testing.

## 8. Items not covered by unit verification

The following require physical hardware and are listed as bench confirmation items
in the VISA determination report §5.1:

| Item | Reason |
|---|---|
| Which VXI-11 logical device name the unit accepts | Firmware-dependent |
| Whether the portmapper answers on TCP, UDP or both | Firmware-dependent |
| Whether the installed firmware offers `HARDCopy:FORMat PNG` | Firmware-dependent |
| Measurement engine settling time | Firmware- and timebase-dependent |
| Exact SCPI command spellings against the programmer manual | The manual was unreachable from the build environment (CON-02) |
| Analogue accuracy, bandwidth and noise behaviour | Instrument specification, not software |
| Pico 2 thermometer with a sensor attached: a real `rd temperature` value to two places, I2C timing with the module's pull-ups, measured accuracy against a reference | No SHT30-D module was connected (CON-09). The firmware has run on a real Pico 2 without one: USB enumeration, every `rd` option, the `NAK`, the `err` replies and `ecureset` were confirmed on 2026-10-03 (TB-SWE4-002 §13A.7). `docs/pico_sht30/Pico_SHT30_Notes.md` §7, PICO-OPEN-02 … -04 and -06 |
| Drive discovery for `benchtools thermo flash` on Linux and macOS | The bench PC runs Windows. Reflashing on Windows was confirmed on a real Pico 2 on 2026-10-03 (PICO-OPEN-05, closed), including with the `rd` firmware of #131; `docs/pico_sht30/Pico_SHT30_Notes.md` §7 |
| TTi 1604 against a physical meter: the frame terminator, the echo's place in the stream, the frequency gate times, key behaviour in remote mode, a USB converter's DTR/RTS levels, the resistance display convention | No meter was attached to the build environment (CON-10); `docs/dmm/TTi1604_Notes.md` §5, DMM-OPEN-01 … -08. Exercised by SWE4-UT-DMMBENCH (§4.6a) and the front-panel check when a meter is attached |
| Behaviour of instrument families named for future work | No drivers exist yet (CON-03) |

---

## 9. Review & Approval

| Role | Name | Signature / Electronic Approval | Date |
|---|---|---|---|
| Author | Claude | Approved | 2026-09-19 |
| Technical Reviewer | Dermot Murphy | — | *pending* |
| Quality Assurance | Dermot Murphy | — | *pending* |
| Approver | Dermot Murphy | — | *pending* |

> **Note:** This document is under configuration management (SUP.8). Post-approval changes require a change request (SUP.10) and a new document version.
