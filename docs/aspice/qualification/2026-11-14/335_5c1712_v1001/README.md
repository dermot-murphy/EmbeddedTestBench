# #335 confirmed on the bench: 5C1712 on V10.01.2000

The run was on 2026-11-14, on the bench PC.

- **Software:** `benchtools` on `fix/335-v1001-twf`.
- **BLE:** the dongle on COM10 (`ble_session.log`).
- **Receiver:** the S2-LP kit on COM4, on ST's firmware, set up with `s2lp_kepler_433_rx.regs` and decoding with the Kepler plugin.

Every command and its reply, with times, is in `commands.txt`.

## The sensor

5C1712 is the J-Link test unit. Another session flashed it with the V10.01.2000 release, at the owner's request. It advertises as `KAPPA_5C1712_V10.01.2000P`.

**Before any change it read:**

- `RD VERSION` V10.01.2000;
- `MODE` NORMAL, `DETECT-METHOD` ACCWAVE, `PHASE` DETECT;
- `TWFA-ENABLE` and `TWFB-ENABLE` ENABLED;
- `RD SYNC-ENABLE` NACK. The release has no sync feature, unlike the V10.01.2000-323 build on the other V10.01 sensors (`../335_twf_detect_always/`).

**The change.** `WR DETECT-METHOD ALWAYS`, acknowledged and read back, then a 1800 s receive.

## Result

1001 frames. 309 were rejected by the radio, all with error 2 (CRC): copies colliding while this many sensors transmit. **0 would not decode.**

**5C1712 sent 99 TWF frames, all 99 bytes**, with RF_CAP 5 and type version 1. Every one decoded with #335's layout (`_twf_v1001`) and **no warning**:

| Field | Value |
|---|---|
| Axis, packets | X, packets 0 to 32 of 256, each with its 3 copies |
| ODR | 25 600 Hz |
| Time taken, 32 bits at 92-95 | 629 879 µs in every frame (16 384 samples at 25 600 Hz is 640 ms) |
| Group ID, at 96 | 1 |
| Sync attribute, at 97-98 | 54403 in every frame of the capture |
| Temperature, battery | 20.7 °C, 2840 mV |
| Order | distance (implied), PARAM bits 4:2 reserved |

5C1712's 6 CONFIG frames of 20 bytes, and the 143 from 5C1705 and 5C168B, decoded with `_config_v10`.

So step 4 of #335 is done: the layout taken from the V10.01.2000 source matches a frame received from a sensor running it. One of these frames is now a unit test (`V1001_TWF` in `tests/instruments/s2lp/test_kepler.py`).

## Afterwards

5C1712 was put back on ACCWAVE with `WR DETECT-METHOD ACCWAVE`, read back. It still runs V10.01.2000. Putting V11 back is for the session that flashed it.
