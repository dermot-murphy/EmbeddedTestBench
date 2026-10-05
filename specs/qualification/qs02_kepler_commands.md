# QS-02 - Kepler BLE command document (hardware qualification)

This document is both a statement of part of the Kepler sensor's BLE command
set and the test of it (ETB-SYS2-073). It is QS-02 of ETB-SYS5-001, run on the
bench PC against sensor 5C1712 for #176, by `qs02_kepler_commands.yaml` and by
`benchtools ble script`.

It qualifies the **bench's** handling of a command document, not the sensor's
firmware:
- each row is a step;
- a delay and a command with nothing expected are recorded as skipped (ETB-SYS2-074);
- a step can set its own timeout (ETB-SYS2-082);
- an expected disconnection is timed (ETB-SYS2-083);
- times are quoted to 10 ms with the dongle's microsecond figure kept (ETB-SYS2-077).

The patterns accept any value of the right shape, so a firmware change does
not make this fail.

Every command reads, except `ECURESET HARD`, an MCU reset the sensor recovers
from by itself. Nothing is written to the sensor's settings.

## Variables

| Variable  | Default | Note |
|-----------|---------|------|
| SENSOR_ID | 5C1712  | The sensor approved for destructive tests |
| SETTLE_MS | 500     | Pause after connecting |
| REPLY_MS  | 45000   | Kepler sensors can stall for up to 45 s after a write or a reset |

## Connect and identify

| Step | Command              | Expected response                          | Timeout (ms) | Note |
|------|----------------------|--------------------------------------------|--------------|------|
| 1    | connect ${SENSOR_ID} |                                            | 30000        | Selected by part of its name |
| 2    | delay ${SETTLE_MS}   |                                            |              | A delay is skipped, not passed |
| 3    | RD VERSION           | /^ACK RD VERSION = V[0-9]+\.[0-9]+\.[0-9]+/ | ${REPLY_MS} | Any version of that shape |
| 4    | RD ID                | /(?i)^ACK RD ID = (0x)?${SENSOR_ID}$/       | ${REPLY_MS} | The identifier in its advertising name |
| 5    | RD SHA               | /^ACK RD SHA = [0-9a-f]{7,40}$/             | ${REPLY_MS} | |

## Readings

| Step | Command          | Expected response                    | Timeout (ms) | Note |
|------|------------------|--------------------------------------|--------------|------|
| 1    | RD TEMPERATURE   | /^ACK RD TEMPERATURE = -?[0-9]+mC$/  | ${REPLY_MS}  | Milli-degrees Celsius |
| 2    | RD BATTERY       | /^ACK RD BATTERY = [0-9.]+ ?m?V$/      | ${REPLY_MS}  | Volts or millivolts, as the firmware words it |
| 3    | RD BATTERY       |                                      | 2000         | Nothing expected: recorded and skipped, with a timeout of its own |

## An unknown command is refused

| Step | Command        | Expected response | Timeout (ms) | Note |
|------|----------------|-------------------|--------------|------|
| 1    | RD NO-SUCH-ITEM | /^NACK/          | ${REPLY_MS}  | The refusal is the sensor's; the bench records it as a reply |

## A reset drops the link, and the time to the drop is measured

| Step | Command              | Expected response | Timeout (ms) | Note |
|------|----------------------|-------------------|--------------|------|
| 1    | ECURESET HARD        | <disconnect>      | 15000        | Passes when the sensor drops the link |
| 2    | connect ${SENSOR_ID} |                   | 60000        | It advertises again after the reset |
| 3    | RD VERSION           | /^ACK RD VERSION/ | ${REPLY_MS}  | And answers again |
| 4    | disconnect           |                   |              | |
