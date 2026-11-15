# Bench test report: RTT from a container without stopping the sensor (#70 step 8)

| Field | Value |
|---|---|
| Result | **FAIL** |
| Bench | Bench PC from a container (rtt only, |
| Specification | /out/step8_rtt.yaml |
| Started | 2026-11-15T09:52:03+00:00 |
| Duration | 60.55 s |
| Tests | 0 passed, 1 failed, 0 errored, 0 skipped (of 1) |

## Instruments

| Alias | Event | Driver | Model | Firmware | Resource |
|---|---|---|---|---|---|
| rtt | RTT | JLinkRttReader | J-Link | - | jlink://host.docker.internal:2341 |

## Problems

### The firmware's periodic log arrives over RTT - FAIL

- `wakes` = 2, limit = 3 - 2 != required 3

## All tests

### The firmware's periodic log arrives over RTT

Result: **FAIL** | Duration: 60.008 s

| Measurement | Value | Limit | Result |
|---|---|---|---|
| wakes | 2 | = 3 | **FAIL** |

