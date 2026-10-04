# Bench test report: QS-06b Refusals on hardware

| Field | Value |
|---|---|
| Result | **ERROR** |
| Bench | Bench PC (Windows) |
| Specification | specs/qualification/qs06b_refusals.yaml |
| Started | 2026-10-04T18:41:13+00:00 |
| Duration | 9.02 s |
| Tests | 0 passed, 0 failed, 5 errored, 0 skipped (of 5) |

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


### Dongle firmware that disagrees with its manifest (expected ERROR) - ERROR

Could not be executed: `dongle.check_firmware could not be called as specified: NordicDongle.check_firmware() got an unexpected keyword argument 'expected'`


### A command that gets no reply (expected ERROR) - ERROR

Could not be executed: `RttTimeout: RTT did not produce '^NEVER-ANSWERED$' within 3.0 s. Received:
SEGGER J-Link V9.42 - Real time terminal output
SEGGER J-Link V8.0, SN=682395790
Process: JLinkGDBServerCL.exe`


## All tests

### A meter that stops answering mid-session (expected ERROR)

Result: **ERROR** | Requirement: TB-SYS2-004, TB-SYS2-094 | Duration: 4.000 s

| Measurement | Value | Limit | Result |
|---|---|---|---|
| first_reading_is_live | 1 | = 1 | PASS |

### A memory read of 16 bytes as one integer (expected ERROR)

Result: **ERROR** | Requirement: TB-SYS2-032, TB-SYS2-094 | Duration: 1.906 s

```
ConfigurationError: read_integer takes 1 to 8 bytes, not 16. For a larger field use read_memory and decode it where its meaning is known.
```

### A memory read in a byte order that does not exist (expected ERROR)

Result: **ERROR** | Requirement: TB-SYS2-032, TB-SYS2-094 | Duration: 0.000 s

```
ConfigurationError: byteorder must be 'little' or 'big', not 'middle'
```

### Dongle firmware that disagrees with its manifest (expected ERROR)

Result: **ERROR** | Requirement: TB-SYS2-036, TB-SYS2-094 | Duration: 0.062 s

```
dongle.check_firmware could not be called as specified: NordicDongle.check_firmware() got an unexpected keyword argument 'expected'
```

### A command that gets no reply (expected ERROR)

Result: **ERROR** | Requirement: TB-SYS2-003, TB-SYS2-094 | Duration: 3.032 s

```
RttTimeout: RTT did not produce '^NEVER-ANSWERED$' within 3.0 s. Received:
SEGGER J-Link V9.42 - Real time terminal output
SEGGER J-Link V8.0, SN=682395790
Process: JLinkGDBServerCL.exe
```

