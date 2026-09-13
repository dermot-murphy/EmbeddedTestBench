# SWE.4 — Software Unit Verification Report

| Field | Value |
|---|---|
| Document ID | BENCHTOOLS-SWE4-002 |
| Version | 3.0 |
| Date | 2026-09-13 |
| Specification | BENCHTOOLS-SWE4-001 |
| Item under verification | `benchtools` 3.0.0 |
| Verdict | **PASS** |

## 1. Execution summary

| Metric | Result |
|---|---|
| Tests executed | **932** |
| Passed | **932** |
| Failed | 0 |
| Errors | 0 |
| Skipped | 0 |
| Statement coverage | **94%** (6 202 statements, 385 missed) |
| Execution time | 34.0 s with coverage instrumentation, 21.5 s without |
| Runtime | CPython 3.11.15, Linux |
| Framework | pytest 9.1.1, pytest-cov |

Command:

```
python3 -m pytest tests/ --cov=benchtools --cov-report=term
```

No test was skipped. The `matplotlib`, `pyvisa` and `pyyaml` optional extras were
installed for this run, so their tests executed.

The suite was also run with all extras blocked, to confirm the claim that the
package works without them: **883 passed, 28 skipped, 0 failed**. (The totals
differ from 932 because the runner command-line module is skipped as a whole
rather than test by test — the shipped specifications are YAML, so without
`pyyaml` there is nothing in that module to run. Its JSON equivalents are covered
in `test_spec.py`.) The whole J-Link driver runs in that configuration, which is
the evidence for JLINK-NFR-001.

No J-Link probe, target board, GDB or GDB Server was present for this run, and no
test needs one (PC-8): the probe is substituted at the GDB/MI boundary, and the
RTT and SWO sockets are substituted by a loopback server.

## 2. Results by test group

| Test group | File | Tests | Result |
|---|---|---|---|
| SWE4-UT-SCOPE | `instruments/tek3014b/test_scope.py` | 87 | Pass |
| SWE4-UT-JLINK | `instruments/jlink/test_probe.py` | 70 | Pass |
| SWE4-UT-LAYERING | `test_layering.py` | 54 | Pass |
| SWE4-UT-GDBMI | `instruments/jlink/test_gdbmi.py` | 37 | Pass |
| SWE4-UT-BENCH | `runner/test_bench.py` | 37 | Pass |
| SWE4-UT-MEASURE | `analysis/test_measure.py` | 35 | Pass |
| SWE4-UT-SPEC | `runner/test_spec.py` | 35 | Pass |
| SWE4-UT-WAVEFORM | `analysis/test_waveform.py` | 34 | Pass |
| SWE4-UT-JLINKSERVER | `instruments/jlink/test_server.py` | 32 | Pass |
| SWE4-UT-SCPI | `core/test_scpi.py` | 28 | Pass |
| SWE4-UT-TIMING | `instruments/jlink/test_timing.py` | 29 | Pass |
| SWE4-UT-JLINKSIM | `instruments/jlink/test_simulator.py` | 23 | Pass |
| SWE4-UT-JLINKCLI | `instruments/jlink/test_cli.py` | 22 | Pass |
| SWE4-UT-RTT | `instruments/jlink/test_rtt.py` | 21 | Pass |
| SWE4-UT-SWO | `instruments/jlink/test_swo.py` | 20 | Pass |
| SWE4-UT-INSTRUMENT | `core/test_instrument.py` | 20 | Pass |
| SWE4-UT-GDBSESSION | `instruments/jlink/test_session.py` | 18 | Pass |
| SWE4-UT-TRACE | `test_traceability.py` | 18 | Pass |
| SWE4-UT-PROCESS | `core/transport/test_process.py` | 18 | Pass |
| SWE4-UT-JLINKSOCKETS | `instruments/jlink/test_sockets.py` | 16 | Pass |
| SWE4-UT-ENGINE | `runner/test_runner.py` | 25 | Pass |
| SWE4-UT-VALIDATE | `core/test_validation.py` | 23 | Pass |
| SWE4-UT-FACTORY | `core/transport/test_factory.py` | 23 | Pass |
| SWE4-UT-LIMITS | `runner/test_limits.py` | 23 | Pass |
| SWE4-UT-SIMBASE | `core/test_simulator.py` | 22 | Pass |
| SWE4-UT-VXI11 | `core/transport/test_vxi11.py` | 22 | Pass |
| SWE4-UT-CLI | `instruments/tek3014b/test_cli.py` | 20 | Pass |
| SWE4-UT-REPORT | `runner/test_report.py` | 20 | Pass |
| SWE4-UT-TRANSPORT | `core/transport/test_base.py` | 19 | Pass |
| SWE4-UT-ENV | `instruments/tek3014b/test_simulator.py` | 19 | Pass |
| SWE4-UT-PLOT | `analysis/test_plotting.py` | 15 | Pass |
| SWE4-UT-RUNCLI | `runner/test_cli.py` | 15 | Pass |
| SWE4-UT-RESOLVE | `runner/test_resolve.py` | 13 | Pass |
| SWE4-UT-SOCKET | `core/transport/test_socket.py` | 12 | Pass |
| SWE4-UT-VISA | `core/transport/test_visa.py` | 6 | Pass |
| **Total** | | **932** | **Pass** |

## 3. Coverage detail

| Element | Module | Statements | Missed | Coverage |
|---|---|---|---|---|
| CORE | `core/enums.py` | 20 | 0 | 100% |
| CORE | `core/errors.py` | 20 | 0 | 100% |
| CORE | `core/transport/constants.py` | 8 | 0 | 100% |
| CORE | `core/validation.py` | 33 | 0 | 100% |
| CORE | `core/instrument.py` | 82 | 2 | 98% |
| CORE | `core/simulator.py` | 93 | 5 | 95% |
| CORE | `core/transport/base.py` | 139 | 7 | 95% |
| CORE | `core/transport/factory.py` | 105 | 5 | 95% |
| CORE | `core/scpi.py` | 127 | 11 | 91% |
| CORE | `core/transport/mock.py` | 50 | 5 | 90% |
| CORE | `core/transport/process.py` | 131 | 14 | 89% |
| CORE | `core/transport/socket_raw.py` | 77 | 9 | 88% |
| CORE | `core/transport/vxi11.py` | 318 | 37 | 88% |
| CORE | `core/transport/visa_backend.py` | 75 | 17 | 77% |
| ANA | `analysis/waveform.py` | 164 | 4 | 98% |
| ANA | `analysis/measure.py` | 235 | 10 | 96% |
| ANA | `analysis/plotting.py` | 70 | 3 | 96% |
| INST | `instruments/generic.py` | 7 | 0 | 100% |
| SCOPE | `instruments/tek3014b/constants.py` | 121 | 0 | 100% |
| SCOPE | `instruments/tek3014b/scope.py` | 326 | 17 | 95% |
| SCOPE | `instruments/tek3014b/cli.py` | 213 | 14 | 93% |
| SCOPE | `instruments/tek3014b/simulator.py` | 442 | 35 | 92% |
| JLINK | `instruments/jlink/gdbmi.py` | 215 | 3 | 99% |
| JLINK | `instruments/jlink/constants.py` | 65 | 1 | 98% |
| JLINK | `instruments/jlink/server.py` | 121 | 4 | 97% |
| JLINK | `instruments/jlink/rtt.py` | 233 | 9 | 96% |
| JLINK | `instruments/jlink/swo.py` | 214 | 9 | 96% |
| JLINK | `instruments/jlink/timing.py` | 81 | 4 | 95% |
| JLINK | `instruments/jlink/cli.py` | 191 | 18 | 91% |
| JLINK | `instruments/jlink/probe.py` | 640 | 61 | 90% |
| JLINK | `instruments/jlink/session.py` | 159 | 16 | 90% |
| JLINK | `instruments/jlink/simulator.py` | 473 | 46 | 90% |
| RUN | `runner/limits.py` | 81 | 0 | 100% |
| RUN | `runner/results.py` | 106 | 0 | 100% |
| RUN | `runner/report.py` | 138 | 1 | 99% |
| RUN | `runner/spec.py` | 139 | 2 | 99% |
| RUN | `runner/bench.py` | 131 | 2 | 98% |
| RUN | `runner/cli.py` | 94 | 3 | 97% |
| RUN | `runner/runner.py` | 139 | 5 | 96% |
| RUN | `runner/resolve.py` | 37 | 2 | 95% |
| — | `cli.py` | 39 | 0 | 100% |
| — | `__main__.py` | 4 | 4 | 0% |
| **TOTAL** | | **6 202** | **385** | **94%** |

The `__init__.py` files (54 statements, all covered) are omitted for brevity; `__main__.py` is discussed below.

### 3.1 Justification for uncovered code

| Module | Uncovered code | Justification |
|---|---|---|
| `__main__.py` | The `python -m` entry guard | Four statements executed only by the interpreter's `-m` machinery. The CLI it delegates to is covered, and `python -m benchtools` is exercised manually. |
| `transport/visa_backend.py` | Error branches inside PyVISA interop | Reaching them means making a third-party library fail in specific ways; the code is a thin translation of its exceptions. |
| `transport/vxi11.py` | Some VXI-11 error-code mappings, the UDP portmapper success path, `remote`/`local` edge cases | Error paths on a protocol whose happy path and principal failure paths are covered. Exercising all 15 error codes would need a deliberately malicious server. |
| `transport/socket_raw.py`, `mock.py` | Defensive guards after `_require_open` | Unreachable unless an invariant is already broken. |
| `instruments/tek3014b/*` | Convenience getters and diagnostic fallbacks | Thin delegations, and an exception handler that exists only to stop a diagnostic message from itself raising. |
| `instruments/tek3014b/simulator.py` | Command handlers the driver does not currently emit | The simulator implements more of the instrument than the driver uses, deliberately, so driver extensions do not require simulator changes first. |
| `core/transport/process.py` | Reader-thread races and pipe-closed guards | Reached only when a pipe closes between a `select`-free read and its completion. Marked `pragma: no cover` where genuinely unreachable in-process. |
| `instruments/jlink/probe.py` | Best-effort cleanup paths, and `monitor` fallbacks for GDB versions that answer differently | Each is an `except BenchToolsError` around a tidy-up step whose failure must not replace the real error. Provoking them means making the simulator fail in a way real GDB does not. |
| `instruments/jlink/session.py`, `rtt.py`, `swo.py` | Socket and transport error branches | The happy path and the principal failures (unreachable port, dead GDB, timeout) are covered against a loopback server; the remainder are `OSError` translations. |
| `instruments/jlink/simulator.py` | MI commands the driver does not currently issue | Same rationale as the oscilloscope simulator: it models more of GDB than the driver uses, so extending the driver does not begin with extending the simulator. |
| `instruments/jlink/cli.py` | Argument-error branches of sub-commands whose happy path is covered | Thin `argparse` plumbing; each is one `return 2`. |

Coverage meets PC-2 (≥ 90%) at package level and at every module level except the
four justified above.

## 4. Work-product and architectural verification results

### 4.1 Traceability consistency

| Check | Result |
|---|---|
| All 157 requirements declared in SWE.1 appear in the traceability matrix | Pass |
| The matrix contains no requirement SWE.1 does not define | Pass |
| Every requirement cited in a docstring is defined in SWE.1 | Pass |
| Every design unit cited in a docstring is a section of SWE.3 | Pass |
| Every architectural element cited in a docstring is defined in SWE.2 | Pass |
| Every test group cited in a test is declared in SWE.4-001 | Pass |
| Every source and test module carries a `Traces to` line | Pass |
| Every architectural decision in SWE.2 is traced in the matrix | Pass |

PC-6 is met. These checks found two live inconsistencies when first run — a test
module citing an undeclared group, and a fixture citing a group that had been
renamed — both fixed. That is the point: they are the failure mode that review
does not catch.

### 4.2 Architectural verification

| Check | Result |
|---|---|
| Every module's imports respect the layering (parametrised over all 49 sources) | Pass |
| `benchtools.core` references no instrument, checked over code identifiers | Pass |
| `benchtools.core` imports in a fresh interpreter with no other element loaded | Pass |
| `benchtools.analysis` imports without instruments or the runner | Pass |
| No module imports a third-party package at module level (CORE-NFR-001, JLINK-NFR-001) | Pass |
| Source discovery guard (the suite cannot pass on an empty file list) | Pass |

PC-5 and PC-9 are met. This is the check that keeps the shared core shareable as
the instruments named in CON-03 are added — and it has already paid: adding the
J-Link driver, which needs a process transport in the core and a non-SCPI
instrument base, moved code *into* the core without any instrument knowledge
leaking in with it.

The third-party import check is new in this revision. CORE-NFR-001 had until now
been verified by inspection and by the extras-blocked run; neither would catch a
module-level `import yaml` added to a module no test imports in that
configuration. It is now parsed for, over every module.

## 5. Quantitative verification of timing accuracy

PC-4 requires injected skews to be recovered to better than one tenth of a sample
interval.

### 5.1 Against synthesised waveforms

Stimulus: 1 MHz, 3.3 V, 2 ns rise time, 100 ps sample interval.

| Injected skew | Recovered | Error | Tolerance asserted |
|---|---|---|---|
| 0 ns (reference) | 0 ns | — | — |
| 12 ns | 12 ns | < 2 ps | 2 ps |
| 25 ns | 25 ns | < 2 ps | 2 ps |
| 5 ns | 5 ns | < 2 ps | 2 ps |
| **Spread (25 ns)** | **25 ns** | **< 2 ps** | 2 ps |

Sub-sample resolution is verified separately: a deliberate 0.35-sample (35 ps)
offset is recovered to within 0.5 ps, i.e. 0.005 of a sample interval.

### 5.2 Through the full driver, against the simulated instrument

Stimulus: four channels at 1 MHz / 3.3 V with skews 0, 12, 25 and 5 ns;
200 ns/div, 10 000 points, giving a 200 ps sample interval.

| Quantity | Result |
|---|---|
| Spread recovered | 25 ns, within 20 ps of injected (0.1 sample interval) |
| Agreement with the instrument's own `DELay` measurement | within 20 ps on all three channel pairs |
| Earliest / latest channel identified | CH1 / CH3, correct |
| End-to-end per-channel skews | 0.000, 12.011, 25.000, 5.011 ns against injected 0, 12, 25, 5 — worst residual 11 ps, i.e. 0.055 of a sample interval |

PC-4 is met.

### 5.3 Period measurement

| Quantity | Result |
|---|---|
| Injected period | 1.000000 µs |
| Host-side mean over 4 periods | 1.000000 µs (relative error < 1 × 10⁻⁶) |
| Peak-to-peak jitter on an ideal signal | < 1 fs (numerical noise only) |
| Instrument-side period | 1.000000 µs |
| Agreement between the two | within 0.1% |

## 6. Debug probe verification results

### 6.1 Timing between two lines of code

The simulated firmware places `sensor.c:40` and `sensor.c:75` exactly 64 000 core
cycles apart, which at the simulated 64 MHz core is exactly 1.000 ms. Five
repetitions of each method, through the driver:

| Method | Measured | Cycles | Resolution | Halts target | Trustworthy | Spread |
|---|---|---|---|---|---|---|
| CYCLE_COUNTER | 1000.000 µs | 64 000 | 0.0156 µs | Yes | Yes | 0 µs |
| TARGET_TIMER | 1000.000 µs | 64 000 | 0.0156 µs | Yes | Yes | 0 µs |
| SWO_ITM | 1000.000 µs | 64 000 | 0.0156 µs | **No** | Yes | 0 µs |
| HOST_CLOCK | 96.040 µs | — | 1000 µs | Yes | **No** | 33.8 µs |

Three independent routes to the injected figure — a DWT register read, two
firmware variables, and a decoded ITM timestamp stream — agree exactly, so the
scaling from ticks to seconds is confirmed by agreement between implementations
rather than against itself.

The fourth row is the point of JLINK-FR-065. The host clock is wrong by a factor
of ten and is *reported* as untrustworthy, because the interval is a tenth of the
method's resolution. A bench test asserting on that figure would be asserting on
scheduling noise, so `is_trustworthy` is asserted in the shipped example
specification (`specs/firmware_timing.yaml`) alongside the limit itself.

`SWO_ITM` recovers the interval with `halts_target` false: the measurement does not
stop the core, which is the only method usable on firmware that must keep running.

### 6.2 Probe operations against the simulated target

| Check | Result |
|---|---|
| Flash from ELF, reporting sections written | Pass — 17 280 bytes in 3 sections |
| Verify against the binary, per section | Pass; a mismatch raises and names the section |
| Verification over an empty section list | Reported as **not** matched, not as a pass |
| Reset halting at the vector, run, halt, step | Pass |
| Breakpoint by source location, function and address | Pass |
| Temporary and conditional breakpoints | Pass, including a condition containing spaces |
| Hardware breakpoint beyond the probe's envelope | Refused, naming the limit (4) |
| Watchpoints on write, read and either | Pass |
| Halt reason reported (breakpoint, watchpoint, step, signal, unknown) | Pass |
| Memory read and write, 8/16/32-bit and arbitrary length | Pass; a transfer longer than the probe's limit is split into several reads (tested with the limit lowered to 16 bytes, so the splitting is observable) |
| Variables by name — integer, string, address, size | Pass; memory and variable views agree |
| Call stack | Pass — 3 frames with function, file and line |
| RTT read, write, command/response, pattern match | Pass, without halting the core |
| RTT logging | Pass; written and flushed per line |
| RTT over a real TCP socket, arriving in fragments | Pass — lines reassembled |
| SWO over a real TCP socket | Pass — events decoded, `collect` honours its timeout |
| GDB Server: already-listening port reused, remote never spawned | Pass |
| GDB Server that exits during start-up | Reported with the server's own output |

## 7. Protocol interoperability results

| Check | Result |
|---|---|
| Built-in VXI-11 client against an independently implemented RPC server | Pass |
| Same driver through `pyvisa` + `pyvisa-py` against the same server | Pass |
| 10 000-point record over a link advertising `maxRecvSize` = 1 kB | Pass, 10 008 bytes intact |
| Command longer than `maxRecvSize` chunked and reassembled | Pass |
| Device-name probe recovers a VXI-11.2-only instrument (`gpib0,1`) | Pass |
| Portmapper `GETPORT` over TCP | Pass |
| Full driver over a raw SCPI socket | Pass |

The second row is the substantive evidence for the VISA determination: an
independent VXI-11 implementation and the built-in one drive the same instrument
to the same result, so the VISA layer is optional middleware.

The GDB/MI side has no equivalent second implementation available in the build
environment: correctness against real GDB is a bench confirmation item
(JLINK-OPEN-02). What is verified here is that the parser handles the grammar as
documented, including the constructs a naive parser gets wrong — see D-09.

## 8. Runner verification results

| Check | Result |
|---|---|
| A measurement outside its limit is reported as a failure, not an error | Pass |
| An unexecutable step is reported as an error, not a failure | Pass |
| JUnit XML keeps `<failure>` and `<error>` distinct | Pass |
| A setup failure aborts the suite and runs no test | Pass |
| Teardown runs after a failure | Pass |
| A test failure does not stop later tests; `--stop-on-error` does | Pass |
| A specification cannot invoke private driver methods | Pass |
| A missing bench instrument is reported before anything executes | Pass |
| A simulated run is disclosed in every report | Pass |
| Exit status 0 / 1 / 2 for pass / problem / usage | Pass |
| The shipped `specs/clock_skew.yaml` and both `benches/*.yaml` load and run | Pass |

## 9. Defects found, and their disposition

| ID | Severity | Status | Regression test |
|---|---|---|---|
| D-01 — IEEE 488.2 payload re-parsed as a block header | **Major** (silent, data-dependent corruption) | **Closed** | `test_payload_containing_a_hash_byte_is_not_re_parsed`, `test_from_payload_does_not_re_parse_a_header`, `test_from_block_and_from_payload_agree`, `test_ascii_encoding_matches_binary`, `test_every_position_transfers_intact` |
| D-02 — inconsistent `absolute_threshold` parameter name | Minor (API usability) | **Closed** | `test_absolute_threshold_overrides_percent` |
| D-03 — 2 s shutdown latency in the test servers | Minor (test efficiency) | **Closed** | Verified by `--durations` |
| D-04 — core transport depended on the oscilloscope simulator | **Major** (architectural; blocked reuse) | **Closed** | `test_core_never_references_an_instrument`, `test_core_is_importable_on_its_own`, `test_layer_dependencies_point_one_way` |
| D-05 — simulator identity string not read by the base class | Minor (wrong `*IDN?` under `sim://`) | **Closed** | `test_bare_sim_resource_uses_the_driver_simulator` |
| D-06 — an all-simulated bench was not reported as simulated | **Major** (evidence integrity) | **Closed** | `test_all_sim_resources_count_as_simulated`, `test_a_mixed_bench_is_not_simulated`, `test_simulation_is_disclosed`, `test_properties_record_the_bench` |
| D-07 — a scope CLI test asked for a plot without guarding on `matplotlib`, so the suite did not in fact pass with the optional extras absent (a **test** defect, not a product defect) | Minor | **Closed** | The test now skips without the extra; verified by the extras-blocked run in §1 |

| D-08 — `TimingResult` reported no resolution for the `TARGET_TIMER` method, and an unknown resolution was treated as trustworthy. A target-timer figure below one tick of the firmware's timer would have been presented as a measurement | **Major** (evidence integrity; JLINK-FR-065, JLINK-NFR-004) | **Closed** | `TestResolutionIsAlwaysReported` (6), notably `test_the_target_timer_resolves_its_own_rate_not_the_core_clock`, `test_an_unknown_resolution_is_not_trusted`, `test_every_method_reports_a_resolution_through_the_probe` |
| D-09 — the ITM decoder classified a source packet by bit 0 of its header instead of the two-bit size field, so every 16-bit ITM write was read as a protocol packet and silently dropped | **Major** (silent data loss on hardware) | **Closed** | `TestSourcePackets` — the 1-, 2- and 4-byte cases |
| D-10 — `RttClient.history` returned only the lines not yet consumed by a read, while documented and used as the complete log. An RTT log would have been missing exactly the lines a test had examined | **Major** (evidence integrity) | **Closed** | `test_history_survives_consuming_reads`, `test_pending_count` |
| D-11 — the simulated probe split `-break-insert` arguments on whitespace, truncating a condition such as `sensor_count > 3` to `sensor_count`, so conditional breakpoints appeared to work while ignoring their condition | Minor (**test double** defect; would have masked a driver defect) | **Closed** | `test_conditional_breakpoint` |
| D-12 — the simulated probe reported `type="breakpoint"` for hardware breakpoints as well as software ones, so the driver's hardware count was always zero and the probe's four-breakpoint envelope could never be enforced | Minor (**test double** defect; disabled a real check) | **Closed** | `test_hardware_breakpoint_limit_is_enforced` |
| D-13 — `--simulate` gave every alias in a bench the oscilloscope driver, so a specification needing a probe failed several steps later on a missing method instead of at once | Minor (diagnosis quality) | **Closed** | `test_simulated_from_a_mapping_uses_the_right_driver`, `test_the_wrong_kind_of_instrument_is_reported` |
| D-14 — `jlink/server.py` had no tests at all: JLINK-FR-003 to -005 were implemented and traced but unverified, and three test names cited in the traceability matrix did not exist | Minor (**verification gap**, found by checking the matrix against the suite) | **Closed** | `SWE4-UT-JLINKSERVER` (32 tests) |

No open defects.

Notes on process effectiveness:

- **D-01 was not caught by the 237-test suite as it then stood**, because the
  vertical positions used in the fixtures happened never to produce the digitiser
  code that triggers it. It was caught by running the worked examples, which is
  why the examples are executed as part of the release check and not treated as
  documentation only.
- **D-06 would have survived any amount of functional testing**, because every
  function behaved correctly; only the report's claim about provenance was wrong.
  It was caught by writing a test that asked what the report *says*, not what the
  code *does*.
- **D-07 was found by actually running the suite with the extras removed**, rather
  than assuming the skip markers were complete. CORE-NFR-001 and CORE-NFR-003 are
  claims about a configuration nobody develops in, so they are only credible if
  that configuration is exercised. It now is, and the figures are in §1. The same
  reasoning produced the parsed check described in §4.2, since the extras-blocked
  run cannot see a module no test imports.
- **D-08, D-09 and D-10 are the same defect in three places**: a figure or a log
  that is wrong in a way nothing visibly fails on. Each was caught by writing the
  test that asks what is *reported*, not whether the code runs. D-09 in particular
  would have dropped every 16-bit trace write on real hardware while passing every
  functional test, because the simulator and the decoder agreed with each other.
- **D-11 and D-12 were defects in the test double, not the product.** Both made a
  real check vacuous: a condition that was ignored, and an envelope that could
  never trip. A simulator that is too permissive is worse than no simulator,
  because the suite reports success. They are recorded here as defects for that
  reason, and each now has a test asserting the behaviour the driver depends on.
- **D-14 was found by checking the traceability matrix against the suite** — the
  matrix cited three tests that did not exist, because a module had been written
  and traced but never tested. The consistency checks of §4.1 do not catch that
  (they check identifiers, not test names), so this one was a manual cross-check;
  it is worth repeating per release.

## 10. Verdict against the pass criteria

| ID | Criterion | Result |
|---|---|---|
| PC-1 | All tests pass | **Pass** — 932/932 |
| PC-2 | Statement coverage ≥ 90% | **Pass** — 94% |
| PC-3 | Every requirement covered | **Pass** — see BENCHTOOLS-TRACE-001 |
| PC-4 | Injected skews recovered to < 0.1 sample interval | **Pass** — worst case 0.055 |
| PC-5 | Layering constraints hold | **Pass** |
| PC-6 | Work-product consistency checks hold | **Pass** |
| PC-7 | Every timing method recovers the injected 1.000 ms interval, except the host clock, which flags itself | **Pass** — §6.1 |
| PC-8 | No test requires a probe, target, debugger or GDB server | **Pass** — §1 |
| PC-9 | No module imports a third-party package at module level | **Pass** — §4.2 |

**Overall verdict: PASS**, subject to the bench confirmation items that cannot be
discharged without physical hardware: the VISA determination report §5.1 for the
oscilloscope, and `docs/jlink/JLink_Integration_Notes.md` §4 for the probe
(JLINK-OPEN-01 to JLINK-OPEN-04, of which the SWO timestamp scaling of CON-05 is
the one that could change a reported figure).

## 11. Supplementary checks performed

| Check | Result |
|---|---|
| `examples/01_capture_and_plot.py` | Runs; produces CSV, plot and hardcopy |
| `examples/02_channel_spread.py` | Runs; host-side skews match instrument-side delay on all pairs |
| `examples/03_period_and_jitter.py` | Runs; host and instrument period agree |
| `examples/04_run_bench_suite.py` | Runs; drives the shipped specification and writes a markdown report |
| `examples/05_jlink_firmware.py` | Runs against the simulated probe; flashes, verifies, reads RTT, variables and the call stack, and reports all four timing methods |
| `benchtools run specs/clock_skew.yaml --simulate` | 5 tests, all pass |
| `benchtools run specs/firmware_timing.yaml --simulate` | 6 tests, all pass in 1.01 s |
| The same against `benches/simulated.yaml --markdown` | Report written; FW-REQ-010/011/020/021 all pass, and the run is disclosed as simulated |
| The same against a bench whose `probe` alias is an oscilloscope | Exits 1 with `ERROR`: "the specification wants instrument 'probe' to be a JLinkProbe, but bench 'wrong' provides a Tek3014B" |
| `benchtools jlink info --resource sim://` and every other sub-command | All run; JSON on stdout |
| The same with a deliberately tightened limit | Exits 1, names the failing measurement and by how much |
| `benchtools` sub-commands `run`, `scope`, `drivers`, `backends` | All run |
| `python -m benchtools` | Runs |
| `benchtools` console script after `pip install -e .` | Installs and runs |
| Full suite with `matplotlib`, `pyvisa`, `pyyaml` and `numpy` blocked | 883 passed, 28 skipped, 0 failed |
| Import with those extras blocked | Package imports; only the plot, VISA and YAML paths raise, each naming its extra |
