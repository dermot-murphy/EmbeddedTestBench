# #84 on hardware: the ETB S2-LP kit firmware, receiving

Run on 2026-11-14 on the bench PC:

- **Kit:** the S2-LP kit on COM4, a NUCLEO-L053R8 with the STEVAL-FKI433V2 (ST-LINK 066CFF515055657867182645).
- **Firmware:** `firmware/s2lp_kit` on branch `feature/84-s2lp-kit-firmware`, built with STM32CubeIDE 2.1.1's arm-none-eabi-gcc 14.3.
- **Host:** CPython 3.14.7 on Windows 10.

Every run only listened. Nothing was transmitted, and no sensor was commanded.

## 1. Before flashing

**Backup of ST's firmware.** The kit's flash, 65 536 bytes from 0x08000000, was read twice over SWD, and both reads gave SHA-256 `c6e16813…f8e6b0`. The strings in it are ST's S2-LP CLI commands. It is kept outside this repository, at `C:\Users\dermot.murphy\Documents\bench_backups\s2lp_kit\`, because ST's licence (SLA0072) does not allow publishing it.

**The kit's register setup under ST's firmware.** Taken with `benchtools s2lp ... --setup plugin:kepler/s2lp_kepler_433_rx.regs registers`:

- `st_registers_dump.json` is the whole dump.
- `st_registers_writable.json` holds its 94 writable registers.

These are replayed onto the new firmware, so the two firmwares receive with the same radio setup. That includes the ten registers ST's firmware sets on the way out of shutdown.

## 2. The firmware on the kit

| Step | Result |
|---|---|
| Flash `s2lp_kit.bin` (`STM32_Programmer_CLI -w ... -v -rst`) | "Download verified successfully" |
| `id` | `ok etb-s2lp-kit V1.00.0000 proto=1 silicon=c1` |
| `rd f0 2`: DEVICE_INFO1/0 | `03c1` |
| `cmd 62` (READY), then `rd 8e 1` (MC_STATE0) | `ok 5201`, `01`: READY, crystal on |
| An unknown command | `err unknown command` |

## 3. Receiving

`kit_rx.py` runs the receive:

1. Power-cycles the radio (`sdn 1`, `sdn 0`).
2. Writes the 94 registers and reads each back.
3. Starts reception with RSSI_LEVEL, LINK_QUALIF2 (PQI), LINK_QUALIF1 (SQI) and AFC_CORR read after each frame.
4. Decodes each frame with the Kepler plugin.

`analyse.py` groups the copies of each transmission by sender, frame type and packet number, and checks that each repeat number arrived.

| | Run 1 (`rx_run1/`) | Run 2 (`rx_run2/`) |
|---|---|---|
| Length | 600 s | 900 s |
| QI | as replayed: PQI_TH 0 | PQI_TH 1 |
| Registers written, read back different | 94, 0 | 94, 0 |
| Frames; decoded | 86; 86 | 131; 131 |
| Rejections | 0 | 0 |
| Board queue overflows; gaps in the sequence numbers | 0; 0 | 0; 0 |
| Transmissions with a repeat count; all copies received | 51; 51 | 77; 77 |
| Copy spacing on air | 41.0-239.7 ms | 41.0-240.1 ms |
| PQI | 0 (PQI_TH 0, S2LP-OPEN-07) | 24-66 |
| SQI | 32-96 | 32-96 |
| Longest deaf time, interrupt to re-armed (`deaf_max_us`) | not yet measured | **393 µs** |

The deaf-time figure was added to the firmware after run 1, and the kit was flashed again before run 2. That build's `s2lp_kit.bin` has SHA-256 `7062550e…ae64f6`.

## 4. Compared with ST's firmware, the same day

ST's firmware received for 20 minutes in batch mode (`../335_340_rx/`):

- 173 frames; 101 transmissions with a repeat count; 2 missing a copy, both from 5BD456;
- copy spacing 31.1-239.2 ms;
- no PQI or SQI, because batch mode cannot read them.

With ST's firmware, the polled mode reads them, but it is deaf for 26-27 ms after each frame (#293).

## 5. Afterwards

The kit was put back on ST's firmware: the backup was written and verified, and the whole flash read back with the backup's SHA-256. `benchtools s2lp -r COM4 --board STEVAL-FKI433V2 info` then answered as before.

## What this does not show

- **The 20 ms repeat case.** The closest copies on air were 41 ms apart, and the sensors set the spacing. The firmware's own figure, 393 µs at most from a frame's interrupt to the radio armed again, says a 20 ms repeat would be caught. It was not seen.
- **Rejections.** None occurred. The CRC, filter and FIFO-error path is checked only by the unit tests.
- **The host driver.** These runs used `kit_rx.py`, not a `benchtools` driver.
