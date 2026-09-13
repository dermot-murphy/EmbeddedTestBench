# Bench Runner Guide

How to write a test specification and a bench configuration, and how to run them.

| Field | Value |
|---|---|
| Document ID | BENCHTOOLS-GUIDE-001 |
| Version | 1.0 |
| Date | 2026-09-13 |
| Applies to | `benchtools` 2.0.0 |

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
    driver: generic             # no dedicated driver yet: identify and raw SCPI
    resource: 192.168.1.60
```

The alias on the left (`scope`, `psu`) is what a specification refers to.

Shorthand, when the defaults suffice:

```yaml
instruments:
  scope: tek3014b@192.168.1.50
  psu: generic@sim://
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
| `requirements` | no | Requirements the suite as a whole addresses |
| `setup` | no | Steps run once before the tests |
| `tests` | yes | One or more named tests |
| `teardown` | no | Steps run once after the tests, in a `finally` |

**A setup failure aborts the suite.** Every measurement taken after an unknown
setup would be meaningless, so none are attempted.

### 3.2 A test

| Key | Required | Meaning |
|---|---|---|
| `name` | yes | Test name |
| `requirement` | no | Requirement verified; may be a list |
| `description` | no | Free text |
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

`do` names a **public** method of a bench instrument. Private names are refused: a
specification is data, possibly written by someone who is not reviewing the
driver. Get the method list from `benchtools scope --help`, from the driver's
docstrings, or by running a wrong name — the error lists what is available.

Built-in actions not bound to an instrument:

| Action | Arguments | Purpose |
|---|---|---|
| `sleep` | `seconds` | A settling time, stated explicitly rather than hidden in a driver |

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

`minimum`/`maximum`/`equals` are accepted as the long forms. Bounds are inclusive.
A failure states by how much the value missed:

```
rising_skew_spread: 25 is above the maximum 20
period: 1.02 is 0.02 from nominal 1, outside +/- 0.01
```

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

Dict keys are tried as text and then as an integer, because YAML gives `3` as a
string while a channel-keyed dict uses `int`.

A path that does not resolve is an **error**, not a failure, and the message names
the element that could not be resolved.

### 5.1 Useful paths for the oscilloscope

| Method | Returns | Useful paths |
|---|---|---|
| `measure_period`, `measure_frequency`, `measure_amplitude`, `measure_delay` | float | *(omit `measure`)* |
| `measure_channel_spread` | `(waveforms, SpreadResult)` | `1.spread`, `1.skews.<n>`, `1.earliest_channel`, `1.latest_channel`, `1.standard_deviation` |
| `measure_period_host` | `(waveforms, PeriodResult)` | `1.mean`, `1.minimum`, `1.maximum`, `1.standard_deviation`, `1.peak_to_peak_jitter`, `1.frequency`, `1.count` |
| `capture_single` | `{channel: Waveform}` | `<n>.peak_to_peak`, `<n>.mean`, `<n>.clipped_sample_count` |

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
`benchtools.core.scpi.ScpiInstrument`; if it sets `SIMULATOR_CLASS`, it works
against `sim://` immediately, and so does every specification that uses it.
