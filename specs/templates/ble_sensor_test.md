# BLE sensor test — template

Copy this file, rename it for what it tests, and edit the tables. Everything
outside a step table is prose for the reader; the runner ignores it.

Run it against a sensor:

```
benchtools ble --resource COM10 script specs/templates/ble_sensor_test.md \
    --var SENSOR_ID=5C1712 --report results.md --events events.log
```

The exit status is 0 when every checked step passed and 1 when one failed or
errored, or the run could not start.

- `--report` writes every step: command, expected, actual, response time,
  timeout - how long it waited at most, and why - result and note.
- `--events` writes the event log: one line per event, tab-separated, with the
  time it happened - `time  event  step  data  result`. Events are `TX`, `RX`,
  `DELAY`, `CONNECT`, `DISCONNECT` and `ERROR`; an `RX` line carries the
  dongle's own measurement of the exchange, to the microsecond.
- `--timeout-s` sets the default wait for a reply (3 s); `--timeout
  PREFIX=MS` overrides the Command prefix table below for one run, and is
  repeatable; `--log` on `benchtools ble` records the raw exchange with the
  dongle.

## How a document is read

**Variables** are declared in the table below and used as `${NAME}` anywhere in
a command, an expected response, a timeout or a delay. A variable with no
default must be given with `--var NAME=VALUE`; the sensor under test is one.

**Each `##` heading is a test**, and each row of its table is a step, run in
order. The first step must be a `connect`: the runner opens the link there and
closes it when the document ends.

| Step kind | Command cell | Expected response cell | Timeout cell |
|---|---|---|---|
| Connect | `connect <address or part of the name>` | empty | connect window, ms |
| Command, checked | the command text | the reply, exactly (trimmed) | reply wait, ms |
| Command, checked by pattern | the command text | `/regular expression/` | reply wait, ms |
| Command, sensor disconnects | the command text | `<disconnect>` | wait for the drop, ms |
| Command, unchecked | the command text | empty | listening window, ms |
| Delay | `delay <milliseconds>` | empty | must be empty |
| Disconnect | `disconnect` | empty | must be empty |

An empty Timeout cell uses the timeout the **Command prefix** table gives the
command, else the run's default. Some commands take longer than others: give a
family of them - every `routine`, every `wr` - a row in that table, and a
single command a timeout of its own. A prefix matches the start of the command,
ignoring case, and the longest prefix that matches wins. It applies to the
commands sent to the sensor - the reply wait, the listening window or the wait
for the drop - not to `connect`, `delay` or `disconnect`.

Add a **Frames** column to require a number of reply frames - usually `1` - for
a command that must answer exactly once. A sensor that answers twice leaves
every later command a reply behind; the extra frames are named in the result.

**Every step gets one result**, the first of these that applies:

| Result | When |
|---|---|
| **ERROR** | The system returned a failure code: the dongle refused the command, a connect or disconnect failed, or no reply came where one was expected |
| **SKIP** | The expected cell is empty: a delay, a connect or disconnect that worked, or a command nothing was promised for |
| **FAIL** | The actual reply differs from the expected one, or the sensor stayed connected after a `<disconnect>` step |
| **PASS** | The actual reply matches the expected one, or the sensor dropped the link as expected |

The run is **ERROR** if any step errored, else **FAIL** if any failed, else
**PASS**. A step that fails does not stop the ones after it. **Response time**
is from the end of the command to the start of the reply - or to the
disconnection, for a `<disconnect>` step - on the dongle's microsecond clock,
quoted in the report to 10 ms and in the event log in full.

`connect ${SENSOR_ID}` matches an address (`D1:8D:3B:4C:19:96`) exactly, or
otherwise any sensor whose advertised name contains the text, ignoring case -
the strongest such sensor if several do. It scans for 10 s first, long enough
for a sensor that advertises every 9 s, and tries the link up to three times.

## Variables

| Variable     | Default | Note |
|--------------|---------|------|
| SENSOR_ID    |         | Required. The sensor's ID, as in its name `KAPPA_<ID>_...` and its `rd id` reply: `5C1712` |
| SETTLE_MS    | 500     | Pause after connecting, before the first command |
| VERSION      | V11     | The start of the version the sensor must report |
| REBOOT_MS    | 15000   | How long a reset sensor may take to drop the link |
| ROUTINE_MS   | 30000   | How long a routine may take to answer |

## Timeouts by command prefix

| Command prefix | Timeout (ms)  | Note |
|----------------|---------------|------|
| routine        | ${ROUTINE_MS} | A routine runs before it answers |

## Connect and identify

| Step | Command              | Expected response              | Timeout (ms) | Note |
|------|----------------------|--------------------------------|--------------|------|
| 1    | connect ${SENSOR_ID} |                                |              | Must work, or nothing after it can |
| 2    | delay ${SETTLE_MS}   |                                |              | |
| 3    | rd version           | /^ACK rd version = ${VERSION}/ |              | The sensor answers `ACK <verb> <object> = <value>` |

## Build identity

What the sensor says it is, and what it was built from. `(?i)` makes a pattern
ignore case, as `connect` does, so `--var SENSOR_ID=5c1712` checks the same.

| Step | Command     | Expected response                             | Timeout (ms) | Note |
|------|-------------|-----------------------------------------------|--------------|------|
| 1    | rd id       | /(?i)^ACK rd id = 0x${SENSOR_ID}$/            |              | The ID in the advertised name |
| 2    | rd sha      | /^ACK rd sha = [0-9a-f]{7,40}$/               |              | Git commit the firmware was built from, abbreviated |
| 3    | rd compiler | /^ACK rd compiler = V[0-9]+\.[0-9]+\.[0-9]+$/ |              | Compiler version: `V9.03.01` |
| 4    | rd pcb      | /^ACK rd pcb = V[0-9]+[A-Z]*$/                |              | Board revision: `V4X` |

## Commands and replies

Replace these rows with the commands under test. One row is one command.

| Step | Command    | Expected response                             | Timeout (ms) | Note |
|------|------------|-----------------------------------------------|--------------|------|
| 1    | rd version | /^ACK rd version = V[0-9]+\.[0-9]+\.[0-9]+$/  |              | A pattern: any three-part version |
| 2    | delay 250  |                                               |              | A pause is a step like any other |
| 3    | rd version |                                               | 1000         | No expected response: sent, and the reply recorded, never fails |

## A command that takes longer

`routine config start factory` runs a routine before it answers, so it waits
the `routine` timeout from the Command prefix table rather than the default.
Check the reply against what the firmware sends; the pattern here accepts any
acknowledgement.

| Step | Command                      | Expected response | Timeout (ms) | Note |
|------|------------------------------|-------------------|--------------|------|
| 1    | routine config start factory | /^ACK/            |              | Waits ${ROUTINE_MS} ms: its prefix's timeout |

## A command after which the sensor resets

`wr mode normal` makes the sensor drop the link and reset. `<disconnect>`
expects exactly that, and the time from the command to the disconnection is
the step's response time. Connect again to carry on.

| Step | Command              | Expected response | Timeout (ms)  | Note |
|------|----------------------|-------------------|---------------|------|
| 1    | wr mode normal       | <disconnect>      | ${REBOOT_MS}  | Passes when the sensor drops the link |
| 2    | connect ${SENSOR_ID} |                   | 30000         | It must advertise again after the reset |
| 3    | rd version           | /^ACK rd version/ |               | And answer |

## A value that must not change

A **Save** column keeps a step's reply for later steps to use as `${NAME}`: read
a value, do something that should leave it alone, read it again. A pattern's
named group saves just that part of the reply.

| Step | Command    | Expected response                          | Save    | Note |
|------|------------|--------------------------------------------|---------|------|
| 1    | rd version | /^ACK rd version = (?P<value>V[0-9.]+)$/   | BUILD   | Saves the version alone |
| 2    | rd id      | /^ACK rd id = 0x/                          |         | Something in between |
| 3    | rd version | ACK rd version = ${BUILD}                  |         | Must be unchanged |

## Disconnect

| Step | Command    | Expected response | Timeout (ms) | Note |
|------|------------|-------------------|--------------|------|
| 1    | disconnect |                   |              | Optional: the runner closes the link anyway |

## Converting to Robot Framework

The format is chosen so that each row becomes one keyword call, with the
variables written as they are here:

| Row | Robot Framework |
|---|---|
| `connect ${SENSOR_ID}` | `Connect    ${SENSOR_ID}` |
| `rd version` \| `ACK rd version = V11.00.0000` | `Send Command And Expect    rd version    ACK rd version = V11.00.0000` |
| `rd version` \| `/^ACK rd version = V11/` | `Send Command And Expect Match    rd version    ^ACK rd version = V11` |
| `rd version` \| (empty) | `Send Command    rd version` |
| `wr mode normal` \| `<disconnect>` | `Send Command And Expect Disconnect    wr mode normal` |
| a Timeout cell of 30000 | `...    timeout=30 s` on the same keyword |
| a Command prefix row `routine` \| 30000 | `...    timeout=30 s` on each keyword whose command starts with `routine` - Robot has no timeout by prefix, so a translator applies the row as the runner does; a suite's `Test Timeout` bounds a whole test, not one command |
| a Frames cell of 1 | `Reply Frames Should Be    1` after the command |
| a Save cell of `BUILD` | `${BUILD}=    Send Command    rd version` |
| `delay 250` | `Sleep    250 ms` |
| `disconnect` | `Disconnect` |

The Variables table becomes `*** Variables ***`, each `##` heading a test case,
and `--var NAME=VALUE` is Robot's own `--variable NAME:VALUE`. The result
priority - ERROR, SKIP, FAIL, PASS - maps onto Robot's own statuses (an error
is a FAIL with the reason, a skip is `Skip`).
