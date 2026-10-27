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
no part.

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
  `S2LPGetNBytesBatch` it was **12.0, 12.0 and 12.0 ms**, against 26 to 27 ms
  on 2026-10-25. Only `S2LPIrqGetStatus` was sent between the two, each time.
- **Copy spacing.** By the board's timer, packet A's copies came 131 ms then
  190 ms apart, and packet B's 229 ms then 31 ms apart.
- **`since_last` on hardware.** Packet B's copy 2 arrived 31 ms after copy 1,
  during the stop that ended call 2 (`events.tsv`: "1 replies with it"), and
  was set aside. Call 3, with `since_last=True`, returned it without starting
  a receive. This is the case the 2026-10-25 run did not reach.
