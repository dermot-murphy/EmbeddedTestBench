<img src="../../assets/brand/svg/logos/embeddedtestbench-logo-compact.svg" alt="Embedded Test Bench" width="240">

# Software Integration & Integration Test

*Automotive SPICE® PAM v4.0 | SWE.5 — Software Integration and Integration Test*

---

## 1. Document Identification & Control

| Field | Value | Field | Value |
|---|---|---|---|
| **Document ID** | ETB-SWE5-001 | **Version** | [latest, §2](#2-revision-history) |
| **Project** | Embedded Test Bench | **Date** | [latest, §2](#2-revision-history) |
| **Status** | [by location, ETB-SUP1-001 §6.3](EmbeddedTestBench_SUP1_Quality_Assurance_Plan.md#63-document-status) | **Classification** | Internal |
| **Author** | Claude | **Reviewer** | Dermot Murphy |
| **Approver** | Dermot Murphy | **Related Process** | SWE.5 |

> Reviewer and Approver are the same person; see ETB-DEV-002.

---

## 2. Revision History

| Version | Date | Author | Description of Change |
|---|---|---|---|
| 0.1 | 2026-09-19 | Claude | Initial |
| 0.2 | 2026-10-04 | Claude | #183: product renamed to Embedded Test Bench - document file name prefix `EmbeddedTestBench_`, identifier prefix `ETB-` (was `TB-`), product name in prose. Earlier revision rows keep the names in use when they were written. |
| 0.3 | 2026-10-05 | Claude | #204: Review & Approval table points to the merge of the pull request that last changed the document, which is the review and approval (ETB-SUP8-001 §5.7); no per-change signatures or dates. |
| 0.4 | 2026-10-05 | Claude | #194: the compact brand logo added above the title, the same line in every controlled document (ETB-SUP8-001 §6.3). |
| 0.5 | 2026-10-25 | Claude | #210: Version and Date in the identification table are links to the last revision history row, which holds them (ETB-SUP8-001 §6.2). |
| next | 2026-11-17 | Claude | #371: the Status cell links to the status rule, ETB-SUP1-001 §6.3. A document's status follows from where it is in the repository (Released, Agreed, In review, In work) and is not written in by hand. |
| next | 2026-11-17 | Claude | #377: Referenced Documents cite each controlled document at the version of its last numbered revision row, kept by `scripts/doc_versions.py` (ETB-SUP8-001 §6.2). |
| next | 2026-11-17 | Claude | #370: §4 adds stages I9 to I13 (viewer, plugins, the two firmware protocols, serial capture). §5 adds the matching groups. §6 - each case names its tests and its `v0.03.0000` result, and partial cases state their gap. ETB-IT-04's property is restated; ETB-IT-11 to -15 are added; the selection rule is stated. §9 gives the release's results, and points to ETB-SWE4-002 §15 for defects, not §17. |

---

## 3. Purpose & Scope

### 3.1 Purpose

This document says how the software units of Embedded Test Bench are integrated into the
architecture of ETB-SWE2-001, and how the integrated result is tested — that is,
how the **interfaces between units** are shown to work, as distinct from the
units themselves (ETB-SWE4-001) and from the software as a whole against its
requirements (ETB-SWE6-001).

### 3.2 Referenced Documents

| Document ID | Title | Version |
|---|---|---|
| ETB-SWE2-001 | Embedded Test Bench Software Architecture | 0.33 |
| ETB-SWE3-001 | Embedded Test Bench Software Detailed Design | 1.90 |
| ETB-SWE4-001 | Embedded Test Bench Unit Verification Specification | 1.92 |
| ETB-SWE4-002 | Embedded Test Bench Unit Verification Report | 1.87 |
| ETB-SWE6-001 | Embedded Test Bench Software Qualification Test | 0.7 |
| ETB-SYS4-001 | Embedded Test Bench System Integration & Integration Test | 0.6 |
| ETB-SUP9-001 | Embedded Test Bench Problem Resolution Management Plan | 0.5 |

### 3.3 Scope

The Python package `benchtools` and the dongle firmware's host-facing protocol.
Integration of software with physical instruments is system integration and
belongs to ETB-SYS4-001.

---

## 4. Integration Strategy

Integration is **continuous and bottom-up**. There is no separate integration
phase, because there is no period during which the parts exist separately: a
unit is merged only when the suite — which includes every integration test
below — passes with it in place.

| Stage | What is joined | What the joining must show |
|---|---|---|
| I1 | Transports + SCPI plumbing (`core`) | A framed exchange survives the transport's chunking; errors propagate as errors |
| I2 | `core` + one driver | The driver reaches the instrument only through the core's link abstraction |
| I3 | Driver + its simulator | Driver and simulator satisfy the same interface; the driver cannot tell which it has |
| I4 | Drivers + bench model (`core.bench`) | A bench description names instruments and yields opened, identified drivers |
| I5 | Bench + runner | The runner drives real driver objects, resolves saved values between steps, and evaluates expectations against what the drivers returned |
| I6 | Runner + reporting | A run produces markdown and machine-readable output containing every step and every identity |
| I7 | Runner + markdown command scripts | A document in `specs/` is parsed into steps and executed against the dongle driver |
| I8 | Host driver + dongle firmware protocol | Commands framed by the host are accepted by the firmware's parser and answered with dongle-side timestamps |
| I9 | Runner + event log + viewer | The viewer rebuilds a run from the event log alone, and it matches the runner's record |
| I10 | Core plugin registry + device plugins | A plugin loaded from its folder supplies its decoder, panel and record entries, and no core module imports it |
| I11 | S2-LP driver + ETB kit firmware protocol | Host and firmware agree on the protocol: version, limits, record kinds |
| I12 | PICO2 Test Board driver + its firmware protocol | Host, simulator and firmware agree on commands, errors and reply text |
| I13 | Runner + serial capture instrument | A specification drives a capture and checks what it captured |

### 4.1 The Layering Test Is an Integration Test

`tests/test_layering.py` asserts the dependency rules of ETB-SWE2-001 §5:
`core` imports no instrument, instruments import no other instrument, the runner
imports drivers only through the registry. It is an integration test in the
strict sense — it tests a property of the assembled whole that no unit test
could see — and it fails the build when the architecture is violated rather than
waiting for a review to notice.

### 4.2 Integration Against Simulators

Integration tests run against the simulated instruments, deliberately. That is
what makes them run on every change with no bench attached. The honest
consequence is stated rather than hidden: an integration test passing against a
simulator shows that the **software** fits together, not that the software fits
the **instrument**. The latter is ETB-SYS4-001's job, and the items it has not
yet discharged are listed there.

---

## 5. Integration Test Groups

| Group | Location | Interfaces exercised |
|---|---|---|
| Layering | `tests/test_layering.py` | Every module boundary in ETB-SWE2-001 §5 |
| Traceability | `tests/test_traceability.py` | Documents ↔ code ↔ matrix |
| Bench loading | `tests/core/` | Bench description → registry → opened drivers → identity records |
| Transport ↔ protocol | `tests/core/` | Framing, chunking, timeouts, error propagation |
| Driver ↔ simulator | `tests/instruments/*/` | Each driver against its simulator through the shared interface |
| Runner ↔ drivers | `tests/runner/` | Step dispatch, argument resolution, saved-value references, limit evaluation |
| Runner ↔ reporting | `tests/runner/` | Report contents: identities, simulation disclosure, per-step records |
| Command scripts | `tests/instruments/nordic_dongle/test_script.py` | Markdown parsing → step execution → result classification |
| End-to-end specifications | `tests/runner/`, `specs/` | A whole specification against the simulated bench |
| Viewer | `tests/viewer/` | Event log → rebuilt run → per-step views |
| Plugins | `tests/core/test_plugins.py` | Plugin folder → registry → driver actions, viewer panels, run record |
| Firmware protocols | `tests/instruments/pico2_test_board/test_firmware_protocol.py`, `tests/runner/test_integration_cases.py` | Host constants against the firmware's headers |

---

## 6. Interface Test Cases

The interface properties that integration must establish. Each case names the
tests that realise it, and its result in the release run of `v0.03.0000` (CI
run 44057132180; the JUnit is in `docs/aspice/unit_results/v0.03.0000/`).
Tests added by #370 have no release result yet; their first is the next
release's. A case marked **Partial** is realised in part, and its gap is stated.
`tests/test_traceability.py` fails if a test named here does not exist (#370).

**Selection (SWE.5.BP2).** Every case is selected on every change. Its tests are
part of the `pytest` suite, which runs whole on every push and pull request
(§8, ETB-SWE4-001 §4.8). No case is selected or deselected per release.

| ID | Property | Why a unit test cannot show it | Tests | Result |
|---|---|---|---|---|
| ETB-IT-01 | A reply split across transport reads is reassembled into one message | Requires the real framing code above the real chunking | `core/transport/test_base.py::TestFraming::test_read_message_reassembles_chunks`<br>`core/transport/test_vxi11.py::TestVxi11OverASocket::test_large_transfer_is_reassembled`<br>`core/transport/test_socket.py::TestSocketTransport::test_binary_block_is_read_by_length` | Pass: 3 of 3 in the `v0.03.0000` release run |
| ETB-IT-02 | A transport error surfaces as an error, never as an empty or default value | The substitution would happen at the boundary between two units | `core/transport/test_base.py::TestLifecycle::test_starved_link_times_out`<br>`core/transport/test_socket.py::TestSocketTransport::test_silent_instrument_times_out`<br>`core/transport/test_process.py::TestFailures::test_writing_to_a_dead_process_is_reported`<br>`instruments/nordic_dongle/test_script.py::TestASensorThatDoesNotAnswer::test_a_step_that_expected_a_reply_is_an_error` | Partial. Pass: 4 of 4 in the `v0.03.0000` release run. Gap: No test injects a transport fault into a YAML step run by the runner; the dongle script path is shown |
| ETB-IT-03 | A driver behaves identically against instrument and simulator | The property is about two implementations of one interface | `core/transport/test_socket.py::TestSocketTransport::test_full_driver_over_a_socket`<br>`core/transport/test_vxi11.py::TestVxi11OverASocket::test_full_driver_over_the_socket`<br>`instruments/tti1604/test_dmm.py::TestTheSerialLink::test_a_frame_on_a_serial_port_is_decoded`<br>`instruments/s2lp/test_session.py::TestWhatAKitActuallySends::test_an_echo_that_ran_into_the_reply_is_split_off` | Partial. Pass: 4 of 4 in the `v0.03.0000` release run. Gap: Against simulators and real transports only; equivalence with the instrument itself is ETB-SYS4-001 |
| ETB-IT-04 | Running a specification records the identity of every instrument the run used | Spans bench model, registry, drivers and the report | `runner/test_bench.py::TestDescribingInstruments::test_what_is_recorded`<br>`runner/test_runner.py::TestInstrumentsInTheRecord::test_the_run_records_what_it_used`<br>`runner/test_report.py::TestInstrumentsSection::test_the_table_names_the_instrument_and_its_build`<br>`runner/test_bench_self_check.py::TestTheCheckPasses::test_every_instrument_identity_is_recorded` | Pass: 4 of 4 in the `v0.03.0000` release run |
| ETB-IT-05 | A value saved in one step is resolved correctly as an argument in a later step | Spans the resolver, the runner's state and the driver's signature | `runner/test_sensor_bringup.py::TestItPasses::test_the_device_was_chosen_by_that_identifier`<br>`runner/test_run_events.py::TestRebuildingTheRun::test_step_end_carries_resolved_arguments_result_and_measurements`<br>`runner/test_compare_steps.py::test_a_loaded_battery_no_higher_than_unloaded_in_a_run` | Pass: 3 of 3 in the `v0.03.0000` release run |
| ETB-IT-06 | An expectation is evaluated against what the driver actually returned, with its units | Spans driver return types and the limit types | `runner/test_runner.py::TestHappyPath::test_measured_value_is_scaled_for_the_limit`<br>`runner/test_runner.py::TestFailureVersusError::test_out_of_limit_is_a_failure_not_an_error`<br>`runner/test_runner.py::TestFailureVersusError::test_non_numeric_measurement_is_an_error`<br>`runner/test_sensor_power_signal_and_link.py::TestItPasses::test_the_current_is_measured_through_the_meter` | Pass: 4 of 4 in the `v0.03.0000` release run |
| ETB-IT-07 | A simulated run is labelled simulated in **every** output format | Spans bench model and each report writer | `runner/test_report.py::TestMarkdown::test_simulation_is_disclosed`<br>`runner/test_report.py::TestJunit::test_properties_record_the_bench`<br>`runner/test_run_events.py::TestRebuildingTheRun::test_run_start_carries_the_whole_plan`<br>`runner/test_runner.py::TestStatusAggregation::test_simulated_flag_is_recorded`<br>`runner/test_integration_cases.py::test_the_json_report_says_the_run_was_simulated` | Partial. Pass: 4 of 4 in the `v0.03.0000` release run; 1 added in #370, passing on its branch. Gap: The console summary line is not asserted |
| ETB-IT-08 | A markdown table becomes an ordered sequence of executed steps, including delays and unasserted commands | Spans parser, runner and result classification | `instruments/nordic_dongle/test_script.py::TestRunningIt::test_the_steps_are_reported_in_document_order`<br>`instruments/nordic_dongle/test_script.py::TestRunningIt::test_a_delay_waits_and_is_skipped`<br>`instruments/nordic_dongle/test_script.py::TestRunningIt::test_a_command_with_nothing_promised_is_skipped_but_recorded`<br>`instruments/nordic_dongle/test_script.py::TestTheShippedDocument::test_it_passes_against_the_simulated_sensor` | Partial. Pass: 4 of 4 in the `v0.03.0000` release run. Gap: Shown through the script runner, not through `specs/sensor_commands.yaml` and the runner |
| ETB-IT-09 | A step that fails does not stop the following steps from being recorded | A property of the run loop, not of any step | `runner/test_runner.py::TestSetupAndSkips::test_a_failure_does_not_stop_later_tests`<br>`runner/test_runner.py::TestHappyPath::test_teardown_runs_even_after_a_failure`<br>`instruments/nordic_dongle/test_script.py::TestRunningIt::test_one_failure_fails_the_run`<br>`runner/test_bench_self_check.py::TestTheCheckWouldFail::test_the_other_instruments_still_pass_when_the_supply_fails` | Partial. Pass: 4 of 4 in the `v0.03.0000` release run. Gap: No YAML test asserts a later step in the same case after a FAIL step; by design an ERROR step ends its case |
| ETB-IT-10 | The runner reaches a driver only through the registry | Only visible across the assembled package | `runner/test_bench.py::TestDriverRegistry::test_a_new_driver_can_be_registered`<br>`test_layering.py::test_layer_dependencies_point_one_way[runner/runner.py]`<br>`runner/test_bench.py::TestInstrumentConfig::test_unknown_driver_lists_the_registered_ones`<br>`runner/test_integration_cases.py::test_no_runner_module_imports_an_instrument` | Pass: 3 of 3 in the `v0.03.0000` release run; 1 added in #370, passing on its branch |
| ETB-IT-11 | The viewer rebuilds a run (test tree, step verdicts, saved values, and the instrument traffic inside each step) from the runner's event log alone, and the rebuilt run matches the runner's own record | The records are written by the runner and the drivers through the core event log, and read back by the viewer's state and hub. A unit test on either side uses hand-written records, so it cannot show that the two sides agree on one log. | `viewer/test_state.py::TestRebuild::test_the_whole_tree_matches_the_run`<br>`viewer/test_state.py::TestRebuild::test_steps_are_described_and_saved_values_kept`<br>`viewer/test_step_events.py::TestRecordedRun::test_every_step_lists_exactly_its_own_records`<br>`viewer/test_step_events.py::TestRecordedRun::test_a_supply_step_shows_its_commands_and_replies` | Pass: 4 of 4 in the `v0.03.0000` release run |
| ETB-IT-12 | A device plugin loaded from its folder supplies its decoder to the S2-LP driver's actions, its panel to the viewer, and its name and commit to the run record, and no benchtools module imports a plugin | The interface lies between the core plugin registry, a folder outside the package (plugins/kepler or the synthetic test plugin), the driver, the runner and the viewer. Each unit alone sees only its own side of the lookup. | `core/test_plugins.py::TestActions::test_the_kepler_names_are_the_dut_actions_with_the_kepler_decoder`<br>`core/test_plugins.py::TestRunRecords::test_the_record_and_run_start_name_each_plugin_and_its_ref`<br>`core/test_plugins.py::TestViewer::test_a_panel_is_fed_each_frame_and_viewed_by_name`<br>`core/test_plugins.py::test_no_benchtools_module_imports_a_plugin_or_a_kepler_module` | Pass: 4 of 4 in the `v0.03.0000` release run |
| ETB-IT-13 | Commands that the S2-LP driver frames for the ETB kit firmware are accepted by the firmware's parser, the firmware's frame and rejection records are decoded by the driver, and both sides agree on the protocol version | The property is about two implementations of one line protocol, in two languages (benchtools/instruments/s2lp/kit_driver.py and kit_firmware.py, and firmware/s2lp_kit). Neither side's unit tests can show that they agree. | `instruments/s2lp/test_kit_firmware.py::TestChoosingTheFirmware::test_the_kit_firmware_is_found_by_asking`<br>`instruments/s2lp/test_kit_firmware.py::TestChoosingTheFirmware::test_another_protocol_version_is_refused`<br>`instruments/s2lp/test_kit_firmware.py::TestStream::test_frames_with_their_registers_and_decode`<br>`instruments/s2lp/test_kit_firmware.py::TestStream::test_a_lost_record_is_counted_on_the_next`<br>`runner/test_integration_cases.py::TestTheKitFirmwareProtocolAgrees::test_the_protocol_version`<br>`runner/test_integration_cases.py::TestTheKitFirmwareProtocolAgrees::test_the_limits` | Pass: 4 of 4 in the `v0.03.0000` release run; 2 added in #370, passing on its branch |
| ETB-IT-14 | The PICO2 Test Board host driver, its simulator and its firmware agree on the command table, error codes, protocol version and reply text, and a specification drives the board through the runner | The host driver and the firmware are two implementations of one protocol in two languages. The simulator stands in for the firmware in every other test, so only a cross-check against the firmware sources shows that it is faithful. | `instruments/pico2_test_board/test_firmware_protocol.py::test_commands_agree`<br>`instruments/pico2_test_board/test_firmware_protocol.py::test_errors_agree`<br>`instruments/pico2_test_board/test_simulator.py::TestConversion::test_matches_the_firmware_vectors`<br>`instruments/pico2_test_board/test_spec.py::test_the_sequence_passes` | Pass: 4 of 4 in the `v0.03.0000` release run |
| ETB-IT-15 | A specification step drives the serial capture instrument through the runner (uart.command, uart.capture), and the captured lines and extracted value are checked against the specification's limits | The property spans the runner's step dispatch and limit checking, the serial capture driver's background capture thread, and its result object. The driver's unit tests never pass through the runner. | `instruments/serial_capture/test_capture.py::TestCapture::test_a_match_ends_it_early_and_gives_the_value`<br>`instruments/serial_capture/test_capture.py::TestCapture::test_as_dict`<br>`instruments/serial_capture/test_console.py::TestRoutine::test_complete_with_a_match`<br>`runner/test_shipped_benches.py::test_the_simulated_bench_provides_every_shipped_specification[serial_capture.yaml]`<br>`runner/test_integration_cases.py::test_the_serial_capture_specification_passes_through_the_runner` | Pass: 4 of 4 in the `v0.03.0000` release run; 1 added in #370, passing on its branch |

---

## 7. Entry and Exit Criteria

**Entry:** the units involved pass their own verification (ETB-SWE4-002); the
architecture they must fit is recorded in ETB-SWE2-001.

**Exit:** all integration test groups in §5 pass; the layering test passes; no
open Critical or Major problem affects an interface in §6.

Both are checked on every change, so "the integration test has passed" is a
statement about the current revision rather than about a point in the past.

---

## 8. Regression

The whole suite runs on every change. There is no separate regression
selection, because selecting a subset would require knowing which tests a change
could affect — exactly the knowledge a defect at an interface proves was wrong.

---

## 9. Results

### 9.1 Release `v0.03.0000`

| Measure | Value |
|---|---|
| Tests passing, unit and integration together | 4 555 of 4 557, with 2 Windows-only skips (ETB-SWE4-002 §4.0) |
| Statement coverage | 95.25 % to 95.31 % across the Python legs |
| Integration cases (§6) | 15. Of these, 10 are realised in full and 5 in part; the gaps are stated per case. ETB-IT-11 to -15 were defined after the release, against tests that ran in it, except those #370 added |
| Open Critical or Major integration problems | None |

Defects found at integration, and their resolutions, are recorded in
ETB-SWE4-002 §15 alongside the unit defects, because in this project the same
run found them.

From the next release on, this section gives each release's results the same
way, from that release's CI run.

---

## 10. Items Not Covered

| Item | Why | Covered by |
|---|---|---|
| Driver ↔ real instrument behaviour | No hardware in CI | ETB-SYS4-001 |
| Host ↔ dongle protocol over real USB | Requires the dongle | ETB-SYS4-001 |
| Timing measured through a real transport | Requires hardware | ETB-SYS5-001 |
| Firmware internal integration | Built and size-checked in CI; not unit-tested on target | ETB-SYS4-001 |

---

## 11. Review & Approval

Review and approval of this document are not entered in this table. They are
given by the merge of the pull request that last changed the document, and that
merge is the record (ETB-SUP8-001 §5.7). The evidence is the pull request, its
CI result and its merge record: who merged it, when, and the merge commit. The
last row of the revision history names the issue, and the issue links the pull
request.

| Role | Name | Recorded by |
|---|---|---|
| Author | Claude | The commits in the pull request |
| Reviewer | Dermot Murphy | The merge of the pull request that last changed this document |
| Approver | Dermot Murphy | The merge of the pull request that last changed this document |
