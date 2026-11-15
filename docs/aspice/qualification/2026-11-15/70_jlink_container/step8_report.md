# Bench test report: RTT from a container without stopping the sensor (#70 step 8)

| Field | Value |
|---|---|
| Result | **PASS** |
| Bench | Bench PC from a container (rtt only, |
| Specification | /out/step8_rtt.yaml |
| Started | 2026-11-15T09:53:20+00:00 |
| Duration | 41.01 s |
| Tests | 1 passed, 0 failed, 0 errored, 0 skipped (of 1) |

## Instruments

| Alias | Event | Driver | Model | Firmware | Resource |
|---|---|---|---|---|---|
| rtt | RTT | JLinkRttReader | J-Link | - | jlink://host.docker.internal:2341 |

## All tests

### The firmware's periodic log arrives over RTT

Result: **PASS** | Duration: 40.479 s

| Measurement | Value | Limit | Result |
|---|---|---|---|
| wakes | 2 | = 2 | PASS |

