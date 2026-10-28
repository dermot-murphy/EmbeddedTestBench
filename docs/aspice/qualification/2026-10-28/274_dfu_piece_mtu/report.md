# Bench test report: ETB 274 - DFU piece size and ATT MTU on 5C1712, both bootloaders

| Field | Value |
|---|---|
| Result | **PASS** |
| Bench | Bench PC (Windows) |
| Specification | dfu_piece_mtu_5C1712.yaml |
| Parameters | att_mtu = 23, backup_bl_version_address = 1040396, backup_hex = U:/Temp/claude/U--GitHub-EmbeddedTestBench/3e11e252-0b63-4702-9e7c-925fb3f7f509/scratchpad/bench274/backup_5C1712_full.hex, boot_s = 15.0, connect_s = 60.0, dfu_target = KAPPA_5C1712, id_address = 268439680, piece = 20, reply_timeout_s = 45.0, scan_s = 20.0, sensor_address = D1:8D:3B:4C:19:96, settings_bl_version_address = 1044492, step_1_package = U:/PrivateWork/Sensoteq/Kepler/innovateuk-sensor/software/output/legacy_images/candidate/KAPPAX_Release_BL_V2.00.0000_UPGRADE_OTA.zip, step_2_package = U:/PrivateWork/Sensoteq/Kepler/innovateuk-sensor/software/output/legacy_images/candidate/KAPPAX_APP_SDK17_PCB_V4X_RELEASE_OTA.zip, step_timeout_s = 180.0, v10_00_hex = U:/PrivateWork/Sensoteq/Kepler/innovateuk-sensor/software/output/legacy_images/V10.00.0000/KAPPAX_PCB_V4X_Production_V10.00.0000-plus-bl-and-softdevice.hex |
| Started | 2026-10-28T16:06:23+00:00 |
| Duration | 341.30 s |
| Tests | 2 passed, 0 failed, 0 errored, 0 skipped (of 2) |

## Instruments

| Alias | Event | Driver | Model | Firmware | Resource |
|---|---|---|---|---|---|
| dongle | BLE | NordicDongle | PCA10059 | 1.8.0 (built 2026-10-28T15:43:31Z) | COM10 |
| probe | JLINK | JLinkProbe | J-Link | J-Link ARM V8 compiled Nov 28 2014 13:44:46 | jlink:// |

## Requirements verified

| Requirement | Result |
|---|---|
| BLE-FR-121 | PASS |

## All tests

### Both bootloaders report their ATT MTU and piece size

Result: **PASS** | Requirement: BLE-FR-121 | Duration: 231.096 s

| Measurement | Value | Limit | Result |
|---|---|---|---|
| on_v10_00_0000 | ACK RD VERSION = V10.00.0000 | = "ACK RD VERSION = V10.00.0000" | PASS |
| session_swdl | ACK SESSION SWDL | = "ACK SESSION SWDL" | PASS |
| step_1_success | Success | = "Success" | PASS |
| step_1_done | done | = "done" | PASS |
| bl_v1_01_att_mtu | 23 | = 23 | PASS |
| bl_v1_01_piece | 20 | = 20 | PASS |
| step_2_success | Success | = "Success" | PASS |
| step_2_done | done | = "done" | PASS |
| bl_v2_00_att_mtu | 23 | = 23 | PASS |
| bl_v2_00_piece | 20 | = 20 | PASS |
| bootloader_now_v2 | ACK rd version-dfu = V2.00.0000 | = "ACK rd version-dfu = V2.00.0000" | PASS |

### Restore 5C1712 from its backup

Result: **PASS** | Duration: 56.883 s

| Measurement | Value | Limit | Result |
|---|---|---|---|
| backup_verified | 1 | = 1 | PASS |
| uicr_kept_after_restore | 1 | = 1 | PASS |
| sensor_id_word_after_restore | 3.03521e+08 | = 3.03521e+08 | PASS |
| restored_version | ACK rd version = V11.02.0000-286-GD01F2A1B0 | = "ACK rd version = V11.02.0000-286-gd01f2a1b0", ignoring case | PASS |
| restored_id | ACK rd id = 0x5C1712 | = "ACK rd id = 0x5C1712", ignoring case | PASS |

