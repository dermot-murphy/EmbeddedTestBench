# Bench test report: QS-03 Supply refusals and safe state (hardware)

| Field | Value |
|---|---|
| Result | **PASS** |
| Bench | Bench PC (Windows) |
| Specification | specs/qualification/qs03_supply.yaml |
| Selected tests | Independent: state, setpoints and readback, Independent: safe state |
| Started | 2026-10-04T17:05:39+00:00 |
| Duration | 3.73 s |
| Tests | 2 passed, 0 failed, 0 errored, 6 skipped (of 8) |

## Instruments

| Alias | Event | Driver | Model | Firmware | Resource |
|---|---|---|---|---|---|
| psu | PSU | Gpd3303D | GPD-3303D | V1.09 | COM11 |

## Requirements verified

| Requirement | Result |
|---|---|
| TB-SYS2-020 | PASS |
| TB-SYS2-021 | PASS |
| TB-SYS2-022 | skip |
| TB-SYS2-023 | skip |
| TB-SYS2-024 | skip |

## All tests

### Independent: state, setpoints and readback

Result: **PASS** | Requirement: TB-SYS2-020, TB-SYS2-021, TB-SYS2-022 | Duration: 2.422 s

| Measurement | Value | Limit | Result |
|---|---|---|---|
| tracking | independent | = "independent" | PASS |
| output_off | 0 | = 0 | PASS |
| ch1_voltage_setpoint | 1.5 V | = 1.5 +/- 0.01 | PASS |
| ch1_current_setpoint | 0.1 A | = 0.1 +/- 0.001 | PASS |
| ch1_output_still_off | 0 | = 0 | PASS |
| ch2_voltage_setpoint | 2.5 V | = 2.5 +/- 0.01 | PASS |
| ch2_output_still_off | 0 | = 0 | PASS |
| ch1_output_voltage | 0 V | = 0 +/- 0.05 | PASS |
| ch1_output_current | 0 A | = 0 +/- 0.005 | PASS |

### Independent: safe state

Result: **PASS** | Requirement: TB-SYS2-024 | Duration: 1.266 s

| Measurement | Value | Limit | Result |
|---|---|---|---|
| ch1_setpoint_zero | 0 V | = 0 +/- 0.01 | PASS |
| ch1_off | 0 | = 0 | PASS |
| ch2_setpoint_zero | 0 V | = 0 +/- 0.01 | PASS |
| ch2_off | 0 | = 0 | PASS |

### Series: state

Result: **SKIP** | Requirement: TB-SYS2-022 | Duration: 0.000 s

Skipped: not selected

### Series: a channel 2 setpoint is refused (expected ERROR)

Result: **SKIP** | Requirement: TB-SYS2-023 | Duration: 0.000 s

Skipped: not selected

### Series: safe state

Result: **SKIP** | Requirement: TB-SYS2-024 | Duration: 0.000 s

Skipped: not selected

### Parallel: state

Result: **SKIP** | Requirement: TB-SYS2-022 | Duration: 0.000 s

Skipped: not selected

### Parallel: a channel 2 setpoint is refused (expected ERROR)

Result: **SKIP** | Requirement: TB-SYS2-023 | Duration: 0.000 s

Skipped: not selected

### Parallel: safe state

Result: **SKIP** | Requirement: TB-SYS2-024 | Duration: 0.000 s

Skipped: not selected

