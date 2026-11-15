# #84: the benchtools driver on the S2-LP kit firmware, 2026-11-14

Bench check of the host driver for the ETB S2-LP kit firmware
(S2LP-FR-098 .. S2LP-FR-100, S2LP-DD-KITHOST). The firmware itself was checked
earlier the same day: `../84_kit_firmware/`.

Kit: NUCLEO-L053R8 with the STEVAL-FKI433V2 S2-LP board, on COM4 through the
ST-LINK. Receive only: nothing was transmitted, and no sensor was commanded.

## 1. ST's firmware still connects (`st_probe/`)

Before flashing, with ST's CLI firmware on the kit, the driver connected with
its default `firmware="auto"`:

```
> id
< id
< no such command
> SdkEvalRfboardIdentification 0
...
```

ST's interpreter answered `id` with `no such command` about 3 ms after it was sent. The driver
kept ST's session and identified the board as before:
`STMicroelectronics,STEVAL-FKI433V2,S2-LP 0xC1,library 1.3.5,board 80,XTAL 49999561 Hz`.
The traceback in `stdout.txt` is the check script calling `frequency_hz`, a
property, as a method. It came after the connection and is not a driver fault.

## 2. Flash

`firmware/s2lp_kit` was built on this branch. `build/s2lp_kit.bin` has SHA-256
`267fed19…aec5c6`, the same image as `../84_kit_firmware/r1_check`. It was
written with `STM32_Programmer_CLI -c port=SWD -w ... 0x08000000 -v -rst`,
which reported "Download verified successfully". The backup of ST's image was
checked first: SHA-256 `c6e16813…f8e6b0`. It is kept outside this repository
(SLA0072).

## 3. Receiving through the driver (`run1/`)

`kit_stream.py` uses `S2lpDevkit` only, with `../84_kit_firmware/st_registers_writable.json`:

| Step | Result (`run1/summary.json`) |
|---|---|
| `S2lpDevkit.connect("COM4")`, firmware `auto` | `kit_firmware` true; identity `STMicroelectronics,S2-LP DK,S2-LP 0xC1,etb-s2lp-kit V1.00.0000,protocol 1` |
| `power_cycle()`, 94 registers written with `write_register` and read back | 0 differing |
| `frequency_hz()`, an ST-only call | refused: "S2LPRadioGetFrequencyBase needs ST's CLI firmware; this kit runs etb-s2lp-kit V1.00.0000, ..." |
| `stream(decoder=<Kepler>, timeout=300)` | 115 records, seq 0 to 114 with no gap; 24 frames, all decoded (21 TWF from 5C1712, 3 ALIVE from 5BD456), every one with its 4 registers; PQI 20 to 63; 91 rejections; counters `frames=24 rejects=91 overflows=0 deaf_max_us=390` |
| `stream(count=3)` | ended after 3 receptions (3 rejections); the board stopped; nothing left over |
| QI after both streams | 0x01: the PQI check was switched on for each stream (`wr 37 03`) and put back |

`run1/session.log` holds every line in both directions. `run1/packets.jsonl`
holds every packet as the driver recorded it, with sequence number, board time,
registers and decode.

A first attempt at this run passed the decoder's name, `"kepler"`, to `stream`,
which takes a callable, as on ST's firmware (S2LP-FR-047). Every frame then
carried a decode error, "'str' object is not callable". The run was discarded
and repeated with the plugin's decoder. The stream itself behaved the same.

## 4. The rejections

91 of 115 receptions were rejected, with interrupt status `09607212` (or
`09607612`): CRC error and data discarded. The earlier firmware runs that day
had none (`../84_kit_firmware/rx_run2`: 131 frames, 0 rejections). The driver
does not cause them:

- **Same rate with the old script.** `ab_kit_rx/` is `../84_kit_firmware/kit_rx.py`
  for 180 s straight after `run1`, with no `benchtools` driver involved: 15
  frames, 55 rejections.
- **Away from the frames received.** 92 of the 94 rejections (both streams)
  were more than 0.5 s from any frame accepted. So they are not failed copies
  of the frames received; another transmitter, or frames with a different
  setup, is on the air.
- **ST's firmware saw them too.** The #335 streams earlier that day, on ST's
  firmware, recorded 268 of 1049 (`335_5c1712_v10`) and 309 of 1001
  (`335_5c1712_v1001`) receptions with an error.

Their source is not established.

## 5. Afterwards

The backup of ST's image was written and verified. The whole flash was read
back, with SHA-256 `c6e16813…f8e6b0`, the backup's. Then
`benchtools s2lp -r COM4 --board STEVAL-FKI433V2 info` was run, with the probe
in place, and answered as before (`after_restore_info.json`).

## What this does not show

- **A lost record on the bench.** No sequence gap and no overflow occurred.
  `lost_before` is checked only by `SWE4-UT-S2LPKITHOST`
  (`test_a_lost_record_is_counted_on_the_next`).
- **A board left receiving at connection.** It was not tried on the kit. That
  case is covered only by `test_a_board_left_receiving_is_stopped`.
- **`dut_frame` and the other measures.** They run through `stream` and were
  not run on the kit.
