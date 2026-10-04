# Requirements Traceability Matrix

*Automotive SPICE® PAM v4.0 | Bidirectional traceability across SWE.1 to SWE.4*

---

## 1. Document Identification & Control

| Field | Value | Field | Value |
|---|---|---|---|
| **Document ID** | ETB-RTM-001 | **Version** | 1.22 |
| **Project** | Embedded Test Bench | **Date** | 2026-10-04 |
| **Status** | Draft | **Classification** | Internal |
| **Author** | Claude | **Reviewer** | Dermot Murphy |
| **Approver** | Dermot Murphy | **Related Process** | SWE.1 / SWE.2 / SWE.3 / SWE.4 |

> **Note — Reviewer independence (ETB-DEV-002):** The Reviewer and Approver are the same person (Dermot Murphy). This is accepted under deviation record **ETB-DEV-002** (`docs/aspice/EmbeddedTestBench_DEV002_Independent_Review_Deviation.md`) on the basis that Embedded Test Bench has a single human team member.

---

## 2. Revision History

| Version | Date | Author | Description of Change |
|---|---|---|---|
| 0.1 | 2026-09-19 | Claude | Initial |
| 0.2 | 2026-09-23 | Claude | Section 12 added: DMM requirements to design, code and test. STK-18 decomposed. OPEN-03 narrowed to the instrument families still unwritten. Sections 13 to 17 renumbered. |
| 0.3 | 2026-09-23 | Claude | Rows added for BLE-FR-025 and DMM-FR-045. |
| 0.4 | 2026-09-24 | Claude | Rows added for RUN-FR-054…057. |
| 0.5 | 2026-09-25 | Claude | Rows added for BLE-FR-026, -046…049 and -109…116; BLE-FR-102, -106 and -107 re-traced to the revised requirements and the split into BLE-DD-SCRIPT and BLE-DD-SCRIPTRUN (#46, #48). |
| 0.6 | 2026-09-26 | Claude | PSU-FR-002 and -003 rows name the renamed tests (#64). OPEN-08 now points to TB-IF-001 §12. TB-IF-001 and TB-SWE3-002 added to the referenced documents (#63). Header version brought into line with this history. |
| 0.7 | 2026-09-30 | Claude | Section 13 added: PICO requirements to design, code and test. STK-21 and STK-22 decomposed; PICO-ARC-001 rows; AD-24 traced; OPEN-09 added. Sections 14 to 18 renumbered (#104). |
| 0.8 | 2026-10-02 | Claude | #115: rows for CORE-FR-061, -062 and DMM-FR-027 … -033, -046, -070, -080, -081; DMM-FR-016 and -021 rows name their new tests. AD-25 and AD-26 traced. STK-18 row and OPEN-03 extended; OPEN-10 added. The `DMM-` prefix is now checked by `tests/test_traceability.py`, which it was not before. Requirement count corrected to 356. |
| 0.9 | 2026-10-02 | Claude | #116: rows for RUN-FR-007 and RUN-FR-017; AD-27 traced. |
| 1.0 | 2026-10-02 | Claude | #120: RUN-FR-035 row names `test_the_simulated_bench_provides_every_shipped_specification`. |
| 1.1 | 2026-10-02 | Claude | #124: row for BLE-FR-071. |
| 1.2 | 2026-10-02 | Claude | #126: CORE-FR-060 row updated; rows for CORE-FR-063 and RUN-FR-008; AD-28 traced. |
| 1.3 | 2026-10-03 | Claude | #127: rows for PICO-FR-070 … -076 (reflashing with no BOOTSEL press); STK-21 and STK-22 rows extended; PICO-DD-FLASH added to the PICO architecture row; OPEN-09 extended to PICO-OPEN-05, then updated for PICO-OPEN-01 and -05 closed on a real Pico 2; PICO-FR-070 row gains the two `touch_1200` note tests. Requirement count corrected to 368 functional. |
| 1.4 | 2026-10-03 | Claude | #131: rows for PICO-FR-006, -007, -027, -047 and -061; PICO-FR-001 … -005, -020 … -025, -030, -040 … -043, -046, -050 and -060 re-traced to the `rd` command set and its tests; PICO-FR-044 marked withdrawn. STK-21 and STK-22 rows updated. AD-24's verifying tests corrected: the raw-word tests no longer exist; AD-24 recorded as superseded in TB-SWE2-001 0.8. OPEN-09 extended to the `rd` command set and the target build, then narrowed after the first run on a real Pico 2 (2026-10-03): PICO-FR-031 carries the #131 target-build figures. §16 requirement count corrected to the number SWE.1 declares (366 functional, one of them withdrawn; it had read 356 since #116). With #127 merged: STK-21 and STK-22 rows carry both changes; PICO-FR-071, -073 and -076 re-traced to `flash` confirming the build by `rd` (the image's name, version and commit SHA; the ambiguous-SHA and missing-version tests); OPEN-09 restated for PICO-OPEN-01 … -06; §16 requirement count recomputed from SWE.1 as 373 functional declared, 372 in force. |
| 1.5 | 2026-10-03 | Claude | #134: row for RUN-FR-059 (running a selected subset of test cases); §16 requirement count 374 functional declared, 373 in force. |
| 1.6 | 2026-10-03 | Claude | #135: rows for CORE-FR-064 and RUN-FR-060 (structured event-log records); §16 requirement count 376 functional declared, 375 in force. |
| 1.7 | 2026-10-03 | Claude | #136: rows for RUN-FR-061 … -065 (the run control channel); RUN-DD-CONTROL added to RUN-ARC-001; §16 requirement count 381 functional declared, 380 in force. |
| 1.8 | 2026-10-03 | Claude | #137: STK-23 row; rows for VIEW-FR-001 … -009 (the test run viewer); VIEW-ARC-001 row; §16 requirement count 390 functional declared, 389 in force. |
| 1.9 | 2026-10-03 | Claude | #138: rows for VIEW-FR-010 … -012 (instrument traffic, front panels, a step's traffic); VIEW-DD-TRAFFIC in VIEW-ARC-001; §16 count 393 declared, 392 in force. |
| 1.10 | 2026-10-03 | Claude | #139: rows for S2LP-FR-080 and VIEW-FR-013 … -015 (RF and BLE pages); VIEW-DD-RADIO in VIEW-ARC-001; §16 count 397 declared, 396 in force. |
| 1.11 | 2026-10-03 | Claude | #140: rows for CORE-FR-065, PSU-FR-044, PICO-FR-048, DMM-FR-034 and VIEW-FR-016 … -018 (readings and graphs); VIEW-DD-GRAPHS in VIEW-ARC-001; §16 count 404 declared, 403 in force. |
| 1.12 | 2026-10-03 | Claude | #148: rows for VIEW-FR-019 … -021 (Event log pause and filters); VIEW-DD-TAGS in VIEW-ARC-001; §16 count 407 declared, 406 in force. |
| 1.13 | 2026-10-03 | Claude | #149: rows for VIEW-FR-022 … -024 (the status bar); VIEW-DD-STATUS in VIEW-ARC-001; §16 count 410 declared, 409 in force. |
| 1.14 | 2026-10-03 | Claude | #141: rows for VIEW-FR-025 … -027 (the viewer from another PC); §16 count 413 declared, 412 in force. |
| 1.15 | 2026-10-03 | Claude | #151: rows for S2LP-FR-081 … -083; S2LP-FR-070's test count 26 → 29; §16 count 416 declared, 415 in force. |
| 1.16 | 2026-10-03 | Claude | #152: rows for VIEW-FR-028 … -030 (rf_monitor's Latest Data, Config and Identification); VIEW-DD-KEPLER in VIEW-ARC-001; §16 count 419 declared, 418 in force. |
| 1.17 | 2026-10-03 | Claude | #153: rows for VIEW-FR-031 … -033 (rf_monitor's sensor graphs); VIEW-DD-SENSOR in VIEW-ARC-001; §16 count 422 declared, 421 in force. |
| 1.18 | 2026-10-03 | Claude | #154: rows for VIEW-FR-034 … -036 (the TWF screen); VIEW-DD-TWF in VIEW-ARC-001; §16 count 425 declared, 424 in force. |
| 1.19 | 2026-10-03 | Claude | #155: rows for VIEW-FR-037 … -039 (Diagnostics and Sync); VIEW-DD-DIAG in VIEW-ARC-001; §16 count 428 declared, 427 in force. |
| 1.20 | 2026-10-03 | Claude | #156: rows for VIEW-FR-040 … -042 (notes and report); VIEW-DD-REPORT in VIEW-ARC-001; §16 count 431 declared, 430 in force. |
| 1.21 | 2026-10-03 | Claude | #157: rows for S2LP-FR-084, RUN-FR-066 and VIEW-FR-043 … -045 (the ST GUI page); VIEW-DD-STGUI in VIEW-ARC-001; §16 count 436 declared, 435 in force. |
| 1.22 | 2026-10-04 | Claude | #183: product renamed to Embedded Test Bench - document file name prefix `EmbeddedTestBench_`, identifier prefix `ETB-` (was `TB-`), product name in prose. Earlier revision rows keep the names in use when they were written. |

---

## 3. Purpose & Scope

### 3.1 Purpose

This matrix carries the trace in both directions: stakeholder requirement to software requirement to architecture element to design unit to source to test, and back. It is one work product rather than a section repeated in five, because a trace split across documents is a trace that can disagree with itself.

It is checked mechanically by `tests/test_traceability.py` on every run of the suite: a requirement declared in ETB-SWE1-001 and absent here fails the build, as does a requirement, design unit or test group cited in source or tests without being declared.

### 3.2 Referenced Documents

| Document ID | Title | Version |
|---|---|---|
| ETB-SYS2-001 | Embedded Test Bench System Requirements Specification | 0.1 |
| ETB-SWE1-001 | Embedded Test Bench Software Requirements Specification | 0.1 |
| ETB-SWE2-001 | Embedded Test Bench Software Architecture Description | 0.1 |
| ETB-SWE3-001 | Embedded Test Bench Software Detailed Design | 0.4 |
| ETB-SWE3-002 | GPD-3303D Driver Design and Lessons Learned | 0.1 |
| ETB-IF-001 | GPD-3303D Remote Control Interface Specification | 0.1 |
| ETB-RTM-001 | Embedded Test Bench Requirements Traceability Matrix | 0.6 |

---

## 4. Stakeholder requirements to software requirements

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
| STK-09 — J-Link: flash, verify, run/stop, breakpoints, RAM, variables, RTT, timing, call stack | JLINK-FR-001 … -006, -010, -011, -020 … -023, -030 … -036, -040 … -045, -050 … -055, -060 … -067, -090; CORE-FR-009, -012 … -016; JLINK-NFR-001, -004 |
| STK-10 — use the probe from the test bench | JLINK-FR-080, -081, -053; RUN-FR-001, -010; CORE-FR-012 … -014 |
| STK-11 — Windows first, Docker eventually | CORE-FR-009; JLINK-FR-003, -004, -005; JLINK-NFR-002, -003 |
| STK-12 — Markdown to Robot Framework | BLE-FR-100 … -116, AD-23 — a command set specified in markdown is read and run as the test of itself. JLINK-FR-081, -100 — return types constrained for a keyword layer (AD-15). Robot Framework itself undecided: CON-06, OPEN-04. |
| STK-14 — BLE UART command/response and response time | BLE-FR-040 … -045, -050 … -054; CORE-FR-017; BLE-NFR-005 |
| STK-15 — scan, select and advertising profile | BLE-FR-020 … -024, -030 … -036, -080 |
| STK-16 — dongle firmware, SES and SDK 17 | BLE-FR-090, -001, -003, -010; BLE-NFR-001 … -003, -006 |
| STK-17 — log the session to a text file | BLE-FR-060 … -062, -004 |
| STK-13 — programmable supply for the sensor | PSU-FR-001 … -060; PSU-NFR-001 … -003; CORE-FR-017 |
| STK-19 — S2-LP kit: registers, transmit, receive, log | S2LP-FR-001 … -060; S2LP-NFR-001 … -004; CORE-FR-017 |
| STK-20 — use ST's firmware if it is fit for purpose | AD-20; S2LP-FR-001, -002; S2LP-NFR-002. The firmware was examined before any was written: BENCHTOOLS-SWE4-002 §10, `docs/s2lp/S2LP_Devkit_Notes.md` §1 |
| STK-21 — local temperature with a Pico 2 and a DollaTek SHT30-D | PICO-FR-001, -003 … -005, -007, -010, -020 … -027, -030, -031, -040, -042, -043, -045 … -047, -050, -060, -061, -070 … -076; PICO-NFR-001 … -006; AD-24 (superseded by #131, see §16). PICO-FR-044 withdrawn (#131). |
| STK-22 — firmware reports its title and version | PICO-FR-002, -005 … -007, -040, -041, -060, -061, -073, -075. Since #131 the "title" is the name reported by `rd name`, beside `rd copyright`, `rd version` and `rd sha`; `flash` checks the name, version and commit SHA of the image it installed (PICO-FR-073). |
| STK-23 — watch and control a run (#130) | VIEW-FR-001 … -045; RUN-FR-066; S2LP-FR-080 … -084; CORE-FR-065; PSU-FR-044; PICO-FR-048; DMM-FR-034; RUN-FR-059 … -065; CORE-FR-064 |
| STK-18 — RS-232 multimeter | DMM-FR-001 … -033, -045, -046, -070, -080, -081; DMM-NFR-001 … -004; CORE-FR-017, -061, -062. Implemented for the TTi 1604. No behaviour confirmed against a physical meter: `docs/dmm/TTi1604_Notes.md` §5. |

## 5. CORE requirements to design, code and test

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
| CORE-FR-009 | ARC-003 | CORE-DD-PROCESS | `core/transport/process.py` | `TestRoundTrip` (5), `TestFailures` (6), `TestLifecycle` (4), `TestBackendRegistration` (2); notably `test_a_program_that_exits_at_once_reports_its_stderr`, `test_stderr_is_drained_so_the_child_cannot_block` |
| CORE-FR-017 | ARC-003 | CORE-DD-SERIAL | `core/transport/serial_port.py` | `TestResourceParsing` (13), `TestLoopback` (6), `test_a_write_the_far_end_will_not_take_is_a_timeout` |
| CORE-FR-010 | ARC-003 | CORE-DD-FACTORY | `core/transport/factory.py` | `TestDriverRegistry.test_a_new_driver_can_be_registered`, `test_backends_listing` |
| CORE-FR-011 | ARC-003 | CORE-DD-FACTORY | `parse_resource` | `TestParseResource` (17), `TestOpenTransport` (2) |
| CORE-FR-012 | ARC-006 | CORE-DD-INSTRUMENT | `core/instrument.py` | `test_initialise_opens_then_runs_the_hook`, `test_context_manager_initialises_once`, `test_context_manager_closes_on_an_exception`, `test_close_releases` |
| CORE-FR-013 | ARC-006 | CORE-DD-INSTRUMENT | `InstrumentIdentity`, `Instrument.identify` | `test_fields_can_be_given_directly`, `test_from_idn_parses_four_fields`, `test_from_idn_tolerates_missing_fields`, `test_identity_is_cached`, `test_refresh_re_reads`, `test_convenience_properties` |
| CORE-FR-014 | ARC-006, ARC-004 | CORE-DD-INSTRUMENT | `Instrument.SIMULATOR_CLASS` | `test_unknown_model_falls_back`, `test_the_probe_is_an_instrument_but_not_scpi`, `test_bare_sim_resource_uses_the_driver_simulator` |
| CORE-FR-015 | ARC-006 | CORE-DD-INSTRUMENT | `read_event_queue`, `check_errors` | `test_no_error_queue_by_default`, `test_reported_events_raise`, `test_after_configuration_respects_the_flag` |
| CORE-FR-016 | ARC-006 | CORE-DD-INSTRUMENT | `Instrument.close` | `test_close_never_raises`, `test_closing_is_idempotent` |
| CORE-FR-020 | ARC-001, ARC-006 | CORE-DD-SCPI, CORE-DD-INSTRUMENT | `ScpiInstrument.connect/initialise/close` | `test_context_manager_closes`, `test_reset_reinitialises`, `TestGenericInstrument` |
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
| CORE-FR-050 | ARC-004 | CORE-DD-FIRMWARE | `FirmwareBuild.from_path`, `load`, `built_at`; the `hint` each caller supplies | `TestReading` (6), `TestDiagnostics` (4), `TestBuildDates` (3), `test_a_missing_manifest_says_how_to_produce_one` |
| CORE-FR-061 | ARC-002, ARC-003 | CORE-DD-TRANSPORT, CORE-DD-SERIAL, CORE-DD-MOCK | `Transport.read_available`, `Transport.discard_input`, `SerialTransport.discard_input`, `MockTransport.discard_input` | `TestStreamReading` (7), notably `test_read_raw_never_returns_on_a_link_without_end_of_message`; `TestStreaming` (2) in `test_serial.py`; `test_connecting_over_a_serial_port_sees_the_echo` |
| CORE-FR-062 | ARC-004 | CORE-DD-SIM, CORE-DD-MOCK | `MockTransport._poll_responder`, `SimulatedTti1604.poll_within` | `test_a_virtual_clock_simulator_is_given_the_read_timeout`, `test_a_read_shorter_than_the_measurement_times_out` |
| CORE-FR-063 | ARC-004, AD-28 | CORE-DD-EVENTS, CORE-DD-INSTRUMENT | `EventSource`, `SourceLogger`, `connecting_as`, `validate_source_name`; `Instrument.EVENT_SOURCE`, `event_source`, `_adopt`; `Transport._logger`; each driver's `self._logger` | `TestSourceNames` (18), `TestPerInstrumentNames` (15), `SWE4-UT-EVENTNAMES` (21) |
| CORE-FR-060 | ARC-004, AD-28 | CORE-DD-EVENTS | `EventLogHandler`, `start_event_log`, `EventTail`, `source_of`; `benchtools run --event-log`; `ScpiInstrument._io_log`; the monitor's `source_key`, `style_of` | `SWE4-UT-EVENTS` (54), `SWE4-UT-TESTBENCH` (32) |
| CORE-FR-064 | ARC-004 | CORE-DD-EVENTS | `log_event`, `jsonable`, `MAX_ITEMS`; `EventLogHandler.emit` (`kind`, `data`) | `SWE4-UT-RUNEVENTS` (21) |
| CORE-FR-065 | ARC-004 | CORE-DD-EVENTS | `log_reading` | `test_log_reading_is_ordinary_text_on_a_console`, `TestDriversLogReadings` (5) |
| CORE-FR-041 | ARC-004 | CORE-DD-SIM | `_unknown_command` | `test_unknown_header_is_recorded_not_ignored`, `test_unknown_query_still_answers` |

### CORE non-functional

| Requirement | Realised by | Verified by |
|---|---|---|
| CORE-NFR-001 | AD-01; `pyproject.toml` `dependencies = []`; `vxi11.py` and the whole J-Link driver import only stdlib | `test_no_mandatory_third_party_imports` (every module parsed); plus the extras-blocked suite run, BENCHTOOLS-SWE4-002 §2.2 |
| CORE-NFR-002 | `requires-python = ">=3.8"`; no newer syntax or library | Inspection |
| CORE-NFR-003 | Lazy imports in `plotting.py`, `visa_backend.py`, `spec.load_mapping` | `test_clear_error_when_matplotlib_is_absent`; the module skips in `test_plotting.py`, `test_visa.py`, `runner/test_cli.py` |
| CORE-NFR-004 | AD-06; `core/validation.py` | `test_nothing_is_sent_when_validation_fails`, plus every `ConfigurationError` test |
| CORE-NFR-005 | CORE-DD-ERR | `TestErrorHandling`, `test_refused_connection_mentions_the_tds3014b_limitation`, `test_unknown_device_name_raises`, `test_unparsable_stb_is_reported` |
| CORE-NFR-006 | `Transport.timeout`, `wait_for_acquisition` deadline, socket timeouts | `test_timeout_must_be_positive`, `test_starved_link_times_out`, `test_silent_instrument_times_out`, `test_timeout_is_restored_after_the_transfer` |
| CORE-NFR-007 | — | 94% measured; BENCHTOOLS-SWE4-002 §3 |
| CORE-NFR-008 | AD-02 | `test_core_never_references_an_instrument`, `test_core_is_importable_on_its_own` |
| CORE-NFR-009 | AD-02 | `test_layer_dependencies_point_one_way` (over 50 sources), `test_analysis_is_importable_without_instruments` |

## 6. ANA requirements to design, code and test

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
| ANA-FR-022 | ARC-002 | ANA-DD-SAMPLES | `SampleSet`, `extract_number` | `SWE4-UT-SAMPLES` (9) |

## 7. INST and SCOPE requirements to design, code and test

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

## 8. JLINK requirements to design, code and test

| Requirement | Architecture | Design unit | Source | Verifying test(s) |
|---|---|---|---|---|
| JLINK-FR-001 | JLINK-ARC-001 | JLINK-DD-GDBMI | `jlink/gdbmi.py` | `SWE4-UT-GDBMI` (37), notably `test_repeated_key_yields_every_entry`, `test_mixed_names_keep_their_keys`, `test_nested_structures`, `test_text_is_unescaped`, `test_non_mi_lines_are_ignored` |
| JLINK-FR-002 | JLINK-ARC-001 | JLINK-DD-SESSION | `jlink/session.py` | `TestCommands` (7), `TestAsyncRecords` (6), `TestDiagnostics` (3) |
| JLINK-FR-003 | JLINK-ARC-001 | JLINK-DD-SERVER | `jlink/server.py` | `TestDiscovery` (13), `TestCommandLine` (11), `TestServerOutput` (3); notably `test_windows_names_are_searched_first`, `test_install_directories_are_searched_after_path`, `test_a_host_gdb_that_cannot_debug_arm_is_refused`, `test_unattended_flags_are_present`, `test_the_server_is_not_single_run`, `test_a_missing_tool_is_reported_with_what_to_do` |
| JLINK-FR-004 | JLINK-ARC-001 | JLINK-DD-SERVER, JLINK-DD-PROBE | `GdbServer.start`, `JLinkProbe._parse_target` | `test_an_already_listening_port_is_used`, `test_a_remote_server_is_never_spawned`, `test_a_server_that_exits_reports_its_own_output`, `test_resource_parsing` |
| JLINK-FR-005 | JLINK-ARC-001 | JLINK-DD-SERVER | `GdbServer.stop`, `was_spawned` | `test_only_a_spawned_server_is_stopped`, `test_closing_is_idempotent` |
| JLINK-FR-006 | JLINK-ARC-001 | JLINK-DD-PROBE, JLINK-DD-CLI | `JLinkProbe._close`, `leave_halted` | `test_closing_leaves_the_target_running`, `test_closing_can_leave_the_target_halted`, `test_the_target_is_left_running_unless_asked` (7) |
| JLINK-FR-010 | JLINK-ARC-001 | JLINK-DD-CONST | `jlink/constants.py` | `test_limits_are_data_driven`, `test_hardware_breakpoint_limit_is_enforced`, `test_channel_beyond_the_limit_is_rejected` |
| JLINK-FR-011 | JLINK-ARC-001 | JLINK-DD-PROBE | `JLinkProbe.load_symbols` | `test_symbols_are_loaded`, `test_missing_elf_is_reported`, `test_missing_symbols_are_mentioned_in_the_error` |
| JLINK-FR-020 | JLINK-ARC-001 | JLINK-DD-PROBE | `JLinkProbe.flash` | `test_flash_reports_what_was_written`, `test_flash_resets_first_by_default`, `test_a_named_image_is_loaded_before_it_is_read`, `test_preserved_ranges_survive_the_flash`, `test_a_preserved_range_that_will_not_stick_raises`, `test_flash_result_serialises` |
| JLINK-FR-021 | JLINK-ARC-001 | JLINK-DD-PROBE | `JLinkProbe.verify`, `SectionVerdict` | `test_verify_alone_reports_mismatched_sections`, `test_verify_result_serialises` |
| JLINK-FR-022 | JLINK-ARC-001 | JLINK-DD-PROBE | `VerifyResult.matched` | `test_verification_failure_raises`, `test_an_empty_comparison_is_not_a_pass`, `test_flash_without_an_image_is_rejected` |
| JLINK-FR-023 | JLINK-ARC-001 | JLINK-DD-PROBE | `JLinkProbe.erase` | `test_erase_resets_first_and_leaves_flash_blank`, `test_an_erase_that_did_not_happen_raises`, `test_the_blank_check_can_be_skipped`, `test_erase` (CLI), `test_monitor_passthrough`, `TestExecutionModel` |
| JLINK-FR-024 | JLINK-ARC-001 | JLINK-DD-PROBE | `JLinkProbe.image_build`, over CORE-DD-FIRMWARE | `TestWhatWasFlashed` (5), `test_the_reported_version_is_recorded_as_text` |
| JLINK-FR-030 | JLINK-ARC-001 | JLINK-DD-PROBE | `reset`, `run`, `halt`, `step` | `test_reset_halts_by_default`, `test_reset_can_leave_it_running`, `test_step`, `test_run_to_a_location` |
| JLINK-FR-031 | JLINK-ARC-001 | JLINK-DD-PROBE | `is_halted`, `program_counter`, `registers` | `test_program_counter_and_registers`, `test_halt_reports_where` |
| JLINK-FR-032 | JLINK-ARC-001 | JLINK-DD-PROBE, JLINK-DD-CONST | `wait_for_halt`, `HaltReason` | `test_never_reaching_a_breakpoint_times_out`, `test_unknown_halt_reason_does_not_break_the_driver` |
| JLINK-FR-033 | JLINK-ARC-001 | JLINK-DD-PROBE | `set_breakpoint`, `list_breakpoints`, `delete_breakpoint`, `clear_breakpoints` | `TestBreakpoints` (8), notably `test_conditional_breakpoint`, `test_temporary_breakpoint_is_marked` |
| JLINK-FR-034 | JLINK-ARC-001 | JLINK-DD-PROBE, JLINK-DD-CONST | `set_breakpoint(hardware=True)` | `test_hardware_breakpoint_limit_is_enforced` |
| JLINK-FR-035 | JLINK-ARC-001 | JLINK-DD-PROBE | `set_watchpoint` | `test_watchpoints` |
| JLINK-FR-036 | JLINK-ARC-001 | JLINK-DD-PROBE | `run_to` | `test_run_to_a_location`, `test_unreachable_location_is_reported` |
| JLINK-FR-040 | JLINK-ARC-001 | JLINK-DD-PROBE | `read_memory`, `write_memory`, `read_word`, `read_u8`, `read_u16` | `TestMemory` (7), notably `test_large_transfers_are_split`, `test_negative_size_is_rejected` |
| JLINK-FR-041 | JLINK-ARC-001 | JLINK-DD-PROBE | `read_variable`, `write_variable`, `variable_address`, `variable_size` | `TestVariables` (19), notably `test_a_structure_holding_a_string_is_a_structure`, `test_read_string`, `test_memory_agrees_with_the_variable`, `test_value_parsing` |
| JLINK-FR-042 | JLINK-ARC-001 | JLINK-DD-PROBE | `evaluate` | `test_evaluate_expression`, `test_unknown_variable_is_reported` |
| JLINK-FR-043 | JLINK-ARC-001 | JLINK-DD-PROBE | `read_integer` | `TestByteOrderedReads` (6), `test_the_identifier_comes_from_the_part` |
| JLINK-FR-045 | JLINK-ARC-001 | JLINK-DD-PROBE, JLINK-DD-GDBMI | `call_stack`, `StackFrame` | `TestCallStack` (6), notably `test_frames_innermost_first`, `test_frames_carry_source_positions` |
| JLINK-FR-050 | JLINK-ARC-001 | JLINK-DD-RTT | `jlink/rtt.py`, `RttClient.read`, `write`, `SocketRttBackend` | `test_lines_arrive_when_the_target_runs`, `test_read_returns_text`, `test_write_reaches_the_target`, `test_probe_rtt_helpers`; over a real socket: `TestRttOverASocket` (8) |
| JLINK-FR-051 | JLINK-ARC-001 | JLINK-DD-RTT | `read_lines`, `read_line`, `pending_count` | `test_reads_consume`, `test_read_line_waits`, `test_read_line_returns_none_on_timeout`, `test_pending_count`, `test_a_fragmented_line_is_assembled_by_the_client` |
| JLINK-FR-052 | JLINK-ARC-001 | JLINK-DD-RTT | `expect`, `RttTimeout` | `test_expect_finds_a_pattern`, `test_expect_timeout_reports_what_arrived`, `test_rtt_expect_through_the_probe` |
| JLINK-FR-053 | JLINK-ARC-001 | JLINK-DD-RTT | `command` | `test_command_and_reply`, `test_command_discards_older_lines` |
| JLINK-FR-054 | JLINK-ARC-001 | JLINK-DD-PROBE | `JLinkProbe.rtt_lines_within` | `TestIsItRunning` (3), `test_a_board_that_says_nothing_on_rtt` |
| JLINK-FR-055 | JLINK-ARC-001 | JLINK-DD-RTT | `start(log_path=…)`, `_history` | `test_log_file_is_written_and_flushed`, `test_log_path_is_reported`, `test_history_survives_consuming_reads`, `test_probe_rtt_log` |
| JLINK-FR-060 | JLINK-ARC-001 | JLINK-DD-TIMING, JLINK-DD-PROBE | `measure_time_between`, `TimingResult` | `test_recovers_the_exact_interval`, `test_result_records_the_method_and_clock`, `test_method_accepts_a_string` |
| JLINK-FR-061 | JLINK-ARC-001 | JLINK-DD-PROBE, JLINK-DD-CONST | `enable_cycle_counter`, `read_cycle_counter`, `_counter_delta` | `TestCycleCounter` (6), notably `test_dwt_is_enabled_first`, `test_counter_wrap_is_handled` |
| JLINK-FR-062 | JLINK-ARC-001 | JLINK-DD-TIMING | `TimingMethod.HOST_CLOCK` | `test_produces_a_figure`, `test_a_short_interval_is_flagged_untrustworthy` |
| JLINK-FR-063 | JLINK-ARC-001 | JLINK-DD-PROBE | `_measure_target_variables` | `test_from_two_variables_filled_in_by_the_firmware`, `test_reading_one_timer_at_both_points`, `test_without_any_variable_is_rejected` |
| JLINK-FR-064 | JLINK-ARC-001 | JLINK-DD-SWO, JLINK-DD-PROBE | `jlink/swo.py`, `SwoStream`, `_measure_swo` | `SWE4-UT-SWO` (20), `test_recovers_the_interval_without_halting`, `test_a_port_with_no_instrumentation_is_reported`; over a real socket: `TestSwoOverASocket` (8) |
| JLINK-FR-065 | JLINK-ARC-001 | JLINK-DD-TIMING | `resolution_seconds`, `is_trustworthy`, `halts_target` | `test_a_short_interval_is_flagged_untrustworthy`, `test_recovers_the_interval_without_halting`, `test_serialises_for_a_report` |
| JLINK-FR-066 | JLINK-ARC-001 | JLINK-DD-TIMING | `TimingResult` statistics | `test_repeat_gives_statistics`, `test_statistics_over_varying_samples`, `test_repeat_must_be_positive` |
| JLINK-FR-067 | JLINK-ARC-001 | JLINK-DD-TIMING | `TimingResult.seconds` | `test_no_samples_is_an_error_not_a_zero`, `test_repr_survives_no_samples` |
| JLINK-FR-080 | JLINK-ARC-001, RUN-ARC-001 | JLINK-DD-PROBE, RUN-DD-BENCH | `register_driver("jlink", JLinkProbe)` | `test_declared_drivers_are_checked`, `test_the_wrong_kind_of_instrument_is_reported`, `test_simulated_from_a_mapping_uses_the_right_driver` |
| JLINK-FR-081 | JLINK-ARC-001 | JLINK-DD-TIMING, JLINK-DD-PROBE | `as_dict` on every result type | `test_serialises_for_a_report`, `test_verify_result_serialises`, `test_flash_result_serialises`, `test_shipped_specifications_are_valid[firmware_timing.yaml]` |
| JLINK-FR-090 | JLINK-ARC-001 | JLINK-DD-SIM | `jlink/simulator.py` | `SWE4-UT-JLINKSIM` (23) |
| JLINK-FR-100 | JLINK-ARC-001 | JLINK-DD-CLI | `jlink/cli.py` | `SWE4-UT-JLINKCLI` (30) |
| JLINK-FR-101 | JLINK-ARC-001 | JLINK-DD-PROBE, RUN-DD-BENCH | `JLinkProbe.connect(attach=False)`, `JLinkRttReader`, driver `jlink-rtt` | `SWE4-UT-JLINKRTTONLY` (`TestRttOnly`, 3) |
| JLINK-FR-102 | JLINK-ARC-001 | JLINK-DD-PROBE | `JLinkProbe.rtt_samples` | `SWE4-UT-JLINKRTTONLY` (`TestRttSamples`, 3) |

### JLINK non-functional

| Requirement | Evidence |
|---|---|
| JLINK-NFR-001 | `test_no_mandatory_third_party_imports` parses every module and fails on a third-party import at module level; `pyproject.toml` declares no new dependency for the driver. |
| JLINK-NFR-002 | `CORE-DD-PROCESS` uses reader threads rather than `select` (which rejects pipe handles on Windows); `select` is used only on sockets, where Windows supports it; `JLINK-DD-SERVER` searches Windows executable names first. Verified by `SWE4-UT-PROCESS`, `SWE4-UT-JLINKSOCKETS` and `test_windows_names_are_searched_first`; confirmation on a Windows host is JLINK-OPEN-01. |
| JLINK-NFR-003 | `test_resource_parsing`, `test_a_remote_server_is_never_spawned`, `test_the_host_is_an_argument`; both links are TCP by construction (AD-13). |
| JLINK-NFR-004 | `test_result_records_the_method_and_clock`, `test_serialises_for_a_report`, `test_methods_without_cycles_omit_them`, and the CLI's `warning` key (`SWE4-UT-JLINKCLI`). |

## 9. BLE requirements to design, code and test

The element spans two languages, so the *Source* column names the firmware file
where the firmware implements the requirement.

| Requirement | Architecture | Design unit | Source | Verifying test(s) |
|---|---|---|---|---|
| BLE-FR-001 | BLE-ARC-001 | BLE-DD-PROTOCOL | `firmware/include/protocol.h`, `protocol.py` | `SWE4-UT-BLEPROTO` (34), `SWE4-UT-BLEFW` (17) |
| BLE-FR-002 | BLE-ARC-001 | BLE-DD-CMD, BLE-DD-SESSION, BLE-DD-TEST | `firmware/src/cmd_parser.c`, `session.py` | `TestCommands` (6), `test_every_command_has_a_handler_in_the_firmware`; firmware side: `SWE4-UT-FWUNIT` `test_cmd_parser` (47) |
| BLE-FR-003 | BLE-ARC-001 | BLE-DD-CDC, BLE-DD-TEST | `firmware/src/cdc_acm.c` | `test_a_dropping_dongle_says_so`, `test_drop_notices_are_counted`; firmware side: `test_a_full_queue_drops_whole_lines_and_counts_them`, `test_writes_are_serialised_one_at_a_time`, `test_the_tail_of_an_over_long_command_is_not_a_command` |
| BLE-FR-004 | BLE-ARC-001 | BLE-DD-PROFILE, BLE-DD-SCANNER | `AdvertisingProfile.is_complete`, `report_advertising` | `test_a_lossy_capture_is_declared`, `test_a_lossy_link_is_declared_rather_than_averaged`; firmware side: `test_a_dropped_line_is_counted_as_not_reported`, `test_the_counters_reconcile_what_was_seen_and_sent` |
| BLE-FR-010 | BLE-ARC-001 | BLE-DD-TIMESTAMP, BLE-DD-TEST | `firmware/src/timestamp.c` | `test_events_arrive_on_the_nominal_interval`, `test_the_clock_advances_monotonically`; firmware side: `test_timestamp` (11), notably `test_the_counter_is_extended_past_thirty_two_bits` |
| BLE-FR-011 | BLE-ARC-001 | BLE-DD-SESSION, BLE-DD-LATENCY | `Event.host_time`, `LatencySource` | `test_host_time_is_recorded_on_every_event`, `test_both_clocks_are_recorded` |
| BLE-FR-012 | BLE-ARC-001 | BLE-DD-VERSION, BLE-DD-CMD, BLE-DD-FIRMWARE | `firmware_version.h`, `Makefile` (`manifest`), `command_ver` | `TestTheDongleReportsItsBuild` (3); `firmware_version.c`'s local fallback: `test_firmware_version` (3); firmware side: `test_ver_reports_which_build_is_on_the_dongle`, `test_the_build_date_carries_no_spaces` |
| BLE-FR-013 | BLE-ARC-001 | BLE-DD-BOOTLOADER, BLE-DD-CMD | `bootloader.c`, `command_dfu`, `NordicDongle.enter_dfu` | `test_the_dongle_is_asked_into_its_bootloader_first`; firmware side: `test_dfu_answers_before_it_resets` |
| BLE-FR-014 | BLE-ARC-001 | BLE-DD-FIRMWARE, BLE-DD-DONGLE, BLE-DD-CLI | `FirmwareBuild`, `FirmwareStatus`, `check_firmware`, `update_firmware`, `ensure_firmware`, `ble firmware` | `TestStatus` (8), `TestChecking` (7), `TestUpdating` (8), `TestFirmwareCommand` (5), notably `test_the_same_version_rebuilt_is_a_mismatch` and `test_a_flash_that_does_not_take_is_reported` |
| BLE-FR-020 | BLE-ARC-001 | BLE-DD-SCANNER | `firmware/src/ble_scanner.c`, `NordicDongle.scan` | `test_scan_finds_the_sensors`, `test_scanning_finds_sensors` |
| BLE-FR-021 | BLE-ARC-001 | BLE-DD-SCANNER | `scanner_get`, `_sensor_from_event` | `test_a_sensor_with_no_name_is_still_listed` |
| BLE-FR-022 | BLE-ARC-001 | BLE-DD-SCANNER, BLE-DD-CONST | `passes_filter`, `ScanFilter` | `test_filtering_by_name`, `test_filtering_by_signal_strength`, `test_filtering_by_address`, `test_a_name_filter_is_applied` |
| BLE-FR-023 | BLE-ARC-001 | BLE-DD-DONGLE | `NordicDongle.select` | `TestSelection` (8), notably `test_the_address_type_travels_with_the_address` |
| BLE-FR-024 | BLE-ARC-001 | BLE-DD-DONGLE | `command_select` (firmware), `select` | `test_selecting_an_unknown_address_is_allowed` |
| BLE-FR-030 | BLE-ARC-001 | BLE-DD-SCANNER | `report_advertising` | `test_the_events_carry_what_was_advertised`, `test_the_advertising_payload_carries_the_name` |
| BLE-FR-031 | BLE-ARC-001 | BLE-DD-PROFILE | `AdvertisingProfile` | `TestIntervals` (5), `test_the_nominal_interval_is_recovered` |
| BLE-FR-032 | BLE-ARC-001 | BLE-DD-PROFILE | `advertising_events` | `TestCoalescing` (3), `test_channels_rotate` |
| BLE-FR-033 | BLE-ARC-001 | BLE-DD-PROFILE | `expected_jitter_s`, `within_specification` | `TestJitter` (4) |
| BLE-FR-034 | BLE-ARC-001 | BLE-DD-PROFILE | `gaps`, `missed_events` | `TestMissedEvents` (5), `test_a_sensor_that_skips_beacons_is_caught` |
| BLE-FR-035 | BLE-ARC-001 | BLE-DD-PROFILE | `duty_cycle`, `reception_ratio` | `TestDutyCycleAndCounts` (4) |
| BLE-FR-036 | BLE-ARC-001 | BLE-DD-PROFILE | `as_dict`, `_require_intervals` | `test_as_dict_survives_too_few_events`, `test_a_silent_sensor_gives_no_statistics_rather_than_zero` |
| BLE-FR-025 | BLE-ARC-001 | BLE-DD-DONGLE | `strongest` | `TestStrongest` (4) |
| BLE-FR-026 | BLE-ARC-001 | BLE-DD-DONGLE | `NordicDongle.select_by_name` | `test_a_name_fragment_selects_the_strongest_match`, `test_a_name_fragment_ignores_case_by_default`, `test_case_can_be_made_to_matter`, `test_a_fragment_nothing_matches_names_what_was_heard`, `test_an_empty_fragment_is_refused` |
| BLE-FR-040 | BLE-ARC-001 | BLE-DD-NUS | `firmware/src/nus_client.c`, `open_link` | `test_connect_and_disconnect`, `test_connecting_emits_the_ready_event` |
| BLE-FR-041 | BLE-ARC-001 | BLE-DD-NUS, BLE-DD-DONGLE | `nus_client_interval_us` | `test_the_connection_interval_is_recorded` |
| BLE-FR-042 | BLE-ARC-001 | BLE-DD-NUS | `nus_client_write`, `NordicDongle.write` | `test_a_write_reports_what_it_sent`, `test_binary_payloads` |
| BLE-FR-043 | BLE-ARC-001 | BLE-DD-NUS | `nus_client_command`, `NordicDongle.command` | `test_a_command_and_its_reply`, `test_a_command_reports_both_timestamps` |
| BLE-FR-044 | BLE-ARC-001 | BLE-DD-CMD | `command_cmd` (firmware) | firmware `test_a_sensor_that_does_not_reply_is_a_timeout_not_a_measurement`; host side `test_an_unknown_command_still_answers` |
| BLE-FR-045 | BLE-ARC-001 | BLE-DD-DONGLE, BLE-DD-CONST | `NordicDongle._encode` | `test_an_over_long_payload_is_refused_before_sending` |
| BLE-FR-046 | BLE-ARC-001 | BLE-DD-NUS, BLE-DD-CMDARGS, BLE-DD-DONGLE | `nus_client_connect`, `cmd_args_connect`, `NordicDongle._start_connect` | `test_the_connect_window_is_sent_to_the_dongle`, `test_an_out_of_range_connect_window_is_refused_before_sending`, `test_an_older_dongle_is_sent_no_window`; firmware `test_connecting_listens_continuously_for_the_time_asked`, `test_connect_refuses_a_bad_timeout` |
| BLE-FR-047 | BLE-ARC-001 | BLE-DD-CMD, BLE-DD-CMDARGS, BLE-DD-DONGLE | `command_cmd`, `cmd_args_timeout`, `NordicDongle.command` | `TestCommandTimeout` (4); firmware `test_cmd_takes_a_timeout_for_a_slow_command`, `test_cmd_refuses_a_bad_timeout` |
| BLE-FR-048 | BLE-ARC-001 | BLE-DD-DONGLE | `NordicDongle.command_expecting_disconnect`, `DisconnectSample` | `TestExpectingADisconnect` (2, `test_dongle.py`) |
| BLE-FR-049 | BLE-ARC-001 | BLE-DD-DONGLE | `NordicDongle.open_link`, `_disconnect` | `test_a_sensor_that_never_links_is_reported_as_not_connected`, `test_a_link_that_never_becomes_ready_is_reported_as_linked`, `test_a_failed_link_is_closed_so_the_next_attempt_is_not_refused` |
| BLE-FR-050 | BLE-ARC-001 | BLE-DD-NUS, BLE-DD-LATENCY | `nus_client_command`, `ResponseSample` | `test_a_command_reports_both_timestamps`, `test_a_slow_command_takes_longer` |
| BLE-FR-051 | BLE-ARC-001 | BLE-DD-LATENCY | `LatencySource.HOST` | `test_the_host_clock_can_be_asked_for`, `test_the_host_clock_resolves_a_millisecond` |
| BLE-FR-052 | BLE-ARC-001 | BLE-DD-LATENCY | `ResponseTiming` | `TestStatistics` (5), `test_a_measurable_latency` |
| BLE-FR-053 | BLE-ARC-001 | BLE-DD-LATENCY | `is_trustworthy`, `quantisation_s` | `TestTrustworthiness` (6), `test_a_latency_inside_the_connection_interval_is_flagged`, `test_cmd_warns_when_the_figure_is_not_resolvable` |
| BLE-FR-054 | BLE-ARC-001 | BLE-DD-LATENCY | `ResponseTiming._values` | `test_no_samples_is_an_error_not_a_zero` |
| BLE-FR-060 | BLE-ARC-001 | BLE-DD-SESSION | `DongleSession.log_to` | `TestLogging` (6 in the session, 4 in the driver) |
| BLE-FR-061 | BLE-ARC-001 | BLE-DD-SESSION | `_read_line`, `_write_log` | `test_non_protocol_lines_are_ignored`, `test_events_reach_the_log_too` |
| BLE-FR-062 | BLE-ARC-001 | BLE-DD-SESSION | `note`, `log_note` | `test_a_note_can_be_written`, `test_a_note_lands_in_the_log` |
| BLE-FR-070 | BLE-ARC-001 | BLE-DD-CLI | `nordic_dongle/cli.py` | `SWE4-UT-BLECLI` (18) |
| BLE-FR-071 | BLE-ARC-001 | BLE-DD-CLI | `_choose`, `_select`, `_cmd_cmd`, the `--addr`/`--select` exclusive groups in `nordic_dongle/cli.py` | `TestChoosingASensor` (16) |
| BLE-FR-080 | BLE-ARC-001, RUN-ARC-001 | BLE-DD-SIM, RUN-DD-BENCH | `simulator.py`, `register_driver("ble-dongle", …)` | `SWE4-UT-BLESIM` (27), `test_the_top_level_command_dispatches` |
| BLE-FR-100 | BLE-ARC-001, AD-23 | BLE-DD-SCRIPT | `parse_script`, `load_script`, `CommandScript` | `TestReadingTheDocument` (11), `TestTheShippedDocument` (2) |
| BLE-FR-101 | BLE-ARC-001, AD-23 | BLE-DD-SCRIPT | `ScriptStep.matches`, `ScriptStep.pattern` | `TestMatching` (6), `test_a_matching_reply_passes`, `test_a_reply_that_does_not_match_fails_and_shows_both` |
| BLE-FR-102 | BLE-ARC-001, AD-23 | BLE-DD-SCRIPTRUN | `_run_step`, `_is_no_reply` | `test_a_step_that_expected_a_reply_is_an_error`, `test_a_step_that_expected_none_is_still_only_skipped`, `test_nothing_is_recorded_as_a_response` |
| BLE-FR-103 | BLE-ARC-001, AD-23 | BLE-DD-SCRIPT | `_parse_delay`, `_run_step` delay branch | `test_a_delay_waits_and_is_skipped`, `test_the_ways_a_delay_is_written` (4) |
| BLE-FR-104 | BLE-ARC-001, AD-23 | BLE-DD-SCRIPT | `_run_step` listen branch | `test_a_command_with_nothing_promised_is_skipped_but_recorded`, `test_a_step_that_expected_none_is_still_only_skipped`, `test_the_listening_window_is_the_one_given_not_the_timeout` |
| BLE-FR-105 | BLE-ARC-001, AD-23 | BLE-DD-SCRIPT | `StepResult`, `reported_s`, `_elapsed` | `test_the_time_is_the_dongle_clock_at_ten_millisecond_resolution`, `test_the_measured_time_is_kept_beside_the_quoted_one`, `test_the_record_carries_every_column` |
| BLE-FR-106 | BLE-ARC-001, AD-23 | BLE-DD-SCRIPTRUN | `ScriptRun.result`, `passed`, `failed`, `errors`, `skipped`, `CommandScript.checks` | `test_one_failure_fails_the_run`, `test_an_error_outranks_a_failure_in_the_verdict`, `test_a_skipped_step_does_not_make_a_run_pass_on_its_own`, `test_how_many_steps_actually_check_something` |
| BLE-FR-107 | BLE-ARC-001, AD-23 | BLE-DD-SCRIPT | the refusals in `parse_script` and `_Reader` | `TestTheDocumentIsRefused` (11), `TestVariables` (9), `TestTheTimeoutColumn` (5 refusals), `test_connect_names_a_sensor`, `test_connect_has_no_expected_response` |
| BLE-FR-108 | BLE-ARC-001, AD-23 | BLE-DD-SCRIPT, BLE-DD-SESSION | `ScriptRun.markdown`, `write`; `NordicDongle.run_script`, `_note` | `TestTheReport` (7), `TestThroughTheDriver` (2), `test_the_session_log_carries_the_exchange_and_names_the_test` |
| BLE-FR-109 | BLE-ARC-001, AD-23 | BLE-DD-SCRIPTRUN | `_run_step`, `_run_connect`, `_run_disconnect`, `_result` | `TestResultsInPriorityOrder` (5), `TestASensorThatDoesNotAnswer` (4) |
| BLE-FR-110 | BLE-ARC-001, AD-23 | BLE-DD-SCRIPT | `_Reader`, `_substitute`, `parse_script(variables=)` | `TestVariables` (9), `TestTheTemplate` (2) |
| BLE-FR-111 | BLE-ARC-001, AD-23 | BLE-DD-SCRIPT, BLE-DD-SCRIPTRUN | `_interpret`, `_run_connect`, `_run_disconnect`, `CommandScript.connects` | `TestConnectAndDisconnect` (8) |
| BLE-FR-112 | BLE-ARC-001, AD-23 | BLE-DD-SCRIPT, BLE-DD-SCRIPTRUN | `_parse_timeout`, `ScriptStep.timeout_s` | `TestTheTimeoutColumn` (7) |
| BLE-FR-113 | BLE-ARC-001, AD-23 | BLE-DD-SCRIPTRUN | `ScriptStep.expects_disconnect`, `_run_expect_disconnect` | `TestExpectingADisconnect` (3, `test_script.py`) |
| BLE-FR-114 | BLE-ARC-001, AD-23 | BLE-DD-SCRIPT, BLE-DD-SCRIPTRUN | `ScriptStep.note`, `StepResult.notes` | `test_the_note_column_is_carried_to_the_result`, `test_the_report_has_response_time_result_and_note_columns` |
| BLE-FR-115 | BLE-ARC-001, AD-23 | BLE-DD-SCRIPTRUN | `EventLog` | `TestTheEventLog` (2), `test_the_event_log_is_written_where_asked` |
| BLE-FR-116 | BLE-ARC-001, AD-23 | BLE-DD-CLI | `_cmd_script` | `TestScript` (5, `test_cli.py`) |
| BLE-FR-117 | BLE-ARC-001 | BLE-DD-DONGLE | `NordicDongle.sample_command` | `SWE4-UT-BLESAMPLE` (4) |
| BLE-FR-118 | BLE-ARC-001 | BLE-DD-LATENCY | `ResponseSample.value` | `test_the_value_a_reply_reports` (4) |
| BLE-FR-090 | BLE-ARC-001 | BLE-DD-BUILD | `firmware/ses/*.emProject`, `firmware/Makefile`, `firmware/gcc/*.ld`, `firmware/scripts/{package_dfu,compile_check}.*`, `.github/workflows/firmware.yml` | `compile_check.sh` compiles every unit against real SDK headers (BENCHTOOLS-SWE4-002 §4.4); the workflow builds, links, sizes and packages against SDK 17.1.0 (§4.6, BLE-OPEN-01 discharged); flashing remains a bench confirmation item (CON-07) |

### BLE non-functional

| Requirement | Evidence |
|---|---|
| BLE-NFR-001 | `test_no_dynamic_allocation` parses every firmware source; buffers are `PROTO_MAX_*` sized; no recursion by inspection; `compile_check.sh` compiles the whole firmware with `-Wall -Wextra` and no warnings; `SWE4-UT-FWUNIT` exercises the bounded buffers at their limits. |
| BLE-NFR-006 | `SWE4-UT-FWUNIT`: 131 cases run the firmware's own sources on a host, with no dongle, SDK or toolchain; `firmware/nordic_dongle/Makefile` builds it headlessly, and `.github/workflows/firmware.yml` does both on every push touching `firmware/**`. |
| BLE-NFR-002 | `BLE-DD-CDC`: the radio event handler queues and returns. `test_cdc_acm` proves the queue never blocks and that every path leaves its critical region; behaviour under load on the part is a bench confirmation item (BLE-OPEN-02). |
| BLE-NFR-003 | `SWE4-UT-BLEFW`: the header is parsed and compared with the driver's constants - commands, argument bounds, handlers, events, error codes, limits, version. |
| BLE-NFR-004 | `test_no_mandatory_third_party_imports`; pyserial is the `serial` extra, imported inside `_open_link`. |
| BLE-NFR-005 | `test_the_dongle_clock_is_the_default`, `test_as_dict_carries_the_figure_and_its_caveats`, and the CLI's `warning` key. |

## 10. S2LP requirements to design, code and test

| Requirement | Architecture | Design unit | Source | Verifying test(s) |
|---|---|---|---|---|
| S2LP-FR-001 | S2LP-ARC-001, AD-20 | S2LP-DD-SESSION, -CONST | `session.py`, `constants.COMMANDS` | `TestConnection` (9), `TestFraming` (5) |
| S2LP-FR-002 | S2LP-ARC-001 | S2LP-DD-PROTOCOL | `format_command` | `TestFormattingCommands` (12) |
| S2LP-FR-003 | S2LP-ARC-001 | S2LP-DD-SESSION | `read_reply` brace depth | `test_a_reply_spread_over_several_lines`, `test_a_reply_that_never_closes_is_a_timeout_that_says_what_arrived`, `test_nested_braces_do_not_end_the_reply_early` |
| S2LP-FR-004 | S2LP-ARC-001 | S2LP-DD-PROTOCOL | `Reply.hex_number`, `_NUMBER` | `test_a_hex_tag_has_no_0x_in_front_of_it`, `test_every_line_is_kept_verbatim`, `test_output_before_the_reply_is_kept_not_swallowed` |
| S2LP-FR-005 | S2LP-ARC-001 | S2LP-DD-SESSION | `S2lpSession.stop` | `TestStopping` (2), `test_the_stop_character_is_not_a_command` |
| S2LP-FR-010 | S2LP-ARC-001 | S2LP-DD-S2LP, -REGS | `read_register(s)`, `write_register(s)` | `TestRegisters` (12) |
| S2LP-FR-011 | S2LP-ARC-001 | S2LP-DD-REGS | `registers.py` | `SWE4-UT-S2LPREG` (34), notably `TestTheTableItself` (9) |
| S2LP-FR-012 | S2LP-ARC-001 | S2LP-DD-REGS, -S2LP | `Field.insert`, `write_field` | `TestFields` (4 driver, 7 map), notably `test_writing_a_field_leaves_the_rest_of_the_register_alone` |
| S2LP-FR-013 | S2LP-ARC-001 | S2LP-DD-S2LP | `write_registers` access check | `test_a_read_only_register_is_refused_rather_than_ignored`, `test_a_write_to_a_read_only_register_is_ignored` |
| S2LP-FR-014 | S2LP-ARC-001 | S2LP-DD-S2LP, -REGS | `read_all_registers`, `dump_registers`, `contiguous_runs` | `test_read_all_registers_is_not_123_round_trips`, `test_the_dump_names_registers_and_decodes_fields`, `test_what_has_been_changed_is_the_short_answer` |
| S2LP-FR-015 | S2LP-ARC-001 | S2LP-DD-S2LP | address check in `read_registers` | `test_a_mis_framed_reply_is_caught_not_believed`, `test_a_short_reply_is_caught` |
| S2LP-FR-016 | S2LP-ARC-001 | S2LP-DD-S2LP, -CONST | `strobe`, `Strobe` | `TestStrobes` (5) |
| S2LP-FR-017 | S2LP-ARC-001 | S2LP-DD-CONFIG | `parse_register_file`, `load_register_file` | `TestParsingWhatPeopleWrite` (11), `TestLoadingFromDisk` (3) |
| S2LP-FR-018 | S2LP-ARC-001 | S2LP-DD-CONFIG | the refusals in `parse_register_file` | `TestRefusingWhatIsWrong` (8), `test_an_empty_file_is_refused` |
| S2LP-FR-019 | S2LP-ARC-001 | S2LP-DD-CONFIG, -S2LP | `apply_configuration`, `verify_configuration`, `ConfigurationCheck` | `TestApplyingToARadio` (5), `TestVerifyingAgainstARadio` (8), notably `test_a_loose_check_ignores_what_the_file_does_not_name` and `test_a_strict_check_does_not` |
| S2LP-FR-021 | S2LP-ARC-001 | S2LP-DD-CONFIG, -S2LP | `_reset_mode`, `_reset_before_configuring`, `power_cycle` | `TestStartingFromAKnownState` (9), notably `test_a_reset_that_did_not_take_stops_before_writing`; `test_the_reset_strobe_does_not_restore_register_defaults`, `test_the_reset_strobe_leaves_the_register_file_alone` |
| S2LP-FR-020 | S2LP-ARC-001 | S2LP-DD-CONFIG, -S2LP | `format_register_file`, `save_configuration` | `TestWritingAFileBack` (4), `TestCapturingFromARadio` (3) |
| S2LP-FR-030 | S2LP-ARC-001 | S2LP-DD-S2LP | `configure_radio` and the radio properties | `TestRadioConfiguration` (12) |
| S2LP-FR-031 | S2LP-ARC-001 | S2LP-DD-S2LP | `configure_radio` returns `radio_info()` | `test_configure_returns_what_the_radio_says_afterwards` |
| S2LP-FR-032 | S2LP-ARC-001 | S2LP-DD-S2LP, -CONST | `_check_frequency`, `BOARDS`, `SYNTH_BANDS` | `test_a_frequency_outside_the_board_s_band_is_refused` (3), `test_a_frequency_no_s2lp_can_tune_is_refused` (3) |
| S2LP-FR-033 | S2LP-ARC-001 | S2LP-DD-S2LP | `_post_open`, `_read_identity`, `board`, `band` | `test_connecting_configures_nothing`, `test_the_board_is_not_invented`, `test_a_named_board_brings_its_band`, `test_the_band_comes_from_the_named_board` |
| S2LP-FR-035 | S2LP-ARC-001 | S2LP-DD-EEPROM, -S2LP | `eeprom.py`, `_read_eeprom`, `_check_board_against_eeprom`, `band` | `SWE4-UT-S2LPEEPROM` (13) |
| S2LP-FR-034 | S2LP-ARC-001 | S2LP-DD-S2LP | `rssi_dbm_from_register` | `TestRssiConversion` (3), `test_the_rssi_is_encoded_as_the_register_encodes_it` |
| S2LP-FR-040 | S2LP-ARC-001 | S2LP-DD-TRAFFIC, -PACKETS | `transmit`, `transmit_batch` | `TestTransmit` (5) |
| S2LP-FR-041 | S2LP-ARC-001 | S2LP-DD-TRAFFIC, -PACKETS | `receive`, `Packet` | `TestReceive` (4), notably `test_nothing_on_the_air_returns_none_not_an_empty_packet` |
| S2LP-FR-042 | S2LP-ARC-001 | S2LP-DD-TRAFFIC | `capture(continuous=True)`, `_capture_batch` | `test_a_batch_capture_is_not_gap_free`, `test_a_batch_capture_asks_for_the_early_re_arm` |
| S2LP-FR-043 | S2LP-ARC-001, AD-20 | S2LP-DD-PACKETS | `Capture.gaps`, `rearm`, `is_continuous` | `test_a_polled_capture_reports_its_gaps`, `test_a_single_reception_is_continuous` |
| S2LP-FR-044 | S2LP-ARC-001 | S2LP-DD-PACKETS | `Capture.stopped_early` | `test_a_capture_that_gets_nothing_says_so_rather_than_failing` |
| S2LP-FR-045 | S2LP-ARC-001 | S2LP-DD-SESSION | `S2lpSession.log_to` | `TestLogging` (5 session), `test_the_session_log_carries_both_directions` |
| S2LP-FR-046 | S2LP-ARC-001 | S2LP-DD-PACKETS | `PacketLog` | `TestLogs` (6), notably `test_a_truncated_packet_log_still_reads` |
| S2LP-FR-047 | S2LP-ARC-001 | S2LP-DD-TRAFFIC | `stream`, `_stream_batch`, `_stream_polled`, `_annotate`, `FRAME_REGISTERS` | `TestBatchStream` (9), notably `test_it_is_the_default_and_starts_the_loop_once` and `test_a_caller_that_stops_iterating_stops_the_board`; `TestStream` (9), notably `test_each_frame_carries_the_registers_read_after_it` |
| S2LP-FR-048 | S2LP-ARC-001 | S2LP-DD-TRAFFIC | `prepare_traffic`, `_check_tx_source` | `TestTheInterrupt` (8) |
| S2LP-FR-049 | S2LP-ARC-001 | S2LP-DD-PREAMBLE, -TRAFFIC | `preamble.py`, `_enable_pqi`, `measure_preamble`, `check_preamble`; `specs/kepler_preamble.yaml` | `SWE4-UT-S2LPPREAMBLE` (15), `TestPreamble` (7), `TestPreambleCommand` (3) |
| S2LP-FR-070 | S2LP-ARC-001 | S2LP-DD-KEPLER | `decode_kepler_frame` | `SWE4-UT-S2LPKEPLER` (29) |
| S2LP-FR-071 | S2LP-ARC-001 | S2LP-DD-PACKETS, -TRAFFIC | `Packet.registers`, `decoded`, `decode_error` | `test_raw_and_decoded_are_one_record`, `test_a_frame_that_will_not_decode_keeps_its_bytes` |
| S2LP-FR-072 | S2LP-ARC-001 | S2LP-DD-TRAFFIC | `S2lpDevkit.kepler_samples` | `SWE4-UT-S2LPSAMPLES` (6) |
| S2LP-FR-073 | S2LP-ARC-001 | S2LP-DD-TRAFFIC | `S2lpDevkit.kepler_frame` | `SWE4-UT-S2LPFRAME` (3) |
| S2LP-FR-080 | S2LP-ARC-001 | S2LP-DD-S2LP | `S2lpDevkit._record`, `log_event` | `TestDriverRecords` (2) |
| S2LP-FR-081 | S2LP-ARC-001 | S2LP-DD-KEPLER | `CONFIG_PARAMETERS`, `config_parameter`, `name_config`, `permute_poly_any_size` | `TestParameters` (10), `test_a_config_frame_names_its_parameters` |
| S2LP-FR-082 | S2LP-ARC-001 | S2LP-DD-KEPLER | `twf_sample`, `permute_poly`, `odr_hz` | `TestPolynomial` (2), `TestWaveform` (2), `test_odr_codes` |
| S2LP-FR-083 | S2LP-ARC-001 | S2LP-DD-KEPLER | `_response`, `reset_reasons`, `PCB_VERSIONS`, `SENSOR_PHASES`, `PRODUCTS` | `test_response`, `test_a_hires_response_times_in_microseconds`, `test_a_config_response_carries_id_value_pairs`, `test_an_empty_config_response_is_fourteen_bytes`, `test_reset_reasons`, `test_version_names_its_reset_reason_and_pcb`, `test_alive_names_its_phase` |
| S2LP-FR-084 | S2LP-ARC-001 | S2LP-DD-S2LP | `S2lpDevkit.read_setup` | `TestDriver` (2) |
| S2LP-FR-050 | S2LP-ARC-001 | S2LP-DD-SIM | `simulator.py`, `register_driver("s2lp", …)` | `SWE4-UT-S2LPSIM` (25), `test_correct_driver_per_alias` |
| S2LP-FR-060 | S2LP-ARC-001 | S2LP-DD-CLI | `cli.py` | `SWE4-UT-S2LPCLI` (25) |

### S2LP non-functional

| Requirement | Evidence |
|---|---|
| S2LP-NFR-001 | `test_no_mandatory_third_party_imports`; the kit reaches its port through CORE-DD-SERIAL, whose pyserial import is inside `_open_link`. |
| S2LP-NFR-002 | No file in this repository is derived from ST source by copying: the register map holds addresses, reset values, field names and bit positions, and no vendor prose. `docs/s2lp/S2LP_Devkit_Notes.md` §6 records how it was cross-checked and under what terms. |
| S2LP-NFR-003 | `Packet.board_time_us` is named for its unit and its clock, measured on a kit as microseconds (#76); `Capture.gaps` and `rearm` state how a capture was taken. The timer's resolution and its 71.6-minute wrap are stated in `packets.py`, in SWE.3 and in the notes. |
| S2LP-NFR-004 | `test_connecting_configures_nothing`; transmission is only `transmit`/`transmit_batch`, each an explicit call. |

## 11. PSU requirements to design, code and test

| Requirement | Architecture | Design unit | Source | Verifying test(s) |
|---|---|---|---|---|
| PSU-FR-001 | PSU-ARC-001 | PSU-DD-PSU | `set_voltage`, `set_current_limit`, `voltage_setpoint`, `current_limit` | `TestSetting` (8) |
| PSU-FR-002 | PSU-ARC-001 | PSU-DD-PSU, PSU-DD-CONST | `_check_range` | `test_an_impossible_voltage_is_refused_before_it_is_sent` (3), `test_an_impossible_current_limit_is_refused` (2), `test_an_out_of_range_setting_is_rejected_and_the_setpoint_kept` |
| PSU-FR-003 | PSU-ARC-001 | PSU-DD-PSU | `_quantise` | `test_the_setpoint_read_back_agrees_to_the_read_back_resolution`, `test_a_value_between_steps_is_rounded_as_the_supply_rounds_it` |
| PSU-FR-004 | PSU-ARC-001 | PSU-DD-PSU | `_check_channel` | `test_a_channel_that_does_not_exist_is_named` (4), `test_a_channel_that_does_not_exist_is_refused` |
| PSU-FR-005 | PSU-ARC-001 | PSU-DD-PSU | `configure_channel` | `test_configure_sets_the_limit_before_the_voltage` |
| PSU-FR-006 | PSU-ARC-001, AD-21 | PSU-DD-PSU | `_check_tracking`, called from `set_voltage`, `set_current_limit`, `output_on`, `output_off`; `SimulatedGpd._set` and `_follow` model the supply's silence | `TestTracking` (14 in `test_psu.py`), `TestTracking` (10 in `test_simulator.py`) |
| PSU-FR-010 | PSU-ARC-001 | PSU-DD-PSU | `measure_voltage`, `measure_current`, `_parse_reading` | `TestMeasuring` (8) |
| PSU-FR-011 | PSU-ARC-001 | PSU-DD-PSU | `ChannelReading.power`, `measure_power` | `test_power_is_derived_from_both_readings` |
| PSU-FR-012 | PSU-ARC-001 | PSU-DD-PSU | `read_channel`, `read_all` | `test_read_channel_gathers_everything_at_once`, `test_read_all_covers_every_channel` |
| PSU-FR-020 | PSU-ARC-001 | PSU-DD-PSU, PSU-DD-SIM | `ChannelReading.mode`, `channel_mode` | `TestCurrentLimit` (5), notably `test_the_rail_is_below_its_setpoint_there` |
| PSU-FR-021 | PSU-ARC-001 | PSU-DD-PSU, PSU-DD-CONST | `status`, `SupplyStatus` | `TestStatus` (6) |
| PSU-FR-022 | PSU-ARC-001 | PSU-DD-PSU | `status` length check | `test_a_short_reply_blames_the_line_rate` |
| PSU-FR-023 | PSU-ARC-001 | PSU-DD-PSU | `ChannelReading.regulated` | `test_regulated_is_the_question_a_test_actually_means` |
| PSU-FR-024 | PSU-ARC-001 | PSU-DD-PSU | `read_event_queue` | `TestErrors` (6) |
| PSU-FR-030 | PSU-ARC-001, AD-19 | PSU-DD-PSU | `output_on`, `output_off`, `set_output`, `is_output_on` | `TestOutputSwitching` (11), notably `test_switching_a_channel_off_parks_it_at_zero_volts` |
| PSU-FR-031 | PSU-ARC-001, AD-19 | PSU-DD-PSU | `_parked` | `test_the_setpoint_survives_being_switched_off` |
| PSU-FR-032 | PSU-ARC-001, AD-19 | PSU-DD-PSU | `set_voltage` parked branch | `test_setting_a_voltage_on_a_parked_channel_does_not_energise_it`, `test_and_that_new_setpoint_is_what_comes_up` |
| PSU-FR-033 | PSU-ARC-001 | PSU-DD-PSU | `set_current_limit` | `test_the_current_limit_is_not_parked` |
| PSU-FR-034 | PSU-ARC-001, AD-19 | PSU-DD-PSU | `output_off` | `test_the_last_channel_off_opens_the_real_switch` |
| PSU-FR-035 | PSU-ARC-001 | PSU-DD-PSU | `all_outputs_on`, `all_outputs_off` | `test_all_outputs_off_really_switches_off`, `test_all_outputs_on_restores_every_parked_channel` |
| PSU-FR-040 | PSU-ARC-001 | PSU-DD-PSU | `_post_open`, `_read_identity` | `test_connecting_changes_nothing`, `test_it_knows_the_output_was_already_on`, `TestConnection` (7) |
| PSU-FR-041 | PSU-ARC-001 | PSU-DD-PSU, PSU-DD-CONST | `_pace`, `_default_command_interval` | `TestPacing` (7) |
| PSU-FR-042 | PSU-ARC-001 | PSU-DD-PSU | `_normalise_resource` | `test_a_bare_port_name_is_a_serial_port`, `test_resource_forms` (5) |
| PSU-FR-043 | PSU-ARC-001 | PSU-DD-PSU | `reset` | `TestReset` (3) |
| PSU-FR-044 | PSU-ARC-001 | PSU-DD-PSU | `measure_voltage`, `measure_current` | `test_the_supply_s_voltage_and_current`, `test_a_channel_reading_logs_both` |
| PSU-FR-050 | PSU-ARC-001 | PSU-DD-SIM | `simulator.py`, `register_driver("gpd3303d", …)` | `SWE4-UT-PSUSIM` (20), `test_correct_driver_per_alias` |
| PSU-FR-060 | PSU-ARC-001 | PSU-DD-CLI | `cli.py`, including the current-limit and tracking notes in `_cmd_read` | `SWE4-UT-PSUCLI` (23), notably `TestTrackingIsVisibleWhenReading` (3) |

### PSU non-functional

| Requirement | Evidence |
|---|---|
| PSU-NFR-001 | `test_no_mandatory_third_party_imports`; the supply reaches its port through CORE-DD-SERIAL, whose pyserial import is inside `_open_link`. |
| PSU-NFR-002 | `test_set_does_not_switch_the_output_on`, `test_setting_a_voltage_on_a_parked_channel_does_not_energise_it`, `test_connecting_changes_nothing`. Energising is always an explicit call. |
| PSU-NFR-003 | Volts, amps and watts throughout; `ChannelReading` carries `mode`, and `read` on the command line warns when a channel is in current limit. |

## 12. DMM requirements to design, code and test

| Requirement | Architecture | Design unit | Source | Verifying test(s) |
|---|---|---|---|---|
| DMM-FR-001 | DMM-ARC-001 | DMM-DD-CONST, DMM-DD-DMM | `connect`, `DEFAULT_BAUDRATE`, `BYTESIZE`, `PARITY`, `STOPBITS` | `test_the_handshake_lines_are_driven_for_a_serial_port` |
| DMM-FR-002 | DMM-ARC-001, CORE-ARC-002 | DMM-DD-DMM, `transport.serial_port` | `connect`, `SerialTransport._open_link` | `test_the_handshake_lines_are_driven_for_a_serial_port`, `test_requested_states_are_applied_after_opening` |
| DMM-FR-003 | DMM-ARC-001 | DMM-DD-DMM | `connect` (`dsrdtr=False`) | `test_the_handshake_lines_are_driven_for_a_serial_port` |
| DMM-FR-004 | DMM-ARC-001 | DMM-DD-DMM | `_normalise_resource` | `test_a_bare_port_name_is_a_port_not_a_host` |
| DMM-FR-005 | DMM-ARC-001 | DMM-DD-DMM | `_read_identity` | `test_identity_comes_from_the_driver`, `test_info_says_the_identity_is_the_driver_s_own` |
| DMM-FR-006 | DMM-ARC-001 | DMM-DD-DMM | `_post_open`, `remote` | `test_connecting_enters_remote_mode`, `test_remote_mode_can_be_declined` |
| DMM-FR-007 | DMM-ARC-001 | DMM-DD-DMM | `local` | `test_going_local_stops_the_stream` |
| DMM-FR-008 | DMM-ARC-001 | DMM-DD-DMM | `_post_open` | `test_connecting_does_not_touch_the_operate_key`, `test_operate_toggles_rather_than_switching_on` |
| DMM-FR-009 | DMM-ARC-001 | DMM-DD-DMM | `read` | `test_a_silent_meter_names_both_states_that_cause_it` |
| DMM-FR-010 | DMM-ARC-001 | DMM-DD-PROTO | `find_frame_start`, `FrameAssembler.frames` | `test_complete_frames_are_recovered_from_a_stream`, `test_a_partial_frame_is_held_until_the_rest_arrives` |
| DMM-FR-011 | DMM-ARC-001 | DMM-DD-PROTO | `decode` | `test_decoding_from_the_wrong_offset_is_refused`, `test_a_short_frame_is_refused` |
| DMM-FR-012 | DMM-ARC-001 | DMM-DD-PROTO, DMM-DD-CONST | `digits_text`, `SEGMENT_PATTERNS` | `TestSegmentDecoding` (13) |
| DMM-FR-013 | DMM-ARC-001 | DMM-DD-PROTO | `digits_text` | `test_an_unknown_pattern_is_marked_not_dropped` |
| DMM-FR-014 | DMM-ARC-001 | DMM-DD-PROTO | `decode` | `test_ac_is_reported`, `TestScaling` (9) |
| DMM-FR-015 | DMM-ARC-001 | DMM-DD-PROTO | `unit_and_scale` | `TestScaling` (9) |
| DMM-FR-016 | DMM-ARC-001 | DMM-DD-PROTO | `unit_and_scale` | `test_the_four_hundred_ohm_range_is_not_scaled`, `test_every_other_ohms_range_displays_kilohms` (3) |
| DMM-FR-017 | DMM-ARC-001 | DMM-DD-PROTO | `unit_and_scale` | `test_hertz_wins_over_the_measurement_type` |
| DMM-FR-018 | DMM-ARC-001 | DMM-DD-PROTO | `decode`, `OVERRANGE_TEXT` | `test_overrange_is_not_a_number`, `test_a_value_too_large_for_the_display_becomes_overrange` |
| DMM-FR-019 | DMM-ARC-001 | DMM-DD-PROTO, DMM-DD-CLI | `Reading.text`, `_as_dict` | `test_the_display_text_is_reported_beside_the_value` |
| DMM-FR-020 | DMM-ARC-001 | DMM-DD-PROTO | `Reading.held` | `test_a_held_display_is_flagged`, `test_a_reviewed_minimum_is_also_held`, `test_a_live_reading_is_not_held`, `test_a_held_reading_is_flagged_rather_than_hidden` |
| DMM-FR-021 | DMM-ARC-001 | DMM-DD-PROTO | `decode` | `test_the_function_flags_reach_the_frame`, `test_the_status_flags_reach_the_frame` |
| DMM-FR-022 | DMM-ARC-001 | DMM-DD-PROTO | `Reading.raw` | `test_the_raw_frame_is_kept_as_evidence` |
| DMM-FR-023 | DMM-ARC-001 | DMM-DD-DMM, DMM-DD-CONST | `press`, `KEYS` | `test_an_unknown_key_is_refused_by_name`, `test_an_unknown_key_fails_without_a_traceback` |
| DMM-FR-024 | DMM-ARC-001 | DMM-DD-DMM | `_send_character`, `_await_echo` | `test_a_dropped_keystroke_is_resent`, `test_every_command_is_echoed` |
| DMM-FR-025 | DMM-ARC-001 | DMM-DD-DMM | `_send_character` | `test_a_meter_that_never_echoes_is_reported_with_the_likely_cause` |
| DMM-FR-026 | DMM-ARC-001 | DMM-DD-PROTO | `FrameAssembler.residue`, `_drain` | `test_an_echo_is_recovered_as_residue`, `test_a_digit_byte_equal_to_a_key_character_is_not_mistaken_for_an_echo` |
| DMM-FR-027 | DMM-ARC-001 | DMM-DD-DMM | `_receive`, `_drain` (via `Transport.read_available`) | `TestTheSerialLink` (2): the #115 regression over pyserial's `loop://` |
| DMM-FR-028 | DMM-ARC-001 | DMM-DD-PROTO | `frame_problem`, `FrameAssembler.frames` | `TestFrameValidation` (6), `test_a_stream_joined_part_way_through_a_frame_resynchronises` |
| DMM-FR-029 | DMM-ARC-001 | DMM-DD-DMM | `_select_type`, `_select_coupling`, `_await`, `Reading.function` | `TestConfirmation` (3), `test_an_echo_is_not_found_inside_a_frame`; on hardware `test_a_tour_of_the_safe_functions` and the panel test |
| DMM-FR-030 | DMM-ARC-001 | DMM-DD-DMM, DMM-DD-CONST | `set_range`, `select_auto_range`, `RANGES` | `TestRanges` (6) in `test_dmm.py` |
| DMM-FR-031 | DMM-ARC-001 | DMM-DD-DMM | `measure`, `_discard_input` | `test_a_measurement_is_taken_after_the_call` |
| DMM-FR-032 | DMM-ARC-001 | DMM-DD-DMM, DMM-DD-CONST | `_patience`, `GATE_TIME` | `test_the_ten_second_gate_is_waited_for`; on hardware `test_the_frequency_gate` |
| DMM-FR-033 | DMM-ARC-001 | DMM-DD-DMM | `select_hertz`, frequency branch of `set_range` | `test_hertz_needs_an_ac_range`, `test_the_ten_second_gate_is_waited_for` |
| DMM-FR-034 | DMM-ARC-001 | DMM-DD-DMM | `Tti1604.read` | `test_the_meter_s_reading` |
| DMM-FR-045 | DMM-ARC-001 | DMM-DD-DMM, DMM-DD-SIM | `connect(simulated_value=...)` | `test_the_bench_can_say_what_the_simulated_meter_reads`; `specs/sensor_power_signal_and_link.yaml` against `benches/simulated_bench.yaml` |
| DMM-FR-046 | DMM-ARC-001 | DMM-DD-SIM | `SimulatedTti1604`: `frame`, `_digit_bytes`, `_auto_range_code`, `poll_within`, `measurement_time` | `TestTheMeterAsTheManualDescribesIt` (11) |
| DMM-FR-070 | DMM-ARC-001 | DMM-DD-CLI | `cli.py` | `test_cli.py` (8) |
| DMM-FR-080 | DMM-ARC-001 | — (a test artefact, ETB-SWE4-001 §1.6) | `tests/bench/tti1604/test_bench.py`, `conftest.py` | `SWE4-UT-DMMBENCH`: dry run against the simulator, 10 passed, 4 skipped (the reference tests) with no reference and with each reference in turn; on hardware when a meter is attached |
| DMM-FR-081 | DMM-ARC-001 | — (a bench tool, as `examples/10_psu_front_panel_check.py` is for the supply) | `examples/12_dmm_front_panel_check.py` | `SWE4-UT-DMMPANEL` (7): every step taken and logged with the driver's read-back, answers and a mismatch recorded, `q` stopping early, and the meter left on DC volts, auto, local after a completed, stopped or failed run |
| DMM-NFR-001 | DMM-ARC-001 | DMM-DD-DMM | pyserial reached only through `SerialTransport`; `sim://` needs none | `test_layer_dependencies_point_one_way`, the suite runs with no serial library |
| DMM-NFR-002 | DMM-ARC-001 | DMM-DD-DMM, DMM-DD-CLI | no call sends `g`; no `on` sub-command exists | `test_connecting_does_not_touch_the_operate_key` |
| DMM-NFR-003 | DMM-ARC-001 | DMM-DD-CONST | module docstring cites each source; open items listed | Inspection: `docs/dmm/TTi1604_Notes.md` §1, §5 |
| DMM-NFR-004 | DMM-ARC-001 | DMM-DD-CONST | facts recorded in this project's form; licence and authorship cited | Inspection: `docs/dmm/TTi1604_Notes.md` §1 |

## 13. PICO requirements to design, code and test

Firmware tests are in `firmware/pico_sht30/test/` (`SWE4-UT-PICOFW`); Python
tests in `tests/instruments/pico_sht30/`.

| Requirement | Architecture | Design unit | Source | Verifying test(s) |
|---|---|---|---|---|
| PICO-FR-001 | PICO-ARC-001 | PICO-DD-PROTOCOL, PICO-DD-PARSER | `cmd_line_push`, `cmd_execute`, `cmd_rd_begin` | `test_a_line_is_ready_at_lf`, `test_cr_is_ignored`, `test_a_blank_line_has_no_reply`, `test_rd_name` (C); `test_commands_agree`, `test_errors_agree`, `test_rd` (simulator) |
| PICO-FR-002 | PICO-ARC-001 | PICO-DD-VERSION, PICO-DD-BUILD | `firmware_version.h`, `firmware_version.c`, `CMakeLists.txt` (`FIRMWARE_GIT_SHA`) | `test_rd_sha_reports_the_injected_commit`, `test_rd_identity_matches_the_header` (C); `test_name_and_copyright_agree`, `test_version_is_semantic`; inspection of `CMakeLists.txt` for the SHA injection |
| PICO-FR-003 | PICO-ARC-001 | PICO-DD-PARSER | `cmd_execute` lookup and argument check | `test_an_unknown_command_is_refused`, `test_commands_are_case_sensitive`, `test_an_unexpected_argument_is_refused`, `test_more_tokens_than_are_stored_is_still_refused`, `test_ver_temp_and_reset_are_no_longer_commands`, `test_rd_without_an_option_is_refused`, `test_rd_with_two_options_is_refused`, `test_a_refused_ecureset_does_not_reboot` (C); `test_rd_needs_exactly_one_option`, `test_removed_commands_are_unknown` (3) |
| PICO-FR-004 | PICO-ARC-001 | PICO-DD-PARSER | `cmd_line_push` discard state, `cmd_report_overflow` | `test_an_over_length_line_is_dropped_whole`, `test_the_line_after_an_overflow_is_accepted`, `test_the_longest_line_that_fits_is_ready`, `test_an_overflow_is_reported` (C) |
| PICO-FR-005 | PICO-ARC-001 | PICO-DD-PARSER, PICO-DD-MAIN | `cmd_rd`, `main` | `test_rd_identity_does_not_touch_the_sensor` (C); `test_identity_survives_a_missing_sensor` |
| PICO-FR-006 | PICO-ARC-001 | PICO-DD-PROTOCOL, PICO-DD-VERSION, PICO-DD-PARSER | `cmd_rd`, `cmd_rd_fields`, `firmware_g_name`, `firmware_g_copyright`, `firmware_g_version`, `firmware_g_sha` | `test_rd_name`, `test_rd_copyright`, `test_rd_version`, `test_rd_sha_reports_the_injected_commit`, `test_rd_identity_matches_the_header` (C); `test_rd` (simulator: the four identity options) |
| PICO-FR-007 | PICO-ARC-001 | PICO-DD-PARSER, PICO-DD-DRIVER | `cmd_rd` (`NAK` branch), `PicoSht30.rd`, `RdRefusedError` | `test_rd_unknown_option_is_a_nak`, `test_rd_options_are_case_sensitive`, `test_rd_a_partial_option_is_a_nak`, `test_rd_the_longest_option_is_echoed_whole` (C); `test_rd[rd colour-…]` (simulator), `test_nak` |
| PICO-FR-010 | PICO-ARC-001 | PICO-DD-BOARD, PICO-DD-HAL | `board_config.h`, `hal_init` | `test_default_address_agrees`; inspection of `board_config.h`; the target build |
| PICO-FR-020 | PICO-ARC-001 | PICO-DD-SHT30, PICO-DD-PARSER | `sht30_measure`, `cmd_rd_temperature` | `test_measure_sends_the_high_repeatability_command`, `test_measure_waits_out_the_conversion_then_reads_six_bytes`, `test_rd_temperature_takes_one_measurement` (C); `test_every_reading_is_a_new_measurement` |
| PICO-FR-021 | PICO-ARC-001 | PICO-DD-SHT30, PICO-DD-PARSER | `sht30_crc8`, `sht30_take_word`, `cmd_rd_temperature` | `test_crc_matches_the_datasheet_check_value`, `test_measure_reports_a_corrupted_frame`, `test_rd_temperature_with_a_corrupted_frame`, `test_status_with_a_corrupted_word`, `test_read_status_checks_the_crc` (C); `test_error` (crc), `test_a_crc_failure_affects_one_reading` |
| PICO-FR-022 | PICO-ARC-001 | PICO-DD-SHT30 | `sht30_ticks_to_millicelsius` | `test_temperature_end_points`, `test_temperature_mid_scale`, `test_temperature_rounds_to_nearest`, `test_humidity_end_points_and_mid_scale` (C); `test_matches_the_firmware_vectors` (5) |
| PICO-FR-023 | PICO-ARC-001 | PICO-DD-SHT30, PICO-DD-PARSER | `sht30_from_hal`, `cmd_from_sht30`, `cmd_rd_temperature` | `test_measure_reports_an_absent_sensor`, `test_measure_reports_a_bus_timeout`, `test_measure_reports_a_nack_on_the_read`, `test_rd_temperature_with_no_sensor`, `test_rd_temperature_with_no_answer_to_the_read`, `test_rd_temperature_with_a_bus_timeout`, `test_rd_temperature_with_a_bus_timeout_on_the_read`, `test_status_with_no_sensor`, `test_status_with_a_bus_timeout`, `test_sreset_with_no_sensor` (C); `test_faults` |
| PICO-FR-024 | PICO-ARC-001 | PICO-DD-SHT30, PICO-DD-PARSER | `sht30_read_status`, `cmd_status` | `test_read_status`, `test_status_reports_the_register`, `test_status_with_no_sensor` (C); `test_status_after_power_up` |
| PICO-FR-025 | PICO-ARC-001 | PICO-DD-SHT30, PICO-DD-MAIN | `sht30_soft_reset`, `cmd_sreset`, `main` | `test_soft_reset_sends_the_command_and_waits`, `test_soft_reset_of_an_absent_sensor_does_not_wait`, `test_sreset` (C); inspection of `main.c` |
| PICO-FR-026 | PICO-ARC-001 | PICO-DD-SHT30 | `sht30_decode` | `test_a_bad_temperature_crc_leaves_the_reading_untouched`, `test_a_bad_humidity_crc_leaves_the_reading_untouched`, `test_read_status_checks_the_crc` (C) |
| PICO-FR-027 | PICO-ARC-001 | PICO-DD-TEXT, PICO-DD-PARSER, PICO-DD-CONST | `text_centi`, `cmd_rd_temperature`, `milli_to_centi_text` | `test_centi_units_have_two_places`, `test_centi_rounds_half_away_from_zero`, `test_negative_centi_units_carry_the_sign`, `test_centi_never_prints_minus_zero`, `test_centi_extremes_are_formatted`, `test_rd_temperature_has_two_places`, `test_rd_temperature_is_rounded`, `test_rd_temperature_below_zero`, `test_rd_temperature_just_below_zero_has_no_sign`, `test_rd_temperature_with_no_sensor` (C); `test_two_places_half_away_from_zero` (12), `test_rd_temperature`, `test_error` (3) |
| PICO-FR-030 | PICO-ARC-001 | PICO-DD-PARSER, PICO-DD-HAL | `cmd_ecureset`, `cmd_after`, `hal_reboot`, `hal_reboot_to_bootloader` | `test_ecureset_replies_before_rebooting`, `test_bootsel_replies_before_rebooting`, `test_a_refused_ecureset_does_not_reboot` (C); `test_ecureset` (simulator) |
| PICO-FR-031 | PICO-ARC-001 | PICO-DD-BUILD | `CMakeLists.txt`, `pico_sdk_import.cmake` | Target build of the #131 firmware: `pico_sht30.uf2`, 58 368 B; 28 764 B text, 3 476 B bss, 0 warnings (ETB-SWE4-002 §13A.2); flashed and run on a Pico 2 (§13A.7) |
| PICO-FR-040 | PICO-ARC-001 | PICO-DD-DRIVER | `_post_open`, `firmware_info` | `test_another_device_is_refused`, `test_connecting_sends_only_rd`, `test_connect_through_the_factory` |
| PICO-FR-041 | PICO-ARC-001 | PICO-DD-DRIVER | `firmware_info`, `FirmwareInfo`, `name`, `version`, `sha`, `_read_identity` | `TestIdentity` (8): `test_name_version_and_sha`, `test_firmware_info`, `test_identity`, `test_a_different_version_is_reported_as_it_is` |
| PICO-FR-042 | PICO-ARC-001 | PICO-DD-DRIVER | `read`, `Reading` | `TestReading` (9): `test_temperature`, `test_below_zero`, `test_two_decimal_places`, `test_every_reading_is_a_new_measurement` |
| PICO-FR-043 | PICO-ARC-001 | PICO-DD-DRIVER | `execute`, `rd`, `SensorError` | `test_status_with_no_sensor`, `test_err_reply`, `test_a_malformed_err_reply` |
| PICO-FR-044 | — | — | — | **Withdrawn** (#131): `rd temperature` carries no raw word. The format check that replaces it is traced under PICO-FR-047. |
| PICO-FR-045 | PICO-ARC-001 | PICO-DD-DRIVER | `_normalise_resource` | `test_resource_forms` (6) |
| PICO-FR-046 | PICO-ARC-001 | PICO-DD-DRIVER | `status`, `SensorStatus`, `soft_reset_sensor`, `reset` (`ecureset`), `enter_bootloader` | `TestStatusAndControl` (9), notably `test_reboot_is_ecureset` |
| PICO-FR-047 | PICO-ARC-001 | PICO-DD-DRIVER | `rd`, `read`, `NoReadingError`, `RdRefusedError` | `TestRd` (4): `test_other_options`, `test_nak`, `test_err_reply`, `test_a_reply_that_is_neither_ack_nor_nak`; `test_a_reply_for_another_option_is_refused`; `test_a_value_not_to_two_places_is_refused` (5); `TestFailedReadings`: `test_error` (3), `test_no_reading_is_an_instrument_error` |
| PICO-FR-048 | PICO-ARC-001 | PICO-DD-DRIVER | `PicoSht30.read` | `test_the_thermometer_s_temperature` |
| PICO-FR-050 | PICO-ARC-001 | PICO-DD-SIM | `simulator.py`, `register_driver("pico-sht30", …)` | `SWE4-UT-PICOSIM` (36), `test_faults` |
| PICO-FR-060 | PICO-ARC-001 | PICO-DD-CLI | `cli.py`, `benchtools/cli.py` | `test_temp`, `test_temp_series`, `test_count_must_be_positive`, `test_status`, `test_sreset_and_bootsel`, `test_json_file`, `test_connection_failure_is_reported`, `test_reachable_from_the_top_level` |
| PICO-FR-061 | PICO-ARC-001 | PICO-DD-CLI | `_cmd_info`, `_cmd_rd`, `_cmd_ecureset` | `test_info`, `test_rd` (5), `test_rd_rejects_an_unknown_option`, `test_ecureset` |
| PICO-FR-070 | PICO-ARC-001 | PICO-DD-FLASH | `PicoFlasher._enter_bootloader`, `find_bootloader_drives`, `candidate_roots`, `touch_1200` | `test_success_from_running_firmware`, `test_success_from_bootloader`, `test_falls_back_to_1200_baud_when_the_protocol_does_not_answer`, `test_touch_1200_error_is_a_note_not_a_failure`, `test_touch_1200_note_reaches_the_result`, `test_drive_is_recognised_by_its_info_file`, `test_windows_roots`, `test_linux_roots`, `test_macos_roots` |
| PICO-FR-071 | PICO-ARC-001 | PICO-DD-FLASH | `Uf2Image.parse`, `for_rp2350`, `is_thermometer` (the firmware name) | `test_image_is_parsed`, `test_not_a_whole_number_of_blocks`, `test_bad_magic`, `test_missing_file`, `test_rp2040_image_is_refused`, `test_other_firmware_needs_any_image` |
| PICO-FR-072 | PICO-ARC-001 | PICO-DD-FLASH | `copy_image`, `PicoFlasher.flash` | `test_copy_image_writes_the_file`, `test_copy_error_while_drive_remains`, `test_copy_error_after_the_drive_went_is_not_an_error`, `test_copy_failure` |
| PICO-FR-073 | PICO-ARC-001 | PICO-DD-FLASH | `PicoFlasher._verify` (`rd name`, `rd version`, `rd sha` through `firmware_info`), `Uf2Image.version`, `Uf2Image.sha`, `_port_after`, `find_pico_ports`, `FlashResult` | `test_success_from_running_firmware`, `test_version_mismatch_is_reported_not_raised`, `test_build_mismatch_is_reported` (a commit SHA mismatch), `test_ambiguous_sha_is_not_compared`, `test_missing_version_is_not_compared`, `test_port_found_by_vendor_id`, `test_no_verify` |
| PICO-FR-074 | PICO-ARC-001 | PICO-DD-FLASH | `PicoFlasher._wait_for`, `_one_drive`, `_port_after`, `candidate_roots` | `test_bootloader_timeout`, `test_no_drive_and_no_port`, `test_two_drives_need_drive_option`, `test_drive_that_never_goes_away`, `test_port_that_never_comes_back`, `test_other_systems_are_unsupported` |
| PICO-FR-075 | PICO-ARC-001 | PICO-DD-CLI, PICO-DD-FLASH | `_cmd_flash`, `build_parser`, `main` (standalone sub-commands), `FlashResult.as_dict` | `test_cli_flash`, `test_cli_flash_mismatch_exits_1`, `test_cli_flash_error_exits_1` |
| PICO-FR-076 | PICO-ARC-001 | PICO-DD-FLASH, PICO-DD-SIM | `SimulatedRp2350` (`copy` takes the image's version and SHA), `SimulatedPicoSht30.on_bootloader` | `test_simulated_drive_is_removed`, and every flasher test above that uses the `board` fixture |

### PICO non-functional

| Requirement | Evidence |
|---|---|
| PICO-NFR-001 | `hal.h` is the only seam; `hal_pico.c` is the only file including SDK headers and is excluded from the host test build, which compiles the other sources unchanged (`SWE4-UT-PICOFW`, 83 cases). |
| PICO-NFR-002 | `test_firmware_uses_no_stdio_formatting`, `test_firmware_sources_use_tabs`; review against MISRA C:2012 in `docs/pico_sht30/Pico_SHT30_Notes.md` §6, with deviations recorded there and in `hal_pico.c`. No `malloc`, no recursion, fixed-width types throughout. |
| PICO-NFR-003 | Target build and host test build both pass with `-Wall -Wextra -Wconversion -Wshadow -Wstrict-prototypes -Werror`; host tests pass under ASan and UBSan (ETB-SWE4-002 §13A). |
| PICO-NFR-004 | `SWE4-UT-PICOFWPROTO` (9): `test_commands_agree`, `test_errors_agree`, `test_protocol_version_agrees`, `test_sensor_agrees`, `test_name_and_copyright_agree`, `test_version_is_semantic`, `test_default_address_agrees`. |
| PICO-NFR-005 | `test_no_mandatory_third_party_imports`; the port is reached through CORE-DD-SERIAL, whose pyserial import is deferred. |
| PICO-NFR-006 | `.github/workflows/style.yml` step "Run CStyleCheck (Pico thermometer)", `fail-on: info`, no baseline; `.cstylecheck-pico-aliases.txt`, `.cstylecheck-pico-exclusions.yml`. Local run with CStyleCheck v1.5.1: 18 files, 0 errors, 0 warnings, 0 info. |

## 14. RUN requirements to design, code and test

| Requirement | Architecture | Design unit | Source | Verifying test(s) |
|---|---|---|---|---|
| RUN-FR-001 | ARC-001 | RUN-DD-BENCH | `runner/bench.py` | `test_named_bench_file`, `test_simulate_overrides_the_configured_resource` |
| RUN-FR-002 | ARC-001 | RUN-DD-BENCH | `BenchConfig`, `load_bench` | `TestBenchConfig` (6), `TestInstrumentConfig` (7) |
| RUN-FR-003 | ARC-001 | RUN-DD-BENCH | driver registry | `TestDriverRegistry` (2), `test_unknown_driver_lists_the_registered_ones` |
| RUN-FR-004 | ARC-001 | RUN-DD-BENCH | `Bench.get`, `Bench.close` | `test_instruments_connect_on_first_use`, `test_the_same_instance_is_reused`, `test_close_releases_everything` |
| RUN-FR-005 | ARC-001 | RUN-DD-BENCH | `BenchConfig.simulated`, `Bench(simulate=)` | `test_simulated_factory`, `test_simulated_run_passes` |
| RUN-FR-006 | ARC-001 | RUN-DD-BENCH | `Bench.is_simulated` | `test_all_sim_resources_count_as_simulated`, `test_a_real_resource_is_not_simulated`, `test_a_mixed_bench_is_not_simulated`, `test_simulate_flag_forces_it` |
| RUN-FR-007 | RUN-ARC-001, AD-27 | RUN-DD-BENCH, CORE-DD-PATHS | `Bench._resolve_options`, `BenchConfig.directory`, `resolve_input_path`, `@input_paths` on `JLinkProbe.connect` and `NordicDongle.connect` | `TestBenchOptions` (4), `test_a_shipped_specification_runs_the_same_from_outside_the_checkout` (14), `TestResolveInputPath` (14), `TestEveryDriverDeclaresItsInputFiles` (28) |
| RUN-FR-008 | RUN-ARC-001, AD-28 | RUN-DD-SPEC, RUN-DD-BENCH, RUN-DD-REPORT | `_parse_instruments`, `TestSpec.instrument_events`; `InstrumentConfig.event`, `Bench.name_events`, `event_source_for`, `check_event_sources`; `BenchRunner.run`; the report's Instruments table | `SWE4-UT-EVENTNAMES` (21) |
| RUN-FR-010 | ARC-001 | RUN-DD-SPEC | `runner/spec.py` | `test_json_needs_no_third_party_package`, `test_yaml_when_available` |
| RUN-FR-011 | ARC-001 | RUN-DD-SPEC | `TestSpec.from_mapping` | `TestSpecParsing` (8) |
| RUN-FR-012 | ARC-001 | RUN-DD-SPEC | `TestCase.requirement` | `test_case_requirements_list_is_joined`, `test_requirement_roll_up` |
| RUN-FR-013 | ARC-001 | RUN-DD-RESOLVE | `runner/resolve.py` | `TestResolution` (9), `TestErrors` (4) |
| RUN-FR-014 | ARC-001 | RUN-DD-SPEC | validation in `from_mapping` | `test_malformed_specifications_are_reported` (7), `TestExpectationParsing` (6) |
| RUN-FR-015 | ARC-001 | RUN-DD-SPEC | `TestCase.skip` | `test_skip_is_carried`, `test_skipped_test_is_not_executed` |
| RUN-FR-016 | ARC-001 | RUN-DD-RESOLVE, RUN-DD-SPEC | `Reference`, `parse_references`, `resolve_references`, `Expectation.limit_against`; `BenchRunner.run_step` resolves arguments | `TestReferences` (9), `TestLimitsTakenFromAnEarlierStep` (6), `SWE4-UT-BRINGUP` (12) |
| RUN-FR-017 | RUN-ARC-001, AD-27 | RUN-DD-RUNNER, CORE-DD-PATHS | `BenchRunner.run_step` resolves declared arguments; `resolve_arguments`, `search_locations`, `@input_paths` on the S2-LP, dongle and probe methods | `TestStepArguments` (3), `test_a_shipped_specification_runs_the_same_from_outside_the_checkout` (14), `TestResolveInputPath` (14), `TestResolveArguments` (3), `TestDeclaration` (3) |
| RUN-FR-020 | ARC-001 | RUN-DD-LIMITS | `Limit` | `TestChecking.test_maximum/minimum/two_sided` |
| RUN-FR-021 | ARC-001 | RUN-DD-LIMITS | `Limit.window` | `test_absolute_tolerance`, `test_percentage_tolerance`, `test_exact_equality` |
| RUN-FR-022 | ARC-001 | RUN-DD-SPEC | `Expectation.scale` | `test_measured_value_is_scaled_for_the_limit` |
| RUN-FR-023 | ARC-001 | RUN-DD-LIMITS | `Limit.text`, `LimitOutcome.reason` | `TestRendering` (6), `test_out_of_limit_is_a_failure_not_an_error` |
| RUN-FR-024 | ARC-001 | RUN-DD-LIMITS | `TextLimit`, `Expectation._limit_for`, `_format_value` | `TestTextLimits` (8), `test_the_reported_version_is_recorded_as_text` |
| RUN-FR-025 | ARC-001 | RUN-DD-SPEC, RUN-DD-ENGINE | `spec.render`, `Expectation.format`, `BenchRunner._render_limit`, `MeasurementRecord.as_dict` | `TestHowAValueIsReported` (8), `test_the_identifier_is_reported_in_hex`, `test_the_number_is_still_in_the_record` |
| RUN-FR-030 | ARC-001 | RUN-DD-RUNNER, -RESULTS | `runner/runner.py`, `results.py` | `TestHappyPath` (7) |
| RUN-FR-031 | ARC-001 | RUN-DD-RUNNER | error vs failure classification | `TestFailureVersusError` (9) |
| RUN-FR-032 | ARC-001 | RUN-DD-RUNNER | setup abort, teardown `finally` | `test_setup_failure_aborts_the_suite`, `test_teardown_runs_even_after_a_failure` |
| RUN-FR-033 | ARC-001 | RUN-DD-RUNNER | `stop_on_error` | `test_a_failure_does_not_stop_later_tests`, `test_stop_on_error_abandons_the_rest` |
| RUN-FR-034 | ARC-001 | RUN-DD-RUNNER | `_resolve_action` | `test_private_methods_are_unreachable` |
| RUN-FR-035 | ARC-001 | RUN-DD-BENCH | `Bench.require` | `test_missing_instrument_is_reported_before_anything_runs`, `test_require_reports_everything_missing`, `test_the_simulated_bench_provides_every_shipped_specification` (14) |
| RUN-FR-036 | ARC-001 | RUN-DD-RUNNER | `_resolve_action` property branch | `TestPropertySteps` (6), notably `test_the_value_is_the_one_at_the_time_of_the_step` |
| RUN-FR-037 | ARC-001 | RUN-DD-BENCH, RUN-DD-RESULTS, RUN-DD-REPORT | `Bench.describe_instruments`, `RunRecord.instruments`, the report's Instruments table | `TestDescribingInstruments` (4), `TestInstrumentsInTheRecord` (2), `TestInstrumentsSection` (4) |
| RUN-FR-040 | ARC-001 | RUN-DD-RESULTS | `requirements_verified` | `test_requirement_roll_up`, `test_requirement_takes_the_worst_of_its_tests`, `test_requirements_table` |
| RUN-FR-041 | ARC-001 | RUN-DD-REPORT | `write_json` | `TestJson` (3) |
| RUN-FR-042 | ARC-001 | RUN-DD-REPORT | `format_markdown` | `TestMarkdown` (8) |
| RUN-FR-043 | ARC-001 | RUN-DD-REPORT | `write_junit` | `TestJunit` (6) |
| RUN-FR-054 | PICO-ARC-001 | PICO-DD-DRIVER, -CONST, -SIM, -CLI, -FLASH | `instruments/pico_sht30/{thermometer,constants,simulator,cli,flash}.py` |
| PICO-ARC-001 | PICO-DD-PROTOCOL, -VERSION, -BOARD, -HAL, -SHT30, -TEXT, -PARSER, -MAIN, -BUILD, -TEST | `firmware/pico_sht30/{include,src,test}/*`, `CMakeLists.txt`, `pico_sdk_import.cmake` |
| RUN-ARC-001 | RUN-DD-SPEC, RUN-DD-RUNCLI | `TestSpec.warning`, `_warnings_of`, `_announce_warnings` | `test_the_warning_is_printed_before_anything_runs` |
| VIEW-ARC-001 | VIEW-DD-STATE, -SERVER, -TRAFFIC, -RADIO, -GRAPHS, -TAGS, -STATUS, -KEPLER, -SENSOR, -TWF, -DIAG, -REPORT, -STGUI, -PAGE | `viewer/*.py`, `viewer/static/*` |
| RUN-FR-055 | RUN-ARC-001 | RUN-DD-RUNCLI | `_announce_warnings` (stderr) | `test_the_warning_is_printed_before_anything_runs` |
| RUN-FR-056 | RUN-ARC-001 | RUN-DD-RUNCLI | `_acknowledged`, `--acknowledge` | `test_hardware_without_a_terminal_refuses_to_start`, `test_a_terminal_is_asked_and_yes_proceeds`, `test_anything_but_yes_stops_the_run` (4) |
| RUN-FR-057 | RUN-ARC-001 | RUN-DD-RUNCLI | `_acknowledged`, `_EXIT_NOT_ACKNOWLEDGED` | `test_a_simulated_run_is_not_gated`, `test_a_specification_with_no_warning_is_never_gated` |
| RUN-FR-058 | RUN-ARC-001 | RUN-DD-SPEC, RUN-DD-RESULTS, RUN-DD-REPORT | `substitute_parameters`, `TestSpec.parameters`, `RunRecord.parameters` | `SWE4-UT-PARAMS` (7) |
| RUN-FR-059 | RUN-ARC-001 | RUN-DD-RUNNER, RUN-DD-RESULTS, RUN-DD-REPORT, RUN-DD-CLI | `BenchRunner.run(selection)`, `check_selection`, `NOT_SELECTED`, `RunRecord.selection`, `--test` | `SWE4-UT-SELECT` (14) |
| RUN-FR-060 | RUN-ARC-001 | RUN-DD-RUNNER | `BenchRunner.run`, `_plan`, `run_case`, `_log_case_end`, `run_step`, `_execute_step`, `PHASE_*` | `SWE4-UT-RUNEVENTS` (21) |
| RUN-FR-061 | RUN-ARC-001 | RUN-DD-CONTROL, RUN-DD-RUNNER, RUN-DD-CLI | `ControlServer`, `HOST`, `--control` | `SWE4-UT-CONTROL` (33) |
| RUN-FR-062 | RUN-ARC-001 | RUN-DD-CONTROL, RUN-DD-RUNNER, RUN-DD-CLI | `RunControl.checkpoint`, `request`, `status`; `run_steps` | `SWE4-UT-CONTROL` (33) |
| RUN-FR-063 | RUN-ARC-001 | RUN-DD-CONTROL, RUN-DD-RUNNER, RUN-DD-CLI | `ABORT`, `ABORTED`, `_run_tests`, `_Interrupted` | `SWE4-UT-CONTROL` (33) |
| RUN-FR-064 | RUN-ARC-001 | RUN-DD-CONTROL, RUN-DD-RUNNER, RUN-DD-CLI | `RESTART_FROM`, `_restart`, `_restart_refusal`, `_references_in`, `run_case(first, kept)`, `SKIPPED_BY_OPERATOR` | `SWE4-UT-CONTROL` (33) |
| RUN-FR-065 | RUN-ARC-001 | RUN-DD-CONTROL, RUN-DD-RUNNER, RUN-DD-CLI | `RunControl._refusal`, `control` and `control_applied` records | `SWE4-UT-CONTROL` (33) |
| RUN-FR-066 | RUN-ARC-001 | RUN-DD-CONTROL, RUN-DD-RUNNER | `READ_SETUP`, `_read_setups` | `TestRunner` (3) |
| VIEW-FR-001 | VIEW-ARC-001 | VIEW-DD-SERVER, VIEW-DD-PAGE | `ViewerServer`, `_Handler._static`, `static/*`, `benchtools view` | `TestPage` (4), `TestCommandLine` (2) |
| VIEW-FR-002 | VIEW-ARC-001 | VIEW-DD-SERVER | `_Handler._host_allowed`, `GUARD_HEADER` | `TestGuards` (4) |
| VIEW-FR-003 | VIEW-ARC-001 | VIEW-DD-STATE, VIEW-DD-SERVER | `RunState.apply`, `Hub.follow`, `Hub.poll` | `SWE4-UT-VIEWSTATE` (14), `test_attach_to_a_finished_log_shows_the_run` |
| VIEW-FR-004 | VIEW-ARC-001 | VIEW-DD-STATE, VIEW-DD-PAGE | `describe_step`, `RunState`, `renderRun` | `TestDescribeStep` (4), `TestRebuild` (6) |
| VIEW-FR-005 | VIEW-ARC-001 | VIEW-DD-SERVER, VIEW-DD-PAGE | `Hub.since`, `Hub.wait`, `_Handler._events`, `connect` | `test_the_event_stream_replays_the_log_then_the_state`, `test_records_arriving_later_are_not_lost` |
| VIEW-FR-006 | VIEW-ARC-001 | VIEW-DD-SERVER, VIEW-DD-PAGE | `_Handler._control`, `send_control`, `updateControls`, `control` | `TestControl` (4), `TestControlRecords` (4) |
| VIEW-FR-007 | VIEW-ARC-001 | VIEW-DD-SERVER | `Catalogue`, `Launcher.start` | `TestCatalogue` (2), `TestStart` (4) |
| VIEW-FR-008 | VIEW-ARC-001 | VIEW-DD-SERVER, VIEW-DD-PAGE | `Launcher.start` (warning), `showSpec` | `test_a_warning_must_be_acknowledged_on_hardware`, `test_specifications_with_their_test_cases_and_warnings` |
| VIEW-FR-009 | VIEW-ARC-001 | VIEW-DD-SERVER, VIEW-DD-STATE, VIEW-DD-PAGE | `/api/attach`, `Hub.control_port`, `_on_control_listening`, `renderEvents` | `test_attach_needs_a_log_and_a_numeric_port`, `test_the_control_port_is_taken_from_the_log` |
| VIEW-FR-010 | VIEW-ARC-001 | VIEW-DD-TRAFFIC, VIEW-DD-PAGE | `classify`, `Traffic`, `loadInstruments` | `TestClassify` (11), `TestPairing` (7), `test_every_supply_query_has_its_reply`, `test_no_dongle_reply_is_left_unasked` |
| VIEW-FR-011 | VIEW-ARC-001 | VIEW-DD-TRAFFIC, VIEW-DD-SERVER | `PsuPanel`, `JlinkPanel`, `panel_for`, `Hub._apply` | `TestPanels` (3), `test_the_panels_are_built` |
| VIEW-FR-012 | VIEW-ARC-001 | VIEW-DD-TRAFFIC, VIEW-DD-SERVER, VIEW-DD-PAGE | `Traffic.view(t0, t1)`, `Hub.instruments`, `/api/instruments`, `toggleTraffic` | `test_a_step_s_window_holds_only_its_own_traffic`, `TestInstruments` (4) |
| VIEW-FR-013 | VIEW-ARC-001 | VIEW-DD-RADIO, VIEW-DD-PAGE | `RfFrames`, `loadRadio` | `TestFrames` (6) |
| VIEW-FR-014 | VIEW-ARC-001 | VIEW-DD-RADIO, VIEW-DD-SERVER | `RfFrames.view(sensor)`, `/api/radio` | `test_each_sensor_s_latest_frame_of_each_type`, `test_one_sensor_only` |
| VIEW-FR-015 | VIEW-ARC-001 | VIEW-DD-RADIO, VIEW-DD-SERVER, VIEW-DD-PAGE | `BleAir`, `parse_fields`, `Hub.bluetooth`, `/api/ble`, `loadBle` | `TestBle` (6) |
| VIEW-FR-016 | VIEW-ARC-001 | VIEW-DD-GRAPHS | `Readings`, `lineChart` | `TestReadings` (5), `test_the_hub_serves_graphs` |
| VIEW-FR-017 | VIEW-ARC-001 | VIEW-DD-GRAPHS | `advertising`, `_intervals` | `TestAdvertising` (4) |
| VIEW-FR-018 | VIEW-ARC-001 | VIEW-DD-GRAPHS, VIEW-DD-SERVER | `step_markers`, `Hub.graphs`, `/api/graphs`, `lineChart` | `test_step_markers_in_time_order` |
| VIEW-FR-019 | VIEW-ARC-001 | VIEW-DD-PAGE | `heldBack`, `renderCount`, `events-pause` | Browser check (SWE4 report); `test_the_hub_tags_records_and_lists_the_tests` |
| VIEW-FR-020 | VIEW-ARC-001 | VIEW-DD-TAGS, VIEW-DD-PAGE | `Tagger._kinds`, `shown`, `KINDS` | `TestKinds` (9) |
| VIEW-FR-021 | VIEW-ARC-001 | VIEW-DD-TAGS, VIEW-DD-SERVER, VIEW-DD-PAGE | `sensor_of`, `Tagger.tag`, `Tagger.tests`, `shown` | `TestSensor` (6), `TestTest` (3), `test_the_hub_tags_records_and_lists_the_tests` |
| VIEW-FR-022 | VIEW-ARC-001 | VIEW-DD-STATUS | `InstrumentStatus`, `renderStatus` | `TestInstruments` (3), `test_the_hub_serves_status` |
| VIEW-FR-023 | VIEW-ARC-001 | VIEW-DD-STATUS | `progress`, `_steps_to_run` | `test_part_way_through`, `test_a_test_case_that_ended_early_leaves_the_total`, `test_test_cases_not_selected_are_not_counted`, `test_a_restart_counts_its_steps_again`, `test_setup_and_teardown_are_named` |
| VIEW-FR-024 | VIEW-ARC-001 | VIEW-DD-STATUS | `_expected`, `MIN_STEPS_FOR_ESTIMATE` | `test_the_estimate_uses_the_same_step_then_its_action_then_all` |
| VIEW-FR-025 | VIEW-ARC-001 | VIEW-DD-SERVER | `_authorised`, `_sign_in`, `is_loopback`, `new_token`, `--bind` | `TestToken` (8), `test_another_address_without_a_token_is_refused`, `test_reached_by_another_address_of_this_machine` |
| VIEW-FR-026 | VIEW-ARC-001 | VIEW-DD-SERVER | `_post_refusal`, `--read-only` | `TestReadOnly` (2) |
| VIEW-FR-027 | VIEW-ARC-001 | VIEW-DD-SERVER, RUN-DD-CONTROL | `ViewerServer(tls=)`, `--tls-cert`, `--tls-key`; `ControlServer` on `HOST` | `test_https_with_a_certificate`, `test_it_listens_on_127_0_0_1_only` |
| VIEW-FR-028 | VIEW-ARC-001 | VIEW-DD-KEPLER | `KeplerView.feed`, `byte_roles`, `header_rows`, `payload_rows`, `renderLatest` | `TestLatestData` (5) |
| VIEW-FR-029 | VIEW-ARC-001 | VIEW-DD-KEPLER | `KeplerView.view` (config, groups), `CONFIG_GROUPS`, `renderConfig` | `TestConfig` (4), `test_the_frames_list_names_config_parameters` |
| VIEW-FR-030 | VIEW-ARC-001 | VIEW-DD-KEPLER | `KeplerView` (identification), `renderIdentification` | `TestIdentification` (2) |
| VIEW-FR-031 | VIEW-ARC-001 | VIEW-DD-SENSOR | `SensorSeries.feed`, `_first_copy` | `TestEnvironment` (3) |
| VIEW-FR-032 | VIEW-ARC-001 | VIEW-DD-SENSOR | `SensorSeries._alive`, `_twf`, `to_mg`, `to_mm_s`, `lineChart` (raw) | `TestConversion` (2), `TestShortInterval` (7) |
| VIEW-FR-033 | VIEW-ARC-001 | VIEW-DD-SENSOR | `SensorSeries.view` (ticks, delta), `zoom` | `TestTicks` (2) |
| VIEW-FR-034 | VIEW-ARC-001 | VIEW-DD-TWF | `TwfAssembler.feed`, `_Capture.waveform` | `test_sample_for_sample_under_each_method` (4), `test_a_missing_packet_is_a_gap`, `test_distance_spreads_a_lost_packet_across_the_waveform`, `test_the_twf_scale_sets_mg_and_the_odr_code_the_time`, `test_packet_zero_after_a_complete_capture_starts_the_next` |
| VIEW-FR-035 | VIEW-ARC-001 | VIEW-DD-TWF | `spectrum`, `fill_gaps`, `_fft`, `TwfAssembler.view`, `loadTwf` | `TestSpectrum` (5) |
| VIEW-FR-036 | VIEW-ARC-001 | VIEW-DD-TWF | `TwfAssembler.view` (fallback), `zoomTwf` | `test_buffer_and_axis_from_the_frame` |
| VIEW-FR-037 | VIEW-ARC-001 | VIEW-DD-DIAG | `Diagnostics`, `_TypeStats`, `loadDiagnostics` | `test_frames_packets_and_drops`, `test_periods_mean_deviation_and_extremes_with_their_frames`, `test_a_lost_first_copy_still_counts_the_frame`, `test_a_burst_closes_after_a_gap_without_a_first_copy`, `test_a_burst_still_arriving_is_not_yet_counted`, `test_types_without_a_counter_count_no_drops`, `test_one_sensor_at_a_time_and_reset` |
| VIEW-FR-038 | VIEW-ARC-001 | VIEW-DD-DIAG | `_TypeStats.recent`, Auto/Hold | `test_the_last_ten_frames_newest_first_with_their_deltas`, `test_an_unknown_type_is_counted_not_an_error` |
| VIEW-FR-039 | VIEW-ARC-001 | VIEW-DD-DIAG | `SyncTracker` | `TestSync` (5) |
| VIEW-FR-040 | VIEW-ARC-001 | VIEW-DD-REPORT | `NotesStore`, `/api/notes`, `notes.js` | `TestNotes` (4), `test_the_api_saves_notes_and_serves_the_report` |
| VIEW-FR-041 | VIEW-ARC-001 | VIEW-DD-REPORT | `build_report`, `svg_chart`, `/api/report` | `TestSvgChart` (2), `TestReport` (3) |
| VIEW-FR-042 | VIEW-ARC-001 | VIEW-DD-REPORT | `_CSS` (print), `report-print` | `test_it_is_self_contained_and_escaped` |
| VIEW-FR-043 | VIEW-ARC-001 | VIEW-DD-STGUI | `StGui`, `rf_setup_rows` | `test_rf_setup_rows`, `test_the_hub_serves_the_page_and_the_file` |
| VIEW-FR-044 | VIEW-ARC-001 | VIEW-DD-STGUI | `register_rows`, `regs_text`, `/api/stgui/regs` | `test_register_rows_mark_a_changed_register`, `test_the_register_file_round_trips` |
| VIEW-FR-045 | VIEW-ARC-001 | VIEW-DD-STGUI | `st_row`, `/api/stgui/refresh`, `stgui.js` | `test_frames_as_st_s_gui_lists_them`, `test_nothing_read_yet` |
| RUN-FR-050 | ARC-001 | RUN-DD-CLI | `runner/cli.py` | `TestRunCommand` (8) |
| RUN-FR-051 | ARC-001 | RUN-DD-CLI | exit statuses | `test_simulated_run_passes`, `test_failure_exits_nonzero`, `test_no_bench_and_no_simulate_is_a_usage_error` |
| RUN-FR-052 | ARC-001 | RUN-DD-CLI | report path suffixing | `test_several_specs_get_suffixed_reports` |
| RUN-FR-053 | ARC-001 | RUN-DD-CLI | `benchtools/cli.py` | `TestTopLevelDispatch` (7) |

## 15. Architecture to design to source

| Architectural element | Design unit | Source |
|---|---|---|
| CORE-ARC-006 | CORE-DD-INSTRUMENT | `core/instrument.py` |
| CORE-ARC-001 | CORE-DD-SCPI | `core/scpi.py` |
| CORE-ARC-002 | CORE-DD-TRANSPORT | `core/transport/base.py` |
| CORE-ARC-003 | CORE-DD-VXI11, -SOCKET, -VISA, -PROCESS, -SERIAL, -FACTORY | `core/transport/{vxi11,socket_raw,visa_backend,process,serial_port,factory,constants}.py` |
| CORE-ARC-004 | CORE-DD-SIM, CORE-DD-MOCK | `core/simulator.py`, `core/transport/mock.py` |
| CORE-ARC-005 | CORE-DD-ENUMS, -VALIDATE, -ERR | `core/{enums,validation,errors}.py` |
| CORE-ARC-007 | CORE-DD-FIRMWARE | `core/firmware.py` |
| ANA-ARC-001 | ANA-DD-WAVEFORM | `analysis/waveform.py` |
| ANA-ARC-002 | ANA-DD-MEASURE, ANA-DD-PLOT | `analysis/{measure,plotting}.py` |
| INST-ARC-001 | INST-DD-GENERIC | `instruments/generic.py` |
| SCOPE-ARC-001 | SCOPE-DD-SCOPE, -CONST, -SIM, -CLI | `instruments/tek3014b/*.py` |
| JLINK-ARC-001 | JLINK-DD-GDBMI, -SESSION, -SERVER, -RTT, -SWO, -TIMING, -CONST, -SIM, -PROBE, -CLI | `instruments/jlink/*.py` |
| BLE-ARC-001 | BLE-DD-PROTOCOL, -SESSION, -PROFILE, -LATENCY, -CONST, -DONGLE, -SIM, -CLI | `instruments/nordic_dongle/*.py` |
| BLE-ARC-001 | BLE-DD-CDC, -TIMESTAMP, -SCANNER, -NUS, -CMD, -MAIN, -BUILD, -TEST | `firmware/nordic_dongle/{src,include,config,ses,gcc,scripts,test}/*` |
| S2LP-ARC-001 | S2LP-DD-S2LP, -REGS, -CONFIG, -PROTOCOL, -SESSION, -PACKETS, -SIM, -CLI, -CONST | `instruments/s2lp/{s2lp,registers,configuration,protocol,session,packets,simulator,cli,constants}.py` |
| PSU-ARC-001 | PSU-DD-PSU, -CONST, -SIM, -CLI | `instruments/gpd3303d/{psu,constants,simulator,cli}.py` |
| RUN-ARC-001 | RUN-DD-SPEC, -LIMITS, -RESOLVE, -BENCH, -RESULTS, -RUNNER, -CONTROL, -REPORT, -CLI | `runner/*.py`, `cli.py` |

## 16. Coverage analysis

| Question | Answer |
|---|---|
| Requirements with no verifying test | **None.** All 435 functional requirements in force (436 declared; PICO-FR-044 is withdrawn) and 36 non-functional requirements trace to at least one test, or to a recorded inspection where a test is not the appropriate method (CORE-NFR-002, BLE-FR-090, BLE-NFR-002, and part of CORE-NFR-001). The firmware requirements are verified against the artefact the firmware is built from, not against a running dongle: see CON-07. |
| Tests not tracing to a requirement | **None.** Every test file names its requirements in its module docstring. |
| Source modules with no design unit | **None.** Every module names its design unit in its docstring - firmware sources included, checked by `test_every_source_declares_its_trace` in `SWE4-UT-BLEFW`; `__main__.py` is covered by RUN-DD-CLI. |
| Design units with no source | **None.** |
| Stakeholder requirements not decomposed | **None of those in scope.** STK-01 to STK-11 and STK-14 to STK-17 trace downward; STK-06 additionally produces BENCHTOOLS-VISA-001 as its work product. STK-12 is partly addressed (AD-15 constrains the driver boundary for it, and AD-23 reads a markdown command document as a test) and Robot Framework itself is deferred: CON-06, OPEN-04. STK-13 is decomposed into `PSU-` and verified; STK-19 and STK-20 into `S2LP-` and AD-20. STK-18 is decomposed into `DMM-` and verified against a simulator; no behaviour is confirmed on a physical meter (DMM-OPEN-01…05). |
| Architectural decisions without a verifying test | **None.** AD-01 → `test_full_driver_over_the_socket`; AD-02 → `test_layering.py`; AD-03 → `TestDriverRegistry`; AD-04 → `TestFraming`; AD-05 → `test_payload_containing_a_hash_byte_is_not_re_parsed`; AD-06 → `TestChannelSpread`; AD-07 → `test_busy_is_polled_until_clear`; AD-08 → `TestSpecParsing`; AD-09 → `TestFailureVersusError`; AD-10 → `test_all_sim_resources_count_as_simulated`; AD-11 → `test_the_probe_is_an_instrument_but_not_scpi`, `test_scpi_instrument_is_an_instrument`; AD-12 → `SWE4-UT-GDBMI`, `SWE4-UT-GDBSESSION`, `test_connect_to_the_simulator`; AD-13 → `test_resource_parsing`, `test_a_remote_server_is_never_spawned`; AD-14 → `SWE4-UT-TIMING`, `test_a_short_interval_is_flagged_untrustworthy`; AD-15 → `test_serialises_for_a_report`, `test_shipped_specifications_are_valid`; AD-16 → `SWE4-UT-BLEFW`; AD-17 → `test_both_clocks_are_recorded`, `test_the_host_clock_resolves_a_millisecond`; AD-18 → `test_a_lossy_link_is_declared_rather_than_averaged`, `test_a_dropping_dongle_says_so`; AD-19 → `TestOutputSwitching` (11), notably `test_the_last_channel_off_opens_the_real_switch` and `test_setting_a_voltage_on_a_parked_channel_does_not_energise_it`; AD-20 → `SWE4-UT-S2LPPROTO` and `SWE4-UT-S2LPSESSION` verify the driver against ST's declared command set, and `test_a_polled_capture_reports_its_gaps` verifies the honesty the decision requires; AD-21 → `TestTracking` in `test_psu.py` (14), with `TestTracking` in `test_simulator.py` (10) establishing that the supply really does discard what the driver refuses to send; AD-22 → `TestReferences` (9) and `TestLimitsTakenFromAnEarlierStep` (6) for the mechanism, and `SWE4-UT-BRINGUP` (12) for what it is for - the shipped chained specification, with each fact it establishes broken in turn to confirm it would fail; AD-23 → `SWE4-UT-BLESCRIPT` (58), including `TestTheShippedDocument`, which runs `specs/sensor_commands.md` against the simulated sensor so the worked example cannot rot.; AD-24 → the shared conversion vectors in `test_sht30.c` and `test_matches_the_firmware_vectors`, and the shared two-place vectors in `test_text.c` and `test_two_places_half_away_from_zero`. Since #131 the raw word no longer travels with the reading, so the host-side cross-check AD-24 called for is gone (PICO-FR-044 withdrawn); AD-24 is marked superseded by #131 in ETB-SWE2-001 0.8, and what replaces it - the two-place format check and `Error`/`NAK` - is verified under PICO-FR-027 and -047; AD-25 → `TestConfirmation` (3), `test_an_echo_is_not_found_inside_a_frame`, `TestRanges` (6) in `test_dmm.py`; AD-26 → `TestTheSerialLink` (2), `TestStreamReading` (7), `test_a_measurement_is_taken_after_the_call`, `test_the_ten_second_gate_is_waited_for`; AD-27 → `SWE4-UT-PATHS` (70), notably `test_a_shipped_specification_runs_the_same_from_outside_the_checkout`; AD-28 → `SWE4-UT-EVENTNAMES` (21), notably `test_records_carry_the_specification_s_names`, and `test_two_instruments_of_one_driver_are_told_apart` |

## 17. Open items

| ID | Item | Owner action |
|---|---|---|
| OPEN-01 | Bench confirmation items in BENCHTOOLS-VISA-001 §5.1 (device name, portmapper transport, hardcopy format, measurement settling, record lengths) | Discharge on first use with physical hardware. |
| OPEN-02 | TDS3000 SCPI command spellings not transcribed from the programmer manual (CON-02) | Spot-check against Tektronix 071-0381-03 on first bench use. |
| OPEN-03 | No requirements yet for the instrument families still named for future work (CON-03): loads, signal sources, logic and protocol analysers. STK-13, STK-18 and STK-19/STK-20 are **closed**: the GPD-3303D supply (PSU-FR-001 … -060), the TTi 1604 multimeter (DMM-FR-001 … -081) and the S2-LP kit (S2LP-FR-001 … -060) are each specified, designed, implemented and tested | Add a prefixed requirements section, design unit, test group and matrix rows per instrument as each driver is written, as was done for `PSU-` and `DMM-`. |
| OPEN-06 | The dongle firmware builds, links, fits and packages against nRF5 SDK 17.1.0 in CI, but has not been flashed or run (CON-07) | **Narrowed**: BLE-OPEN-01 is discharged — `.github/workflows/firmware.yml` run 12 on `f66a248`, 51 652 bytes of flash and 12 636 of static RAM (BENCHTOOLS-SWE4-002 §4.6). What remains is to flash the DFU package and work through `docs/ble/BLE_Dongle_Notes.md` §5.3 (BLE-OPEN-02 to BLE-OPEN-04). |
| OPEN-04 | **Narrowed.** Tests written as a markdown document are implemented for the BLE command set: `BLE-FR-100 … -116`, AD-23, `specs/sensor_commands.md`, and the template `specs/templates/ble_sensor_test.md`, whose rows each map to one Robot Framework keyword and whose `${NAME}` variables are Robot's own syntax. What remains undecided is Robot Framework itself (STK-12, CON-06) - a general keyword layer over every instrument, rather than one document format for one element | Decide whether to adopt Robot Framework. If adopted, add a `ROBOT-` element in front of the existing runner; AD-15 has kept the driver boundary suitable for it, and AD-23 is evidence that a document-driven test needs no framework to be useful. |
| OPEN-07 | S2-LP kit bench confirmation items — `docs/s2lp/S2LP_Devkit_Notes.md` §7: the firmware's exact reply text and error codes, the board name it reports, the meaning of `S2LPGetNBytesBatch`'s reference-timer argument, and the link budget in practice | Discharge on first use with a kit. Tracked there as S2LP-OPEN-01 to S2LP-OPEN-05. Nothing in them blocks use of the driver: the parser reads tags by name and keeps every line, so an unexpected reply is visible rather than fatal. |
| OPEN-08 | PSU bench confirmation items — ETB-IF-001 §12: the command interval a real supply needs, settling time, the slaved-channel behaviour, series and parallel tracking bits, current programming resolution, and `VOUT` read-back | PSU-OPEN-01 and -02 closed 2026-09-26; PSU-OPEN-06 partly. The rest open, tracked in ETB-IF-001 §12. |
| OPEN-05 | J-Link bench confirmation items (CON-04, CON-05) — `docs/jlink/JLink_Integration_Notes.md` §4: Windows execution, real MI version behaviour, SWO timestamp scaling, RTT control-block discovery, flash timing | Discharge on first use with a probe and a target. Tracked there as JLINK-OPEN-01 to JLINK-OPEN-04. |
| OPEN-10 | TTi 1604 bench confirmation items (CON-10) — `docs/dmm/TTi1604_Notes.md` §5: DMM-OPEN-01 … -08 | Run `tests/bench/tti1604` (SWE4-UT-DMMBENCH) and the panel test with the meter attached, and keep the findings record. A meter is connected to the owner's bench PC. |
| OPEN-09 | Pico 2 thermometer bench confirmation items (CON-09) — `docs/pico_sht30/Pico_SHT30_Notes.md` §7. **Done 2026-10-03** on a real Pico 2 on Windows: reflashing with `benchtools thermo flash` by all three routes into the bootloader (PICO-OPEN-05, closed); with no module connected, the #131 target build, USB enumeration, `rd name`, `rd copyright`, `rd version` and `rd sha`, `NAK`, the `err` replies, `Error` without the module, and `ecureset` (PICO-OPEN-01 closed, PICO-OPEN-06 confirmed in part); and `flash` installing the #131 firmware and confirming its name, version and commit SHA by `rd`. **Still open:** `rd temperature` with a real value to two places and the module's pull-ups, accuracy against a reference thermometer, the reference PDFs that could not be fetched in the build environment, and drive discovery on Linux and macOS | Discharge when an SHT30-D module is connected. Tracked there as PICO-OPEN-02 (confirmed in part: `Error` and `err 4` with no module), PICO-OPEN-03, PICO-OPEN-04 and PICO-OPEN-06. |

---

## 18. Review & Approval

| Role | Name | Signature / Electronic Approval | Date |
|---|---|---|---|
| Author | Claude | Approved | 2026-09-19 |
| Technical Reviewer | Dermot Murphy | — | *pending* |
| Quality Assurance | Dermot Murphy | — | *pending* |
| Approver | Dermot Murphy | — | *pending* |

> **Note:** This document is under configuration management (SUP.8). Post-approval changes require a change request (SUP.10) and a new document version.
