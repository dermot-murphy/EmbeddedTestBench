# Bench test report: RTT from a container without stopping the sensor (#70 step 8)

| Field | Value |
|---|---|
| Result | **ERROR** |
| Bench | Bench PC from a container (rtt only, |
| Specification | /out/step8_rtt.yaml |
| Started | 2026-11-15T09:51:02+00:00 |
| Duration | 0.53 s |
| Tests | 0 passed, 0 failed, 1 errored, 0 skipped (of 1) |

## Instruments

| Alias | Event | Driver | Model | Firmware | Resource |
|---|---|---|---|---|---|
| rtt | RTT | JLinkRttReader | J-Link | - | jlink://host.docker.internal:2341 |

## Problems

### RTT lines arrive - ERROR

Could not be executed: `a step failed to execute`

- `lines` = -, limit >= 1 - path 'value': cannot resolve 'value' on a int

## All tests

### RTT lines arrive

Result: **ERROR** | Duration: 0.001 s

| Measurement | Value | Limit | Result |
|---|---|---|---|
| lines | - | >= 1 | **ERROR** |

