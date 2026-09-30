# Pico 2 + SHT30-D Reference Documents

Official sources for the schematics, user guides and datasheets this element is
built from. `fetch_datasheets.sh` downloads them into `datasheets/`.

**Status:** only the Pico 2 pinout is in the repository so far. The build
environment's network policy refused `datasheets.raspberrypi.com` and
`sensirion.com` (HTTP 403 at the proxy). The pinout came from Raspberry Pi's own
documentation repository on GitHub, which was reachable. Run the script on a
machine with normal internet access and commit the result (PICO-OPEN-04).

| # | Document | Publisher | Covers | URL | In repo |
|---|---|---|---|---|---|
| 1 | Raspberry Pi Pico 2 Datasheet | Raspberry Pi Ltd | Board: pinout, power, electrical, **schematic** (appendix), mechanical | https://datasheets.raspberrypi.com/pico/pico-2-datasheet.pdf | fetch |
| 2 | Raspberry Pi Pico 2 pinout | Raspberry Pi Ltd | Pin functions, GPIO numbering | https://datasheets.raspberrypi.com/pico/Pico-2-Pinout.pdf | SVG: `datasheets/pico-2-r4-pinout.svg` (CC BY-SA 4.0) |
| 3 | Raspberry Pi Pico 2 design files | Raspberry Pi Ltd | **Schematic** and PCB (KiCad), BOM | https://datasheets.raspberrypi.com/pico/RPi-Pico-2-PUBLIC-20240708.zip | fetch |
| 4 | RP2350 Datasheet | Raspberry Pi Ltd | Microcontroller: I2C controller (§12.2), USB, watchdog, bootrom | https://datasheets.raspberrypi.com/rp2350/rp2350-datasheet.pdf | fetch |
| 5 | Getting started with Raspberry Pi Pico-series | Raspberry Pi Ltd | **User guide**: toolchain install, building, UF2 download, BOOTSEL | https://datasheets.raspberrypi.com/pico/getting-started-with-pico.pdf | fetch |
| 6 | Raspberry Pi Pico-series C/C++ SDK | Raspberry Pi Ltd | SDK reference: `hardware_i2c`, `pico_stdio_usb`, `pico_bootrom`, `pico_unique_id` | https://datasheets.raspberrypi.com/pico/raspberry-pi-pico-c-sdk.pdf | fetch |
| 7 | Datasheet SHT3x-DIS | Sensirion AG | **Sensor datasheet**: commands, timing, CRC, conversion, status register, electrical | https://sensirion.com/media/documents/213E6A3B/63A5A569/Datasheet_SHT3x_DIS.pdf | fetch |
| 8 | DollaTek SHT30-D module | DollaTek | No datasheet or schematic is published. The module is the common "GY-SHT30-D" breakout: SHT30-DIS, 100 nF decoupling, 10 kΩ pull-ups on SDA and SCL, ADDR and ALERT on header pins. The seller's listing is the only DollaTek document. | — | n/a |

Cross-checks used during development, both reachable from the build environment:

* Sensirion's open-source C driver, BSD-3-Clause:
  https://github.com/Sensirion/embedded-i2c-sht3x. It confirms the command codes,
  CRC parameters and conversion.
* Pico SDK 2.1.1 source: https://github.com/raspberrypi/pico-sdk. The firmware
  was built against it (BENCHTOOLS-SWE4-002 §10A).

Licensing: Raspberry Pi's documentation is CC BY-SA 4.0. The PDFs are freely
downloadable from the publishers and are stored here unmodified, as reference
copies. Sensirion's datasheet is © Sensirion AG, free to download; keep it
unmodified.
