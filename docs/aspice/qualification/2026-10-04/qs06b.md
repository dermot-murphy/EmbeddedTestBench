# Bench test report: QS-06b Refusals on hardware

| Field | Value |
|---|---|
| Result | **ERROR** |
| Bench | Bench PC (Windows) |
| Specification | specs/qualification/qs06b_refusals.yaml |
| Started | 2026-10-04T18:42:11+00:00 |
| Duration | 8.98 s |
| Tests | 0 passed, 1 failed, 5 errored, 0 skipped (of 6) |

## Instruments

| Alias | Event | Driver | Model | Firmware | Resource |
|---|---|---|---|---|---|
| dmm | DMM | Tti1604 | 1604 | - | COM13 |
| dongle | BLE | NordicDongle | PCA10059 | 1.4.0 (built local:Sep-29-2026T11:41:48) | COM10 |
| probe | JLINK | JLinkProbe | J-Link | J-Link ARM V8 compiled Nov 28 2014 13:44:46 | jlink:// |

## Requirements verified

| Requirement | Result |
|---|---|
| TB-SYS2-003 | **ERROR** |
| TB-SYS2-004 | **ERROR** |
| TB-SYS2-032 | **ERROR** |
| TB-SYS2-036 | **ERROR** |
| TB-SYS2-094 | **ERROR** |

## Problems

### A meter that stops answering mid-session (expected ERROR) - ERROR

Could not be executed: `InstrumentError: no measurement from the 1604 within 3.0 s. A healthy meter is silent in exactly two states: not in remote mode (this driver has not put it there), and switched off at the Operate key - which does not affect this interface, so the link looks the same either way.`


### A memory read of 16 bytes as one integer (expected ERROR) - ERROR

Could not be executed: `ConfigurationError: read_integer takes 1 to 8 bytes, not 16. For a larger field use read_memory and decode it where its meaning is known.`


### A memory read in a byte order that does not exist (expected ERROR) - ERROR

Could not be executed: `ConfigurationError: byteorder must be 'little' or 'big', not 'middle'`


### Dongle firmware that disagrees with its manifest is refused (expected ERROR) - ERROR

Could not be executed: `InstrumentError: the dongle is not running the expected firmware and updating was not permitted: dongle runs 1.4.0 (built local:Sep-29-2026T11:41:48); the build is 9.9.9 (built 2000-01-01T00:00:00Z)`


### The same mismatch, compared and asserted, is a failure (expected FAIL) - FAIL

- `dongle_matches_manifest` = 0, limit = 1 - 0 != required 1

### A command that gets no reply (expected ERROR) - ERROR

Could not be executed: `RttTimeout: RTT did not produce '^NEVER-ANSWERED$' within 3.0 s. Received:
SEGGER J-Link V9.42 - Real time terminal output
SEGGER J-Link V8.0, SN=682395790
Process: JLinkGDBServerCL.exe
`


## All tests

### A meter that stops answering mid-session (expected ERROR)

Result: **ERROR** | Requirement: TB-SYS2-004, TB-SYS2-094 | Duration: 4.016 s

| Measurement | Value | Limit | Result |
|---|---|---|---|
| first_reading_is_live | 1 | = 1 | PASS |

### A memory read of 16 bytes as one integer (expected ERROR)

Result: **ERROR** | Requirement: TB-SYS2-032, TB-SYS2-094 | Duration: 1.890 s

```
ConfigurationError: read_integer takes 1 to 8 bytes, not 16. For a larger field use read_memory and decode it where its meaning is known.
```

### A memory read in a byte order that does not exist (expected ERROR)

Result: **ERROR** | Requirement: TB-SYS2-032, TB-SYS2-094 | Duration: 0.000 s

```
ConfigurationError: byteorder must be 'little' or 'big', not 'middle'
```

### Dongle firmware that disagrees with its manifest is refused (expected ERROR)

Result: **ERROR** | Requirement: TB-SYS2-036, TB-SYS2-094 | Duration: 0.063 s

```
InstrumentError: the dongle is not running the expected firmware and updating was not permitted: dongle runs 1.4.0 (built local:Sep-29-2026T11:41:48); the build is 9.9.9 (built 2000-01-01T00:00:00Z)
```

### The same mismatch, compared and asserted, is a failure (expected FAIL)

Result: **FAIL** | Requirement: TB-SYS2-003, TB-SYS2-036 | Duration: 0.015 s

| Measurement | Value | Limit | Result |
|---|---|---|---|
| compared | 1 | = 1 | PASS |
| dongle_matches_manifest | 0 | = 1 | **FAIL** |

### A command that gets no reply (expected ERROR)

Result: **ERROR** | Requirement: TB-SYS2-003, TB-SYS2-094 | Duration: 3.000 s

```
RttTimeout: RTT did not produce '^NEVER-ANSWERED$' within 3.0 s. Received:
SEGGER J-Link V9.42 - Real time terminal output
SEGGER J-Link V8.0, SN=682395790
Process: JLinkGDBServerCL.exe

```

