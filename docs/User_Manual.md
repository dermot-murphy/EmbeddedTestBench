# Embedded Test Bench — User Manual

| | |
|---|---|
| Applies to | Release `v0.01.0000` and `develop` after it |
| Issue | #196 |
| Audience | An engineer new to the bench, and a Claude Code session working in this repository ([§8](#8-for-claude-code-sessions)) |

This manual takes you from nothing to a working run, then on to the real bench.
It does not repeat the reference material; it points to it:

| For | Read |
|---|---|
| Every key of a specification and a bench file | [Bench Runner Guide](Bench_Runner_Guide.md) |
| Setting up a PC for the real instruments | [Bench Self-Check Setup](Bench_Self_Check_Setup.md) |
| One instrument in depth | The notes under `docs/<instrument>/` (listed in [docs/README.md](README.md)) |
| What the release contains, and its known problems | ETB-SVD-001, [Software Version Description](aspice/EmbeddedTestBench_SVD_Software_Version_Description.md) |
| What has been shown on hardware | ETB-SYS5-002, [System Qualification Test Report](aspice/EmbeddedTestBench_SYS5_002_System_Qualification_Test_Report.md) |

Every command and output in this manual was run in the session that wrote it
(2026-10-05, Windows 10, Python 3.14, on the **simulated** bench), or read from
the code. Output is abbreviated with `...`. Nothing here was run against real
instruments; statements about the real bench are taken from the documents
cited beside them.

---

## Contents

1. [What it is](#1-what-it-is)
2. [Installing](#2-installing)
3. [The first run: the simulated bench, end to end](#3-the-first-run-the-simulated-bench-end-to-end)
4. [The real bench](#4-the-real-bench)
5. [Writing tests](#5-writing-tests)
6. [Viewing and reporting](#6-viewing-and-reporting)
7. [The command-line tools](#7-the-command-line-tools)
8. [For Claude Code sessions](#8-for-claude-code-sessions)
9. [Troubleshooting](#9-troubleshooting)

---

## 1. What it is

Embedded Test Bench is a Python package, `benchtools`, plus the material around
it:

- **Instrument drivers**: a GW Instek GPD-3303D supply, a TTi 1604 multimeter, a
  Tektronix TDS3014B oscilloscope, a SEGGER J-Link debug probe, a Nordic BLE
  dongle, an ST S2-LP sub-GHz kit and a Raspberry Pi Pico 2 + SHT30-D
  thermometer.
- **A declarative test runner** (`benchtools run`). A *specification* says what
  to do and what counts as a pass. A *bench file* says which instruments are
  where. The runner produces JSON, Markdown and JUnit reports and an event log.
- **A browser viewer** (`benchtools view`) to watch, start and steer a run.
- **A GitHub Action** (`action.yml`) that runs specifications in CI.
- **Firmware** for two of the instruments: the Nordic dongle
  (`firmware/nordic_dongle`) and the Pico 2 thermometer (`firmware/pico_sht30`).
- **An ASPICE CL2 document set** under `docs/aspice/`.

The package has no mandatory third-party dependency. No VISA installation is
needed.

### The two modes

| | Simulated bench | Real bench |
|---|---|---|
| Instruments | In-process models, resource `sim://` | Hardware on serial ports, USB and LAN |
| How you choose it | `--bench benches/simulated_bench.yaml`, or `--simulate` | `--bench benches/bench_pc.yaml` (or your own copy of `benches/lab1.yaml`) |
| What a pass means | The specification and the tooling are sound | The thing under test met its requirement |
| Safety warnings | Printed, never gated | Printed, and the run waits for an acknowledgement ([§4.5](#45-the-bench-self-check-and-safety-warnings)) |
| Reports | Marked simulated in every format | Name each instrument's identity |

A simulated report is never evidence about hardware. Every report says which
kind it is, and nothing turns that off.

**`--simulate` and `simulated_bench.yaml` are not the same.** Both replace every
instrument with its simulator. Only the bench file also carries the instrument
*options*, such as where the firmware manifests are. A specification that
checks firmware against a manifest (`specs/sensor_bringup.yaml`) therefore
passes on `benches/simulated_bench.yaml` and fails with `--simulate`
([§9.2](#92-common-errors)).

---

## 2. Installing

Python **3.8 or later** (`requires-python = ">=3.8"` in `pyproject.toml`). CI
tests 3.8, 3.9 and 3.12.

### 2.1 From the release tag, without cloning

```sh
pip install "benchtools[spec] @ git+https://github.com/dermot-murphy/EmbeddedTestBench@v0.01.0000"
```

Add `serial` to the extras for a real bench ([§2.3](#23-the-extras)). Checked in a fresh virtual environment:

```
> benchtools --version
benchtools 0.01.0000
> pip show benchtools
Name: benchtools
Version: 0.1.0
```

`pip show` reports `0.1.0` because packaging normalises the version under PEP
440. Both name the same release (ETB-SVD-001 §5.1).

This installs the package only. The example specifications and bench files
(`specs/`, `benches/`, `configs/`) are in the repository, so for the first run
in [§3](#3-the-first-run-the-simulated-bench-end-to-end) use a checkout.

### 2.2 From a checkout

```sh
git clone https://github.com/dermot-murphy/EmbeddedTestBench
cd EmbeddedTestBench
git checkout v0.01.0000          # or stay on develop
pip install -e ".[spec,serial,test]"
```

### 2.3 The extras

| Extra | Brings | Needed for |
|---|---|---|
| *(none)* | nothing | Drivers, analysis, runner, viewer, JSON specifications |
| `spec` | PyYAML ≥ 5.1 | Reading `.yaml` specifications and bench files — every shipped one |
| `serial` | pyserial ≥ 3.4 | The supply, multimeter, dongle, S2-LP kit and thermometer on a real port |
| `visa` | pyvisa, pyvisa-py | Only if your site routes instruments through VISA |
| `plot` | matplotlib ≥ 3.3 | Host-side plots (`scope spread --plot`) |
| `test` | all of the above plus pytest, pytest-cov | Running the test suite |

For the simulated bench, `spec` is enough. For the real bench, `spec,serial`.

### 2.4 Running the tools

The console script is `benchtools`. `python -m benchtools` is the same program;
it is the form to use from a checkout when another installed copy of the
package might be first on `PATH`.

```
> python -m benchtools --version
benchtools 0.01.0000
```

### 2.5 Firmware toolchains (only if you build instrument firmware)

You do not need these to run tests. Versions are those pinned in
`.github/workflows/firmware.yml` (ETB-SVD-001 §5.5).

| Firmware | Toolchain | Build | Details |
|---|---|---|---|
| Nordic dongle, `firmware/nordic_dongle` | GNU Arm Embedded 10.3-2021.10, nRF5 SDK 17.1.0, `nrfutil` 6.1.7 for DFU | `make SDK_ROOT=/path/to/nRF5_SDK_17.1.0` | [BLE Dongle Notes](ble/BLE_Dongle_Notes.md) |
| Pico 2 thermometer, `firmware/pico_sht30` | Arm GNU Toolchain 14.2.Rel1, Pico SDK 2.1.1 | `PICO_SDK_PATH=... cmake -S . -B build && cmake --build build` | [Pico 2 + SHT30-D Notes](pico_sht30/Pico_SHT30_Notes.md) |

The J-Link driver needs two executables, not Python packages: SEGGER's J-Link
GDB Server and an ARM GDB (`arm-none-eabi-gdb`). See
[Bench Self-Check Setup §4](Bench_Self_Check_Setup.md#4-permissions-and-drivers)
and [J-Link Integration Notes](jlink/JLink_Integration_Notes.md).

---

## 3. The first run: the simulated bench, end to end

From the root of a checkout. Nothing here touches hardware.

### 3.1 Run a specification

`specs/sensor_bringup.yaml` is the worked example: power, dongle firmware, flash,
identity, RTT, radio and version, against `benches/simulated_bench.yaml`.

```sh
python -m benchtools run specs/sensor_bringup.yaml \
    --bench benches/simulated_bench.yaml \
    --json out/run.json --markdown out/run.md --junit out/run.xml \
    --event-log out/run.events.jsonl
```

(In PowerShell, put it on one line or continue lines with a backtick instead of
`\`.)

```
Sensor bring-up: PASS - 7 passed, 0 failed, 0 errored, 0 skipped in 0.05 s
  JSON    : out/run.json
  Markdown: out/run.md
  JUnit   : out/run.xml
```

The exit status is the verdict (`benchtools/runner/cli.py`):

| Status | Meaning |
|---|---|
| 0 | Everything passed |
| 1 | A test failed, or a step could not be executed |
| 2 | Usage or specification error |
| 3 | A safety warning was not acknowledged on a real bench; nothing was opened |

Every shipped specification that does not need a Kepler sensor passes on the
simulated bench. Checked on 2026-10-05, one at a time:

| Specification | Simulated bench |
|---|---|
| `bench_self_check`, `clock_skew`, `dongle_firmware`, `firmware_timing`, `kepler_battery`¹, `radio_link`, `sensor_ble`, `sensor_bringup`, `sensor_commands`, `sensor_power_signal_and_link`, `sensor_rails` | PASS |
| `kepler_preamble`, `kepler_temperature`, `kepler_version` | ERROR at setup: `dongle.select` of the real sensor's address `D1:8D:3B:4C:19:96` is refused. They need hardware; each file says so |

¹ `kepler_battery` and `bench_self_check` carry a safety warning. On the
simulated bench it is printed and the run carries on.

To run a single test case, name it exactly; the others are reported as skipped:

```
> python -m benchtools run specs/sensor_bringup.yaml --bench benches/simulated_bench.yaml --test "The board identifies itself"
Sensor bring-up: PASS - 1 passed, 0 failed, 0 errored, 6 skipped in 0.01 s
```

Several specifications in one command write one report each, suffixed `_1`,
`_2`, ...:

```
> python -m benchtools run specs/sensor_bringup.yaml specs/dongle_firmware.yaml --bench benches/simulated_bench.yaml --markdown out/multi.md
Sensor bring-up: PASS - 7 passed, 0 failed, 0 errored, 0 skipped in 0.01 s
  Markdown: out/multi_1.md
BLE dongle firmware identity: PASS - 3 passed, 0 failed, 0 errored, 0 skipped in 0.00 s
  Markdown: out/multi_2.md
```

### 3.2 Read the reports

**Markdown** — for a person. It opens with the verdict and the disclosure:

```markdown
# Bench test report: Sensor bring-up

| Field | Value |
|---|---|
| Result | **PASS** |
| Bench | Simulated bench (simulated) |
| Specification | specs/sensor_bringup.yaml |
...
> Run against simulated instruments. These results verify the specification and the tooling, **not** any physical hardware.

## Instruments

| Alias | Event | Driver | Model | Firmware | Resource |
|---|---|---|---|---|---|
| dongle | BLE | NordicDongle | PCA10059 | 1.4.0 (built 2026-09-13T12:00:00Z) | sim:// |
| probe | JLINK | JLinkProbe | J-Link V11 | V7.94e | sim:// |
| psu | PSU | Gpd3303D | GPD-3303D | V1.09 | sim:// |
...
### The board is powered at 3.2 V and is not in current limit

Result: **PASS** | Requirement: SYS-REQ-010 | Duration: 0.001 s

| Measurement | Value | Limit | Result |
|---|---|---|---|
| rail_voltage | 3.2 V | = 3.2 +/- 0.05 | PASS |
| rail_regulated | 1 | = 1 | PASS |
| rail_current | 0 A | <= 0.5 | PASS |
```

**JSON** — for a program. Top-level keys: `suite`, `bench`, `spec_source`,
`parameters`, `selection`, `simulated`, `status`, `started`, `finished`,
`duration_s`, `totals`, `instruments`, `requirements`,
`requirements_verified`, `setup_error`, `cases`. Each case has `name`,
`status`, `requirement`, `duration_s`, `error`, `skip_reason` and its `steps`
with their measurements.

```
"simulated": true, "status": "PASS",
"totals": {"total": 7, "passed": 7, "failed": 0, "errored": 0, "skipped": 0}
```

**JUnit XML** — for CI. One `<testcase>` per test; a FAIL is `<failure>`, an
ERROR is `<error>`; the bench and the simulated flag are properties:

```xml
<testsuite name="Sensor bring-up" tests="7" failures="0" errors="0" skipped="0" ...>
  <properties><property name="bench" value="Simulated bench" />
    <property name="simulated" value="true" /> ...
```

**Event log** (`--event-log`) — one JSON object per line: every instrument's
traffic and every runner step, each tagged with a `source` such as `PSU`,
`BLE`, `JLINK` or `TEST`. It is what the viewer reads. Its format is in the
[Bench Runner Guide §6.3–6.4](Bench_Runner_Guide.md#63-event-log-names-which-instrument-said-what).

**Read FAIL and ERROR differently.** FAIL: the bench worked and the thing under
test missed its limit. ERROR: a step could not run, so the test told you
nothing. See [Bench Runner Guide §7](Bench_Runner_Guide.md#7-failure-versus-error--read-this-before-interpreting-a-report).

### 3.3 Open the viewer

```
> python -m benchtools view
benchtools view: http://127.0.0.1:8130/  (Ctrl+C to stop)
```

Open the address in a browser. To look at the run you just made, give it the
event log:

```sh
python -m benchtools view --event-log out/run.events.jsonl --read-only
```

The Run page then shows "Sensor bring-up", PASS, and every step with its
result. `--read-only` refuses to start or control anything, which is right for
looking at a finished run. Stop the viewer with Ctrl+C.

You can also start a run from the viewer's **Start / attach** page: choose
`specs/sensor_bringup.yaml` and the bench `benches/simulated_bench.yaml`. Such a
run writes its event log, JSON and Markdown to `runs/` (change with `--runs`),
named `<date>-<time>-<spec>.*`, plus a `.console.txt` of the runner's output.
Checked: a run started this way on the simulated bench ended PASS.

That is the end-to-end path: run, report, view.

---

## 4. The real bench

### 4.1 The bench files

| File | What it is |
|---|---|
| `benches/bench_pc.yaml` | The Windows bench PC **as it exists**, qualified on 2026-10-04 (#176, ETB-SYS5-002). Use this one on that PC |
| `benches/lab1.yaml` | A commented example of every instrument. Copy it for a new bench and change the addresses |
| `benches/simulated_bench.yaml` | Every instrument simulated, with manifests. The one to use for [§3](#3-the-first-run-the-simulated-bench-end-to-end) and CI |
| `benches/simulated.yaml` | An older, smaller simulated bench: scope, probe and dongle |

A bench file names each instrument by an alias, with a `driver`, a `resource`,
a `timeout` and driver `options`. The format is in the
[Bench Runner Guide §2](Bench_Runner_Guide.md#2-bench-configuration);
`python -m benchtools drivers` lists the driver names.

### 4.2 The bench PC's instruments and ports

From `benches/bench_pc.yaml` and ETB-SYS5-002 §4.1:

| Alias | Instrument | Resource | USB serial number |
|---|---|---|---|
| `dongle` | Nordic PCA10059 BLE dongle, firmware 1.4.0 | COM10 | `D7FA0F34C85A` |
| `psu` | GW Instek GPD-3303D, SN GER916893, firmware V1.09, 9600 baud | COM11 (FTDI) | `A105X5XCA` |
| `dmm` | TTi 1604 multimeter | COM13 (FTDI FT232) | `A9LQ0R81A` |
| `temp` | Raspberry Pi Pico 2 thermometer, `firmware/pico_sht30` V1.00.0000 | COM14 | `AC5483CD0798FB0B` |
| `s2lp` | NUCLEO-L053R8 + STEVAL-FKI433V2, ST's CLI firmware | COM4 (ST-LINK VCP) | `066CFF515055657867182645` |
| `probe` | J-Link OB-SAM3U128-V2-NordicSem, S/N 682395790, on Kepler sensor **5C1712** | `jlink://` (USB) | — |
| `rtt` | The same J-Link, RTT only, never halting the target | `jlink://127.0.0.1:2341` | — |

There is **no oscilloscope** on this bench. A specification that needs `scope`
stops at connect and names the missing alias (ETB-SYS5-002 §6.7).
The SHT30-D module is **not yet wired** to the Pico (ETB-SYS5-002 §3.3): the
thermometer identifies itself but measures nothing real.

**Ports and identification.** COM numbers can change when a device is
re-plugged. Before a session, match each port to its USB serial number
(`python -m serial.tools.list_ports -v`, see
[Bench Self-Check Setup §3](Bench_Self_Check_Setup.md#3-find-the-ports)).
Then let each instrument identify itself, for example
`python -m benchtools psu -r COM11 info` ([§7](#7-the-command-line-tools)).
Every run records each instrument's model, serial number and firmware in its
report and JSON. A report that does not name the instruments is not evidence.

Some instruments need particular line settings. The driver applies them; the
notes explain them:

- **TTi 1604**: the driver asserts DTR and clears RTS, which power the meter's
  interface. A three-wire cable will not work ([TTi 1604 Notes](dmm/TTi1604_Notes.md)).
- **GPD-3303D**: replies end in a carriage return; the line rate must match the
  front panel's; keep `command_interval: 0.05` ([GPD-3303D Notes](psu/GPD3303D_Notes.md)).
- **S2-LP kit**: name the board (`board: STEVAL-FKI433V2`) so a mismatch fails
  at connect ([S2-LP Devkit Notes](s2lp/S2LP_Devkit_Notes.md)).

### 4.3 Safety limits

These are rules set by the owner. They are not enforced by the software, so
they are yours to keep.

#### The supply, while Kepler sensor 5C1712 is wired to it

From `specs/qualification/README.md` and ETB-SYS5-002 §4.4:

- The GPD-3303D stays in **INDEPENDENT** tracking. Never series or parallel:
  either could put up to twice the intended voltage on the sensor.
- Every voltage setpoint stays **between 2.8 V and 3.3 V**.
- **No output is switched on** unless the owner says otherwise for that run.
- **Never call `psu.reset()`**: it sets both channels to 0 V.

To switch the supply off, use `psu.all_outputs_off`: it opens the output
switch and leaves the setpoints alone.

Several shipped specifications break these limits. `specs/sensor_bringup.yaml`
sets 3.2 V **and switches the output on**. `specs/bench_self_check.yaml`
drives 1 V and switches it on. Read a specification's `psu` steps before you
run it on the bench PC. `specs/qualification/qs03_supply.yaml` is the example
that keeps within the limits.

#### The J-Link and the sensor

From `docs/jlink/JLink_Integration_Notes.md` §4.1–4.2,
`specs/qualification/README.md` and ETB-SYS5-002:

- **5C1712 is the only sensor approved for destructive tests** and
  configuration changes.
- **Back up the sensor before any erase or flash** (code flash and UICR, with
  `nrfjprog --readcode ... --readuicr`). A chip erase also erases UICR, and with
  it the sensor ID. `jlink flash --preserve 0x10001080:4` keeps the ID across a
  flash.
- **A GDB attach halts the SoftDevice.** After detach, the sensor faults and
  stops advertising until `nrfjprog -f NRF52 --reset` (#95). End every run that
  attaches the probe with a reset. To read the log while talking to the sensor
  over BLE, use the `rtt` alias (`jlink-rtt`), which never attaches.
- **`probe` and `rtt` cannot hold the J-Link at the same time.** A suite uses one
  or the other.
- **Resetting with `reset(halt=False)` leaves the core halted** on a real probe
  (#177). Reset halted, then `run`.

#### Sensor commands with side effects

From the [Robot Keyword Catalogue §2.5](robot/Robot_Keyword_Catalogue.md#25-commands-a-sensor-treats-specially):

| Command | Effect |
|---|---|
| `RD EOL START 60 30` | **Crashes the sensor.** The link drops about 34 s later, and routine state is lost. Only on 5C1712 |
| `wr mode ...` | Resets the sensor; the link drops |
| `ECURESET HARD` | MCU reset; the link drops |

### 4.4 Running on the real bench

```sh
python -m benchtools run specs/qualification/qs10_bench_identity.yaml --bench benches/bench_pc.yaml \
    --event-log E/qs10.events.jsonl --markdown E/qs10.md --json E/qs10.json --junit E/qs10.junit.xml
```

The qualification procedure in `specs/qualification/README.md` is the worked
example of a hardware session: order, backups, restores, evidence names.

### 4.5 The bench self-check and safety warnings

`specs/bench_self_check.yaml` asks, before a session, whether every instrument
can be reached, identified and driven. It is meant for a bench with
**nothing connected**: it drives the supply to 1 V at 100 mA with the output
on, and puts the meter on a current range. Setup is in
[Bench Self-Check Setup](Bench_Self_Check_Setup.md).

**Do not run it on the bench PC while the Kepler sensor is wired.** It breaks
the supply limits of [§4.3](#43-safety-limits). It also declares a `scope`,
which the bench PC does not have.

A specification, test or step can carry a `warning:`. The runner behaves as
software requirements RUN-FR-054 to RUN-FR-057 say:

| | Behaviour |
|---|---|
| RUN-FR-054 | The warning is printed before the bench is opened and before any setup step |
| RUN-FR-055 | It goes to the error stream, so redirecting the output does not hide it |
| RUN-FR-056 | On a real bench the run does not start until acknowledged: `--acknowledge` on the command line, or typing the full word `yes` at the prompt (`y` is not enough). With no terminal and no `--acknowledge`, the run is refused |
| RUN-FR-057 | A simulated run is never gated. A refusal exits **3**, distinct from a test failure |

On the simulated bench (checked):

```
> python -m benchtools run specs/bench_self_check.yaml --bench benches/simulated_bench.yaml

!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
SAFETY WARNING - Bench self-check
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
DISCONNECT EVERYTHING FROM THE INSTRUMENTS BEFORE RUNNING THIS TEST.
...
Bench self-check: PASS - 5 passed, 0 failed, 0 errored, 0 skipped in 0.01 s
```

`--acknowledge` is an operator's statement that the warning has been acted on.
Pass it only when that is true.

---

## 5. Writing tests

The full reference is the [Bench Runner Guide](Bench_Runner_Guide.md). This is
the shape of it.

### 5.1 A specification

```yaml
name: Sensor bring-up                  # required; appears in every report
description: ...
warning: |                             # optional; see §4.5
  ...
requirements: [SYS-REQ-010]
parameters:                            # optional; values named once, used as {param: name}
  readings: 5
instruments:                           # alias: driver; checked against the bench
  psu: gpd3303d
  probe: jlink
setup:                                 # once, before the tests; a failure aborts the suite
  - do: psu.configure_channel
    with: {channel: 1, volts: 3.2, current_limit: 0.5, output: true}
tests:
  - name: The board is powered at 3.2 V and is not in current limit
    requirement: SYS-REQ-010
    steps:
      - do: psu.read_channel
        with: {channel: 1}
        save: rail
        expect:
          - {name: rail_voltage, measure: voltage, nominal: 3.2, tolerance: 0.05}
teardown:                              # once, after the tests, whatever happened
  - do: psu.all_outputs_off
```

(Abridged from `specs/sensor_bringup.yaml`. That file powers the output on, so
see [§4.3](#43-safety-limits) before running it on hardware.)

### 5.2 Steps

- `do: <alias>.<method>` calls a public method or reads a property of the
  instrument with that alias. A wrong name is an error that lists the methods
  that exist. `do: sleep` with `seconds` is the one built-in action.
- `with:` gives keyword arguments.
- `save: <name>` keeps the result. A later step uses it as `{from: <name>.<path>}`,
  as an argument or as a limit. This is how a test compares two independent
  facts, such as the version flashed and the version reported, without writing
  either into the specification.
- A test can be marked `skip:` with a `skip_reason:`.

### 5.3 Expectations

Each `expect:` entry has a `name`, a `measure` path into the result (omit it
for a plain number; `length` for how many items a list has), and a limit:

| Limit | Keys |
|---|---|
| Bounds | `min`, `max` (inclusive) |
| Window | `nominal` with `tolerance` or `tolerance_percent` |
| Exact number | `nominal` alone |
| Exact text | `equals: "1.4.2"` |
| From an earlier step | `equals: {from: build.version}` |

`unit`, `scale` and `display_unit` present a value in a natural unit; `format`
changes only how it reads (`"{:06X}"` for an identifier). A path that does not
resolve is an **ERROR**, not a FAIL. Useful paths per instrument are in
[Bench Runner Guide §5](Bench_Runner_Guide.md#5-addressing-a-value-inside-a-result-measure).

### 5.4 Subsets of a run

- `--test NAME`, repeatable, runs only those test cases. Setup and teardown
  still run. An unknown name is a usage error (exit 2) that lists the names.
- The viewer's Start page offers the same choice of test cases.
- The `instruments:` block lets a suite use a subset of a bench. A suite naming
  an alias the bench lacks stops before any step and says which.

### 5.5 Command documents

A sensor's commands and expected replies can be a Markdown document, run by
`dongle.run_script` (see `specs/sensor_commands.yaml` and
`specs/sensor_commands.md`; template `specs/templates/ble_sensor_test.md`;
[Bench Runner Guide §3.5](Bench_Runner_Guide.md#35-a-command-and-response-document)).

### 5.6 Robot Framework keywords

[docs/robot/Robot_Keyword_Catalogue.md](robot/Robot_Keyword_Catalogue.md)
proposes Robot Framework keywords for the dongle, the J-Link, the GPD-3303D and
the S2-LP. **It is a proposal: no keyword library exists**, and Robot Framework
itself is undecided. It is still worth reading for the hardware behaviour that
set each keyword's defaults: timeouts, commands that reset the sensor, and
retries.

### 5.7 Developing a specification

1. Write it against the simulated bench first.
2. Run with `-v` (each step) or `-vv` (every line to and from the instruments).
3. Only then point it at the real bench, after checking it against
   [§4.3](#43-safety-limits).

---

## 6. Viewing and reporting

### 6.1 `benchtools view`

```
usage: benchtools view [-h] [--event-log PATH] [--control PORT]
                       [--bind ADDRESS] [--read-only] [--tls-cert PEM]
                       [--tls-key PEM] [--port PORT] [--specs DIR]
                       [--benches DIR] [--runs DIR] [--version]
```

| Option | Meaning |
|---|---|
| `--port` | Page port, default 8130; `0` picks one |
| `--event-log PATH` | Follow this run's event log from the start |
| `--control PORT` | The run's control port, if the event log does not give it |
| `--read-only` | Refuse to start, attach or control a run |
| `--bind ADDRESS` | Listen somewhere other than 127.0.0.1. It then prints an access token and refuses requests without it |
| `--tls-cert`, `--tls-key` | Serve HTTPS |
| `--specs`, `--benches`, `--runs` | Where it offers specifications and benches from, and where runs it starts write (defaults `specs`, `benches`, `runs`) |

Pages (`benchtools/viewer/static/index.html`):

| Page | Shows |
|---|---|
| Run | The specification, each test case and step with its live status, result and measurements, and the run controls |
| Instruments | Each instrument's exchanges, the latest or those in a time window, with a panel per instrument |
| RF | S2-LP traffic: frames, latest data, configuration, identification, environment, ticks, TWF, diagnostics, sync, and an ST GUI register view |
| BLE | Devices, events, commands and replies |
| Graphs | Readings over time, and BLE advertising |
| Event log | Every instrument's traffic, filtered by source |
| Notes & report | A fault description and findings to save, and a report to download as HTML or print to PDF |
| Start / attach | Start a run (specification, bench or simulated, test cases), or attach to one already going |

### 6.2 Run control

A run started with `--control 0` serves a control channel on 127.0.0.1 and
prints its port:

```
> python -m benchtools run specs/sensor_bringup.yaml --bench benches/simulated_bench.yaml --event-log out/ev.jsonl --control 0
control channel on 127.0.0.1:50250
Sensor bring-up: PASS - 7 passed, 0 failed, 0 errored, 0 skipped in 0.01 s
```

The viewer attaches to it (Start / attach, or `view --event-log out/ev.jsonl`)
and offers **Pause**, **Resume**, **Restart test case**, **Abort**, and a restart
from any step. A request takes effect between steps. Teardown cannot be
interrupted. Every intervention is written to the event log. The protocol is in
[Bench Runner Guide §6.5](Bench_Runner_Guide.md#65-controlling-a-run-pause-resume-abort-restart).

A run started from the viewer with a warned specification on a real bench must
be acknowledged on the page; the viewer then passes `--acknowledge`.

**Simulate on the Start page means `--simulate`.** For a specification that
needs manifests, such as `sensor_bringup.yaml`, choose the bench
`benches/simulated_bench.yaml` instead ([§1](#the-two-modes)).

### 6.3 Evidence

A result is evidence when someone else can see what was run, on what, and what
came back. For a run that matters, write all four records side by side under
one name:

```sh
--event-log E/<id>.events.jsonl --markdown E/<id>.md --json E/<id>.json --junit E/<id>.junit.xml
```

That is the convention of the 2026-10-04 qualification campaign, in
`docs/aspice/qualification/2026-10-04/` (ETB-SYS5-002 §5.3). Its rules:

- Keep a run that ended otherwise than intended under `attempts/` with a
  numbered name, and record why. **Never overwrite evidence.**
- A run with out-of-limit settings is kept, and marked as **not** evidence.
- Never present a simulated report as a measurement.

### 6.4 In CI: the GitHub Action

`action.yml` runs specifications in a workflow and publishes JUnit XML and a job
summary. `.github/workflows/bench.yml` runs `specs/sensor_bringup.yaml` and
`specs/sensor_commands.yaml` on `benches/simulated_bench.yaml` on every push. From
another repository:

```yaml
- uses: dermot-murphy/EmbeddedTestBench@v0.01.0000
  with:
    specs: specs/sensor_commands.yaml
    bench: benches/simulated_bench.yaml
```

---

## 7. The command-line tools

```
> python -m benchtools --help
Commands:
  run         run bench test specifications against a bench
  view        watch and control test runs in a browser (127.0.0.1 only)
  scope       control a Tektronix TDS3014B oscilloscope
  jlink       control a target through a SEGGER J-Link debug probe
  ble         scan, drive and profile a BLE sensor through a Nordic dongle
  psu         control a GW Instek GPD-3303D bench power supply
  s2lp        drive an ST S2-LP sub-1 GHz development kit
  thermo      read a Pico 2 + SHT30-D thermometer: identity and temperature
  drivers     list the instrument drivers a bench configuration can name
  backends    list the transport backends a resource string can select
```

There is also `dmm`, for the TTi 1604. The top-level help does not list it,
but it works.

Each tool takes `-r/--resource`. The default is `sim://`, the simulator, so
**a tool given no resource never touches hardware.** Options that say which
instrument come **before** the sub-command; the sub-command's own arguments
come after it. Results are printed as JSON, and `--json PATH` also writes them
to a file. `<tool> <sub-command> --help` gives each sub-command's options.

| Tool | Resource | Sub-commands | Tried on the simulator |
|---|---|---|---|
| `psu` (GPD-3303D) | `COM11`, `/dev/ttyUSB0`, `serial://COM4:57600`, `sim://` | `info`, `read`, `set <ch> -V -I [--on]`, `on`, `off`, `status` | `psu -r sim:// set 1 -V 3.3 -I 0.5 --on` → `"voltage": 3.3, "mode": "CV", "is_on": true` |
| `dmm` (TTi 1604) | `COM13`, `/dev/ttyUSB0`, `sim://` | `info`, `read`, `press`, `keys` | `dmm -r sim:// read` → `"value": 1.0, "unit": "V"` |
| `jlink` (J-Link) | `jlink://[host][:port]`, `sim://`; with `-d DEVICE`, `-e ELF`, `--gdb`, `--server` | `info`, `flash [--preserve ADDR:SIZE]`, `verify`, `erase`, `reset [--run]`, `run`, `halt`, `read`, `write`, `var`, `stack`, `rtt`, `time` | `jlink -r sim:// info` → `"model": "J-Link V11", "halted": true` |
| `ble` (Nordic dongle) | `COM10`, `/dev/ttyACM0`, `serial://socket://host:4001`, `sim://` | `info`, `firmware`, `scan`, `select`, `profile`, `cmd`, `script`, `monitor` | `ble -r sim:// scan` → 3 sensors, first `SENS-0A1B2C` |
| `s2lp` (S2-LP kit) | `COM4`, `/dev/ttyACM0`, `sim://`; `--board`, `--setup REGS` | `info`, `registers`, `radio`, `config`, `tx`, `rx`, `capture`, `packets`, `stream`, `preamble`, `strobe` | `s2lp -r sim:// info` → `"library": "1.3.5"` |
| `thermo` (Pico 2 + SHT30-D) | `COM14`, `/dev/ttyACM0`, `sim://` | `info`, `rd`, `temp`, `status`, `sreset`, `ecureset`, `bootsel`, `flash` | `thermo -r sim:// temp` → `"temperature_c": 22.5` |
| `scope` (TDS3014B) | IP address, VISA-style string, `sim://`; `-b` backend | `idn`, `screenshot`, `capture`, `spread`, `period`, `measure` | `scope -r sim:// idn` → `"model": "TDS 3014B"` |

Commands that change the instrument or the target: `psu set/on/off`,
`jlink flash/erase/reset/write`, `thermo sreset/ecureset/bootsel/flash`,
`s2lp tx/config/registers` writes and `strobe`, `dmm press`. `jlink erase` also
erases UICR on an nRF52, and with it the sensor ID; its help says so. Pass a
real resource to these only within [§4.3](#43-safety-limits).

Each instrument's notes go further: [J-Link](jlink/JLink_Integration_Notes.md),
[BLE dongle](ble/BLE_Dongle_Notes.md), [GPD-3303D](psu/GPD3303D_Notes.md),
[TTi 1604](dmm/TTi1604_Notes.md), [S2-LP](s2lp/S2LP_Devkit_Notes.md),
[Pico 2 + SHT30-D](pico_sht30/Pico_SHT30_Notes.md),
[TDS3014B](tek3014b/VISA_Determination_Report.md).

The tkinter Embedded Test Bench monitor (`tools/test_bench`) is frozen. The
viewer replaces it, except for three uses that need no test run
([Embedded Test Bench Monitor](test_bench/Embedded_Test_Bench_Monitor.md)).

---

## 8. For Claude Code sessions

This section is written for an AI agent working in this repository. Read it
before touching the bench. It does not replace `CLAUDE.md`; where they overlap,
`CLAUDE.md` governs the procedure.

### 8.1 Where the bench facts live

Do not rely on what you remember from an earlier session. Read these:

| Fact | Source |
|---|---|
| Which instruments exist, on which ports, with which serial numbers | `benches/bench_pc.yaml`, and ETB-SYS5-002 §4.1 |
| How each instrument behaves, its traps, its open items | `docs/<instrument>/*_Notes.md`: `jlink/`, `ble/`, `psu/`, `dmm/`, `s2lp/`, `pico_sht30/`, `tek3014b/` |
| The supply protocol, command by command | ETB-IF-001, `docs/aspice/EmbeddedTestBench_IF001_GPD3303D_Remote_Control_Interface.md` |
| What has been shown on hardware, and what has not | ETB-SYS5-002, and its evidence in `docs/aspice/qualification/2026-10-04/` |
| The hardware session procedure and the owner's safety limits | `specs/qualification/README.md` |
| Sensor commands with side effects, timeouts | `docs/robot/Robot_Keyword_Catalogue.md` §2.5–2.6, §3.6, §4.3 |
| Known problems in this release | ETB-SVD-001 §7, and the open issues |
| Spec and bench file format | `docs/Bench_Runner_Guide.md` |

### 8.2 What must never be done on the real bench

- **Never use the J-Link, the sensor or any instrument while another session is
  testing it.** One serial port has one owner. The J-Link can be held by one
  process. A second session's command can reset the sensor under the first
  one's test, and neither report will say so. If you have not been told the
  bench is yours, use the simulated bench.
- **The supply** (while 5C1712 is wired): INDEPENDENT tracking only; setpoints
  2.8–3.3 V; no output on unless the owner says so for that run; never
  `psu.reset()`, never series or parallel. See [§4.3](#43-safety-limits).
- **Never run a specification on hardware without reading its steps first**,
  including the shipped ones. `sensor_bringup.yaml` and `bench_self_check.yaml`
  switch the supply on.
- **Never pass `--acknowledge` for someone else.** It states that a person has
  acted on the warning. If the owner has not said so, do not pass it.
- **J-Link**: back up flash and UICR before any erase or flash; reset the
  sensor after any run that attaches the probe; use `rtt` (never attaches)
  while a BLE link is open.
- **Sensor commands**: `RD EOL START` crashes the sensor; `wr mode`,
  `ECURESET HARD` reset it. Only on 5C1712, and only when the test needs it.
- **No real resource by accident.** Each CLI tool defaults to `sim://`. Name a
  COM port only when you mean to drive that instrument.

### 8.3 Verify against the instrument, not memory

ETB-RISK-004 records the risk that a model with no memory between sessions
loses what was not written down. `CLAUDE.md` ("Verify, don't assert") draws the
consequence: state how a tool or instrument behaves only after checking it in
the current session. That means:

- Ask the instrument (`info`, `idn`, `status`, a read-back) rather than repeat a
  value from an earlier conversation. Ports, firmware versions and supply state
  change between sessions.
- Read the code or run `--help` before writing an option into a command or a
  document. Do not invent options.
- Check a simulator result against hardware before calling a behaviour real.
  The simulated probe does not model #177 or #178 (ETB-SYS5-002 §8, O1).
- If you could not check something, say that it is unverified.

### 8.4 The procedure in `CLAUDE.md`

Read `CLAUDE.md` itself. In short:

- The repository uses gitflow. Never commit to `main` or `develop`.
- Every change starts with an issue. Branch `feature/`, `docs/` or `fix/<topic>`
  from `develop`, and put the issue number in each commit message.
- Push with `git push -u origin <branch>`. Open a pull request only if asked,
  and its base is **`develop`**, set explicitly. Release and hotfix branches are
  the only defined exceptions.
- **Merge only when the repository owner says so.**
- Stack pull requests only when told to, and follow `CLAUDE.md`'s retargeting
  procedure if you do.
- Update the issue with what was done. Close it when CI is green, or say that no
  workflow applies.
- A change to a controlled document under `docs/aspice/` raises its
  `major.minor` version and date, and appends one revision-history row as the
  last row (ETB-SUP8-001 §6, §6.2). `tests/test_traceability.py` fails if a
  history is not oldest first.
- `CLAUDE.md` and ETB-SUP8-001 §5 are one configuration item: change both or
  neither.
- Before pushing, run
  `python -m pytest -q -p no:cacheprovider tests/test_traceability.py`.

### 8.5 How to report results

- Write the four records of [§6.3](#63-evidence) for every run you report.
- Quote the verdict line and the measurements that decide it. Say whether the
  run was **simulated** or **hardware**, and name the bench file.
- Keep FAIL and ERROR apart. An ERROR is a run that told you nothing.
- Keep failed attempts; never overwrite them.
- Report a problem in the bench as an issue, not a test failure of the product.
- Do not restate a simulated pass as a hardware result.

### 8.6 Known problems to expect

Five defects are open from the 2026-10-04 campaign. They are listed with their
workarounds in [§9.1](#91-known-problems-177-to-181). Check their state before
working around them: `gh issue view 177` and so on.

---

## 9. Troubleshooting

### 9.1 Known problems (#177 to #181)

From ETB-SYS5-002 §8 and ETB-SVD-001 §7. All five were open on 2026-10-05.

| Issue | Problem | Workaround |
|---|---|---|
| #177 | J-Link: `reset(halt=False)` leaves the target halted on a real probe. The simulator does not show it | Reset halted, then `probe.run` (as `specs/qualification/qs01_bringup.yaml` does) |
| #178 | J-Link: registers read just after `reset(halt=True)` are stale; the PC reads 0 | Do not trust a register read immediately after a reset. In QS-01b the PC read correctly after one instruction step (ETB-SYS5-002 §6.2) |
| #179 | S2-LP: receive refused after a transmit in the same session (GPIO3 reads 0) | Run receive in its own session: `--test` on the receive case alone passed in QS-07 |
| #180 | BLE dongle: `open_link` makes one attempt and does not retry a link that fails to establish (reason 0x3E) | Re-run the test. The QS-07 attempts that hit it were re-run (ETB-SYS5-002 §6.8) |
| #181 | TTi 1604: frequency mode not recognised; the meter is lost afterwards; an open input on ohms reads blank, not overrange | Use DC volts only, which is qualified. Do not select frequency: after it the meter went silent or stopped echoing keys for the rest of the session, and a power cycle did not restore every check (ETB-SYS5-002 §6.10) |

Other limits from ETB-SVD-001 §7:

- The Kepler specifications cannot run on the simulated bench: there is no
  simulated Kepler sensor (they error at `dongle.select`).
- No oscilloscope on the bench PC; the SHT30-D is not wired.
- After a GDB attach to the sensor it stops advertising until
  `nrfjprog -f NRF52 --reset` (#95).

### 9.2 Common errors

Each of these was reproduced, except where marked *(from docs)*.

| Message, or symptom | Cause | Fix |
|---|---|---|
| `error: no bench configuration given. Pass --bench PATH for real hardware, or --simulate ...` (exit 2) | Neither `--bench` nor `--simulate` | Add `--bench benches/simulated_bench.yaml` |
| With `--simulate`: `FAIL The dongle is running the build it should be` and `ERROR ... ConfigurationError: no firmware manifest found for '...'` | `--simulate` has no manifest options | Use `--bench benches/simulated_bench.yaml` |
| `error: no test case named 'nope'; the specification contains: ...` (exit 2) | `--test` names must match exactly | Copy a name from the list |
| `setup failed: setup step 'dongle.select': DongleCommandError: the dongle refused 'select D1:8D:3B:4C:19:96'` | A Kepler specification on the simulated bench | It needs the real sensor |
| `uses instrument(s) 'scope', which the bench ... does not define` *(from ETB-SYS5-002)* | The specification needs an alias the bench lacks | Use a bench with it, or drop it from the specification |
| `there is no terminal to confirm at. Re-run with --acknowledge ...` (exit 3) *(from code)* | A warned specification on a real bench, run unattended | Act on the warning, then `--acknowledge`, or run at a terminal |
| `reading ... needs pyyaml (pip install benchtools[spec])` *(from code)* | The `spec` extra is missing | `pip install -e ".[spec]"` |
| A port will not open *(from docs)* | The `serial` extra, a wrong COM number, another process holding the port, or (Linux) group permissions | [Bench Self-Check Setup §3–4](Bench_Self_Check_Setup.md#3-find-the-ports) |
| The meter answers nothing *(from docs)* | DTR/RTS not passed: three-wire cable | [TTi 1604 Notes](dmm/TTi1604_Notes.md) |
| The supply answers nothing *(from docs)* | Baud rate does not match the front panel | Utility > Baud on the supply |
| `pip show benchtools` reports `0.1.0` | PEP 440 normalisation of `0.01.0000` | Expected. `benchtools --version` gives the project's form |
| `pip show benchtools` reports `4.0.0` | Installed metadata from before the version scheme was set (ETB-SVD-001 §5.1) | Reinstall: `pip install -e ".[spec,serial,test]"`. A fresh editable install reports `benchtools 0.01.0000` |
| `benchtools` runs a different copy from your checkout | Another install is first on `PATH` | Use `python -m benchtools` from the checkout's root |
