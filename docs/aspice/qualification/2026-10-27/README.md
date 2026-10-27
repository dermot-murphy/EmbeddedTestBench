# #299 on hardware: a shorter re-arm between two receives

Run on 2026-10-27 on the bench PC, with the S2-LP kit on COM4 (NUCLEO-L053R8
with STEVAL-FKI433V2) set up with
`plugins/kepler/configs/s2lp_kepler_433_rx.regs`, and sensor 5C1712's ALIVE
packets on air. Software: CPython 3.14.7 on Windows 10, with `benchtools` from
this repository's working tree on `fix/299-s2lp-rearm-gap`, based on `develop`
cf0114c.

Both runs only listened. No command went to the sensor, and no other
instrument was used.

## 1. Probes before the change (`299_rearm_probe/`)

`probe_299.py` drives the kit's session directly, so the driver change plays
no part, and its packet log stays empty: only the session log is kept.

| Probe | What | Result |
|---|---|---|
| E1 | 300 batch receives, each run 50 to 320 ms and stopped by the host, then `S2LPIrqGetStatus` and `S2MGpioGetValue 3`, as the driver did before every receive | The line read high 300 times out of 300. IRQ_STATUS read `09605002` every time |
| E2 | `S2LPGetNBytesReportAll 1` sent once, then 20 batches of 3 s started without it | 31 of 31 reports carried the report-all fields (`{seq_num...}`) |

E1 is the ground for skipping the line check right after the driver's own
acknowledged stop; IRQ_STATUS is still read, which clears what the stop leaves
pending (#99). E2 is the ground for sending ReportAll once per connection.

## 2. The gap with the change (`299_kepler_frame_gap/`)

`measure_299.py` is the #293 script (`docs/aspice/qualification/2026-10-25/`)
with the plugin's register file path. It makes three
`kepler_frame("ALIVE", source="5C1712")` calls in a row on each of two ALIVE
packets: the first with the default, the second with `since_last=True`.

| Packet | Call 1 | Call 2 | Call 3 |
|---|---|---|---|
| A, default | copy 0 | copy 1 | copy 2 |
| B, `since_last=True` | copy 0 | copy 1 | copy 2, taken from the frames set aside |

- **Gap.** From the `StopCmd` acknowledgement to the echo of the next
  `S2LPGetNBytesBatch` it was **12.0, 11.0, 12.0 and 12.0 ms**, against 26 to
  27 ms on 2026-10-25. Those are the four times a call's return was followed by
  another call's receive: A1, A2 and B0, which follows A2 at once, and B1. Only
  `S2LPIrqGetStatus` was sent between the two, each time. One echo began with
  the firmware's `>` prompt (session log line 1520), which a first count missed.
- **Copy spacing.** By the board's timer, packet A's copies came 131 ms then
  190 ms apart, and packet B's 229 ms then 31 ms apart.
- **`since_last` on hardware.** Packet B's copy 2 arrived 31 ms after copy 1,
  during the stop that ended call 2 (`events.tsv`: "1 replies with it"), and
  was set aside. Call 3, with `since_last=True`, returned it without starting
  a receive. This is the case the 2026-10-25 run did not reach.

## 3. Stops with more pending (`299_rearm_probe_e3/`)

Added after review of PR #307, which asked whether a stop with a reception
pending, the case #99 was about, had been tried. `probe_299_e3.py` makes 2 000
batch receives, each stopped by the host after a random 5 to 120 ms, while
other sensors and noise are on air. After each stop it reads IRQ_STATUS and
then the line. It ran on this branch's working tree, after commit 66b94a7, for
`S2lpSession.last_stop_acknowledged`.

| IRQ_STATUS after the stop | Stops | Line high after the read | A frame came with the stop |
|---|---|---|---|
| 0x09605002 (clean) | 1 994 | 1 994 | 76 |
| 0x09607002 | 5 | 5 | 0 |
| 0x00000601 | 1 | 1 | 0 |

Every stop was acknowledged. #99's 0x09607003 did not occur. The driver now reads
IRQ_STATUS and checks the line whenever more is pending than a clean stop
leaves (`CLEAN_STOP_IRQS`), so the 6 stops in the last two rows, and #99's case,
get the line check.
