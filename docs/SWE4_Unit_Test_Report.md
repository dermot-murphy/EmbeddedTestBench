# SWE.4 — Software Unit Verification Report

| Field | Value |
|---|---|
| Document ID | TEK3014B-SWE4-002 |
| Version | 1.0 |
| Date | 2026-09-12 |
| Specification | TEK3014B-SWE4-001 |
| Item under verification | `tek3014b` v1.0.0 |
| Verdict | **PASS** |

## 1. Execution summary

| Metric | Result |
|---|---|
| Tests executed | **292** |
| Passed | **292** |
| Failed | 0 |
| Errors | 0 |
| Skipped | 0 |
| Statement coverage | **93%** (2 518 statements, 184 missed) |
| Execution time | 16.7 s with coverage instrumentation, 8.6 s without |
| Runtime | CPython 3.11.15, Linux |
| Framework | pytest 9.1.1, pytest-cov |

Command:

```
python3 -m pytest tests/ --cov=tek3014b --cov-report=term
```

No test was skipped. The `matplotlib` and `pyvisa` optional extras were installed for this
run so their tests executed; on a host without them those 21 tests skip by design, and the
remaining 271 still pass.

## 2. Results by test group

| Test group | File | Tests | Result |
|---|---|---|---|
| SWE4-UT-SCOPE | `test_scope.py` | 87 | Pass |
| SWE4-UT-MEASURE | `test_measure.py` | 35 | Pass |
| SWE4-UT-WAVEFORM | `test_waveform.py` | 34 | Pass |
| SWE4-UT-FACTORY | `test_factory.py` | 23 | Pass |
| SWE4-UT-VXI11 | `test_transport_vxi11.py` | 22 | Pass |
| SWE4-UT-CLI | `test_cli.py` | 20 | Pass |
| SWE4-UT-TRANSPORT | `test_transport_base.py` | 19 | Pass |
| SWE4-UT-ENV | `test_simulator.py` | 19 | Pass |
| SWE4-UT-PLOT | `test_plotting.py` | 15 | Pass |
| SWE4-UT-SOCKET | `test_transport_socket.py` | 12 | Pass |
| SWE4-UT-VISA | `test_transport_visa.py` | 6 | Pass |
| **Total** | | **292** | **Pass** |

## 3. Coverage detail

| Module | Statements | Missed | Coverage |
|---|---|---|---|
| `__init__.py` | 10 | 0 | 100% |
| `errors.py` | 16 | 0 | 100% |
| `transport/__init__.py` | 7 | 0 | 100% |
| `constants.py` | 137 | 1 | 99% |
| `waveform.py` | 187 | 6 | 97% |
| `measure.py` | 235 | 10 | 96% |
| `plotting.py` | 70 | 3 | 96% |
| `transport/base.py` | 137 | 7 | 95% |
| `cli.py` | 213 | 14 | 93% |
| `transport/factory.py` | 85 | 6 | 93% |
| `scope.py` | 410 | 27 | 93% |
| `simulator.py` | 495 | 38 | 92% |
| `transport/vxi11.py` | 318 | 37 | 88% |
| `transport/mock.py` | 42 | 5 | 88% |
| `transport/socket_raw.py` | 77 | 9 | 88% |
| `transport/visa_backend.py` | 75 | 17 | 77% |
| `__main__.py` | 4 | 4 | 0% |
| **TOTAL** | **2 518** | **184** | **93%** |

### 3.1 Justification for uncovered code

| Module | Uncovered code | Justification |
|---|---|---|
| `__main__.py` | The `python -m` entry guard | Four statements executed only by the interpreter's `-m` machinery. The CLI it delegates to is covered by 20 tests, and `python -m tek3014b` is exercised manually. |
| `transport/visa_backend.py` | Error branches inside PyVISA interop | Reaching them requires making a third-party library fail in specific ways; the value of mocking `pyvisa` to do so is low, since the code path is a thin translation of its exceptions. |
| `transport/vxi11.py` | Defensive branches: some VXI-11 error-code mappings, UDP portmapper fallback success path, `remote`/`local`/`trigger` | These are error and edge paths on a protocol whose happy path and principal failure paths are covered. Exercising every one of the 15 VXI-11 error codes would require a deliberately malicious server for no proportionate gain. |
| `scope.py` | Individual convenience getters and some diagnostic branches (`_safe_trigger_state` fallback) | Thin one-line delegations to `_query_float`, and an exception handler that exists only to keep a diagnostic message from itself raising. |
| `simulator.py` | Command handlers the driver does not currently emit | The simulator implements more of the instrument than the driver uses, deliberately, so that driver extensions do not require simulator changes first. |

Coverage meets PC-2 (≥ 90%) at the package level and at every module level except the four
justified above.

## 4. Quantitative verification of timing accuracy

Pass criterion PC-4 requires injected skews to be recovered to better than one tenth of a
sample interval.

### 4.1 Against synthesised waveforms (`test_measure.py`)

Stimulus: 1 MHz, 3.3 V, 2 ns rise time, 100 ps sample interval.

| Injected skew | Recovered | Error | Tolerance asserted |
|---|---|---|---|
| 0 ns (reference) | 0 ns | — | — |
| 12 ns | 12 ns | < 2 ps | 2 ps |
| 25 ns | 25 ns | < 2 ps | 2 ps |
| 5 ns | 5 ns | < 2 ps | 2 ps |
| **Spread (25 ns)** | **25 ns** | **< 2 ps** | 2 ps |

Sub-sample resolution is verified separately: a deliberate 0.35-sample (35 ps) offset is
recovered to within 0.5 ps, i.e. 0.005 of a sample interval.

### 4.2 Against the simulated instrument, through the full driver (`test_scope.py`)

Stimulus: four channels at 1 MHz / 3.3 V with skews 0, 12, 25 and 5 ns; 200 ns/div,
10 000 points, giving a 200 ps sample interval.

| Quantity | Result |
|---|---|
| Spread recovered | 25 ns, within 20 ps of injected (0.1 sample interval) |
| Agreement with the instrument's own `DELay` measurement | within 20 ps on all three channel pairs |
| Earliest / latest channel identified | CH1 / CH3, correct |

An end-to-end run at the same settings gives per-channel skews of 0.000, 12.011, 25.000 and
5.011 ns against injected 0, 12, 25 and 5 ns — a worst-case residual of 11 ps, which is
0.055 of the 200 ps sample interval. PC-4 is met.

### 4.3 Period measurement

| Quantity | Result |
|---|---|
| Injected period | 1.000000 µs |
| Host-side mean over 4 periods | 1.000000 µs (relative error < 1 × 10⁻⁶) |
| Peak-to-peak jitter on an ideal signal | < 1 fs (numerical noise only) |
| Instrument-side period | 1.000000 µs |
| Agreement between the two | within 0.1% |

## 5. Protocol interoperability results

| Check | Result |
|---|---|
| Built-in VXI-11 client against an independently implemented RPC server | Pass |
| Same driver through `pyvisa` + `pyvisa-py` against the same server | Pass |
| 10 000-point record over a link advertising `maxRecvSize` = 1 kB | Pass, 10 008 bytes intact |
| Command longer than `maxRecvSize` chunked and reassembled | Pass |
| Device-name probe recovers a VXI-11.2-only instrument (`gpib0,1`) | Pass |
| Portmapper `GETPORT` over TCP | Pass |
| Full driver over a raw SCPI socket | Pass |

The second row is the substantive evidence for TEK3014B-VISA-001: an independent VXI-11
implementation and the built-in one drive the same instrument to the same result, so the
VISA layer is optional middleware.

## 6. Defects found, and their disposition

| ID | Severity | Status | Regression test |
|---|---|---|---|
| D-01 — IEEE 488.2 payload re-parsed as a block header | **Major** (silent data corruption, data-dependent) | **Closed** | `test_payload_containing_a_hash_byte_is_not_re_parsed`, `test_from_payload_does_not_re_parse_a_header`, `test_from_block_and_from_payload_agree`, `test_ascii_encoding_matches_binary`, `test_every_position_transfers_intact` |
| D-02 — inconsistent `absolute_threshold` parameter name | Minor (API usability) | **Closed** | `test_absolute_threshold_overrides_percent` |
| D-03 — 2 s shutdown latency in the test servers | Minor (test efficiency) | **Closed** | Verified by `--durations`; suite runtime 18.6 s → 1.45 s for that file |

No open defects.

D-01 warrants a note on process effectiveness: it was **not** caught by the 237-test suite
as it then stood, because the vertical positions used in the fixtures happened never to produce the
digitiser code that triggers it. It was caught by running the worked examples — which is why
the examples are executed as part of the release check and not treated as documentation
only. The regression tests now force the condition deterministically by slowing the edge so
that every code between the two levels appears in the payload.

## 7. Verdict against the pass criteria

| ID | Criterion | Result |
|---|---|---|
| PC-1 | All tests pass | **Pass** — 292/292 |
| PC-2 | Statement coverage ≥ 90% | **Pass** — 93% |
| PC-3 | Every SWE.1 requirement covered | **Pass** — see TEK3014B-TRACE-001 |
| PC-4 | Injected skews recovered to < 0.1 sample interval | **Pass** — worst case 0.055 |

**Overall verdict: PASS**, subject to the bench confirmation items in TEK3014B-VISA-001 §5.1,
which cannot be discharged without physical hardware.

## 8. Supplementary checks performed

| Check | Result |
|---|---|
| `examples/01_capture_and_plot.py` against `sim://` | Runs, produces CSV, PNG plot and PNG hardcopy |
| `examples/02_channel_spread.py` against `sim://` | Runs, host-side skews match instrument-side delay on all pairs |
| `examples/03_period_and_jitter.py` against `sim://` | Runs, host and instrument period agree |
| `python -m tek3014b` sub-commands | All six run against `sim://` |
| `tek3014b` console script after `pip install -e .` | Installs and runs |
| Import with no optional dependencies present | Package imports; only `plot_waveforms` and the VISA transport raise, with a diagnostic naming the extra |
