# Software Unit Verification Report

*Automotive SPICE® PAM v4.0 | SWE.4 Software Unit Verification*

---

## 1. Document Identification & Control

| Field | Value | Field | Value |
|---|---|---|---|
| **Document ID** | TB-SWE4-002 | **Version** | 1.8 |
| **Project** | TestBench | **Date** | 2026-10-03 |
| **Status** | Draft | **Classification** | Internal |
| **Author** | Claude | **Reviewer** | Dermot Murphy |
| **Approver** | Dermot Murphy | **Related Process** | SWE.4 |

> **Note — Reviewer independence (TB-DEV-002):** The Reviewer and Approver are the same person (Dermot Murphy). This is accepted under deviation record **TB-DEV-002** (`docs/aspice/TestBench_DEV002_Independent_Review_Deviation.md`) on the basis that TestBench has a single human team member.

---

## 2. Revision History

| Version | Date | Author | Description of Change |
|---|---|---|---|
| 0.1 | 2026-09-19 | Claude | Initial |
| 0.2 | 2026-09-26 | Claude | §13.4: PSU-OPEN-01 and -02 closed and PSU-OPEN-06 partly confirmed on a real supply (#61, #63). |
| 0.3 | 2026-09-30 | Claude | §15: D-42 added and closed — `RttClient` polled its backend outside its lock, so the reader thread and a caller's read could poll at once. (D-41 is used on `main` by #106.) |
| 0.4 | 2026-09-30 | Claude | Execution summary re-run after adding the `PICO-` element; test groups SWE4-UT-PICO, -PICOSIM, -PICOCLI and -PICOFWPROTO added to §5; §13A added for the Pico 2 thermometer firmware and driver (#104). |
| 0.5 | 2026-10-02 | Claude | #115: execution summary re-run; §13B added for the TTi 1604 (the serial read defect, confirmation, ranges, the frequency gate, the bench test and front-panel check); D-43 and D-44 added and closed; DMM rows added to §5 and §6.1. |
| 0.6 | 2026-10-02 | Claude | #116: execution summary re-run; SWE4-UT-PATHS added to §5; §14.3 added - every shipped specification run from outside the checkout, before and after; D-45 added and closed. |
| 0.7 | 2026-10-02 | Claude | #120: execution summary re-run; §14.3 notes that the simulated bench now defines `rtt`, so `kepler_temperature.yaml` reaches `dongle.select` like the other Kepler specifications. |
| 0.8 | 2026-10-02 | Claude | #124: execution summary re-run; SWE4-UT-BLECLI count updated; D-46 added and closed. |
| 0.9 | 2026-10-02 | Claude | #126: execution summary re-run; SWE4-UT-EVENTNAMES added to §5; D-47 added and closed. |
| 1.0 | 2026-10-03 | Claude | #127: execution summary re-run on the bench PC (Windows, without coverage); SWE4-UT-PICOFLASH added to §5; §13A.6 added for reflashing the Pico 2 with no BOOTSEL press; PICO-OPEN-05 added to §13A.5. Then, after hardware confirmation on a real Pico 2 on 2026-10-03: execution summary re-run (2 756 executed, two `touch_1200` cases added); SWE4-UT-PICOFLASH 32 → 34; §4 CON-09 paragraph, §13A.5 (PICO-OPEN-01 and -05 closed, PICO-OPEN-02 not yet tested) and §13A.6 (the three methods on hardware and the Windows 1200-baud finding) updated. |
| 1.1 | 2026-10-03 | Claude | #131: whole suite re-run on Windows (§4); SWE4-UT-PICO, -PICOSIM, -PICOCLI and -PICOFWPROTO counts updated in §5; §13A re-run for the `rd` command set - 83 firmware unit cases, built with clang 21 on Windows; two-place rounding vectors added to §13A.3; §13A.2 target build repeated for #131 on the bench PC (Arm GNU 14.2.1, 0 warnings, new size figures); §13A.4 records what was not repeated; PICO-OPEN-01 and -02 restated for `rd`, PICO-OPEN-06 added; §13A.7 records the first run on a real Pico 2 - PICO-OPEN-01 closed, -02 and -06 confirmed except a reading with the sensor attached. With #127 merged: §13A.6 revised for `flash` confirming the build by `rd` (name, version and commit SHA read from the image in place of the title and build date), SWE4-UT-PICOFLASH 34 → 35, the Pico directory re-run after the merge (140 cases), and the `rd` firmware flashed and confirmed by `flash` on the real Pico 2; the first-run section is §13A.7, after #127's §13A.6. |
| 1.2 | 2026-10-03 | Claude | #134: SWE4-UT-SELECT added to §5 (14 cases, pass). |
| 1.3 | 2026-10-03 | Claude | #135: SWE4-UT-RUNEVENTS added to §5 (21 cases, pass). |
| 1.4 | 2026-10-03 | Claude | #136: SWE4-UT-CONTROL added to §5 (33 cases, pass). |
| 1.5 | 2026-10-03 | Claude | #137: SWE4-UT-VIEWSTATE (14) and SWE4-UT-VIEWSERVER (25) added to §5, pass. The page was also exercised in a browser against a simulated run: start, live tree, pause, restart while paused, the Event log page, and a phone-width layout. |
| 1.6 | 2026-10-03 | Claude | #138: SWE4-UT-VIEWTRAFFIC (26) added to §5 and SWE4-UT-VIEWSERVER 25 → 29, pass. The Instruments page was exercised in a browser against a simulated run of five instruments. |
| 1.7 | 2026-10-03 | Claude | #139: SWE4-UT-VIEWRADIO (14) added to §5, pass. The RF and BLE pages were exercised in a browser on the same simulated log. |
| 1.8 | 2026-10-03 | Claude | #140: SWE4-UT-VIEWGRAPHS (16) added to §5, pass. The Graphs page was exercised in a browser on a simulated run with supply, thermometer, meter and dongle. |

---

## 3. Purpose & Scope

### 3.1 Purpose

This document records what the verification of TB-SWE4-001 actually produced: the run, its coverage, the measured accuracy of every quantitative claim, the defects it found and their disposition, and the verdict against the pass criteria.

It is deliberately a separate work product from the specification. A specification and its results in one file can be edited into agreement; kept apart, a claim that stopped being true has to be changed where a reader can see it.

### 3.2 Referenced Documents

| Document ID | Title | Version |
|---|---|---|
| TB-SYS2-001 | TestBench System Requirements Specification | 0.1 |
| TB-SWE1-001 | TestBench Software Requirements Specification | 0.1 |
| TB-SWE2-001 | TestBench Software Architecture Description | 0.1 |
| TB-SWE3-001 | TestBench Software Detailed Design | 0.1 |
| TB-RTM-001 | TestBench Requirements Traceability Matrix | 0.1 |
| TB-SWE4-001 | TestBench Software Unit Verification Specification | 0.1 |

---

## 4. Execution summary

| Metric | Result |
|---|---|
| Tests executed | **2 756** |
| Passed | **2 750** |
| Failed | 0 |
| Errors | 0 |
| Skipped | 6 |
| Statement coverage | Not measured for revision 1.0: `pytest-cov` is not installed on the bench PC. Revision 0.9 measured **95%** (13 695 statements, 679 missed). |
| Execution time | 187.6 s, without coverage instrumentation |
| Runtime | CPython 3.14.7, Windows 10 (10.0.19045) |
| Framework | pytest 9.1.1 |

Command:

```
python -m pytest -q -x
```

The six skipped tests are in `core/transport/test_visa.py`: the `pyvisa`
optional extra is not installed on the bench PC, and those tests skip without
it, as designed. The `matplotlib`, `pyyaml` and `pyserial` extras were
installed, so their tests executed.

The suite was also run with all extras blocked - `matplotlib`, `pyvisa`,
`pyyaml` and `pyserial` - to confirm the claim that the package works
without them: **2 444 passed, 51 skipped, 2 failed. The two failures are on `develop` already and are not this change's: `test_events.py::TestWhatFeedsIt::test_the_runner_reports_each_test_s_result` and `test_serial.py::TestHandshakeLines::test_requested_states_are_applied_after_opening` both need pyserial and do not skip without it** (revision 0.5). They were blocked by a
`sitecustomize` that raises `ModuleNotFoundError` for those four names, which
is closer to a machine that never had them than uninstalling is. (The totals
differ from the figure above because the runner command-line module is skipped as a whole
rather than test by test — the shipped specifications are YAML, so without
`pyyaml` there is nothing in that module to run. Its JSON equivalents are covered
in `test_spec.py`.) The whole J-Link driver runs in that configuration, which is
the evidence for JLINK-NFR-001.

No J-Link probe, target board, GDB, GDB Server, BLE dongle, BLE sensor or TTi
1604 multimeter was present for this run, and no test needs one (PC-8): the probe is substituted at
the GDB/MI boundary, the RTT and SWO sockets by a loopback server, the dongle at
its line protocol, and the serial port by pyserial's own `loop://` handler.

Revision 1.0 re-ran the whole suite with #127's `flash` command on the bench
PC; the figures above are that run.
Revision 1.1 re-ran the whole suite with #131's `rd` command set on the same
Windows bench PC, before #127 was merged into it: **2 753 tests, 2 747 passed,
0 failed, 0 errors, 6 skipped**, in 189.6 s, CPython 3.14.7 on Windows 10,
pytest 9.1.1 (`python -m pytest`, JUnit XML for the counts). The six skips are
`test_visa.py`, because `pyvisa` is not installed on that machine, and
`pytest-cov` is not installed there either, so coverage was not measured. After
the merge of #127, only the Pico directory and the traceability check were
re-run (§5, §13A.6); the whole suite has not been re-run on the merged code.
Revision 0.9 re-ran the whole suite with #126's per-instrument event-log names
(CPython 3.11.15 on Linux, with coverage: 2 721 executed, 2 720 passed, 1
skipped). Its change to the Test Bench monitor's Events
page was also driven headless (Xvfb, Python 3.12 with Tk): declared names get a
check box and colour of their own, and a lower-case log reads the same.
Revision 0.8 re-ran it with #124's change to choosing a sensor on the BLE
command line, merged with #120.
Revision 0.7 re-ran it with #120's `rtt` entry on the simulated bench.
Revision 0.6 re-ran the whole suite with #116's input-path resolution. The run with every optional extra blocked was not
repeated for 0.6: the change adds no import of an optional package, and
`test_input_paths.py` skips its one YAML-dependent test when `pyyaml` is absent.
Revision 0.5 re-ran the whole suite with #115's changes to the TTi 1604 driver
and the core transport. Revision 0.4 re-ran the whole suite on the merge of `develop` - including
D-42's regression test (#107) - with the `PICO-` element (#104). The per-group table in §5 has
not been regenerated for the groups `develop` added since revision 0.1, so its
rows do not sum to the total: the total is the collected count.

**The Pico 2 thermometer firmware has run on a real Pico 2, but not yet with
a sensor attached** (CON-09). Its 83 host unit tests pass and it agrees with its
driver (§13A). On 2026-10-03 the host's `flash` command reflashed it on Windows
by all three routes into the bootloader (PICO-OPEN-05, §13A.6). The #131
firmware, with the `rd` command set, was cross-compiled on the bench PC and
flashed to the same Pico 2 the same day, and `flash` confirmed its name,
version and commit SHA by `rd`; every reply that does not need the SHT30-D
module was confirmed there (§13A.7). A real temperature value waits for the
module (PICO-OPEN-02).

**The dongle firmware is built but not executed** (CON-07): no dongle is
available. It is verified against the driver it must agree with, against the
hygiene rules of §4.3, by its own unit tests (§4.4), and by a real
cross-compile, link and DFU package against nRF5 SDK 17.1.0 in CI (§4.6).
Behaviour on silicon remains BLE-OPEN-02 to -04.

## 5. Results by test group

| Test group | File | Tests | Result |
|---|---|---|---|
| SWE4-UT-SCOPE | `instruments/tek3014b/test_scope.py` | 87 | Pass |
| SWE4-UT-JLINK | `instruments/jlink/test_probe.py` | 86 | Pass |
| SWE4-UT-S2LP | `instruments/s2lp/test_s2lp.py` | 75 | Pass |
| SWE4-UT-S2LPREG | `instruments/s2lp/test_registers.py` | 34 | Pass |
| SWE4-UT-S2LPPROTO | `instruments/s2lp/test_protocol.py` | 31 | Pass |
| SWE4-UT-S2LPCONFIG | `instruments/s2lp/test_configuration.py` | 63 | Pass |
| SWE4-UT-S2LPSIM | `instruments/s2lp/test_simulator.py` | 28 | Pass |
| SWE4-UT-S2LPCLI | `instruments/s2lp/test_cli.py` | 35 | Pass |
| SWE4-UT-S2LPSESSION | `instruments/s2lp/test_session.py` | 14 | Pass |
| SWE4-UT-PSU | `instruments/gpd3303d/test_psu.py` | 102 | Pass |
| SWE4-UT-BLE | `instruments/nordic_dongle/test_dongle.py` | 64 | Pass |
| SWE4-UT-BLEFIRMWARE | `instruments/nordic_dongle/test_firmware.py` | 49 | Pass |
| SWE4-UT-BLEPROTO | `instruments/nordic_dongle/test_protocol.py` | 34 | Pass |
| SWE4-UT-BLEPROFILE | `instruments/nordic_dongle/test_profile.py` | 30 | Pass |
| SWE4-UT-BLESIM | `instruments/nordic_dongle/test_simulator.py` | 30 | Pass |
| SWE4-UT-PSUSIM | `instruments/gpd3303d/test_simulator.py` | 35 | Pass |
| SWE4-UT-PSUCLI | `instruments/gpd3303d/test_cli.py` | 23 | Pass |
| SWE4-UT-SERIAL | `core/transport/test_serial.py` | 31 | Pass |
| SWE4-UT-BLESESSION | `instruments/nordic_dongle/test_session.py` | 23 | Pass |
| SWE4-UT-BLECLI | `instruments/nordic_dongle/test_cli.py` | 46 | Pass |
| SWE4-UT-BLESCRIPT | `instruments/nordic_dongle/test_script.py` | 58 | Pass |
| SWE4-UT-BLELATENCY | `instruments/nordic_dongle/test_latency.py` | 20 | Pass |
| SWE4-UT-BLEFW | `instruments/nordic_dongle/test_firmware_protocol.py` | 17 | Pass |
| SWE4-UT-LAYERING | `test_layering.py` | 81 | Pass |
| SWE4-UT-GDBMI | `instruments/jlink/test_gdbmi.py` | 37 | Pass |
| SWE4-UT-BENCH | `runner/test_bench.py` | 41 | Pass |
| SWE4-UT-MEASURE | `analysis/test_measure.py` | 35 | Pass |
| SWE4-UT-SPEC | `runner/test_spec.py` | 38 | Pass |
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
| SWE4-UT-ENGINE | `runner/test_runner.py` | 33 | Pass |
| SWE4-UT-VALIDATE | `core/test_validation.py` | 23 | Pass |
| SWE4-UT-FACTORY | `core/transport/test_factory.py` | 23 | Pass |
| SWE4-UT-LIMITS | `runner/test_limits.py` | 45 | Pass |
| SWE4-UT-SIMBASE | `core/test_simulator.py` | 22 | Pass |
| SWE4-UT-VXI11 | `core/transport/test_vxi11.py` | 22 | Pass |
| SWE4-UT-CLI | `instruments/tek3014b/test_cli.py` | 20 | Pass |
| SWE4-UT-REPORT | `runner/test_report.py` | 24 | Pass |
| SWE4-UT-TRANSPORT | `core/transport/test_base.py` | 29 | Pass |
| SWE4-UT-ENV | `instruments/tek3014b/test_simulator.py` | 19 | Pass |
| SWE4-UT-PLOT | `analysis/test_plotting.py` | 15 | Pass |
| SWE4-UT-RUNCLI | `runner/test_cli.py` | 15 | Pass |
| SWE4-UT-SELECT | `runner/test_selection.py` | 14 | Pass |
| SWE4-UT-RUNEVENTS | `runner/test_run_events.py` | 21 | Pass |
| SWE4-UT-CONTROL | `runner/test_control.py` | 33 | Pass |
| SWE4-UT-VIEWSTATE | `viewer/test_state.py` | 14 | Pass |
| SWE4-UT-VIEWSERVER | `viewer/test_server.py` | 29 | Pass |
| SWE4-UT-VIEWTRAFFIC | `viewer/test_traffic.py` | 26 | Pass |
| SWE4-UT-VIEWRADIO | `viewer/test_radio.py` | 14 | Pass |
| SWE4-UT-VIEWGRAPHS | `viewer/test_graphs.py` | 16 | Pass |
| SWE4-UT-PATHS | `core/test_paths.py`, `runner/test_input_paths.py` | 70 | Pass |
| SWE4-UT-EVENTNAMES | `runner/test_event_names.py` | 21 | Pass |
| SWE4-UT-RESOLVE | `runner/test_resolve.py` | 27 | Pass |
| SWE4-UT-BRINGUP | `runner/test_sensor_bringup.py` | 18 | Pass |
| SWE4-UT-COREFW | `core/test_firmware.py` | 13 | Pass |
| SWE4-UT-SOCKET | `core/transport/test_socket.py` | 12 | Pass |
| SWE4-UT-VISA | `core/transport/test_visa.py` | 6 | Pass |
| SWE4-UT-PICO | `instruments/pico_sht30/test_thermometer.py` | 44 | Pass |
| SWE4-UT-DMM | `instruments/tti1604/test_dmm.py` | 34 | Pass |
| SWE4-UT-DMMPROTO | `instruments/tti1604/test_protocol.py` | 56 | Pass |
| SWE4-UT-DMMSIM | `instruments/tti1604/test_simulator.py` | 28 | Pass |
| SWE4-UT-DMMCLI | `instruments/tti1604/test_cli.py` | 8 | Pass |
| SWE4-UT-DMMPANEL | `instruments/tti1604/test_front_panel_check.py` | 7 | Pass |
| SWE4-UT-PICOSIM | `instruments/pico_sht30/test_simulator.py` | 36 | Pass |
| SWE4-UT-PICOCLI | `instruments/pico_sht30/test_cli.py` | 16 | Pass |
| SWE4-UT-PICOFLASH | `instruments/pico_sht30/test_flash.py` | 35 | Pass |
| SWE4-UT-PICOFWPROTO | `instruments/pico_sht30/test_firmware_protocol.py` | 9 | Pass |
| **Total** | | **2 591** (2 590 passed, 1 skipped) | **Pass** |

The thermometer firmware's own unit tests (`SWE4-UT-PICOFW`, 83 cases) run
under CTest, not pytest, and are reported in §13A. The five `PICO` rows above
are the counts after #127 was merged into #131 (140 in all, from
`python -m pytest tests/instruments/pico_sht30 -q`); the total row is still the
revision 0.4 figure, as explained in §4.

## 6. Coverage detail

| Element | Module | Statements | Missed | Coverage |
|---|---|---|---|---|
| S2LP | `instruments/s2lp/registers.py` | 95 | 0 | 100% |
| S2LP | `instruments/s2lp/configuration.py` | 130 | 4 | 97% |
| S2LP | `instruments/s2lp/constants.py` | 57 | 1 | 98% |
| S2LP | `instruments/s2lp/protocol.py` | 97 | 4 | 96% |
| S2LP | `instruments/s2lp/s2lp.py` | 386 | 15 | 96% |
| S2LP | `instruments/s2lp/cli.py` | 171 | 9 | 95% |
| S2LP | `instruments/s2lp/session.py` | 123 | 9 | 93% |
| S2LP | `instruments/s2lp/simulator.py` | 231 | 26 | 89% |
| S2LP | `instruments/s2lp/packets.py` | 123 | 19 | 85% |
| PSU | `instruments/gpd3303d/constants.py` | 25 | 0 | 100% |
| PSU | `instruments/gpd3303d/psu.py` | 253 | 5 | 98% |
| PSU | `instruments/gpd3303d/simulator.py` | 140 | 7 | 95% |
| PSU | `instruments/gpd3303d/cli.py` | 113 | 6 | 95% |
| CORE | `core/enums.py` | 20 | 0 | 100% |
| CORE | `core/firmware.py` | 80 | 3 | 96% |
| CORE | `core/errors.py` | 20 | 0 | 100% |
| CORE | `core/transport/constants.py` | 8 | 0 | 100% |
| CORE | `core/validation.py` | 33 | 0 | 100% |
| CORE | `core/instrument.py` | 82 | 2 | 98% |
| CORE | `core/simulator.py` | 96 | 5 | 95% |
| CORE | `core/transport/base.py` | 139 | 7 | 95% |
| CORE | `core/transport/factory.py` | 107 | 5 | 95% |
| CORE | `core/transport/mock.py` | 60 | 4 | 93% |
| CORE | `core/transport/serial_port.py` | 87 | 6 | 93% |
| CORE | `core/scpi.py` | 127 | 11 | 91% |
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
| JLINK | `instruments/jlink/timing.py` | 81 | 3 | 96% |
| JLINK | `instruments/jlink/cli.py` | 191 | 18 | 91% |
| JLINK | `instruments/jlink/probe.py` | 640 | 61 | 90% |
| JLINK | `instruments/jlink/session.py` | 159 | 16 | 90% |
| JLINK | `instruments/jlink/simulator.py` | 473 | 46 | 90% |
| BLE | `instruments/nordic_dongle/profile.py` | 152 | 3 | 98% |
| BLE | `instruments/nordic_dongle/cli.py` | 147 | 4 | 97% |
| BLE | `instruments/nordic_dongle/latency.py` | 93 | 3 | 97% |
| BLE | `instruments/nordic_dongle/script.py` | 243 | 4 | 98% |
| BLE | `instruments/nordic_dongle/protocol.py` | 95 | 3 | 97% |
| BLE | `instruments/nordic_dongle/constants.py` | 72 | 3 | 96% |
| BLE | `instruments/nordic_dongle/dongle.py` | 285 | 13 | 95% |
| BLE | `instruments/nordic_dongle/session.py` | 165 | 9 | 95% |
| BLE | `instruments/nordic_dongle/simulator.py` | 276 | 17 | 94% |
| RUN | `runner/limits.py` | 98 | 1 | 99% |
| RUN | `runner/results.py` | 106 | 0 | 100% |
| RUN | `runner/bench.py` | 134 | 2 | 99% |
| RUN | `runner/report.py` | 138 | 1 | 99% |
| RUN | `runner/spec.py` | 188 | 7 | 96% |
| RUN | `runner/cli.py` | 94 | 3 | 97% |
| RUN | `runner/runner.py` | 139 | 5 | 96% |
| RUN | `runner/resolve.py` | 92 | 0 | 100% |
| — | `cli.py` | 42 | 0 | 100% |
| — | `__main__.py` | 4 | 4 | 0% |
| **TOTAL** | | **7 604** | **444** | **94%** |

The `__init__.py` files are omitted for brevity; `__main__.py` is discussed below.

### 6.1 Justification for uncovered code

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
| `instruments/jlink/cli.py`, `nordic_dongle/cli.py` | Argument-error branches of sub-commands whose happy path is covered | Thin `argparse` plumbing; each is one `return 2`. |
| `instruments/tti1604/cli.py` | `--json` file output, `--reject-held` and the connect-error branch (89%; unchanged by #115) | Thin `argparse` plumbing whose happy path is covered; the decoding it reports is covered in full by SWE4-UT-DMMPROTO. |
| `core/transport/serial_port.py` | Buffer-reset and `in_waiting` fallbacks for URL handlers that do not implement them | Reached only with a pyserial URL handler that lacks the call; the guards exist so an exotic handler degrades instead of raising. |
| `instruments/nordic_dongle/session.py`, `dongle.py` | Transport-error branches and best-effort cleanup | The principal failures (timeout, refusal, protocol mismatch) are covered; the remainder translate a dead link. |

Coverage meets PC-2 (≥ 90%) at package level and at every module level except the
four justified above.

## 7. Work-product and architectural verification results

### 7.1 Traceability consistency

| Check | Result |
|---|---|
| All 195 requirements declared in SWE.1 appear in the traceability matrix | Pass |
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

### 7.2 Architectural verification

| Check | Result |
|---|---|
| Every module's imports respect the layering (parametrised over all 58 sources) | Pass |
| `benchtools.core` references no instrument, checked over code identifiers | Pass |
| `benchtools.core` imports in a fresh interpreter with no other element loaded | Pass |
| `benchtools.analysis` imports without instruments or the runner | Pass |
| No module imports a third-party package at module level (CORE-NFR-001, JLINK-NFR-001) | Pass |
| Source discovery guard (the suite cannot pass on an empty file list) | Pass |

### 7.3 Firmware verification without a compiler

The dongle firmware cannot be built here, so it is verified against the two
things that do not need a toolchain: the artefact it shares with the driver, and
the rules it is written to.

| Check | Result |
|---|---|
| Every command in `PROTO_COMMAND_TABLE` is known to the driver | Pass (12 commands) |
| The driver invents no command the firmware would reject | Pass |
| Argument bounds agree, command by command | Pass |
| Every documented command has a handler attached in `cmd_parser.c` | Pass |
| Event names agree | Pass (7 events) |
| Error codes agree, symbol by symbol | Pass (11 codes) |
| `PROTO_MAX_*` limits agree with `DongleLimits` | Pass (4 limits) |
| Protocol version and model agree | Pass |
| Every firmware source carries a `Traces to` line | Pass (12 files) |
| No `malloc`/`calloc`/`realloc`/`free` anywhere in the firmware | Pass (BLE-NFR-001) |
| House indentation (tabs) throughout the firmware | Pass |

PC-10 is met.

### 7.4 Firmware unit tests

The firmware now has unit tests of its own: Unity, built by CMake, run by CTest,
with fake SDK headers at the SDK boundary so the firmware's sources compile
unchanged and the logic under test is the logic that runs on the dongle.

| Binary | Cases | Result |
|---|---|---|
| `test_cmd_parser` | 50 | Pass |
| `test_ble_scanner` | 30 | Pass |
| `test_nus_client` | 20 | Pass |
| `test_cdc_acm` | 20 | Pass |
| `test_timestamp` | 11 | Pass |
| **Total** | **131** | **Pass** |

```
cmake -S firmware/nordic_dongle/test -B build/firmware-tests
cmake --build build/firmware-tests
ctest --test-dir build/firmware-tests --output-on-failure
```

`test_cmd_parser` is the one to note. The host driver is tested against a
*simulated* dongle; this is the only place the **real firmware's** replies are
checked, so the two halves of the protocol are now verified against each other
from both sides rather than one side being assumed.

The suite found two defects immediately (D-27, D-28), both of the kind that
compile cleanly and behave wrongly.

### 7.5 Firmware compilation against real SDK headers

Since the first issue of this report, the firmware has been **compiled**, in the
`canembed/canembed-arm` container image, which carries `arm-none-eabi-gcc`
10.2.1, SEGGER Embedded Studio 4.16 and nRF5 SDK 15.2.0.

The firmware targets SDK 17.1.0, which is not in the image and cannot be
downloaded here (Nordic's hosts are blocked by the network policy), so this is a
**cross-version** check. It is run by
`firmware/nordic_dongle/scripts/compile_check.sh`.

| Unit | Result |
|---|---|
| `timestamp.c` | Compiles, 0 warnings |
| `cdc_acm.c` | Compiles, 0 warnings |
| `ble_scanner.c` | Compiles, 0 warnings |
| `cmd_parser.c` | Compiles, 0 warnings |
| `nus_client.c` | Compiles apart from two SDK 17 members (`ble_nus_c_init_t.error_handler`, `.p_gatt_queue`) |
| `main.c` | Compiles apart from `ble_db_discovery_init_t`, which SDK 15.2 does not have |

Compiled with `-Wall -Wextra -std=c99 -O2` for Cortex-M4 hard-float. The four
excluded lines are the SDK 17 GATT-queue plumbing, which SDK 15.2 has no
equivalent for; they are listed by the script rather than skipped silently, and
a second pass compiles copies of those two files with exactly those lines
removed - both then compile with 0 warnings.

**What this establishes:** syntax, types, every SDK API this firmware calls that
exists in both versions, and the `sdk_config.h` keys the SDK's own headers
static-assert on. **What it does not:** that the firmware links, fits in flash,
or runs. That is §4.6, which is where BLE-OPEN-01 is discharged.

It found seven defects (D-20 to D-26), one of which was a concurrency error that
no amount of reading had caught.

PC-12 is met: every firmware unit test passes, and the firmware still compiles
for the target after the fixes they prompted.

### 7.6 First build against nRF5 SDK 17.1.0, linked and packaged

The `firmware` workflow builds against the real SDK: it downloads nRF5 SDK
17.1.0, cross-compiles with `arm-none-eabi-gcc` 10.3-2021.10, links, reports the
size, and packages the hex as a DFU zip. It runs on every push touching
`firmware/**`.

Run 12 on commit `f66a248` is the first green one. Both jobs pass and all five
artefacts are produced - `.hex`, `.out`, `.map`, `nordic_dongle_dfu.zip` and
`firmware_manifest.json`.

The link map, from the build's own `size` output:

| | Bytes | Region | Used |
|---|---|---|---|
| Flash (`text` + `data`) | 51 652 | 0x27000 … 0x100000 less the bootloader, 0xd9000 = 888 832 | 5.8% |
| Static RAM (`data` + `bss`) | 12 636 | 0x3d518 = 251 160 above the SoftDevice's requirement | 5.0% |

`text` 49 800, `data` 1 852, `bss` 10 784. The 8 KiB stack and 2 KiB heap are
set by the build (`__STACK_SIZE`, `__HEAP_SIZE`); the `.map` in the artefact is
the authority on where they sit relative to those figures. Either way the image
is nowhere near the region, which was the open question.

**BLE-OPEN-01 is discharged.** The firmware builds, links and fits, and the
GATT-queue lines that SDK 15.2 could not compile do compile against SDK 17.1.0.
What remains is on-silicon behaviour, which is BLE-OPEN-02 to -04 and CON-07 -
none of which can be reached without a dongle.

Getting there took eleven red runs, and what they found is worth recording,
because none of it was reachable by reading:

- The build could not have linked on any machine (D-37). The Makefile named a
  source that does not exist in nrfx 2.x and omitted three that do; a missing
  source was a warning, not an error.
- `sdk_config.h` was missing seven keys (D-38). Each fails inside an unrelated
  SDK file, because SDK modules expand their own configuration macros into
  static assertions and, in one case, into a ternary in C code - so a key is
  required even when the feature it configures is switched off.
- The GATT queue was sized for 20-byte writes against a protocol that sends up
  to 96 (D-36), which would have refused every long command on the part.

One tooling fault is not a product defect but is recorded here because it will
catch anyone following the flashing instructions: an unpinned
`pip install nrfutil` on a current Python does not refuse to install - it
resolves backwards to a Python 2 era release, which dies in `pkg generate` on
`dict.iteritems`. The workflow now pins `nrfutil==6.1.7` and a 3.10 interpreter,
and `docs/ble/BLE_Dongle_Notes.md` §3.2 says why.

PC-5 and PC-9 are met. This is the check that keeps the shared core shareable as
the instruments named in CON-03 are added — and it has already paid: adding the
J-Link driver, which needs a process transport in the core and a non-SCPI
instrument base, moved code *into* the core without any instrument knowledge
leaking in with it.

The third-party import check is new in this revision. CORE-NFR-001 had until now
been verified by inspection and by the extras-blocked run; neither would catch a
module-level `import yaml` added to a module no test imports in that
configuration. It is now parsed for, over every module.

## 8. Quantitative verification of timing accuracy

PC-4 requires injected skews to be recovered to better than one tenth of a sample
interval.

### 8.1 Against synthesised waveforms

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

### 8.2 Through the full driver, against the simulated instrument

Stimulus: four channels at 1 MHz / 3.3 V with skews 0, 12, 25 and 5 ns;
200 ns/div, 10 000 points, giving a 200 ps sample interval.

| Quantity | Result |
|---|---|
| Spread recovered | 25 ns, within 20 ps of injected (0.1 sample interval) |
| Agreement with the instrument's own `DELay` measurement | within 20 ps on all three channel pairs |
| Earliest / latest channel identified | CH1 / CH3, correct |
| End-to-end per-channel skews | 0.000, 12.011, 25.000, 5.011 ns against injected 0, 12, 25, 5 — worst residual 11 ps, i.e. 0.055 of a sample interval |

PC-4 is met.

### 8.3 Period measurement

| Quantity | Result |
|---|---|
| Injected period | 1.000000 µs |
| Host-side mean over 4 periods | 1.000000 µs (relative error < 1 × 10⁻⁶) |
| Peak-to-peak jitter on an ideal signal | < 1 fs (numerical noise only) |
| Instrument-side period | 1.000000 µs |
| Agreement between the two | within 0.1% |

## 9. Debug probe verification results

### 9.1 Timing between two lines of code

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

### 9.2 Probe operations against the simulated target

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

## 10. BLE dongle verification results

### 10.1 Advertising profile

The simulated sensor advertises at 100 ms with advertising delays of 0, 3, 7 and
10 ms in rotation - the specification's 0-10 ms advDelay, made deterministic. A
five second capture through the driver:

| Quantity | Measured | Expected by construction |
|---|---|---|
| Advertising events | 49 | 5.0 s / 105 ms, rounded down, plus the first |
| Mean interval | 105.00 ms | 105 ms (100 + mean delay) |
| Minimum interval | 100.00 ms | exactly 100 ms |
| Maximum interval | 110.00 ms | exactly 110 ms |
| Spread | 10.00 ms | exactly 10 ms |
| Jitter (sd) | 3.85 ms | 2.9 ms for uniform advDelay; higher for a 4-point rotation |
| Missed events | 0 | 0 |
| Duty cycle | 1.000 | 1.0 |
| Complete | true | no drops configured |

The bounds are exact, which is the point of a deterministic model: a scaling
error of any size moves them.

The second sensor skips one beacon in five. Over three seconds it reports missed
events and a duty cycle below 1.0, so a dropout is detected rather than averaged
away. With `drop_every` set on the dongle, `is_complete` goes false and the CLI
adds its warning - the case where missed beacons must *not* be blamed on the
sensor.

### 10.2 Command and response

| Check | Result |
|---|---|
| Connect, discover the UART service, report ready | Pass |
| Connection interval reported from the `+conn` event | Pass — 30.0 ms |
| Command and reply | Pass — `version` → `1.4.2` |
| Round trip on the dongle's clock | Pass — 12.500 ms, exactly as modelled |
| A command that takes real work | Pass — 95.000 ms |
| 95 ms flagged trustworthy, 12.5 ms not | Pass — 12.5 ms is inside one connection interval |
| Host-clock figures kept separately | Pass — 0.02 ms in simulation, correctly flagged unresolvable |
| An over-long payload refused before transmission | Pass |
| A sensor that cannot be connected to | Pass — refusal reported with the reason |

The trustworthiness rule is the one worth stating: with a 30 ms connection
interval, a 12.5 ms round trip says where the write landed in the interval, not
what the sensor's firmware did. The tooling refuses to present it as the latter.

### 10.3 Session log

A profile capture logged to a text file contains the commands sent, the replies,
every `+adv` event with both timestamps, and any comment the caller wrote -
flushed per line, so a session that then hangs still has a complete log. Verified
by `TestLogging` in both `SWE4-UT-BLESESSION` and `SWE4-UT-BLE`.

## 11. Protocol interoperability results

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

## 12. S2-LP kit verification results

No S2-LP kit was present (PC-8). The driver is verified against a simulated kit
that models a **register file with a radio attached**: writing a register changes
what the queries that read it answer, and a packet queued on the simulated air is
delivered to exactly one receive.

### 12.1 The vendor firmware was examined before any was written

STK-20 asked whether ST's firmware is fit for purpose. It was read, not assumed
about: the source of the CLI application ST's S2-LP DK GUI drives is published at
`STMicroelectronics/x-cube-subg2`, under
`Projects/NUCLEO-L053R8/Examples/S2868A1_CLI/`.

| Question | Answer, and where it was read |
|---|---|
| What does the GUI talk to? | `README.md`: "CLI example for S2-LP Expansion Board and S2-LP DK GUI". A CLI application over the kit's USB serial port |
| What is the wire format? | `command-interpreter2.c` — ASCII lines; `command-interpreter2.h` documents the argument letters (`u` one byte, `v` two, `w` four, `b` a string in `{ }` hex or quotes) |
| Can every register be read and written? | Yes: `SDK_CLI_commands.h` declares `SdkEvalSpiReadRegisters` (`uu`) and `SdkEvalSpiWriteRegisters` (`ub`), plus strobes and FIFO access |
| Can it transmit and receive? | Yes: `S2LP_CLI_commands.h` declares `S2LPSendNBytes`, `S2LPSendNBytesBatch`, `S2LPGetNBytes`, `S2LPGetNBytesBatch` |
| What do replies look like? | `SDK_CLI_commands.c` and `response.c` — brace-delimited tags, e.g. `{regs_list: 0x00,0x0A}` and `{timer:000004D2}` |
| Can a long capture be stopped? | Yes: `checkStop()` polls the port for the single character `S` inside the capture loops |
| Line rate | 115200 8N1 (`stm32l0xx_nucleo.c`) |

**Conclusion: fit for purpose, and used unchanged** (AD-20). Nothing in this
repository runs on the kit. Three limits come with that decision and are carried
into the design rather than hidden:

| Limit | Consequence, and what the driver does about it |
|---|---|
| Reception is **polled** — the firmware arms the radio when asked and returns | A packet arriving between calls is invisible. `Capture.gaps` records every re-arm; `is_continuous` is false when there were any, and `capture(continuous=True)` keeps the board in its own loop so that there are none |
| Timestamps are the **motherboard's millisecond timer** | Good enough to order packets and time a sequence, not to characterise protocol timing. The field is named `board_time_ms`, and the limit is stated wherever it is reported |
| ST's package is under **SLA0072**, a limited licence | The protocol is interoperated with; no ST source is vendored. The register map holds facts about the silicon, not vendor prose (S2LP-NFR-002) |

### 12.2 The register map

123 registers, each with its address, reset value, access and named bit fields.
The map is data, so it is verified as data: unique addresses, unique names, no
overlapping fields, every field inside its byte, and every status register
read-only (`SWE4-UT-S2LPREG`, 34 cases).

Read as contiguous runs, a full dump is **15 commands rather than 123** — on a
115200 baud link, the difference between a dump that feels instant and one that
does not. A dump renders as:

```
0x2E PCKTCTRL3              = 0xC0            PCKT_FRMT=3
0x2F PCKTCTRL2              = 0x07  (reset)   MBUS_3OF6_EN=1 MANCHESTER_EN=1 FIX_VAR_LEN=1
```

which is the point of holding the map at all: 123 hex bytes say nothing about
how a radio was configured, and this says it.

### 12.3 Register values from a file

The values a test requires are read from a file of register names and hex
values, applied, and checked back. The check has two modes, and the difference
between them is the point:

| | Loose (default) | Strict |
|---|---|---|
| Registers the file names | must match | must match |
| Registers it does not name | not examined | must be at their reset value |
| Question answered | "is what this test needs set?" | "is the radio in exactly this configuration?" |
| Reads | only the named registers | the whole map |

Applied to a fresh simulated radio and then verified:

```
3 register(s) match config.regs and nothing else is set
```

and after a single stray write to a register the file does not name, the loose
check still passes while the strict one reports:

```
1 set but not named by the file: GPIO0_CONF = 0x55
```

Every way a file can be wrong is refused naming the file and the line — an
unknown register, a value that does not fit a byte, a read-only register, a
register set twice, a line that is not a setting, and an empty file. Applying
verifies by read-back, because this radio's writes are acknowledged by the
firmware rather than by the radio.

### 12.4 A configuration is applied to a known radio

A file that names some registers says nothing about the others, so what a
partial file produces depends on what ran before it. `reset` settles that, and
the reset itself is confirmed before anything is written:

| Applied after a stray write to GPIO0_CONF | Registers not at their default afterwards |
|---|---|
| `apply_configuration(file)` | `GPIO0_CONF`, plus the file's own |
| `apply_configuration(file, reset="defaults")` | the file's own |
| `apply_configuration(file, reset="power")` | the file's own |

which is what makes the strict check meaningful: after a reset and an apply,
"the radio holds this file and nothing else" is a statement the suite has
established rather than inherited.

The device's reset **strobe** is deliberately not one of the choices - see
D-35. A simulated kit whose `SdkEvalSdn` never shuts down produces:

```
InstrumentError: the radio is not at its register defaults after a power reset:
GPIO0_CONF = 0x55 (default 0x0A). The configuration was not applied, because it
would have been written on top of a state nobody established.
```

### 12.5 A capture states how it was taken

| Capture | Packets | Gaps | `is_continuous` | What it may be quoted as |
|---|---|---|---|---|
| `capture(count=3)` — board-side loop | 3 | 0 | yes | a record of the air for its duration |
| `capture(count=2, continuous=False)` | 0 | 9 | no | "nothing was heard while listening" — nothing more |

The second row is the one that matters. Both captures are honest; only the first
supports a statement about what was *not* transmitted.

## 13. Power supply verification results

No GPD-3303D was present (PC-8). The driver is verified against a simulated
supply that models a **load**, which is what makes the interesting condition
reachable: a channel whose load draws more than its limit.

### 13.1 Constant current is detected, not averaged over

Channel 2 with 2 Ω across it, set to 3.3 V with a 500 mA limit:

| Quantity | Value | |
|---|---|---|
| Setpoint | 3.300 V | what the test asked for |
| Measured voltage | 1.000 V | what the board actually got |
| Measured current | 0.500 A | the limit, not the demand |
| Mode | `CC` | the reason for the other three |
| `regulated` | `False` | the one line a test should assert on |

The figure to note is 1.000 V. A driver that reported only the voltage would
hand a test a plausible number describing a circuit nobody asked for, and the
test would fail somewhere else entirely - or, worse, pass.

### 13.2 The emulated per-channel switch behaves as documented

| Action | Channel 1 | Channel 2 | Supply's own switch |
|---|---|---|---|
| both configured, `all_outputs_on()` | 3.300 V | 5.000 V | closed |
| `output_off(1)` | 0.000 V | 5.000 V | **still closed** |
| `set_voltage(1, 5.0)` | 0.000 V | 5.000 V | still closed |
| `output_on(1)` | 5.000 V | 5.000 V | closed |
| `output_off(1)`, `output_off(2)` | 0.000 V | 0.000 V | **open** |

Row three is the property that matters: programming a parked channel does not
energise it. Row five is the other: once every channel is off, the supply's real
switch is opened, so "all off" is not two rails sitting at zero volts.

### 13.3 Channel 2 while the supply is tracking

The element was retargeted from the GPD-2303S to the GPD-3303D. The two
supplies share a command set, and the driver's behaviour is unchanged except
for one property the 3303D brings with its tracking modes: in **series** and
**parallel**, the supply drives CH2 from CH1, and a setpoint addressed to CH2
is accepted and discarded. No error, nothing in `STATUS?`, and a read-back of
CH2 that agrees with CH1.

That is the shape of D-30 and D-31 again - a command that appears to succeed
and changes nothing - so it is refused rather than reported:

| Call, supply in series or parallel tracking | Result |
|---|---|
| `set_voltage(2, 3.3)`, `set_current_limit(2, 0.5)` | refused, naming the mode; nothing sent |
| `output_on(2)`, `output_off(2)` | refused: the per-channel switch is emulated by programming the channel to zero, so it is discarded too |
| `set_voltage(1, 5.0)` | applied - CH1 is the master in both modes, and CH2 follows it |
| `all_outputs_on()`, `all_outputs_off()`, `reset()` | applied: they act on the supply's real switch and on CH1, so a safe state is reachable in every mode |
| tracking mode the status word does not decode | warned about and **allowed**, so one unconfirmed status bit cannot disable setting altogether |

The simulated supply models the discard - `VSET2:` in tracking mode changes
nothing and records no error - so the refusal is tested against the behaviour it
exists for rather than against a rule restating itself. That is the lesson of
D-31 and D-35 applied in advance: a test double that is politely wrong makes
every test above it vacuous.

The supply's third output, the fixed 2.5 / 3.3 / 5 V rail, is outside the
element. It is selected by a front-panel switch that no command reaches, so a
driver could only repeat what it had been told about it.

### 13.4 What could not be verified without the instrument

| Item | Why |
|---|---|
| PSU-OPEN-01 | **Closed 2026-09-26** (TB-IF-001 §7). Bit 0 is sent first; the output is bit 6, not bit 5 as the manual-based decode assumed; the V1.09 reply is spaced and followed by a legend. The driver was corrected in #61. |
| PSU-OPEN-02 | **Closed 2026-09-26** (TB-IF-001 §8). `No Error.`, `Invalid Character.`, `Data out of range.`, `Undefined Header.`; one error held, cleared by reading it. |
| PSU-OPEN-03 | The command interval a real GPD-3303D needs. 50 ms is a conservative default taken from the supply having no flow control; the figure to confirm is the smallest interval at which a long sweep loses nothing. |
| PSU-OPEN-04 | Settling time after a setpoint change. The driver does not wait; a specification that measures immediately after `set_voltage` should state its own `sleep`. |
| PSU-OPEN-05 | Whether a real GPD-3303D discards a setpoint sent to the slaved channel **silently**, as modelled here, or records something in `ERR?`. The driver refuses the command either way, so the refusal is right in both cases; what is unconfirmed is the sentence that says the supply reports nothing. Send `VSET2:1.000` in series tracking, then `ERR?`. |
| PSU-OPEN-06 | Independent **confirmed 2026-09-26**: bit 2 `0`, bit 3 `1`, read bit 2 first. The original decode read that as parallel (#61). Series and parallel still need the front-panel switch moved. |

## 13A. Pico 2 thermometer verification results

### 13A.1 Firmware unit tests (`SWE4-UT-PICOFW`)

Host build for #131: clang 21.1.0 on Windows 10 (Ninja, CMake 3.27), C11,
`-Wall -Wextra -Wconversion -Wshadow -Wstrict-prototypes -Werror`,
`-fsanitize=address,undefined -fno-sanitize-recover=all`, Unity v2.6.0, with
`-D_CRT_SECURE_NO_WARNINGS` and the AddressSanitizer runtime on `PATH`
(TB-SWE4-001 §1.4b). The bench PC's MinGW GCC 6.3 cannot be used: it stops with
an internal compiler error on `-fsanitize=address`, which it did before #131
too. The #104 run, 61 cases, was with GCC on Linux.

| Suite | File | Cases | Result |
|---|---|---|---|
| text | `test/test_text.c` | 15 | Pass |
| sht30 | `test/test_sht30.c` | 22 | Pass |
| cmd_parser | `test/test_cmd_parser.c` | 46 | Pass |
| **Total** | | **83** | **Pass**, no warnings, no sanitizer reports |

Against #104's 61 cases, `text` gains five for `text_centi` (two places,
rounding half away from zero, the sign, no `-0.00`, the extremes), and
`cmd_parser`'s `ver` and `temp` cases are replaced by cases for every `rd`
option, the injected SHA, identity without touching the sensor, `NAK` for an
unknown, partial or wrongly cased option and the longest option echoed whole,
`err 2` for no option or two, the temperature's places, rounding and sign, one
measurement per `rd temperature`, `Error` for each sensor failure (no sensor, a
NACK on the read, a corrupted frame, a bus timeout on either transfer), `ver`,
`temp` and `reset` refused, and `ecureset` replying before it reboots.

### 13A.2 Target build (PICO-FR-031, PICO-NFR-003)

The figures below are for the #131 firmware, built from commit `5c80ae7` on
the Windows 10 bench PC on 2026-10-03. The #104 firmware, built on Linux, was
60 928 bytes as a UF2, with text 29 996 B and bss 3 884 B; the `rd` firmware is
smaller because the humidity and raw-word replies are gone.

| Item | #131 result |
|---|---|
| SDK | Raspberry Pi Pico C SDK 2.1.1, TinyUSB submodule, prebuilt picotool 2.1.1 |
| Toolchain | Arm GNU Toolchain 14.2.Rel1 (`arm-none-eabi-gcc` 14.2.1) |
| Board / platform | `pico2` / `rp2350-arm-s` (Cortex-M33, secure) |
| Warnings on the firmware's own sources | **0** (`-Werror`) |
| Image | `pico_sht30.uf2`, 58 368 bytes |
| Size (`arm-none-eabi-size`) | text 28 764 B, data 0 B, bss 3 476 B |
| Commit SHA injected | Configure printed `FIRMWARE_GIT_SHA=b6213cc` before the #131 commit was made; after the commit the next build re-configured itself and injected `5c80ae7`, which `rd sha` then reported on the Pico (§13A.6) |

### 13A.3 Conversion reference vectors

The same vectors are asserted in C (`test_sht30.c`) and in Python
(`test_matches_the_firmware_vectors`). Since #131 only the temperature is
reported, and the raw word no longer travels with it; the humidity vectors
still hold for the firmware's conversion:

| Raw word | Temperature | Raw word | Humidity |
|---|---|---|---|
| 0x0000 | −45.000 °C | 0x0000 | 0.000 % |
| 0x0001 | −44.997 °C (rounded, not truncated) | 0x6666 | 40.000 % |
| 0x4000 | −1.249 °C | 0x8000 | 50.001 % |
| 0x6666 | 25.000 °C | 0xFFFF | 100.000 % |
| 0xFFFF | 130.000 °C | | |

CRC-8 check value CRC(0xBE, 0xEF) = 0x92, as the datasheet gives it.

The two-place rounding of `rd temperature` (PICO-FR-027) is asserted the same
way, in C (`test_text.c`, `test_cmd_parser.c`) and in Python
(`test_two_places_half_away_from_zero`, 12 vectors):

| Thousandths | Reported | Thousandths | Reported |
|---|---|---|---|
| 22 848 | `22.85` | −1 234 | `-1.23` |
| 22 844 | `22.84` | −1 235 | `-1.24` |
| 25 000 | `25.00` | −5 | `-0.01` |
| 5 | `0.01` | −4 | `0.00` (never `-0.00`) |
| 4 | `0.00` | −45 000 | `-45.00` |
| 0 | `0.00` | 130 000 | `130.00` |

### 13A.4 Static analysis

**CStyleCheck v1.5.1** (TB-STD-002 and TB-STY-001), over all 18 C files of
`firmware/pico_sht30` - sources, headers and host unit tests - with
`.cstylecheck.yml`, the Pico alias map and the Pico exclusions: **0 errors,
0 warnings, 0 info**, with no baseline (PICO-NFR-006). The first run found 210;
they were fixed in the code (enum member prefixes, `m_` statics, `g_` globals,
`U` suffixes, one non-ASCII character, and `cmd_execute` split under the
60-line limit) or covered by a documented alias or exclusion. That run was for
#104. CStyleCheck is not installed on the bench PC, so for #131 it has not been
run locally; the result is the CI job's (`.github/workflows/style.yml`).

No MISRA checker (for example cppcheck's MISRA addon, PC-lint, Helix QAC) was
available in the build environment. MISRA C:2012 conformance is therefore by
construction and review (`docs/pico_sht30/Pico_SHT30_Notes.md` §6) plus the
mechanical checks of `SWE4-UT-PICOFWPROTO` and CStyleCheck; a MISRA tool run is
PICO-OPEN-04.

### 13A.5 Bench confirmation items

| ID | Item |
|---|---|
| PICO-OPEN-01 | **Closed 2026-10-03** (§13A.7). Flash `pico_sht30.uf2`, confirm USB enumeration, and confirm `rd name`, `rd copyright`, `rd version` and `rd sha` return the name, copyright, `V1.00.0000` and the SHA the build injected. |
| PICO-OPEN-02 | **Confirmed in part 2026-10-03** (§13A.7): with no module connected, `rd temperature` answers `ACK rd temperature = Error` and `status` answers `err 4`. Still open: a value to two places with the DollaTek module on GP4/GP5 at 0x44. |
| PICO-OPEN-03 | Compare against a reference thermometer: expect agreement within ±0.2 °C typical between 0 and 65 °C, allowing for self-heating of the Pico. |
| PICO-OPEN-04 | The reference PDFs (Pico 2 datasheet and schematic, RP2350 datasheet, SDK guide, Sensirion SHT3x-DIS datasheet) could not be fetched in the build environment; run `docs/pico_sht30/fetch_datasheets.sh` and commit them. Run a MISRA C:2012 checker over `firmware/pico_sht30/src`. |
| PICO-OPEN-05 | Reflash a real Pico 2 with `benchtools thermo flash`: from the running thermometer (`bootsel`), from a board already in its bootloader, and through the 1200-baud reset; confirm the drive is found without `--drive`. **Closed 2026-10-03** on Windows 10: all three methods exited 0 with every check passing (§13A.7). Drive discovery on Linux and macOS is untested on hardware. With the `rd` firmware of #131, `flash -r COM14` (method `bootsel`) passed its `name`, `version` and `sha` checks (§13A.7). |
| PICO-OPEN-06 | **Confirmed in part 2026-10-03** (§13A.2, §13A.7): the `rd` command set (#131) on a real Pico 2. The #131 firmware was cross-compiled with no warnings, its size recorded, the SHA injected, and it was flashed; every `rd` option, the `NAK`, the `err` replies and `ecureset` behaved as specified. Still open: `rd temperature` with a real value to two places, which needs the SHT30-D module connected (PICO-OPEN-02). |

### 13A.6 Reflashing without BOOTSEL (`SWE4-UT-PICOFLASH`, #127)

`instruments/pico_sht30/test_flash.py`: **35 cases, all pass**. The whole Pico
SHT30 directory, `tests/instruments/pico_sht30`, is 140 cases, all passing, re-run
after #127 was merged into #131 (`python -m pytest tests/instruments/pico_sht30
-q`). Since that merge `flash` confirms the build by the `rd` command set
instead of `ver`: the image is recognised by the firmware's name, and its
version and commit SHA are read from it to compare with `rd version` and
`rd sha`. The ambiguous build-date case was replaced by an ambiguous-SHA case,
and a missing-version case was added. No Pico, drive or serial port is involved: every operating-system
interaction is a seam of `PicoFlasher`, and `SimulatedRp2350` plays the board.

| Area | What the cases establish |
|---|---|
| The image | A UF2 laid out as an SDK 2.x RP2350 build lays it out (an `absolute` block ahead of `rp2350-arm-s` blocks) is accepted; bad magic numbers, a length that is not whole blocks and a missing file are refused; an RP2040 image is refused; an image without the thermometer's name (`Pico 2 SHT30 Temperature Sensor`) is refused unless `--any-image`; an image with more than one commit SHA, or with no version string, is flashed but that point is not compared, and the result says so in a note. |
| Reaching the bootloader | From the running firmware (`bootsel`); from a board already in its bootloader, with no `bootsel` sent; and, when the port does not answer the protocol, through the 1200-baud reset. An error from the port during that reset is kept as a note in the result, not raised. |
| Confirming the result | The checks are `name`, `version` and `sha`, read by `rd`; the version is the image's unless `--expect-version` is given. A version that differs from `--expect-version`, and a commit SHA that differs from the image's (the old image still running), each give `ok: false` without raising; when no port was given, the one the port search returns is used (the search is simulated here: the USB vendor-ID filter itself runs only through pyserial, untested without a Pico); `--no-verify` is honoured. |
| Failures | Bootloader timeout; no drive and no port; two drives; a copy that fails while the drive remains; a drive that never goes away; a port that never comes back - each raises an error naming what happened. A close error after the drive has gone is not a failure. |
| Drive discovery | A drive is recognised by `INFO_UF2.TXT` naming `RP2350`; the search roots on Windows (the drive-letter list), Linux and macOS (with `glob` patched); any other system is refused with a request for `--drive`. Discovery has not been run against a real mounted RP2350 drive on any system. |
| Command line | `benchtools thermo -r sim:// flash` prints the JSON result and exits 0; a mismatch exits 1 with the JSON result; an error exits 1 with an `error:` message on stderr. |

**Confirmed on hardware on 2026-10-03** (PICO-OPEN-05, closed), with the
firmware of the time, which answered `ver`; the checks were then `title`,
`version` and `built`, on the bench
PC (Windows 10) with a real Pico 2, USB serial AC5483CD0798FB0B, enumerating
as COM14. The image was built on the bench PC from this branch with Pico SDK
2.1.1, Arm GNU Toolchain 14.2.Rel1 (14.2.1 20241119) and the prebuilt picotool
2.1.1 (x64-win): 60 416 bytes, 118 blocks, families `absolute` and
`rp2350-arm-s`.

| Route | Command | Result |
|---|---|---|
| Already in the bootloader | The board arrived in its bootloader as drive D: (`INFO_UF2.TXT` naming `Board-ID: RP2350`); `benchtools thermo -r "" flash pico_sht30.uf2 --expect-version 1.0.0` | `ok: true`, method `already-in-bootloader`; the port found by vendor ID as COM14; about 2.5 s end to end. `ver` afterwards matched the image's build date `2026-10-03T12:06:39Z`. |
| From the running thermometer | Rebuilt for a new build date, then `flash -r COM14 ... --expect-version 1.0.0` | `ok: true`, method `bootsel`; build date `12:06:39Z` → `12:07:19Z`; title, version and build checks all passed. |
| 1200-baud reset | The protocol open made to fail once, so that `flash -r COM14` falls back | `ok: true`, method `1200-baud`; title and build checks passed. |
| From the running thermometer, `rd` firmware (#131, after the merge) | `benchtools thermo -r COM14 flash pico_sht30.uf2`, image built from commit `5c80ae7` | `ok: true`, method `bootsel`; checks `name`, `version` (`V1.00.0000`, from the image) and `sha` (`5c80ae7`) all passed. |

The 1200-baud run found a fault, fixed in this branch. On Windows the Pico
reboots while pyserial is still configuring the port at 1200 baud, and pyserial
raises `SerialException` with `PermissionError(13, 'A device attached to the
system is not functioning.', None, 31)`. `touch_1200` raised that as a
`FlashError`, failing a reset that had worked. It now returns the error as a
note in the result, and success is decided by the bootloader drive appearing.
Two cases were added for it (`test_touch_1200_error_is_a_note_not_a_failure`,
`test_touch_1200_note_reaches_the_result`).

This confirms the SDK's 1200-baud reset in this firmware, which is an SDK
USB-serial build; it was not tried on any other firmware. Drive discovery was
confirmed on Windows and port discovery by vendor ID through pyserial; drive
discovery on Linux and macOS has not been tried on hardware. A Pico whose
firmware has crashed, or which does not enumerate on USB, still needs BOOTSEL
or an SWD probe.

### 13A.7 First run on a real Pico 2 (2026-10-03)

Bench PC on Windows 10, a Raspberry Pi Pico 2 with USB serial number
`AC5483CD0798FB0B` on COM14, and **no SHT30-D module connected**. The firmware
of §13A.2 was flashed with `benchtools thermo flash` (the `bootsel` method of
#127, §13A.6), with no button pressed. The raw replies on COM14 were:

| Sent | Reply | Expected? |
|---|---|---|
| `rd name` | `ACK rd name = Pico 2 SHT30 Temperature Sensor` | Yes |
| `rd copyright` | `ACK rd copyright = (c) 2026 Dermot Murphy` | Yes |
| `rd version` | `ACK rd version = V1.00.0000` | Yes |
| `rd sha` | `ACK rd sha = 5c80ae7` | Yes, the commit built |
| `rd temperature` | `ACK rd temperature = Error` | Yes, no sensor is connected |
| `rd colour` | `NAK rd colour = Error` | Yes |
| `rd` | `err 2 wrong number of arguments` | Yes |
| `ver`, `temp`, `reset` | `err 1 unknown command` | Yes, removed by #131 |
| `status` | `err 4 the sensor did not acknowledge` | Yes, no sensor is connected |

`benchtools thermo -r COM14 info`, and each `rd <option>` through the driver's
command line, returned the same values. `ecureset` through the driver rebooted
the Pico, and it came back answering `rd sha = 5c80ae7`. The raw `ok` reply to
`ecureset` was not captured separately.

After #127 was merged into this branch, `flash` confirms the build by `rd`
(§13A.6). `benchtools thermo -r COM14 flash pico_sht30.uf2`, with the same
image, reported `ok`, method `bootsel`, and its checks `name`, `version`
(`V1.00.0000`) and `sha` (`5c80ae7`) all passed.

## 13B. TTi 1604 multimeter verification results (#115)

No TTi 1604 was attached to the build environment (CON-10). The driver was
verified against its simulator, over pyserial's `loop://` - a real serial
object, which never signals end-of-message - and against frames built from the
manufacturer's remote-control note.

### 13B.1 The driver could not read a real serial port

Reproduced on `develop` @ `337ad10` before the fix, and fixed (D-43):

| Step, `develop` before #115 | Result |
|---|---|
| `SerialTransport("loop://").read_raw()` with 11 bytes waiting | `TransportTimeoutError` after the timeout; all 11 bytes left in the buffer |
| `Tti1604(SerialTransport("loop://")).initialise()` | `InstrumentError: the 1604 did not echo 'u' after 3 attempts … check that DTR is asserted` |
| The same, after #115 | Remote mode acknowledged; frames written to the port decode (`TestTheSerialLink`) |

The unit tests had passed throughout, because the mock transport signals
end-of-message after every reply and a serial port never does.

### 13B.2 What a key press now has to prove

| Condition | Result |
|---|---|
| Every `select_*`, through the simulator | Returns the reading that shows the change |
| A key the meter echoes but does not act on | `InstrumentError` naming the function and range the readings show |
| A key lost while every frame carries `0x66`, the Volts key's character | Resent; the echo is never taken from inside a frame |
| AC or DC on resistance | Refused before any key is sent |
| `select_auto_range` on a meter already auto-ranging | Nothing pressed (it used to toggle) |
| `set_range(400)`, `set_range(4e-3)` | Each step confirmed; a full scale the function lacks is refused with the list |
| `set_range(4000)` measuring frequency | Waits for the 10 s gate (≥ 10 s of virtual time) and confirms it |

### 13B.3 Decoding against the manufacturer's note

The note's worked example, `96 219 242 102 182` = `12.345`, decodes exactly.
Touch-Hold at bit 1 of the function byte and auto-range-set at bit 1 of the
status byte decode as the note gives them (D-44). The resistance multiplier is
derived, and reads 1 234.5 Ω from both `1.2345` and `1234.5` on the 4 kΩ range
and 1.2345 MΩ from both `1.2345` and `1234.5` on the 4 MΩ range; a display that
fits no multiplier carries no value.

### 13B.4 The bench test and the front-panel check

`tests/bench/tti1604` (SWE4-UT-DMMBENCH, outside the default run) was dry-run
against the simulator: 10 passed and 4 skipped (the reference tests) with no
reference, and with each of DC volts, resistance, DC current on each socket and
frequency named in turn the reference test ran and passed and the open-input
test stood aside. The front-panel check, `examples/12_dmm_front_panel_check.py`,
runs all twelve steps against the simulator and is itself unit-tested
(SWE4-UT-DMMPANEL). Neither has yet been run against a meter: that is
DMM-OPEN-01 … -08.

### 13B.5 Bench confirmation items

DMM-OPEN-01 … -08, `docs/dmm/TTi1604_Notes.md` §5. None blocks use of the
driver: each is accepted either way, refused rather than guessed, or confined
to a function the driver does not select.

## 14. Runner verification results

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
| Every shipped `specs/*.yaml` runs against `benches/simulated_bench.yaml`: 38 cases, all pass | Pass |
| A value saved by one step is usable by a later one, as an argument and as a limit | Pass |
| A reference to a name nothing has saved is an error, naming what has been saved | Pass |
| A limit stated as text compares as text, and the report shows the text | Pass |
| A value reported through a format reads as the part does, and the number stays in the record | Pass |

### 14.1 A chained test, run end to end

`specs/sensor_bringup.yaml` is the first test of a bench session and the first
shipped specification that is a **chain** rather than a list: what one step
establishes decides what the next one does.

| Step | Establishes | Used by |
|---|---|---|
| `psu.configure_channel`, `psu.read_channel` | the board is powered at 3.2 V and not in current limit | everything after it |
| `dongle.ensure_firmware` | the instrument that will measure the board is the build it should be | the radio steps |
| `probe.flash` | the image is on the part and verifies | — |
| `probe.image_build` | what the build system recorded about that image | the version comparison |
| `probe.read_u8`, `probe.read_integer` at UICR `CUSTOMER[0]` | that the identity record is valid, and which board this is - reported as `0A1B2C`, as it reads on the board | the scan and the selection |
| `probe.reset(halt=false)`, `probe.rtt_lines_within` | it started and is running | — |
| `dongle.scan`, `select`, `open_link` | that board, found over the air **by its own identifier** | the command |
| `dongle.command("rd version")` | what the running firmware says it is | compared with the manifest |

Run on the simulated bench, all seven cases pass and the record is marked
simulated. The run is not the interesting part, though: a specification that
passes whatever the bench does reads as evidence and is worse than none. So each
fact it claims to establish was broken in turn (`SWE4-UT-BRINGUP`):

| Broken | Result |
|---|---|
| The build manifest says 9.9.9, the board says 1.4.2 | **FAIL** on `reported_version`, with both versions in the record - not an error |
| The identity record is 0xFFFFFFFF (never programmed), or its validity byte is not zero | **FAIL** where it is read, rather than three steps later as "no sensor found" |
| The record is valid but the identifier is zero | **FAIL**: the scan would otherwise go looking for board 000000 |
| The board is started and says nothing on RTT | **FAIL** on a count of zero lines, rather than a timeout raised as an error |

The last three are the reason two of the steps are shaped as they are. Checking
the validity byte before reading the identifier, and bounding the identifier
itself, puts the failure where the fault is. Counting RTT lines rather than waiting for a pattern makes a silent board a
failed test rather than a broken bench, which is the distinction of RUN-FR-031
applied to a liveness check.

The manifests the simulated bench reads are fixtures, not build output, and
three tests assert they say what the simulators say - otherwise a simulated run
would fail for reasons that are about the fixture rather than about the
specification.

### 14.2 A command set tested against its own document

`specs/sensor_commands.md` is the sensor's command set written as a document -
a heading per test, a row per step - and `specs/sensor_commands.yaml` runs it.
The suite holds no commands: it powers the board, programs it, starts both logs,
finds the board by its identifier, and hands the document to the driver.

Run against the simulated sensor, the document produces 11 step results:

| | Steps | |
|---|---|---|
| Passed | 8 | a reply that matched what the document says |
| Failed | 0 | |
| Skipped | 3 | one delay, and two commands the document promises nothing for |

and the run passes, because no step failed. The report has the row the
specification asked for - test, step, command, response, expected response, the
exchange time, the result - with `measure` showing 0.10 s against the simulated
sensor's 95 ms, quoted at the 10 ms resolution the report states.

The interesting part is what the tests do to that. `SWE4-UT-BLESCRIPT` asserts
the shipped document parses **and passes**, so the worked example cannot rot;
twelve refusals, each naming the line, because a row read wrongly is a command
nobody tested and nobody missed; and three properties a report of this shape can
get quietly wrong:

- **A skipped step must never read as a passed one.** A document of delays
  passes while checking nothing, so a run reports skipped beside passed and
  failed, and `CommandScript.checks` says how many rows make a claim at all.
- **A step that promised a reply and got none must fail**, not be skipped as
  though nothing was asked. A step that promised nothing must be skipped whether
  or not something arrives.
- **The time must carry its clock.** The dongle's microsecond figure is what is
  measured and 10 ms is what is quoted; both are in the record (BLE-NFR-005).

### 14.3 Every shipped specification, from outside the checkout (#116)

Each of the 14 specifications in `specs/` was run with `benchtools run` from the
checkout and from an empty directory outside it, with `--simulate` and with
`--bench benches/simulated_bench.yaml --simulate`: 56 runs. Reproduced on
`develop` @ `69d76d7` before the fix (D-45):

| Specification | Mode | Inside, before and after | Outside, before | Outside, after |
|---|---|---|---|---|
| `radio_link.yaml` | `--simulate` | PASS 7 | ERROR: register file not found | PASS 7 |
| `sensor_commands.yaml` | `--simulate` | PASS 2 | ERROR: `specs/sensor_commands.md` not found | PASS 2 |
| `bench_self_check.yaml` | simulated bench | PASS 5 | ERROR 1 of 5: dongle build not found | PASS 5 |
| `dongle_firmware.yaml` | simulated bench | PASS 3 | ERROR 3 of 3: dongle build not found | PASS 3 |
| `radio_link.yaml` | simulated bench | PASS 7 | ERROR: register file not found | PASS 7 |
| `sensor_ble.yaml` | simulated bench | PASS 4 | ERROR: dongle build not found | PASS 4 |
| `sensor_bringup.yaml` | simulated bench | PASS 7 | ERROR 4 of 7: sensor and dongle builds not found | PASS 7 |
| `sensor_commands.yaml` | simulated bench | PASS 2 | ERROR: dongle build not found | PASS 2 |
| `sensor_power_signal_and_link.yaml` | simulated bench | PASS 5 | ERROR: dongle build not found | PASS 5 |
| `kepler_*.yaml` (4) | both | ERROR: `dongle.select` refused by the simulated dongle; `kepler_temperature.yaml` on the simulated bench: the bench has no `rtt` instrument | ERROR: register file not found (7 of 8 runs; the eighth as inside) | ERROR, as inside |
| the other 18 runs | both | unchanged | same as inside | same as inside |

After the fix all 56 runs give the same outcome inside and outside the
checkout, and no run inside it changed. The four Kepler specifications error in
both places on `dongle.select`, because the simulated dongle does not model a
Kepler sensor, and `kepler_temperature.yaml` cannot run on the simulated bench,
which defines no `rtt` instrument. Neither is a path fault, and both are outside
#116. The second was fixed by #120: the simulated bench now defines `rtt`, and
`kepler_temperature.yaml` gets past `rtt.rtt_start` and stops at `dongle.select`
as the other three do. The simulated Kepler sensor is #121 and #122. Before the fix they
errored outside the checkout one step earlier, on the register file, and that
step now succeeds. `--simulate` without a bench gives the dongle and probe no
firmware build, so `dongle_firmware.yaml`, `sensor_bringup.yaml` and
`sensor_power_signal_and_link.yaml` fail or error in that mode from either
directory, as before.

The comparison is held in the suite as
`test_a_shipped_specification_runs_the_same_from_outside_the_checkout`, one case
per specification on the simulated bench. Without the fix in `runner/` it fails
for 10 of the 14, along with 6 of the 7 other `test_input_paths.py` tests.

## 15. Defects found, and their disposition

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

| D-15 | `AdvertisingProfile.intervals` subtracted two floats, so an exactly nominal 100 ms interval came out as 0.09999999999999998 and failed a limit written as ">= 0.1" | **Major** (a conforming sensor failed by floating-point representation rather than by behaviour). Found by `test_a_conforming_sensor_is_within_specification`, whose last interval is exactly nominal | **Closed** — intervals are subtracted as integer microseconds and converted once | `test_exactly_nominal_intervals_are_exact`, `test_a_conforming_sensor_is_within_specification` |
| D-16 | An advertising capture was bounded by the host's wall clock, so against a simulator - whose clock advances as fast as it is read - a two second capture collected 430 seconds of events and overflowed the event backlog | Minor (simulation only; on hardware the two clocks agree). Found by reading the first profile the driver produced | **Closed** — `DongleSession.collect` takes a `stop` predicate, and the capture is bounded by the **dongle's** clock with the wall clock as a backstop | `test_collect_stops_early_when_asked`, `test_the_capture_covers_the_window_asked_for` |
| D-17 | `AdvertisingProfile.as_dict` was documented to survive a capture too short for statistics, but `expected_events` reached the interval arithmetic outside the guard and raised | Minor (a failing capture produced an exception instead of a report, which is when a report is most needed) | **Closed** — `expected_events` and `gaps` fall back when there is no interval to reason with | `test_as_dict_survives_too_few_events` |
| D-18 | The simulated dongle rolled an advertising event scheduled for the *current* instant forward by a whole interval, so whenever two sensors coincided the quieter one was never heard | Minor (**test double** defect; a scan silently found fewer sensors than it should) | **Closed** — only a schedule strictly in the past is rolled forward | `test_scan_finds_the_sensors`, `test_scanning_finds_sensors` |
| D-19 | The serial transport reported a write the far end would not take as a connection failure | Minor (diagnosis quality: it sends the reader to look at the cable when the port is fine and flow control is asserted) | **Closed** — reported as a timeout naming flow control | `test_a_write_the_far_end_will_not_take_is_a_timeout` |

| D-20 | `ble_scanner.h` declared functions taking `ble_evt_t` but included only `ble_gap.h`, which does not define it | Minor (would not compile) | **Closed** — includes `ble.h` | `compile_check.sh`: `ble_scanner.c` |
| D-21 | The scan filter policy was written `BLE_GAP_SCAN_FILTER_POLICY_ACCEPT_ALL`; no SoftDevice header has ever spelled it that way (`BLE_GAP_SCAN_FP_ACCEPT_ALL`) | Minor (would not compile) | **Closed** | `compile_check.sh`: `ble_scanner.c`, `nus_client.c` |
| D-22 | `command_list` declared a local `count` shadowing the parameter of the same name, left behind when the handlers were given a uniform signature | Minor (would not compile) | **Closed** — renamed to `found` | `compile_check.sh`: `cmd_parser.c` |
| D-23 | `tx_pump` called `CRITICAL_REGION_EXIT()` inside an early return. The SDK's macro pair opens and closes a *brace*, so the region was structurally unbalanced — and the intent, returning from inside a critical region, is wrong regardless | **Major** (would not compile; and the pattern, had it compiled, leaves interrupts disabled on one path) | **Closed** — the decision is taken inside the region and acted on outside it | `compile_check.sh`: `cdc_acm.c` |
| D-24 | `APP_USBD_STRINGS_USER` was defined as a string descriptor. It is an X-macro *list*, so the definition broke `app_usbd_string_desc.h` itself | Minor (would not compile; the error appeared inside an SDK header, several levels from the cause) | **Closed** — no user strings are declared | `compile_check.sh`: `cdc_acm.c` |
| D-25 | `sdk_config.h` defined `BLE_DB_DISCOVERY_BLE_OBSERVER_PRIO`; the SDK's header reads `BLE_DB_DISC_BLE_OBSERVER_PRIO` | Minor, and the worst kind of configuration error: **the wrong name compiles and does nothing**, so the module would have registered its observer at an unintended priority had the header not asserted | **Closed** | `compile_check.sh`: `main.c` |
| D-26 | SDK 17's `ble_nus_c` and `ble_db_discovery` submit GATT operations through a queue (`nrf_ble_gq`); the firmware created none and passed `NULL` | **Major** (would have compiled and then failed at run time, on the first characteristic discovery) | **Closed** — `main.c` owns one queue and hands it to both, per Nordic's own central examples | Found by the version delta, since SDK 15.2 has no queue at all; verified by inspection against the SDK 17 API |

Missing SES project entries were corrected with them: `nrf_sortlist.c` and
`nrf_atflags.c` (required by `app_timer` v2 and `ble_conn_state`), `nrf_ble_gq.c`,
and the include paths for `sortlist`, `atomic_flags`, `nrf_ble_gq` and
`ble_link_ctx_manager`.

| D-27 | An advertising line the transmit queue **refused** was still counted as reported, so the firmware's "reported" and "received" counters always agreed | **Major** (evidence integrity): the host compares those counters to tell a lossy link from a quiet sensor, and this made `AdvertisingProfile.is_complete` incapable of ever being false for a firmware-side drop | **Closed** — counted only when the queue accepts the line | `test_a_dropped_line_is_counted_as_not_reported` |
| D-28 | After an over-long command the receiver started a **new** line where the buffer overflowed, instead of discarding to the terminator. The tail of a truncated command therefore became a command: `xxx…xxxreset` would have executed `reset` | **Major** (a command nobody sent) | **Closed** — bytes are discarded until the terminator | `test_the_tail_of_an_over_long_command_is_not_a_command` |
| D-29 | The driver refused to connect to a dongle whose protocol version differed from its own. Since refreshing the firmware runs **over that connection**, an out-of-date dongle could not be reached to be fixed - the check made the recovery path impossible | **Major** (the fault excluded its own remedy) | **Closed** — only a *major* version difference is fatal, a minor one warns, and `update_firmware=True` suspends the check | `test_an_incompatible_dongle_can_still_be_reached_to_update_it`, `test_a_different_minor_version_is_survivable` |

Two smaller corrections came with them: `cmd_parser_init` now clears the
selection, so the module can be brought back to a known state (the target wants
that after a soft restart as much as the tests do); and the sources that use
`UNUSED_PARAMETER` now include `app_util_platform.h` rather than relying on the
SDK to provide it transitively.

| D-30 | The driver treated the supply's **global** output switch as the state of each channel. Connecting to a supply whose output was off therefore marked both channels off, after which `set_voltage` parked the value instead of sending it - and the supply was never programmed at all | **Major**: `configure_channel` then `output_on` would energise a rail at the *previous* setpoint, silently, and every subsequent reading would be consistent with it | **Closed** — a channel is parked if and only if the driver parked it; there is now one fact where there were two that could disagree | `test_configure_sets_the_limit_before_the_voltage`, `TestReset` (3), `test_it_can_be_turned_on` |
| D-31 | The simulated supply's command pattern allowed only a channel digit, so `OUT0` matched nothing and was silently refused. Every "switch off" in a simulated test appeared to succeed while the model stayed on | **Major** (in the test double, so the whole class of switching tests was vacuous — see the note on D-11 and D-12 below) | **Closed** — the digit position is parsed as a digit, and a channel that does not exist is refused explicitly rather than by failing to parse | `test_out0_is_understood`, `test_a_channel_that_does_not_exist_is_refused` |

| D-32 | The S2-LP driver read the firmware's ``{rssi:D4}`` tag as decimal. ST's firmware writes that tag with its ``%x`` specifier, so it carries **bare hex**: ``D4`` read as decimal is 4, and the driver reported -144 dBm for a signal at -40 dBm | **Major** (evidence integrity): a plausible number, wrong by 104 dB, in every received packet and in the packet log | **Closed** — tags the firmware writes in hex are read in hex, explicitly, by `Reply.hex_number` | `test_a_hex_tag_has_no_0x_in_front_of_it`, `test_the_rssi_is_the_one_the_board_reported` |
| D-33 | The reply parser's number pattern had no sign, so a negative value arrived positive. `S2LPQiGetRssidBm` answers in dBm: -110 dBm was read as +110 dBm | **Major**, and of the worst kind: the result is not merely wrong but physically impossible, and nothing downstream would have questioned it | **Closed** — the pattern accepts a leading minus, and the driver's RSSI test asserts the sign | `test_rssi_is_read_in_dbm`, `TestNumbers` |
| D-34 | A polled capture counted a re-arm per iteration with no bound on iterations. Against a radio that answers "nothing" immediately it spent the whole timeout re-arming - 35 006 times in two seconds - and reported that as a capture | **Minor** on hardware, where each arm blocks; **major** as a measurement claim, because the gap count is what tells a reader whether a capture was continuous | **Closed** — the polled path is bounded by an attempt count as well as by time, and reports `stopped_early` | `test_a_polled_capture_is_bounded_by_attempts` |

| D-35 | The simulated kit modelled the **SRES strobe as restoring register defaults**. ST's own command header calls it a "reset of all digital part, except SPI registers", and the driver's own docstring said so - but the simulator disagreed, and the test asserting `reset()` restored defaults passed against it | **Major** (in the test double, so the error was invisible): a driver using `reset()` to reach a known state would have passed every test here and left every register exactly as it was on the bench, with a configuration file then applied on top of an unknown state | **Closed** — SRES empties the FIFOs and leaves the register file; `SdkEvalSdn` (shutdown and back) is modelled as the power-on reset, which on the part is the only thing that restores defaults. `power_cycle()` added, and `apply_configuration(reset=...)` uses it | `test_the_reset_strobe_does_not_restore_register_defaults`, `test_the_reset_strobe_leaves_the_register_file_alone`, `test_a_power_cycle_does` |

| D-36 | The dongle's GATT queue was left at the SDK's default write size of 20 bytes while the host protocol sends commands up to `PROTO_MAX_PAYLOAD` (96). `nrf_ble_gq` refuses a longer write with `NRF_ERROR_DATA_SIZE` | **Major**, and invisible to every check that had been run: it compiles, links and passes the host-side tests, and fails only on the part, on any command over 20 bytes | **Closed** — `NRF_BLE_GQ_DATAPOOL_ELEMENT_SIZE` and `NRF_BLE_GQ_GATTC_WRITE_MAX_DATA_LEN` are taken from `protocol.h`, so the queue is sized from the protocol rather than alongside it | Structural: `sdk_config.h` includes `protocol.h`; the sizes cannot now disagree |
| D-37 | The Makefile's source list had never been exercised against a real SDK tree. It named `nrfx_power_clock.c`, which does not exist in nrfx 2.x, and omitted `nrf_section_iter.c`, `nrf_drv_power.c` and `utf.c`, which were on the include path but never compiled. Nordic's `Makefile.common` only **warns** about a source it cannot find | **Major**: the firmware could not be built as delivered — the first three faults are compile or link failures, and the warning meant the cause was in the middle of the output rather than at the end | **Closed** — the source list is corrected, and the Makefile now stops with the list of names it cannot find and what to check, rather than warning | The `firmware` workflow: a missing source is a hard error, so a recurrence cannot reach a green build |
| D-38 | `sdk_config.h`, written by hand, was missing seven keys the SDK's own modules expand into static assertions (`NRF_SORTLIST_CONFIG_LOG_ENABLED` and `_LOG_LEVEL`, `POWER_CONFIG_SOC_OBSERVER_PRIO`, `POWER_CONFIG_STATE_OBSERVER_PRIO`, the `APP_USBD_STRING_ID_*` and string descriptors, `NRF_SDH_BLE_GAP_DATA_LENGTH`) | **Major** as a build fault, and awkward to diagnose: the error surfaces in an unrelated SDK file, and `nrf_sortlist.h` needs its logging key present even with logging off because it expands the name through a **ternary in C code**, not through the preprocessor | **Closed** — every key is present, each with the comment saying which module asserts on it and why | The `firmware` workflow, which compiles every unit against the real SDK headers |

| D-39 | The simulated target modelled **reset-and-run as reset-and-halt**: `monitor reset 0` left the core halted and silent. Writing the bring-up specification is what found it - the board was started and never said anything | **Major in the model** (the class of D-31 and D-35): the simulator contradicted the thing it stands for, so "start the firmware and check it is running" could not be demonstrated, and any test of it would have been measuring the simulator | **Closed** — a reset with the run argument resets and then runs, emitting whatever the firmware emits along its flow, exactly as a resume does | `test_a_running_target_produces_lines`, `test_a_halted_target_produces_none`, `TestItPasses` |

| D-40 | `DEFAULT_SENSORS` is a module-level tuple of dataclasses holding mutable dicts, and every `SimulatedDongle` shared them. A test that changed one sensor's replies changed them for every simulator built afterwards | **Major in the test double**, and of the worst kind to diagnose: the tests it broke were in other files, and the failures described the sensor rather than the test that had altered it. Found by writing a test that silenced a sensor and watching six unrelated tests fail | **Closed** — a simulated dongle deep-copies the sensors it is given, so one simulator cannot poison another. The test that found it now models silence with a stub instead, which is the honest way to model a sensor the simulator does not have | `test_the_default_population_is_not_shared_between_simulators`, `TestASensorThatDoesNotAnswer` (4) |

| D-42 | `RttClient._pump()` runs on the background reader thread and on the caller's thread (from `read()` and `read_lines()`), and it called `self._backend.rtt_poll()` **before** taking `self._lock`. Two pumps could therefore poll at once. The simulator's drain is check-then-pop, and on Python 3.9 CI it raised `IndexError: pop from an empty deque` in `test_a_line_already_waiting_is_not_a_reading` (PR #105, run 36668656206) | **Minor on hardware**, where two polls at once could split one RTT line between two callers; **major as a test-suite fault**, because it failed an unrelated PR's CI intermittently and looked like a flake. Found by reading that failure to its cause instead of re-running it | **Closed** — the poll is now taken under the client's lock with the rest of the pump. A deterministic test replaces the scheduler's luck: a backend that detects overlapping polls, driven from four threads; it counted 99 overlaps before the fix and 0 after | `TestConcurrency.test_the_backend_is_never_polled_twice_at_once` |
| D-43 | The TTi 1604 driver read the link with `Transport.read_raw()`, which waits for an end-of-message that a serial port never signals. On a real port every read timed out with the received bytes left in the transport's buffer, so connecting always failed - and the error blamed DTR and RTS. The unit tests passed because the mock transport signals end-of-message after every reply | **Critical** - the driver could not talk to any real meter. Found by comparing it with the reverted #106 driver and reproduced over pyserial's `loop://` (#115) | **Closed** - `Transport.read_available()` and `discard_input()` (CORE-FR-061); the driver reads with a fixed short poll it never varies (LL-07) and loops to its own deadline. A virtual-clock simulator is now given the read timeout (CORE-FR-062), and the simulator keeps the meter's reading rate, so a wait shorter than the meter's fails in the tests. The frequency gate, which the old 2 s settling time could not wait for, is allowed for (DMM-FR-032) | `TestTheSerialLink` (2), `TestStreamReading` (7), `test_the_ten_second_gate_is_waited_for`, `test_a_read_shorter_than_the_measurement_times_out` |
| D-44 | Two annunciator bits were at the wrong positions: Touch-Hold at bit 0 of the function byte and auto-range-set at bit 2 of the status byte, from a summary, where the manufacturer's note gives bit 1 for both. A Touch-Hold display was not reported as held | **Major** - a frozen reading could pass as live. Found by reading the manufacturer's note, now in `docs/dmm/reference/` | **Closed** - both moved to bit 1 | `TestTheManufacturersNote` (4) |
| D-45 | Every driver opened an input file named by a relative path - an S2-LP register file, a command document, a firmware build, an ELF image - relative to the working directory, and nothing resolved it against the specification or bench file that named it. Started outside the TestTools checkout, the normal case, 12 of 28 specification runs on the simulated bench errored before measuring anything (§14.3) | **Major** - a test errored for a reason unrelated to the thing under test, and only in the directory it is meant to be used from. Every test passed because each was run from the checkout | **Closed** - drivers declare their input files; the runner and bench resolve them beside the declaring file, then the working directory, then the checkout (AD-27, #116) | `test_a_shipped_specification_runs_the_same_from_outside_the_checkout` (14), `TestStepArguments` (3), `TestBenchOptions` (4) |
| D-46 | On the BLE command line, `--select` with anything but the exact advertised name failed: the scan's firmware filter matched by containment, then `select()` matched the name exactly, found nothing and parsed the text as an address - "not a BLE address". `cmd --addr` was accepted and never read. Found on hardware with sensor 5C1712 during #73, ticketed as #124 | **Major** - the advertised name carries the firmware version, so the name an operator knows never matched; the only working form was an address | **Closed** - `select` and `--select` resolve an address, a name or part of one through `select_by_name`, with an unfiltered rescan for another case; `cmd --addr` selects; `--addr` with `--select` exits 2 | `TestChoosingASensor` (16; 13 fail before the fix) |
| D-47 | The event log named a record's source from a fixed table of driver packages. The Pico 2 thermometer was not in it, so its records read `bench`; the shared transports' lines read `bench` whatever instrument they carried; and two instruments of one driver - `probe` and `rtt` - were indistinguishable. Found in #126 | **Major** for a log whose purpose is to say which part of the bench did what: a supply's and a thermometer's lines could not be told apart, nor two J-Link links | **Closed** - each instrument carries a name, allocated by the specification and the bench, the specification winning, defaults per driver including `TEMP`; everything an instrument owns logs under it; clashes refused before connecting (AD-28) | `SWE4-UT-EVENTNAMES` (21), `TestPerInstrumentNames` (15), `TestSourceNames` (18) |

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
- **Unit tests found what compiling could not.** D-27 and D-28 both compile
  perfectly. One made a loss-detection counter incapable of detecting loss; the
  other would have executed the tail of a truncated command. Neither is visible
  by reading, and neither would have been found by a bench session that did not
  happen to overflow a buffer or a queue. This is the argument for testing
  firmware logic on a host: the cases that matter are the ones that are awkward
  to provoke on the part.
- **Compiling found in twenty minutes what review had not found at all.** Seven
  defects, five of which stop the build outright, in code that had been read
  carefully twice. Two are worth singling out: D-23, where the SDK's
  critical-region macros are a brace pair and cannot contain a `return` - a rule
  invisible unless you have read the macro or the compiler tells you; and D-26,
  where the code would have compiled and failed on the first GATT discovery,
  which is the failure a bench engineer would have spent an afternoon on. The
  lesson is not subtle: **source that has never been near a compiler should be
  described as such, and getting it to a compiler is worth real effort.**
- **The version gap was informative rather than an obstacle.** SDK 15.2 lacking
  the GATT queue is precisely what exposed D-26: the compiler's complaint that a
  member did not exist prompted the question of what it is *for* in SDK 17.
- **D-15 is the defect this element was most likely to produce**, and the least
  likely to be noticed: a sensor advertising exactly to specification, failed by
  a limit it meets, because of the last bit of a double. It was found by a test
  written to assert that *correct* behaviour passes - the case that is easy to
  leave untested, since a suite full of deliberately wrong inputs never
  exercises it.
- **D-18 is the same lesson as D-11 and D-12 in the previous revision**: a test
  double that is quietly wrong makes a real check vacuous. Here a scan found two
  sensors instead of three, and every test that asserted "the sensors I expect
  are present" still passed, because they asserted on the two.
- **D-14 was found by checking the traceability matrix against the suite** — the
  matrix cited three tests that did not exist, because a module had been written
  and traced but never tested. The consistency checks of §4.1 do not catch that
  (they check identifiers, not test names), so this one was a manual cross-check;
  it is worth repeating per release.

## 16. Verdict against the pass criteria

| ID | Criterion | Result |
|---|---|---|
| PC-1 | All tests pass | **Pass** — 2 558/2 558 run (1 skipped: `tests/tools/test_test_bench.py` needs `tkinter`, absent in the build environment), and 61/61 thermometer firmware cases (§13A.1) |
| PC-2 | Statement coverage ≥ 90% | **Pass** — 95% |
| PC-3 | Every requirement covered | **Pass** — see BENCHTOOLS-TRACE-001 |
| PC-4 | Injected skews recovered to < 0.1 sample interval | **Pass** — worst case 0.055 |
| PC-5 | Layering constraints hold | **Pass** |
| PC-6 | Work-product consistency checks hold | **Pass** |
| PC-7 | Every timing method recovers the injected 1.000 ms interval, except the host clock, which flags itself | **Pass** — §6.1 |
| PC-8 | No test requires a probe, target, debugger or GDB server | **Pass** — §1 |
| PC-9 | No module imports a third-party package at module level | **Pass** — §4.2 |
| PC-10 | Firmware and driver agree; firmware hygiene holds | **Pass** — §4.3 |
| PC-12 | Firmware unit tests pass; the firmware still compiles | **Pass** — §4.4, §4.5 |
| PC-11 | A simulated 100 ms sensor reads as 105 ms mean, 10 ms spread; a sensor that skips beacons is reported as missing them | **Pass** — §7.1 |

**Overall verdict: PASS**, subject to the bench confirmation items that cannot be
discharged without physical hardware:

- the VISA determination report §5.1, for the oscilloscope;
- `docs/jlink/JLink_Integration_Notes.md` §4, for the probe (JLINK-OPEN-01 to
  -04, of which the SWO timestamp scaling is the one that could change a
  reported figure);
- `docs/dmm/TTi1604_Notes.md` §5, for the multimeter (DMM-OPEN-01 … -08), by
  running `tests/bench/tti1604` and the front-panel check with a meter attached;
- `docs/ble/BLE_Dongle_Notes.md` §5, for the dongle. The firmware now has unit
  tests (§4.4), **compiles** against real SDK headers (§4.5) and **builds,
  links and packages** against nRF5 SDK 17.1.0 in CI (§4.6), which is a
  materially stronger position than this report's first issue described. The
  verdict covers the host driver, the protocol agreement, the firmware's
  source-level rules, its compilation and its link. It does not cover behaviour
  on silicon: nothing here has run on a dongle, which BLE-OPEN-02 to -04 exist
  to establish.

## 17. Supplementary checks performed

| Check | Result |
|---|---|
| `examples/01_capture_and_plot.py` | Runs; produces CSV, plot and hardcopy |
| `examples/02_channel_spread.py` | Runs; host-side skews match instrument-side delay on all pairs |
| `examples/03_period_and_jitter.py` | Runs; host and instrument period agree |
| `examples/04_run_bench_suite.py` | Runs; drives the shipped specification and writes a markdown report |
| `examples/05_jlink_firmware.py` | Runs against the simulated probe; flashes, verifies, reads RTT, variables and the call stack, and reports all four timing methods |
| `examples/06_ble_sensor.py` | Runs against the simulated dongle; scans, profiles advertising, connects and times replies on both clocks |
| `benchtools run specs/clock_skew.yaml --simulate` | 5 tests, all pass |
| `benchtools run specs/firmware_timing.yaml --simulate` | 6 tests, all pass in 1.01 s |
| The same against `benches/simulated.yaml --markdown` | Report written; FW-REQ-010/011/020/021 all pass, and the run is disclosed as simulated |
| The same against a bench whose `probe` alias is an oscilloscope | Exits 1 with `ERROR`: "the specification wants instrument 'probe' to be a JLinkProbe, but bench 'wrong' provides a Tek3014B" |
| `benchtools jlink info --resource sim://` and every other sub-command | All run; JSON on stdout |
| `benchtools run specs/sensor_ble.yaml --simulate` | 4 tests, all pass; measured 105 ms mean interval, 0 missed, 95 ms response |
| `benchtools ble --resource sim://` with every sub-command | All run; JSON on stdout, session log written |
| The same with a deliberately tightened limit | Exits 1, names the failing measurement and by how much |
| `benchtools` sub-commands `run`, `scope`, `drivers`, `backends` | All run |
| `python -m benchtools` | Runs |
| `benchtools` console script after `pip install -e .` | Installs and runs |
| Full suite with `matplotlib`, `pyvisa`, `pyyaml` and `pyserial` blocked | 1 807 passed, 40 skipped, 0 failed |
| `firmware/nordic_dongle/scripts/compile_check.sh` in `canembed/canembed-arm` | All six firmware units compile, 0 warnings, apart from four listed SDK 17-only lines (§4.5) |
| `ctest --test-dir build/firmware-tests` | 5 binaries, 131 cases, all pass in 0.01 s |
| `make SDK_ROOT=…` against SDK 15.2 | Drives a real build to the compile stage; stops only on files SDK 15.2 places elsewhere or lacks, which is the expected result for an SDK 17 project |
| Import with those extras blocked | Package imports; only the plot, VISA and YAML paths raise, each naming its extra |

---

## 18. Review & Approval

| Role | Name | Signature / Electronic Approval | Date |
|---|---|---|---|
| Author | Claude | Approved | 2026-09-19 |
| Technical Reviewer | Dermot Murphy | — | *pending* |
| Quality Assurance | Dermot Murphy | — | *pending* |
| Approver | Dermot Murphy | — | *pending* |

> **Note:** This document is under configuration management (SUP.8). Post-approval changes require a change request (SUP.10) and a new document version.
