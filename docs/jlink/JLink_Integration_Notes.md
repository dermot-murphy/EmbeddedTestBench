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

That is the `gdb` backend, and the default. Since #71 a probe can instead be
given `backend: segger`, which drives it with SEGGER's own J-Link Commander and
RTT Logger and needs no GDB - for a bench that flashes, verifies, erases,
reads and writes memory, resets and reads RTT, and nothing more. §4.9 says what
it does and what of it is verified (AD-30).

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
| JLINK-OPEN-02 | GDB/MI output of the installed GDB | **Closed 2026-10-04** (ETB-SYS5-002 §6.2). Info, call stack, a variable by name, a breakpoint on `main`, an instruction step and `compare-sections` were parsed from GDB 14.2 against nRF52840 sensor 5C1712. One defect was found in register reads after `monitor reset` (#178), not in the MI parsing; fixed, see §4.4 | — |
| JLINK-OPEN-03 | **SWO/ITM local timestamp scaling** | The tick-to-cycle scaling depends on the trace prescaler configured by the server and the firmware. Implemented from the ARMv7-M architecture reference manual; unconfirmed | Measure a known interval with `CYCLE_COUNTER` and with `SWO_ITM` and compare. Until then, quote SWO figures as provisional (CON-05) |
| JLINK-OPEN-04 | RTT control-block discovery and flash timing | **Figures recorded 2026-10-04** (ETB-SYS5-002 §9): chip erase 0.6 s; flash and verify 14.7 s for a 1.17 MB HEX (V10 with SoftDevice) and 17.0 s for 1.34 MB (V11 with SoftDevice and bootloader); RTT output within 20 s of reset and run. The driver's 180 s flash timeout covers these | Set tighter timeouts only with more figures |

| JLINK-OPEN-05 | The `segger` backend on a real probe (#71) | **Closed 2026-11-14** (§4.9). Run on 5C1712 with J-Link OB V8 (S/N 682395790) and Commander V9.42. Every operation the backend offers worked, after one fix: Commander's connect notices had been taken for errors. A DHCSR read does not halt the core. A halt does not survive Commander's exit, so `halt` on this backend always fails, as designed. Erase, UICR write, flash with `--preserve`, `reset --run` and RTT all worked | - |

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

### 4.3 Resetting into a running target (issue #177)

Verified on 5C1712 (nRF52840, J-Link OB V8, GDB Server V9.42, GDB 15.2.90
from Arm GNU Toolchain 14.2.Rel1),
2026-10-05. The GDB Server halts the core after `monitor reset`, whatever the
reset type: after `monitor reset 0` DHCSR read `0x00030003`, the DWT PC sample
register `0xE000101C` read `0xFFFFFFFF`, and RTT stayed silent. `reset(halt=False)`
therefore resumes the core with `-exec-continue` after the reset; the firmware
then logged its periodic `Waking n` lines for the whole 20 s watched. The CLI's
`reset --run` was never affected, because `close()` sends `monitor go`.

Checking whether the core runs: J-Link Commander's `mem32 E000EDF0 1` does not
halt the core on connecting, though ending its session resumed a halted one.
`nrfjprog --memrd` halted a running core and left it halted, so it is not a
check of whether a target is running.

### 4.4 Registers after a reset (issue #178)

Same bench, 2026-10-05. GDB does not see what a `monitor` command does to the
core. After `monitor reset` and `monitor halt`, GDB still reported the
registers it had read at attach: `program_counter()` gave `0x00025F40`, the PC
from before the reset, while the server's `monitor reg pc` gave `0x00000A80`,
the reset handler named by the vector table. After `maintenance flush
register-cache` GDB read `0x00000A80`, SP `0x20000400`, LR `0xFFFFFFFF` and
xPSR `0x01000000`. `reset()` now sends that flush after every reset. In GDB
15.2.90, `flushregs` is a deprecated alias of the same command.

### 4.5 Flashing a running target (issue #259)

Kepler bench, 2026-10-16 (TX-1074). After `probe.reset` with `halt: false`
the core ran, and the next `probe.flash` failed before programming anything:

```
GdbError: -interpreter-exec console "monitor reset" failed: Cannot execute this command while the target is running.
Use the "interrupt" command to stop the target
and then try again.
```

GDB itself refuses to pass a `monitor` command on while it has the target
running. `reset()` and `flash()` now halt a running core with `-exec-interrupt`
first, so a specification no longer needs a `probe.halt` step before
`probe.flash`. The simulated GDB refuses `monitor` while running in the same
words, which is how the suite caught it.

### 4.6 A failed connect stops the server it started (issue #254)

Kepler bench, 2026-10-21 (TX-1121). A bench entry with no `gdb_executable`
started `JLinkGDBServerCL.exe` and then found no GDB. `connect` raised, but no
probe existed yet for `bench.close()` to close, and the server ran on for two
and a half hours holding the probe until it was killed by hand.

`connect` now stops the server whenever it raises after starting it: no GDB
found, GDB failing to start, or the probe failing to build. A failure in
`initialise` (opening the session, attaching) already closed the probe, which
stops its server. `GdbServer.stop()` does nothing to a server this connect did
not spawn, so one that was already listening is left running.

### 4.7 Flashing combined HEX images in turn (issue #253)

Kepler bench, 2026-10-20 (TX-1084), GDB 15.2 on Windows, images on `U:`. In
one run, the third `probe.flash` of three combined images made GDB print that
the image flashed before it "has changed; re-reading symbols", and GDB
answered nothing more; every later probe step, the teardown included, failed.

**Cause, confirmed on 5C1712 on 2026-10-23.** After a flash, `flash` reads the
image as GDB's exec file so that `verify` can compare against it. GDB's `load`
first re-reads any symbol file whose modification time has changed since it
was read, and re-reading a combined HEX file this way hangs GDB. Neither the
images nor their age matter; what matters is the exec file's time changing
between two flashes - a rebuild, a copy, or a mapped drive reporting a new
time. Flashing DEBUG, moving the DEBUG file's time, then flashing RELEASE: on
`develop` GDB stopped answering the `load` in 3 runs of 4; with the fix, 3 of
3 flashed and verified.

`flash(path)` now discards the exec file (`-file-exec-and-symbols` with no
argument) immediately before `load "<path>"`, so GDB holds no file to re-read.
The image is still read as the exec file after the load, for `verify`. Calling
`probe.load_symbols` with a HEX file between flashes, as a workaround, made it
the exec file again, which is why that did not help.

### 4.8 Restoring an image set, keeping UICR (issue #264)

5C1712, 2026-10-23. `probe.restore` was used to go from a non-default image
(the DEBUG combined image) to a known one (the RELEASE combined image) and then
back to the sensor's normal image (a full-flash backup), in one session. Every
image verified, and the whole UICR page, 784 bytes from `0x10001000`, read the
same at the end as at the start.

The run also showed why the whole page is kept rather than the sensor ID alone.
A plain `probe.flash` of the DEBUG image with `preserve` on `0x10001080` only
left `PSELRESET[0]` and `PSELRESET[1]` (`0x10001200`, `0x10001204`) erased:
the image's UICR record does not carry them. The firmware writes them back
itself at its next boot, which hides the loss, but a specification that read
UICR straight after the flash would have seen it. `restore` keeps the page by
default (`keep=(NRF52_UICR,)`).

### 4.9 The `segger` backend (issue #71)

Selected with `backend: segger` in the probe's `options`, or `--backend
segger` on `benchtools jlink`. Each operation is one run of `JLink.exe` with a
command file (`exitonerror 1`, the commands, `q`); RTT is read by
`JLinkRTTLogger.exe` into a file the driver reads as it grows.

| Operation | Commands | Check made by the driver |
|---|---|---|
| `info` | none: the start-up banner | - |
| `flash` | `r`, `h`, `loadfile <image>` | every range of the image read back with `savebin` and compared |
| `verify` | `savebin` per range | the same comparison |
| `erase` | `r`, `h`, `erase` | flash word at 0 read back in a new run; must be `0xFFFFFFFF` |
| `read` | `savebin <file>, <addr>, <n>` | the file holds exactly *n* bytes |
| `write` | `w4` per aligned word, `w1` per other byte | read back in a new run; must match. Not by default in the peripheral or system region, where write-1-to-clear bits do not read back (`--no-read-back` skips it anywhere) |
| `reset`, `run`, `halt` | `r` + `h` or `g`; `g` (always); `h` | DHCSR read in a new run: `run` and `reset --run` raise if still halted, `halt` raises if Commander's exit let the core go |
| close | `g`, unless `leave_halted` | - |
| `rtt` | `JLinkRTTLogger.exe -Device -If -Speed [-USB] -RTTChannel 0 <file>` | a logger that stops is reported with what it printed |

`var`, `stack`, `time`, `run --until`, breakpoints, registers, `monitor` and
writing to RTT are refused, naming the operation and the backend, before any
tool runs.

**What was checked, and how (2026-11-13).** Nothing in this section was run
against a probe. The local manual (`Doc/Manuals/UM08001_JLink.pdf`, V9.42) no
longer carries Commander's command reference, so the syntax was read from the
help and diagnostic strings inside `JLink.exe` and `JLinkRTTLogger.exe`
V9.42. `JLink.exe` was **not** started, even for help: it has no help option
among its command-line options (an unknown one is reported as "Unknown command
line option"), and it was not certain that it would exit without opening the
USB probe.

| Item | Status |
|---|---|
| Options `-NoGui`, `-Device`, `-If`, `-Speed`, `-USB`, `-AutoConnect`, `-CommandFile`; `-NoGui` and `-AutoConnect` take a value | In the binary's strings |
| `ExitOnError <1\|0>`, `h`/`Halt`, `g`/`Go`, `erase` (no range: chip erase), `loadfile <file> [, <Addr>] [, noreset\|reset]`, `savebin <file>, <addr>, <n> (hex)`, `w1`/`w4 <addr>, <data> (hex)`, `q` | In the binary's strings |
| `r` for reset | Help text "Reset CPU." is there; the name beside it could not be read. **Unverified** |
| Banner `S/N:`, `Firmware:`, `Hardware version:` | Format strings in the binary |
| Exit status when `ExitOnError` stops a run | **Unverified**; the driver also fails a run on any of the binary's error messages |
| A quoted file name with a space | **Unverified**; logged when used |
| Whether `w4` into flash or UICR programs the part or only the DLL's cache | **Unverified**; each write is read back in a new run, which would show it |
| Whether a chip `erase` also erases the nRF52840's UICR | **Unverified**; only the flash word at 0 is checked |
| Whether a core halted by `h` stays halted after Commander exits | **Unverified**; on 2026-10-05 ending a session resumed a halted core (§4.3). The simulator models the resume |
| RTT Logger options; its default channel is 1 | In the binary's strings; the logger ran on 5C1712 on 2026-09-26 with `-RTTChannel 0` |
| Whether stopping the logger loses bytes not yet written | **Unverified**. It is first sent a newline on its input, as it asks for a key, and given 2 s to exit and close its file; only then terminated. Whether it reads that key from a pipe is unverified |
| Reading DHCSR with `savebin` without halting the core | **Unverified**; `mem32` did not halt it on 2026-10-05. Every reset, run and halt reads DHCSR in a new run that connects with `-AutoConnect 1`: if that connect halted a running core, `run` and `reset --run` would raise for a core that runs |
| Time cost | **Unmeasured**: each reset, run and halt is two Commander runs (the command and the DHCSR read), and stopping RTT can wait up to 2 s for the logger to quit before it is terminated. Time both on the bench |
| Commander and the logger holding the probe at the same time | **Unverified**; only one client held the probe reliably in earlier sessions |
| Tool names `JLinkExe`, `JLinkRTTLoggerExe` on Linux | **Unverified** |

**Bench check (JLINK-OPEN-05), planned before it ran.** On 5C1712, with its UICR backed up:

1. **DHCSR read does not disturb the core.** `--backend segger reset --run`;
   `read 0xE000EDF0 4` twice, in two separate runs; `halt`; `read 0xE000EDF0
   4` again. Expect `0x00050001` (running) from both reads after the reset, and
   `0x00030003` (halted) after the halt if the halt holds; `halt` itself exits
   with an error if the core ran again, and the read after it shows which. If
   the first reads
   say halted, the DHCSR read itself halts the core and the backend's state
   checks are wrong.
2. **Timing.** Time `reset --run`, `run`, `halt` (each two Commander runs) and
   the end of `rtt` (up to 2 s waiting for the logger to quit).
3. `--backend segger info`; `read 0x10001080 4`; `erase` and a read of UICR;
   `write 0x10001080 005c1712` into the erased UICR, and its read-back;
   `flash` of the V11 HEX with `--preserve 0x10001080:4`; `reset --run`;
   `rtt --duration 20`.

Each line of the table above marked unverified is then confirmed or corrected.

**Bench check result (2026-11-14, JLINK-OPEN-05).** It ran on 5C1712 with
J-Link OB-SAM3U128-V2 (firmware V8, Nov 28 2014, S/N 682395790), Commander and
RTT Logger V9.42, and Python 3.11. Before any probe use, flash and UICR were
backed up with `nrfjprog --readcode --readuicr`. UICR held CUSTOMER[0]
`0x12175C00` (ID 5C1712) and `0x10001014`/`18` = `0x000F8000`/`0x000FE000`.

- **First finding: a fix.** Every run except `info` failed with "J-Link
  connection not established yet but required for command". Commander V9.42
  connects lazily, even with `-AutoConnect 1`. The first command that needs the
  probe prints that line and then connects to the probe. The first command that
  needs the target prints "Target connection not established yet ..." and then
  connects to the target. Both lines appear on every run that succeeds. The
  first had been listed in `ERROR_MARKERS` and is now removed. A failed connect
  is still caught by the lines that follow it ("...FAILED", "Could not connect
  to the target device"). The same laziness meant that `info`'s empty command
  file never connected, so the S/N and firmware were blank. `info` now sends
  `f` (firmware info), which connects to the probe but not to the target. The
  simulator now prints both notices where Commander does.
- **DHCSR.** After `reset --run`, two `read 0xE000EDF0 4` in separate runs both
  gave `0x00050001` (running). Reading DHCSR with `savebin`, through a new
  connect, does not halt the core. The backend's state checks are therefore
  sound.
- **`halt`.** `halt` exited with "halted the core, but it was running again once
  Commander exited", and the read that followed gave `0x00050001`. Ending a
  Commander run lets a core that `h` halted run again. This is now seen with a
  halt that Commander itself made. `--backend segger halt` therefore always
  fails on this target, as this section predicted. Use `backend: gdb` to hold a
  core halted.
- **Erase.** Chip `erase` took 0.44 s inside Commander ("Erase: 0.167s"). It
  erased UICR as well: `0x10001080` and `0x10001014`..`1B` read `FF` afterwards,
  and so did the flash at 0.
- **Write into UICR.** `write 0x10001080 005c1712` read back `005c1712` in a new
  run. `w4` into UICR programs the part, not only the DLL's cache.
- **Flash.** The backup HEX (1 052 672 bytes written, flash and UICR) was
  flashed with `--preserve 0x10001080:4` in 37.9 s, read back range by range
  and passed. `0x10001080` and the bootloader address read as before.
- **Run and RTT.** `reset --run` reported running. `rtt --duration 20` logged
  57 lines: "Sensor ID is: 0x5C1712", "VERSION: V11.03.0000 (0fbb3f85)",
  "NVM Memory: PASSED". The sensor was back as before the check.
- **The logger's stop.** `JLinkRTTLogger.exe` does not read the quit key from a
  pipe. Sent a newline on its input, it was still running 10 s later, so the
  driver waited the full `quit_timeout` (2 s) and then terminated it. Sent
  CTRL_BREAK, in a process group of its own, it exited after 0.02 s with
  status `0xC000013A`, and its file held all 1016 bytes it reported as written.
  The driver now starts it that way on Windows and sends CTRL_BREAK first.
  `rtt --duration 20` went from 28.1 s to 26.1 s. Elsewhere, where CTRL_BREAK
  does not exist, the newline and the terminate remain (unverified on Linux).
- **Failed connects** (the checks that could be made without changing the
  wiring or the supply):
  - With a probe serial number that is not attached (`--serial 123456789`),
    Commander printed "Connecting to J-Link via USB...FAILED" and exited 1.
    The `...FAILED` marker caught it.
  - With `--interface JTAG` on this SWD-only target, Commander stopped at a
    `JTAGConf>` prompt for the chain position and took the next command as its
    answer. It then exited **0**, with no error line at all. The driver caught
    it only because the read wrote no file. `JTAGConf>` is now a marker.
  - Not run, because they need someone at the bench: the supply off, with the
    J-Link back-powering the sensor (§4.3), and the probe unplugged. Their
    wording is still unseen.
- **Timing** (each wall clock time includes about 0.4 s for Python to start;
  one Commander run alone is about 0.22 s):

  | Command | Commander runs | Time |
  |---|---|---|
  | `info` | 1 (`f`) | 0.6 s |
  | `read` 4 bytes | 1 | 1.0 s |
  | `halt` (fails, see above) | 2 | 1.0 s |
  | `reset --run`, `run` | 2 | 1.3 s |
  | `write` with read-back | 2 | 1.6 s |
  | `erase` with blank check | 2 | 2.0 s |
  | `flash` of 1.05 MB with read-back | 2 + one per range | 37.9 s |
  | `rtt --duration 20` | 2, then the logger | 28.1 s with the 2 s wait; 26.1 s with CTRL_BREAK |

**The table above, item by item, after the check:**

| Item | Result |
|---|---|
| `r` for reset | Confirmed: "Reset: Reset device via AIRCR.SYSRESETREQ." |
| Exit status | A run that succeeds exits 0. A failed probe connect exits 1. A JTAG chain prompt exits 0 with no error line, so the output markers are needed, not the status alone |
| A quoted file name with a space | Not exercised: the scratch paths have no spaces |
| `w4` into UICR | Confirmed: it programs the part |
| Chip `erase` and UICR | Confirmed: UICR is erased too |
| A halt surviving Commander's exit | It does not: the core runs again |
| Stopping the logger | It does not read the key from a pipe. CTRL_BREAK stops it at once with its file complete |
| DHCSR read without halting | Confirmed: it does not halt |
| Commander and the logger at once | Not exercised: the CLI runs nothing else while the logger reads |
| Linux tool names | Not exercised |

**`halt` on this backend.** If ending a Commander run resumes the core, as it
did once on 2026-10-05 (§4.3), then **`--backend segger halt` always fails**:
the core is halted, Commander exits, the core runs again, and the DHCSR read
that follows says so. The driver raises rather than report a halted core that
is running. A core that has to stay halted - to read it at rest, to keep it
off the air - needs `backend: gdb`. `reset` without `--run` only logs it.

## 5. What this driver does not do

| Not supported | Reason |
|---|---|
| RTT channels other than up-channel 0 | Not republished on the server's RTT port (§2.2) |
| Unlimited software breakpoints in flash | The probe's envelope is four hardware breakpoints; software breakpoints in RAM are GDB's business |
| Semihosting | Not required; RTT serves the same purpose without halting |
| Multi-core or multi-target sessions | One target per connection. Two probes are two instruments in the bench configuration |
| Flashing a raw binary | An ELF or Intel HEX image is flashed and verified (issue #69); a raw binary has no addresses. `monitor loadbin` is reachable through `monitor()` if one is ever required. The `segger` backend refuses one too |
| Symbols, breakpoints, stepping, registers, call stack, timing or RTT writes on the `segger` backend | It has no GDB (§4.9); select `backend: gdb` |
| `nrfjprog` | Nordic's tool, not SEGGER's, and nRF-specific; not part of either backend (#71) |
