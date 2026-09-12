# TestTools

## `tek3014b` — Tektronix TDS3014B oscilloscope driver (Ethernet)

Control a Tektronix TDS3014B over Ethernet from Python: configure up to four channels,
trigger, capture waveforms and screen images, and measure — including the timing spread of
several channels switching, which the instrument cannot measure on its own.

**No VISA installation required.** The driver implements the VXI-11 protocol directly on the
Python standard library, so it has **zero mandatory dependencies**. See
[docs/VISA_Determination_Report.md](docs/VISA_Determination_Report.md) for the full analysis.

---

## Does this need VISA? — short answer

**No — but a plain TCP socket will not work either.**

The TDS3014B's Ethernet port runs an **ONC-RPC VXI-11 server**. It has no raw SCPI socket
(port 4000 exists on *later* Tektronix scopes, not this generation). What you need is a
VXI-11 client, and VISA is only one way to get one. This package contains its own, in about
320 lines of standard-library Python.

| Approach | Dependencies | Works on a TDS3014B |
|---|---|---|
| **Built-in VXI-11** (default) | **none** | **Yes** |
| `pyvisa` + `pyvisa-py` | 2 pure-Python | Yes |
| `pyvisa` + NI-VISA / TekVISA | 1 Python + large native install | Yes |
| Raw TCP socket | none | **No — no such service** |

Both the built-in transport and PyVISA are verified against the same protocol server in the
test suite, which is what makes "VISA is optional" a measured statement rather than a claim.

---

## Installation

```bash
pip install -e .                  # driver only, no third-party dependencies
pip install -e ".[plot]"          # + matplotlib, for host-side plots
pip install -e ".[visa]"          # + pyvisa/pyvisa-py, if your site standardises on VISA
pip install -e ".[test]"          # everything, for running the test suite
```

Requires Python 3.8 or later.

---

## Quick start

Everything below runs without hardware — use `sim://` in place of an address to drive the
built-in instrument simulator.

```python
from tek3014b import Tek3014B

with Tek3014B.connect("192.168.1.50") as scope:      # or "sim://"
    print(scope.identity())

    # Vertical: volts/div and screen position, per channel
    scope.configure_channel(1, volts_per_div=1.0, position_div=-2.0, coupling="DC")
    scope.configure_channel(2, volts_per_div=1.0, position_div=1.0,  coupling="DC")

    # Horizontal and trigger
    scope.set_time_per_div(200e-9)
    scope.configure_edge_trigger(source=1, level=1.65, slope="RISE", mode="NORMAL")

    # Trigger once; both channels come from the SAME acquisition
    waveforms = scope.capture_single([1, 2])

    scope.save_csv(waveforms, "capture.csv")
    scope.screenshot("screen.png")
```

### The headline measurement: spread in time of channels going high

```python
with Tek3014B.connect("192.168.1.50") as scope:
    for channel, position in zip((1, 2, 3, 4), (-4.0, -3.0, -2.0, -1.0)):
        scope.configure_channel(channel, volts_per_div=1.0, position_div=position)
    scope.set_time_per_div(200e-9)
    scope.configure_edge_trigger(source=1, level=1.65)

    waveforms, spread = scope.measure_channel_spread([1, 2, 3, 4], direction="RISE")

    print("spread      : %.3f ns" % (spread.spread * 1e9))
    print("first / last: CH%d / CH%d" % (spread.earliest_channel, spread.latest_channel))
    for channel, skew in sorted(spread.skews.items()):
        print("  CH%d skew : %+8.3f ns" % (channel, skew * 1e9))
```

Why host-side? The instrument's own `DELay` measurement takes **two** sources. A four-channel
spread would need three sequential measurements over three different acquisitions, which
measures instrument repeatability as much as signal skew. Capturing all four channels from
one acquisition on a common time base gives a real answer — and edge times are interpolated
between samples, so resolution is not limited to the sample interval (measured: ~11 ps
residual on a 200 ps sample interval).

### Period, with jitter statistics

```python
waveforms, period = scope.measure_period_host(1)
print("mean %.6f us, jitter %.3f ns pk-pk, over %d cycles"
      % (period.mean * 1e6, period.peak_to_peak_jitter * 1e9, period.count))

print("instrument says: %.6f us" % (scope.measure_period(1) * 1e6))
```

---

## Command line

```bash
tek3014b --help
tek3014b -r sim:// idn

# Capture four channels and report the rising-edge spread
tek3014b -r 192.168.1.50 spread -c 1,2,3,4 \
    --vdiv 1.0 --position=-4,-3,-2,-1 --tdiv 200e-9 \
    --trigger-source 1 --trigger-level 1.65 \
    --csv spread.csv --plot spread.png --screenshot screen.png

tek3014b -r 192.168.1.50 capture -c 1,2 --vdiv 1.0 --tdiv 1e-6 --csv cap.csv
tek3014b -r 192.168.1.50 period  -c 1  --vdiv 1.0 --tdiv 1e-6
tek3014b -r 192.168.1.50 measure -c 1  --type PERIOD
tek3014b -r 192.168.1.50 screenshot screen.png
```

Results are printed as JSON, so the tool composes into a larger harness. Exit status is
`0` success, `1` instrument/driver error, `2` usage error.

> **Note on negative values:** pass them with `=`, as in `--position=-4,-3,-2,-1`.
> `argparse` otherwise reads a leading `-` as an option prefix.

---

## Addressing the instrument

| Resource string | Transport |
|---|---|
| `192.168.1.50` | VXI-11 (**default** for a bare address) |
| `vxi11://192.168.1.50` | VXI-11, explicit |
| `vxi11://192.168.1.50/gpib0,1` | VXI-11 with a forced logical device name |
| `TCPIP::192.168.1.50::INSTR` | VXI-11 — a VISA-style *string*, but **not** a VISA *library* |
| `visa://TCPIP::192.168.1.50::INSTR` | PyVISA |
| `socket://192.168.1.50:4000` | Raw socket (not a TDS3014B) |
| `sim://` | Built-in simulator |

If a connection is refused, the instrument may want a different VXI-11 logical device name.
The driver probes `inst0`, then `gpib0,1`, then `hpib,7`, then `inst`; run with `-v` to see
which one was accepted, or force one with `vxi11://<host>/<name>`.

---

## Things worth knowing

**Watch for clipping.** If a trace runs off the top or bottom of the graticule, the driver
warns and `Waveform.is_clipped` is `True`. Do not trust amplitude or any threshold-based
timing result from a clipped record — level estimation is wrong, so the 50% threshold is
wrong, so the edge times are wrong. A 3.3 V signal at 1 V/div needs its position kept within
roughly ±1.5 divisions of centre.

**One link at a time.** The instrument supports very few simultaneous VXI-11 links. Always
use the driver as a context manager so the link is released even on an exception.

**Acquisition completion is polled, not `*OPC?`-ed.** On this instrument family `*OPC?`
returns when the command is *parsed*, not when the acquisition finishes.

**`connect()` does not reset the instrument.** It only puts the response format into a known
state. Call `scope.reset()` explicitly if you want the front-panel setup cleared.

---

## Examples

| File | What it shows |
|---|---|
| [`examples/01_capture_and_plot.py`](examples/01_capture_and_plot.py) | Configure, trigger, capture; CSV, host-side plot and instrument screenshot |
| [`examples/02_channel_spread.py`](examples/02_channel_spread.py) | Four-channel timing spread, cross-checked against the instrument's own delay measurement |
| [`examples/03_period_and_jitter.py`](examples/03_period_and_jitter.py) | Period measured both ways, with jitter statistics |

Each takes an address as its argument and defaults to `sim://`:

```bash
python examples/02_channel_spread.py 192.168.1.50
python examples/02_channel_spread.py            # simulator
```

---

## Testing

```bash
python -m pytest tests/ --cov=tek3014b --cov-report=term
```

292 tests, 93% statement coverage, no hardware required. The suite includes an independently
implemented VXI-11 RPC server and a SCPI socket server on loopback, so the protocol code is
verified against something other than itself.

---

## Documentation

| Document | Contents |
|---|---|
| [VISA Determination Report](docs/VISA_Determination_Report.md) | Whether VISA is required, with evidence, options and bench confirmation items |
| [SWE.1 Requirements](docs/SWE1_Software_Requirements_Specification.md) | 44 functional and 8 non-functional requirements |
| [SWE.2 Architecture](docs/SWE2_Software_Architecture.md) | Layering, elements, and the seven key design decisions |
| [SWE.3 Detailed Design](docs/SWE3_Software_Detailed_Design.md) | Per-module design units |
| [SWE.4 Test Specification](docs/SWE4_Unit_Test_Specification.md) | Strategy, test groups, pass criteria |
| [SWE.4 Test Report](docs/SWE4_Unit_Test_Report.md) | Results, coverage, timing accuracy, defects found |
| [Traceability Matrix](docs/Traceability_Matrix.md) | Bidirectional trace, stakeholder need to test |

Work products follow Automotive SPICE V4.0 SWE.1–SWE.4. The driver is a test tool: it is not
delivered vehicle software and carries no ASIL classification.

---

## Status and limitations

Verification to date is against a protocol-level simulator and independently implemented
loopback servers — **not against physical hardware**. That proves the protocol and the
arithmetic; it does not prove firmware-specific behaviour. Before using this for
qualification work, discharge the bench confirmation items in
[the VISA report §5.1](docs/VISA_Determination_Report.md#51-limits-of-this-verification--read-this-before-the-bench),
notably the SCPI command spellings, which could not be transcribed from the Tektronix
programmer manual during development.
