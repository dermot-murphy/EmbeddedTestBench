# #340 and #335 on hardware: a 20-minute receive

## Setup

- **Date and place:** 2026-11-14, the bench PC.
- **Kit:** the S2-LP kit on COM4 (NUCLEO-L053R8 with STEVAL-FKI433V2), running ST's CLI firmware, set up with `plugins/kepler/configs/s2lp_kepler_433_rx.regs`.
- **Software:**
  - CPython 3.14.7 on Windows 10;
  - `benchtools` from a local, unpushed merge of `fix/340-viewer-single-decode` (95cf34e) and `fix/335-v1001-twf` (b2bbd13) into `develop` (8893180).

The run only listened. No command went to any sensor, and no other instrument was used.

```bash
python -m benchtools s2lp -r COM4 --board STEVAL-FKI433V2 --plugin plugins/kepler \
    --setup plugin:kepler/s2lp_kepler_433_rx.regs --log events.jsonl \
    --packet-log packets.jsonl --json summary.json \
    stream --decode kepler --timeout 1200 > stream.jsonl
```

## Result

173 frames, 0 rejected, 0 undecoded (`summary.json`):

| Sender | Firmware (RF_CAP) | Frame type | Length | Frames |
|---|---|---|---|---|
| 5C1712 | V11 (6) | TWF | 100 | 72 |
| 5C1712 | V11 (6) | ALIVE | 35 | 9 |
| 5C4EE7 | V11 (6) | RESPONSE | 14 | 10 |
| 5C1805 | V10.01 (5) | CMD | 15 | 24 |
| 5C1705 | V10.01 (5) | CMD | 15 | 24 |
| 5C168B | V10.01 (5) | CMD | 15 | 24 |
| 5C314E | V10.00 (4) | ALIVE | 35 | 6 |
| 5BD456 | (2) | ALIVE | 41 | 4 |

### #340: the record names its decoder

- **The driver.** Every one of the 173 records names its decoder: `"decoder": "kepler"`, in both `stream.jsonl` and `packets.jsonl`.
- **The viewer.** `viewer_check.py` feeds the packet log to the viewer's `RfFrames` as `rf_packet` records, and counts how often the Kepler decoder runs (`viewer_check.txt`):
  - **As logged**, with the decoder named: 173 frames received and described, and **0** decoder calls.
  - **With the `decoder` field removed**, as in a log from before #340: 173 frames described, and 173 decoder calls, as before #340.

  The stream's own event log (`--log`) is the session's raw log and carries no `rf_packet` records. That is why the check feeds the packet log.

### #335: the V10.01 TWF frame was not seen

- The three V10.01 sensors were on the air. They sent RF_CAP 5, as the firmware source says, but only CMD frames, every 50 s.
- V10.01 sends TWF only in its TRANSMIT phase (`app_normal.c` at V10.01.2000). None of these sensors was in that phase in 20 minutes.
- So the 99-byte layout is still checked only against frames built from the firmware source.
- Sending a command to these sensors to change their phase is outside the bench rules: sensor commands go to 5C1712 only. So the bench step of #335 stays open.
