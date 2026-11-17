<img src="../../assets/brand/svg/logos/embeddedtestbench-logo-compact.svg" alt="Embedded Test Bench" width="240">

# Software Qualification Test

*Automotive SPICE® PAM v4.0 | SWE.6 — Software Qualification Test*

---

## 1. Document Identification & Control

| Field | Value | Field | Value |
|---|---|---|---|
| **Document ID** | ETB-SWE6-001 | **Version** | [latest, §2](#2-revision-history) |
| **Project** | Embedded Test Bench | **Date** | [latest, §2](#2-revision-history) |
| **Status** | [by location, ETB-SUP1-001 §6.3](EmbeddedTestBench_SUP1_Quality_Assurance_Plan.md#63-document-status) | **Classification** | Internal |
| **Author** | Claude | **Reviewer** | Dermot Murphy |
| **Approver** | Dermot Murphy | **Related Process** | SWE.6 |

> Reviewer and Approver are the same person; see ETB-DEV-002.

---

## 2. Revision History

| Version | Date | Author | Description of Change |
|---|---|---|---|
| 0.1 | 2026-09-19 | Claude | Initial |
| 0.2 | 2026-09-23 | Claude | TB-QT-02a added: the five-instrument specification run against the simulated bench. |
| 0.3 | 2026-09-24 | Claude | TB-QT-05 added: the bench self-check, simulated and gated. |
| 0.4 | 2026-10-04 | Claude | #183: product renamed to Embedded Test Bench - document file name prefix `EmbeddedTestBench_`, identifier prefix `ETB-` (was `TB-`), product name in prose. Earlier revision rows keep the names in use when they were written. |
| 0.5 | 2026-10-05 | Claude | #204: Review & Approval table points to the merge of the pull request that last changed the document, which is the review and approval (ETB-SUP8-001 §5.7); no per-change signatures or dates. |
| 0.6 | 2026-10-05 | Claude | #194: the compact brand logo added above the title, the same line in every controlled document (ETB-SUP8-001 §6.3). |
| 0.7 | 2026-10-25 | Claude | #210: Version and Date in the identification table are links to the last revision history row, which holds them (ETB-SUP8-001 §6.2). |
| next | 2026-11-17 | Claude | #371: the Status cell links to the status rule, ETB-SUP1-001 §6.3. A document's status follows from where it is in the repository (Released, Agreed, In review, In work) and is not written in by hand. |
| next | 2026-11-17 | Claude | #377: Referenced Documents cite each controlled document at the version of its last numbered revision row, kept by `scripts/doc_versions.py` (ETB-SUP8-001 §6.2). |
| next | 2026-11-17 | Claude | #370: §5 - each case names the requirements it qualifies, with no wildcards, and the tests that realise it, with their `v0.03.0000` result; partial cases state their gap. The second ETB-QT-05 is renumbered ETB-QT-21. ETB-QT-13's criterion is restated to match JLINK-FR-054. ETB-QT-01 is realised by a new test. The selection rule is stated. §6 X2 notes the partial cases. §7 gives the release's qualification summary. |

---

## 3. Purpose & Scope

### 3.1 Purpose

This document says how the integrated software is shown to meet the software
requirements of ETB-SWE1-001 — not unit by unit and not interface by interface,
but as the thing an engineer actually uses.

### 3.2 Referenced Documents

| Document ID | Title | Version |
|---|---|---|
| ETB-SWE1-001 | Embedded Test Bench Software Requirements Specification | 1.70 |
| ETB-SWE5-001 | Embedded Test Bench Software Integration & Integration Test | 0.5 |
| ETB-SYS5-001 | Embedded Test Bench System Qualification Test | 0.7 |
| ETB-RTM-001 | Embedded Test Bench Traceability Matrix | 1.83 |
| ETB-TMPL-002 | Embedded Test Bench Test Case Specification — Template | 0.5 |

### 3.3 Scope

`benchtools` as installed: its command-line interfaces, its bench and
specification file formats, and its reports. Qualification of the whole bench
including instruments is ETB-SYS5-001.

---

## 4. Qualification Strategy

Qualification is by **use**: the software is exercised the way an engineer
exercises it — a bench file, a specification file, a command, a report — and the
result is compared with what ETB-SWE1-001 says should happen.

Three properties shape the strategy:

1. **Every requirement must be covered.** `tests/test_traceability.py` fails the
   build if a requirement in ETB-SWE1-001 has no covering test, so coverage of
   requirements is mechanical rather than asserted here.
2. **Qualification runs against the simulated bench.** This is what lets it run
   on every change; what it therefore does *not* show is stated in §8.
3. **Negative cases qualify as much as positive ones.** A tool whose value is
   refusing to make unsupported claims is not qualified by showing that it works
   when everything is fine.

---

## 5. Qualification Test Cases

| ID | Qualifies | Scenario | Pass criterion | Tests | Result |
|---|---|---|---|---|---|
| ETB-QT-01 | CORE-FR-014, INST-FR-002, RUN-FR-037 | Load `benches/simulated_bench.yaml` and open every instrument in it | Every driver opens; every identity is recorded | `runner/test_shipped_benches.py::TestEveryShippedBench::test_it_loads[simulated_bench.yaml]`<br>`runner/test_shipped_benches.py::TestEveryShippedBench::test_every_driver_is_registered[simulated_bench.yaml]`<br>`runner/test_bench_self_check.py::TestTheCheckPasses::test_every_instrument_identity_is_recorded`<br>`core/test_scpi.py::TestSimulatorInjection::test_bare_sim_resource_uses_the_driver_simulator`<br>`runner/test_integration_cases.py::test_every_simulated_instrument_answers_with_an_identity` | Pass: 4 of 4 in the `v0.03.0000` release run; 1 added in #370, passing on its branch |
| ETB-QT-02 | RUN-FR-016, RUN-FR-024, RUN-FR-025 | Run `specs/sensor_bringup.yaml` against the simulated bench | Run completes; report names spec, bench and every identity; result is pass | `runner/test_sensor_bringup.py::TestItPasses::test_every_case_passes`<br>`runner/test_sensor_bringup.py::TestItPasses::test_the_run_is_disclosed_as_simulated`<br>`runner/test_sensor_bringup.py::TestItPasses::test_the_reported_version_is_recorded_as_text`<br>`runner/test_sensor_bringup.py::TestItPasses::test_the_identifier_is_reported_in_hex` | Partial. Pass: 4 of 4 in the `v0.03.0000` release run. Gap: No test asserts that this run's report names the specification, the bench and every identity |
| ETB-QT-02a | RUN-FR-016, RUN-FR-024, DMM-FR-045, BLE-FR-025 | Run `specs/sensor_power_signal_and_link.yaml` against the simulated bench: five instruments in one pass, including a current measured through the meter and a board chosen by signal strength | Run completes; every instrument identity recorded; result is pass. A bench stating a simulated current outside the specification's band fails that test and only that test | `runner/test_sensor_power_signal_and_link.py::TestItPasses::test_the_specification_passes_on_the_simulated_bench`<br>`runner/test_sensor_power_signal_and_link.py::TestItPasses::test_the_current_is_measured_through_the_meter`<br>`runner/test_sensor_power_signal_and_link.py::TestItPasses::test_the_strongest_board_is_the_one_connected_to`<br>`runner/test_sensor_power_signal_and_link.py::TestItWouldFail::test_a_board_drawing_too_much_fails_the_current_test_only` | Partial. Pass: 4 of 4 in the `v0.03.0000` release run. Gap: Identities are not asserted for this run |
| ETB-QT-03 | BLE-FR-100, BLE-FR-105, BLE-FR-108 | Run `specs/sensor_commands.yaml`, which executes `specs/sensor_commands.md` | Each markdown test appears in the report with per-step command, response, expectation, time and result | `instruments/nordic_dongle/test_script.py::TestTheShippedDocument::test_it_passes_against_the_simulated_sensor`<br>`instruments/nordic_dongle/test_script.py::TestTheReport::test_it_has_a_row_per_step_with_the_columns_asked_for`<br>`instruments/nordic_dongle/test_script.py::TestTheReport::test_the_record_carries_every_column`<br>`instruments/nordic_dongle/test_script.py::TestThroughTheDriver::test_it_runs_a_document_and_writes_the_report` | Partial. Pass: 4 of 4 in the `v0.03.0000` release run. Gap: Run through the script runner, not through `specs/sensor_commands.yaml` and the runner |
| ETB-QT-04 | BLE-FR-103, BLE-FR-104, BLE-FR-106 | A markdown step that is a delay, and a step with no stated expectation | Both recorded as **skip**, in order, neither as pass | `instruments/nordic_dongle/test_script.py::TestRunningIt::test_a_delay_waits_and_is_skipped`<br>`instruments/nordic_dongle/test_script.py::TestRunningIt::test_a_command_with_nothing_promised_is_skipped_but_recorded`<br>`instruments/nordic_dongle/test_script.py::TestRunningIt::test_a_skipped_step_does_not_make_a_run_pass_on_its_own`<br>`instruments/nordic_dongle/test_script.py::TestRunningIt::test_the_steps_are_reported_in_document_order` | Pass: 4 of 4 in the `v0.03.0000` release run |
| ETB-QT-05 | RUN-FR-023, RUN-FR-031, RUN-FR-033, BLE-FR-101, BLE-FR-106 | A step whose response does not match its expectation | Step **fail**; following steps still executed and recorded; overall result fail | `instruments/nordic_dongle/test_script.py::TestRunningIt::test_one_failure_fails_the_run`<br>`instruments/nordic_dongle/test_script.py::TestRunningIt::test_a_reply_that_does_not_match_fails_and_shows_both`<br>`runner/test_runner.py::TestSetupAndSkips::test_a_failure_does_not_stop_later_tests`<br>`runner/test_runner.py::TestFailureVersusError::test_out_of_limit_is_a_failure_not_an_error` | Pass: 4 of 4 in the `v0.03.0000` release run |
| ETB-QT-06 | RUN-FR-016, RUN-FR-060 | A specification that saves a value in one step and uses it in a later one | The later step receives the saved value; the report shows both | `runner/test_sensor_bringup.py::TestItPasses::test_the_device_was_chosen_by_that_identifier`<br>`runner/test_sensor_bringup.py::TestItPasses::test_the_identifier_is_reported_in_hex`<br>`runner/test_run_events.py::TestRebuildingTheRun::test_step_end_carries_resolved_arguments_result_and_measurements`<br>`instruments/nordic_dongle/test_script.py::TestSavingAReply::test_a_saved_reply_is_compared_later` | Pass: 4 of 4 in the `v0.03.0000` release run |
| ETB-QT-07 | RUN-FR-025 | A value with a `format:` presentation | Report shows the formatted value; the raw value is retained | `runner/test_limits.py::TestHowAValueIsReported::test_the_value_is_rendered`<br>`runner/test_limits.py::TestHowAValueIsReported::test_the_number_is_kept_beside_it`<br>`runner/test_sensor_bringup.py::TestItPasses::test_the_identifier_is_reported_in_hex`<br>`runner/test_sensor_bringup.py::TestItPasses::test_the_number_is_still_in_the_record` | Pass: 4 of 4 in the `v0.03.0000` release run |
| ETB-QT-08 | PSU-FR-001, PSU-FR-010, PSU-FR-012, PSU-FR-021 | Set channel 1 to 3.2 V, limit 500 mA, output on, read back | Setpoints and readings agree; state reported | `instruments/gpd3303d/test_psu.py::TestSetting::test_configure_can_switch_on_and_reads_back`<br>`instruments/gpd3303d/test_psu.py::TestMeasuring::test_read_channel_gathers_everything_at_once`<br>`instruments/gpd3303d/test_psu.py::TestStatus::test_the_output_bit_follows_the_output`<br>`runner/test_sensor_bringup.py::TestItPasses::test_the_rail_is_the_one_that_was_asked_for` | Pass: 4 of 4 in the `v0.03.0000` release run |
| ETB-QT-09 | PSU-FR-006 | Attempt a per-channel write while the supply is tracking | The write is **refused** with a message naming the reason; no setpoint is sent | `instruments/gpd3303d/test_psu.py::TestTracking::test_a_voltage_is_refused`<br>`instruments/gpd3303d/test_psu.py::TestTracking::test_the_refusal_says_what_to_do_instead`<br>`instruments/gpd3303d/test_psu.py::TestTracking::test_nothing_was_sent`<br>`instruments/gpd3303d/test_psu.py::TestTracking::test_switching_the_slaved_channel_is_refused` | Pass: 4 of 4 in the `v0.03.0000` release run |
| ETB-QT-10 | PSU-FR-006, PSU-FR-043 | Reset the supply from a tracking mode | Safe state reached — outputs off, setpoints zero | `instruments/gpd3303d/test_psu.py::TestTracking::test_reset_still_works`<br>`instruments/gpd3303d/test_psu.py::TestReset::test_it_switches_off_and_zeroes_the_rails`<br>`instruments/gpd3303d/test_psu.py::TestReset::test_it_leaves_the_current_limits_alone` | Pass: 3 of 3 in the `v0.03.0000` release run |
| ETB-QT-11 | JLINK-FR-020, JLINK-FR-024, JLINK-FR-043 | Flash an image with a manifest, verify, read UICR 0x10001080 | Programmed image verifies; identifier read and rendered as six uppercase hex digits | `instruments/jlink/test_probe.py::TestFlashAndVerify::test_flash_reports_what_was_written`<br>`instruments/jlink/test_probe.py::TestWhatWasFlashed::test_it_reads_the_manifest_beside_the_image`<br>`runner/test_sensor_bringup.py::TestItPasses::test_the_identifier_comes_from_the_part`<br>`runner/test_sensor_bringup.py::TestItPasses::test_the_identifier_is_reported_in_hex` | Pass: 4 of 4 in the `v0.03.0000` release run |
| ETB-QT-12 | JLINK-FR-043 | Read memory with an unsupported width or byte order | Refused with an error; no value returned | `instruments/jlink/test_probe.py::TestByteOrderedReads::test_a_width_it_does_not_support_is_refused`<br>`instruments/jlink/test_probe.py::TestByteOrderedReads::test_a_misspelled_byte_order_is_refused` | Pass: 2 of 2 in the `v0.03.0000` release run |
| ETB-QT-13 | JLINK-FR-054 | Start the target and check RTT output within a timeout | RTT output observed within the timeout; silence is reported as a count of zero lines, which the limit fails | `instruments/jlink/test_probe.py::TestIsItRunning::test_a_running_target_produces_lines`<br>`instruments/jlink/test_probe.py::TestIsItRunning::test_a_halted_target_produces_none`<br>`instruments/jlink/test_probe.py::TestIsItRunning::test_it_does_not_wait_once_lines_have_arrived`<br>`runner/test_sensor_bringup.py::TestItWouldFail::test_a_board_that_says_nothing_on_rtt` | Pass: 4 of 4 in the `v0.03.0000` release run |
| ETB-QT-14 | BLE-FR-022, BLE-FR-043 | Scan, match the advertising name against the rendered identifier, connect, send `rd version` | Connected device's identifier matches; version matches the manifest of the flashed image | `runner/test_sensor_bringup.py::TestItPasses::test_the_device_was_chosen_by_that_identifier`<br>`runner/test_sensor_bringup.py::TestItWouldFail::test_a_firmware_that_reports_another_version`<br>`instruments/nordic_dongle/test_dongle.py::TestScanning::test_filtering_by_name`<br>`instruments/nordic_dongle/test_dongle.py::TestUart::test_a_command_and_its_reply` | Pass: 4 of 4 in the `v0.03.0000` release run |
| ETB-QT-15 | BLE-FR-047, BLE-FR-102, BLE-FR-104, BLE-FR-109 | A command that receives no reply | Recorded as an error or an empty response as the specification requires — never as a pass | `instruments/nordic_dongle/test_script.py::TestASensorThatDoesNotAnswer::test_a_step_that_expected_a_reply_is_an_error`<br>`instruments/nordic_dongle/test_script.py::TestASensorThatDoesNotAnswer::test_nothing_is_recorded_as_a_response`<br>`instruments/nordic_dongle/test_script.py::TestASensorThatDoesNotAnswer::test_a_step_that_expected_none_is_still_only_skipped`<br>`instruments/nordic_dongle/test_dongle.py::TestCommandTimeout::test_a_reply_slower_than_the_wait_is_a_timeout` | Pass: 4 of 4 in the `v0.03.0000` release run |
| ETB-QT-16 | SCOPE-FR-060, SCOPE-FR-062, ANA-FR-016 | Configure channels, capture, measure period and inter-channel spread | Measurements returned with units and resolution | `instruments/tek3014b/test_scope.py::TestHostSideMeasurements::test_spread_matches_the_injected_skews`<br>`instruments/tek3014b/test_scope.py::TestHostSideMeasurements::test_host_period_agrees_with_the_instrument`<br>`instruments/tek3014b/test_scope.py::TestInstrumentMeasurements::test_units_are_reported`<br>`runner/test_runner.py::TestHappyPath::test_measured_value_is_scaled_for_the_limit` | Partial. Pass: 4 of 4 in the `v0.03.0000` release run. Gap: No test shows a measurement returned with its resolution |
| ETB-QT-17 | RUN-FR-006, RUN-FR-042, RUN-FR-043 | Run a specification against a bench containing a simulated instrument | Every report format states that the run was simulated | `runner/test_report.py::TestMarkdown::test_simulation_is_disclosed`<br>`runner/test_report.py::TestJunit::test_properties_record_the_bench`<br>`runner/test_run_events.py::TestRebuildingTheRun::test_run_start_carries_the_whole_plan`<br>`runner/test_bench.py::TestBench::test_all_sim_resources_count_as_simulated`<br>`runner/test_integration_cases.py::test_the_json_report_says_the_run_was_simulated` | Partial. Pass: 4 of 4 in the `v0.03.0000` release run; 1 added in #370, passing on its branch. Gap: The console summary line is not asserted |
| ETB-QT-18 | RUN-FR-035 | Ask for an instrument that the bench does not contain | Clear error naming what was asked for; no run started | `runner/test_runner.py::TestSetupAndSkips::test_missing_instrument_is_reported_before_anything_runs`<br>`runner/test_bench.py::TestBench::test_require_reports_everything_missing`<br>`runner/test_bench.py::TestBench::test_unknown_alias_lists_what_exists`<br>`runner/test_run_events.py::TestRebuildingTheRun::test_a_refused_bench_still_starts_and_ends_the_run` | Pass: 4 of 4 in the `v0.03.0000` release run |
| ETB-QT-19 | RUN-FR-041, RUN-FR-043, RUN-FR-050 | Produce machine-readable results | Output consumable by CI, containing each test and its result | `runner/test_report.py::TestJunit::test_counts_and_elements`<br>`runner/test_report.py::TestJunit::test_failure_and_error_are_distinct_elements`<br>`runner/test_report.py::TestJson::test_round_trips`<br>`runner/test_cli.py::TestRunCommand::test_reports_are_written` | Pass: 4 of 4 in the `v0.03.0000` release run |
| ETB-QT-20 | JLINK-FR-024, BLE-FR-014, RUN-FR-016 | A version mismatch between a device and its firmware manifest | Run fails with the two versions named | `runner/test_sensor_bringup.py::TestItWouldFail::test_a_firmware_that_reports_another_version`<br>`instruments/jlink/test_probe.py::TestWhatWasFlashed::test_it_reads_the_manifest_beside_the_image`<br>`instruments/nordic_dongle/test_firmware.py::TestStatus::test_the_description_names_both_builds`<br>`instruments/nordic_dongle/test_firmware.py::TestChecking::test_connect_can_require_it` | Pass: 4 of 4 in the `v0.03.0000` release run |
| ETB-QT-21 | RUN-FR-054, RUN-FR-055, RUN-FR-056, RUN-FR-057 | Run `specs/bench_self_check.yaml`: against the simulated bench unattended, and against a non-simulated bench with no terminal and no `--acknowledge` | Simulated run prints the warning and passes ungated; the hardware run prints the warning, exits 3 and opens no instrument | `runner/test_cli.py::TestSafetyWarning::test_the_warning_is_printed_before_anything_runs`<br>`runner/test_cli.py::TestSafetyWarning::test_a_simulated_run_is_not_gated`<br>`runner/test_cli.py::TestSafetyWarning::test_hardware_without_a_terminal_refuses_to_start`<br>`runner/test_bench_self_check.py::TestTheCheckPasses::test_a_healthy_bench_passes` | Partial. Pass: 4 of 4 in the `v0.03.0000` release run. Gap: That no instrument is opened is shown only by the exit code |

Each case names the requirements it qualifies and the tests that realise it,
with their result in the release run of `v0.03.0000` (CI run 44057132180; the
JUnit is in `docs/aspice/unit_results/v0.03.0000/`). A case marked **Partial**
is realised in part, and its gap is stated. ETB-QT-21 was the second of two
cases numbered ETB-QT-05 before #370. `tests/test_traceability.py` fails if a
test named here does not exist. Manually performed qualification cases, where
any are added, are written on ETB-TMPL-002.

**Selection (SWE.6.BP2).** For each release, every case in this table is
selected. Their tests run in the release's CI run, which runs the whole `pytest`
suite (ETB-SWE4-001 §4.8). A case is added here when a requirement change needs
a new scenario (ETB-SUP10-001 §5, step 2), and removed only with the
requirement it qualifies.

---

## 6. Entry and Exit Criteria

**Entry:** integration complete per ETB-SWE5-001 §7; the requirement set under
qualification is at a known version.

**Exit:**

| # | Criterion | State |
|---|---|---|
| X1 | Every requirement in ETB-SWE1-001 has at least one covering test | Enforced by `tests/test_traceability.py` |
| X2 | All qualification cases in §5 pass | Yes, against the simulated bench. Six cases are realised in part, with the gaps stated in §5 |
| X3 | No open Critical or Major problem against a qualified requirement | Yes |
| X4 | Items not covered are listed with the document that will cover them | §8 |

---

## 7. Results

### 7.1 Release `v0.03.0000`

The qualification summary for the release (SWE.6.BP5).

| Measure | Value |
|---|---|
| Tests passing | 4 555 of 4 557, with 2 Windows-only skips (ETB-SWE4-002 §4.0) |
| Statement coverage | 95.25 % to 95.31 % |
| Requirements without a covering test | 0 (`tests/test_traceability.py`) |
| Qualification cases | 22. Of these, 16 are realised in full and 6 in part (§5); none fails |
| Bench used | Simulated |

The last row is the one that matters most when reading the rows above it. What
the simulated bench cannot show is in §8; the hardware qualification is
ETB-SYS5-001.

From the next release on, this section gives each release's summary the same
way, from that release's CI run.

---

## 8. Items Not Covered

Qualification against the simulated bench cannot show:

| Item | Covered by |
|---|---|
| That a driver's understanding of an instrument's command set is correct | ETB-SYS5-001 |
| That measured times reflect real transport and radio behaviour | ETB-SYS5-001 |
| That the supply's real tracking behaviour matches what the simulator models | ETB-SYS5-001, PSU bench-confirmation items |
| That flash programming and verification behave as modelled on a real target | ETB-SYS5-001, JLINK bench-confirmation items |
| Firmware behaviour on the dongle hardware | ETB-SYS5-001, BLE bench-confirmation items |

---

## 9. Review & Approval

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
