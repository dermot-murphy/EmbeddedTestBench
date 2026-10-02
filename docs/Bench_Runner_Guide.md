# Bench Runner Guide

How to write a test specification and a bench configuration, and how to run them.

| Field | Value |
|---|---|
| Document ID | BENCHTOOLS-GUIDE-001 |
| Version | 3.1 |
| Date | 2026-10-02 |
| Applies to | `benchtools` 4.0.0 |

---

## 1. The two files, and why they are separate

| File | Answers | Changes when |
|---|---|---|
| **Test specification** | What to do, and what counts as a pass | The test changes |
| **Bench configuration** | Which instruments exist, and where | The rig changes |

Keeping them apart is what makes a specification portable. The same suite runs on
the lab rig, on a second rig with different addresses, or entirely against
simulators, with no edit to the test.

Both can be YAML (needs the `spec` extra: `pip install benchtools[spec]`) or JSON
(needs nothing).

---

## 2. Bench configuration

```yaml
name: Lab bench 1
description: Clock distribution test rig.

instruments:
  scope:
    driver: tek3014b
    resource: 192.168.1.50      # or vxi11://192.168.1.50/gpib0,1
    timeout: 15.0

  psu:
    driver: gpd3303d            # GW Instek GPD-3303D, over its USB-serial port
    resource: /dev/ttyUSB0      # COM4 on Windows
    options:
      baudrate: 9600            # must match the supply's front-panel setting

  dmm:
    driver: generic             # no dedicated driver yet: identify and raw SCPI
    resource: 192.168.1.60

  probe:
    driver: jlink               # a debug probe is a bench instrument too
    resource: jlink://          # or jlink://bench-pc:2331 for a probe elsewhere
    device: nRF52840_xxAA
    elf: build/app.elf
    core_clock_hz: 64000000

  dongle:
    driver: ble-dongle          # and so is a BLE dongle
    resource: /dev/ttyACM0      # COM5 on Windows; a bare name means a serial port
    options:
      firmware: firmware/nordic_dongle/_build   # the build it should be running
      update_firmware: false                    # true to refresh it when it is not
```

Keys a driver does not recognise are passed to it, which is how the probe gets
`device`, `elf` and `core_clock_hz`. A driver ignores what it does not use.

The alias on the left (`scope`, `psu`) is what a specification refers to.

Shorthand, when the defaults suffice:

```yaml
instruments:
  scope: tek3014b@192.168.1.50
  psu: gpd3303d@sim://
```

| Key | Meaning |
|---|---|
| `driver` | A registered driver name. `benchtools drivers` lists them. |
| `resource` | Address or resource string. Defaults to `sim://`. |
| `timeout` | I/O timeout in seconds. Defaults to 10. |
| `options` | Extra keyword arguments passed to the driver's `connect`. |

Instruments connect on **first use**, so a suite that only touches the scope does
not need the PSU powered up.

---

## 3. Test specification

```yaml
name: Clock distribution timing
description: Verify the clock fan-out skew and period.
requirements: [SYS-REQ-042, SYS-REQ-043]

setup:                       # once, before all tests
  - do: scope.configure_channel
    with: {channel: 1, volts_per_div: 1.0, position_div: -4.0}
  - do: scope.set_time_per_div
    with: {seconds_per_div: 200.0e-9}
  - do: scope.configure_edge_trigger
    with: {source: 1, level: 1.65, slope: RISE, mode: NORMAL}

tests:
  - name: Rising-edge skew within 20 ns
    requirement: SYS-REQ-042
    steps:
      - do: scope.measure_channel_spread
        with: {channels: [1, 2, 3, 4], direction: RISE}
        expect:
          - name: rising_skew_spread
            measure: "1.spread"      # see §5
            unit: s
            scale: 1.0e9             # state the limit in ns
            display_unit: ns
            max: 20.0

teardown:                    # once, after all tests, whatever the outcome
  - do: scope.run
    with: {continuous: true}
```

### 3.1 Structure

| Key | Required | Meaning |
|---|---|---|
| `name` | yes | Suite name; appears in every report |
| `description` | no | Free text |
| `warning` | no | A hazard, printed before anything is energised; gates the run on real hardware |
| `requirements` | no | Requirements the suite as a whole addresses |
| `instruments` | no | Alias to driver name, declaring what kind of instrument each alias must be |
| `setup` | no | Steps run once before the tests |
| `tests` | yes | One or more named tests |
| `teardown` | no | Steps run once after the tests, in a `finally` |

**A setup failure aborts the suite.** Every measurement taken after an unknown
setup would be meaningless, so none are attempted.

#### `warning`: a hazard the operator must see first

Some suites are dangerous to run with the bench in its normal state — they
energise outputs, put a meter on a current range, or drive a line that
something is connected to. `warning` says so, and the runner prints it
**before the bench is opened**, on the error stream so that redirecting the
output does not hide it:

```yaml
warning: |
  DISCONNECT EVERYTHING FROM THE INSTRUMENTS BEFORE RUNNING THIS TEST.
  This test energises the supply output.
```

On a bench that is not simulated the run then stops until the warning is
acknowledged:

* `--acknowledge` confirms it up front, which is how an unattended hardware run
  is done.
* At a terminal, the runner asks. Only the full word `yes` counts — `y` is not
  confirmation of a warning about damaging equipment.
* Refusing exits **3**, distinct from a test failure, and no instrument is
  opened.

A **simulated** run is never gated: nothing is energised, and there is nobody
to ask. That is what keeps a warned specification runnable in CI.

The reason the gate exists rather than a printed line alone is that the
consequence of ignoring this particular warning is silent — something wired to
the bench is damaged, and no report says so.

The `instruments` block states what each alias has to be:

```yaml
instruments:
  probe: jlink
  scope: tek3014b
```

It does two things. It makes `--simulate` work for a suite that spans more than one
kind of instrument — without it, every alias would be simulated as the same driver.
And it is checked against the bench before the first step runs, so pointing a suite
at the wrong rig is reported as

```
the specification wants instrument 'probe' to be a JLinkProbe,
but bench 'lab2' provides a Tek3014B
```

rather than failing four steps later on a method that does not exist. Driver
aliases are resolved before comparing, so `tds3014b` and `tek3014b` are the same
answer.

### 3.2 A test

| Key | Required | Meaning |
|---|---|---|
| `name` | yes | Test name |
| `requirement` | no | Requirement verified; may be a list |
| `description` | no | Free text |
| `warning` | no | A hazard, printed before anything is energised; gates the run on real hardware |
| `steps` | yes | Steps executed in order |
| `skip` / `skip_reason` | no | Mark the test unrun, with a reason |

### 3.3 A step

| Key | Required | Meaning |
|---|---|---|
| `do` | yes | `<instrument>.<method>`, or a built-in action |
| `with` | no | Keyword arguments for the call (alias: `args`) |
| `expect` | no | Measurements to extract and check |
| `save` | no | Keep the result under this name |
| `description` | no | Free text |
| `warning` | no | A hazard, printed before anything is energised; gates the run on real hardware |

`do` names a **public** method of a bench instrument. Private names are refused: a
specification is data, possibly written by someone who is not reviewing the
driver. Get the method list from `benchtools scope --help`, from the driver's
docstrings, or by running a wrong name — the error lists what is available.

`do` may also name a **property** — a reading with no arguments, such as
`dongle.firmware_version`. It is read when the step runs, and `with:` is an
error:

```yaml
- do: dongle.protocol_is_compatible
  expect: [{name: compatible, equals: 1}]
- do: dongle.firmware_version
  save: firmware
```

Built-in actions not bound to an instrument:

| Action | Arguments | Purpose |
|---|---|---|
| `sleep` | `seconds` | A settling time, stated explicitly rather than hidden in a driver |

### 3.4 Values a test requires, from a file

A step's arguments do not have to be written in the specification. Where an
instrument supports it, a file can carry them — the S2-LP driver reads the
register values a test requires from a file of names and hex values:

```yaml
setup:
  - do: s2lp.apply_configuration
    with: {source: configs/s2lp_915_38k4_basic.regs}

tests:
  - name: The radio holds the values this suite requires
    steps:
      - do: s2lp.verify_configuration
        with: {source: configs/s2lp_915_38k4_basic.regs, strict: true}
        expect: [{name: configured, measure: matches, equals: 1}]
```

This keeps two things that change at different rates apart: the settings, worked
out by whoever characterised the radio, and the test, written by whoever decides
what must be proven. A relative path is found beside the specification first,
so the file means the same thing wherever the runner is started from - see
[§6.2](#62-relative-paths-and-where-the-runner-is-started).

`configs/` holds the shipped examples. See
[S2-LP Devkit Notes §3.3](../docs/s2lp/S2LP_Devkit_Notes.md) for the file format
and what it refuses.

### 3.5 A command and response document

A sensor's command set is written down before anyone tests it. Copying those
commands into a specification makes two things that must agree, and they stop
agreeing the first time someone adds a command to one of them. So the document
is the test: `dongle.run_script` reads it and runs it.

```markdown
## Identity

| Step | Command    | Expected response    | Notes |
|------|------------|----------------------|-------|
| 1    | rd version | /^[0-9]+\.[0-9]+\.[0-9]+$/ | The build decides which |
| 2    | rd id      | /^SENS-[0-9A-F]{6}$/ | Matches the advertising name |
| 3    | delay 100  |                      | |
| 4    | log start  |                      | Nothing promised |
```

Each `##` heading is a test; each row is a step. Extra columns are ignored, so a
document can carry notes and requirement references. Three kinds of step, and
only the first can fail:

| Row | Result |
|---|---|
| A command with an expected response | **pass** if the reply matches, **fail** if it does not or none arrives |
| `delay <milliseconds>` | **skip** — waiting is not a claim about the sensor |
| A command with an empty expected cell | **skip** — sent, and whatever comes back within a short window is recorded |

An expected response is matched exactly after trimming; written `/like this/` it
is a regular expression, for a reply carrying a value that varies. Anchor it
with `^` and `$` to require the whole reply. A pipe inside any cell is written
`\|` - `/^ACK = (ENABLED\|DISABLED)$/` - as in GitHub's markdown; an unescaped
one ends the cell.

The specification that runs the document holds no commands at all:

```yaml
- do: dongle.run_script
  with: {source: specs/sensor_commands.md, report: ble_commands.md}
  expect:
    - {name: command_steps_failed, measure: failed, equals: 0}
    - {name: command_steps_passed, measure: passed, minimum: 1}
```

`failed`, not `passed`, is the verdict: a run passes when no step failed. The
second expectation is what stops a document of delays and fire-and-forget
commands reading as a document that checked everything.

The report it writes has a row per step — test, step, command, response,
expected response, the time from the end of the command to the start of the
response at 10 ms resolution, and the result — and the session log
(`dongle.start_log`) carries the whole exchange with a note marking each test.
`specs/sensor_commands.md` and `specs/sensor_commands.yaml` are the worked
example; a document that would not parse, or would not pass against the
simulated sensor, fails the suite's own tests.

#### Variables, connecting, and running a document on its own

A document can take parameters and open its own link, so one file tests any
sensor it is pointed at. `specs/templates/ble_sensor_test.md` is the template
to copy.

```markdown
| Variable  | Default | Notes |
|-----------|---------|-------|
| SENSOR_ID |         | Required |
| SETTLE_MS | 500     |       |

## Connect and identify

| Step | Command              | Expected response      |
|------|----------------------|------------------------|
| 1    | connect ${SENSOR_ID} |                        |
| 2    | delay ${SETTLE_MS}   |                        |
| 3    | rd version           | /^ACK rd version = V11/ |
| 4    | disconnect           |                        |
```

- **Variables** are declared in a `| Variable | Default |` table before the first
  step and used as `${NAME}` in any command, expected response or delay. One
  with no default must be given a value. Using an undeclared variable, or
  giving a value for one, is an error naming the line.
- **`connect <sensor>`** scans for 10 s, selects the sensor by address or by a
  fragment of its advertised name (any case, strongest match), and opens the
  link, trying up to three times. A link the document opened is closed when
  the run ends, pass or fail.
- **`disconnect`** closes the link.
- **`<disconnect>`** as the expected response says the sensor will drop the
  link after the command - a reset. The command is sent without waiting for a
  reply, and the time to the disconnection is measured on the dongle's clock.
- A **Timeout** column, in milliseconds, sets how long a step waits: for a
  reply, a listening window, the link to drop, or a connect. Empty uses the
  run's default (`--timeout-s`, 3 s). Some commands take longer than others;
  waits over 2 s need dongle firmware 1.3 (`cmd <hex> timeout=<ms>`).
- A **Note** column is carried into the report beside the result.
- A **Frames** column says how many reply frames - notifications - a command
  must produce, usually `1`: a sensor that answers twice leaves every later
  command reading the previous one's reply. The step listens 0.5 s after the
  reply, fails on a different count naming the extra frames, and logs each as
  an `RX` event. A Frames cell is a claim even with no expected response.
- A **Save** column names a variable to keep the step's reply in; later steps
  use it as `${NAME}`, so a value read before an action can be compared with the
  one after it. A pattern's first named group - `(?P<value>...)` - saves just
  that part. Only a reply that passed its check, or had nothing expected of it,
  is saved; a step using a value that was never saved is an error. Inside a
  pattern the saved value is matched literally.
- Tables that name none of the step columns - a legend, a conversion table -
  are prose and are left alone.

Every step gets one result, the first of these that applies:

| Result | When |
|---|---|
| **ERROR** | The system returned a failure code: the dongle refused the command, a connect or disconnect failed, or no reply came where one was expected |
| **SKIP** | The expected cell is empty - a delay, a connect or disconnect that worked, or a command nothing was promised for |
| **FAIL** | The reply differs from the expected one, or the link stayed up after a `<disconnect>` step |
| **PASS** | The reply matches, or the link dropped as expected |

The run is **ERROR** if any step errored, else **FAIL** if any failed, else
**PASS**. The report has a row per step: command, expected, actual, response
time (to 10 ms), result and note.

A document that connects runs on its own:

```
benchtools ble --resource COM10 script specs/templates/ble_sensor_test.md \
    --var SENSOR_ID=5C1712 --report results.md --events events.log
```

It prints the run as JSON and exits 0 when every checked step passed, 1 when one
failed or errored, or the run could not start. `--events` writes the event
log: one tab-separated line per event - `time`, `event`, `step`, `data`,
`result` - where the events are `TX`, `RX`, `DELAY`, `CONNECT`, `DISCONNECT` and
`ERROR`. The time is the host's, to the millisecond; each `RX` line carries the
dongle's own measurement of the exchange, to the microsecond. From a
specification, pass the values with `variables` and the log with `events`:
`{do: dongle.run_script, with: {source: ..., variables: {SENSOR_ID: 5C1712},
events: events.log}}`.

A `<disconnect>` whose reason is `0x08` was a supervision timeout: the sensor
went silent, and the measured time includes the dongle's 4 s wait to decide
the link had gone.

A link that drops without being asked - a sensor that crashes or resets -
is found before the next step, even when it happened during a delay. It is
logged once as a `DISCONNECT` event, with the reason and the dongle's time,
against the step during or after which it happened. Every step after it, up to
the next `connect`, is **ERROR** with that reason and is not sent; a `connect`
recovers and the run goes on.

The template's *Build identity* test reads the sensor's `rd id`, `rd sha`
(the firmware's git commit), `rd compiler` and `rd pcb`, and checks the ID
against `${SENSOR_ID}`. A pattern starting `(?i)` ignores case.

`${NAME}` is Robot Framework's variable syntax, and each row is one keyword
call; the template ends with the mapping, for when these documents move to
Robot Framework.

### 3.6 Values a later step takes from an earlier one

A bench test is rarely a list of independent actions. The identifier read off a
part decides which radio to connect to; the version a build produced decides
what the firmware must report. Write those into the specification and the test
asserts its own input: it passes on the wrong board, and it goes stale the day
someone rebuilds the firmware.

`save:` keeps a step's result under a name. Any later step can then use it —
as an argument, or as a limit — by writing `{from: <name>}`:

```yaml
- do: probe.read_integer
  with: {address: 0x10001081, size: 3, byteorder: big}
  save: sensor_id

- do: dongle.scan
  with:
    duration: 3.0
    name: {from: sensor_id, format: "{:06X}"}      # the dongle matches a name containing this
```

| Key | Meaning |
|---|---|
| `from` | The `save` name, optionally with a path into it: `build.version` |
| `format` | Optional [`str.format`](https://docs.python.org/3/library/string.html#formatstrings) template, for when the thing on the wire is a rendering of the value rather than the value |

The path after the name is the same dotted form as `measure` (§5), so
`{from: reading.voltage}` works on a step that saved a result object.

As a limit, a reference is what makes a comparison between two independently
established facts expressible:

```yaml
- do: probe.image_build          # what the build system recorded
  save: build

- do: dongle.command             # what the board says over the air
  with: {request: "rd version"}
  expect:
    - name: reported_version
      measure: text
      equals: {from: build.version}
```

A tolerance may accompany a numeric reference (`equals: {from: x}`,
`tolerance: 0.1`); a bound may not — use one or the other. A reference to a name
nothing has saved is an **error**, and the message lists what has been saved,
because a reference to a step that has not run yet is invisible in the
specification itself.

`specs/sensor_bringup.yaml` is the worked example: it reads a board's identifier
off the part, finds that board over the air by it, and compares what the board
reports with what was flashed onto it.

### 3.7 Parameters: values named once, at the top

The values a reader is most likely to want to change - a tolerance, how many
readings, which sensor - belong where they can be found, not scattered through
the steps. A `parameters` block names them, and `{param: <name>}` stands for one
anywhere below: an argument, a bound, a tolerance.

```yaml
parameters:
  readings: 5
  mcu_vs_machine_c: 5.0
  alive_period_s: 10

setup:
  - do: dongle.command
    with:
      request: {param: alive_period_s, format: "WR ALIVE-PERIOD {}"}   # -> "WR ALIVE-PERIOD 10"

tests:
  - name: The MCU temperature agrees with the machine temperature
    steps:
      - do: rtt.rtt_samples
        with: {pattern: 'MCU Temperature:\s*(-?\d+)mC', count: {param: readings}, scale: 0.001}
        expect:
          - name: mcu_highest_from_machine
            measure: maximum
            equals: {from: ble.mean}
            tolerance: {param: mcu_vs_machine_c}
```

`format` renders the value into text, for a command that carries it. A name the
block does not define is refused, and the message lists those it does. The
values a run used are in its JSON record and at the top of its report, so a
result can always be read against the limits that produced it.
`specs/kepler_temperature.yaml` is the worked example.

### 3.8 Repeated readings

`dongle.sample_command`, `probe.rtt_samples` and `s2lp.kepler_samples` each take
N readings of one quantity - a reply, a log line, a decoded frame field - and
return them with their statistics. A limit then applies to the set:

| `measure` | Meaning |
|---|---|
| `count` | readings taken; compare with how many were asked for, since a quiet source returns fewer rather than raising |
| `minimum`, `maximum`, `mean` | as named |
| `spread` | highest less lowest: how far the readings moved |

Bounding `minimum` and `maximum` against another source's `mean` puts every
reading inside the window, not just their average.

---

## 4. Limits

A measured value on its own is not a result. The limit is the part a reviewer
reads.

| Form | Keys | Example |
|---|---|---|
| Upper bound | `max` | `max: 20.0` |
| Lower bound | `min` | `min: 1.0` |
| Both | `min`, `max` | `min: 0.9`, `max: 1.1` |
| Nominal, absolute window | `nominal`, `tolerance` | `nominal: 3.3`, `tolerance: 0.1` |
| Nominal, relative window | `nominal`, `tolerance_percent` | `nominal: 1.0`, `tolerance_percent: 1.0` |
| Exact | `nominal` alone | `nominal: 4` |
| Exact, text | `equals` with a string | `equals: "1.4.2"` |
| Taken from an earlier step | `equals` with a reference | `equals: {from: build.version}` |

`minimum`/`maximum`/`equals` are accepted as the long forms. Bounds are inclusive.
A failure states by how much the value missed:

```
rising_skew_spread: 25 is above the maximum 20
period: 1.02 is 0.02 from nominal 1, outside +/- 0.01
"1.3.9" != required "1.4.2"
```

A limit written as text compares as text: no scaling, exact on the stripped
value, and the report shows the text rather than a number. Exact on purpose —
a looser rule would pass `1.4.20` for `1.4.2`, which is the failure such a limit
exists to catch. See §3.6 for taking one from an earlier step.

### 4.1 Units and `scale`

Write the limit in whatever unit reads naturally and use `scale` to get there:

```yaml
- name: skew
  measure: "1.spread"
  unit: s              # what the driver returns
  scale: 1.0e9         # multiply by this before checking
  display_unit: ns     # what the report shows
  max: 20.0            # so this is 20 ns
```

Both the scaled and the raw value are kept in the JSON record.

### 4.2 How the value reads: `format`

Some values are not decimal numbers to the person reading the report. An
identifier, an address, a register mask: 662316 and `0A1B2C` are the same value,
and only one of them can be compared with what is printed on the board.

```yaml
- name: sensor_id
  format: "{:06X}"       # how it is reported
  min: 1
  max: 16777214          # how it is checked
```

```
| sensor_id | 0A1B2C | >= 000001, <= FFFFFE | PASS |
```

`format` is presentation only. The limit is still checked against the number,
the bounds are rendered the same way so the two read together, and the number
stays in the JSON record as `raw_value` — a report a person reads and a record a
tool computes with want different things, and this is not a reason to give up
either. It applies after `scale`. A template that cannot be applied to the value
is an **error**, not a quiet fall back to the number: a broken specification
should not hide behind a result that looks right.

---

## 5. Addressing a value inside a result: `measure`

Driver methods return what suits them — a float, a dataclass, a dict keyed by
channel, or a tuple. `measure` is a dotted path applied left to right; each element
is tried as a mapping key, then a sequence index, then an attribute, then a
zero-argument method.

| `measure` | Resolves to | For a method returning |
|---|---|---|
| *(omitted)* | the whole result | a float, e.g. `measure_period` |
| `spread` | `result.spread` | a result object |
| `1.spread` | `result[1].spread` | `(waveforms, SpreadResult)` |
| `1.skews.3` | `result[1].skews[3]` | as above, then a channel-keyed dict |
| `1.peak_to_peak_jitter` | `result[1].peak_to_peak_jitter` | `(waveforms, PeriodResult)` |
| `length` | how many | a method returning a list, e.g. `dongle.scan` |

Dict keys are tried as text and then as an integer, because YAML gives `3` as a
string while a channel-keyed dict uses `int`.

A path that does not resolve is an **error**, not a failure, and the message names
the element that could not be resolved.

`length` is worth knowing for a step that returns a list: `measure: length` with
`min: 1` makes "the scan found the board" a limit that can fail. Addressing
element `0` instead would *error* on an empty list, and "nothing was found" is a
test result, not a broken bench. A mapping key or attribute of that name still
wins.

### 5.1 Useful paths for the oscilloscope

| Method | Returns | Useful paths |
|---|---|---|
| `measure_period`, `measure_frequency`, `measure_amplitude`, `measure_delay` | float | *(omit `measure`)* |
| `measure_channel_spread` | `(waveforms, SpreadResult)` | `1.spread`, `1.skews.<n>`, `1.earliest_channel`, `1.latest_channel`, `1.standard_deviation` |
| `measure_period_host` | `(waveforms, PeriodResult)` | `1.mean`, `1.minimum`, `1.maximum`, `1.standard_deviation`, `1.peak_to_peak_jitter`, `1.frequency`, `1.count` |
| `capture_single` | `{channel: Waveform}` | `<n>.peak_to_peak`, `<n>.mean`, `<n>.clipped_sample_count` |

### 5.2 Useful paths for the debug probe

| Method | Returns | Useful paths |
|---|---|---|
| `read_variable`, `read_word`, `read_u8`, `variable_address`, `evaluate` | a scalar | *(omit `measure`)* |
| `read_integer` | a scalar, `size` bytes in the `byteorder` given | *(omit `measure`)* — for a record whose width and byte order are its own, not the core's |
| `rtt_samples` | `SampleSet` | `count`, `minimum`, `maximum`, `mean`, `spread` (§3.8) |
| `measure_time_between` | `TimingResult` | `microseconds`, `milliseconds`, `cycles`, `spread`, `standard_deviation`, `minimum`, `maximum`, `count`, `is_trustworthy`, `halts_target`, `resolution_seconds` |
| `flash` | `FlashResult` | `bytes_written`, `verify.matched`, `seconds`, `sections` |
| `verify` | `VerifyResult` | `matched`, `mismatched`, `sections` |
| `call_stack` | `[StackFrame]` | `0.function`, `0.line`, `0.file` — and the list itself for a depth limit |
| `wait_for_halt`, `halt` | `HaltInfo` | `reason`, `line`, `file`, `function`, `address`, `breakpoint_number` |
| `rtt_read_lines` | `[str]` | the list itself, or `length` |
| `rtt_lines_within` | how many lines arrived | *(omit `measure`)* — `min: 1` is "it is running" |
| `rtt_command`, `rtt_expect` | a regular-expression match | `1` for the first group, `0` for the whole match |
| `image_build` | `FirmwareBuild` | `version`, `built` — what the build system recorded about the image that was flashed |

Two of these are worth asserting on beside any timing limit:

```yaml
- do: probe.measure_time_between
  with: {start: sensor.c:40, end: sensor.c:75, method: CYCLE_COUNTER, repeat: 20}
  expect:
    - name: acquisition_time
      measure: milliseconds
      unit: ms
      max: 1.2
    - name: measurement_is_resolvable
      measure: is_trustworthy       # false if the method cannot resolve the interval
      equals: 1
    - name: firmware_kept_running
      measure: halts_target         # 0 requires a non-intrusive method
      equals: 0
```

A boolean is compared as `1` or `0`, since a limit is numeric throughout.

A limit on a figure whose method cannot resolve it is not a test, so the runner
gives you the means to say so in the specification rather than in a comment.

### 5.3 Useful paths for the BLE dongle

| Method | Returns | Useful paths |
|---|---|---|
| `scan` | `[Sensor]` | `length`, `0.rssi`, `0.name`, `0.address` |
| `select`, `open_link` | `Sensor` | `address`, `name`, `rssi` |
| `measure_advertising_profile` | `AdvertisingProfile` | `mean_interval_s`, `minimum_interval_s`, `maximum_interval_s`, `spread_s`, `jitter_s`, `expected_jitter_s`, `rate_hz`, `count`, `missed_events`, `expected_events`, `duty_cycle`, `reception_ratio`, `is_complete`, `lost_reports` |
| `measure_response_time` | `ResponseTiming` | `milliseconds`, `seconds`, `minimum_s`, `maximum_s`, `spread_s`, `standard_deviation_s`, `count`, `is_trustworthy`, `quantisation_s` |
| `command` | `ResponseSample` | `text`, `dongle_us`, `host_s` |
| `write` | `int` | *(omit `measure`)* |

Three of these belong in a specification beside the limits, not in a comment:

```yaml
- do: dongle.measure_advertising_profile
  with: {duration: 5.0, expected_interval: 0.100}
  expect:
    - name: mean_interval
      measure: mean_interval_s
      unit: s
      scale: 1000.0
      display_unit: ms
      min: 99.0                 # a conforming sensor sits ABOVE nominal:
      max: 112.0                # advDelay adds 0-10 ms to every interval
    - name: missed_events
      measure: missed_events
      max: 0
    - name: capture_was_lossless
      measure: is_complete      # 0 means the host lost reports, so a missed
      equals: 1                 # beacon cannot be blamed on the sensor
```

A limit of "100 ms ± 1 ms" fails every conforming sensor, because the Bluetooth
specification *requires* a random 0-10 ms advertising delay. See
`docs/ble/BLE_Dongle_Notes.md` §4.1.

---

## 6. Running

```bash
# Against simulators: no hardware, no bench file
benchtools run specs/clock_skew.yaml --simulate

# Against a rig
benchtools run specs/clock_skew.yaml --bench benches/lab1.yaml

# Several suites, with all three report formats
benchtools run specs/*.yaml --bench benches/lab1.yaml \
    --json results.json --markdown report.md --junit results.xml
```

| Option | Effect |
|---|---|
| `--bench PATH` | Bench configuration |
| `--simulate` | Replace every instrument with its simulator |
| `--json`, `--markdown`, `--junit` | Write reports (paths are suffixed per suite when several are given) |
| `--stop-on-error` | Abandon the remaining tests after the first error |
| `-v`, `-vv` | Log each step, then full debug including SCPI traffic |

### 6.1 Exit status

| Status | Meaning |
|---|---|
| 0 | Everything passed |
| 1 | A test failed, or a step could not be executed |
| 2 | Usage or specification error |

So the command is usable directly as a CI step.

### 6.2 Relative paths, and where the runner is started

The runner is normally started in the repository of the firmware under test, not
in this one, so a specification or bench file cannot rely on the working
directory to find what it names (#116):

```bash
cd ~/firmware-under-test
benchtools run ~/TestTools/specs/radio_link.yaml --simulate     # finds configs/ in TestTools
benchtools run ~/TestTools/specs/sensor_bringup.yaml \
    --bench ~/TestTools/benches/lab1.yaml                        # finds ./build here
```

**Input files** - a file a driver reads - given as a relative path are looked for
in this order, and the first that exists is used:

1. the directory of the file that names it: the specification for a step
   argument, the bench file for a bench option;
2. the working directory;
3. the TestTools checkout (where `configs/`, `specs/` and `benches/simulated/`
   live).

An absolute path is used as given. A step argument found nowhere is an **error**
that lists every location searched. A bench option found nowhere is passed to the
driver unchanged, with the locations logged as a warning, because a simulator may
never read it; the driver that does read it reports what is missing.

Which arguments are input files is declared by each driver, not guessed:

| Driver | Input-file arguments |
|---|---|
| `s2lp` | `source` of `load_configuration`, `apply_configuration`, `verify_configuration` |
| `ble-dongle` | bench option `firmware`; `firmware` of `expect_firmware`, `check_firmware`, `update_firmware`, `ensure_firmware`; `source` of `run_script` |
| `jlink`, `jlink-rtt` | bench options `elf`, `firmware`; `elf` of `load_symbols`; `path` of `flash`, `image_build`, `verify` |
| `gpd3303d`, `tti1604`, `tek3014b`, `pico-sht30` | none |

**Output files** - logs, reports, screenshots, `--json`/`--markdown`/`--junit` -
are written relative to the working directory, as before. A run started in the
firmware repository leaves its logs there.

A file beside the specification wins over one of the same name in the working
directory. To use a different register file from a shipped specification, copy
the specification, or give an absolute path.

---

## 7. Failure versus error — read this before interpreting a report

| Outcome | Meaning | What to do |
|---|---|---|
| **PASS** | Every measurement met its limit | — |
| **FAIL** | A measurement was outside its limit | The bench worked; the thing under test did not meet its requirement |
| **ERROR** | A step could not be executed | The test told you nothing. Fix the rig or the specification, then re-run |
| **SKIP** | Marked unrun | — |

The distinction is carried through the JSON record, the markdown report and JUnit
XML (`<failure>` versus `<error>`). Conflating them turns a broken rig into a pile
of apparent product defects and hides the real ones.

A requirement's outcome is the **worst** of its tests, so a requirement covered by
one passing and one skipped test is reported as SKIP: it is not fully verified.

---

## 8. Simulated runs are always disclosed

A run is recorded as simulated when `--simulate` is used **or** when no instrument
on the bench is real hardware, and every report says so:

> Run against simulated instruments. These results verify the specification and
> the tooling, **not** any physical hardware.

One real instrument makes it a hardware run. Do not present a simulated report as
a measurement result.

### 8.1 Which instruments made the measurements

Every run records what the bench actually was — driver, model, serial number,
resource, and the firmware build where the instrument reports one — for the
instruments the run *used*. It is recorded after the run rather than before, so
an instrument the suite refreshed in setup is recorded as the one that produced
the numbers, and an instrument that would not identify is recorded with its
error rather than dropped.

The markdown report carries it beside the verdict:

| Alias | Driver | Model | Firmware | Resource |
|---|---|---|---|---|
| dongle | NordicDongle | PCA10059 | 1.1.0 (built 2026-09-13T12:00:00Z) | /dev/ttyACM0 |

and the JSON record carries the same under `instruments`. A measurement without
the instrument that made it is not evidence; for anything programmable, the
firmware build decides whether the number means what it appears to mean.

---

## 9. Developing a specification

1. Write it against `--simulate` first. Every driver ships a simulator, so the
   structure, paths and limits can be debugged with no hardware.
2. Run with `-vv` to see each step and the SCPI it produces.
3. A wrong method name lists the available methods; a wrong `measure` path names
   the element that failed to resolve.
4. Only then point it at a bench.

A specification that runs green against simulators is not evidence about hardware,
but it is evidence that the specification itself is sound — which is the part worth
debugging without a rig attached.

---

## 10. Adding an instrument to the runner

A new driver becomes available to specifications by registering it:

```python
from benchtools.runner import register_driver
from my_package import PowerSupply

register_driver("psu-1234", PowerSupply)
```

A bench configuration can then name `driver: psu-1234`. The driver must subclass
`benchtools.core.instrument.Instrument` — `ScpiInstrument` for anything speaking
SCPI, `Instrument` directly for anything that does not, as the J-Link driver does.
If it sets `SIMULATOR_CLASS`, it works against `sim://` immediately, and so does
every specification that uses it.

What the runner requires of a driver is only this: a `connect` classmethod, the
context-manager lifecycle, `identify`, and public methods that return plain values
or objects a dotted `measure` path can walk. Anything meeting that is a bench
instrument, whatever it speaks on the wire.

An argument that names a file the driver reads must be declared, so the runner
finds it from wherever it is started ([§6.2](#62-relative-paths-and-where-the-runner-is-started)):

```python
from benchtools.core.paths import input_paths

class PowerSupply(Instrument):
    @classmethod
    @input_paths("profile")          # beneath @classmethod / @staticmethod
    def connect(cls, resource, profile=None, **options): ...

    @input_paths("source")
    def load_sequence(self, source): ...
```

Do not declare an output path: it is written relative to the working directory.
