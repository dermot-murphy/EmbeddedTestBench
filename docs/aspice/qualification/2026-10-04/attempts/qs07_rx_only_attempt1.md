# Bench test report: QS-07 Sub-GHz link (hardware)

| Field | Value |
|---|---|
| Result | **ERROR** |
| Bench | Bench PC (Windows) |
| Specification | specs/qualification/qs07_subghz_link.yaml |
| Parameters | receive_setup = configs/s2lp_kepler_433_rx.regs, sensor_address = D1:8D:3B:4C:19:96, sensor_id = 5C1712 |
| Selected tests | A frame from the sensor is received after a reset over BLE |
| Started | 2026-10-04T16:59:42+00:00 |
| Duration | 32.70 s |
| Tests | 0 passed, 0 failed, 1 errored, 4 skipped (of 5) |

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

Result: **SKIP** | Requirement: TB-SYS2-046 | Duration: 0.000 s

Skipped: not selected

### Every register can be read

Result: **SKIP** | Requirement: TB-SYS2-046 | Duration: 0.000 s

Skipped: not selected

### A register is written and reads back, then is restored

Result: **SKIP** | Requirement: TB-SYS2-046 | Duration: 0.000 s

Skipped: not selected

### A packet is transmitted and recorded

Result: **SKIP** | Requirement: TB-SYS2-046 | Duration: 0.000 s

Skipped: not selected

### A frame from the sensor is received after a reset over BLE

Result: **ERROR** | Requirement: TB-SYS2-046 | Duration: 32.703 s

| Measurement | Value | Limit | Result |
|---|---|---|---|
| registers_mismatched | 0 | = 0 | PASS |

