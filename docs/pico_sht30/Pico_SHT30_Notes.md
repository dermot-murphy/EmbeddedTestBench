# Pico 2 + SHT30-D Thermometer Notes

| Field | Value |
|---|---|
| Document ID | ETB-PICO-001 |
| Version | 1.3 |
| Date | 2026-10-03 |
| Element | `PICO-` — `benchtools.instruments.pico_sht30` and `firmware/pico_sht30` |
| Issue | #104; `flash` #127; `rd` command set #131 |

A Raspberry Pi Pico 2 reads the local temperature from a DollaTek SHT30-D
module and reports it over USB, together with the firmware's name, copyright,
version and the commit it was built from. This
note covers the hardware, the wiring, how to build and flash the firmware, how
to read it from the host, the facts taken from the reference documents, the
MISRA C position, and what remains to confirm on a bench.

## 1. Hardware

| Part | What it is | Reference |
|---|---|---|
| Raspberry Pi Pico 2 | RP2350A: dual Arm Cortex-M33 (or Hazard3 RISC-V) at 150 MHz, 520 KB SRAM, 4 MB flash, USB 1.1 device, two I2C controllers | Pico 2 datasheet, RP2350 datasheet (§2 of `References.md`) |
| DollaTek SHT30-D | A breakout board for the **Sensirion SHT30-DIS**: the sensor, a decoupling capacitor, I2C pull-up resistors, and an ADDR strap. Sold under several names (GY-SHT30-D). DollaTek publishes no datasheet of its own; the Sensirion datasheet is the authority for everything the firmware does. | Sensirion SHT3x-DIS datasheet |

SHT30-DIS in brief (Sensirion datasheet): 2.15–5.5 V supply; I2C up to 1 MHz;
address 0x44 (ADDR low) or 0x45 (ADDR high); temperature −40 to 125 °C
specified, ±0.2 °C typical from 0 to 65 °C; humidity 0–100 %RH, ±2 %RH typical
from 10 to 90 %RH.

## 2. Wiring

![Pico 2 pinout](datasheets/pico-2-r4-pinout.svg)

*Pinout: Raspberry Pi Ltd, `raspberrypi/documentation`, CC BY-SA 4.0.*

| SHT30-D pin | Pico 2 pin | Pico 2 function |
|---|---|---|
| VIN | 36 | 3V3(OUT) |
| GND | 38 | GND |
| SDA | 6 | GP4 — I2C0 SDA |
| SCL | 7 | GP5 — I2C0 SCL |
| ADDR | GND (or leave unconnected if the module pulls it low) | address 0x44 |
| ALERT | not connected | — |

The module carries its own pull-ups; the firmware enables the RP2350's internal
pull-ups as well, which is harmless in parallel and keeps a bare sensor usable.
Keep the wires short (under 30 cm at 100 kHz), and mount the sensor away from
the Pico: the RP2350 and its regulator warm the board by a degree or more, and
the sensor will report that faithfully.

Different wiring is a build option, not a source edit:

```
cmake -S firmware/pico_sht30 -B build/pico_sht30 \
      -DCMAKE_C_FLAGS="-DBOARD_I2C_SDA_PIN=16U -DBOARD_I2C_SCL_PIN=17U -DBOARD_SHT30_ADDRESS=0x45U"
```

## 3. Building and flashing

Prerequisites: CMake ≥ 3.13, the Arm GNU toolchain (`arm-none-eabi-gcc`), and
the Pico C SDK 2.1.1 or later with its TinyUSB submodule. SDK 2.x builds
`picotool` from source on first use if it is not installed.

```
git clone --branch 2.1.1 https://github.com/raspberrypi/pico-sdk
git -C pico-sdk submodule update --init lib/tinyusb
export PICO_SDK_PATH=$PWD/pico-sdk

cmake -S firmware/pico_sht30 -B build/pico_sht30
cmake --build build/pico_sht30 -j
```

This produces `build/pico_sht30/pico_sht30.uf2`. The configure step reads the
short SHA of the commit being built (`git rev-parse --short=7 HEAD`), prints it
as `pico_sht30: FIRMWARE_GIT_SHA=<sha>`, and builds it into the image, where
`rd sha` reports it. Outside a git checkout it is `unknown`. A new commit makes
the next build re-configure, so the image never carries a stale SHA.

To download it to the Pico 2, use one command (#127):

```
benchtools thermo -r /dev/ttyACM0 flash build/pico_sht30/pico_sht30.uf2 --expect-version V1.00.0000
benchtools thermo -r COM5 flash build\pico_sht30\pico_sht30.uf2          # Windows
benchtools thermo -r '' flash build/pico_sht30/pico_sht30.uf2           # blank board; port found afterwards
```

It does what used to be three manual steps, and then checks the result:

1. **Into the bootloader.** If a drive named **RP2350** is already mounted, the
   Pico is in its bootloader already and that drive is used. This is how the
   first flash of a blank Pico 2 works: a board with no image starts in its
   bootloader. Otherwise the running thermometer is sent `bootsel`. If the port
   does not answer the protocol - another image is running, for instance - it
   is opened and closed at 1200 baud instead, which the Pico SDK's USB serial
   takes as a request to reboot into the bootloader. On Windows the Pico
   often reboots while the port is still being opened, and Windows then
   reports "a device attached to the system is not functioning". That is the
   reset working, so it is kept as a note in the result rather than treated as
   a failure. The command then waits for the drive (15 s,
   `--bootloader-timeout`); the drive appearing is what shows the reset worked.
2. **Copy.** The UF2 is checked first: every block must be well formed and for
   an RP2350, and the image must carry the thermometer's name,
   `Pico 2 SHT30 Temperature Sensor` (pass `--any-image` to flash something
   else). It is then copied onto the drive.
   The Pico reboots as the last block lands, and the drive goes away.
3. **Check.** The serial port comes back (20 s, `--port-timeout`; with `-r ''`
   it is found by the Raspberry Pi USB vendor ID) and the thermometer is
   identified with `rd`. Three checks are made: `rd name` must be the
   thermometer's name; `rd version` must be the version given with
   `--expect-version` (in the form `VX.YY.ZZZZ`) or, without it, the version
   stored in the image; and `rd sha` must be the commit SHA stored in the
   image. The version and the SHA are read from the image itself, each a
   NUL-terminated string that must occur exactly once; if either cannot be
   found that way, its check is skipped and a note says so. A matching SHA
   shows that the image just copied is the one running, not an older build of
   the same version.

The result is printed as JSON: the image, the drive, how the bootloader was
reached (`already-in-bootloader`, `bootsel` or `1200-baud`), the firmware's
name, copyright, version and SHA before and after, and each check with what was expected and what was found. The command
exits 0 only if every check passed; a mismatch, a timeout or a failed copy
exits 1. `--no-verify` skips the check, and `--drive E:` (or a mount point)
names the drive if it cannot be found. Drives are searched for on Windows
(drive letters), Linux (`/media`, `/run/media`, `/mnt`) and macOS (`/Volumes`);
on any other system, pass `--drive`. `-r sim://` runs the whole sequence
against a simulated board.

**When `flash` cannot help.** If the firmware has crashed, or the Pico does not
appear on USB at all, nothing on the host can reach it. Then use the button,
which always works:

1. Hold **BOOTSEL** and plug the Pico into USB.
2. A drive named **RP2350** appears.
3. Either copy `pico_sht30.uf2` onto it by hand, or run `flash` as above,
   which finds the drive already present. The Pico reboots into the
   thermometer and enumerates as a USB serial port (`/dev/ttyACM0` on Linux,
   `COMn` on Windows).

An SWD probe on the Pico's debug header is the other way in.

`flash` was confirmed on a real Pico 2 (USB serial AC5483CD0798FB0B, COM14)
on the bench PC (Windows 10) on 2026-10-03, by all three routes into the
bootloader: a board already in its bootloader, the running thermometer
(`bootsel`) and the 1200-baud reset. Each exited 0 with every check passing,
the drive (D:) was found without `--drive`, and with `-r ""` the port was
found by vendor ID. The image was built on the bench PC with Pico SDK 2.1.1,
Arm GNU Toolchain 14.2.Rel1 and picotool 2.1.1. Those runs used the firmware
of the time, which answered `ver`, so they checked its title, version and
build date. Later the same day the `rd` firmware of #131 (built from commit
`5c80ae7`) was flashed with `benchtools thermo -r COM14 flash pico_sht30.uf2`:
method `bootsel`, and the `name`, `version` (`V1.00.0000`) and `sha`
(`5c80ae7`) checks all passed (§7.1). Drive discovery on Linux and macOS has
not been tried on hardware. See PICO-OPEN-05 in §7.

Host unit tests for the firmware, no Pico needed:

```
cmake -S firmware/pico_sht30/test -B build/pico-tests
cmake --build build/pico-tests && ctest --test-dir build/pico-tests --output-on-failure
```

On Windows, use clang rather than MinGW GCC 6.3, which stops with an internal
compiler error on `-fsanitize=address`; ETB-SWE4-001 §1.4b gives the commands.

### 3.1 The version number

The version is `V<major>.<minor>.<patch>`, the minor number as two digits and
the patch number as four: `V1.00.0000` is the baseline set by #131. It follows
semantic versioning and is bumped with **every** change to the firmware or its
host driver:

| Change | Bump | Example |
|---|---|---|
| A breaking change to the protocol | major | `V1.00.0000` → `V2.00.0000` |
| An added command or feature | minor | `V1.00.0000` → `V1.01.0000` |
| A fix | patch | `V1.00.0000` → `V1.00.0001` |

It is edited in `firmware/pico_sht30/include/firmware_version.h` and nowhere
else (PICO-FR-002). The name and copyright are defined there too.

## 4. Using it

In a terminal (any serial program, 115200 8N1, although USB ignores the rate):

```
rd name
ACK rd name = Pico 2 SHT30 Temperature Sensor
rd copyright
ACK rd copyright = (c) 2026 Dermot Murphy
rd version
ACK rd version = V1.00.0000
rd sha
ACK rd sha = 1a2b3c4
rd temperature
ACK rd temperature = 22.85
rd humidity
NAK rd humidity = Error
status
ok status=0x0010
```

The commands (protocol 2.0, `firmware/pico_sht30/include/protocol.h`):

| Command | Reply |
|---|---|
| `rd name` | `ACK rd name = Pico 2 SHT30 Temperature Sensor` |
| `rd copyright` | `ACK rd copyright = (c) 2026 Dermot Murphy` |
| `rd version` | `ACK rd version = V1.00.0000` |
| `rd sha` | `ACK rd sha = <7-character commit SHA, or unknown>` |
| `rd temperature` | `ACK rd temperature = <°C to 2 places>`, e.g. `22.85`, `-1.24`; `ACK rd temperature = Error` when the sensor could not be read |
| `rd <anything else>` | `NAK rd <option> = Error` |
| `rd` with no option, or two | `err 2 wrong number of arguments` |
| `status` | `ok status=0x<hhhh>` - the sensor's status register |
| `sreset` | `ok` - soft-reset the sensor |
| `ecureset` | `ok`, then the Pico reboots (this was `reset` before #131) |
| `bootsel` | `ok`, then the Pico reboots into its USB bootloader |
| `help` | one `# <command> - <help>` line per command, then `ok` |

`ver`, `temp` and `reset` were removed by #131 and now answer
`err 1 unknown command`. The temperature is rounded half away from zero from
the sensor's thousandths of a degree (22.848 → `22.85`, −1.235 → `-1.24`), and
a value that rounds to zero is `0.00`, never `-0.00`. Humidity is measured with
every reading but is not reported.

From the host:

```
benchtools thermo -r /dev/ttyACM0 info        # name, copyright, version, sha
benchtools thermo -r /dev/ttyACM0 rd sha
benchtools thermo -r /dev/ttyACM0 temp --count 10 --interval 1
benchtools thermo -r /dev/ttyACM0 ecureset
benchtools thermo -r sim:// temp              # no hardware
```

```python
from benchtools.instruments.pico_sht30 import NoReadingError, PicoSht30

with PicoSht30.connect("/dev/ttyACM0") as thermometer:     # COM5 on Windows
    print(thermometer.name, thermometer.version, thermometer.sha)
    try:
        print("%.2f °C" % thermometer.temperature())
    except NoReadingError:
        print("the sensor could not be read")
```

Connecting reads the four identity values and refuses a device whose `rd name`
is not `Pico 2 SHT30 Temperature Sensor`. In a bench configuration the driver is
named `pico-sht30` (alias `thermometer`).

| Reply | Meaning | What to check |
|---|---|---|
| `ACK rd temperature = Error` | No reading: the sensor did not acknowledge, a frame failed its CRC, or the bus timed out. The driver raises `NoReadingError`. | Use `status` to see which: the codes below |
| `err 4 the sensor did not acknowledge` | NACK at 0x44 (`status`, `sreset`) | Wiring, power, ADDR strap (0x45?) |
| `err 5 the sensor checksum did not match` | Corrupted frame (`status`) | Wire length, pull-ups, noise |
| `err 6 I2C bus timeout` | Transfer did not complete (`status`, `sreset`) | SDA/SCL swapped, a line held low |
| `NAK rd <option> = Error` | An option the firmware does not know. The driver raises `RdRefusedError`. | Spelling and case: options are lower case |

### 4.1 On a bench

Both shipped benches carry the thermometer as `temp`, named `TEMP` in the event
log (#126):

```yaml
temp:
  driver: pico-sht30
  resource: /dev/ttyACM2        # site-specific; sim:// in benches/simulated_bench.yaml
  timeout: 5.0
  event: TEMP
```

A specification uses it as `temp.read`, which sends `rd temperature`, and can
give it another name in the
event log, e.g. `temp: {driver: pico-sht30, event: ROOM}` - see the
[Bench Runner Guide §6.3](../Bench_Runner_Guide.md#63-event-log-names-which-instrument-said-what).
`TEMP` is also the driver's default, so it applies on any bench that names none.

## 5. Facts taken from the reference documents

| Fact | Value | Where used |
|---|---|---|
| Measure, single shot, high repeatability, no clock stretching | command 0x2400 | `SHT30_CMD_MEASURE_HIGH` |
| Max measurement duration, high repeatability | 15 ms | wait 16 ms |
| Read status register | 0xF32D | `SHT30_CMD_READ_STATUS` |
| Clear status register | 0x3041 | `SHT30_CMD_CLEAR_STATUS` (defined, not used) |
| Soft reset | 0x30A2, ready within 1.5 ms | wait 2 ms |
| CRC-8 | poly 0x31, init 0xFF, no reflection, no final XOR; CRC(0xBEEF) = 0x92 | `sht30_crc8` |
| Temperature | T = −45 + 175 · S_T / (2¹⁶ − 1) | `sht30_ticks_to_millicelsius` |
| Humidity | RH = 100 · S_RH / (2¹⁶ − 1) | `sht30_ticks_to_millipercent` |
| Status bits | 15 alert pending, 13 heater, 11 RH alert, 10 T alert, 4 reset detected, 1 command failed, 0 write CRC failed | `SHT30_STATUS_*`, `STATUS_BITS` |
| Pico 2 I2C0 default pins | GP4 SDA (pin 6), GP5 SCL (pin 7) | `board_config.h` |
| Pico 2 3V3(OUT) | pin 36, up to 300 mA for external circuits | wiring |

The command codes and CRC parameters were cross-checked against Sensirion's own
open-source driver (`github.com/Sensirion/embedded-i2c-sht3x`).

## 6. MISRA C:2012

The firmware is written to MISRA C:2012 (with Amendments 2 and 3, which cover
C11). Measures taken:

* No `<stdio.h>` formatting (Rule 21.6): replies are built with the bounded
  `text.c`, never `printf`/`snprintf`. Checked by a test.
* No dynamic memory (Rule 21.3), no recursion (Rule 17.2), no variadic functions
  (Rule 17.1).
* Fixed-width types throughout (Dir 4.6), `U` suffixes on unsigned constants
  (Rule 7.2), explicit casts on every narrowing (Rule 10.x), and 64-bit
  intermediate arithmetic where 32 bits would overflow.
* Every `if … else if` chain ends in `else`, every `switch` has `default`
  (Rules 15.7, 16.4); one exit per function (Rule 15.5).
* Pointer parameters are checked for NULL; outputs are written only on success.

Recorded deviations:

| Rule | Where | Justification |
|---|---|---|
| 21.6 (required) | `hal_pico.c` | `stdio_puts_raw` and `stdio_flush` are the Pico SDK's USB CDC output path; no formatting function is used. |
| Dir 4.6 (advisory) | `hal_pico.c` | Pico SDK prototypes use `uint` and `int`; values are cast at the boundary. |
| 20.10 (advisory) | `cmd_parser.c` | `#` and `##` in the X-macros that build the dispatch table from `protocol.h`, so the protocol is defined once (PICO-NFR-004). |
| 2.2 / Dir 4.1 | `main.c` | `for (;;)` without exit is the intended behaviour of an embedded main loop. |

All of the firmware's C code, host unit tests included, also passes the
project's C coding standard (ETB-STD-002, ETB-STY-001) as checked by CStyleCheck
in CI, with no baseline (PICO-NFR-006). The Pico step uses its own module alias
map (`.cstylecheck-pico-aliases.txt`) and a short, justified exclusion list
(`.cstylecheck-pico-exclusions.yml`): the `X` of the X-macro idiom, Unity's
`setUp`/`tearDown`, and literal reference vectors in the tests.

No MISRA checker was available in the build environment; a checker run is
PICO-OPEN-04.

## 7. Bench confirmation items

| ID | Item | How |
|---|---|---|
| PICO-OPEN-01 | USB enumeration and identity | **Closed 2026-10-03** (§7.1). Flash the UF2; `benchtools thermo -r <port> info` must show the name `Pico 2 SHT30 Temperature Sensor`, copyright `(c) 2026 Dermot Murphy`, version `V1.00.0000`, and the SHA the configure step printed. `rd colour` must answer `NAK rd colour = Error`; `ver` must answer `err 1`. |
| PICO-OPEN-02 | Sensor on the bus, and a missing sensor reported | `rd temperature` must answer a value to two places; with SDA disconnected it must answer `ACK rd temperature = Error`, never a value, and `status` must answer `err 4`. **Confirmed in part 2026-10-03** (§7.1): with no module connected, `Error` and `err 4` are answered as specified. Still open: a value to two places with the module connected. |
| PICO-OPEN-03 | Accuracy | Beside a calibrated reference thermometer, away from the Pico, after 10 minutes: agreement within ±0.2 °C typical (0–65 °C) plus the reference's own uncertainty. |
| PICO-OPEN-04 | Reference PDFs and MISRA tool run | The hosts serving the PDFs were blocked in the build environment; run `fetch_datasheets.sh` and commit the files. Run a MISRA C:2012 checker over `firmware/pico_sht30/src`. |
| PICO-OPEN-05 | Reflashing with `benchtools thermo flash` (#127) | Run `flash` three ways and check that each exits 0 with every check passing: from the running thermometer (method `bootsel`); from a board started with BOOTSEL held (method `already-in-bootloader`); and from a board running other USB-serial firmware built with the Pico SDK (method `1200-baud`), which also confirms that the SDK's 1200-baud reset is enabled in such a build. Confirm that the drive is found on the bench PC's operating system without `--drive`. **Closed 2026-10-03** on Windows 10, with a 60 416-byte UF2 (118 blocks, families `absolute` and `rp2350-arm-s`) built on the bench PC with Pico SDK 2.1.1, Arm GNU Toolchain 14.2.Rel1 and picotool 2.1.1. (1) The board arrived in its bootloader as drive D:; `flash` with `-r ""` gave method `already-in-bootloader`, found the port as COM14 by vendor ID, and passed every check in about 2.5 s. (2) After a rebuild, `flash -r COM14` from the running thermometer gave method `bootsel`; the build date changed from `12:06:39Z` to `12:07:19Z` and the title, version and build checks passed. (3) With the protocol open made to fail once, `flash -r COM14` gave method `1200-baud` and the title and build checks passed. The reset was tried on the thermometer firmware, which is itself an SDK USB-serial build, not on other firmware. On Windows the Pico reboots while pyserial is still opening the port, so the open raises "A device attached to the system is not functioning"; `touch_1200` now keeps that as a note, and the drive appearing decides success. The drive was found without `--drive` on Windows; Linux and macOS have not been tried on hardware. These three runs predate #131 and checked `ver`; with the `rd` firmware of #131, `flash -r COM14` (method `bootsel`) passed its `name`, `version` and `sha` checks (§7.1). |
| PICO-OPEN-06 | The `rd` command set (#131) on a real Pico 2 | **Confirmed in part 2026-10-03** (§7.1). The #131 firmware was cross-compiled on the bench PC with no warnings, the build injected the SHA, and it was flashed to a Pico 2. Every `rd` option, the `NAK`, the `err` replies and `ecureset` behaved as specified. Still open: `rd temperature` with a real value to two places, which needs the SHT30-D module connected (PICO-OPEN-02). |

### 7.1 First run on a real Pico 2 (2026-10-03)

The bench PC runs Windows 10. The Pico 2 has USB serial number
`AC5483CD0798FB0B` and appeared as COM14. **No SHT30-D module was connected.**

The firmware was built from commit `5c80ae7` with Pico SDK 2.1.1, Arm GNU
Toolchain 14.2.Rel1 (`arm-none-eabi-gcc` 14.2.1) and a prebuilt picotool 2.1.1.
There were no warnings under `-Werror`. The UF2 is 58 368 bytes; text is
28 764 B, data 0 B and bss 3 476 B. Before the commit was made, the configure
step printed `FIRMWARE_GIT_SHA=b6213cc`; after it, the next build re-configured
itself and injected `5c80ae7`. So a new commit does reach the image.

The image was flashed with `benchtools thermo flash`, which uses the `bootsel`
command (from #127's branch), so no button was pressed. The raw replies on
COM14 were:

| Sent | Reply |
|---|---|
| `rd name` | `ACK rd name = Pico 2 SHT30 Temperature Sensor` |
| `rd copyright` | `ACK rd copyright = (c) 2026 Dermot Murphy` |
| `rd version` | `ACK rd version = V1.00.0000` |
| `rd sha` | `ACK rd sha = 5c80ae7` |
| `rd temperature` | `ACK rd temperature = Error` (expected: no sensor) |
| `rd colour` | `NAK rd colour = Error` |
| `rd` | `err 2 wrong number of arguments` |
| `ver`, `temp`, `reset` | `err 1 unknown command` |
| `status` | `err 4 the sensor did not acknowledge` (expected: no sensor) |

`benchtools thermo -r COM14 info`, and each `rd <option>` through the driver,
returned the same values. `ecureset` rebooted the Pico, and it came back
answering `rd sha = 5c80ae7`. The raw `ok` reply to `ecureset` was not
captured on its own.

After #127 was merged into this branch, `flash` confirms a new build by `rd`
instead of `ver`. `benchtools thermo -r COM14 flash pico_sht30.uf2`, with the
same image, reported `ok`, method `bootsel`, and the checks `name`
(`Pico 2 SHT30 Temperature Sensor`), `version` (`V1.00.0000`) and `sha`
(`5c80ae7`) all passed.
