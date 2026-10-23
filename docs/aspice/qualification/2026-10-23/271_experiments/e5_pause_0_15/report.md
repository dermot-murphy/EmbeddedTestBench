# Bench test report: ETB 271 experiments - SoftDevice and bootloader package to bootloader V1.01.0000

| Field | Value |
|---|---|
| Result | **PASS** |
| Bench | Kepler bench (5C1712) |
| Specification | U:/GitHub/EmbeddedTestBench/docs/aspice/qualification/2026-10-23/271_experiments/exp_271.yaml |
| Parameters | backup_bl_version_address = 1040396, boot_s = 15.0, bootloader_idle_s = 45.0, connect_s = 60.0, debug_hex = U:/PrivateWork/Sensoteq/Kepler/innovateuk-sensor/software/output/KAPPAX_APP_SDK17_PCB_V4X_DEBUG/package/KAPPAX_APP_SDK17_PCB_V4X_DEBUG-plus-bl-and-softdevice.hex, dfu_target = KAPPA_5C1712, id_address = 268439680, id_word = 303520768, off_channel = 1, off_max_v = 0.05, refused_timeout_s = 60.0, reply_timeout_s = 45.0, scan_s = 20.0, sensor_address = D1:8D:3B:4C:19:96, sensor_id = 5C1712, settings_bl_version_address = 1044492, step_1_package = U:/PrivateWork/Sensoteq/Kepler/innovateuk-sensor/software/output/legacy_images/candidate/KAPPAX_Release_BL_V2.00.0000_UPGRADE_OTA.zip, step_1_timeout_s = 180.0, step_2_package = U:/PrivateWork/Sensoteq/Kepler/innovateuk-sensor/software/output/legacy_images/candidate/KAPPAX_APP_SDK17_PCB_V4X_RELEASE_OTA.zip, step_2_timeout_s = 180.0, supply_channel = 2, supply_v = 3.3, two_frame_window_s = 2.0, v10_00_hex = U:/PrivateWork/Sensoteq/Kepler/innovateuk-sensor/software/output/legacy_images/V10.00.0000/KAPPAX_PCB_V4X_Production_V10.00.0000-plus-bl-and-softdevice.hex, v5_package = U:/PrivateWork/Sensoteq/Kepler/innovateuk-sensor/software/output/KAPPAX_APP_SDK17_PCB_V5_DEBUG/package/KAPPAX_APP_SDK17_PCB_V5_DEBUG_OTA.zip |
| Selected tests | E5 pause 0.15 s after each data create, Restore 5C1712 - sensor ID, DEBUG image, NORMAL mode, FACTORY |
| Started | 2026-10-23T16:57:30+00:00 |
| Duration | 204.47 s |
| Tests | 2 passed, 0 failed, 0 errored, 4 skipped (of 6) |

## Instruments

| Alias | Event | Driver | Model | Firmware | Resource |
|---|---|---|---|---|---|
| dongle | BLE | NordicDongle | PCA10059 | 1.7.0 (built 2026-10-23T10:55:19Z) | COM10 |
| probe | JLINK | JLinkProbe | J-Link | J-Link ARM V8 compiled Nov 28 2014 13:44:46 | jlink:// |
| psu | PSU | Gpd3303D | GPD-3303D | V1.09 | COM11 |

## All tests

### E1 pause 0.5 s after each data create

Result: **SKIP** | Duration: 0.000 s

Skipped: not selected

### E2 receipt every 2 pieces

Result: **SKIP** | Duration: 0.000 s

Skipped: not selected

### E3 pause 0.5 s and receipt every 2 pieces

Result: **SKIP** | Duration: 0.000 s

Skipped: not selected

### E4 pause 2 s after each data create

Result: **SKIP** | Duration: 0.000 s

Skipped: not selected

### E5 pause 0.15 s after each data create

Result: **PASS** | Duration: 61.928 s

| Measurement | Value | Limit | Result |
|---|---|---|---|
| sd_bl_package_result | Success | = "Success" | PASS |

### Restore 5C1712 - sensor ID, DEBUG image, NORMAL mode, FACTORY

Result: **PASS** | Duration: 72.522 s

| Measurement | Value | Limit | Result |
|---|---|---|---|
| debug_image_verified | 1 | = 1 | PASS |
| uicr_kept_after_restore | 1 | = 1 | PASS |
| sensor_id_word_kept_after_restore | 3.03521e+08 | = 3.03521e+08 | PASS |
| teardown_mode_normal | ACK wr mode NORMAL | = "ACK wr mode NORMAL" | PASS |
| teardown_factory | ACK routine config = FACTORY | = "ACK routine config = FACTORY" | PASS |
| teardown_rd_id | ACK rd id = 0x5C1712 | = "ACK rd id = 0x5C1712" | PASS |

