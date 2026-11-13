# PICO2 Test Board User Manual

| Field | Value |
|---|---|
| **Document ID** | ETB-PICO-002 |
| **Version** | [latest, §13](#13-revision-history) |
| **Date** | [latest, §13](#13-revision-history) |
| **Element** | `PICO-` — `benchtools.instruments.pico2_test_board` and `firmware/pico2_test_board` |
| **Applies to** | Firmware `V1.00.0000` (protocol 2.2) and `develop` after #330 |
| **Issue** | #330 |

How to use the PICO2 Test Board: what it does, how it is wired, how to flash
it, every command it answers, the `benchtools pico2` command line, the Python
driver, and how to drive it from a test sequence. The engineering detail -
datasheet facts, the MISRA C position, the build internals and the bench
confirmation items - is in the
[PICO2 Test Board Notes](PICO2_Test_Board_Notes.md) (ETB-PICO-001). The
requirements are ETB-SWE1-001 §15.

Every command, reply and output shown here was read from the code
(`firmware/pico2_test_board/include/protocol.h`, `src/cmd_parser.c`,
`src/cmd_fgen.c`, `src/fgen.c` and `benchtools/instruments/pico2_test_board/`)
or run against the simulated board (`sim://`) on 2026-11-13. What has been
seen on the real board is said where it is used, and what has not is listed
in [§10](#10-limits-and-known-gaps).

---

## Contents

1. [What the board is](#1-what-the-board-is)
2. [Wiring](#2-wiring)
3. [Connecting](#3-connecting)
4. [Flashing and building](#4-flashing-and-building)
5. [Serial command reference](#5-serial-command-reference)
6. [The `benchtools pico2` command line](#6-the-benchtools-pico2-command-line)
7. [The Python driver](#7-the-python-driver)
8. [Test sequences](#8-test-sequences)
9. [Worked examples](#9-worked-examples)
10. [Limits and known gaps](#10-limits-and-known-gaps)
11. [Troubleshooting](#11-troubleshooting)
12. [Earlier names](#12-earlier-names)
13. [Revision History](#13-revision-history)

---

## 1. What the board is

A Raspberry Pi Pico 2 (RP2350) running the firmware in
`firmware/pico2_test_board`. It appears on the host as one USB serial port and
answers one text command per line. It was called the **Pico 2 SHT30
Temperature Sensor** until #330 ([§12](#12-earlier-names)).

| Function | Hardware | Commands | Range |
|---|---|---|---|
| Identity | the firmware | `rd name`, `rd copyright`, `rd version`, `rd sha` | `PICO2 Test Board`, `(c) 2026 Dermot Murphy`, `V1.00.0000`, the 7-character commit SHA of the build |
| Temperature | Sensirion SHT30-DIS on a DollaTek SHT30-D module, I2C0, address 0x44 | `rd temperature`, `status`, `sreset` | °C to two decimal places; ±0.2 °C typical from 0 to 65 °C (Sensirion datasheet) |
| Indicator LEDs | red, yellow and green LEDs, each lit when its pin is high | `wr led-<colour> on\|off`, `rd led-<colour>` | on or off, read back from the pin |
| Frequency generator, channels 1 and 2 | Adafruit UDA1334A I2S DAC: channel 1 the left output, channel 2 the right | `wr`, `rd`, `routine` | 10 Hz to 12 kHz; `sine`, `square`, `triangle`, `sawtooth`, `sine2` (two sines summed); amplitude 0 to 100 % of full scale; duty 1 to 99 %; a set number of cycles or continuous |
| Frequency generator, channel 3 | GP15, a 3.3 V logic output driven by a PWM slice | `wr`, `rd`, `routine` | 10 Hz to 12 kHz, square only, duty 1 to 99 % |
| Maintenance | the RP2350 | `ecureset`, `bootsel`, `help` | reboot; reboot into the USB bootloader; list the commands |

On the bench PC it is the instrument `pico2`, on COM14, USB serial number
`AC5483CD0798FB0B` (`benches/bench_pc.yaml`).

## 2. Wiring

Pin numbers are the Pico 2's physical pins; the pinout is in the
[Notes §2](PICO2_Test_Board_Notes.md#2-wiring).

| Signal | Pico 2 pin | GPIO | Connected to |
|---|---|---|---|
| SHT30-D VIN | 36 | 3V3(OUT) | SHT30-D VIN |
| SHT30-D GND | 38 | GND | SHT30-D GND |
| I2C0 SDA | 6 | GP4 | SHT30-D SDA |
| I2C0 SCL | 7 | GP5 | SHT30-D SCL |
| SHT30-D ADDR | — | — | GND or left open (address 0x44); ALERT not connected |
| Red LED | 24 | GP18 | LED and its series resistor; high = lit |
| Yellow LED | 25 | GP19 | LED and its series resistor; high = lit |
| Green LED | 26 | GP20 | LED and its series resistor; high = lit |
| DAC DIN | 9 | GP6 | UDA1334A DIN |
| DAC BCLK | 10 | GP7 | UDA1334A BCLK |
| DAC WSEL | 11 | GP8 | UDA1334A WSEL |
| DAC VIN | 40 | VBUS (5 V from USB) | UDA1334A VIN; the board has its own 3.3 V regulator |
| DAC GND | 18 | GND | UDA1334A GND |
| DAC MUTE | — | — | not connected: the firmware never mutes the DAC |
| Generator channel 3 | 20 | GP15 | the square-wave output, 3.3 V logic |
| DAC outputs | — | — | channel 1 = the UDA1334A's left output, channel 2 = its right output |

The DAC runs at 150 MHz / 24 / 2 / 64 = **48 828.125 Hz**, inside the 16 to
50 kHz range that the Adafruit board's `SCLK` pull-down selects. BCLK and WSEL
must stay on adjacent GPIOs. The LEDs are off from power-up and after
`ecureset`. Other pins are a build option, not a source edit
([Notes §2](PICO2_Test_Board_Notes.md#2-wiring) and
[§2.1](PICO2_Test_Board_Notes.md#21-frequency-generator-wiring-202)).

Mount the sensor away from the Pico: the RP2350 and its regulator warm the
board, and the sensor reports that.

## 3. Connecting

Plug the Pico 2 into USB. It enumerates as a USB CDC serial port: `COM14` on
the bench PC, `COMn` on another Windows PC, `/dev/ttyACMn` on Linux. Find the
port by its serial number with `python -m serial.tools.list_ports -v`. The
line rate is ignored by USB CDC; the tools open the port at 115200.

Check it with:

```
> python -m benchtools pico2 -r COM14 info
{
  "copyright": "(c) 2026 Dermot Murphy",
  "name": "PICO2 Test Board",
  "sha": "<7-character commit SHA>",
  "version": "V1.00.0000"
}
```

Any serial terminal also works (115200 8N1, LF line ending; a CR is ignored).
Type `help` for the command list.

## 4. Flashing and building

**Flashing a built image.** One command, with no button press:

```
python -m benchtools pico2 -r COM14 flash pico2_test_board.uf2
python -m benchtools pico2 -r COM14 flash build\pico2_test_board.uf2 --expect-version V1.00.0000
python -m benchtools pico2 -r "" flash pico2_test_board.uf2      # a blank board; the port is found afterwards
```

It checks the image (every UF2 block for an RP2350, and the firmware's name in
it), reboots the board into its bootloader (`bootsel`, or a 1200-baud reset if
the port does not answer, or the **RP2350** drive if one is already mounted),
copies the image, waits for the port to come back, and checks `rd name`,
`rd version` and `rd sha` against the image. The result is printed as JSON;
the exit status is 0 only if every check passed.

| Option | Meaning |
|---|---|
| `--expect-version VX.YY.ZZZZ` | the version the new image must report (default: the version stored in the image) |
| `--drive E:` | the RP2350 drive, if it is not found |
| `--any-image` | allow an image that is not this firmware |
| `--no-verify` | do not read `rd` afterwards |
| `--bootloader-timeout S` | seconds to wait for the drive (default 15) |
| `--port-timeout S` | seconds to wait for the port to come back (default 20) |

If the firmware has crashed, or the board does not appear on USB: hold
**BOOTSEL**, plug it in, and either copy the `.uf2` onto the RP2350 drive or run
`flash` as above.

**Building from source.** Arm GNU Toolchain 14.2.Rel1 and Pico SDK 2.1.1 with
its TinyUSB submodule:

```
export PICO_SDK_PATH=/path/to/pico-sdk
cmake -S firmware/pico2_test_board -B build/pico2_test_board
cmake --build build/pico2_test_board -j
```

This makes `build/pico2_test_board/pico2_test_board.uf2`, with the commit SHA
built in for `rd sha`. The [Notes §3](PICO2_Test_Board_Notes.md#3-building-and-flashing)
cover prerequisites, the host unit tests and the version-number rule. The
version is bumped with every change to the firmware or its host driver.

## 5. Serial command reference

One command per line, terminated by LF; CR is ignored, a blank line gets no
reply. Commands, options and values are matched exactly, **case included**. A
line longer than 63 characters is refused whole. There is exactly one reply
line per command, except `help` and `routine freq results` with no channel,
which send several. Reply forms:

| Reply | Meaning |
|---|---|
| `ACK <command> = <value>` | `rd`, `wr` and `routine` done; the value may contain spaces |
| `NAK <command> = Error` | `rd`, `wr` or `routine` refused: unknown option, value out of range, or a routine that cannot start. Nothing changed |
| `ok` or `ok key=value` | the other commands done |
| `err <code> <text>` | the command could not be run (table below) |
| `# ...` | an information line (`help` only) |

| Error | Text | When |
|---|---|---|
| `err 1` | unknown command | the command word is not one of those below (`ver`, `temp` and `reset` included) |
| `err 2` | wrong number of arguments | e.g. `rd` alone, `rd name 1`, `wr led-red`, `wr led-red 2 on` |
| `err 3` | line too long | more than 63 characters |
| `err 4` | the sensor did not acknowledge | `status`, `sreset`: no sensor at 0x44 |
| `err 5` | the sensor checksum did not match | `status`: a corrupted frame |
| `err 6` | I2C bus timeout | `status`, `sreset`: a line held low |

### 5.1 Identity, temperature and LEDs

| Command | Example reply | Notes |
|---|---|---|
| `rd name` | `ACK rd name = PICO2 Test Board` | |
| `rd copyright` | `ACK rd copyright = (c) 2026 Dermot Murphy` | |
| `rd version` | `ACK rd version = V1.00.0000` | |
| `rd sha` | `ACK rd sha = 1a2b3c4` | `unknown` for a build outside a git checkout |
| `rd temperature` | `ACK rd temperature = 22.85` | one new measurement each time, °C rounded half away from zero to two places (`-1.24`; never `-0.00`). `ACK rd temperature = Error` when the sensor could not be read |
| `rd led-red` (`led-yellow`, `led-green`) | `ACK rd led-red = off` | read from the pin's output latch |
| `wr led-red on` / `off` | `ACK wr led-red = on` | the state read back from the pin after the write |
| `wr led-blue on`, `wr led-red 1` | `NAK wr led-blue = Error` | unknown option, or a value other than `on`/`off`; nothing changes |
| `rd colour` | `NAK rd colour = Error` | any unknown `rd` option |
| `status` | `ok status=0x0010` | the SHT30 status register (bit 4, 0x0010, is "reset detected") |
| `sreset` | `ok` | soft-reset the sensor; the Pico keeps running |
| `ecureset` | `ok`, then the Pico reboots | the port goes away and comes back; every setting returns to its default and the LEDs go off |
| `bootsel` | `ok`, then the Pico reboots into its USB bootloader | an **RP2350** drive appears; copy a `.uf2` to it |
| `help` | nine lines: `# help - list the commands`, `# rd - ...`, `# wr - ...`, `# routine - ...`, `# status - ...`, `# sreset - ...`, `# ecureset - ...`, `# bootsel - ...`, then `ok` | |

Humidity is measured with each reading but not reported.

### 5.2 Frequency generator

The generator is controlled like a UDS ECU: `wr` stores a setting, `rd` reads
it back, and `routine` starts, stops and reports a channel. `<ch>` is `1`, `2`
or `3`; when it is left out the command means channel 1, and the reply always
names the channel. **A `wr` does not change what is being generated**: it takes
effect at the next `routine freq start`.

| Setting | Value | Channels | Default |
|---|---|---|---|
| `freq` | 10 to 12000 Hz, up to three decimal places; a `k` suffix multiplies by 1000 (`1.5k`) | 1, 2, 3 | 1000 |
| `wave` | `square`, `sine`, `triangle`, `sawtooth`, `sine2` | 1, 2 (channel 3: `square` only) | `square` |
| `duty` | 1 to 99 % (the square wave's high time) | 1, 2, 3 | 50 |
| `amp` | 0 to 100 % of the DAC's full scale | 1, 2 | 100 |
| `freq2` | `sine2`'s second sine, 10 to 12000 Hz, `k` suffix | 1, 2 | 2000 |
| `ratio` | `sine2`'s second sine's amplitude relative to the first, 0 to 1 | 1, 2 | 0.5 |
| `cycles` | periods of `freq` to generate, then stop; `0` runs until aborted | 1, 2, 3 | 0 |

Every channel starts with the defaults at power-up and after `ecureset`.
Values out of range are refused with `NAK`, never clamped. Numbers are replied
to two decimal places (`ACK wr ratio 1 = 0.50`), `cycles` as an integer and
`wave` as its name.

| Command | Example reply |
|---|---|
| `wr freq [<ch>] <hz>` | `wr freq 5k` → `ACK wr freq 1 = 5000.00` |
| `wr wave [<ch>] <wave>` | `wr wave 2 sine` → `ACK wr wave 2 = sine` |
| `wr duty [<ch>] <percent>` | `wr duty 3 25` → `ACK wr duty 3 = 25.00` |
| `wr amp [<ch>] <percent>` | `wr amp 50` → `ACK wr amp 1 = 50.00` |
| `wr freq2 [<ch>] <hz>` | `wr freq2 2 1k` → `ACK wr freq2 2 = 1000.00` |
| `wr ratio [<ch>] <0..1>` | `wr ratio 2 0.5` → `ACK wr ratio 2 = 0.50` |
| `wr cycles [<ch>] <count>` | `wr cycles 2000` → `ACK wr cycles 1 = 2000` |
| a value refused | `wr amp 150` → `NAK wr amp 1 = Error`; `wr wave 3 sine` → `NAK wr wave 3 = Error`; `wr amp 3 50` → `NAK wr amp 3 = Error` |
| `rd <setting> [<ch>]` | `rd freq 2` → `ACK rd freq 2 = 1000.00` (the stored setting) |
| `routine freq start [<ch>]` | `ACK routine freq start 1 = Running` |
| a start refused | `NAK routine freq start 1 = Error`: the channel is already running continuously; abort it first |
| `routine freq abort [<ch>]` | `ACK routine freq abort 1 = Aborted`; with no channel, every channel: `ACK routine freq abort = Aborted` |
| `routine freq results <ch>` | `ACK routine freq results 1 = Running, sine, 1000.00 Hz`, or `ACK routine freq results 3 = Not Started` |
| `routine freq results` | one such line for each channel, 1 to 3 |
| `routine all abort` | `ACK routine all abort = Aborted`: stops every channel |

The status in `routine freq results` is `Not Started` (never started since
power-up), `Running`, `Aborted` or `Complete` (a finite run that finished by
itself). The waveform and frequency it reports are those actually generated:
the frequency is the one the phase step or the PWM divider achieves, which can
differ slightly from the setting. Aborting a channel that never started leaves
it `Not Started`.

A channel running a finite number of cycles can be started again, which
restarts it; a channel running continuously cannot (`NAK`) until it is aborted.
A channel that is not running outputs mid-scale silence (channels 1 and 2).

**`sine2`.** Two sines summed: `freq` at amplitude `amp / (1 + ratio)` and
`freq2` at `amp × ratio / (1 + ratio)`, so the combined peak never exceeds
`amp`. `cycles` counts periods of `freq`, and `routine freq results` reports
`freq`.

**Band limit.** The square, triangle and sawtooth on channels 1 and 2 are
built with harmonics up to 0.45 × 48 828.125 Hz = 21.97 kHz only. Above about
2.5 kHz (square), 3 kHz (triangle) and 2 kHz (sawtooth) they are visibly
rounded, because too few harmonics fit. These limits are calculated, not
measured. Channel 3 is a true square wave across the range.

**Level.** 100 % is the DAC's full scale, about 900 mV rms typical by the
UDA1334A data sheet. This has **not** been measured on the board
([§10](#10-limits-and-known-gaps)).

## 6. The `benchtools pico2` command line

```
python -m benchtools pico2 [-r RESOURCE] [--timeout S] [--json PATH] [-v] <sub-command> ...
```

`-r` takes `COM14`, `/dev/ttyACM0`, `serial://COM14` or `sim://`. The default is
`sim://`, the simulated board, so **a command given no resource never touches
hardware**. Options come before the sub-command. Results are JSON; `--json PATH`
also writes them to a file. Exit status 0 on success, 1 on any error, printed
as `error: ...`. `pico2-test-board`, and the names before #330 (`thermo`,
`pico-sht30`, `sht30`), reach the same command.

| Sub-command | Does | Example and output (simulated board) |
|---|---|---|
| `info` | `rd name`, `copyright`, `version`, `sha` | `pico2 -r sim:// info` → `{"copyright": "(c) 2026 Dermot Murphy", "name": "PICO2 Test Board", "sha": "0c0ffee", "version": "V1.00.0000"}` |
| `rd <option> [channel]` | one `rd`; the option is checked before sending | `pico2 -r sim:// rd freq 2` → `{"channel": 2, "option": "freq", "value": "1000.00"}` |
| `wr <led> on\|off` | switch an LED; exit 1 if it does not read back | `pico2 -r sim:// wr led-red on` → `{"option": "led-red", "value": "on"}` |
| `wr <setting> [channel] value` | store a generator setting | `pico2 -r sim:// wr amp 2 50` → `{"channel": 2, "setting": "amp", "value": "50.00"}` |
| `routine freq start [channel]` | start a channel (default 1) | → `{"channel": 1, "status": "Running"}` |
| `routine freq abort [channel]` | stop a channel, or all | → `{"channel": null, "status": "Aborted"}` with no channel |
| `routine freq results [channel]` | report a channel, or all | → `{"channel": 1, "frequency_hz": null, "status": "Not Started", "wave": null}` |
| `routine all abort` | stop everything | → `{"status": "Aborted"}` |
| `temp [-n COUNT] [-i SECONDS]` | one reading, or a series | `pico2 -r sim:// temp` → `{"temperature_c": 22.5, "text": "22.50", "timestamp": ...}` |
| `status` | the sensor status register, decoded | → `{"raw": "0x0010", "reset_detected": true, ...}` |
| `sreset` | soft-reset the sensor | → `{"sensor_reset": true}` |
| `ecureset` | reboot the Pico | → `{"rebooted": true}` |
| `bootsel` | reboot into the bootloader | → `{"bootloader": true, "next": "copy the .uf2 to the RP2350 drive that appears"}` |
| `flash <uf2> [options]` | reflash and check ([§4](#4-flashing-and-building)) | `pico2 -r COM14 flash pico2_test_board.uf2` |

Each invocation opens the port, identifies the board, runs one sub-command and
closes the port. The real board keeps its settings, and keeps generating,
after the port closes: the firmware does not watch the port. The simulated
board is new for each invocation, so `routine freq results` there always shows
`Not Started`.

A wrong option is refused before anything is sent: `wr led-red 1`,
`wr led-blue on` and `rd humidity` exit with a usage error. A value the board
refuses is reported as `error: 'wr wave 3 sine' refused: NAK wr wave 3 = Error`.

## 7. The Python driver

```python
from benchtools.instruments.pico2_test_board import Pico2TestBoard

with Pico2TestBoard.connect("COM14") as board:      # "sim://" for the simulator
    ...
```

`connect(resource="sim://", timeout=2.0, baudrate=115200)` takes a bare port
name as a serial port. Connecting reads the identity and refuses a device whose
`rd name` is not `PICO2 Test Board` (`ProtocolError`).

| Method or property | Sends | Returns, or raises |
|---|---|---|
| `firmware_info(refresh=False)` | `rd name`, `copyright`, `version`, `sha` (cached) | `FirmwareInfo(name, copyright, version, sha)` |
| `name`, `version`, `sha` (properties) | from `firmware_info()` | text |
| `temperature()` | `rd temperature` | °C as a float; `NoReadingError` if the sensor could not be read |
| `read()` | `rd temperature` | `Reading(temperature, text, timestamp)`; logged as a reading |
| `status()` | `status` | `SensorStatus(raw)`; `flag("reset_detected")` etc. |
| `soft_reset_sensor()` | `sreset` | — |
| `led(colour)` | `rd led-<colour>` | `True` if lit |
| `set_led(colour, lit)` | `wr led-<colour> on\|off` | the state read back; `ProtocolError` if it is not the one written |
| `rd(option, channel=None)` | `rd <option> [<channel>]` | the value as text; `RdRefusedError` for `NAK` |
| `wr(setting, value, channel=None)` | `wr <setting> [<channel>] <value>` | the value stored, as text; `WrRefusedError` for `NAK`; `ValueError` for an LED given a channel |
| `start_freq(channel, freq, cycles=None, wave="square", **options)` | `wr wave`, `wr freq`, `wr cycles`, then each of `duty`, `amp`, `freq2`, `ratio` given, then `routine freq start` | — ; `CommandRefusedError` if a value or the start is refused |
| `freq_start(channel=1)` | `routine freq start <ch>` | — ; `CommandRefusedError` if running continuously |
| `abort_freq(channel=None)` | `routine freq abort [<ch>]` | — |
| `abort_all()` | `routine all abort` | — |
| `freq_status(channel=None)` | `routine freq results [<ch>]` | `FreqStatus(channel, status, wave, frequency)`, or a list of three |
| `execute(command)` | any `ok`/`err` command | the `key=value` fields; `SensorError` for `err` |
| `reset()` | `ecureset` | — (reconnect afterwards) |
| `enter_bootloader()` | `bootsel` | — |

Colours are `red`, `yellow` and `green`; another raises `ValueError` before
anything is sent. `RdRefusedError` and `WrRefusedError` are both
`CommandRefusedError`, so one `except` catches any refusal. `cycles=None` in
`start_freq` means continuous. The inherited SCPI methods (`clear_status`,
`event_status`, `operation_complete`, `self_test_passed`) send `*` commands that
this firmware does not know; do not use them.

```python
"""Light the green LED, log ten readings, and play a 1 kHz sine on channel 1."""
import time

from benchtools.instruments.pico2_test_board import NoReadingError, Pico2TestBoard

with Pico2TestBoard.connect("COM14") as board:
    print(board.name, board.version, board.sha)
    board.set_led("green", True)
    for _ in range(10):
        try:
            print("%.2f °C" % board.temperature())
        except NoReadingError:
            print("no reading")
        time.sleep(1.0)
    board.start_freq(1, 1000, wave="sine", amp=50)
    print(board.freq_status(1))      # FreqStatus(channel=1, status='Running', ...)
    time.sleep(5.0)
    board.abort_all()
    board.set_led("green", False)
```

The old class names `PicoSht30` and `SimulatedPicoSht30` are aliases of
`Pico2TestBoard` and `SimulatedPico2TestBoard`.

## 8. Test sequences

### 8.1 The bench file entry

The shipped benches carry the board as `pico2`:

```yaml
instruments:
  pico2:
    driver: pico2-test-board      # or pico2; pico-sht30 and thermometer still load
    resource: COM14               # sim:// in benches/simulated_bench.yaml
    timeout: 5.0
    event: TEMP                   # its name in the event log
```

A specification names the instruments it needs:

```yaml
instruments:
  pico2: pico2-test-board
```

### 8.2 Steps

Every public method and property of the driver is a step, `do: pico2.<name>`,
with its arguments under `with:` by name. A method returning `True`/`False`
measures as `1`/`0`; a result object is addressed with `measure:`
([Bench Runner Guide §5](../Bench_Runner_Guide.md#5-addressing-a-value-inside-a-result-measure)).

| Step | `with:` | Measure | Value |
|---|---|---|---|
| `pico2.name`, `pico2.version`, `pico2.sha` | — | *(omitted)* | text |
| `pico2.firmware_info` | `refresh` | `name`, `copyright`, `version`, `sha` | text |
| `pico2.temperature` | — | *(omitted)* | °C |
| `pico2.read` | — | `temperature`, `text` | °C; the firmware's text |
| `pico2.status` | — | `raw` | the status word |
| `pico2.soft_reset_sensor` | — | — | — |
| `pico2.set_led` | `colour`, `lit` | *(omitted)* | `1` lit, `0` out, read back |
| `pico2.led` | `colour` | *(omitted)* | `1` lit, `0` out |
| `pico2.wr` | `setting`, `value`, `channel` | *(omitted)* | the value stored, as text (`"50.00"`) |
| `pico2.rd` | `option`, `channel` | *(omitted)* | the value, as text |
| `pico2.start_freq` | `channel`, `freq`, `cycles`, `wave`, and any of `duty`, `amp`, `freq2`, `ratio` | — | — |
| `pico2.freq_start` | `channel` | — | — |
| `pico2.freq_status` | `channel` | `status`, `wave`, `frequency` | `Running` etc.; the waveform; Hz |
| `pico2.abort_freq` | `channel` (none: all) | — | — |
| `pico2.abort_all` | — | — | — |
| `pico2.execute` | `command` | a field name, e.g. `status` | text |

The LED argument is `lit`, not `on`: YAML reads a bare `on` key as `true`, so a
specification could not name it. Put `pico2.abort_all` and the LEDs off in
`teardown:`, so the board is left idle however the run ends. Do not use
`pico2.reset` or `pico2.enter_bootloader` in a sequence: the port goes away
and the connection with it.

### 8.3 The shipped sequence: `specs/pico2_test_board.yaml`

| Test case | Steps | Expectations |
|---|---|---|
| The board identifies itself | `pico2.name`, `pico2.version` | the name is `PICO2 Test Board`; the version has the form `V<n>.<nn>.<nnnn>` |
| Each LED lights and goes out | `pico2.set_led` on and off for each colour; `pico2.led` for green | each read-back `1` when lit and `0` when out |
| The temperature is a room temperature | `pico2.temperature` | 10 to 40 °C |
| A finite run on channel 1 completes by itself | `pico2.start_freq` (channel 1, 1000 Hz, 500 cycles, sine, amp 50); `sleep` 1 s; `pico2.freq_status` | `Complete`, at 1000 Hz |
| Every channel runs continuously until aborted | `pico2.start_freq` on channel 1 (1 kHz sine), 2 (`sine2`, 500 Hz + 1 kHz, ratio 0.5) and 3 (2 kHz square, duty 25); `freq_status`; `abort_all`; `freq_status` | channel 2 `Running` `sine2`, channel 3 `Running`, channel 1 `Aborted` after the abort |

Its teardown aborts everything and turns the three LEDs off. It checks what the
board reports over the serial link, not the analogue outputs.

On the simulated bench, with no hardware:

```
> python -m benchtools run specs/pico2_test_board.yaml --bench benches/simulated_bench.yaml
PICO2 Test Board check: PASS - 5 passed, 0 failed, 0 errored, 0 skipped in 1.00 s
```

On the bench PC, the board on COM14:

```
python -m benchtools run specs/pico2_test_board.yaml --bench benches/bench_pc.yaml --markdown pico2.md
```

`tests/instruments/pico2_test_board/test_spec.py` (SWE4-UT-PICOSPEC) runs it on
the simulated bench in CI. The run on the real bench is not recorded in this
manual.

## 9. Worked examples

Each is shown as serial commands, then as `benchtools pico2` and as test
steps where that differs. `-r COM14` stands for the board's port.

**LEDs.** Red on, check, off:

```
wr led-red on          ACK wr led-red = on
rd led-red             ACK rd led-red = on
wr led-red off         ACK wr led-red = off
```

```
python -m benchtools pico2 -r COM14 wr led-red on
```

```yaml
- do: pico2.set_led
  with: {colour: red, lit: true}
  expect: [{name: red_lit, equals: 1}]
```

**A temperature series.** Ten readings a second apart:

```
python -m benchtools pico2 -r COM14 temp --count 10 --interval 1 --json temps.json
```

In a sequence, one reading with limits: `do: pico2.temperature` with
`expect: [{name: room, minimum: 15, maximum: 30, unit: degC}]`.

**A 1 kHz sine on channel 1, half scale, continuous:**

```
wr wave 1 sine         ACK wr wave 1 = sine
wr freq 1 1k           ACK wr freq 1 = 1000.00
wr amp 1 50            ACK wr amp 1 = 50.00
wr cycles 1 0          ACK wr cycles 1 = 0
routine freq start 1   ACK routine freq start 1 = Running
```

```python
board.start_freq(1, 1000, wave="sine", amp=50)
```

**A two-tone `sine2` on channel 2:** 500 Hz plus 1 kHz at half its amplitude,
full scale combined, so 500 Hz at 2/3 and 1 kHz at 1/3 of full scale:

```
wr wave 2 sine2
wr freq 2 500
wr freq2 2 1k
wr ratio 2 0.5
wr amp 2 100
routine freq start 2   ACK routine freq start 2 = Running
```

```yaml
- do: pico2.start_freq
  with: {channel: 2, freq: 500, wave: sine2, freq2: 1000, ratio: 0.5, amp: 100}
```

**A finite burst:** 2000 cycles of 1 kHz on channel 1, which stops by itself
after 2 s:

```
wr cycles 1 2000
routine freq start 1               ACK routine freq start 1 = Running
routine freq results 1             ACK routine freq results 1 = Running, sine, 1000.00 Hz
(about 2 s later)
routine freq results 1             ACK routine freq results 1 = Complete, sine, 1000.00 Hz
```

```yaml
- do: pico2.start_freq
  with: {channel: 1, freq: 1000, cycles: 2000, wave: sine, amp: 50}
- do: sleep
  with: {seconds: 2.5}
- do: pico2.freq_status
  with: {channel: 1}
  expect: [{name: burst_done, measure: status, equals: Complete}]
```

**A square wave on channel 3:** 2 kHz at 25 % duty on GP15:

```
python -m benchtools pico2 -r COM14 wr wave 3 square
python -m benchtools pico2 -r COM14 wr freq 3 2k
python -m benchtools pico2 -r COM14 wr duty 3 25
python -m benchtools pico2 -r COM14 routine freq start 3
```

**Stopping everything:**

```
routine all abort      ACK routine all abort = Aborted
```

```
python -m benchtools pico2 -r COM14 routine all abort
```

To change a channel that is running continuously, abort it, write the new
settings, and start it again.

## 10. Limits and known gaps

Seen on the real board (Pico 2 on COM14, 2026-11-13, firmware `V1.00.0000`):

- A 45-check serial proof passed: each LED on and off with its read-back,
  `led-blue` refused; the temperature read 24.28 to 24.31 °C; every generator
  setting read back; values out of range refused; 2000 cycles at 1 kHz
  completed in 2.08 s.
- On a scope: a 1 kHz sine on channel 1 (left), a 2 kHz sine on channel 2
  (right), and `sine2` of 500 Hz and 1 kHz.

**Not yet confirmed on hardware** (PICO-OPEN-07 and PICO-OPEN-03 in the
[Notes §7](PICO2_Test_Board_Notes.md#7-bench-confirmation-items)):

- the output level: 100 % is about 900 mV rms only by the data sheet; the
  coupling and load the outputs drive;
- the square, triangle and sawtooth waveforms, and the band-limit corners
  quoted in §5.2;
- channel 3 on GP15, on a scope;
- frequency accuracy against a reference (the TTi 1604);
- exact cycle counts on channels 1 to 3;
- what the DAC outputs at power-up before the firmware starts (MUTE is not
  connected), and silence after `routine all abort`;
- the temperature against a calibrated reference (PICO-OPEN-03);
- the shipped sequence `specs/pico2_test_board.yaml` run against the real board.

Other limits: one command at a time (the next is read after the reply); a
setting takes effect only at the next start; humidity is not reported; the
simulator models the replies and timing of the generator, not its waveforms.

## 11. Troubleshooting

| Symptom | Likely cause | What to do |
|---|---|---|
| `could not connect to COM14` | wrong port, or another program has it open | `python -m serial.tools.list_ports -v`, find serial `AC5483CD0798FB0B`; close terminals |
| `device reports name ..., not 'PICO2 Test Board'` | another firmware, or the board's firmware from before #330 (`Pico 2 SHT30 Temperature Sensor`) | flash the current image ([§4](#4-flashing-and-building)) |
| `ACK rd temperature = Error`, `NoReadingError` | sensor absent, a CRC failure, or a bus timeout | send `status`: `err 4` wiring, power or address; `err 5` noise or long wires; `err 6` SDA/SCL swapped or held low |
| `NAK wr <setting> 1 = Error` | value out of range, more than three decimal places, or not allowed on that channel (`amp`, `freq2`, `ratio` and any wave but `square` on channel 3) | check §5.2 |
| `NAK routine freq start 1 = Error` | the channel is running continuously | `routine freq abort 1`, then start |
| A setting written but the output did not change | a `wr` takes effect at the next start | abort and start the channel |
| `err 1 unknown command` | a typo, upper case, or `ver`/`temp`/`reset` (removed by #131) | commands are lower case |
| `err 2 wrong number of arguments` | a channel given to an LED or an identity option; a missing value | `wr led-red on`, not `wr led-red 1 on` |
| No signal on the DAC outputs | DAC not powered (VIN on VBUS), DIN/BCLK/WSEL not on GP6/GP7/GP8, channel not started | check §2; `routine freq results` |
| A square, triangle or sawtooth looks rounded at a few kHz | the band limit at 21.97 kHz | use channel 3 for a sharp square wave |
| `flash` times out waiting for the drive | the board did not reboot into its bootloader | hold BOOTSEL and re-plug, then run `flash` again |

## 12. Earlier names

Until #330 (2026-11-13) the board was the **Pico 2 SHT30 Temperature Sensor**,
and its last firmware was `V1.02.0000`. #330 renamed it the PICO2 Test Board
and reset the version to `V1.00.0000`; protocol 2.2 is unchanged. The old
names are still accepted:

| What | Now | Before #330, still accepted |
|---|---|---|
| `rd name` | `PICO2 Test Board` | `Pico 2 SHT30 Temperature Sensor` (no longer accepted by the driver) |
| Command line | `benchtools pico2` (also `pico2-test-board`) | `benchtools thermo`, `pico-sht30`, `sht30` |
| Bench driver | `pico2-test-board`, `pico2` | `pico-sht30`, `thermometer` |
| Bench alias | `pico2` | `temp` (in older bench files) |
| Python package | `benchtools.instruments.pico2_test_board` | — (`benchtools.instruments.pico_sht30` is gone) |
| Python class | `Pico2TestBoard`, `SimulatedPico2TestBoard` | `PicoSht30`, `SimulatedPicoSht30` |
| `set_led` argument | `lit` | `on` |
| Firmware directory, image | `firmware/pico2_test_board`, `pico2_test_board.uf2` | `firmware/pico_sht30`, `pico_sht30.uf2` |
| Documents | `docs/pico2_test_board/` | `docs/pico_sht30/` |

The event-log name is still `TEMP`.

## 13. Revision History

| Version | Date | Author | Description of Change |
|---|---|---|---|
| 0.1 | 2026-11-13 | Claude | #330: first issue. |
