# PicoScope 3000D MSO — Interface Notes

Working notes for the `picoscope3000` driver (#200): how the scope is reached,
where each fact came from, and what has not been confirmed. This is the
interface note the issue asks for, in the form of the other instruments'
notes (`docs/dmm/TTi1604_Notes.md`).

The bench's unit is a **PicoScope 3405D MSO**, serial `HT415/0202`,
calibrated 27 Feb 2020, on USB. Its bench entry is `pscope` in
`benches/bench_pc.yaml`.

---

## 1. Sources

| Source | What it establishes | How it was read |
|---|---|---|
| The unit itself, through `ps3000a.dll`, 2026-11-13 | ADC full scale, the ranges it accepts, offset limits, the timebase formula, the timebases refused per channel load, memory per channel load, segments, AWG buffer, identity strings | Measured (§3). Scripts in the session that added the driver; results recorded here |
| Pico Technology, *PicoScope 3000 Series specifications* — <https://www.picotech.com/oscilloscope/3000/picoscope-3000-oscilloscope-specifications> | Bandwidth, sample rates, buffer, resolution, input ranges and impedance, digital inputs and threshold, signal generator and AWG, and that there are no digital outputs | Read 2026-11-13. The page is one column per model; the 3405D values were taken from the seventh column |
| *PicoScope 3000 Series (A API) Programmer's Guide* | The C API | Not readable in the session (the PDF text could not be extracted). Every API detail below that was not measured is marked **unverified** |
| `ps3000a.dll` export table | The functions the library offers | Read from the DLL: 79 `ps3000a*` names, none for a digital or pattern output |

---

## 2. How it is reached

The PicoScope is not a message-based instrument. There is no command text on
a wire; the host calls Pico Technology's C library, which talks to the unit
over USB through Pico's WinUSB driver.

| Layer | On the bench PC |
|---|---|
| USB device | `USB\VID_0CE9&PID_1211`, "PicoScope 3000 series PC Oscilloscope" |
| Windows driver | WinUSB, Pico Technology `oem69.inf`, version 2.4.0.2, 2022-06-10 (read from the device's driver properties in Windows, `Get-PnpDeviceProperty`; `ps3000a` does not report it) |
| C library | `ps3000a.dll` from `C:\Program Files\Pico Technology\PicoScope 7 T&M Stable`; reports driver version 2.2.160.7569 |
| Python | `ctypes`, in `benchtools/instruments/picoscope3000/sdk.py`. No Pico Python package (`picosdk`) is used or needed |

The library is looked for in `sdk_path` (bench option or `--sdk-path`), then
`PICOSDK_PATH`, then the PicoSDK and PicoScope folders under
`C:\Program Files\Pico Technology`, then the system's library path.

Resource strings: `pico://` opens the first unit, `pico://HT415/0202` that
serial number, `sim://` the simulator. The bench file names the serial, so a
second PicoScope on the PC is never opened by mistake.

**One owner.** The unit is held by one process at a time. What the driver's
open returns while PicoScope 7 holds the unit was not observed; `0x3` was seen
with no unit on USB, and is the likely answer (unverified). Close PicoScope 7
first. How the scope is driven, call by call, and every dependency, is
ETB-IF-002 (`docs/aspice/EmbeddedTestBench_IF002_PicoScope3000_Driver_Interface.md`).

**Older 3000 models are a different library.** The 3204/3205/3206 (no suffix)
use `ps3000.dll`, not `ps3000a`. This driver does not open them.

---

## 3. Measured on the 3405D (2026-11-13)

| Fact | Value | Call |
|---|---|---|
| Full-scale ADC code | 32512 (and −32512) | `ps3000aMaximumValue`, `ps3000aMinimumValue` |
| Ranges accepted | index 1 to 10: ±20 mV, 50 mV, 100 mV, 200 mV, 500 mV, 1 V, 2 V, 5 V, 10 V, 20 V. Index 0 (10 mV) and 11 (50 V) refused, status `0x0F` | `ps3000aGetAnalogueOffset` |
| Offset limits (DC) | ±0.25 V on 20–200 mV; ±2.5 V on 0.5–2 V; ±20 V on 5–20 V | `ps3000aGetAnalogueOffset` |
| Timebase *n* | 2ⁿ ns for *n* < 3, then (*n* − 2) × 8 ns; checked at *n* = 0–5, 10, 127, 252 | `ps3000aGetTimebase2` |
| Fastest timebase | 0 (1 ns) with one channel; 1 with two; 2 with four, or with A and both digital ports; 3 with four channels and a digital port. Refused faster with status `0x0E` | `ps3000aGetTimebase2` |
| Memory | 268 435 200 samples with A alone; 134 217 600 with A and B; 67 108 800 with four channels; 33 554 400 with four channels and one or two digital ports | `ps3000aGetTimebase2` (maxSamples) |
| Segments | up to 500 000 | `ps3000aGetMaxSegments` |
| AWG | 32 768 samples; codes −32768 to 32767 | `ps3000aSigGenArbitraryMinMaxValues` |
| Identity | variant `3405DMSO`, serial `HT415/0202`, hardware 1, USB 2.0, cal date `27Feb20` | `ps3000aGetUnitInfo` keys 0–5 |
| Power | opened with status 0 on USB 2.0, without the external supply question | `ps3000aOpenUnit` |
| Trigger `RISE` | the SDK's direction 2: the captured trace crossed upwards at t = 0 | `ps3000aSetSimpleTrigger` |

`ps3000aGetValues` returned four analogue channels and both digital ports in
one block at 8 ns (timebase 3) with nothing connected: inputs at 0 V within
two codes, every digital bit low.

**Known signal on channel A.** Channel A is wired to the PICO2 Test Board's
generator channel 1, the UDA1334A's left output (owner, 2026-11-13). With
that channel set to a 2500 Hz sine (`routine freq results 1` reported
2500.00 Hz), the driver captured 1.91 V peak-to-peak and measured 2500.52 Hz
over 10 000 samples at 1 µs, triggered rising at 0 V. Channels 2 and 3 were
running at 4000 Hz and 6000 Hz at the same time and did not appear on A.

## 4. From the specification page (3405D column)

100 MHz bandwidth; 1 GS/s with one channel, 500 MS/s with two channels or
ports, 250 MS/s with up to four, 125 MS/s otherwise; 256 MS buffer; 8 bits;
1 MΩ ∥ 14 pF; AC/DC; 20 MHz bandwidth limit; 16 digital inputs in two ports
of 8, 100 MHz, threshold ±5 V per port; signal generator DC to 1 MHz, within
±2 V, 600 Ω, rear-panel BNC; AWG 20 MS/s, 32 kS, 12 bits.

**No digital outputs.** The page lists digital inputs and digital triggering
only, and the library exports no digital-output function. Issue #200 asked for
digital output "if the model has it"; it does not. The only output is the
signal generator.

---

## 5. Not yet verified

ETB-RISK-004: these are written from the SDK header's conventions, not
checked on the unit. Each is a hardware check still to do. The identifiers
are those of ETB-RTM-001 OPEN-11 and ETB-SWE4-002 §13C.3.

| ID | Item | Where in the code | How to check |
|---|---|---|---|
| PSCOPE-OPEN-01 | Digital bits against a real logic signal: bit order in a port's code (bit 0 = D0), and the threshold scaling, −32767..32767 for −5..5 V | `sdk.get_values`, `scope._scale`, `scope._level` | A known logic signal on D0 only; a slow ramp on a digital input |
| PSCOPE-OPEN-02 | Digital trigger (`ps3000aSetTriggerChannelConditionsV2`, `…DigitalPortProperties`, `…ChannelProperties`) and the direction codes | `sdk.set_digital_trigger`, `DigitalDirection` | Trigger on a known edge |
| PSCOPE-OPEN-03 | The signal generator: `ps3000aSetSigGenBuiltInV2` argument order and the `WaveType` codes | `sdk.set_siggen`, `WaveType` | The generator's BNC into an analogue channel. What it is wired to on the bench is not stated, so it has not been driven |
| PSCOPE-OPEN-04 | #200's acceptance: four analogue channels and the digital channels in one block, each against a known signal. Done for channel A only (§3, the PICO2 Test Board generator) | `scope.capture` | Known signals on B, C, D and the digital inputs |
| PSCOPE-OPEN-05 | SDK values marked unverified in `constants.py`: threshold directions other than `RISE`; the power-source statuses `0x119`, `0x11A`, `0x11E` | `ThresholdDirection`, `constants.POWER_STATUSES` | Trigger `FALL` on a sine; the statuses only show on a port that cannot power the unit |

The simulator also allows timebase 2 with three analogue channels on; that
load was not measured (ETB-SWE3-001 PSCOPE-DD-SIM).

---

## 6. Using it

```bash
python -m benchtools pscope -r pico:// info
python -m benchtools pscope -r pico:// capture -c A B C D --range 2 --digital 0 1 \
    --interval 8e-9 --samples 10000 --trigger A --level 0 --auto-ms 200 --csv block.csv
python -m benchtools pscope -r pico:// siggen --wave SINE --frequency 1000 --vpp 1
python -m benchtools pscope -r pico:// siggen --off
```

Options before the sub-command (`-r`, `--timeout`, `--json`, `--sdk-path`)
belong to the tool; the rest to the sub-command.

Before driving the generator on the real bench, know what its BNC is wired
to: it is an output.
