# Pico 2 + SHT30-D thermometer firmware

A Raspberry Pi Pico 2 reads a Sensirion SHT30-DIS (on a DollaTek SHT30-D module)
over I2C and answers over USB CDC:

```
rd name         -> ACK rd name = Pico 2 SHT30 Temperature Sensor
rd copyright    -> ACK rd copyright = (c) 2026 Dermot Murphy
rd version      -> ACK rd version = V1.00.0000
rd sha          -> ACK rd sha = <7-character commit SHA>
rd temperature  -> ACK rd temperature = 22.85      (or = Error when the sensor cannot be read)
rd <other>      -> NAK rd <other> = Error
```

`status`, `sreset`, `ecureset` (reboot), `bootsel` and `help` answer `ok ...` or
`err <code> <text>`. `ver`, `temp` and `reset` were removed in protocol 2.0
(#131).

| Path | Contents |
|---|---|
| `include/protocol.h` | The host link: commands and error codes (the one definition) |
| `include/firmware_version.h` | Name, copyright and version. The version is `V<major>.<minor, 2 digits>.<patch, 4 digits>`, semantic, and bumped with every change to the firmware or its driver |
| `include/board_config.h` | Pins, bus rate and sensor address |
| `include/hal.h` | The hardware seam |
| `src/` | `main.c`, `cmd_parser.c`, `sht30.c`, `text.c`, `hal_pico.c`, `firmware_version.c` |
| `test/` | Host unit tests (Unity, CTest) against a fake HAL |

Build: `PICO_SDK_PATH=... cmake -S . -B build && cmake --build build`, which
produces `build/pico_sht30.uf2`, with the short SHA of the commit it was built
from injected for `rd sha` (`unknown` outside a git checkout). Hold BOOTSEL, plug the Pico in, and copy the
`.uf2` onto the RP2350 drive.

For wiring, building, flashing, the MISRA position and the bench confirmation
items, see `docs/pico_sht30/Pico_SHT30_Notes.md`. Requirements: TB-SWE1-001 §15.
