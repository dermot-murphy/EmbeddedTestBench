# Manifests for the simulated bench

These are **not** build outputs. They are the two manifests
`benches/simulated_bench.yaml` points at, so that `specs/sensor_bringup.yaml`
can be run end to end with no hardware and no firmware build:

| File | Stands in for | Must agree with |
|---|---|---|
| `dongle/firmware_manifest.json` | `firmware/nordic_dongle/_build/firmware_manifest.json` | `SimulatedDongle.DEFAULT_FIRMWARE_VERSION` and `DEFAULT_FIRMWARE_BUILT` |
| `sensor/firmware_manifest.json` | the sensor build's manifest | the version the simulated sensor reports for `rd version` |

The agreement is the point. The bring-up specification checks a dongle against
the build it should be running and compares what a sensor reports with what was
flashed onto it; if these files did not match the simulators, the simulated run
would fail for reasons that say nothing about the specification. They are
asserted to match in `tests/runner/test_sensor_bringup.py`, so a change to
either simulator that would have made this bench a fiction fails a test instead.

A real bench points at real build output — see `benches/lab1.yaml`.

## The Kepler sensor (#121, #122)

`simulated_bench.yaml` also stands in for the bench's Kepler sensor 5C1712. One
model of it (`benchtools/simulated/kepler.py`) is behind four instruments:

| Instrument | What it sees of 5C1712 |
|---|---|
| `dongle` | the sensor at `D1:8D:3B:4C:19:96`, answering `RD VERSION`, `RD SHA`, `RD ID`, `RD BATTERY`, `RD BATTERY-LOADED`, `RD TEMPERATURE`, `WR ALIVE-PERIOD`, `WR PREAMBLE-LENGTH` and `ECURESET HARD` |
| `psu` | its battery input on channel 2: `RD BATTERY` reads what channel 2 is set to |
| `rtt` | its RTT log, `MCU Temperature: <n>mC` once a second, because the entry sets `simulated_target: kepler-5C1712` |
| `s2lp` | its 433 MHz VERSION and ALIVE frames, three copies each, because the entry sets `simulated_targets: [kepler-5C1712]`; heard only once the kit's registers are set up for the sensor, as `plugin:kepler/s2lp_kepler_433_rx.regs` sets them |

All four Kepler specifications pass on this bench. The frames are on an air
clock that a waiting receive moves on to the next transmission, so the sensor's
10 s alive period takes no time. What the model assumes rather than captured is
listed in `benchtools/simulated/kepler.py` and in BLE-DD-KEPLERSIM. A simulated
pass shows that a specification and the bench agree with that model, not that
a sensor works.
