# Bench test report: QS-10 Bench identity

| Field | Value |
|---|---|
| Result | **ERROR** |
| Bench | Bench PC (Windows) (simulated) |
| Specification | specs/qualification/qs10_bench_identity.yaml |
| Started | 2026-10-04T18:54:39+00:00 |
| Duration | 0.16 s |
| Tests | 0 passed, 0 failed, 1 errored, 0 skipped (of 1) |

> Run against simulated instruments. These results verify the specification and the tooling, **not** any physical hardware.

## Instruments

| Alias | Event | Driver | Model | Firmware | Resource |
|---|---|---|---|---|---|
| dmm | DMM | Tti1604 | 1604 | - | COM13 |
| dongle | BLE | NordicDongle | PCA10059 | 1.4.0 (built 2026-09-13T12:00:00Z) | COM10 |
| psu | PSU | Gpd3303D | GPD-3303D | V1.09 | COM11 |
| s2lp | RF | S2lpDevkit | STEVAL-FKI433V2 | 80 | COM4 |

## Requirements verified

| Requirement | Result |
|---|---|
| TB-SYS2-015 | **ERROR** |

## Problems

### Every instrument answers and is identified - ERROR

Could not be executed: `a step failed to execute`

- `s2lp_band_hz` = -, limit >= 4.3e+08, <= 4.4e+08 - path 'frequency_hz': cannot resolve 'frequency_hz' on a dict

## All tests

### Every instrument answers and is identified

Result: **ERROR** | Requirement: TB-SYS2-015 | Duration: 0.156 s

| Measurement | Value | Limit | Result |
|---|---|---|---|
| psu_tracking | independent | = "independent" | PASS |
| dmm_unit_is_si | V | = "V" | PASS |
| dongle_scan_ran | 3 | >= 0 | PASS |
| s2lp_band_hz | - | >= 4.3e+08, <= 4.4e+08 | **ERROR** |

