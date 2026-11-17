# #396: the dongle reports dropped lines in `+drop`

Bench check on 2026-11-17, on hardware: the bench dongle (PCA10059, COM10)
running firmware 1.9.0 from branch `fix/396-code-notes-agree`, built
2026-11-17T22:30:08Z.

## Method

1. `select 45:56:86:D3:FD:71` (the device seen most often in a scan), `adv start`,
   `scan start 60000`.
2. Close the host port for 55 s. With the port closed the firmware queues
   every line and drops what does not fit in its 31 free slots.
3. Reopen the port, read for 4 s, then `adv stop`, `scan stop`, `ver`.

`ble_session.log` is everything read after the port was reopened.

## Result: PASS

| Item | Value |
|---|---|
| `+drop` events | 1: `+drop t=219099861 count=164` |
| Sum of `+drop` counts | 164 |
| `adv stats` on `adv stop` | `received=213 reported=49` |
| `ver` | `dropped=164` |

The `+drop` count equals the firmware's own total, and
`received` = `reported` + `dropped` (213 = 49 + 164). The report arrived
once the queue had room again, after the queued lines.

The dongle was put back on the build Kepler pins (1.8.0, built
2026-11-17T09:36:12Z) afterwards.
