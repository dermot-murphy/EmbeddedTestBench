# Hardware qualification — procedure (TB-SYS5-001, #176)

These specifications are the hardware configuration of TB-SYS5-001's
qualification scenarios. They run against `benches/bench_pc.yaml`, the Windows
bench PC. The results of the 2026-10-04 campaign and their evidence are in
TB-SYS5-002 and `docs/aspice/qualification/2026-10-04/`.

## Safety limits, set by the owner

Kepler sensor 5C1712 is wired to the GPD-3303D's outputs. While it is:

- the supply stays in **INDEPENDENT** tracking: series or parallel could put up
  to twice the intended voltage on the sensor;
- every voltage setpoint stays **between 2.8 V and 3.3 V**;
- **no output is switched on**;
- the driver's `psu.reset()` is not used, because it sets 0 V.

`qs03_supply.yaml` keeps to these limits. Before running any specification
that touches the supply, check that it does too.

## Before starting

1. Check the ports against the serial numbers in `benches/bench_pc.yaml`. The
   COM numbers can change when a device is re-plugged.
2. Leave the multimeter's inputs open; QS-09 depends on it.
3. **Back up sensor 5C1712** before QS-01. QS-01 and QS-01b chip-erase it.

   ```
   nrfjprog -f NRF52 --readcode 5C1712_full_backup.hex --readuicr
   nrfjprog -f NRF52 --reset
   ```

   Keep a second copy away from the session's scratch area.
4. Use a Python with pyserial and pyyaml. On the bench PC that is
   `C:\compilers\python\python311\python.exe`.

## Order, and what each run needs

Write each run's evidence beside the others:

`--event-log E/<id>.events.jsonl --markdown E/<id>.md --json E/<id>.json --junit E/<id>.junit.xml`

| Order | Scenario | Command | Needs |
|---|---|---|---|
| 1 | QS-01 | `benchtools run specs/qualification/qs01_bringup.yaml --bench benches/bench_pc.yaml` | The backup. Flashes V10.01.2000 |
| 2 | QS-01b | `... qs01b_debug.yaml ...` | Flashes the reference V11.00.0000-96 release build and loads its ELF |
| 3 | restore | see below | The backup |
| 4 | QS-02 | `... qs02_kepler_commands.yaml ...` | The sensor's own firmware, restored |
| 5 | QS-07 | `... qs07_subghz_link.yaml ...` | The S2-LP kit on COM4 |
| 6 | QS-03 | `... qs03_supply.yaml ...` | The supply in INDEPENDENT, outputs off |
| 7 | QS-06 | `... qs06a_missing_instrument.yaml ...` and `... qs06b_refusals.yaml ...` | Then reset the sensor (below) |
| 8 | QS-09 | `set BENCHTOOLS_TTI1604=COM13` and `set BENCHTOOLS_TTI1604_REPORT=E\qs09_tti1604_bench_findings.md`, then `python -m pytest tests/bench/tti1604 -v --junitxml=E\qs09.junit.xml` | Multimeter inputs open |
| 9 | QS-10 | `... qs10_bench_identity.yaml ...`, then the same with `--simulate` and `_simulated` in the evidence names | Every instrument except the J-Link |
| 10 | QS-08 | `gh run list --branch develop` | CI's latest runs on `develop` |

`...` stands for `python -m benchtools run specs/qualification/`, plus the bench
option and the evidence options above.

### Restoring the sensor (after QS-01b)

```
nrfjprog -f NRF52 --eraseall
nrfjprog -f NRF52 --program 5C1712_full_backup.hex --verify
nrfjprog -f NRF52 --readcode after_restore.hex --readuicr
nrfjprog -f NRF52 --reset
```

`after_restore.hex` must be byte-identical to the backup (`cmp`). Check that the
sensor answers `RD VERSION` with its own version again.

### After any run that attaches the J-Link

A GDB attach halts the sensor's SoftDevice, and after detach the sensor faults
and stops advertising (#95). Reset it:

```
nrfjprog -f NRF52 --reset
```

## Reading the results

Some tests are written to end in ERROR, because the requirement is that the
bench refuses. Their names say "(expected ERROR)" or "(expected FAIL)", and
TB-SYS5-002 reads such an outcome as the pass.

When a run ends otherwise, keep its evidence under `attempts/` with a numbered
name, and record why in TB-SYS5-002. Never overwrite it.
