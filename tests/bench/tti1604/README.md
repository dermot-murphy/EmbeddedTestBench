# Bench test — TTi 1604

Exercises the `tti1604` driver against a real meter (DMM-FR-080,
SWE4-UT-DMMBENCH). It is **not** part of the default test run (`tests/bench` is
excluded by `norecursedirs`), and it skips unless the meter's port is named.

For the interactive check against the meter's own display, see
`examples/12_dmm_front_panel_check.py`.

## Running it

```
BENCHTOOLS_TTI1604=/dev/ttyUSB0 python -m pytest tests/bench/tti1604 -v      # Linux
set BENCHTOOLS_TTI1604=COM6 && python -m pytest tests/bench/tti1604 -v       # Windows
BENCHTOOLS_TTI1604=sim:// python -m pytest tests/bench/tti1604 -v            # dry run
```

About 45 s with the input open, most of it the 10 s frequency gate. A markdown
record of what the meter did is written to `tti1604_bench_findings.md` (or the
path in `BENCHTOOLS_TTI1604_REPORT`); keep it with the bench confirmation items
in `docs/dmm/TTi1604_Notes.md` §5.

## Before you start

1. Mains on, Operate pressed, straight-through 9-way cable (all pins) from the
   rear D-type to the USB converter.
2. **Inputs open**, unless you are naming a reference below.

## References — wire one at a time

| Variable | Wire | Test that runs |
|---|---|---|
| *(none)* | Nothing on the inputs | Everything except the four below; ohms with an open input must read OFL |
| `BENCHTOOLS_TTI1604_DCV=3.300` | A known DC voltage (e.g. the GPD-3303D) across V/Ω and COM | `test_dc_voltage` |
| `BENCHTOOLS_TTI1604_OHMS=4700` | A known resistor across V/Ω and COM, nothing else | `test_resistance` — settles DMM-OPEN-08 |
| `BENCHTOOLS_TTI1604_HZ=1000` | A sine of known frequency, at least 2,000 counts on an AC volts range, across V/Ω and COM | `test_frequency` |
| `BENCHTOOLS_TTI1604_DCI=0.0123` | Leads in **mA and COM**, in series with a load drawing a known current (above 0.4 A: the **10 A** socket) | `test_dc_current` |
| `BENCHTOOLS_TTI1604_TOLERANCE=0.005` | — | Relative tolerance for every comparison; 1% by default |

The current test is the only one that selects a current function, and it runs
only when `BENCHTOOLS_TTI1604_DCI` is set: a current function puts the meter's
shunt across its input, which across a voltage source blows the fuse. The
function tour selects AC and millivolt ranges and frequency, which is harmless
on an open or low-voltage input; it never selects resistance, which drives a
test current into whatever is connected.

## What each test settles

| Test | Settles |
|---|---|
| `test_the_meter_answers_and_reads` | The link, DTR/RTS, remote mode, the #115 read path |
| `test_keys_are_acknowledged_promptly` | A marginal converter (DMM-OPEN-07) |
| `test_every_frame_decodes`, `test_the_raw_stream` | The frame format and terminator (DMM-OPEN-01, -03) |
| `test_the_reading_rate_is_two_and_a_half_per_second` | The 0.4 s reading interval the waits assume |
| `test_a_tour_of_the_safe_functions`, `test_every_dc_voltage_range` | Keys and their confirmation from the readings (AD-25) |
| `test_the_frequency_gate` | The gate flag and range labels (DMM-OPEN-06) |
| `test_resistance` | The display convention on the resistance ranges (DMM-OPEN-08) |
| `test_local_then_remote` | Handing the meter back (DMM-FR-007) |
