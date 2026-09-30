# Bench test — TTi 1604

Exercises the driver against a real meter. It is **not** part of the default
test run (`tests/bench` is excluded by `norecursedirs`), and it skips unless
the meter's port is named.

## Running it

```
BENCHTOOLS_TTI1604=/dev/ttyUSB1 pytest tests/bench/tti1604 -v        # Linux
set BENCHTOOLS_TTI1604=COM6 && pytest tests/bench/tti1604 -v          # Windows
BENCHTOOLS_TTI1604=sim:// pytest tests/bench/tti1604 -v              # dry run
```

About 45 s with the input open, most of it the 10 s frequency gate. A markdown
record of what the meter did is written to `tti1604_bench_findings.md` (or the
path in `BENCHTOOLS_TTI1604_REPORT`); keep it with the bench confirmation items
(`docs/dmm/TTi1604_Notes.md` §5).

## Before you start

1. Mains on, Operate pressed, straight-through 9-way cable (all pins) from the
   rear D-type to the USB converter.
2. **Inputs open**, unless you are naming a reference below.

## References — wire one at a time

| Variable | Wire | Test that runs |
|---|---|---|
| *(none)* | Nothing on the inputs | Everything except the four below; ohms with an open input must read OFL |
| `BENCHTOOLS_TTI1604_DCV=3.300` | A known DC voltage (e.g. the GPD-3303D) across V/Ω and COM | `test_dc_voltage` |
| `BENCHTOOLS_TTI1604_OHMS=4700` | A known resistor across V/Ω and COM, nothing else | `test_resistance` - settles DMM-OPEN-02 |
| `BENCHTOOLS_TTI1604_HZ=1000` | A sine of known frequency, ≥ 2,000 counts on an AC volts range, across V/Ω and COM | `test_frequency` |
| `BENCHTOOLS_TTI1604_DCI=0.0123` | Leads in **mA and COM**, in series with a load drawing a known current (above 0.4 A: the **10 A** socket) | `test_dc_current` |
| `BENCHTOOLS_TTI1604_TOLERANCE=0.005` | - | Relative tolerance for all comparisons; 1% by default |

The current test is the only one that selects a current function, and it runs
only when `BENCHTOOLS_TTI1604_DCI` is set: a current function puts the meter's
shunt across its input, which across a voltage source blows the fuse
(DMM-NFR-002). With a reference wired, the function tour still selects AC and
millivolt ranges and frequency, which is harmless on a low-voltage source; it
never selects resistance, which drives a test current into what is connected.

## What each test settles

| Test | Settles |
|---|---|
| `test_the_meter_answers_and_reads` | The link, DTR/RTS, remote mode (DMM-FR-001, -004) |
| `test_keys_are_acknowledged_first_time` | A marginal converter (DMM-OPEN-07) |
| `test_every_frame_decodes`, `test_the_raw_stream` | The frame format and terminator (DMM-OPEN-01, -06) |
| `test_the_reading_rate_is_two_and_a_half_per_second` | The 0.4 s reading interval AD-25 assumes |
| `test_a_tour_of_the_safe_functions`, `test_every_dc_voltage_range` | Keys and their confirmation from readings (AD-24) |
| `test_the_frequency_gate` | The gate flag and range labels (DMM-OPEN-04); D-41 |
| `test_resistance` | The derived resistance multiplier (DMM-OPEN-02) |
| `test_local_then_remote` | Handing the meter back (DMM-FR-006) |
