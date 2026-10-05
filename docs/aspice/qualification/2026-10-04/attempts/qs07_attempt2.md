# Bench test report: QS-07 Sub-GHz link (hardware)

| Field | Value |
|---|---|
| Result | **ERROR** |
| Bench | Bench PC (Windows) |
| Specification | specs/qualification/qs07_subghz_link.yaml |
| Parameters | receive_setup = configs/s2lp_kepler_433_rx.regs, sensor_address = D1:8D:3B:4C:19:96, sensor_id = 5C1712 |
| Started | 2026-10-04T17:01:37+00:00 |
| Duration | 36.52 s |
| Tests | 4 passed, 0 failed, 1 errored, 0 skipped (of 5) |

## Instruments

| Alias | Event | Driver | Model | Firmware | Resource |
|---|---|---|---|---|---|
| dongle | BLE | NordicDongle | PCA10059 | 1.4.0 (built local:Sep-29-2026T11:41:48) | COM10 |
| s2lp | RF | S2lpDevkit | STEVAL-FKI433V2 | 80 | COM4 |

## Requirements verified

| Requirement | Result |
|---|---|
| TB-SYS2-046 | **ERROR** |

## Problems

### A frame from the sensor is received after a reset over BLE - ERROR

Could not be executed: `InstrumentError: could not connect to D1:8D:3B:4C:19:96: the dongle reported the connection lost (reason 0x3e). A sensor that advertises rarely can fall outside the connect window; try again, or check it is in range and not connected to something else.`


## All tests

### A register file is programmed and every register it names reads back

Result: **PASS** | Requirement: TB-SYS2-046 | Duration: 0.734 s

| Measurement | Value | Limit | Result |
|---|---|---|---|
| registers_checked | 28 | >= 20 | PASS |
| registers_mismatched | 0 | = 0 | PASS |

### Every register can be read

Result: **PASS** | Requirement: TB-SYS2-046 | Duration: 0.282 s

| Measurement | Value | Limit | Result |
|---|---|---|---|
| registers_read | 123 | >= 100 | PASS |

### A register is written and reads back, then is restored

Result: **PASS** | Requirement: TB-SYS2-046 | Duration: 0.062 s

| Measurement | Value | Limit | Result |
|---|---|---|---|
| sync0_before | 0x4E | >= 0x00, <= 0xFF | PASS |
| sync0_written | 0x5A | = 0x5A | PASS |
| sync0_restored | 0x4E | = 0x4E | PASS |

### A packet is transmitted and recorded

Result: **PASS** | Requirement: TB-SYS2-046 | Duration: 0.063 s

| Measurement | Value | Limit | Result |
|---|---|---|---|
| bytes_sent | 17 | = 17 | PASS |
| firmware_error_code | 0 | = 0 | PASS |

### A frame from the sensor is received after a reset over BLE

Result: **ERROR** | Requirement: TB-SYS2-046 | Duration: 35.375 s

| Measurement | Value | Limit | Result |
|---|---|---|---|
| registers_mismatched | 0 | = 0 | PASS |

