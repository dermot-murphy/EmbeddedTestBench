# SWE.4 — Software Unit Verification Specification

| Field | Value |
|---|---|
| Document ID | TEK3014B-SWE4-001 |
| Version | 1.0 |
| Date | 2026-09-12 |
| Process reference | Automotive SPICE V4.0, SWE.4 Software Unit Verification |

## 1. Verification strategy

### 1.1 Method

Automated unit and integration tests executed with `pytest`. Every test is runnable without
instrument hardware; no test is skipped for lack of hardware. Two tests skip only when an
optional dependency is absent (`matplotlib`, `pyvisa`), which is the correct behaviour for
an optional extra.

### 1.2 Test environment

| Item | Value |
|---|---|
| Language / runtime | CPython 3.11.15 (minimum supported: 3.8) |
| Framework | `pytest` with `pytest-cov` |
| Instrument substitute | `tek3014b.simulator.SimulatedTDS3014B` behind `MockTransport` |
| VXI-11 substitute | `tests/vxi11_server.py` — an ONC-RPC server on a loopback socket |
| Socket substitute | `tests/scpi_socket_server.py` — line-oriented SCPI over loopback TCP |
| Optional extras exercised | `matplotlib` (plots), `pyvisa` + `pyvisa-py` (VISA transport) |

### 1.3 Independence of the oracle

Two measures ensure tests do not merely confirm the code agrees with itself:

1. **The RPC test server is an independent implementation.** `tests/vxi11_server.py` encodes
   and decodes the wire format with its own `struct` calls; it does not import the client's
   codec. A passing test therefore means two independent implementations agree on bytes.
2. **The simulator computes measurements analytically.** Values returned by the simulated
   `MEASUrement` subsystem are derived from the `ChannelSignal` model parameters, not from
   the sampled record. Host-side analysis of the record is thus checked against an
   independent reference.

Additionally, host-side analysis is cross-checked against the simulated instrument's own
measurement engine (`test_spread_skews_match_the_instrument_delay_measurement`), so the two
computation paths must agree.

### 1.4 Test selection rationale

| Technique | Where applied |
|---|---|
| Equivalence partitioning | Channel numbers, encodings, transfer widths, resource-string forms |
| Boundary value analysis | Volts/div (1 mV, 10 V, just outside both), position (±5, ±6), time/div, record length, XDR payload lengths mod 4 |
| Error guessing / negative testing | Malformed blocks, truncated XDR, refused device names, unreachable portmapper, silent instrument, unparsable responses |
| Known-answer testing | Synthesised signals with exactly known period and skew; measured values compared to the injected values |
| Interface testing | Assertions on the exact SCPI emitted, because a misspelled command is silently ignored by real hardware |
| Regression testing | One test per defect found during development (see §4) |

### 1.5 Pass criteria

| ID | Criterion |
|---|---|
| PC-1 | All tests pass. |
| PC-2 | Statement coverage ≥ 90% (SWE1-NFR-007). |
| PC-3 | Every SWE.1 requirement is covered by at least one test (see the traceability matrix). |
| PC-4 | Timing measurements recover injected skews to better than one tenth of a sample interval. |

## 2. Test groups

| Test ID | File | Purpose | Requirements verified |
|---|---|---|---|
| SWE4-UT-VXI11 | `test_transport_vxi11.py` | VXI-11 client at wire level | SWE1-FR-001, -002, -006, -007, NFR-001 |
| SWE4-UT-VXI11-001 | " | XDR codec round-trips; padding at every length mod 4; truncation rejected | SWE1-FR-001 |
| SWE4-UT-VXI11-002 | " | Client drives an independently implemented RPC server over TCP | SWE1-FR-001 |
| SWE4-UT-VXI11-003 | " | Complete driver operates over a real VXI-11 socket | SWE1-FR-001, -050 |
| SWE4-UT-VXI11-004 | " | Portmapper `GETPORT` correctly formed; unreachable case reported | SWE1-FR-002 |
| SWE4-UT-VXI11-WIRE | `vxi11_server.py` | Independent RPC server (test apparatus, not a test) | — |
| SWE4-UT-TRANSPORT | `test_transport_base.py` | Message framing, buffering, stale-response discard, lifecycle, timeouts | SWE1-FR-006, NFR-005, NFR-006 |
| SWE4-UT-FACTORY | `test_factory.py` | Resource-string parsing; VXI-11 is the default; VISA is opt-in | SWE1-FR-004, -005 |
| SWE4-UT-SOCKET | `test_transport_socket.py` | Raw socket transport; length-bounded and idle-bounded reads | SWE1-FR-003 |
| SWE4-UT-VISA | `test_transport_visa.py` | PyVISA transport against the same RPC server | SWE1-FR-004, NFR-003 |
| SWE4-UT-WAVEFORM | `test_waveform.py` | Block parsing, code decoding, scaling, clipping, CSV export | SWE1-FR-051, -052, -053, -054, -055 |
| SWE4-UT-MEASURE | `test_measure.py` | Level estimation, edge detection, interpolation, hysteresis, period, width, rise time, N-channel spread | SWE1-FR-061..-066 |
| SWE4-UT-SCOPE | `test_scope.py` | Driver behaviour and emitted SCPI; validation; acquisition; capture; measurement; hardcopy; error handling | SWE1-FR-010..-043, -050, -060, -067, -080, -081, -101, NFR-004 |
| SWE4-UT-PLOT | `test_plotting.py` | Host-side rendering, spread annotation, missing-dependency diagnostic | SWE1-FR-070, -071, NFR-003 |
| SWE4-UT-CLI | `test_cli.py` | Every sub-command end to end; argument expansion; exit statuses | SWE1-FR-100 |
| SWE4-UT-ENV | `test_simulator.py` | Self-checks on the simulator itself | SWE1-FR-090 |

## 3. Notable individual test cases

| Test | What it pins down |
|---|---|
| `test_device_names_are_probed_in_order` | An instrument answering only to the VXI-11.2 name `gpib0,1` still connects, and `inst0` was tried first. |
| `test_large_transfer_is_reassembled` | A 10 000-point record arrives intact over a link advertising a 1 kB `maxRecvSize`. |
| `test_write_is_chunked_to_max_recv_size` | A command longer than `maxRecvSize` is split and correctly reassembled by the far end. |
| `test_write_discards_a_stale_response` | An unread previous response cannot be returned as the answer to a new query. |
| `test_read_exactly_allows_the_terminator_inside_binary_data` | Binary payloads containing `0x0A` are not truncated. |
| `test_payload_containing_a_hash_byte_is_not_re_parsed` | Regression for defect D-01 (§4): sample code 35 (`#`) is data, not a block header. |
| `test_ascii_encoding_matches_binary` | Both transfer encodings decode to identical digitiser codes. |
| `test_interpolation_beats_the_sample_interval` | A deliberate 0.35-sample delay is resolved to within 0.5 ps, proving sub-sample resolution. |
| `test_spread_equals_the_injected_skew` | Measured spread equals the injected skew to within 2 ps. |
| `test_spread_skews_match_the_instrument_delay_measurement` | Host-side analysis agrees with the instrument's own two-source delay measurement. |
| `test_nothing_is_sent_when_validation_fails` | A rejected setting leaves the instrument untouched (SWE1-NFR-004). |
| `test_no_trigger_times_out_with_a_useful_message` | An absent trigger produces `AcquisitionTimeoutError` naming the likely cause. |
| `test_unsupported_format_falls_back` | Firmware that silently ignores `HARDCopy:FORMat PNG` still yields an image. |
| `test_clear_error_when_matplotlib_is_absent` | A missing optional extra produces `OptionalDependencyError`, not `ImportError`. |
| `test_refused_connection_mentions_the_tds3014b_limitation` | The raw-socket failure message redirects the user to VXI-11. |

## 4. Defects found by this verification

| ID | Defect | Detected by | Resolution |
|---|---|---|---|
| D-01 | `Waveform.from_block` re-parsed a payload whose IEEE 488.2 header had already been consumed by the driver. Benign whenever the payload contained no `0x23` byte, but corrupted or failed the transfer when a sample code equalled 35. Data-dependent, therefore intermittent on real hardware. | Running `examples/01_capture_and_plot.py`, which used a vertical position that produced code 35 on the rising edge. Not caught by the initial test suite, whose vertical positions happened to avoid that code. | De-framing separated from decoding: `Waveform.from_payload` (no header parsing) is used by the driver; `from_block` retained for complete blocks. `from_ascii` added for the ASCII encoding, which was also unhandled. Regression tests added with the edge slowed so every code is guaranteed to appear, rather than relying on chance. |
| D-02 | `threshold_for()` took `absolute=` while every public function took `absolute_threshold=`. | Writing `test_absolute_threshold_overrides_percent`. | Parameter renamed for consistency across the API. |
| D-03 | The loopback test servers took 2 s each to shut down: closing a listening socket does not wake a thread blocked in `accept()`. Suite runtime 18.6 s. | Profiling with `--durations`. | Listening sockets given a 0.1 s poll timeout. Suite runtime 1.45 s for that file. |

D-01 is the significant one. It is recorded here in full because it is the class of defect
this kind of driver is most prone to — a framing error that is silent for most data and
wrong for some — and because it justifies the design split now documented in
SWE3-DD-WAVEFORM and AD-03.

## 5. Items not covered by unit verification

The following require physical hardware and are listed as bench confirmation items in
TEK3014B-VISA-001 §5.1:

| Item | Reason |
|---|---|
| Which VXI-11 logical device name the unit accepts | Firmware-dependent |
| Whether the portmapper answers on TCP, UDP or both | Firmware-dependent |
| Whether the installed firmware offers `HARDCopy:FORMat PNG` | Firmware-dependent |
| Measurement engine settling time | Firmware- and timebase-dependent |
| Exact SCPI command spellings against the programmer manual | The manual was unreachable from the build environment (CON-02) |
| Analogue accuracy, bandwidth and noise behaviour | Instrument specification, not software |
