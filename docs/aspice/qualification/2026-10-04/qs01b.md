# Bench test report: QS-01b Debug control and firmware state (hardware)

| Field | Value |
|---|---|
| Result | **FAIL** |
| Bench | Bench PC (Windows) |
| Specification | specs/qualification/qs01b_debug.yaml |
| Parameters | elf = U:/privatework/sensoteq/kepler/innovateuk-sensor/software/output/KAPPAX_APP_SDK17_PCB_V4X_RELEASE/exe/KAPPAX_APP_SDK17_PCB_V4X_RELEASE.elf, image = U:/privatework/sensoteq/kepler/innovateuk-sensor/software/output/KAPPAX_APP_SDK17_PCB_V4X_RELEASE/package/KAPPAX_APP_SDK17_PCB_V4X_RELEASE-plus-bl-and-softdevice.hex, manifest = specs/qualification/firmware/v11.00.0000-96, sensor_address = D1:8D:3B:4C:19:96 |
| Started | 2026-10-04T16:50:08+00:00 |
| Duration | 84.58 s |
| Tests | 4 passed, 1 failed, 0 errored, 0 skipped (of 5) |

## Instruments

| Alias | Event | Driver | Model | Firmware | Resource |
|---|---|---|---|---|---|
| dongle | BLE | NordicDongle | PCA10059 | 1.4.0 (built local:Sep-29-2026T11:41:48) | COM10 |
| probe | JLINK | JLinkProbe | J-Link | J-Link ARM V8 compiled Nov 28 2014 13:44:46 | jlink:// |

## Requirements verified

| Requirement | Result |
|---|---|
| TB-SYS2-002 | PASS |
| TB-SYS2-030 | PASS |
| TB-SYS2-031 | **FAIL** |
| TB-SYS2-033 | PASS |
| TB-SYS2-035 | PASS |
| TB-SYS2-036 | PASS |
| TB-SYS2-041 | PASS |

## Problems

### The core halts, steps and stops at a breakpoint - FAIL

- `pc_after_step` = 0x00000A82, limit = 0x00000000 +/- 0x00000004 - 2690 is 2690 from nominal 0, outside +/- 4

## All tests

### The image is programmed and verified, keeping the identity record

Result: **PASS** | Requirement: TB-SYS2-030, TB-SYS2-036 | Duration: 22.047 s

| Measurement | Value | Limit | Result |
|---|---|---|---|
| image_verified | 1 | = 1 | PASS |
| identity_kept | 3.03521e+08 | = 3.03521e+08 | PASS |

### The core halts, steps and stops at a breakpoint

Result: **FAIL** | Requirement: TB-SYS2-031 | Duration: 0.703 s

| Measurement | Value | Limit | Result |
|---|---|---|---|
| pc_at_reset | 0x00000000 | >= 0x00000000, <= 0x000FFFFF | PASS |
| pc_after_step | 0x00000A82 | = 0x00000000 +/- 0x00000004 | **FAIL** |
| stopped_in | main | = "main" | PASS |

### Firmware state is read by name while halted

Result: **PASS** | Requirement: TB-SYS2-002, TB-SYS2-033 | Duration: 0.031 s

| Measurement | Value | Limit | Result |
|---|---|---|---|
| frames | 1 | >= 1 | PASS |
| innermost_function | main | = "main" | PASS |
| SystemCoreClock | 6.4e+07 Hz | = 6.4e+07 | PASS |

### Start-up is timed on the cycle counter with its resolution stated

Result: **PASS** | Requirement: TB-SYS2-035 | Duration: 0.750 s

| Measurement | Value | Limit | Result |
|---|---|---|---|
| systeminit_to_main | 0.0223593 s | >= 1e-07, <= 1 | PASS |
| systeminit_to_main_cycles | 1.43099e+06 | >= 1 | PASS |
| resolution | 1.5625e-08 s | >= 1e-09, <= 1e-06 | PASS |

### The sensor runs and reports the version that was programmed

Result: **PASS** | Requirement: TB-SYS2-036, TB-SYS2-041 | Duration: 61.031 s

| Measurement | Value | Limit | Result |
|---|---|---|---|
| found | 1 | = 1 | PASS |
| reported_version | V11.00.0000-96-g25a54b97a | = "V11.00.0000-96-g25a54b97a" | PASS |

