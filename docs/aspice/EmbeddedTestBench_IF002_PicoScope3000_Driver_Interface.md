<img src="../../assets/brand/svg/logos/embeddedtestbench-logo-compact.svg" alt="Embedded Test Bench" width="240">

# PicoScope 3000D Driver Interface and Dependencies

*Automotive SPICE® PAM v4.0 | SYS.3 System Architectural Design (interfaces ETB-SIF-12 and ETB-SIF-13) and SWE.2 Software Architectural Design (interface specification)*

---

## 1. Document Identification & Control

| Field | Value | Field | Value |
|---|---|---|---|
| **Document ID** | ETB-IF-002 | **Version** | [latest, §2](#2-revision-history) |
| **Project** | Embedded Test Bench | **Date** | [latest, §2](#2-revision-history) |
| **Status** | Draft | **Classification** | Internal |
| **Author** | Claude | **Reviewer** | Dermot Murphy |
| **Approver** | Dermot Murphy | **Related Process** | SYS.3, SWE.2 |

> **Note — Reviewer independence (ETB-DEV-002):** The Reviewer and Approver are the same person (Dermot Murphy). This is accepted under deviation record **ETB-DEV-002** (`docs/aspice/EmbeddedTestBench_DEV002_Independent_Review_Deviation.md`) on the basis that Embedded Test Bench has a single human team member.

---

## 2. Revision History

| Version | Date | Author | Description of Change |
|---|---|---|---|
| 0.1 | 2026-11-13 | Claude | #200: first issue. How Embedded Test Bench drives the PicoScope 3000D MSO, and everything that has to be present for it to do so. |

---

## 3. Purpose & Scope

### 3.1 Purpose

This document says how Embedded Test Bench drives a PicoScope 3000D series
mixed-signal oscilloscope, and what it depends on to do so: every layer
between a test specification and the scope's USB connector, who supplies each
one, which version is on the bench, and what fails when one is missing.

The PicoScope is unlike the other instruments on the bench. There is no
command text on a wire to capture and specify, as ETB-IF-001 does for the
supply. The host calls functions in Pico Technology's C library, and the
library talks to the unit over USB. The interface Embedded Test Bench owns is
therefore the set of library calls it makes, with what it passes and what it
takes back, and that is what this document specifies.

It is the interface specification for system interfaces **ETB-SIF-12**
(SE-HOST ↔ SE-PSCOPE) and **ETB-SIF-13** (SE-PSCOPE ↔ SE-TARGET,
ETB-SYS3-001), and for the software element **PSCOPE-ARC-001**
(ETB-SWE2-001).

### 3.2 Scope

In scope: the `ps3000a` library calls the driver makes, the order it makes
them in, the conversions between the library's codes and SI units, the
library's status codes as the driver handles them, the software and drivers
that must be installed, and the simulator that stands in for all of it.

Out of scope: the PicoScope 7 application, streaming and rapid-block modes,
ETS, memory segments and the arbitrary waveform generator. The driver uses
none of them.

### 3.3 Referenced Documents

| Document ID | Title | Version |
|---|---|---|
| ETB-SYS2-001 | Embedded Test Bench System Requirements (ETB-SYS2-065) | latest |
| ETB-SYS3-001 | Embedded Test Bench System Architecture | latest |
| ETB-SWE1-001 | Embedded Test Bench Software Requirements Specification, §17 | latest |
| ETB-SWE2-001 | Embedded Test Bench Software Architecture Description (PSCOPE-ARC-001) | latest |
| ETB-SWE3-001 | Embedded Test Bench Software Detailed Design (PSCOPE-DD-*) | latest |
| ETB-ACQ4-001 | Supplier Monitoring Plan, §4.4 (the `ps3000a` library) | latest |
| ETB-PICO-002 | PICO2 Test Board User Manual, §5.3 (the known signal on channel A) | latest |
| — | `docs/picoscope3000/PicoScope3000_Notes.md`: measurements, sources and open items | — |
| — | Pico Technology, *PicoScope 3000 Series specifications* (web page, read 2026-11-13) | Manufacturer's |
| — | Pico Technology, *PicoScope 3000 Series (A API) Programmer's Guide* | Manufacturer's; not read (§11) |

### 3.4 Unit Under Observation

| Item | Value |
|---|---|
| Model | PicoScope 3405D MSO (variant string `3405DMSO`) |
| Serial | HT415/0202, calibrated 27 Feb 2020, hardware version 1 |
| Host | The bench PC, Windows 10 Pro 22H2 (10.0.19045), 64-bit |
| Connection | USB 2.0 (the unit is USB 3.0; it opened on USB 2.0 without asking for power) |
| Library | `ps3000a.dll` 2.2.160.7569 from PicoScope 7 T&M Stable |
| Date | 2026-11-13 |

### 3.5 Evidence Classes

As in ETB-IF-001: **measured** means observed on the unit above through the
library in the session that wrote the driver; **spec page** means Pico's
published specification; **unverified** means taken from the SDK's
conventions without either, and listed in §11.

---

## 4. The Dependency Stack

From the test down to the connector. Each layer must be present for the one
above it to work.

| # | Layer | What it is | Supplied by | On the bench PC | If it is missing |
|---|---|---|---|---|---|
| 1 | Specification or script | `pscope.capture`, `benchtools pscope capture`, or Python | The user | — | — |
| 2 | `benchtools.runner` | Resolves the bench entry `driver: picoscope3000` to the class | This project | `develop` | — |
| 3 | `benchtools.instruments.picoscope3000` | The driver: `scope`, `constants`, `sdk`, `simulator`, `cli` | This project | — | — |
| 4 | `benchtools.analysis` | `Waveform`, measurement, CSV; `plotting` for `--plot` | This project | — | — |
| 5 | Python `ctypes` | Loads the library and marshals the calls | The Python standard library | Python 3.14.7, 64-bit | — (always present) |
| 6 | `ps3000a` library | `ps3000a.dll` on Windows, `libps3000a.so` on Linux, `libps3000a.dylib` on macOS | Pico Technology, with PicoScope 7 or the PicoSDK | `ps3000a.dll` 2.2.160.7569, 5 899 920 bytes, in `C:\Program Files\Pico Technology\PicoScope 7 T&M Stable` | `OptionalDependencyError` at open: "the PicoScope ps3000a library was not found. Install PicoScope 7 or the PicoSDK, or name its folder with sdk_path or PICOSDK_PATH" |
| 7 | The library's own imports | `winusb.dll`, `setupapi.dll`, `kernel32.dll`, `user32.dll`, `gdi32.dll`, `shell32.dll`, `comctl32.dll`, `version.dll` | Windows | Present | The library fails to load (`OSError` from `ctypes`) |
| 8 | USB device driver | WinUSB, bound by Pico's `oem69.inf` | Pico Technology, installed with PicoScope 7 | Version 2.4.0.2, 2022-06-10 | The unit enumerates without a driver; open fails with status 0x3 |
| 9 | USB | `VID_0CE9&PID_1211`, "PicoScope 3000 series PC Oscilloscope" | — | USB 2.0, through a hub | Open fails with status 0x3; the device is absent from Device Manager |
| 10 | The unit | PicoScope 3405D MSO | Pico Technology | HT415/0202 | As 9 |

The library's imports (row 7) were read from its import strings: it needs
only Windows' own libraries and WinUSB. It does not load the other DLLs in
the PicoScope 7 folder (`picoipp.dll`, `picocv.dll`), so copying
`ps3000a.dll` alone to another folder and naming it with `sdk_path` is
expected to work. That was not tried.

### 4.1 Python packages

| Package | Needed for | Required? |
|---|---|---|
| none beyond the standard library | the driver, the simulator, `benchtools pscope info` and `capture` with `--csv` | — |
| `matplotlib` (extra `plot`) | `capture --plot` | Optional. Without it, `--plot` raises `OptionalDependencyError` |
| `pyyaml` (extra `spec`) | reading a `.yaml` bench file or specification | Optional, as for every instrument |
| `picosdk` (Pico's Python wrappers) | — | **Not used.** See §4.2 |

### 4.2 Why `ctypes` and not Pico's Python package

Pico's own Python package is a thin layer of `ctypes` definitions over the
same library; it does not remove the need for layers 6 to 10. Calling the
library directly keeps a bare `benchtools` install importable and lets the
simulator stand in at one well-defined seam (§9). The cost is that function
signatures, structures and enumeration values are written by hand in
`sdk.py` and `constants.py`, and those not measured are open (§11).

### 4.3 Bitness

The library and the Python interpreter must have the same bitness. The bench
PC runs 64-bit Python and the 64-bit library from `C:\Program Files`. A
32-bit Python cannot load it, and `ctypes` reports that as an `OSError` when
the library is loaded.

---

## 5. Finding and Loading the Library

`sdk.find_library(sdk_path)` returns the first file that exists, in this
order:

1. the folder given as `sdk_path` (bench option `options: {sdk_path: ...}`,
   or `--sdk-path` on the command line), and its `lib` subfolder;
2. the folder in the environment variable `PICOSDK_PATH`, and its `lib`
   subfolder;
3. on Windows, `C:\Program Files\Pico Technology\SDK\lib`, then each
   `C:\Program Files\Pico Technology\PicoScope*` folder in name order; on
   Linux and macOS, `/opt/picoscope/lib`, `/usr/local/lib` and
   `/Library/Frameworks/PicoSDK.framework/Libraries/libps3000a`;
4. whatever the system's `ctypes.util.find_library("ps3000a")` finds.

The library is loaded at **open**, not at import, so importing
`benchtools`, running the simulator and running the test suite never need
it. On Windows the library's folder is added with `os.add_dll_directory`
before loading, so its own neighbours would be found if a later version
needs them, and it is loaded with `ctypes.WinDLL` (the library uses the
`stdcall` convention on 32-bit Windows; on 64-bit there is one convention).
Elsewhere it is loaded with `ctypes.CDLL`.

**PicoScope 7 updates replace the library.** Installing a new PicoScope 7
changes the folder name (`PicoScope 7 T&M Stable`) or the file in it. The
search finds the new one; the version the driver ran against is in the
identity it logs (`driver 2.2.160.7569`).

---

## 6. Resources, Ownership and the Bench Entry

| Resource string | Opens |
|---|---|
| `pico://` (also `pico`, `usb`, `usb://`) | the first unit the library finds |
| `pico://HT415/0202` | the unit with that serial number |
| `sim://` | the simulated unit (§9) |

Anything else is refused with `ConfigurationError` before the library is
touched. The bench PC's entry (`benches/bench_pc.yaml`):

```yaml
pscope:
  driver: picoscope3000
  resource: pico://HT415/0202
  timeout: 10.0
  event: PSCOPE
```

**One owner.** The library gives the unit to one process at a time. What
`ps3000aOpenUnit` returns while PicoScope 7 or another `benchtools` process
holds the unit was not observed; 0x3 was seen when the unit was not on USB at
all, and it is the likely answer for a held unit too (unverified). Close
PicoScope 7 before a run.

---

## 7. Call Sequences

`ps3000a` names are the library's; `h` is the handle `ps3000aOpenUnit`
returns. Every call returns a `PICO_STATUS`; any non-zero status raises
(§8), except where a row says otherwise.

### 7.1 Open

`PicoScope3000.connect(resource)` then `initialise()`:

| Step | Call | Arguments | Notes |
|---|---|---|---|
| 1 | `ps3000aOpenUnit` | `&h`, serial as ASCII or `NULL` | Status 0x119, 0x11A or 0x11E with `h` > 0 means the unit wants its power source confirmed (unverified, §11) |
| 1a | `ps3000aChangePowerSource` | `h`, the same status | Only after 1 returned one of those statuses |
| 2 | `ps3000aMaximumValue` | `h`, `&max` | 32 512 on the 3405D (measured); used for every conversion in §8 |
| 3 | `ps3000aGetUnitInfo` | `h`, buffer, 80, `&length`, key | Keys 3 (variant), 4 (serial), 0 (driver version) for the identity; 0 to 5 for `unit_info()`. A refused key gives an empty string, not an error |
| 4 | `ps3000aSetChannel` × 4 | `h`, channel 0–3, enabled, coupling, range index, offset | The driver's defaults: A on, ±5 V, DC, 0 V; B to D off |
| 5 | `ps3000aSetDigitalPort` × 2 | `h`, 0x80 / 0x81, 0, level | Both ports off |
| 6 | `ps3000aSetSimpleTrigger` | `h`, 0, 0, 0, 2, 0, 0 | Trigger off, so a capture is immediate until a trigger is set |

The driver sends nothing to the signal generator at open. Whether opening
the unit resets the generator was not observed.

### 7.2 Configuration

| Driver method | Calls | What is checked first |
|---|---|---|
| `configure_channel(ch, range_volts, coupling, offset, enabled)` | `ps3000aGetAnalogueOffset(h, range, coupling, &max, &min)`, then `ps3000aSetChannel` | The range is rounded up to the next of the ten (§8.2); the offset must be within what the library reports for that range and coupling. A refusal changes nothing |
| `enable_channel(ch, on)` | as above, with the channel's other settings kept | — |
| `configure_digital_port(port, enabled, threshold)` | `ps3000aSetDigitalPort(h, 0x80 + port, enabled, level)` | Threshold within ±5 V; port 0 or 1 |
| `set_timebase(n)`, `set_sample_interval(s)`, `set_record_length(n, pre)` | none: held in the driver until a capture | n ≥ 0; at least 2 samples; pre-trigger fraction 0 to 1 |
| `configure_edge_trigger(src, level, slope, auto_ms, delay)` | `ps3000aSetSimpleTrigger(h, 1, src, threshold, direction, delay, auto_ms)` | The level, plus the channel's offset, within the channel's range |
| `configure_digital_trigger({bit: cond}, auto_ms)` | `ps3000aSetSimpleTrigger(h, 0, …)` (clears the analogue trigger); `ps3000aSetTriggerChannelConditionsV2(h, &c, 1)` with only `digital` TRUE; `ps3000aSetTriggerDigitalPortProperties(h, dirs, n)`; `ps3000aSetTriggerChannelProperties(h, NULL, 0, 0, auto_ms)` | Bits 0 to 15, each in a port that is on. Unverified on the unit (§11) |
| `disable_trigger()` | `ps3000aSetSimpleTrigger(h, 0, 0, 0, 2, 0, 0)` | — |
| `set_signal_generator(wave, f, vpp, offset)` | `ps3000aSetSigGenBuiltInV2(h, offset µV, vpp µV, wave, f, f, 0, 0, 0, 0, 0, 0, 0, 0, 0)` | `|offset| + vpp/2` ≤ 2 V, 0 ≤ f ≤ 1 MHz (spec page). Unverified on the unit (§11) |
| `signal_generator_off()` | `ps3000aSetSigGenBuiltInV2` with 0 µV, 0 µV, `DC_VOLTAGE`, 0 Hz | — |

### 7.3 Capture

`capture(timeout)`:

| Step | Call | Notes |
|---|---|---|
| 1 | — | At least one channel or port must be on, or `ConfigurationError` |
| 2 | `ps3000aGetTimebase2(h, n, samples, &interval_ns, 1, &max_samples, 0)` | The library refuses a timebase too fast for what is on (0x0E) or a length beyond memory. The interval it returns is the one the records use |
| 3 | `ps3000aRunBlock(h, pre, samples − pre, n, 1, &busy_ms, 0, NULL, NULL)` | `pre` = samples × pre-trigger fraction, rounded |
| 4 | `ps3000aIsReady(h, &ready)` every 5 ms | Until ready, or until `timeout` (default the connect timeout, 10 s on the bench); then `ps3000aStop` and `AcquisitionTimeoutError` |
| 5 | `ps3000aSetDataBuffer(h, source, buffer, samples, 0, 0)` per channel and per port | Sources 0–3 for A–D, 0x80 and 0x81 for the ports; the `int16` buffers are held by the driver until step 6 returns |
| 6 | `ps3000aGetValues(h, 0, &count, 1, 0, 0, &overflow)` | No down-sampling. `count` may be less than asked; the records take `count`. Bit *n* of `overflow` is channel *n* over range |
| 7 | — | Conversion to `Waveform` records (§8.1), and a warning in the event log naming any channel over range |

The block is one acquisition: every analogue and digital record shares one
time base, so the times of events on different channels are directly
comparable. This is what ETB-SYS2-065 requires.

### 7.4 Close

`close()`: `ps3000aStop(h)`, then `ps3000aCloseUnit(h)`, then the handle is
cleared. It never raises, and a second close does nothing.

---

## 8. Data Conversion

### 8.1 Codes to SI units

For an analogue sample with code *c* on a channel with full scale *R* volts
and analogue offset *O* volts, sample *i* of a block whose trigger is at
sample *p*, interval Δt:

```
volts = c × R / 32512 − O
time  = (i − p) × Δt          (seconds; 0 is the trigger)
```

32 512 is `ps3000aMaximumValue` as read at open, not a constant. In the
`Waveform` record this is a `WaveformPreamble` with `y_multiplier = R / max`,
`y_zero = −O`, `y_offset = 0`, `x_increment = Δt`, `point_offset = p`, and
the raw codes are kept. A code at ±32 512 counts as clipped
(`Waveform.is_clipped`).

A digital port's code carries its eight bits in the low byte, bit 0 being D0
(port 0) or D8 (port 1) (unverified, §11). Each bit becomes a `Waveform` of
0.0 and 1.0 with `y_unit` `"bit"`, named `D0` to `D15`, on the same time
base.

The threshold of a digital port is passed as
`level = round(threshold / 5 V × 32767)` (unverified, §11).

An analogue trigger level is passed as
`threshold = round((level + O) / R × max)`.

### 8.2 Ranges, offsets and timebases

| Range index | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|---|---|---|---|---|---|---|---|---|---|---|
| Full scale, ± | 20 mV | 50 mV | 100 mV | 200 mV | 500 mV | 1 V | 2 V | 5 V | 10 V | 20 V |
| Offset limit, ± | 0.25 V | 0.25 V | 0.25 V | 0.25 V | 2.5 V | 2.5 V | 2.5 V | 20 V | 20 V | 20 V |

Indices 0 and 11 are refused by the 3405D with 0x0F (measured). Timebase *n*
has an interval of 2ⁿ ns for *n* < 3 and (*n* − 2) × 8 ns from 3 (measured);
`set_sample_interval(s)` picks the timebase with the longest interval not
above *s*. Whether a timebase is available depends on what is on; §3 of the
notes gives the measured limits.

---

## 9. The Simulator

`sim://` replaces layers 6 to 10 of §4 with `SimulatedPs3000a`, which has
the same Python methods as `Ps3000aSdk` (`open`, `unit_info`,
`set_channel`, `timebase`, `run_block`, `get_values`, `set_siggen` and the
rest). The driver above the seam is the same code for both. It models:

- a signal on each channel (1 kHz sine on A, 0–3.3 V square on B, triangle
  on C, 1.2 V DC on D), digitised with the range and offset set, clipped at
  ±32 512 with the overflow bit;
- the signal generator wired to channel A;
- a 2 kHz counter on the digital inputs;
- edge triggers found in the signal, and a capture that never completes with
  no edge and no auto-trigger, as the unit behaves;
- the timebases and memory the unit refused or reported (measured), and
  timebase 2 with three channels on, which was not measured.

It does not model the USB link, the library's timing, or any SDK value
marked unverified: a simulated pass says nothing about §11.

---

## 10. Status Codes

The driver raises `InstrumentError` naming the call and its status for any
non-zero status, with the status in `events`. Opening raises
`ConnectionFailedError`. Only statuses seen on the unit are given a meaning
in messages; others are given by number.

| Status | Meaning, as seen | Where |
|---|---|---|
| 0x00 | OK | every call |
| 0x03 | No unit found; also what a unit held by another process returns | `ps3000aOpenUnit` |
| 0x0E | Timebase not available with the channels and ports enabled | `ps3000aGetTimebase2` |
| 0x0F | Range not available on this model | `ps3000aGetAnalogueOffset`, `ps3000aSetChannel` |
| 0x119, 0x11A, 0x11E | Power source to be confirmed (unverified) | `ps3000aOpenUnit` |

---

## 11. Open Items

ETB-RISK-004: these follow the SDK's conventions and have not been confirmed
on the unit. The identifiers are those of ETB-RTM-001 OPEN-11.

| ID | Item |
|---|---|
| PSCOPE-OPEN-01 | The digital bits against a real logic signal: bit order in a port's code, and the threshold scaling |
| PSCOPE-OPEN-02 | The digital trigger calls and the `DigitalDirection` codes |
| PSCOPE-OPEN-03 | `ps3000aSetSigGenBuiltInV2`'s argument order and the `WaveType` codes. What the generator's BNC is wired to on the bench is not stated, so it has not been driven |
| PSCOPE-OPEN-04 | #200's acceptance on channels B to D and the digital inputs. Channel A is done: 32 settings of the PICO2 Test Board generator (ETB-PICO-002 §5.3) |
| PSCOPE-OPEN-05 | The trigger directions other than `RISE`, and the power-source statuses |

The programmer's guide could not be read when the driver was written (its
text could not be extracted). Reading it, or the PicoSDK's C headers, would
settle 01, 02, 03 and 05 on paper; each still needs a check on the unit.

Also not tried: Linux and macOS (the library names and folders in §5 are the
PicoSDK's conventions), the unit on a USB 3.0 port, and a copy of
`ps3000a.dll` outside the PicoScope 7 folder.

---

## 12. Interface Requirements on a Host

A host that is to drive the PicoScope needs:

1. Python 3.8 or later with `ctypes`, of the same bitness as the library;
2. the `ps3000a` library, from PicoScope 7 or the PicoSDK, findable as in §5;
3. Pico's USB driver bound to the unit (installed with either of the above);
4. the unit on USB, and no other process holding it;
5. for `--plot`, `matplotlib`.

A container needs the Linux library and the USB device passed in; ETB-SYS3-001
§6.1 records that as a property of USB instruments.
