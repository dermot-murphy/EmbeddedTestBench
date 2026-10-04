# Bench test report: QS-10 Bench identity

| Field | Value |
|---|---|
| Result | **FAIL** |
| Bench | Bench PC (Windows) |
| Specification | specs/qualification/qs10_bench_identity.yaml |
| Started | 2026-10-04T18:55:24+00:00 |
| Duration | 6.97 s |
| Tests | 0 passed, 1 failed, 0 errored, 0 skipped (of 1) |

## Instruments

| Alias | Event | Driver | Model | Firmware | Resource |
|---|---|---|---|---|---|
| dmm | DMM | Tti1604 | 1604 | - | COM13 |
| dongle | BLE | NordicDongle | PCA10059 | 1.4.0 (built local:Sep-29-2026T11:41:48) | COM10 |
| psu | PSU | Gpd3303D | GPD-3303D | V1.09 | COM11 |
| s2lp | RF | S2lpDevkit | STEVAL-FKI433V2 | 80 | COM4 |
| temp | TEMP | PicoSht30 | Pico 2/SHT30 | V1.00.0000 (5c80ae7) | COM14 |

## Requirements verified

| Requirement | Result |
|---|---|
| TB-SYS2-015 | **FAIL** |

## Problems

### Every instrument answers and is identified - FAIL

- `s2lp_band_hz` = 8.34608e+08 Hz, limit >= 4.3e+08, <= 4.4e+08 - 8.34608e+08 is above the maximum 4.4e+08

## All tests

### Every instrument answers and is identified

Result: **FAIL** | Requirement: TB-SYS2-015 | Duration: 6.969 s

| Measurement | Value | Limit | Result |
|---|---|---|---|
| psu_tracking | independent | = "independent" | PASS |
| dmm_unit_is_si | V | = "V" | PASS |
| dongle_scan_ran | 5 | >= 0 | PASS |
| s2lp_band_hz | 8.34608e+08 Hz | >= 4.3e+08, <= 4.4e+08 | **FAIL** |
| thermometer_version | V1.00.0000 | = "V1.00.0000" | PASS |

