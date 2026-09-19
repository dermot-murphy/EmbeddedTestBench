# Sensor BLE command set

This document is both the specification of the sensor's command set and the test
of it. `benchtools` runs it against a board and reports every step — see
[Bench Runner Guide §3.5](../docs/Bench_Runner_Guide.md) for the format and
`specs/sensor_commands.yaml` for the suite that runs it.

Each `##` heading is a test. Each row is a step:

- a **command with an expected response** is checked, and passes or fails;
- `delay <milliseconds>` waits, and is skipped;
- a command with **no expected response** is sent and whatever comes back is
  recorded, and is skipped.

An expected response written `/like this/` is a regular expression, for a reply
carrying a value that varies. Anchor it with `^` and `$` to require the whole
reply.

## Identity

The board must say what it is before anything else is believed about it. The
version here is compared with the version the firmware reports; the suite also
compares it with the build that was flashed.

| Step | Command    | Expected response    | Notes |
|------|------------|----------------------|-------|
| 1    | rd version | /^[0-9]+\.[0-9]+\.[0-9]+$/ | Three numbers; the build decides which |
| 2    | rd id      | /^SENS-[0-9A-F]{6}$/ | Matches the identifier in the advertising name |

## Sensor readings

| Step | Command | Expected response | Notes |
|------|---------|-------------------|-------|
| 1    | temp    | /^-?[0-9]+\.[0-9]$/ | Degrees Celsius, one decimal |
| 2    | battery | /^[0-9]{1,3}$/      | Percent |
| 3    | measure | /^OK [0-9]+$/       | A measurement takes ~95 ms, which the times show |

## Settling between measurements

A delay is a step like any other: it appears in the report, in order, and is
skipped rather than passed — waiting is not a claim about the sensor.

| Step | Command   | Expected response |
|------|-----------|-------------------|
| 1    | measure   | /^OK [0-9]+$/     |
| 2    | delay 100 |                   |
| 3    | measure   | /^OK [0-9]+$/     |

## Commands with nothing promised

The document makes no claim about what these reply, so they cannot fail. What
came back is recorded anyway: a board that started answering something new is
worth seeing, and the next revision of this document can make a claim about it.

| Step | Command | Expected response | Notes |
|------|---------|-------------------|-------|
| 1    | id      |                   | The bare form, kept for older firmware |
| 2    | version |                   | As above |

## Unknown commands are refused

A board that answers anything at all to a command it does not have is a board
whose replies mean less than they appear to.

| Step | Command             | Expected response   |
|------|---------------------|---------------------|
| 1    | definitely-not-a-command | ERR unknown command |
