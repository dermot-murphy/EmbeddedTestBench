# Bench test report: QS-10 Bench identity

| Field | Value |
|---|---|
| Result | **PASS** |
| Bench | Bench PC (Windows) (simulated) |
| Specification | specs/qualification/qs10_bench_identity.yaml |
| Started | 2026-10-04T18:55:58+00:00 |
| Duration | 0.16 s |
| Tests | 1 passed, 0 failed, 0 errored, 0 skipped (of 1) |

> Run against simulated instruments. These results verify the specification and the tooling, **not** any physical hardware.

## Instruments

| Alias | Event | Driver | Model | Firmware | Resource |
|---|---|---|---|---|---|
| dmm | DMM | Tti1604 | 1604 | - | COM13 |
| dongle | BLE | NordicDongle | PCA10059 | 1.4.0 (built 2026-09-13T12:00:00Z) | COM10 |
| psu | PSU | Gpd3303D | GPD-3303D | V1.09 | COM11 |
| s2lp | RF | S2lpDevkit | STEVAL-FKI433V2 | 80 | COM4 |
| temp | TEMP | PicoSht30 | Pico 2/SHT30 | V1.00.0000 (0c0ffee) | COM14 |

## Requirements verified

| Requirement | Result |
|---|---|
| TB-SYS2-015 | PASS |

## All tests

### Every instrument answers and is identified

Result: **PASS** | Requirement: TB-SYS2-015 | Duration: 0.156 s

| Measurement | Value | Limit | Result |
|---|---|---|---|
| psu_tracking | independent | = "independent" | PASS |
| dmm_unit_is_si | V | = "V" | PASS |
| dongle_scan_ran | 3 | >= 0 | PASS |
| s2lp_registers_read | 123 | >= 100 | PASS |
| thermometer_version | V1.00.0000 | = "V1.00.0000" | PASS |

