# SWE.4 — Software Unit Verification Report

| Field | Value |
|---|---|
| Document ID | BENCHTOOLS-SWE4-002 |
| Version | 2.0 |
| Date | 2026-09-13 |
| Specification | BENCHTOOLS-SWE4-001 |
| Item under verification | `benchtools` 2.0.0 |
| Verdict | **PASS** |

## 1. Execution summary

| Metric | Result |
|---|---|
| Tests executed | **579** |
| Passed | **579** |
| Failed | 0 |
| Errors | 0 |
| Skipped | 0 |
| Statement coverage | **94%** (3 585 statements, 200 missed) |
| Execution time | 20.0 s with coverage instrumentation, 10.5 s without |
| Runtime | CPython 3.11.15, Linux |
| Framework | pytest 9.1.1, pytest-cov |

Command:

```
python3 -m pytest tests/ --cov=benchtools --cov-report=term
```

No test was skipped. The `matplotlib`, `pyvisa` and `pyyaml` optional extras were
installed for this run, so their tests executed.

The suite was also run with all three extras blocked, to confirm the claim that
the package works without them: **538 passed, 27 skipped, 0 failed**. (The totals
differ from 579 because the runner command-line module is skipped as a whole
rather than test by test — the shipped specifications are YAML, so without
`pyyaml` there is nothing in that module to run. Its JSON equivalents are covered
in `test_spec.py`.)

## 2. Results by test group

| Test group | File | Tests | Result |
|---|---|---|---|
| SWE4-UT-SCOPE | `instruments/tek3014b/test_scope.py` | 87 | Pass |
| SWE4-UT-LAYERING | `test_layering.py` | 41 | Pass |
| SWE4-UT-TRACE | `test_traceability.py` | 18 | Pass |
| SWE4-UT-MEASURE | `analysis/test_measure.py` | 35 | Pass |
| SWE4-UT-WAVEFORM | `analysis/test_waveform.py` | 34 | Pass |
| SWE4-UT-SPEC | `runner/test_spec.py` | 31 | Pass |
| SWE4-UT-BENCH | `runner/test_bench.py` | 29 | Pass |
| SWE4-UT-SCPI | `core/test_scpi.py` | 27 | Pass |
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
| **Total** | | **579** | **Pass** |

## 3. Coverage detail

| Element | Module | Statements | Missed | Coverage |
|---|---|---|---|---|
| CORE | `core/enums.py` | 20 | 0 | 100% |
| CORE | `core/errors.py` | 20 | 0 | 100% |
| CORE | `core/validation.py` | 33 | 0 | 100% |
| CORE | `core/transport/constants.py` | 8 | 0 | 100% |
| CORE | `core/simulator.py` | 93 | 5 | 95% |
| CORE | `core/transport/base.py` | 136 | 7 | 95% |
| CORE | `core/transport/factory.py` | 103 | 6 | 94% |
| CORE | `core/scpi.py` | 165 | 11 | 93% |
| CORE | `core/transport/vxi11.py` | 318 | 37 | 88% |
| CORE | `core/transport/mock.py` | 50 | 6 | 88% |
| CORE | `core/transport/socket_raw.py` | 77 | 9 | 88% |
| CORE | `core/transport/visa_backend.py` | 75 | 17 | 77% |
| ANA | `analysis/waveform.py` | 164 | 4 | 98% |
| ANA | `analysis/measure.py` | 235 | 10 | 96% |
| ANA | `analysis/plotting.py` | 70 | 3 | 96% |
| INST | `instruments/generic.py` | 7 | 0 | 100% |
| SCOPE | `instruments/tek3014b/constants.py` | 121 | 0 | 100% |
| SCOPE | `instruments/tek3014b/scope.py` | 327 | 17 | 95% |
| SCOPE | `instruments/tek3014b/cli.py` | 213 | 14 | 93% |
| SCOPE | `instruments/tek3014b/simulator.py` | 442 | 35 | 92% |
| RUN | `runner/limits.py` | 81 | 0 | 100% |
| RUN | `runner/results.py` | 106 | 0 | 100% |
| RUN | `runner/report.py` | 138 | 1 | 99% |
| RUN | `runner/spec.py` | 135 | 2 | 99% |
| RUN | `runner/bench.py` | 111 | 2 | 98% |
| RUN | `runner/cli.py` | 88 | 3 | 97% |
| RUN | `runner/runner.py` | 138 | 5 | 96% |
| RUN | `runner/resolve.py` | 37 | 2 | 95% |
| — | `cli.py` | 36 | 0 | 100% |
| — | `__main__.py` | 4 | 4 | 0% |
| **TOTAL** | | **3 585** | **200** | **94%** |

### 3.1 Justification for uncovered code

| Module | Uncovered code | Justification |
|---|---|---|
| `__main__.py` | The `python -m` entry guard | Four statements executed only by the interpreter's `-m` machinery. The CLI it delegates to is covered, and `python -m benchtools` is exercised manually. |
| `transport/visa_backend.py` | Error branches inside PyVISA interop | Reaching them means making a third-party library fail in specific ways; the code is a thin translation of its exceptions. |
| `transport/vxi11.py` | Some VXI-11 error-code mappings, the UDP portmapper success path, `remote`/`local` edge cases | Error paths on a protocol whose happy path and principal failure paths are covered. Exercising all 15 error codes would need a deliberately malicious server. |
| `transport/socket_raw.py`, `mock.py` | Defensive guards after `_require_open` | Unreachable unless an invariant is already broken. |
| `instruments/tek3014b/*` | Convenience getters and diagnostic fallbacks | Thin delegations, and an exception handler that exists only to stop a diagnostic message from itself raising. |
| `instruments/tek3014b/simulator.py` | Command handlers the driver does not currently emit | The simulator implements more of the instrument than the driver uses, deliberately, so driver extensions do not require simulator changes first. |

Coverage meets PC-2 (≥ 90%) at package level and at every module level except the
four justified above.

## 4. Work-product and architectural verification results

### 4.1 Traceability consistency

| Check | Result |
|---|---|
| All 108 requirements declared in SWE.1 appear in the traceability matrix | Pass |
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
| Every module's imports respect the layering (parametrised over all 37 sources) | Pass |
| `benchtools.core` references no instrument, checked over code identifiers | Pass |
| `benchtools.core` imports in a fresh interpreter with no other element loaded | Pass |
| `benchtools.analysis` imports without instruments or the runner | Pass |
| Source discovery guard (the suite cannot pass on an empty file list) | Pass |

PC-5 is met. This is the check that keeps the shared core shareable as the
instrument families named in CON-03 are added.

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

## 6. Protocol interoperability results

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

## 7. Runner verification results

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

## 8. Defects found, and their disposition

| ID | Severity | Status | Regression test |
|---|---|---|---|
| D-01 — IEEE 488.2 payload re-parsed as a block header | **Major** (silent, data-dependent corruption) | **Closed** | `test_payload_containing_a_hash_byte_is_not_re_parsed`, `test_from_payload_does_not_re_parse_a_header`, `test_from_block_and_from_payload_agree`, `test_ascii_encoding_matches_binary`, `test_every_position_transfers_intact` |
| D-02 — inconsistent `absolute_threshold` parameter name | Minor (API usability) | **Closed** | `test_absolute_threshold_overrides_percent` |
| D-03 — 2 s shutdown latency in the test servers | Minor (test efficiency) | **Closed** | Verified by `--durations` |
| D-04 — core transport depended on the oscilloscope simulator | **Major** (architectural; blocked reuse) | **Closed** | `test_core_never_references_an_instrument`, `test_core_is_importable_on_its_own`, `test_layer_dependencies_point_one_way` |
| D-05 — simulator identity string not read by the base class | Minor (wrong `*IDN?` under `sim://`) | **Closed** | `test_bare_sim_resource_uses_the_driver_simulator` |
| D-06 — an all-simulated bench was not reported as simulated | **Major** (evidence integrity) | **Closed** | `test_all_sim_resources_count_as_simulated`, `test_a_mixed_bench_is_not_simulated`, `test_simulation_is_disclosed`, `test_properties_record_the_bench` |
| D-07 — a scope CLI test asked for a plot without guarding on `matplotlib`, so the suite did not in fact pass with the optional extras absent (a **test** defect, not a product defect) | Minor | **Closed** | The test now skips without the extra; verified by the extras-blocked run in §1 |

No open defects.

Two notes on process effectiveness:

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
  that configuration is exercised. It now is, and the figures are in §1.

## 9. Verdict against the pass criteria

| ID | Criterion | Result |
|---|---|---|
| PC-1 | All tests pass | **Pass** — 579/579 |
| PC-2 | Statement coverage ≥ 90% | **Pass** — 94% |
| PC-3 | Every requirement covered | **Pass** — see BENCHTOOLS-TRACE-001 |
| PC-4 | Injected skews recovered to < 0.1 sample interval | **Pass** — worst case 0.055 |
| PC-5 | Layering constraints hold | **Pass** |
| PC-6 | Work-product consistency checks hold | **Pass** |

**Overall verdict: PASS**, subject to the bench confirmation items in the VISA
determination report §5.1, which cannot be discharged without physical hardware.

## 10. Supplementary checks performed

| Check | Result |
|---|---|
| `examples/01_capture_and_plot.py` | Runs; produces CSV, plot and hardcopy |
| `examples/02_channel_spread.py` | Runs; host-side skews match instrument-side delay on all pairs |
| `examples/03_period_and_jitter.py` | Runs; host and instrument period agree |
| `examples/04_run_bench_suite.py` | Runs; drives the shipped specification and writes a markdown report |
| `benchtools run specs/clock_skew.yaml --simulate` | 5 tests, all pass |
| The same with a deliberately tightened limit | Exits 1, names the failing measurement and by how much |
| `benchtools` sub-commands `run`, `scope`, `drivers`, `backends` | All run |
| `python -m benchtools` | Runs |
| `benchtools` console script after `pip install -e .` | Installs and runs |
| Full suite with `matplotlib`, `pyvisa` and `pyyaml` blocked | 538 passed, 27 skipped, 0 failed |
| Import with those extras blocked | Package imports; only the plot, VISA and YAML paths raise, each naming its extra |
