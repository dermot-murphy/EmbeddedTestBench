# SWE.4 — Software Unit Verification Specification

| Field | Value |
|---|---|
| Document ID | BENCHTOOLS-SWE4-001 |
| Version | 2.0 |
| Date | 2026-09-13 |
| Process reference | Automotive SPICE V4.0, SWE.4 Software Unit Verification |

## 1. Verification strategy

### 1.1 Method

Automated unit and integration tests executed with `pytest`. Every test runs
without instrument hardware; no test is skipped for lack of it. Tests skip only
when an optional dependency is absent (`matplotlib`, `pyvisa`, `pyyaml`), which is
the correct behaviour for an optional extra.

### 1.2 Test environment

| Item | Value |
|---|---|
| Language / runtime | CPython 3.11.15 (minimum supported: 3.8) |
| Framework | `pytest` with `pytest-cov` |
| Instrument substitute | `benchtools.core.simulator.SimulatedInstrument` and its subclasses, behind `MockTransport` |
| VXI-11 substitute | `tests/core/transport/vxi11_server.py` — an ONC-RPC server on a loopback socket |
| Socket substitute | `tests/core/transport/scpi_socket_server.py` — line-oriented SCPI over loopback TCP |
| Optional extras exercised | `matplotlib`, `pyvisa` + `pyvisa-py`, `pyyaml` |

### 1.3 Independence of the oracle

Three measures ensure tests do not merely confirm the code agrees with itself:

1. **The RPC test server is an independent implementation.** It encodes and
   decodes the wire format with its own `struct` calls and does not import the
   client's codec. A passing test means two independent implementations agree on
   bytes.
2. **Simulators compute measurements analytically.** Values returned by a
   simulated measurement subsystem are derived from the signal model parameters,
   not from the sampled record, so host-side analysis is checked against an
   independent reference.
3. **Cross-validation between computation paths.** Host-side analysis is compared
   against the simulated instrument's own measurement engine
   (`test_spread_skews_match_the_instrument_delay_measurement`), and the built-in
   VXI-11 transport is compared against PyVISA's independent implementation over
   the same server.

### 1.4 Work-product verification

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

### 1.5 Architectural verification

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

### 1.6 Test selection rationale

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
| Round-trip testing | 488.2 block encode/decode, binary versus ASCII curve decoding, JSON report write/read |

### 1.7 Pass criteria

| ID | Criterion |
|---|---|
| PC-1 | All tests pass. |
| PC-2 | Statement coverage ≥ 90% (CORE-NFR-007). |
| PC-3 | Every requirement is covered by at least one test, or by a recorded inspection where a test is not the appropriate method. |
| PC-4 | Timing measurements recover injected skews to better than one tenth of a sample interval. |
| PC-5 | The layering constraints of §1.5 hold. |
| PC-6 | The work-product consistency checks of §1.4 hold. |

## 2. Test groups

| Test ID | File | Purpose | Requirements verified |
|---|---|---|---|
| SWE4-UT-LAYERING | `test_layering.py` | Import graph and element isolation | CORE-NFR-001, -008, -009 |
| SWE4-UT-TRACE | `test_traceability.py` | Consistency between the code and the SWE.1 to SWE.4 work products: every requirement traced, no orphan rows, every cited identifier defined, every module carrying its own trace | All (traceability base practices) |
| SWE4-UT-SCPI | `core/test_scpi.py` | `ScpiInstrument`: lifecycle, primitives, identity, error queue, 488.2 blocks, simulator injection | CORE-FR-020 .. -028, INST-FR-001, -002 |
| SWE4-UT-SIMBASE | `core/test_simulator.py` | Shared simulator harness: dispatch, compound messages, event queue, binary replies, subclassing | CORE-FR-040, -041 |
| SWE4-UT-VALIDATE | `core/test_validation.py` | Range, channel and choice validation; the enumeration base | CORE-FR-030, -031, CORE-NFR-004 |
| SWE4-UT-TRANSPORT | `core/transport/test_base.py` | Message framing, buffering, stale-response discard, lifecycle, timeouts | CORE-FR-005, -007, CORE-NFR-005, -006 |
| SWE4-UT-VXI11 | `core/transport/test_vxi11.py` | VXI-11 client at wire level against an independent RPC server | CORE-FR-001, -002, -007, -008 |
| SWE4-UT-SOCKET | `core/transport/test_socket.py` | Raw socket transport; length-bounded and idle-bounded reads | CORE-FR-003 |
| SWE4-UT-VISA | `core/transport/test_visa.py` | PyVISA transport against the same RPC server | CORE-FR-006, CORE-NFR-003 |
| SWE4-UT-FACTORY | `core/transport/test_factory.py` | Resource parsing; VXI-11 is the default; VISA is opt-in; backend registry | CORE-FR-010, -011 |
| SWE4-UT-WAVEFORM | `analysis/test_waveform.py` | Code decoding, scaling, clipping, CSV export, the four constructors | ANA-FR-001 .. -005 |
| SWE4-UT-MEASURE | `analysis/test_measure.py` | Levels, edges, interpolation, hysteresis, period, width, rise time, N-channel spread | ANA-FR-010 .. -017 |
| SWE4-UT-PLOT | `analysis/test_plotting.py` | Rendering, spread annotation, missing-dependency diagnostic | ANA-FR-020, -021, CORE-NFR-003 |
| SWE4-UT-SCOPE | `instruments/tek3014b/test_scope.py` | Driver behaviour and emitted SCPI; validation; acquisition; capture; measurement; hardcopy; errors | SCOPE-FR-010 .. -101, INST-FR-003 |
| SWE4-UT-ENV | `instruments/tek3014b/test_simulator.py` | Self-checks on the oscilloscope simulator | SCOPE-FR-090 |
| SWE4-UT-CLI | `instruments/tek3014b/test_cli.py` | Scope sub-commands end to end; argument expansion; exit statuses | SCOPE-FR-100 |
| SWE4-UT-LIMITS | `runner/test_limits.py` | Every limit form, construction validation, rendering | RUN-FR-020 .. -023 |
| SWE4-UT-RESOLVE | `runner/test_resolve.py` | Result path resolution and its failure messages | RUN-FR-013 |
| SWE4-UT-SPEC | `runner/test_spec.py` | Specification parsing and every malformed form | RUN-FR-010 .. -015 |
| SWE4-UT-BENCH | `runner/test_bench.py` | Bench configuration, lazy connection, driver registry, simulation detection | RUN-FR-001 .. -006 |
| SWE4-UT-ENGINE | `runner/test_runner.py` | Execution, failure versus error, setup abort, skips, roll-up | RUN-FR-030 .. -035 |
| SWE4-UT-REPORT | `runner/test_report.py` | JSON, markdown and JUnit output | RUN-FR-040 .. -043 |
| SWE4-UT-RUNCLI | `runner/test_cli.py` | Runner command line and top-level dispatch | RUN-FR-050 .. -053 |

## 3. Notable individual test cases

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
| `test_clear_error_when_matplotlib_is_absent` | A missing optional extra produces a named diagnostic, not `ImportError`. |

## 4. Defects found by this verification

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

## 5. Items not covered by unit verification

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
| Behaviour of instrument families named for future work | No drivers exist yet (CON-03) |
