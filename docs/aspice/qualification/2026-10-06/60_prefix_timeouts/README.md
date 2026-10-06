# #60 on hardware: timeouts by command prefix

Run on 2026-10-06 on the bench PC (`benches/bench_pc.yaml`): PCA10059 dongle
on COM10, sensor 5C1712 (`KAPPA_5C1712_V11.00.000`, D1:8D:3B:4C:19:96, firmware
V11.00.0000-95-gc051f3665). Branch `feature/prefix-timeouts` at `c52a269`,
CPython 3.14.7, Windows 10. The supply and the J-Link were not used.

The runs were made from a scratch directory, so the reports name a document
path outside the repository. The files are copied here unchanged.

`prefix_timeouts.md` declares `RD` (`${RD_MS}`, 20000 by default),
`rd version` (5000), `RD ID` (2000) and `ECURESET` (15000), and steps that
take their timeout from each source: a longer prefix, a shorter one, a
variable, a Timeout cell, the run's default, a listening window, the wait for
a `<disconnect>`, and `connect`, which a prefix does not apply to.

| Run | Started with | Result |
|---|---|---|
| 1 | `--var SENSOR_ID=D1:8D:3B:4C:19:96` | **PASS**: 6 passed, 0 failed, 0 errors, 4 skipped |
| 2 | as 1, plus `--var RD_MS=30000 --timeout rd=25000 --timeout XX=4000 --timeout-s 6` | **PASS**: 6 passed, 0 failed, 0 errors, 4 skipped |

The timeout each step reported, from `run1_report.md` and `run2_report.md`:

| Step | Command | Run 1 | Run 2 |
|---|---|---|---|
| 1, 8 | `connect` | 30000 ms, Timeout cell | 30000 ms, Timeout cell |
| 2 | `RD VERSION` | 5000 ms, prefix rd version (document) | 5000 ms, prefix rd version (document) |
| 3 | `RD TEMPERATURE` | 20000 ms, prefix RD (document) | 25000 ms, prefix rd (--timeout) |
| 4 | `RD BATTERY` | 8000 ms, Timeout cell | 8000 ms, Timeout cell |
| 5 | `RD ID`, nothing expected | 2000 ms, prefix RD ID (document) | 2000 ms, prefix RD ID (document) |
| 6 | `XX NOTHING` | 3000 ms, run default (--timeout-s) | 4000 ms, prefix XX (--timeout) |
| 7 | `ECURESET HARD`, `<disconnect>` | 15000 ms, prefix ECURESET (document) | 15000 ms, prefix ECURESET (document) |
| 9 | `rd version` | 5000 ms, prefix rd version (document) | 5000 ms, prefix rd version (document) |

`run1.json` carries the same values as `timeout_ms` and `timeout_from`, and
each `TX` line of the event logs states them.

Step 5's listening window ended when the sensor's reply arrived, about 50 ms
after the command, not after 2000 ms: a command with nothing expected waits up
to its window for a reply. `develop` waits the same way, so this change did
not alter it.

`run1_attempt1_argerror.txt` is a first attempt at run 1 that never started:
`--json` was given after `script`, and argparse refused it (exit 2). It was run
again with `--json` before the sub-command.

`benchtools ble script ... --timeout 5` was also tried: it is refused with
`error: --timeout takes PREFIX=MS ... The run's default is --timeout-s.`
