# Pico 2 + SHT30-D thermometer firmware

A Raspberry Pi Pico 2 reads a Sensirion SHT30-DIS (on a DollaTek SHT30-D module)
over I2C and answers over USB CDC:

```
ver   -> ok title=Pico2-SHT30-Thermometer fw=1.0.0 built=... proto=1.0 board=pico2 serial=... sensor=SHT30-DIS addr=0x44 uptime_s=...
temp  -> ok t=22.848 rh=44.912 raw_t=0x6340 raw_rh=0x72F9
```

| Path | Contents |
|---|---|
| `include/protocol.h` | The host link: commands and error codes (the one definition) |
| `include/firmware_version.h` | Title and version: edit the version here when behaviour changes |
| `include/board_config.h` | Pins, bus rate and sensor address |
| `include/hal.h` | The hardware seam |
| `src/` | `main.c`, `cmd_parser.c`, `sht30.c`, `text.c`, `hal_pico.c`, `firmware_version.c` |
| `test/` | Host unit tests (Unity, CTest) against a fake HAL |

Build: `PICO_SDK_PATH=... cmake -S . -B build && cmake --build build`, which
produces `build/pico_sht30.uf2`. To flash it, run
`benchtools thermo -r <port> flash build/pico_sht30.uf2`: it reboots the Pico
into its bootloader with no button press (or uses the RP2350 drive if one is
already mounted, as on a blank board), copies the image, and checks `ver`
afterwards. If the firmware has crashed or the Pico does not appear on USB,
hold BOOTSEL while plugging it in and copy the `.uf2` onto the RP2350 drive.

For wiring, building, flashing, the MISRA position and the bench confirmation
items, see `docs/pico_sht30/Pico_SHT30_Notes.md`. Requirements: TB-SWE1-001 §15.
