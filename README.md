![Embedded Test Bench](assets/logo_horizontal.png)

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

## Links

- [Documentation wiki](https://github.com/dermot-murphy/EmbeddedTestBench/wiki)
- [Latest release](https://github.com/dermot-murphy/EmbeddedTestBench/releases/latest)
- [System qualification test report (ETB-SYS5-002)](https://github.com/dermot-murphy/EmbeddedTestBench/wiki/ASPICE-SYS5-002-System-Qualification-Test-Report)
- [Source repository](https://github.com/dermot-murphy/EmbeddedTestBench)

---

*Generated from `README.md` on the `main` branch by `scripts/publish_docs.py`. This branch is not edited by hand.*
