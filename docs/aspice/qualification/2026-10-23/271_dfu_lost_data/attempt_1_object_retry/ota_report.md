# Bench test report: BT-003 legacy upgrade - V10.00.0000 to the candidate over the air

| Field | Value |
|---|---|
| Result | **FAIL** |
| Bench | Kepler bench (5C1712) |
| Specification | U:/PrivateWork/Sensoteq/Kepler/innovateuk-sensor/software/test/bench/release_since_v10_00_0000/release_legacy_ota.yaml |
| Parameters | backup_bl_version_address = 1040396, boot_s = 15.0, bootloader_idle_s = 45.0, connect_s = 60.0, debug_hex = ../../../output/KAPPAX_APP_SDK17_PCB_V4X_DEBUG/package/KAPPAX_APP_SDK17_PCB_V4X_DEBUG-plus-bl-and-softdevice.hex, dfu_target = KAPPA_5C1712, id_address = 268439680, id_word = 303520768, off_channel = 1, off_max_v = 0.05, refused_timeout_s = 60.0, reply_timeout_s = 45.0, scan_s = 20.0, sensor_address = D1:8D:3B:4C:19:96, sensor_id = 5C1712, settings_bl_version_address = 1044492, step_1_package = ../../../output/legacy_images/candidate/KAPPAX_Release_BL_V2.00.0000_UPGRADE_OTA.zip, step_1_timeout_s = 180.0, step_2_package = ../../../output/legacy_images/candidate/KAPPAX_APP_SDK17_PCB_V4X_RELEASE_OTA.zip, step_2_timeout_s = 180.0, supply_channel = 2, supply_v = 3.3, two_frame_window_s = 2.0, v10_00_hex = ../../../output/legacy_images/V10.00.0000/KAPPAX_PCB_V4X_Production_V10.00.0000-plus-bl-and-softdevice.hex, v5_package = ../../../output/KAPPAX_APP_SDK17_PCB_V5_DEBUG/package/KAPPAX_APP_SDK17_PCB_V5_DEBUG_OTA.zip |
| Started | 2026-10-23T16:17:45+00:00 |
| Duration | 314.11 s |
| Tests | 1 passed, 2 failed, 0 errored, 0 skipped (of 3) |

## Instruments

| Alias | Event | Driver | Model | Firmware | Resource |
|---|---|---|---|---|---|
| dongle | BLE | NordicDongle | PCA10059 | 1.7.0 (built 2026-10-23T10:55:19Z) | COM10 |
| probe | JLINK | JLinkProbe | J-Link | J-Link ARM V8 compiled Nov 28 2014 13:44:46 | jlink:// |
| psu | PSU | Gpd3303D | GPD-3303D | V1.09 | COM11 |

## Requirements verified

| Requirement | Result |
|---|---|
| V10-F-01 | **FAIL** |

## Problems

### V10-F-01 Field upgrade V10.00.0000 to the candidate over the air - FAIL

- `v10_f_01_step_1_bootloader` = InvalidObject, limit = "Success" - "InvalidObject" != required "Success"
- `v10_f_01_step_1_done` = firmware, limit = "done" - "firmware" != required "done"
- `v10_f_01_step_2_application` = InvalidObject, limit = "Success" - "InvalidObject" != required "Success"
- `v10_f_01_step_2_done` = init, limit = "done" - "init" != required "done"
- `v10_f_01_rd_id_unchanged` = ACK RD ID = 0x5C1712, limit = "ACK rd id = 0x5C1712" - "ACK RD ID = 0x5C1712" != required "ACK rd id = 0x5C1712"
- `v10_f_01_mode_normal` = ACK RD MODE = NORMAL, limit = "ACK rd mode = NORMAL" - "ACK RD MODE = NORMAL" != required "ACK rd mode = NORMAL"
- `v10_f_01_bootloader_v2` = NACK Invalid Command, limit = "ACK rd version-dfu = V2.00.0000" - "NACK Invalid Command" != required "ACK rd version-dfu = V2.00.0000"
- `v10_f_01_config_factory` = ACK RD CONFIG = Custom, limit = "ACK rd config = FACTORY" - "ACK RD CONFIG = Custom" != required "ACK rd config = FACTORY"
- `v10_f_01_twfa_scaling_factory` = ACK RD TWFA-SCALING = 16 g, limit = "ACK rd twfa-scaling = AUTO" - "ACK RD TWFA-SCALING = 16 g" != required "ACK rd twfa-scaling = AUTO"
- `v10_f_01_twfb_scaling_factory` = ACK RD TWFB-SCALING = 32 g, limit = "ACK rd twfb-scaling = AUTO" - "ACK RD TWFB-SCALING = 32 g" != required "ACK rd twfb-scaling = AUTO"
- `v10_f_01_detect_method_factory` = ACK RD DETECT-METHOD = ACCRMS, limit = "ACK rd detect-method = ACCWAVE" - "ACK RD DETECT-METHOD = ACCRMS" != required "ACK rd detect-method = ACCWAVE"
- `v10_f_01_detect_period_factory` = ACK RD DETECT-PERIOD = 100 Secs/Tick, limit = "ACK rd detect-period = 45 Sec/Tick" - "ACK RD DETECT-PERIOD = 100 Secs/Tick" != required "ACK rd detect-period = 45 Sec/Tick"
- `v10_f_01_detect_velrss_factory` = NACK Invalid Command, limit = "ACK rd detect-velrss = 20 mm/s" - "NACK Invalid Command" != required "ACK rd detect-velrss = 20 mm/s"
- `v10_f_01_rms_odr_factory` = NACK Invalid Command, limit = "ACK rd rms-odr = 6400 Hz" - "NACK Invalid Command" != required "ACK rd rms-odr = 6400 Hz"
- `v10_f_01_rms_samples_factory` = NACK Invalid Command, limit = "ACK rd rms-samples = 1024 Samples" - "NACK Invalid Command" != required "ACK rd rms-samples = 1024 Samples"
- `v10_f_01_rms_fmin_factory` = NACK Invalid Command, limit = "ACK rd rms-fmin = 7 Hz" - "NACK Invalid Command" != required "ACK rd rms-fmin = 7 Hz"
- `v10_f_01_battery_time_factory` = NACK Invalid Command, limit = "ACK rd battery-time = 50 mSec" - "NACK Invalid Command" != required "ACK rd battery-time = 50 mSec"

### V10-F-01b A package for another PCB is refused and the unit keeps its application - FAIL

- `v10_f_01b_session_swdl` = ACK SESSION SWDL, limit = "ACK session swdl" - "ACK SESSION SWDL" != required "ACK session swdl"
- `v10_f_01b_v5_refused` = InvalidObject, limit = "ExtendedError" - "InvalidObject" != required "ExtendedError"
- `v10_f_01b_v5_hw_version` = , limit = "HwVersionFailure" - "" != required "HwVersionFailure"
- `v10_f_01b_rd_id_unchanged` = ACK RD ID = 0x5C1712, limit = "ACK rd id = 0x5C1712" - "ACK RD ID = 0x5C1712" != required "ACK rd id = 0x5C1712"
- `v10_f_01b_bootloader_v2` = NACK Invalid Command, limit = "ACK rd version-dfu = V2.00.0000" - "NACK Invalid Command" != required "ACK rd version-dfu = V2.00.0000"

## All tests

### V10-F-01 Field upgrade V10.00.0000 to the candidate over the air

Result: **FAIL** | Requirement: V10-F-01 | Duration: 64.131 s

| Measurement | Value | Limit | Result |
|---|---|---|---|
| v10_f_01_v10_version | ACK RD VERSION = V10.00.0000 | = "ACK RD VERSION = V10.00.0000" | PASS |
| v10_f_01_v10_factory_start | ACK ROUTINE CONFIG = START | = "ACK ROUTINE CONFIG = START" | PASS |
| v10_f_01_v10_factory_two_frames | 2 | = 2 | PASS |
| v10_f_01_v10_wr_twfa_scaling | ACK WR 16 | = "ACK WR 16" | PASS |
| v10_f_01_v10_wr_twfb_scaling | ACK WR 32 | = "ACK WR 32" | PASS |
| v10_f_01_v10_wr_detect_method | ACK WR ACCRMS | = "ACK WR ACCRMS" | PASS |
| v10_f_01_v10_wr_detect_period | ACK WR 100 | = "ACK WR 100" | PASS |
| v10_f_01_v10_twfa_scaling_16 | ACK RD TWFA-SCALING = 16 g | = "ACK RD TWFA-SCALING = 16 g" | PASS |
| v10_f_01_v10_twfb_scaling_32 | ACK RD TWFB-SCALING = 32 g | = "ACK RD TWFB-SCALING = 32 g" | PASS |
| v10_f_01_v10_detect_method_accrms | ACK RD DETECT-METHOD = ACCRMS | = "ACK RD DETECT-METHOD = ACCRMS" | PASS |
| v10_f_01_v10_detect_period_100 | ACK RD DETECT-PERIOD = 100 Secs/Tick | = "ACK RD DETECT-PERIOD = 100 Secs/Tick" | PASS |
| v10_f_01_v10_rd_id | ACK RD ID = 0x5C1712 | = "ACK RD ID = 0x5C1712" | PASS |
| v10_f_01_v10_mode_normal | ACK RD MODE = NORMAL | = "ACK RD MODE = NORMAL" | PASS |
| v10_f_01_v10_session_swdl | ACK SESSION SWDL | = "ACK SESSION SWDL" | PASS |
| v10_f_01_step_1_bootloader | InvalidObject | = "Success" | **FAIL** |
| v10_f_01_step_1_done | firmware | = "done" | **FAIL** |
| v10_f_01_step_2_application | InvalidObject | = "Success" | **FAIL** |
| v10_f_01_step_2_done | init | = "done" | **FAIL** |
| v10_f_01_rd_id_unchanged | ACK RD ID = 0x5C1712 | = "ACK rd id = 0x5C1712" | **FAIL** |
| v10_f_01_mode_normal | ACK RD MODE = NORMAL | = "ACK rd mode = NORMAL" | **FAIL** |
| v10_f_01_bootloader_v2 | NACK Invalid Command | = "ACK rd version-dfu = V2.00.0000" | **FAIL** |
| v10_f_01_config_factory | ACK RD CONFIG = Custom | = "ACK rd config = FACTORY" | **FAIL** |
| v10_f_01_twfa_scaling_factory | ACK RD TWFA-SCALING = 16 g | = "ACK rd twfa-scaling = AUTO" | **FAIL** |
| v10_f_01_twfb_scaling_factory | ACK RD TWFB-SCALING = 32 g | = "ACK rd twfb-scaling = AUTO" | **FAIL** |
| v10_f_01_detect_method_factory | ACK RD DETECT-METHOD = ACCRMS | = "ACK rd detect-method = ACCWAVE" | **FAIL** |
| v10_f_01_detect_period_factory | ACK RD DETECT-PERIOD = 100 Secs/Tick | = "ACK rd detect-period = 45 Sec/Tick" | **FAIL** |
| v10_f_01_detect_velrss_factory | NACK Invalid Command | = "ACK rd detect-velrss = 20 mm/s" | **FAIL** |
| v10_f_01_rms_odr_factory | NACK Invalid Command | = "ACK rd rms-odr = 6400 Hz" | **FAIL** |
| v10_f_01_rms_samples_factory | NACK Invalid Command | = "ACK rd rms-samples = 1024 Samples" | **FAIL** |
| v10_f_01_rms_fmin_factory | NACK Invalid Command | = "ACK rd rms-fmin = 7 Hz" | **FAIL** |
| v10_f_01_battery_time_factory | NACK Invalid Command | = "ACK rd battery-time = 50 mSec" | **FAIL** |

### V10-F-01b A package for another PCB is refused and the unit keeps its application

Result: **FAIL** | Requirement: V10-F-01 | Duration: 110.007 s

| Measurement | Value | Limit | Result |
|---|---|---|---|
| v10_f_01b_session_swdl | ACK SESSION SWDL | = "ACK session swdl" | **FAIL** |
| v10_f_01b_v5_refused | InvalidObject | = "ExtendedError" | **FAIL** |
| v10_f_01b_v5_hw_version |  | = "HwVersionFailure" | **FAIL** |
| v10_f_01b_v5_refused_at_init | init | = "init" | PASS |
| v10_f_01b_rd_id_unchanged | ACK RD ID = 0x5C1712 | = "ACK rd id = 0x5C1712" | **FAIL** |
| v10_f_01b_bootloader_v2 | NACK Invalid Command | = "ACK rd version-dfu = V2.00.0000" | **FAIL** |

### Restore 5C1712 - sensor ID, DEBUG image, NORMAL mode, FACTORY

Result: **PASS** | Duration: 70.003 s

| Measurement | Value | Limit | Result |
|---|---|---|---|
| debug_image_verified | 1 | = 1 | PASS |
| uicr_kept_after_restore | 1 | = 1 | PASS |
| sensor_id_word_kept_after_restore | 3.03521e+08 | = 3.03521e+08 | PASS |
| teardown_mode_normal | ACK wr mode NORMAL | = "ACK wr mode NORMAL" | PASS |
| teardown_factory | ACK routine config = FACTORY | = "ACK routine config = FACTORY" | PASS |
| teardown_rd_id | ACK rd id = 0x5C1712 | = "ACK rd id = 0x5C1712" | PASS |

