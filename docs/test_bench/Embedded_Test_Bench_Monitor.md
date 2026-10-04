# Embedded Test Bench monitor

| | |
|---|---|
| Tool | `tools/test_bench/test_bench.py`, with `sources.py` beside it |
| Based on | The Kepler reference project's `rf_monitor.py` v1.1.0, copied unchanged in the first commit of #82 so every change since is visible in the history |
| Issue | #82 |
| Status | **Frozen** since 2026-10-04 (#142). Replaced by the test run viewer, `benchtools view` |

> **Frozen.** The test run viewer (`benchtools view`, #130) replaces this
> monitor. It was tried on the real bench on 2026-10-04: its Run,
> Instruments, RF, BLE and Graphs pages all worked against sensor 5C1712, the
> S2-LP kit, the BLE dongle, the supply and the multimeter. From now on this
> monitor changes only to fix a defect. Nothing has been removed, and it
> still runs as described below.
>
> **What the viewer does not replace.** The viewer shows what a test run
> records in its event log, so it has nothing to show without a run. Three of
> the monitor's modes have no viewer equivalent, by design:
>
> - **`--port`**: receiving from the S2-LP kit with no test running, as a
>   standalone radio monitor;
> - **`--log`**: reading a log written by ST's S2-LP DK GUI, as rf_monitor did;
> - **`--simulate`**: a simulated kit with a sensor on the air, with no run.
>   The viewer's simulated benches simulate a run, not the air on its own.
>
> Every page has a viewer counterpart:
>
> | Monitor page | Viewer |
> |---|---|
> | Latest Data, Config, Environment, Short Interval, Ticks, TWF, Diagnostics, Sync, ST GUI | The RF page's tabs of the same names (#151 to #157), plus Identification |
> | Events | Event log, with pause and filters by instrument, kind, sensor and test (#148) |
> | PSU, J-Link | Instruments: each instrument's commands and replies, and the supply's and probe's front panels (#138) |
> | Notes, report export | Notes & report (#156) |
> | Settings (sensor filter) | The sensor filter on the RF and Event log pages (#148) |
> | Status bar | The status bar on every page (#149) |

rf_monitor decoded Kepler radio frames from the log ST's S2-LP DK GUI writes.
The Embedded Test Bench monitor keeps all of its pages, and adds five things:

1. **It reads the S2-LP kit itself**, through the benchtools driver, receiving
   with the firmware's own loop as ST's GUI does (#87), so ST's GUI is not
   needed. Each packet is rendered as the line ST's GUI would log and fed to
   rf_monitor's own parser, so every page decodes a live frame exactly as it
   decoded a logged one.
2. **An "ST GUI" page**, laid out as ST's S2-LP DK GUI is (its data brief,
   STSW-S2LP-DK, shows the screen):
   - *top left*, the RF setup: band (from the board's EEPROM), crystal,
     frequency, modulation, data rate, deviation, channel filter, output power,
     and the packet settings decoded from the registers - format, preamble,
     sync words, length, address, CRC, whitening, FEC, TX source, RX timeout;
   - *right*, the registers table: address, register, value and reset
     default, a register changed from its default in red, each row expanding
     to its fields. **Refresh** reads them again, **Export** saves them as a
     register file `--setup` applies;
   - *bottom left*, each frame received, as ST's GUI lists them: timestamp,
     number of bytes, RSSI, data in hex, with CRC failures shown as ST shows
     them.

   The setup is read when the monitor connects and on **Refresh**. The kit's
   port is shared with reception, so reception pauses while it is read - about
   0.3 s on the STEVAL-FKI433V2 - and the Events page records how long.
3. **An "Events" page**: what the whole bench is doing during a test, followed
   live from the run's event log, each source in its own colour and each with a
   checkbox to show or hide it.

   | Source | Colour | What it shows |
   |---|---|---|
   | ST RF | cyan | frames the monitor receives; the S2-LP driver's traffic |
   | PSU | orange | commands to and replies from the GPD-3303D |
   | BLE | blue | the dongle's lines: commands, replies, events |
   | J-Link | green | the probe's actions and every RTT line |
   | TEST | yellow | the runner: suite setup, each step, each test's result |
   | SCOPE, DMM | purple, pink | the oscilloscope's and multimeter's traffic |
   | BENCH | grey | transport housekeeping |

4. **A "PSU" page**: the GPD-3303D's front panel in the upper half - each
   channel's reading, set voltage, current limit and CV or CC, the output, the
   tracking mode - and its last ten commands, each with its reply, below.
5. **A "J-Link" page**: the probe's state in the upper half - probe, target,
   firmware, core halted or running and where it stopped, last flash and
   verify, breakpoints, RTT - and its latest traffic and log below: GDB
   commands, console and async records, RTT lines, the probe's reports.

   The monitor does not own the supply's or the probe's port - the test run
   does - so both pages are rebuilt from the run's event log. A value shows as
   a dash until the log has said it.

## Running it

```bash
pip install matplotlib numpy pyserial

# The kit on COM4, following a test run's events
python -m benchtools run specs/kepler_preamble.yaml --bench benches/lab1.yaml --event-log events.jsonl
python tools/test_bench/test_bench.py --port COM4 --event-log events.jsonl

# No hardware: a simulated kit with a sensor sending ALIVE every few seconds
python tools/test_bench/test_bench.py --simulate

# As rf_monitor did: a log written by ST's GUI
python tools/test_bench/test_bench.py --log rf_log.txt
```

Options: `--board` (optional; the driver reads the board's band from its
EEPROM anyway), `--setup` (register file to receive with; default
`configs/s2lp_kepler_433_rx.regs`), `--packet-log` (also write every packet,
raw and decoded), `--sensor-id` (the initial filter, as in rf_monitor).

**One owner per port.** The monitor opens the S2-LP kit's port, so a test run
alongside it must not use the kit - the run's events come to the monitor
through the event log instead, which is how the supply, dongle and J-Link, each
held by the run, appear on the Events page.

## What is not changed

rf_monitor's other pages - Latest Data, Environment, Short Interval, TWF,
Ticks, Config, Diagnostics, Sync, Notes, Settings and report export - are as
they were. Its status bar still tracks the sensor chosen in the Settings
filter.

The monitor is a tool beside the package, not part of it: it is not linted by
the package's pylint gate, and it needs matplotlib, numpy and tkinter.
`sources.py`, the part without a GUI, is tested in
`tests/tools/test_test_bench.py`.
