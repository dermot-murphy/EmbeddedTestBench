# #335 on the bench: trying to make the V10.01 sensors send TWF

The run was on 2026-11-14, on the bench PC, at the owner's instruction: "send BLE commands to some sensors to detect always. This will cause them to start sending TWFs."

- **Software:** `benchtools` on `fix/335-v1001-twf`.
- **BLE:** the dongle on COM10 (`ble_session.log` has the whole session).
- **Receiver:** the S2-LP kit on COM4, on ST's firmware, set up with `s2lp_kepler_433_rx.regs` and decoding with the Kepler plugin.

The command replies, with times, are in `before.txt` and `writes.txt`.

## The sensors

5C1805, 5C1705 and 5C168B advertise as `KAPPA_..._V10.01.20`. `RD VERSION` answers `V10.01.2000-323-g3ac582ae7` on all three: a development build from 2026-08-12, 323 commits after the V10.01.2000 tag, not the release.

At that commit (`software/source/config/common/api_radio_transport_cfg.h`):

- the TWF frame is the layout #335 decodes: 99 bytes, RF_CAP 5 and TWF type capability 1, time taken at 92, group ID at 96 and sync attribute at 97;
- the build also sends a CMD frame, which its configuration describes as "enabled via SYNC_ENABLE param".

**Before any change, all three read:**

- `MODE` NORMAL;
- `DETECT-METHOD` ACCWAVE;
- `TWFA-ENABLE` and `TWFB-ENABLE` ENABLED;
- `ALIVE-PERIOD` 45 Sec, `DETECT-PERIOD` 45 Sec/Tick and `DETECT-COUNT` 20 Ticks (read on 5C1805);
- `SYNC-ENABLE` ENABLED on 5C1705. The first read of 5C1805 and 5C168B missed them in the scan, but both were sending the same CMD frames.

## Runs

| Run | Change | Length | Frames | From the three V10.01 sensors |
|---|---|---|---|---|
| `./` (stream.jsonl) | `WR DETECT-METHOD ALWAYS` on all three, acknowledged and read back | 1800 s | 264, all decoded | 36 CMD frames each, one every 50 s; **no TWF**; `RD PHASE` = DETECT afterwards |
| `sync_off/` | `WR SYNC-ENABLE OFF` as well, acknowledged and read back | 1800 s | 314, all decoded | the same 36 CMD frames each; **no TWF** |

The other senders were heard as usual, including 108 and 111 V11 TWF frames from 5C1712.

## Why no TWF came

In this firmware line, the sensor takes the vibration sample that runs the machine-on check only when an ALIVE or TWF frame is due. When a different frame is due, it clears the sample request (`app_normal.c` at V10.01.2000, `APP_Normal_RadioAction`). I did not re-read that code at `3ac582ae7`, but the behaviour fits it:

- these sensors sent no ALIVE frame in any capture that day;
- so the check never runs, and the phase never leaves DETECT;
- so `ALWAYS`, which only changes the check's answer, has nothing to act on.

Disabling sync did not stop the CMD frames within 30 minutes. The change probably needs a reset to apply; I did not reset the sensors.

## Afterwards

On all three, `WR SYNC-ENABLE ON` and `WR DETECT-METHOD ACCWAVE` were sent, and each read back ENABLED and ACCWAVE.

## Result

#335 step 4 is **still not confirmed**. No 99-byte TWF frame was received. The layout still matches the build these sensors run, from its source.
