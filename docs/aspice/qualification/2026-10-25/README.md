# #293 on hardware: frames between two `kepler_frame` calls

Run on 2026-10-25 on the bench PC. Hardware: the S2-LP kit (NUCLEO-L053R8 with
STEVAL-FKI433V2) on COM4, set up with `configs/s2lp_kepler_433_rx.regs`, and
sensor 5C1712's ALIVE packets on air. Software: CPython 3.14.7 on Windows 10,
pyserial 3.5, with `benchtools` from this repository's working tree on
`fix/293-kepler-frame-between-calls` at 0960059.

The run only listened. No command went to the sensor, and no other instrument
was used.

## Run

`293_kepler_frame_gap/measure_293.py` makes three
`kepler_frame("ALIVE", source="5C1712")` calls in a row on each of two ALIVE
packets: the first packet with the default, the second with
`since_last=True`. It wraps the session's `send` and `stop`, and the driver's
packet record, to time each step.

| File | What |
|---|---|
| `results.json` | What each call returned |
| `events.tsv` | Seconds from the first call: each command sent, each stop, each frame recorded, each call's start and end |
| `s2lp_session.log` | The raw session log: every line both ways, with wall-clock timestamps |
| `s2lp_packets.jsonl` | The packet log: every reception, including other sensors and CRC failures |

## Results

| Packet | Call 1 | Call 2 | Call 3 |
|---|---|---|---|
| A, default | copy 0 | copy 1 | timed out after 3 s: "1 such frame arrived while the last receive was stopping ... since_last takes them" |
| B, `since_last=True` | copy 0 | copy 1 | copy 2 |

- **Copy spacing.** By the board's timer, packet A's copies came 229 ms then
  31 ms apart, and packet B's 135 ms then 111 ms apart. Copy 2 of packet A
  arrived during the stop that ended call 2. That stop took 33.5 ms, against
  3.5 to 4.4 ms for the others. The copy was logged and set aside, which is
  the failure #293 reported, now named in the error.
- **Deaf gap.** From the `StopCmd` acknowledgement to the echo of the next
  `S2LPGetNBytesBatch` it was 25.9, 27.0, 26.7 and 27.0 ms (session log
  timestamps). It is mostly three commands of about 7 ms each:
  `S2LPIrqGetStatus`, `S2MGpioGetValue` and `S2LPGetNBytesReportAll`. A frame
  that arrives in that gap is missed, with or without `since_last`.
