# ETB S2-LP kit firmware

Firmware `V1.00.0001`, line protocol 1 (#84; patch for #379, MISRA conformance). It runs on the S2-LP kit's
NUCLEO-L053R8, with the S2-LP board on its Arduino headers, in place of ST's CLI
firmware. It receives frames on the radio's interrupt and queues them on the board.

**Why it exists:** ST's CLI firmware arms the radio for one packet at a time
from the host. So a stream that reads PQI and SQI after each frame is deaf for
the whole round trip, measured at 26-27 ms. The Kepler sensor spaces its repeats
from 20 ms. This firmware re-arms inside the interrupt, before anything goes to
the host. It reads the registers the host asked for, timestamps the frame in
microseconds, and numbers each record, so a lost one shows as a gap.

**No ST source is used.** ST's CLI firmware and S2-LP driver are under SLA0072,
which does not allow publishing them (see #84). This firmware has its own:

- startup and vector table (`src/startup.c`);
- linker script (`stm32l053r8.ld`);
- STM32L053 register definitions (`src/l053.h`);
- S2-LP SPI access (`src/s2lp.c`), written from the radio's SPI protocol.

The pin facts are the board's.

## Commands

One per line, `\n` or `\r` ended; each is answered by one line, `ok ...` or
`err <reason>`.

```
id                      ok etb-s2lp-kit V1.00.0000 proto=1 silicon=c1
rd <addr> <count>       ok <hex>              count 1 .. 128, decimal
wr <addr> <hex>         ok                    1 .. 128 bytes
cmd <code>              ok <MC_STATE1><MC_STATE0>, after a command strobe
sdn <0|1>               ok                    1 holds the radio in shutdown
rx start [<addr>,...]   ok                    up to 8 registers read after each frame
rx stop                 (the records still queued, then)
                        ok frames=<n> rejects=<n> overflows=<n> deaf_max_us=<n>
stat                    ok running=<0|1> frames=<n> rejects=<n> overflows=<n>
                        deaf_max_us=<n> queued=<n> uart_overruns=<n>
```

Addresses, codes and data are hexadecimal. While receiving, `rd`, `wr`, `cmd`
and `sdn` answer `err receiving`. A line longer than 300 characters is not run:
it answers `err line too long`.

- `deaf_max_us` is the longest time from a reception's interrupt to the radio
  armed again.
- `uart_overruns` counts bytes from the host that were lost.

USART2 has no FIFO, so its interrupt has priority over the radio's and the
timer's. A host may send `stat` while frames arrive.

While receiving, records arrive unasked:

```
f <seq> <time_us> <length> <registers hex or -> <payload hex>
r <seq> <time_us> <irq status hex>
```

- `seq` counts every record, queued or dropped, from 0 at `rx start`.
- `time_us` is the board's microsecond timer when the interrupt was taken,
  modulo 2^32.
- `r` is a reception the radio discarded: CRC, a filter, or a FIFO error.

`rx start` routes nIRQ to S2-LP GPIO3 (mode 2) and sets the interrupt mask to
data ready, data discarded and FIFO error. Everything else is the host's setup:
frequency, modulation, packet handler and filters.

## Wiring (NUCLEO-L053R8 and the S2-LP DK board)

| Signal | Pin |
|---|---|
| SPI1 SCK, MISO, MOSI (AF0, mode 0, 8 MHz) | PB3, PA6, PA7 |
| S2-LP CS | PA1 |
| Board EEPROM CS (held high) | PB4 |
| S2-LP SDN (high = shutdown) | PA8 |
| S2-LP GPIO3 = nIRQ, EXTI line 0, falling | PC0 |
| TCXO enable (driven high) | PC7 |
| USART2 TX, RX to the ST-LINK VCP, 115200 8N1 | PA2, PA3 (AF4) |
| Green LED: on while receiving | PA5 |

The core runs at 32 MHz from HSI16 through the PLL (x4, /2).

## Host driver

`benchtools`' S2-LP driver drives this firmware as well as ST's. Connecting
sends `id`; on this firmware the driver reads and writes registers, sends
strobes, takes the radio through shutdown, and receives with `stream`, as on
ST's firmware:

```python
from benchtools.core import plugins
from benchtools.instruments.s2lp import S2lpDevkit

plugins.load_plugin("plugins/kepler")
with S2lpDevkit.connect("COM4", log_path="kit.log") as radio:
    assert radio.kit_firmware
    radio.apply_configuration("plugins/kepler/configs/s2lp_kepler_433_rx.regs")
    for packet in radio.stream(decoder=plugins.decoder("kepler"), timeout=60):
        print(packet.extra["seq"], packet.extra.get("pqi"), packet.decoded)
    print(radio.kit_counters)
```

`firmware="st"` or `"kit"` names the firmware instead of asking. ST's radio
commands, `transmit`, `receive` and `capture` need ST's firmware and are
refused here with a message saying so.

## Build

```bash
make -C firmware/s2lp_kit
```

This needs `arm-none-eabi-gcc` on `PATH`, or `ARM_PREFIX=<dir>/arm-none-eabi-`.
STM32CubeIDE's copy works on Windows, with `mingw32-make`. The build writes
`build/s2lp_kit.elf`, `.hex`, `.bin` and `.map`.

## Unit tests

```bash
cmake -S firmware/s2lp_kit/test -B build/s2lp-kit-tests
cmake --build build/s2lp-kit-tests && ctest --test-dir build/s2lp-kit-tests
```

The tests use Unity, fetched from GitHub unless `-DUNITY_DIR=<checkout>` is
given. `test/support/fake_hal.c` stands in for the board and models the
S2-LP's SPI protocol: a register file, a FIFO, and an interrupt status that
clears on read.

## Flash and roll back

```bash
STM32_Programmer_CLI -c port=SWD mode=UR -w build/s2lp_kit.bin 0x08000000 -v -rst
```

To go back to ST's CLI firmware, write the backup taken from the kit before the
first flash. Keep the backup outside this repository, because of ST's licence.
Write it the same way, at 0x08000000.
