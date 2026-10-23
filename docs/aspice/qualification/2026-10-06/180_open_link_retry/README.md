# #180 on hardware: retrying a link that fails to establish

Evidence for ETB-SWE4-002 §10.5 and D-51. Run on 2026-10-06 on the bench PC
(`benches/bench_pc.yaml`): PCA10059 dongle on COM10, sensor 5C1712
(`KAPPA_5C1712_V11.00.000`, D1:8D:3B:4C:19:96, firmware
V11.00.0000-95-gc051f3665). Branch `fix/open-link-retry` at `d31d608`,
CPython 3.14.7, Windows 10. The supply and the J-Link were not used.

The runs were made from a scratch directory, so the reports name a document
path outside the repository. The files are copied here unchanged.

| File | What it is |
|---|---|
| `reset_cycles.py` | Run 1: `NordicDongle.open_link()` (3 attempts), `RD VERSION`, `ECURESET HARD`, 10 times |
| `results.json` | Run 1: one row per cycle |
| `python.log` | Run 1: Python log, with the `ble_connect_attempt` warning |
| `dongle_session.log` | Run 1: the dongle session log, with the retry note |
| `connect_after_reset.md` | Run 2: the command document, 8 `ECURESET HARD` and reconnect cycles |
| `doc_report.md` | Run 2: the markdown report |
| `doc_events.log` | Run 2: the event log, with a `CONNECT` line for each failed try |
| `doc_session.log` | Run 2: the dongle session log |

Run 2 was started with:

```
python -m benchtools ble -r COM10 --log doc_session.log script connect_after_reset.md \
    --var SENSOR_ID=D1:8D:3B:4C:19:96 --report doc_report.md --events doc_events.log
```
