# Bench test report: QS-01 Sensor bring-up (hardware)

| Field | Value |
|---|---|
| Result | **ERROR** |
| Bench | Bench PC (Windows) |
| Specification | specs/qualification/qs01_bringup.yaml |
| Parameters | identity_address = 268439680, image = U:/PrivateWork/Sensoteq/archive/V10.01.2000_V4X/KAPPAX_PCB_V4X_Production_APP_PLUS_SD_V10.01.2000.hex, manifest = specs/qualification/firmware/v10.01.2000 |
| Started | 2026-10-04T16:36:36+00:00 |
| Duration | 47.89 s |
| Tests | 5 passed, 0 failed, 2 errored, 0 skipped (of 7) |

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
| TB-SYS2-032 | PASS |
| TB-SYS2-034 | PASS |
| TB-SYS2-036 | **ERROR** |
| TB-SYS2-040 | **ERROR** |
| TB-SYS2-041 | **ERROR** |
| TB-SYS2-045 | **ERROR** |
| TB-SYS2-048 | PASS |
| TB-SYS2-049 | PASS |
| TB-SYS2-050 | PASS |

## Problems

### The sensor is found over the air by its own identifier - ERROR

Could not be executed: `SpecError: path '0.address': index 0 is out of range for a sequence of 0`

- `boards_with_that_identifier` = 0, limit = 1 - 0 != required 1

### The sensor reports the version that was programmed - ERROR

Could not be executed: `DongleCommandError: the dongle refused 'cmd 52442056455253494f4e timeout=45000': not connected (6)`


## All tests

### The identity record is read off the part before it is erased

Result: **PASS** | Requirement: TB-SYS2-048, TB-SYS2-050 | Duration: 2.063 s

| Measurement | Value | Limit | Result |
|---|---|---|---|
| identity_is_valid | 0 | = 0 | PASS |
| sensor_id | 5C1712 | >= 000001, <= FFFFFE | PASS |

### An erased part reads as an invalid identity record

Result: **PASS** | Requirement: TB-SYS2-049 | Duration: 0.594 s

| Measurement | Value | Limit | Result |
|---|---|---|---|
| erased_validity_byte | 255 | = 255 | PASS |

### The image is programmed and verified

Result: **PASS** | Requirement: TB-SYS2-030, TB-SYS2-036 | Duration: 14.687 s

| Measurement | Value | Limit | Result |
|---|---|---|---|
| image_verified | 1 | = 1 | PASS |

### The identity record is written back and reads as it did

Result: **PASS** | Requirement: TB-SYS2-032, TB-SYS2-048 | Duration: 0.047 s

| Measurement | Value | Limit | Result |
|---|---|---|---|
| identity_is_valid | 0 | = 0 | PASS |
| sensor_id_restored | 5C1712 | = 5C1712 | PASS |

### The sensor starts and is running

Result: **PASS** | Requirement: TB-SYS2-002, TB-SYS2-034 | Duration: 0.391 s

| Measurement | Value | Limit | Result |
|---|---|---|---|
| rtt_lines | 3 | >= 1 | PASS |

### The sensor is found over the air by its own identifier

Result: **ERROR** | Requirement: TB-SYS2-040, TB-SYS2-041, TB-SYS2-045 | Duration: 30.093 s

| Measurement | Value | Limit | Result |
|---|---|---|---|
| boards_with_that_identifier | 0 | = 1 | **FAIL** |

### The sensor reports the version that was programmed

Result: **ERROR** | Requirement: TB-SYS2-036, TB-SYS2-041 | Duration: 0.000 s

```
DongleCommandError: the dongle refused 'cmd 52442056455253494f4e timeout=45000': not connected (6)
```

