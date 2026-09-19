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
