# #325: Kepler's bench specifications on `develop` a274967, on the bench

The run was from 2026-11-15 to 2026-11-16, on the bench PC, against Kepler
sensor 5C1712 on Kepler firmware **V11.03.0000**. It is the regression run for
release `v0.03.0000` (ETB-SVD-001 §6). It repeats the TX-1266 automated set
that Kepler ran on 2026-11-05 on `v0.02.0002`, the baseline. Only the bench
software and the dongle firmware changed between the two runs.

The run's folders are Sensoteq's and are not in this repository. They are in
innovateuk-sensor, under
`software/output/bench_runs/2026-11-15_etb_develop_a274967/`. The baseline is
`.../2026-11-05_0fbb3f85_master/`. This file is the record of what ran and
what it showed.

## Set-up

| Item | This run | Baseline |
|---|---|---|
| Embedded Test Bench | `develop` at a274967 (0.02.0002 plus the work released as 0.03.0000), installed in its own virtual environment | `v0.02.0002` |
| BLE dongle | PCA10059 on COM10, firmware 1.8.0 (protocol 1.8) | Firmware 1.7.0 |
| Kepler specifications | innovateuk-sensor at b1276eba, on Kepler's branch `feature/TX-1269-re-pin-kepler-bench-tests-to-next-etb-release`, in a frozen clone, so edits made to Kepler during the run did not affect it | Kepler `master` at 0fbb3f85 |
| Sensor under test | 5C1712 (BLE D1:8D:3B:4C:19:96), V11.03.0000 V4X DEBUG, flashed by J-Link after a flash and UICR backup | The same sensor and image |
| Test gateway | 5C4EE7 (C9:91:37:E4:C7:36), in TEST mode between specifications | The same |
| Other instruments | GPD-3303D on COM11 (channel 2 at 3.3 V, independent mode); S2-LP kit on COM4; J-Link OB S/N 682395790 | The same |
| Other sensors on air | V10 and V11 sensors, including 5C1705, 5C168B, 5C1805, 5C314E and 5BD456 | Not recorded |

The ticket scripts (`run_bench.sh`) name the `v0.02.0002` install and Kepler's
`bench_kepler.yaml`, which pins dongle firmware 1.7.0. Copies that name this
install and a bench file pinned to 1.8.0 were run instead. The copies are kept
in the run folder's `_scripts/`. The originals were not changed.

## Result

There are 66 run folders: specifications, ticket scripts and session scripts,
in parts A, D, G, I, J and B (unattended) and E and F (attended, with the
J-Link unplugged for part F's 2.9 V case).

| Outcome | Folders |
|---|---|
| Same verdict as the baseline | 60 |
| Better than the baseline | 4: `t_tx_1047_roping_mode_commands` and `r_tx_1047_roping_mode_commands` (PASS 4/0, baseline FAIL 3/1); `s_release_roping` (PASS 10/0, baseline ERROR); `g_frame_values` (PASS 4/0, baseline FAIL 3/1) |
| Worse than the baseline, explained | 2: see below |

The overnight soak (`k_overnight_soak`, 46 904 s) passed, 2 of 2, including
OT-D-26 (a VERSION frame every 12 hours). The power-cycle soak
(`p_power_cycle_soak`) passed, 4 of 4.

**`q_release_quick`: ERROR, 23 passed, 1 failed, 2 errored (baseline: FAIL,
25 passed, 1 failed).**
- OT-D-08 fails in both runs: Kepler's TX-1267.
- The two errors followed a watchdog reset of the sensor at 2026-11-15T18:52:04Z.
  - It happened during case "OT-E-04 read-back, OT-F-08 sync handshake with no
    gateway, OT-F-14 no ALIVE during SYNC", 31 s after a second
    `ROUTINE SYNC START`, with no gateway answering.
  - The sensor's BLE link dropped (reason 0x08), and the next commands were
    refused with `not connected`. The bench reported this correctly.
- The case and its neighbours were run again on 2026-11-16 (`q2_sync_rerun`).
  Its own verdict is **FAIL, 3 passed, 2 failed, 21 skipped**. The SYNC checks
  (OT-F-08, OT-F-14) passed with no reset. The two failures are Kepler test
  limits, not SYNC and not the bench:
  - V10-E-06 read 2840 mV at 3.1 V (limit 2950 to 3150 mV). The J-Link was
    unplugged for the re-run; with it fitted the main run read 3100 mV.
  - OT-E-04: the 64-pair preamble is written by an earlier case that the
    re-run skipped, so the boot frames carried 32 pairs and the read-back was
    `32 Pairs`. That read-back check fails the SYNC case.
  Both were sent to Kepler's TX-1269 session as test changes.
- It is a sensor firmware fault and not a bench defect. It was told to
  Kepler's TX-1269 session; TX-1269 is the re-pin ticket, so the fault
  needs a Kepler bug of its own to stay open after the re-pin closes. None
  has been raised yet.

**`s_release_legacy_ota`: ERROR in V10-F-01b (baseline: PASS 3/0).**
- The V5 DEBUG OTA package the case sends was not in the frozen clone, because
  a build without the DFU signing key makes none.
- Run again with the shared output's V5 DEBUG OTA package
  (`s2_release_legacy_ota`), it passed, 3 of 3. The bootloader refused the
  package with HwVersionFailure and kept the application, as the case requires.

**Deprecation warnings (#238).** Kepler's specifications still use
`s2lp.kepler_frame`, `s2lp.kepler_samples` and
`configs/s2lp_kepler_433_rx.regs`. All of them loaded through the plugin
interface with the deprecation warning, as #325 requires of this release.

## Sensor resets in the RF logs

Every frame the S2-LP kit received in the run was decoded. For 5C1712, each
VERSION frame sent at boot (ticks 1 or 2) and each fall in the ticks-since-reset
field was matched against the step that came before it.

| Finding | Count |
|---|---|
| Boot VERSION frames after a reset command, a power cycle, a J-Link flash or an OTA | 30 in the main parts, 3 in parts E and F, 2 in the SYNC re-run |
| Watchdog and soft resets right after each OTA of the candidate in `s_release_ota` | 3; the baseline has the same three |
| Fall in the ticks field without a VERSION frame | 1, after `ECURESET HARD`, when the receiver was not listening at the reboot |
| Periodic VERSION frame (OT-D-26, ticks 961, no reset) | 1, in the overnight soak |
| **Unexpected reset** | **1**: the watchdog reset at 2026-11-15T18:52:04Z above |

## Remaining limits

- One unattended run, with one sensor and one firmware version.
- `legacy_power.yaml` was not run: it needs a relay board and a PPK2 on the
  bench (TX-1079, #245).
