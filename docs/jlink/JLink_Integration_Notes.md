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
Each is found on `PATH` or in its installer's default directory
(`Program Files/SEGGER/JLink*`, `Program Files (x86)/Arm GNU Toolchain
arm-none-eabi/*/bin`), newest release first; anywhere else, pass `--server` or
`--gdb`. A plain `gdb` is used only if it can debug ARM: MinGW's cannot.

```
python -m benchtools jlink --resource jlink:// --device nRF52840_xxAA --elf build/app.elf info
```

Options naming the probe come before the sub-command, as they do for the
oscilloscope: `jlink --resource … <sub-command> [arguments]`.

The driver starts `JLinkGDBServerCL.exe` with `-nogui -strict`, and stops it when
the probe is closed. `-nogui` matters: without it the server opens a window and
waits, which hangs an unattended run. `-singlerun` must not be added: the server
then exits when the driver's readiness check disconnects, before GDB attaches
(issue #69). If a server is already listening on 2331 — started by hand, or by
a service — it is used as it stands and left running afterwards.

The GDB Server halts the core when GDB attaches, and does not resume it on
detach. The driver sends `monitor go` before detaching, so every sub-command
except `halt`, `reset` (without `--run`) and `run --until` leaves the target
running. Before this, a `read` or `verify` left a sensor halted and silent on
BLE until it was reset (issue #69).

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
| JLINK-OPEN-01 | Execution on a Windows host | **Closed 2026-10-04** (ETB-SYS5-002 §6.1, §6.2). Every probe scenario of the hardware qualification ran on Windows 10, with GDB Server V9.42 and Arm GNU 14.2 GDB | — |
| JLINK-OPEN-02 | GDB/MI output of the installed GDB | **Closed 2026-10-04** (ETB-SYS5-002 §6.2). Info, call stack, a variable by name, a breakpoint on `main`, an instruction step and `compare-sections` were parsed from GDB 14.2 against nRF52840 sensor 5C1712. One defect was found in register reads after `monitor reset` (#178), not in the MI parsing | — |
| JLINK-OPEN-03 | **SWO/ITM local timestamp scaling** | The tick-to-cycle scaling depends on the trace prescaler configured by the server and the firmware. Implemented from the ARMv7-M architecture reference manual; unconfirmed | Measure a known interval with `CYCLE_COUNTER` and with `SWO_ITM` and compare. Until then, quote SWO figures as provisional (CON-05) |
| JLINK-OPEN-04 | RTT control-block discovery and flash timing | **Figures recorded 2026-10-04** (ETB-SYS5-002 §9): chip erase 0.6 s; flash and verify 14.7 s for a 1.17 MB HEX (V10 with SoftDevice) and 17.0 s for 1.34 MB (V11 with SoftDevice and bootloader); RTT output within 20 s of reset and run. The driver's 180 s flash timeout covers these | Set tighter timeouts only with more figures |

JLINK-OPEN-03 is the one that could change a reported number. The other three
would show up as an outright failure, not a wrong figure.

### 4.1 First run on hardware (issue #69)

On 2026-09-26 and -27 the driver ran against a real bench: Windows 10, J-Link
OB-SAM3U128-V2-NordicSem (S/N 682395790, firmware of 2014), J-Link software
V9.42, Arm GNU Toolchain 14.2.Rel1 GDB 15.2, and a Kappa X sensor on an
nRF52840. It carried out erase, flash of an Intel HEX image (SoftDevice and
application), a write of the sensor ID to UICR `0x10001080`, reset, RTT capture
and a BLE check, for V10.01.2000 and then V11.00.0000. What that run found, and
what the driver now does about it:

| Observed | Driver behaviour |
|---|---|
| `-singlerun` made the spawned server exit on the readiness check | Flag removed; `stop()` ends the server |
| The server halts the core on attach and leaves it halted on detach | `close()` sends `monitor go` unless `leave_halted` |
| `monitor version` is unsupported | Identity read from the server's start-up banner |
| `monitor flash erase` said O.K. and erased nothing while the firmware ran | Reset and halt first; blank-check afterwards |
| GDB exited on `file` then `load` of a HEX file on a mapped drive | `load <file>` first, then read it for verify |
| `+download,{...}` is not valid MI | Parser accepts the unnamed tuple |
| `monitor rtt start` is unsupported; RTT is served unasked | Command sent, error ignored |

Figures from that run, for JLINK-OPEN-04: flashing and verifying took 14.2 s
for V10 (416 664 bytes, 9 sections) and 16.2 s for V11 (473 518 bytes, 12
sections, including UICR). A write to UICR through `write` was programmed and
read back identically with `nrfjprog`. The erase also cleared UICR, so the
sensor ID has to be backed up and written back afterwards.

Flashing the V11 image (whose HEX includes a UICR record) over a part whose
UICR already held the sensor ID erased the ID too, and the sensor came up as
`KAPPA_FFFFFF_V11.00.00`. `flash --preserve 0x10001080:4` keeps it: the range is
read first, written back after programming and checked.

The debug operations were then run against the V11 debug build's ELF:

| Operation | Result |
|---|---|
| `flash` of the ELF | 295 592 bytes, 13/13 sections verified, 10.1 s; the bootloader started the new application |
| `var` / `read_variable` | Scalars and the firmware's stack monitor structure (`api_stack_data`), field by field |
| Maximum stack depth | 1 400 of 12 000 bytes, from the firmware's 0xA5 stack paint read over the probe; the firmware's own `bytes_used` agreed |
| Breakpoint at an event, `stack` | Halted at `API_Battery_PowerOnInit`; four frames back to `main` |
| RAM read and write at that event | Written by address and by name, read back both ways |
| `time` (cycle counter) | `HAL_Manager_PowerOnInit` to `API_Log_PowerOnInit`: 11 263 cycles, 176 µs |
| Call stack on a crash | Breakpoints on the fault handlers; `RD EOL START 60 30` over BLE stopped in `app_error_handler_bare` with error code 8, fourteen frames back through `HAL_SPI_Radio_Init` to `main` |

**Halting a target that runs a SoftDevice.** The GDB Server halts the core when
GDB attaches. A short halt while the SoftDevice idled (PC in the SoftDevice's
wait loop) was survived, and `info` and `rtt` left the sensor running. A halt
at a breakpoint, a step, or a long halt is not: resume from one with a reset
(`reset --run`), not `run`. Timing and breakpoints were therefore run from reset,
on code that executes before the SoftDevice starts, and every such session ended
with a reset. Once, after a UICR write and a `reset --run`, the sensor restarted
by watchdog and logged "Fatal error"; it has not recurred and is not explained
(the firmware configures the watchdog to pause while halted). Check a sensor
with a non-halting RTT reader such as `JLinkRTTLogger` after using the driver
on it.

### 4.2 Reading RTT without stopping the target (issue #95)

Verified on 5C1712 (nRF52840, s140, J-Link OB V8, GDB Server V9.42), 2026-09-28,
with a BLE link to the sensor open throughout:

| Set-up | Core | RTT | BLE link |
|---|---|---|---|
| GDB Server with `-nohalt`, no GDB client | running | served on the RTT port | stayed up |
| The same, then GDB `target extended-remote` | **halted** (PC unchanged over 6 s) | silent | **dropped** |

`-nohalt` stops the *server* halting the core; GDB's attach halts it anyway.
After the detach the SoftDevice logged `<error> app: Fatal error` and the sensor
stopped advertising until `nrfjprog --reset`.

So a test that reads a Nordic target's log while it talks to it over BLE uses
`connect(attach=False)`, which starts the server with `-nohalt` and never
attaches, or declares its probe as driver `jlink-rtt`, which always does. Only
RTT works on such a link; anything else needs the attach. A bench file offers
both as separate aliases (`benches/lab1.yaml`: `probe` and `rtt`), on separate
ports, since only one can hold the J-Link at a time.

## 5. What this driver does not do

| Not supported | Reason |
|---|---|
| RTT channels other than up-channel 0 | Not republished on the server's RTT port (§2.2) |
| Unlimited software breakpoints in flash | The probe's envelope is four hardware breakpoints; software breakpoints in RAM are GDB's business |
| Semihosting | Not required; RTT serves the same purpose without halting |
| Multi-core or multi-target sessions | One target per connection. Two probes are two instruments in the bench configuration |
| Flashing a raw binary | An ELF or Intel HEX image is flashed and verified (issue #69); a raw binary has no addresses. `monitor loadbin` is reachable through `monitor()` if one is ever required |
