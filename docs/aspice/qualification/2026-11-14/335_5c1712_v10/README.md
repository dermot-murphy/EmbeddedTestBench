# V10 frames received on the bench: 5C1712 on V10.00.0000

## Setup

- **Date and place:** 2026-11-14, the bench PC.
- **Software:** `benchtools` on `fix/335-v1001-twf`.
- **BLE:** the dongle on COM10 (`ble_session.log`).
- **Receiver:** the S2-LP kit on COM4, on ST's firmware, set up with `s2lp_kepler_433_rx.regs` and decoding with the Kepler plugin.

The commands and their replies, with times, are in `before.txt` and `writes.txt`.

## The sensor

5C1712 is the J-Link test unit. Another session flashed it with V10.00.0000 for this run, at the owner's request.

**Before any change it read:**

- name `KAPPA_5C1712_V10.00.0000P`, `RD VERSION` V10.00.0000;
- `MODE` NORMAL, `DETECT-METHOD` ACCWAVE, `PHASE` DETECT;
- `TWFA-ENABLE` and `TWFB-ENABLE` ENABLED.

`RD ALIVE-PERIOD` does not exist in V10.00.

**The change.** `WR DETECT-METHOD ALWAYS`, acknowledged and read back, then a 1800 s receive.

## Result

1049 frames: 268 rejected by the radio, and 183 that would not decode.

| Sender | Firmware (RF_CAP) | Frames |
|---|---|---|
| 5C1712 | V10.00.0000 (4) | 104 TWF of 96 bytes; 3 ALIVE; 12 CONFIG of 20 bytes |
| 5C1705 | V10.01.2000-323 (5) | 118 ALIVE; 153 VERSION; 36 CMD; 111 CONFIG of 20 bytes |
| 5C168B | V10.01.2000-323 (5) | 60 ALIVE; 71 VERSION; 35 CMD; 60 CONFIG of 20 bytes |
| 5C314E, 5BD456 | V10.00 (4), (2) | 9 ALIVE each |

5C1805 sent nothing in this capture, but it advertised over BLE afterwards. 5C1705 and 5C168B sent ALIVE, VERSION and CONFIG here, for the first time that day, after their settings were put back in the previous run (`../335_twf_detect_always/`).

- **The V10.00 TWF (#313).** These are the first V10.00 TWF frames received. All 104 decode with #313's 96-byte type version 0 layout, which was written from source:
  - axis X, packets 0 to 34 of 256, ODR 25 600 Hz;
  - time taken 629 436 µs, against 640 ms for 16 384 samples at that rate;
  - group ID 1, 21.1 °C, 2800 mV;
  - samples in distance order.
- **The 99-byte V10.01 TWF (#335).** Not seen: 5C1712 runs V10.00, and the V10.01 sensors sent no TWF.
- **CONFIG, 20 bytes.** All 183 refused frames were CONFIG frames, from both V10.00 and V10.01-dev: "a CONFIG frame is 21 bytes; this payload is 20". V10's CONFIG has no Permute Control byte. #346 now decodes it (`_config_v10`), and three of these frames are its unit tests.
- **The 268 rejections** are all radio error 2, a CRC error, with no payload. This many senders transmit at once that the copies collide. None were seen in the earlier captures, which had fewer senders.

## Afterwards

5C1712 was put back on ACCWAVE with `WR DETECT-METHOD ACCWAVE`, read back. It still runs V10.00.0000: putting V11 back is for the session that flashed it.
