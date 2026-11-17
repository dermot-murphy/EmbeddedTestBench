![Embedded Test Bench](assets/embeddedtestbench-website-header.svg)

Bench test tooling: instrument drivers, a debug probe driver, a BLE dongle with
its own firmware, analysis of captured records, and a declarative test runner
that drives a bench and produces pass/fail evidence.

**No VISA installation required, and no vendor Python package.** VXI-11 and GDB/MI
are implemented directly on the Python standard library, so the package has **no
mandatory third-party dependencies** — checked by a test that parses every module,
not just asserted here.

```bash
pip install -e ".[spec,plot]"
benchtools run specs/clock_skew.yaml --simulate --markdown report.md
```

Everything below runs with no hardware: `sim://` and `--simulate` drive in-process
instrument models.

**New here?** Start with the [User Manual](https://github.com/dermot-murphy/EmbeddedTestBench/blob/main/docs/User_Manual.md): installing, a first
run on the simulated bench, the real bench and its safety limits, and a section
for Claude Code sessions.

## At a glance

Embedded Test Bench is for engineers who test embedded devices, such as wireless
sensors, on a bench of real instruments. It drives the bench from a test
specification, or from Python, and records each result with the evidence behind
it, on a desk or in CI. A simulated twin of every instrument runs the same tests
with no hardware at all.

### What it drives

What has been shown on real hardware, and how. *Qualified* means a system
qualification campaign ([ETB-SYS5-002](https://github.com/dermot-murphy/EmbeddedTestBench/blob/main/docs/aspice/EmbeddedTestBench_SYS5_002_System_Qualification_Test_Report.md))
ran it. *Checked on the bench* means it ran on the real instrument, outside such
a campaign. *Simulated only* means it has run only against its simulator. Every
instrument also has a simulator.

| Instrument | On hardware |
|---|---|
| GW Instek GPD-3303D power supply | Qualified, with its outputs off: QS-03 passed, setting and reading back the limits of independent outputs. No output has been switched on in a test |
| TTi 1604 multimeter | Checked on the bench: QS-09 failed ([#181](https://github.com/dermot-murphy/EmbeddedTestBench/issues/181)); the fix was checked on 2026-10-28 with the inputs open. Nothing has been measured against a reference |
| SEGGER J-Link debug probe | Qualified: QS-01 passed; QS-01b failed ([#178](https://github.com/dermot-murphy/EmbeddedTestBench/issues/178)), fixed and checked again on the bench on 2026-10-05 |
| Nordic nRF52840 BLE dongle, with its own firmware | Qualified: QS-02 passed |
| ST S2-LP sub-GHz development kit | Checked on the bench: QS-07 ended in error ([#179](https://github.com/dermot-murphy/EmbeddedTestBench/issues/179), since fixed; not yet rerun), with register access passing and a transmission sent but not shown to arrive. Receiving was checked on the bench since |
| PICO2 Test Board: Raspberry Pi Pico 2 thermometer, LEDs and frequency generator | Its identity is qualified (QS-10). LEDs checked on the bench on 2026-11-12. The thermometer has read a plausible room temperature, with no reference. The generator has been seen only on a scope, in an unrecorded check |
| PicoScope 3000D mixed-signal oscilloscope | Seen working on the bench on 2026-11-13 (analogue channel A), during development, not in a recorded test run |
| Nordic Power Profiler Kit II | Checked on the bench, with nothing wired to it, on 2026-11-14 |
| Tektronix TDS3014B oscilloscope | Simulated only |
| Serial capture of a device's console or test UART | Simulated only |

Each instrument's notes list what is still unconfirmed on hardware.

### Getting started

The latest release is on the [releases page](https://github.com/dermot-murphy/EmbeddedTestBench/releases/latest).
Install it with pip, putting its tag, such as `v0.03.0000`, in place of `<tag>`:

```bash
pip install "benchtools[spec] @ git+https://github.com/dermot-murphy/EmbeddedTestBench@<tag>"
```

The table above describes the source this page was generated from. What each
release contains is in its [Software Version Description (ETB-SVD-001)](https://github.com/dermot-murphy/EmbeddedTestBench/blob/main/docs/aspice/EmbeddedTestBench_SVD_Software_Version_Description.md).

Then run a specification on the simulated bench:

```bash
benchtools run specs/clock_skew.yaml --simulate --markdown report.md
```

In another project's CI, use the bench runner as a GitHub Action, as shown in
[Using the bench runner as an action](https://github.com/dermot-murphy/EmbeddedTestBench/blob/main/README.md#using-the-bench-runner-as-an-action).

### Where to read more

- [User Manual](https://github.com/dermot-murphy/EmbeddedTestBench/blob/main/docs/User_Manual.md): installing, a first run, the real bench and its safety limits
- [Bench Runner Guide](https://github.com/dermot-murphy/EmbeddedTestBench/blob/main/docs/Bench_Runner_Guide.md): writing specifications and bench files
- [Documentation index](https://github.com/dermot-murphy/EmbeddedTestBench/blob/main/docs/README.md): every document, including the ASPICE work products
- [System qualification test report (ETB-SYS5-002)](https://github.com/dermot-murphy/EmbeddedTestBench/blob/main/docs/aspice/EmbeddedTestBench_SYS5_002_System_Qualification_Test_Report.md): what the bench was shown to do on hardware
- Known problems: those in the release are in [ETB-SVD-001 §7](https://github.com/dermot-murphy/EmbeddedTestBench/blob/main/docs/aspice/EmbeddedTestBench_SVD_Software_Version_Description.md#7-known-problems-and-limitations); those found since are the [open issues](https://github.com/dermot-murphy/EmbeddedTestBench/issues)

## Links

- [Documentation wiki](https://github.com/dermot-murphy/EmbeddedTestBench/wiki)
- [Latest release](https://github.com/dermot-murphy/EmbeddedTestBench/releases/latest)
- [System qualification test report (ETB-SYS5-002)](https://github.com/dermot-murphy/EmbeddedTestBench/wiki/ASPICE-SYS5-002-System-Qualification-Test-Report)
- [Source repository](https://github.com/dermot-murphy/EmbeddedTestBench)

---

*Generated from `README.md` on the `main` branch by `scripts/publish_docs.py`. This branch is not edited by hand.*
