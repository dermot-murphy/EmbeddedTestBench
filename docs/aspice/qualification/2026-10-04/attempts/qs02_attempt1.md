# Bench test report: QS-02 BLE command document (hardware)

| Field | Value |
|---|---|
| Result | **FAIL** |
| Bench | Bench PC (Windows) |
| Specification | specs/qualification/qs02_kepler_commands.yaml |
| Parameters | document = specs/qualification/qs02_kepler_commands.md, document_report = docs/aspice/qualification/2026-10-04/qs02_document_report.md |
| Started | 2026-10-04T16:55:27+00:00 |
| Duration | 38.27 s |
| Tests | 0 passed, 1 failed, 0 errored, 0 skipped (of 1) |

## Instruments

| Alias | Event | Driver | Model | Firmware | Resource |
|---|---|---|---|---|---|
| dongle | BLE | NordicDongle | PCA10059 | 1.4.0 (built local:Sep-29-2026T11:41:48) | COM10 |

## Requirements verified

| Requirement | Result |
|---|---|
| TB-SYS2-073 | **FAIL** |
| TB-SYS2-075 | **FAIL** |

## Problems

### The command document runs and every checked step passes - FAIL

- `steps_skipped` = 5, limit >= 6 - 5 is below the minimum 6

## All tests

### The command document runs and every checked step passes

Result: **FAIL** | Requirement: TB-SYS2-073, TB-SYS2-075 | Duration: 38.265 s

| Measurement | Value | Limit | Result |
|---|---|---|---|
| steps_failed | 0 | = 0 | PASS |
| steps_errored | 0 | = 0 | PASS |
| steps_passed | 8 | >= 8 | PASS |
| steps_skipped | 5 | >= 6 | **FAIL** |
| document_result | PASS | = "PASS" | PASS |

