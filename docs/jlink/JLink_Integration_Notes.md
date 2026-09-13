# SEGGER J-Link Integration Notes

| Field | Value |
|---|---|
| Document ID | BENCHTOOLS-JLINK-001 |
| Version | 1.0 |
| Date | 2026-09-13 |
| Element | `benchtools.instruments.jlink` (JLINK-, SWE.1 §8) |
| Status | Verified against a simulated probe and target; bench confirmation items in §4 outstanding |

This is the engineering note for the debug probe, in the same role the VISA
determination report plays for the oscilloscope: the decisions a reader will want
justified, the practicalities of the first deployment, and the things that cannot
be known without hardware.

## 1. Why the GDB Server, and not the DLL

Three ways exist to drive a J-Link from Python. The driver uses the second:

| Route | What it gives | Why not |
|---|---|---|
| `JLinkARM.dll` / `libjlinkarm.so` via `ctypes`, or `pylink-square` | Direct memory, flash and register access; no child processes | **No symbol knowledge.** `read_variable("sensor_mv")` and a call stack with file and line need DWARF parsing — thousands of lines to write and verify. A native library also has to be shipped per platform and made visible inside a container. `pylink-square` is a third-party dependency (CORE-NFR-001). |
| **J-Link GDB Server + GDB, speaking GDB/MI** | GDB's DWARF reader: variables by name, breakpoints by `file:line`, call stacks. A documented, versioned, stable interface. Both links are TCP. | Two processes to manage, an MI parser to write, and asynchronous records to handle. All three are bounded, one-off costs. |
| The GDB Server's telnet / `monitor` interface alone | Reset, halt, flash, memory | No symbols either, and a line-oriented protocol with no request/reply correlation. Used *within* the MI session for the few probe-specific commands that have no MI form. |

Recorded as AD-12 in SWE.2. The consequence worth stating plainly: **VISA is not
involved and neither is any vendor Python package.** The driver's only external
dependencies are two executables it launches or connects to.

## 2. Running it

### 2.1 On a Windows PC (the first deployment)

Install the SEGGER J-Link Software and Documentation Pack, and an
`arm-none-eabi-gdb` (the Arm GNU Toolchain, or the one shipped with a vendor SDK).
Both need to be on `PATH`, or passed explicitly.

```
python -m benchtools jlink --resource jlink:// --device nRF52840_xxAA --elf build/app.elf info
```

Options naming the probe come before the sub-command, as they do for the
oscilloscope: `jlink --resource … <sub-command> [arguments]`.

The driver starts `JLinkGDBServerCL.exe` with `-nogui -silent -singlerun -strict`.
`-nogui` matters: without it the server opens a window and waits, which hangs an
unattended run. If a server is already listening on 2331 — started by hand, or by
a service — it is used as it stands and left running afterwards.

Nothing in the driver uses a POSIX-only facility. In particular the process
transport uses reader threads rather than `select`, because `select` does not
accept pipe handles on Windows (CORE-DD-PROCESS).

### 2.2 Ports

| Port | Purpose | Constant |
|---|---|---|
| 2331 | GDB remote protocol | `DEFAULT_GDB_PORT` |
| 2332 | SWO trace | `DEFAULT_SWO_PORT` |
| 19021 | RTT channel 0 | `DEFAULT_RTT_PORT` |
| 2333 | Telnet / `monitor` | `DEFAULT_TELNET_PORT` |

Only channel 0 of RTT is republished on the server's RTT port. A bench that needs
several RTT channels must read them through the telnet interface or the DLL; this
is recorded as a limitation, not worked around.

### 2.3 In Docker (not yet, but already possible)

A probe is a USB device, and USB pass-through into a container is awkward and
host-specific. The driver therefore never requires the probe to be local:

```
# On the Windows PC with the probe attached:
JLinkGDBServerCL -device nRF52840_xxAA -if SWD -speed 4000 -port 2331 \
                 -rtttelnetport 19021 -nogui -silent -strict

# In the container, with no J-Link software installed at all:
python -m benchtools jlink --resource jlink://bench-pc:2331 --elf build/app.elf info
```

The container still needs a GDB, which is a plain `apt` package, and the ELF file.
The driver refuses to *spawn* a server for a non-local host and says so, rather
than appearing to start one (AD-13, JLINK-FR-004).

### 2.4 Which timing method to use

| Method | Resolution | Halts the core | Needs |
|---|---|---|---|
| `CYCLE_COUNTER` | one core cycle (15.6 ns at 64 MHz) | **Yes** | A Cortex-M with an unlocked DWT |
| `SWO_ITM` | one trace cycle | **No** | The SWO pin wired, trace enabled, and the firmware writing to an ITM stimulus port |
| `TARGET_TIMER` | one timer tick | **Yes** | Firmware that captures a timer into two variables |
| `HOST_CLOCK` | ≈ 1 ms | **Yes** | Nothing |

Pick `SWO_ITM` when the firmware must keep running — a control loop, anything
with a watchdog, anything where a breakpoint changes the behaviour being measured.
Pick `CYCLE_COUNTER` for the exact figure when halting is acceptable. Use
`HOST_CLOCK` only for intervals of tens of milliseconds or more; below that the
result is reported as not trustworthy, and a test asserting on it is asserting on
host scheduling noise.

The 32-bit cycle counter wraps after 67 s at 64 MHz (`ProbeLimits.
cycle_counter_max_seconds`). One wrap is handled; a longer interval needs the
target timer.

## 3. Using it from a bench test

`specs/firmware_timing.yaml` is the worked example, and
`docs/Bench_Runner_Guide.md` documents the specification format. The points
specific to the probe:

- Declare the driver so a simulated run picks the right one:
  `instruments: {probe: jlink}`.
- Assert on `measurement_is_resolvable` (from `is_trustworthy`) beside any timing
  limit. A limit on a figure the method cannot resolve is not a test.
- `halts_target` is assertable too: a test that must not disturb the firmware can
  require that the measurement did not halt it.
- RTT needs no halting, so a test can read firmware output while it runs; a
  breakpoint-based measurement cannot be interleaved with it.

## 4. Bench confirmation items

These cannot be discharged without a probe and a target. Until they are, the
driver is verified against a simulated probe (CON-04).

| ID | Item | Why it is open | How to discharge |
|---|---|---|---|
| JLINK-OPEN-01 | Execution on a Windows host | Developed and verified on Linux. The Windows-specific choices (reader threads rather than `select`, `.exe` search order, `-nogui`) are made but not exercised on Windows | Run the suite and `examples/05_jlink_firmware.py` on the target PC |
| JLINK-OPEN-02 | GDB/MI output of the installed GDB | The MI grammar is stable and versioned, but a given GDB may order or spell fields differently from the simulated dialogue | Run `jlink info`, `stack`, `var` against a real target and compare; the parser is tolerant of unknown fields by construction |
| JLINK-OPEN-03 | **SWO/ITM local timestamp scaling** | The tick-to-cycle scaling depends on the trace prescaler configured by the server and the firmware. Implemented from the ARMv7-M architecture reference manual; unconfirmed | Measure a known interval with `CYCLE_COUNTER` and with `SWO_ITM` and compare. Until then, quote SWO figures as provisional (CON-05) |
| JLINK-OPEN-04 | RTT control-block discovery and flash timing | The server locates the RTT control block by scanning RAM, which takes a firmware-dependent time; flash timing depends on the part | Record the figures on first use and set the driver's timeouts from them |

JLINK-OPEN-03 is the one that could change a reported number. The other three
would show up as an outright failure, not a wrong figure.

## 5. What this driver does not do

| Not supported | Reason |
|---|---|
| RTT channels other than up-channel 0 | Not republished on the server's RTT port (§2.2) |
| Unlimited software breakpoints in flash | The probe's envelope is four hardware breakpoints; software breakpoints in RAM are GDB's business |
| Semihosting | Not required; RTT serves the same purpose without halting |
| Multi-core or multi-target sessions | One target per connection. Two probes are two instruments in the bench configuration |
| Flashing a raw binary or hex file | The ELF is needed anyway for symbols, so it is the single input. `monitor loadbin` is reachable through `monitor()` if a raw image is ever required |
