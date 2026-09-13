# Bidirectional Traceability Matrix

| Field | Value |
|---|---|
| Document ID | BENCHTOOLS-TRACE-001 |
| Version | 2.0 |
| Date | 2026-09-13 |
| Process reference | Automotive SPICE V4.0, SWE.1 BP6 / SWE.2 BP7 / SWE.3 BP5 / SWE.4 BP6 |
| Item | `benchtools` 2.0.0 |

Traceability is maintained in both directions. **Downward** (§2–§6): stakeholder
need → requirement → architecture → design unit → source → test. **Upward**: every
source module and test group names its requirements and design unit in its own
docstring, so the link is carried in the artefact and not only in this table.

## 1. Stakeholder requirements to software requirements

| Stakeholder req | Software requirements |
|---|---|
| STK-01 — interface over Ethernet | CORE-FR-001, -002, -003, -005, -007, -008, -011, -026; SCOPE-FR-101 |
| STK-02 — enable up to four channels | SCOPE-FR-010, -011 |
| STK-03 — screen position and volts per channel | SCOPE-FR-012 … -016; CORE-FR-031 |
| STK-04 — trigger and capture a plot | SCOPE-FR-020 … -022, -030, -031, -040 … -043, -050 … -052, -080, -081, -100; ANA-FR-001 … -005, -020; CORE-FR-027 |
| STK-05 — measurements: period, spread of channels going high | SCOPE-FR-053, -060 … -062; ANA-FR-004, -010 … -017, -021 |
| STK-06 — determine whether VISA must be used | CORE-FR-001, -006; SCOPE-FR-090; BENCHTOOLS-VISA-001 |
| STK-07 — host further tools sharing common code | CORE-FR-004, -010, -020 … -031, -040, -041; CORE-NFR-008, -009; INST-FR-001 … -003 |
| STK-08 — overall bench test runner | RUN-FR-001 … -006, -010 … -015, -020 … -023, -030 … -035, -040 … -043, -050 … -053 |

## 2. CORE requirements to design, code and test

| Requirement | Architecture | Design unit | Source | Verifying test(s) |
|---|---|---|---|---|
| CORE-FR-001 | ARC-003 | CORE-DD-VXI11 | `core/transport/vxi11.py` | `TestXdrCodec` (4), `test_identity_query`, `test_full_driver_over_the_socket` |
| CORE-FR-002 | ARC-003 | CORE-DD-VXI11 | `vxi11.query_portmapper` | `test_getport_returns_the_mapped_port`, `test_unreachable_portmapper_is_reported_clearly` |
| CORE-FR-003 | ARC-003 | CORE-DD-SOCKET | `core/transport/socket_raw.py` | `TestSocketTransport` (12) |
| CORE-FR-004 | ARC-004 | CORE-DD-MOCK | `core/transport/mock.py` | `test_transport_alone_falls_back_to_the_plain_simulator`, `test_an_explicit_responder_wins` |
| CORE-FR-005 | ARC-002 | CORE-DD-TRANSPORT | `core/transport/base.py` | `TestFraming` (9) |
| CORE-FR-006 | ARC-003 | CORE-DD-VISA | `core/transport/visa_backend.py` | `TestVisaTransport` (6), `test_visa_backend_is_opt_in` |
| CORE-FR-007 | ARC-002, ARC-003 | CORE-DD-TRANSPORT, -VXI11 | `base.py`, `Vxi11Transport._send` | `test_large_transfer_is_reassembled`, `test_write_is_chunked_to_max_recv_size` |
| CORE-FR-008 | ARC-003 | CORE-DD-VXI11 | `Vxi11Transport._open_link` | `test_device_names_are_probed_in_order`, `test_link_reports_the_accepted_device_name`, `test_unknown_device_name_raises` |
| CORE-FR-010 | ARC-003 | CORE-DD-FACTORY | `core/transport/factory.py` | `TestDriverRegistry.test_a_new_driver_can_be_registered`, `test_backends_listing` |
| CORE-FR-011 | ARC-003 | CORE-DD-FACTORY | `parse_resource` | `TestParseResource` (17), `TestOpenTransport` (2) |
| CORE-FR-020 | ARC-001 | CORE-DD-SCPI | `ScpiInstrument.connect/initialise/close` | `test_context_manager_closes`, `test_reset_reinitialises`, `TestGenericInstrument` |
| CORE-FR-021 | ARC-001 | CORE-DD-SCPI | `_query_float`, `_query_int`, `_query_fields` | `test_unparsable_number_is_reported`, `test_compound_query_field_count_is_checked` |
| CORE-FR-022 | ARC-001 | CORE-DD-SCPI | `InstrumentIdentity` | `TestInstrumentIdentity` (3), `test_identity_is_cached_then_refreshable` |
| CORE-FR-023 | ARC-001 | CORE-DD-SCPI | `reset`, `clear_status`, `operation_complete`, `event_status` | `test_mandated_queries` |
| CORE-FR-024 | ARC-001 | CORE-DD-SCPI | `read_event_queue`, `check_errors` | `test_scpi_standard_error_queue_is_drained`, `test_check_errors_raises_with_detail`, `test_model_name_appears_in_error_messages` |
| CORE-FR-025 | ARC-001 | CORE-DD-SCPI | `read_event_queue` bound | `test_error_queue_poll_is_bounded` |
| CORE-FR-026 | ARC-001 | CORE-DD-SCPI | `initialise` | `test_reset_restores_defaults_and_response_format` |
| CORE-FR-027 | ARC-001 | CORE-DD-SCPI | `parse_ieee_block`, `format_ieee_block` | `TestIeee488Blocks` (7) |
| CORE-FR-028 | ARC-001 | CORE-DD-SCPI | `write_raw`, `query_raw` | `test_raw_access` |
| CORE-FR-030 | ARC-005 | CORE-DD-ENUMS | `core/enums.py` | `TestScpiEnum` (6) |
| CORE-FR-031 | ARC-005 | CORE-DD-VALIDATE | `core/validation.py` | `TestValidateRange` (6), `TestValidateChannels` (6), `TestValidateChoice` (2) |
| CORE-FR-040 | ARC-004 | CORE-DD-SIM | `core/simulator.py` | `TestBaseSimulator` (12), `TestSubclassing` (3) |
| CORE-FR-041 | ARC-004 | CORE-DD-SIM | `_unknown_command` | `test_unknown_header_is_recorded_not_ignored`, `test_unknown_query_still_answers` |

### CORE non-functional

| Requirement | Realised by | Verified by |
|---|---|---|
| CORE-NFR-001 | AD-01; `pyproject.toml` `dependencies = []`; `vxi11.py` imports only stdlib | Inspection; the extras-blocked suite run (520 passed, 27 skipped) |
| CORE-NFR-002 | `requires-python = ">=3.8"`; no newer syntax or library | Inspection |
| CORE-NFR-003 | Lazy imports in `plotting.py`, `visa_backend.py`, `spec.load_mapping` | `test_clear_error_when_matplotlib_is_absent`; the module skips in `test_plotting.py`, `test_visa.py`, `runner/test_cli.py` |
| CORE-NFR-004 | AD-06; `core/validation.py` | `test_nothing_is_sent_when_validation_fails`, plus every `ConfigurationError` test |
| CORE-NFR-005 | CORE-DD-ERR | `TestErrorHandling`, `test_refused_connection_mentions_the_tds3014b_limitation`, `test_unknown_device_name_raises`, `test_unparsable_stb_is_reported` |
| CORE-NFR-006 | `Transport.timeout`, `wait_for_acquisition` deadline, socket timeouts | `test_timeout_must_be_positive`, `test_starved_link_times_out`, `test_silent_instrument_times_out`, `test_timeout_is_restored_after_the_transfer` |
| CORE-NFR-007 | — | 94% measured; BENCHTOOLS-SWE4-002 §3 |
| CORE-NFR-008 | AD-02 | `test_core_never_references_an_instrument`, `test_core_is_importable_on_its_own` |
| CORE-NFR-009 | AD-02 | `test_layer_dependencies_point_one_way` (37 sources), `test_analysis_is_importable_without_instruments` |

## 3. ANA requirements to design, code and test

| Requirement | Architecture | Design unit | Source | Verifying test(s) |
|---|---|---|---|---|
| ANA-FR-001 | ARC-001 | ANA-DD-WAVEFORM | `decode_curve` | `TestCurveDecoding` (5) |
| ANA-FR-002 | ARC-001 | ANA-DD-WAVEFORM | `WaveformPreamble.time_at`, `.volts_at` | `TestScaling` (7) |
| ANA-FR-003 | ARC-001 | ANA-DD-WAVEFORM | `start_index` | `test_start_index_offsets_the_time_axis`, `test_partial_record_keeps_absolute_times` |
| ANA-FR-004 | ARC-001, ARC-002 | ANA-DD-WAVEFORM, -MEASURE | `clipped_sample_count` | `test_clipping_detection`, `test_clipping_threshold_follows_the_transfer_width`, `test_capture_reports_clipping` |
| ANA-FR-005 | ARC-001 | ANA-DD-WAVEFORM | `to_csv`, `waveforms_to_csv` | `TestExport` (4), `test_csv_export` |
| ANA-FR-010 | ARC-002 | ANA-DD-MEASURE | `estimate_levels` | `TestLevelEstimation` (6) |
| ANA-FR-011 | ARC-002 | ANA-DD-MEASURE | `find_crossings` | `test_rising_edges_are_found_at_the_expected_times`, `test_falling_edges_are_found` |
| ANA-FR-012 | ARC-002 | ANA-DD-MEASURE | interpolation in `find_crossings` | `test_interpolation_beats_the_sample_interval` |
| ANA-FR-013 | ARC-002 | ANA-DD-MEASURE | hysteresis in `find_crossings` | `test_hysteresis_suppresses_noise_retriggering`, `test_negative_hysteresis_is_rejected` |
| ANA-FR-014 | ARC-002 | ANA-DD-MEASURE | `threshold_for` | `test_absolute_threshold_overrides_percent`, `test_absolute_threshold_is_applied_to_every_channel` |
| ANA-FR-015 | ARC-002 | ANA-DD-MEASURE | `measure_period`, `PeriodResult` | `TestPeriod` (5) |
| ANA-FR-016 | ARC-002 | ANA-DD-MEASURE | `measure_channel_spread`, `SpreadResult` | `TestChannelSpread` (12), `TestHostSideMeasurements` (6) |
| ANA-FR-017 | ARC-002 | ANA-DD-MEASURE | `measure_pulse_width`, `measure_rise_time` | `TestPulseWidthAndRiseTime` (5) |
| ANA-FR-020 | ARC-002 | ANA-DD-PLOT | `plot_waveforms` | `TestPlotting` (8) |
| ANA-FR-021 | ARC-002 | ANA-DD-PLOT | `plot_waveforms(spread=)` | `test_spread_annotation` |

## 4. INST and SCOPE requirements to design, code and test

| Requirement | Architecture | Design unit | Source | Verifying test(s) |
|---|---|---|---|---|
| INST-FR-001 | INST-ARC-001 | INST-DD-GENERIC | `instruments/generic.py` | `TestGenericInstrument` (13) |
| INST-FR-002 | CORE-ARC-001 | CORE-DD-SCPI | `SIMULATOR_CLASS` | `test_bare_sim_resource_uses_the_driver_simulator` |
| INST-FR-003 | SCOPE-ARC-001 | SCOPE-DD-CONST | `ModelLimits` | `test_unsupported_bandwidth_is_rejected`; a 2-channel envelope is exercised in `test_scpi.py` |
| SCOPE-FR-010 | SCOPE-ARC-001 | SCOPE-DD-SCOPE | `enable_channel` | `test_enable_and_disable`, `test_all_four_channels_are_supported` |
| SCOPE-FR-011 | SCOPE-ARC-001 | SCOPE-DD-SCOPE | `enabled_channels` | `test_enabled_channels_lists_only_displayed` |
| SCOPE-FR-012 | SCOPE-ARC-001 | SCOPE-DD-SCOPE, -CONST | `set_volts_per_div`, `configure_channel` | `test_volts_per_div_round_trip`, `test_out_of_range_sensitivity_is_rejected` (3) |
| SCOPE-FR-013 | SCOPE-ARC-001 | SCOPE-DD-SCOPE | `set_position` | `test_position_round_trip`, `test_out_of_range_position_is_rejected` (2) |
| SCOPE-FR-014 | SCOPE-ARC-001 | SCOPE-DD-SCOPE | `configure_channel` | `test_configure_channel_sets_every_field` |
| SCOPE-FR-015 | SCOPE-ARC-001 | SCOPE-DD-SCOPE | `get_channel_setup` | `test_read_back_setup` |
| SCOPE-FR-016 | SCOPE-ARC-001 | SCOPE-DD-SCOPE | `configure_channel`, `apply_setup` | `test_configure_channel_sends_one_message`, `test_unset_fields_are_not_sent` |
| SCOPE-FR-020 | SCOPE-ARC-001 | SCOPE-DD-SCOPE | `set_time_per_div` | `test_time_base`, `test_out_of_range_time_base_is_rejected` (2) |
| SCOPE-FR-021 | SCOPE-ARC-001 | SCOPE-DD-SCOPE | `set_horizontal_delay` | `test_horizontal_delay_is_applied`, `test_horizontal_delay_shifts_the_captured_time_axis` |
| SCOPE-FR-022 | SCOPE-ARC-001 | SCOPE-DD-SCOPE | `set_record_length` | `test_record_length`, `test_unsupported_record_length_is_rejected` |
| SCOPE-FR-030 | SCOPE-ARC-001 | SCOPE-DD-SCOPE | `configure_edge_trigger` | `test_edge_trigger_configuration` (4) |
| SCOPE-FR-031 | SCOPE-ARC-001 | SCOPE-DD-SCOPE | `trigger_state`, `force_trigger` | `test_trigger_state_is_typed`, `test_force_trigger_completes_a_pending_acquisition` |
| SCOPE-FR-040 | SCOPE-ARC-001 | SCOPE-DD-SCOPE | `single`, `wait_for_acquisition` | `test_single_completes`, `test_busy_is_polled_until_clear` |
| SCOPE-FR-041 | SCOPE-ARC-001 | SCOPE-DD-SCOPE | `run`, `stop` | `test_run_and_stop` |
| SCOPE-FR-042 | SCOPE-ARC-001 | SCOPE-DD-SCOPE | `set_acquisition_mode` | `test_acquisition_mode_with_averaging`, `test_invalid_average_count_is_rejected` |
| SCOPE-FR-043 | SCOPE-ARC-001 | SCOPE-DD-SCOPE | `wait_for_acquisition` | `test_no_trigger_times_out_with_a_useful_message` |
| SCOPE-FR-050 | SCOPE-ARC-001 | SCOPE-DD-SCOPE | `capture`, `capture_single` | `test_all_four_channels_from_one_acquisition`, `test_record_length_and_scaling` |
| SCOPE-FR-051 | SCOPE-ARC-001 | SCOPE-DD-SCOPE | `capture(encoding, width)` | `test_two_byte_transfer`, `test_ascii_encoding_matches_binary`, `test_payload_containing_a_hash_byte_is_not_re_parsed` |
| SCOPE-FR-052 | SCOPE-ARC-001 | SCOPE-DD-SCOPE | `capture(start, stop)` | `test_partial_record_keeps_absolute_times`, `test_stop_before_start_is_rejected` |
| SCOPE-FR-053 | SCOPE-ARC-001 | SCOPE-DD-SCOPE | clipping warning in `capture` | `test_capture_reports_clipping` |
| SCOPE-FR-060 | SCOPE-ARC-001 | SCOPE-DD-SCOPE | `measure`, `measure_delay` | `TestInstrumentMeasurements` (7) |
| SCOPE-FR-061 | SCOPE-ARC-001 | SCOPE-DD-SCOPE | sentinel check in `measure` | `test_undisplayed_channel_raises` |
| SCOPE-FR-062 | SCOPE-ARC-001, ANA-ARC-002 | SCOPE-DD-SCOPE | `measure_channel_spread`, `measure_period_host` | `TestHostSideMeasurements` (6) |
| SCOPE-FR-080 | SCOPE-ARC-001 | SCOPE-DD-SCOPE | `screenshot` | `TestScreenshot` (5) |
| SCOPE-FR-081 | SCOPE-ARC-001 | SCOPE-DD-SCOPE | `screenshot(verify_format)` | `test_unsupported_format_falls_back` |
| SCOPE-FR-090 | CORE-ARC-004 | SCOPE-DD-SIM | `instruments/tek3014b/simulator.py` | `instruments/tek3014b/test_simulator.py` (19) |
| SCOPE-FR-100 | SCOPE-ARC-001 | SCOPE-DD-CLI | `instruments/tek3014b/cli.py` | `instruments/tek3014b/test_cli.py` (20) |
| SCOPE-FR-101 | SCOPE-ARC-001 | SCOPE-DD-SCOPE | `read_event_queue` override | `TestErrorHandling` (6) |

## 5. RUN requirements to design, code and test

| Requirement | Architecture | Design unit | Source | Verifying test(s) |
|---|---|---|---|---|
| RUN-FR-001 | ARC-001 | RUN-DD-BENCH | `runner/bench.py` | `test_named_bench_file`, `test_simulate_overrides_the_configured_resource` |
| RUN-FR-002 | ARC-001 | RUN-DD-BENCH | `BenchConfig`, `load_bench` | `TestBenchConfig` (6), `TestInstrumentConfig` (7) |
| RUN-FR-003 | ARC-001 | RUN-DD-BENCH | driver registry | `TestDriverRegistry` (2), `test_unknown_driver_lists_the_registered_ones` |
| RUN-FR-004 | ARC-001 | RUN-DD-BENCH | `Bench.get`, `Bench.close` | `test_instruments_connect_on_first_use`, `test_the_same_instance_is_reused`, `test_close_releases_everything` |
| RUN-FR-005 | ARC-001 | RUN-DD-BENCH | `BenchConfig.simulated`, `Bench(simulate=)` | `test_simulated_factory`, `test_simulated_run_passes` |
| RUN-FR-006 | ARC-001 | RUN-DD-BENCH | `Bench.is_simulated` | `test_all_sim_resources_count_as_simulated`, `test_a_real_resource_is_not_simulated`, `test_a_mixed_bench_is_not_simulated`, `test_simulate_flag_forces_it` |
| RUN-FR-010 | ARC-001 | RUN-DD-SPEC | `runner/spec.py` | `test_json_needs_no_third_party_package`, `test_yaml_when_available` |
| RUN-FR-011 | ARC-001 | RUN-DD-SPEC | `TestSpec.from_mapping` | `TestSpecParsing` (8) |
| RUN-FR-012 | ARC-001 | RUN-DD-SPEC | `TestCase.requirement` | `test_case_requirements_list_is_joined`, `test_requirement_roll_up` |
| RUN-FR-013 | ARC-001 | RUN-DD-RESOLVE | `runner/resolve.py` | `TestResolution` (9), `TestErrors` (4) |
| RUN-FR-014 | ARC-001 | RUN-DD-SPEC | validation in `from_mapping` | `test_malformed_specifications_are_reported` (7), `TestExpectationParsing` (6) |
| RUN-FR-015 | ARC-001 | RUN-DD-SPEC | `TestCase.skip` | `test_skip_is_carried`, `test_skipped_test_is_not_executed` |
| RUN-FR-020 | ARC-001 | RUN-DD-LIMITS | `Limit` | `TestChecking.test_maximum/minimum/two_sided` |
| RUN-FR-021 | ARC-001 | RUN-DD-LIMITS | `Limit.window` | `test_absolute_tolerance`, `test_percentage_tolerance`, `test_exact_equality` |
| RUN-FR-022 | ARC-001 | RUN-DD-SPEC | `Expectation.scale` | `test_measured_value_is_scaled_for_the_limit` |
| RUN-FR-023 | ARC-001 | RUN-DD-LIMITS | `Limit.text`, `LimitOutcome.reason` | `TestRendering` (6), `test_out_of_limit_is_a_failure_not_an_error` |
| RUN-FR-030 | ARC-001 | RUN-DD-RUNNER, -RESULTS | `runner/runner.py`, `results.py` | `TestHappyPath` (7) |
| RUN-FR-031 | ARC-001 | RUN-DD-RUNNER | error vs failure classification | `TestFailureVersusError` (9) |
| RUN-FR-032 | ARC-001 | RUN-DD-RUNNER | setup abort, teardown `finally` | `test_setup_failure_aborts_the_suite`, `test_teardown_runs_even_after_a_failure` |
| RUN-FR-033 | ARC-001 | RUN-DD-RUNNER | `stop_on_error` | `test_a_failure_does_not_stop_later_tests`, `test_stop_on_error_abandons_the_rest` |
| RUN-FR-034 | ARC-001 | RUN-DD-RUNNER | `_resolve_action` | `test_private_methods_are_unreachable` |
| RUN-FR-035 | ARC-001 | RUN-DD-BENCH | `Bench.require` | `test_missing_instrument_is_reported_before_anything_runs`, `test_require_reports_everything_missing` |
| RUN-FR-040 | ARC-001 | RUN-DD-RESULTS | `requirements_verified` | `test_requirement_roll_up`, `test_requirement_takes_the_worst_of_its_tests`, `test_requirements_table` |
| RUN-FR-041 | ARC-001 | RUN-DD-REPORT | `write_json` | `TestJson` (3) |
| RUN-FR-042 | ARC-001 | RUN-DD-REPORT | `format_markdown` | `TestMarkdown` (8) |
| RUN-FR-043 | ARC-001 | RUN-DD-REPORT | `write_junit` | `TestJunit` (6) |
| RUN-FR-050 | ARC-001 | RUN-DD-CLI | `runner/cli.py` | `TestRunCommand` (8) |
| RUN-FR-051 | ARC-001 | RUN-DD-CLI | exit statuses | `test_simulated_run_passes`, `test_failure_exits_nonzero`, `test_no_bench_and_no_simulate_is_a_usage_error` |
| RUN-FR-052 | ARC-001 | RUN-DD-CLI | report path suffixing | `test_several_specs_get_suffixed_reports` |
| RUN-FR-053 | ARC-001 | RUN-DD-CLI | `benchtools/cli.py` | `TestTopLevelDispatch` (7) |

## 6. Architecture to design to source

| Architectural element | Design unit | Source |
|---|---|---|
| CORE-ARC-001 | CORE-DD-SCPI | `core/scpi.py` |
| CORE-ARC-002 | CORE-DD-TRANSPORT | `core/transport/base.py` |
| CORE-ARC-003 | CORE-DD-VXI11, -SOCKET, -VISA, -FACTORY | `core/transport/{vxi11,socket_raw,visa_backend,factory,constants}.py` |
| CORE-ARC-004 | CORE-DD-SIM, CORE-DD-MOCK | `core/simulator.py`, `core/transport/mock.py` |
| CORE-ARC-005 | CORE-DD-ENUMS, -VALIDATE, -ERR | `core/{enums,validation,errors}.py` |
| ANA-ARC-001 | ANA-DD-WAVEFORM | `analysis/waveform.py` |
| ANA-ARC-002 | ANA-DD-MEASURE, ANA-DD-PLOT | `analysis/{measure,plotting}.py` |
| INST-ARC-001 | INST-DD-GENERIC | `instruments/generic.py` |
| SCOPE-ARC-001 | SCOPE-DD-SCOPE, -CONST, -SIM, -CLI | `instruments/tek3014b/*.py` |
| RUN-ARC-001 | RUN-DD-SPEC, -LIMITS, -RESOLVE, -BENCH, -RESULTS, -RUNNER, -REPORT, -CLI | `runner/*.py`, `cli.py` |

## 7. Coverage analysis

| Question | Answer |
|---|---|
| Requirements with no verifying test | **None.** All 99 functional and 9 non-functional requirements trace to at least one test, or to a recorded inspection where a test is not the appropriate method (CORE-NFR-002, and part of CORE-NFR-001). |
| Tests not tracing to a requirement | **None.** Every test file names its requirements in its module docstring. |
| Source modules with no design unit | **None.** Every module names its design unit in its docstring; `__main__.py` is covered by RUN-DD-CLI. |
| Design units with no source | **None.** |
| Stakeholder requirements not decomposed | **None.** All eight trace downward; STK-06 additionally produces BENCHTOOLS-VISA-001 as its work product. |
| Architectural decisions without a verifying test | **None.** AD-01 → `test_full_driver_over_the_socket`; AD-02 → `test_layering.py`; AD-03 → `TestDriverRegistry`; AD-04 → `TestFraming`; AD-05 → `test_payload_containing_a_hash_byte_is_not_re_parsed`; AD-06 → `TestChannelSpread`; AD-07 → `test_busy_is_polled_until_clear`; AD-08 → `TestSpecParsing`; AD-09 → `TestFailureVersusError`; AD-10 → `test_all_sim_resources_count_as_simulated`. |

## 8. Open items

| ID | Item | Owner action |
|---|---|---|
| OPEN-01 | Bench confirmation items in BENCHTOOLS-VISA-001 §5.1 (device name, portmapper transport, hardcopy format, measurement settling, record lengths) | Discharge on first use with physical hardware. |
| OPEN-02 | TDS3000 SCPI command spellings not transcribed from the programmer manual (CON-02) | Spot-check against Tektronix 071-0381-03 on first bench use. |
| OPEN-03 | No requirements yet for the instrument families named for future work (CON-03): power supplies and loads, DMMs, signal sources, logic and protocol analysers, BLE and RF | Add a prefixed requirements section, design unit, test group and matrix rows per instrument as each driver is written. |
