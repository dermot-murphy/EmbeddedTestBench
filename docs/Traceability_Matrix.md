# Bidirectional Traceability Matrix

| Field | Value |
|---|---|
| Document ID | TEK3014B-TRACE-001 |
| Version | 1.0 |
| Date | 2026-09-12 |
| Process reference | Automotive SPICE V4.0, SWE.1 BP6 / SWE.2 BP7 / SWE.3 BP5 / SWE.4 BP6 |
| Item | `tek3014b` v1.0.0 |

Traceability is maintained in both directions:

- **Downward** (§2): stakeholder need → requirement → architecture → design unit → source → test.
- **Upward** (§3): every source module and test group names its requirements in its own
  docstring, so the link is carried in the artefact itself and not only in this table.

## 1. Stakeholder requirements to software requirements

| Stakeholder req | Software requirements |
|---|---|
| STK-01 — interface over Ethernet | SWE1-FR-001 … -007, -101 |
| STK-02 — enable up to four channels | SWE1-FR-010, -011 |
| STK-03 — screen position and volts per channel | SWE1-FR-012, -013, -014, -015, -016 |
| STK-04 — trigger and capture a plot | SWE1-FR-020 … -022, -030, -031, -040 … -043, -050, -051, -053, -054, -055, -070, -080, -081, -100 |
| STK-05 — measurements: period, spread in time of channels going high | SWE1-FR-052, -060 … -067, -071, -100 |
| STK-06 — determine whether VISA must be used | SWE1-FR-001, -004, -090; TEK3014B-VISA-001 |

## 2. Software requirements to design, code and test

| Requirement | Architecture | Design unit | Source | Verifying test(s) |
|---|---|---|---|---|
| SWE1-FR-001 | ARC-003 | DD-VXI11 | `transport/vxi11.py` | `TestXdrCodec` (4), `test_identity_query`, `test_full_driver_over_the_socket` |
| SWE1-FR-002 | ARC-003 | DD-VXI11 | `vxi11.query_portmapper` | `test_getport_returns_the_mapped_port`, `test_unreachable_portmapper_is_reported_clearly` |
| SWE1-FR-003 | ARC-003 | DD-SOCKET | `transport/socket_raw.py` | `TestSocketTransport` (12) |
| SWE1-FR-004 | ARC-003, ARC-005 | DD-VISA | `transport/visa_backend.py` | `TestVisaTransport` (6), `test_visa_backend_is_opt_in` |
| SWE1-FR-005 | ARC-003 | DD-FACTORY | `transport/factory.py` | `TestParseResource` (17), `TestOpenTransport` (2) |
| SWE1-FR-006 | ARC-002 | DD-TRANSPORT, DD-VXI11 | `transport/base.py`, `Vxi11Transport._send` | `test_large_transfer_is_reassembled`, `test_write_is_chunked_to_max_recv_size`, `TestFraming` (9) |
| SWE1-FR-007 | ARC-003 | DD-VXI11 | `Vxi11Transport._open_link` | `test_device_names_are_probed_in_order`, `test_link_reports_the_accepted_device_name`, `test_unknown_device_name_raises` |
| SWE1-FR-010 | ARC-001 | DD-SCOPE | `Tek3014B.enable_channel` | `test_enable_and_disable`, `test_all_four_channels_are_supported` |
| SWE1-FR-011 | ARC-001 | DD-SCOPE | `Tek3014B.enabled_channels` | `test_enabled_channels_lists_only_displayed`, `test_capture_defaults_to_displayed_channels` |
| SWE1-FR-012 | ARC-001, ARC-007 | DD-SCOPE, DD-CONST | `set_volts_per_div`, `configure_channel` | `test_volts_per_div_round_trip`, `test_volts_per_div_is_range_checked`, `test_out_of_range_sensitivity_is_rejected` (3) |
| SWE1-FR-013 | ARC-001, ARC-007 | DD-SCOPE, DD-CONST | `set_position`, `configure_channel` | `test_position_round_trip`, `test_position_is_range_checked`, `test_out_of_range_position_is_rejected` (2) |
| SWE1-FR-014 | ARC-001 | DD-SCOPE | `configure_channel` | `test_configure_channel_sets_every_field`, `test_unsupported_bandwidth_is_rejected` |
| SWE1-FR-015 | ARC-001 | DD-SCOPE | `get_channel_setup` | `test_read_back_setup` |
| SWE1-FR-016 | ARC-001 | DD-SCOPE | `configure_channel`, `apply_setup` | `test_configure_channel_sends_one_message`, `test_unset_fields_are_not_sent`, `test_apply_setup_configures_a_list` |
| SWE1-FR-020 | ARC-001, ARC-007 | DD-SCOPE | `set_time_per_div` | `test_time_base`, `test_out_of_range_time_base_is_rejected` (2) |
| SWE1-FR-021 | ARC-001 | DD-SCOPE | `set_horizontal_delay` | `test_horizontal_delay_is_applied`, `test_horizontal_delay_shifts_the_captured_time_axis` |
| SWE1-FR-022 | ARC-001, ARC-007 | DD-SCOPE | `set_record_length` | `test_record_length`, `test_unsupported_record_length_is_rejected` |
| SWE1-FR-030 | ARC-001 | DD-SCOPE | `configure_edge_trigger` | `test_edge_trigger_configuration`, `test_trigger_source_accepts_a_name`, `test_trigger_level_round_trip`, `test_invalid_trigger_channel_is_rejected` |
| SWE1-FR-031 | ARC-001 | DD-SCOPE | `trigger_state`, `force_trigger` | `test_trigger_state_is_typed`, `test_force_trigger_completes_a_pending_acquisition` |
| SWE1-FR-040 | ARC-001 | DD-SCOPE | `single`, `wait_for_acquisition` | `test_single_completes`, `test_busy_is_polled_until_clear` |
| SWE1-FR-041 | ARC-001 | DD-SCOPE | `run`, `stop` | `test_run_and_stop` |
| SWE1-FR-042 | ARC-001, ARC-007 | DD-SCOPE | `set_acquisition_mode` | `test_acquisition_mode_with_averaging`, `test_invalid_average_count_is_rejected` |
| SWE1-FR-043 | ARC-001, ARC-010 | DD-SCOPE, DD-ERR | `wait_for_acquisition` | `test_no_trigger_times_out_with_a_useful_message` |
| SWE1-FR-050 | ARC-001, ARC-004 | DD-SCOPE | `capture`, `capture_single` | `test_all_four_channels_from_one_acquisition`, `test_record_length_and_scaling`, `test_full_driver_over_the_socket` |
| SWE1-FR-051 | ARC-004 | DD-WAVEFORM | `WaveformPreamble.time_at`, `.volts_at` | `TestScaling` (7), `test_time_axis_is_centred_on_the_trigger` |
| SWE1-FR-052 | ARC-004, ARC-005 | DD-WAVEFORM, DD-MEASURE | `Waveform.clipped_sample_count` | `test_clipping_detection`, `test_clipping_threshold_follows_the_transfer_width`, `test_capture_reports_clipping`, `test_samples_clip_at_the_digitiser_rail` |
| SWE1-FR-053 | ARC-004 | DD-WAVEFORM | `to_csv`, `waveforms_to_csv` | `TestExport` (4), `test_csv_export` |
| SWE1-FR-054 | ARC-004 | DD-WAVEFORM | `decode_curve`, `from_payload`, `from_ascii` | `TestCurveDecoding` (5), `test_two_byte_transfer`, `test_ascii_encoding_matches_binary`, `test_from_ascii_decodes_comma_separated_codes` |
| SWE1-FR-055 | ARC-004 | DD-WAVEFORM | `WaveformPreamble.start_index` | `test_partial_record_keeps_absolute_times`, `test_start_index_offsets_the_time_axis` |
| SWE1-FR-060 | ARC-001 | DD-SCOPE | `measure`, `measure_period`, `measure_delay` | `TestInstrumentMeasurements` (7) |
| SWE1-FR-061 | ARC-005 | DD-MEASURE | `measure_period`, `PeriodResult` | `TestPeriod` (5), `test_host_period_agrees_with_the_instrument` |
| SWE1-FR-062 | ARC-005 | DD-MEASURE | `measure_channel_spread`, `SpreadResult` | `TestChannelSpread` (12), `TestHostSideMeasurements` (6) |
| SWE1-FR-063 | ARC-005 | DD-MEASURE | `measure_pulse_width`, `measure_rise_time` | `TestPulseWidthAndRiseTime` (5) |
| SWE1-FR-064 | ARC-005 | DD-MEASURE | `find_crossings` interpolation | `test_interpolation_beats_the_sample_interval`, `test_rising_edges_are_found_at_the_expected_times` |
| SWE1-FR-065 | ARC-005 | DD-MEASURE | `find_crossings` hysteresis | `test_hysteresis_suppresses_noise_retriggering`, `test_negative_hysteresis_is_rejected` |
| SWE1-FR-066 | ARC-005 | DD-MEASURE | `threshold_for` | `test_absolute_threshold_overrides_percent`, `test_absolute_threshold_is_applied_to_every_channel`, `test_percent_outside_the_range_is_rejected` |
| SWE1-FR-067 | ARC-001, ARC-010 | DD-SCOPE | `measure` sentinel check | `test_undisplayed_channel_raises`, `test_undisplayed_channel_returns_the_invalid_sentinel` |
| SWE1-FR-070 | ARC-008 | DD-PLOT | `plot_waveforms` | `TestPlotting` (8) |
| SWE1-FR-071 | ARC-008 | DD-PLOT | `plot_waveforms(spread=)` | `test_spread_annotation` |
| SWE1-FR-080 | ARC-001 | DD-SCOPE | `screenshot` | `TestScreenshot` (5), `test_read_raw_uses_the_idle_gap` |
| SWE1-FR-081 | ARC-001 | DD-SCOPE | `screenshot(verify_format=True)` | `test_unsupported_format_falls_back`, `test_unsupported_format_is_refused` |
| SWE1-FR-090 | ARC-006 | DD-SIM | `simulator.py`, `transport/mock.py` | `test_simulator.py` (19) |
| SWE1-FR-100 | ARC-009 | DD-CLI | `cli.py`, `__main__.py` | `test_cli.py` (20) |
| SWE1-FR-101 | ARC-001, ARC-010 | DD-SCOPE, DD-ERR | `event_queue`, `check_errors` | `TestErrorHandling` (6), `test_unknown_command_lands_in_the_event_queue` |

## 3. Non-functional requirements

| Requirement | Realised by | Verified by |
|---|---|---|
| SWE1-NFR-001 — no mandatory third-party deps | AD-01; `pyproject.toml` `dependencies = []`; `vxi11.py` imports only `socket`, `struct`, `random`, `logging` | Inspection of `pyproject.toml` and module imports; `TestVxi11OverASocket` passes with no third-party package involved in the path under test |
| SWE1-NFR-002 — CPython ≥ 3.8 | `requires-python = ">=3.8"`; no syntax or library newer than 3.8 (`from __future__ import annotations` throughout) | Inspection |
| SWE1-NFR-003 — optional deps lazy and diagnosable | AD-05; `matplotlib` imported inside `plot_waveforms`, `pyvisa` inside `VisaTransport._open_link` | `test_clear_error_when_matplotlib_is_absent`; the `pytestmark` skips in `test_plotting.py` and `test_transport_visa.py` demonstrate the package imports without them |
| SWE1-NFR-004 — validate before transmit | AD-05; `_validate_channel`, `_validate_channels`, `_validate_range`, `ModelLimits` | `test_nothing_is_sent_when_validation_fails`, plus every `ConfigurationError` test (13) |
| SWE1-NFR-005 — typed exceptions, actionable diagnostics | DD-ERR | `TestErrorHandling`, `test_refused_connection_mentions_the_tds3014b_limitation`, `test_no_trigger_times_out_with_a_useful_message`, `test_unknown_device_name_raises`, `test_unparsable_stb_is_reported` |
| SWE1-NFR-006 — bounded timeouts | `Transport.timeout`, `_io_timeout_ms`, `wait_for_acquisition` deadline, socket `settimeout` | `test_timeout_must_be_positive`, `test_starved_link_times_out`, `test_silent_instrument_times_out`, `test_no_trigger_times_out_with_a_useful_message`, `test_timeout_is_restored_after_the_transfer` |
| SWE1-NFR-007 — coverage ≥ 90% | — | 93% measured; TEK3014B-SWE4-002 §3 |
| SWE1-NFR-008 — data-driven capability envelope | `ModelLimits` dataclass; `Tek3014B(limits=...)` | Inspection; `test_unsupported_bandwidth_is_rejected` exercises a model-specific envelope entry |

## 4. Architecture to design to source

| Architectural element | Design unit | Source file |
|---|---|---|
| SWE2-ARC-001 application layer | SWE3-DD-SCOPE | `tek3014b/scope.py` |
| SWE2-ARC-002 transport abstraction | SWE3-DD-TRANSPORT | `tek3014b/transport/base.py` |
| SWE2-ARC-003 concrete transports | SWE3-DD-VXI11, -SOCKET, -VISA, -FACTORY | `transport/vxi11.py`, `socket_raw.py`, `visa_backend.py`, `factory.py`, `mock.py` |
| SWE2-ARC-004 data model | SWE3-DD-WAVEFORM | `tek3014b/waveform.py` |
| SWE2-ARC-005 analysis | SWE3-DD-MEASURE | `tek3014b/measure.py` |
| SWE2-ARC-006 test double | SWE3-DD-SIM | `tek3014b/simulator.py`, `transport/mock.py` |
| SWE2-ARC-007 constants and limits | SWE3-DD-CONST | `tek3014b/constants.py` |
| SWE2-ARC-008 plotting | SWE3-DD-PLOT | `tek3014b/plotting.py` |
| SWE2-ARC-009 CLI | SWE3-DD-CLI | `tek3014b/cli.py`, `__main__.py` |
| SWE2-ARC-010 error hierarchy | SWE3-DD-ERR | `tek3014b/errors.py` |

## 5. Coverage analysis

| Question | Answer |
|---|---|
| Requirements with no verifying test | **None.** All 44 functional and 8 non-functional requirements trace to at least one test, or to a recorded inspection where a test is not the appropriate method (NFR-002, NFR-008 in part). |
| Tests not tracing to a requirement | **None.** Every test file names its requirements in its module docstring. |
| Source modules with no design unit | **None.** Every module in `tek3014b/` names its design unit in its docstring; `__main__.py` is covered by SWE3-DD-CLI. |
| Design units with no source | **None.** |
| Stakeholder requirements not decomposed | **None.** All six trace downward; STK-06 additionally produces TEK3014B-VISA-001 as its work product. |

## 6. Open items

| ID | Item | Owner action |
|---|---|---|
| OPEN-01 | Bench confirmation items in TEK3014B-VISA-001 §5.1 (device name, portmapper transport, hardcopy format, measurement settling, record lengths) | Discharge on first use with physical hardware. |
| OPEN-02 | SCPI command spellings not transcribed from the programmer manual during development (CON-02) | Spot-check against Tektronix 071-0381-03 on first bench use. |
