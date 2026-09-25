# BLE sensor test — template

Copy this file, rename it for what it tests, and edit the tables. Everything
outside a table is prose for the reader; the runner ignores it.

Run it against a sensor:

```
benchtools ble --resource COM10 script specs/templates/ble_sensor_test.md \
    --var SENSOR_ID=5C1712 --report results.md
```

The exit status is 0 when every checked step passed and 1 when one failed or
the run could not start. `--report` writes every step, its reply and its time;
`--log` on `benchtools ble` records the whole exchange.

## How a document is read

**Variables** are declared in the table below and used as `${NAME}` anywhere in
a command, an expected response or a delay. A variable with no default must be
given with `--var NAME=VALUE`; the sensor under test is one.

**Each `##` heading is a test**, and each row of its table is a step, run in
order. The first step of the first test must be a `connect`: the runner opens
the link there and closes it when the document ends.

| Step kind | Command cell | Expected response cell | Result |
|---|---|---|---|
| Connect | `connect <address or part of the name>` | empty | **pass** if the link opens, else **fail** |
| Command, checked | the command text | the reply, exactly (trimmed) | **pass** or **fail** |
| Command, checked by pattern | the command text | `/regular expression/` | **pass** or **fail** |
| Command, unchecked | the command text | empty | skip; the reply is recorded |
| Delay | `delay <milliseconds>` | empty | skip |
| Disconnect | `disconnect` | empty | skip |

A test passes when none of its steps failed; the document passes when no test
failed. A step that fails does not stop the ones after it.

`connect ${SENSOR_ID}` matches an address (`D1:8D:3B:4C:19:96`) exactly, or
otherwise any sensor whose advertised name contains the text, ignoring case -
the strongest such sensor if several do. It scans for 10 s first, long enough
for a sensor that advertises every 9 s, and tries the link up to three times.

## Variables

| Variable     | Default | Notes |
|--------------|---------|-------|
| SENSOR_ID    |         | Required. The sensor's ID, as in its name `KAPPA_<ID>_...` and its `rd id` reply: `5C1712` |
| SETTLE_MS    | 500     | Pause after connecting, before the first command |
| VERSION      | V11     | The start of the version the sensor must report |

## Connect and identify

| Step | Command              | Expected response                        | Notes |
|------|----------------------|------------------------------------------|-------|
| 1    | connect ${SENSOR_ID} |                                          | Must pass, or nothing after it can |
| 2    | delay ${SETTLE_MS}   |                                          | |
| 3    | rd version           | /^ACK rd version = ${VERSION}/           | The sensor answers `ACK <verb> <object> = <value>` |

## Build identity

What the sensor says it is, and what it was built from. `(?i)` makes a pattern
ignore case, as `connect` does, so `--var SENSOR_ID=5c1712` checks the same.

| Step | Command     | Expected response                              | Notes |
|------|-------------|------------------------------------------------|-------|
| 1    | rd id       | /(?i)^ACK rd id = 0x${SENSOR_ID}$/             | The ID in the advertised name |
| 2    | rd sha      | /^ACK rd sha = [0-9a-f]{7,40}$/                | Git commit the firmware was built from, abbreviated |
| 3    | rd compiler | /^ACK rd compiler = V[0-9]+\.[0-9]+\.[0-9]+$/  | Compiler version: `V9.03.01` |
| 4    | rd pcb      | /^ACK rd pcb = V[0-9]+[A-Z]*$/                 | Board revision: `V4X` |

## Commands and replies

Replace these rows with the commands under test. One row is one command.

| Step | Command              | Expected response                        | Notes |
|------|----------------------|------------------------------------------|-------|
| 1    | rd version           | /^ACK rd version = V[0-9]+\.[0-9]+\.[0-9]+$/ | A pattern: any three-part version |
| 2    | delay 250            |                                          | A pause is a step like any other |
| 3    | rd version           |                                          | No expected response: sent and recorded, never fails |

## Disconnect

| Step | Command    | Expected response | Notes |
|------|------------|-------------------|-------|
| 1    | disconnect |                   | Optional: the runner closes the link anyway |

## Converting to Robot Framework

The format is chosen so that each row becomes one keyword call, with the
variables written as they are here:

| Row | Robot Framework |
|---|---|
| `connect ${SENSOR_ID}` | `Connect    ${SENSOR_ID}` |
| `rd version` \| `ACK rd version = V11.00.0000` | `Send Command And Expect    rd version    ACK rd version = V11.00.0000` |
| `rd version` \| `/^ACK rd version = V11/` | `Send Command And Expect Match    rd version    ^ACK rd version = V11` |
| `rd version` \| (empty) | `Send Command    rd version` |
| `delay 250` | `Sleep    250 ms` |
| `disconnect` | `Disconnect` |

The Variables table becomes `*** Variables ***`, each `##` heading a test case,
and `--var NAME=VALUE` is Robot's own `--variable NAME:VALUE`.
