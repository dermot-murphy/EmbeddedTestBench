# Pico 2 + SHT30-D thermometer firmware

A Raspberry Pi Pico 2 reads a Sensirion SHT30-DIS (on a DollaTek SHT30-D module)
over I2C and answers over USB CDC. It also drives three indicator LEDs - red on
GP18, yellow on GP19 and green on GP20, each lit when its pin is high - which
are off from boot and switched by `wr` (#328):

```
rd name         -> ACK rd name = Pico 2 SHT30 Temperature Sensor
rd copyright    -> ACK rd copyright = (c) 2026 Dermot Murphy
rd version      -> ACK rd version = V1.02.0000
rd sha          -> ACK rd sha = <7-character commit SHA>
rd temperature  -> ACK rd temperature = 22.85      (or = Error when the sensor cannot be read)
rd led-red      -> ACK rd led-red = off            (also led-yellow, led-green; on or off)
rd <other>      -> NAK rd <other> = Error
wr led-red on   -> ACK wr led-red = on             (the state read back; also off,
                                                    led-yellow, led-green)
wr led-red 2 on -> err 2 wrong number of arguments (an LED takes no channel)
wr <other> <v>  -> NAK wr <other> = Error          (an option that is neither an LED
                                                    nor a generator setting, or a
                                                    value other than on/off;
                                                    nothing changes)
```

`rd` takes one or two arguments, `wr` two or three and `routine` two or three;
only a generator setting takes the extra one, a channel. A wrong number of
arguments answers `err 2`. `status`,
`sreset`, `ecureset` (reboot), `bootsel` and `help` answer `ok ...` or
`err <code> <text>`. `ver`, `temp` and `reset` were removed in protocol 2.0
(#131); `wr` and the LED options of `rd` were added in protocol 2.1 (#328);
`routine`, and `wr` and `rd` of the generator's settings, in protocol 2.2
(#202). `help` lists nine lines: `help`, `rd`, `wr`, `routine`, `status`,
`sreset`, `ecureset`, `bootsel`, then `ok`.

It also drives a UDA1334A I2S DAC (an Adafruit UDA1334A breakout) as a
frequency generator, with the same `wr` and `rd` and the `routine` command
(#202): `wr freq 5k`, `wr wave sine`, `routine freq start`, `rd duty`. See
`include/protocol.h`. On the bench the board's DIN is on GP6, BCLK on GP7,
WSEL on GP8, VIN on VBUS (5 V) and MUTE is not connected, so the firmware
never mutes the DAC; a board that wires MUTE builds with
`-DBOARD_DAC_MUTE_PIN=<pin>`. The DAC runs at 48 828.125 Hz (150 MHz / 24 /
2 / 64), inside the 16 to 50 kHz range the board's SCLK pull-down selects.
Channel 3 is a square wave on GP15. On 2026-11-13 a scope showed a 1 kHz sine
on channel 1 and a 2 kHz sine on channel 2; the rest of the generator is not
yet checked on hardware (PICO-OPEN-07).

| Path | Contents |
|---|---|
| `include/protocol.h` | The host link: commands and error codes (the one definition) |
| `include/firmware_version.h` | Name, copyright and version. The version is `V<major>.<minor, 2 digits>.<patch, 4 digits>`, semantic, and bumped with every change to the firmware or its driver |
| `include/board_config.h` | Pins (I2C, the three LEDs and the generator), bus rate and sensor address |
| `include/hal.h` | The hardware seam |
| `src/` | `main.c`, `cmd_parser.c`, `cmd_fgen.c`, `fgen.c`, `sht30.c`, `text.c`, `hal_pico.c`, `firmware_version.c` |
| `test/` | Host unit tests (Unity, CTest) against a fake HAL |

Build: `PICO_SDK_PATH=... cmake -S . -B build && cmake --build build`, which
produces `build/pico_sht30.uf2`, with the short SHA of the commit it was built
from injected for `rd sha` (`unknown` outside a git checkout). To flash it, run
`benchtools thermo -r <port> flash build/pico_sht30.uf2`: it reboots the Pico
into its bootloader with no button press (or uses the RP2350 drive if one is
already mounted, as on a blank board), copies the image, and checks afterwards
that `rd name`, `rd version` and `rd sha` match the name, version and commit
SHA stored in the image. If the firmware has crashed or the Pico does not
appear on USB, hold BOOTSEL while plugging it in and copy the `.uf2` onto the
RP2350 drive.

For wiring, building, flashing, the MISRA position and the bench confirmation
items, see `docs/pico_sht30/Pico_SHT30_Notes.md`. Requirements: ETB-SWE1-001 §15.
