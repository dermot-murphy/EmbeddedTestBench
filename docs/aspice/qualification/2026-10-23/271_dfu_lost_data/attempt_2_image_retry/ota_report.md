# Bench test report: BT-003 legacy upgrade - V10.00.0000 to the candidate over the air

| Field | Value |
|---|---|
| Result | **ERROR** |
| Bench | Kepler bench (5C1712) |
| Specification | U:/PrivateWork/Sensoteq/Kepler/innovateuk-sensor/software/test/bench/release_since_v10_00_0000/release_legacy_ota.yaml |
| Parameters | backup_bl_version_address = 1040396, boot_s = 15.0, bootloader_idle_s = 45.0, connect_s = 60.0, debug_hex = ../../../output/KAPPAX_APP_SDK17_PCB_V4X_DEBUG/package/KAPPAX_APP_SDK17_PCB_V4X_DEBUG-plus-bl-and-softdevice.hex, dfu_target = KAPPA_5C1712, id_address = 268439680, id_word = 303520768, off_channel = 1, off_max_v = 0.05, refused_timeout_s = 60.0, reply_timeout_s = 45.0, scan_s = 20.0, sensor_address = D1:8D:3B:4C:19:96, sensor_id = 5C1712, settings_bl_version_address = 1044492, step_1_package = ../../../output/legacy_images/candidate/KAPPAX_Release_BL_V2.00.0000_UPGRADE_OTA.zip, step_1_timeout_s = 180.0, step_2_package = ../../../output/legacy_images/candidate/KAPPAX_APP_SDK17_PCB_V4X_RELEASE_OTA.zip, step_2_timeout_s = 180.0, supply_channel = 2, supply_v = 3.3, two_frame_window_s = 2.0, v10_00_hex = ../../../output/legacy_images/V10.00.0000/KAPPAX_PCB_V4X_Production_V10.00.0000-plus-bl-and-softdevice.hex, v5_package = ../../../output/KAPPAX_APP_SDK17_PCB_V5_DEBUG/package/KAPPAX_APP_SDK17_PCB_V5_DEBUG_OTA.zip |
| Started | 2026-10-23T17:08:45+00:00 |
| Duration | 291.42 s |
| Tests | 1 passed, 0 failed, 2 errored, 0 skipped (of 3) |

## Instruments

| Alias | Event | Driver | Model | Firmware | Resource |
|---|---|---|---|---|---|
| dongle | BLE | NordicDongle | PCA10059 | 1.7.0 (built 2026-10-23T10:55:19Z) | COM10 |
| probe | JLINK | JLinkProbe | J-Link | J-Link ARM V8 compiled Nov 28 2014 13:44:46 | jlink:// |
| psu | PSU | Gpd3303D | GPD-3303D | V1.09 | COM11 |

## Requirements verified

| Requirement | Result |
|---|---|
| V10-F-01 | **ERROR** |

## Problems

### V10-F-01 Field upgrade V10.00.0000 to the candidate over the air - ERROR

Could not be executed: `InstrumentError: no bootloader matching 'KAPPA_5C1712' was heard in 5 s. Heard: 5C:C1:D7:44:44:AF , 5A:51:E0:A8:AB:9F , E4:69:B9:0F:6B:3C KAPPA_5C314E_V10.00.0000P, 23:20:36:1C:85:3D , FE:1C:34:B2:58:90 SENS-G3-3045, C9:91:37:E4:C7:36 KAPPA_5C4EE7_V11.01.0000X, CE:CD:99:EE:91:C1 KAPPA_5C168B_V10.01.20, D9:40:04:9C:22:AA KAPPA_5C1705_V10.01.20. A sensor enters its bootloader on SESSION SWDL and leaves it after 30 s idle.`


### V10-F-01b A package for another PCB is refused and the unit keeps its application - ERROR

Could not be executed: `LinkLostError: could not connect to D1:8D:3B:4C:19:96: the dongle reported no connection (reason timeout). A sensor that advertises rarely can fall outside the connect window; try again, or check it is in range and not connected to something else.`


## All tests

### V10-F-01 Field upgrade V10.00.0000 to the candidate over the air

Result: **ERROR** | Requirement: V10-F-01 | Duration: 70.792 s

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
| v10_f_01_step_1_bootloader | Success | = "Success" | PASS |
| v10_f_01_step_1_done | done | = "done" | PASS |

### V10-F-01b A package for another PCB is refused and the unit keeps its application

Result: **ERROR** | Requirement: V10-F-01 | Duration: 80.040 s

```
LinkLostError: could not connect to D1:8D:3B:4C:19:96: the dongle reported no connection (reason timeout). A sensor that advertises rarely can fall outside the connect window; try again, or check it is in range and not connected to something else.
```

### Restore 5C1712 - sensor ID, DEBUG image, NORMAL mode, FACTORY

Result: **PASS** | Duration: 70.543 s

| Measurement | Value | Limit | Result |
|---|---|---|---|
| debug_image_verified | 1 | = 1 | PASS |
| uicr_kept_after_restore | 1 | = 1 | PASS |
| sensor_id_word_kept_after_restore | 3.03521e+08 | = 3.03521e+08 | PASS |
| teardown_mode_normal | ACK wr mode NORMAL | = "ACK wr mode NORMAL" | PASS |
| teardown_factory | ACK routine config = FACTORY | = "ACK routine config = FACTORY" | PASS |
| teardown_rd_id | ACK rd id = 0x5C1712 | = "ACK rd id = 0x5C1712" | PASS |

