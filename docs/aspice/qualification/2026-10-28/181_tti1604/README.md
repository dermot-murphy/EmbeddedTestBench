# #181 on the TTi 1604, 2026-10-28

Hardware: TTi 1604 on COM13 through FTDI converter A9LQ0R81A, the bench PC,
inputs open throughout (confirmed by the owner). The owner watched the front
panel and pressed its keys where noted.

## Sequence

| # | Capture | What was done | What happened |
|---|---|---|---|
| 1 | `raw/hz_raw_1.txt` | AC volts, then Hz over the link; 30 s raw | `j` echoed; **no frame** in 30 s |
| 2 | (console) | Reconnect | Remote `u` echoed; no frame in 22 s: the meter was still in Hz |
| 3 | `raw/after_hz_volts.txt` | V over the link; 15 s raw | No echo, no frame |
| 4 | `raw/after_hz_volts_45s.txt`, `raw/after_hz_local.txt` | Reconnect twice | Remote `u` not echoed: the link ignored everything |
| 5 | (owner) | Front panel read | **AC, V and Hz lit; digits `0004x`, the last between 0 and 6**: measuring, not sending |
| 6 | (owner) | V pressed on the front panel | AC V and AUTO lit; `benchtools dmm read` answered again |
| 7 | `raw/hz_toggle.txt` | Hz over the link, then Hz again 15 s later | First `j` echoed and taken; the second neither echoed nor acted on. Owner: "back to Hz". V pressed on the panel again |
| 8 | `raw/ohms_open.txt` | Ohms over the link; 12 s raw | Six blank frames, ranges 0 to 5, over 2.8 s, then `0d 55 c8 00 00 fc 8e 1c 01 04`, decoded as overrange. Owner: the panel shows OFL |
| 9 | `bench_test_console.txt`, `tti1604_bench_findings.md` | `tests/bench/tti1604` with the fix, no reference wired | **9 passed, 5 skipped, 0 failed** (QS-09 run 1: 6 passed, 4 failed) |
| 10 | `hz_no_signal_driver.txt` | The fixed driver: `select_hertz`, then `select_volts`, `read` | `select_hertz` raised the recovery message after 8.4 s; the next calls raised it after 0.9 s and 2.0 s, not 22 s |
| 11 | `after_front_panel_v.txt` | V pressed on the panel by the owner; then the driver | Readings resumed at once; the meter was left on DC volts, auto-ranging, in local mode |

## Findings

1. **Frequency is not "not recognised".** The meter switches to Hz, but with
   no signal it sends no frame, so nothing confirms the switch. The driver's
   error showed the reading from before the key.
2. **The meter is not lost; the link is ignored.** In Hz with no signal it
   ignores every key over the link, echo included, until the front panel is
   used. There is no way out over the link (step 7). A power cycle was not
   needed.
3. **Open-input ohms is an overrange.** The decoder reads 0FL correctly; the
   QS-09 frame was a blank one sent while auto-ranging.

Still open: the frequency gate times (DMM-OPEN-06) need a signal source,
which the bench does not have.
