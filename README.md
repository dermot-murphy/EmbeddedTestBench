# TestTools — `benchtools`

Bench test tooling: instrument drivers, a debug probe driver, analysis of captured
records, and a declarative test runner that drives a bench and produces pass/fail
evidence.

**No VISA installation required, and no vendor Python package.** VXI-11 and GDB/MI
are implemented directly on the Python standard library, so the package has **no
mandatory third-party dependencies** — checked by a test that parses every module,
not just asserted here.

```bash
pip install -e ".[spec,plot]"
benchtools run specs/clock_skew.yaml --simulate --markdown report.md
```

Everything below runs with no hardware: `sim://` and `--simulate` drive in-process
instrument models.

---

## Layout

```
benchtools/
├── core/          instrument-agnostic: transport, SCPI base, validation, simulator harness
├── analysis/      waveform scaling, edge/period/spread measurement, plotting
├── instruments/   one subpackage per instrument
│   ├── tek3014b/    Tektronix TDS3014B oscilloscope
│   ├── jlink/       SEGGER J-Link debug probe (flash, RTT, breakpoints, timing)
│   └── generic.py   anything answering *IDN?
└── runner/        declarative bench test runner
```

Dependencies point one way only — **core → analysis → instruments → runner** — and
that is enforced by a test, not a convention. `benchtools.core` contains no
reference to any instrument and imports on its own, which is what keeps it
reusable as instruments are added.

A bench instrument does not have to speak SCPI. `core.instrument.Instrument`
carries the lifecycle (connect, initialise, identify, close, simulate);
`ScpiInstrument` adds SCPI on top. The J-Link driver is an `Instrument` driven over
GDB/MI, and the runner treats it like any other instrument.

| Directory | Contents |
|---|---|
| `specs/` | Example test specifications |
| `benches/` | Example bench configurations |
| `examples/` | Runnable Python examples |
| `docs/` | ASPICE V4 SWE.1–SWE.4 work products |

---

## Does this need VISA? — short answer

**No — but a plain TCP socket will not work either.**

The TDS3014B's Ethernet port runs an **ONC-RPC VXI-11 server**. It has no raw SCPI
socket (port 4000 exists on *later* Tektronix scopes, not this generation). What
you need is a VXI-11 client, and VISA is only one way to get one; `benchtools`
contains its own in about 320 lines of standard-library Python.

| Approach | Dependencies | Works on a TDS3014B |
|---|---|---|
| **Built-in VXI-11** (default) | **none** | **Yes** |
| `pyvisa` + `pyvisa-py` | 2 pure-Python | Yes |
| `pyvisa` + NI-VISA / TekVISA | 1 Python + large native install | Yes |
| Raw TCP socket | none | **No — no such service** |

Both paths are verified against the same protocol server in the test suite, so
"VISA is optional" is a measured statement. Full analysis:
[docs/tek3014b/VISA_Determination_Report.md](docs/tek3014b/VISA_Determination_Report.md).

---

## Installation

```bash
pip install -e .                      # drivers + analysis + runner; no third-party deps
pip install -e ".[spec]"              # + pyyaml, for YAML specs (JSON needs nothing)
pip install -e ".[plot]"              # + matplotlib, for host-side plots
pip install -e ".[visa]"              # + pyvisa/pyvisa-py, if your site standardises on VISA
pip install -e ".[test]"              # everything, for the test suite
```

Requires Python 3.8 or later.

---

## The bench runner

Two files: a **specification** (what to do, what counts as a pass) and a **bench
configuration** (which instruments, where). Separating them means the same suite
runs on any rig, or against simulators, unchanged.

```yaml
# specs/clock_skew.yaml (abridged)
name: Clock distribution timing
requirements: [SYS-REQ-042]

setup:
  - do: scope.configure_channel
    with: {channel: 1, volts_per_div: 1.0, position_div: -4.0}
  - do: scope.configure_edge_trigger
    with: {source: 1, level: 1.65}

tests:
  - name: Rising-edge skew within 20 ns
    requirement: SYS-REQ-042
    steps:
      - do: scope.measure_channel_spread
        with: {channels: [1, 2, 3, 4], direction: RISE}
        expect:
          - name: rising_skew_spread
            measure: "1.spread"
            scale: 1.0e9
            display_unit: ns
            max: 20.0
```

```bash
benchtools run specs/clock_skew.yaml --simulate                      # no hardware
benchtools run specs/clock_skew.yaml --bench benches/lab1.yaml       # real rig
benchtools run specs/*.yaml --bench benches/lab1.yaml \
    --json results.json --markdown report.md --junit results.xml
```

Exit status is **0** pass, **1** failure or error, **2** usage — so it works
directly as a CI step.

**Failure and error are distinct throughout.** A measurement outside its limit is a
*failure* (the bench worked; the thing under test did not meet its requirement). A
step that could not run is an *error* (the test told you nothing). Conflating them
turns a broken rig into a pile of apparent product defects.

A run against simulators is disclosed in every report — whether `--simulate` was
passed or every configured resource simply happens to be a simulator.

Full guide: [docs/Bench_Runner_Guide.md](docs/Bench_Runner_Guide.md).

---

## Oscilloscope driver

```python
from benchtools.instruments.tek3014b import Tek3014B

with Tek3014B.connect("192.168.1.50") as scope:      # or "sim://"
    scope.configure_channel(1, volts_per_div=1.0, position_div=-2.0, coupling="DC")
    scope.configure_channel(2, volts_per_div=1.0, position_div=1.0,  coupling="DC")
    scope.set_time_per_div(200e-9)
    scope.configure_edge_trigger(source=1, level=1.65, slope="RISE", mode="NORMAL")

    waveforms = scope.capture_single([1, 2])         # both from ONE acquisition
    scope.save_csv(waveforms, "capture.csv")
    scope.screenshot("screen.png")
```

### Spread in time of channels going high

```python
waveforms, spread = scope.measure_channel_spread([1, 2, 3, 4], direction="RISE")
print("spread: %.3f ns" % (spread.spread * 1e9))
print("first/last: CH%d / CH%d" % (spread.earliest_channel, spread.latest_channel))
```

Why host-side? An oscilloscope's `DELay` measurement takes **two** sources, so a
four-channel spread would need three measurements across three acquisitions —
measuring instrument repeatability as much as signal skew. One acquisition on a
common time base, with interpolated edge times, recovers injected skews to **~11 ps
on a 200 ps sample interval**.

### Command line

```bash
benchtools scope -r 192.168.1.50 spread -c 1,2,3,4 \
    --vdiv 1.0 --position=-4,-3,-2,-1 --tdiv 200e-9 --trigger-level 1.65 \
    --csv spread.csv --plot spread.png --screenshot screen.png

benchtools scope -r sim:// idn
benchtools drivers        # driver names a bench config can use
benchtools backends       # transport backends a resource string can select
```

> Pass negative values with `=`, as in `--position=-4,-3`. `argparse` otherwise
> reads a leading `-` as an option flag.

---

## Debug probe driver — SEGGER J-Link

Firmware state becomes an assertable quantity in a bench test: flash and verify,
run and halt, breakpoints, RAM, variables by name, RTT, the call stack, and the
time between two lines of code.

```python
from benchtools.instruments.jlink import JLinkProbe, TimingMethod

with JLinkProbe.connect("jlink://", device="nRF52840_xxAA", elf="build/app.elf",
                        core_clock_hz=64e6) as probe:
    result = probe.flash(verify=True)            # 17 280 bytes, 3 sections, verified
    probe.reset(halt=True)

    probe.rtt_start(log_path="rtt.log")          # RTT needs no halting
    probe.run_to("sensor.c:75")
    version = probe.rtt_command("version", r"(\d+\.\d+\.\d+)").group(1)

    print(probe.read_variable("sensor_mv"))      # 1234, by name, from DWARF
    for frame in probe.call_stack():
        print(frame)                             # #0 sensor_done at sensor.c:75

    timing = probe.measure_time_between("sensor.c:40", "sensor.c:75",
                                        method=TimingMethod.SWO_ITM, repeat=20)
    print(timing.microseconds, timing.is_trustworthy, timing.halts_target)
```

It talks to the **J-Link GDB Server** over TCP and to GDB over a pipe, using the
GDB machine interface. That choice is what gives `read_variable("sensor_mv")` and a
call stack with file and line: GDB's DWARF reader does the symbol work. No
`JLinkARM.dll`, no `pylink`, nothing to install in Python.

### Timing between two lines of code, four ways

| Method | Resolution | Halts the core | Needs |
|---|---|---|---|
| `CYCLE_COUNTER` | one core cycle (15.6 ns at 64 MHz) | yes | Cortex-M DWT |
| `SWO_ITM` | one trace cycle | **no** | SWO wired, firmware writing to an ITM port |
| `TARGET_TIMER` | one timer tick | yes | firmware capturing a timer |
| `HOST_CLOCK` | ≈ 1 ms | yes | nothing |

Every result reports the method, its resolution, whether it halted the target, and
whether the interval is large enough for the method to resolve:

```
CYCLE_COUNTER   1000.000 us  (64000 cycles, halts=True)
SWO_ITM         1000.000 us  (64000 cycles, halts=False)
HOST_CLOCK        93.574 us  (- cycles, halts=True)   <- below this method's resolution
```

The last line is the point. A figure a method cannot resolve is flagged rather than
quoted, and a specification can assert on the flag beside the limit.

### Command line

```bash
# Options that say *which* probe come before the sub-command; the sub-command's
# own arguments come after it.
python -m benchtools jlink --resource sim:// info
python -m benchtools jlink --resource jlink:// --device nRF52840_xxAA --elf build/app.elf flash
python -m benchtools jlink --resource sim:// var sensor_mv
python -m benchtools jlink --resource sim:// stack
python -m benchtools jlink --resource sim:// rtt --duration 5 --log rtt.log
python -m benchtools jlink --resource sim:// time sensor.c:40 sensor.c:75 --method swo_itm --repeat 20
```

Every sub-command emits JSON.

### Ready for Docker

The probe is USB, so USB pass-through into a container would be the awkward part —
and is not needed. Both links are TCP: run the GDB Server on the machine the probe
is plugged into, and point the driver at it.

```bash
# on the PC with the probe
JLinkGDBServerCL -device nRF52840_xxAA -if SWD -speed 4000 -nogui -silent -strict
# anywhere else, with no J-Link software at all
python -m benchtools jlink --resource jlink://bench-pc:2331 --elf build/app.elf info
```

See [J-Link Integration Notes](docs/jlink/JLink_Integration_Notes.md) for Windows
setup, the port map, choosing a timing method, and the bench confirmation items.

---

## Addressing an instrument

| Resource string | Transport |
|---|---|
| `192.168.1.50` | VXI-11 (**default** for a bare address) |
| `vxi11://192.168.1.50/gpib0,1` | VXI-11 with a forced logical device name |
| `TCPIP::192.168.1.50::INSTR` | VXI-11 — a VISA-style *string*, not a VISA *library* |
| `visa://TCPIP::192.168.1.50::INSTR` | PyVISA |
| `socket://192.168.1.50:4000` | Raw socket (not a TDS3014B) |
| `sim://` | In-process simulator |

If a connection is refused, the instrument may want a different VXI-11 logical
device name. The driver probes `inst0`, `gpib0,1`, `hpib,7`, `inst`; run with `-v`
to see which was accepted, or force one with `vxi11://<host>/<name>`.

---

## Things worth knowing

**Watch for clipping.** If a trace runs off the graticule, the driver warns and
`Waveform.is_clipped` is `True`. Do not trust amplitude or any threshold-based
timing from a clipped record: level estimation is wrong, so the 50% threshold is
wrong, so the edge times are wrong. A 3.3 V signal at 1 V/div needs its position
within roughly ±1.5 divisions of centre.

**One link at a time.** The TDS3014B supports very few simultaneous VXI-11 links.
Always use a driver as a context manager so the link is released on an exception.

**Acquisition completion is polled, not `*OPC?`-ed.** On this family `*OPC?`
returns when the command is *parsed*, not when the acquisition finishes.

**`connect()` does not reset the instrument.** It only puts the response format
into a known state. Call `reset()` explicitly to clear the front-panel setup.

---

## Adding an instrument

```python
from benchtools.core.scpi import ScpiInstrument
from benchtools.core.simulator import SimulatedInstrument

class MySimulator(SimulatedInstrument):
    DEFAULT_IDN = "ACME,PSU-1,0,1.0"
    def _cmd_VOLTAGE(self, argument): ...

class PowerSupply(ScpiInstrument):
    SIMULATOR_CLASS = MySimulator      # makes sim:// work immediately
    MODEL_NAME = "ACME PSU-1"
    # add only this instrument's command vocabulary
```

The base supplies the link lifecycle, query primitives, identification, the error
queue and IEEE 488.2 block handling. For an instrument that does **not** speak SCPI
— a debug probe, a BLE dongle — subclass `benchtools.core.instrument.Instrument`
instead and implement `_open`, `_close`, `is_open` and `_read_identity`; the J-Link
driver is the worked example. Register either with
`benchtools.runner.register_driver("psu-1234", PowerSupply)` and bench
configurations can name it. New link types (serial, USBTMC, HTTP) register with
`benchtools.core.transport.register_backend`.

---

## Examples

| File | What it shows |
|---|---|
| [`examples/01_capture_and_plot.py`](examples/01_capture_and_plot.py) | Configure, trigger, capture; CSV, plot and screenshot |
| [`examples/02_channel_spread.py`](examples/02_channel_spread.py) | Four-channel skew, cross-checked against the instrument's own delay measurement |
| [`examples/03_period_and_jitter.py`](examples/03_period_and_jitter.py) | Period measured both ways, with jitter statistics |
| [`examples/04_run_bench_suite.py`](examples/04_run_bench_suite.py) | Driving the test runner from Python |
| [`examples/05_jlink_firmware.py`](examples/05_jlink_firmware.py) | Flash, verify, RTT, variables, call stack, and all four timing methods through a J-Link |

Each takes an address (or bench file) and defaults to simulation:

```bash
python examples/02_channel_spread.py 192.168.1.50
python examples/02_channel_spread.py            # simulator
```

---

## Testing

```bash
python -m pytest tests/ --cov=benchtools --cov-report=term
```

**932 tests, 94% statement coverage, no hardware required** — no oscilloscope, no
probe, no target, no GDB. With the optional extras removed: 883 pass, 28 skip,
0 fail.

The suite includes an independently implemented VXI-11 RPC server, a SCPI socket
server and a loopback TCP server standing in for the GDB Server's RTT and SWO
ports, so the protocol code is verified against something other than itself. The
simulated target puts two source lines exactly 64 000 cycles apart, so three
independent timing methods — a DWT register read, two firmware variables and a
decoded ITM stream — can be checked against the same injected 1.000 ms.

It also verifies the architecture and the documents: `test_layering.py` enforces
the dependency direction and fails on any module-level third-party import, and
`test_traceability.py` checks that every requirement is traced and every identifier
cited in a docstring is defined.

---

## Documentation

| Document | Contents |
|---|---|
| [Documentation index](docs/README.md) | Work-product map and identifier prefixes |
| [VISA Determination Report](docs/tek3014b/VISA_Determination_Report.md) | Whether VISA is required, with evidence and bench confirmation items |
| [J-Link Integration Notes](docs/jlink/JLink_Integration_Notes.md) | Why the GDB Server rather than the DLL, Windows and Docker, timing methods, probe confirmation items |
| [Bench Runner Guide](docs/Bench_Runner_Guide.md) | Writing specifications and bench configurations |
| [SWE.1 Requirements](docs/SWE1_Software_Requirements_Specification.md) | 144 functional and 13 non-functional requirements |
| [SWE.2 Architecture](docs/SWE2_Software_Architecture.md) | Layering, elements, fifteen architectural decisions |
| [SWE.3 Detailed Design](docs/SWE3_Software_Detailed_Design.md) | Per-module design units |
| [SWE.4 Test Specification](docs/SWE4_Unit_Test_Specification.md) | Strategy, test groups, pass criteria |
| [SWE.4 Test Report](docs/SWE4_Unit_Test_Report.md) | Results, coverage, measured accuracy, fourteen defects found |
| [Traceability Matrix](docs/Traceability_Matrix.md) | Bidirectional trace, stakeholder need to test |

Work products follow Automotive SPICE V4.0 SWE.1–SWE.4. This is a test tool: it is
not delivered vehicle software and carries no ASIL classification.

---

## Status and limitations

Verification is against protocol simulators and independently implemented loopback
servers — **not against physical hardware**. That proves the protocol, the
arithmetic and the tooling; it does not prove firmware-specific behaviour. Before
using this for qualification work, discharge the bench confirmation items in the
[VISA report §5.1](docs/tek3014b/VISA_Determination_Report.md#51-limits-of-this-verification--read-this-before-the-bench),
notably the SCPI command spellings, which could not be transcribed from the
Tektronix programmer manual during development.

The J-Link driver is verified against a simulated probe and a simulated target. Its
confirmation items are in the [integration notes §4](docs/jlink/JLink_Integration_Notes.md#4-bench-confirmation-items);
the one that could change a reported number is the SWO/ITM timestamp scaling, so
treat SWO timing figures as provisional until they are compared against the cycle
counter on a real part. It has not yet been run on Windows, which is where it is
intended to run first.

Planned next, with no drivers yet: a programmable PSU for the sensor supply, a
Nordic BLE dongle for BLE UART and advertising-profile measurement, a multimeter
for current over RS-232, and — under consideration — authoring tests in Markdown
and translating them to Robot Framework. The driver boundary returns plain types
with that last one in mind, but no translator exists. The core is designed for all
of them and validated against none.
