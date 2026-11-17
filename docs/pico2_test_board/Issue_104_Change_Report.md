# Change Report — Issue #104: Pico 2 + SHT30-D thermometer

| Field | Value |
|---|---|
| Document ID | ETB-CR-104 |
| Date | 2026-09-30 |
| Issue | [#104](https://github.com/dermot-murphy/EmbeddedTestBench/issues/104) — read the local temperature with a Raspberry Pi Pico 2 and a DollaTek SHT30-D |
| Branch | `ccr-dd8136a2-4ayd75` |
| Element | `PICO-` (new) |

## 1. Summary

New bench instrument. A Raspberry Pi Pico 2 runs new C firmware that reads a
Sensirion SHT30-DIS on a DollaTek SHT30-D module over I2C. It reports its
**title and version** (`ver`) and the **temperature** (`temp`) over USB CDC.
A `benchtools` host driver, simulator, command line and example go with it.
The full ASPICE SWE.1–SWE.4 work-product set and the traceability matrix are
updated to match.

## 2. Decisions

| Question | Decision |
|---|---|
| Firmware language | C on the Pico C SDK, to MISRA C:2012, tab-indented |
| Scope | Firmware, host driver, tests, example, ASPICE documents |
| Reference documents | Committed where reachable; see §5 |
| Wiring | I2C0, SDA GP4 (pin 6), SCL GP5 (pin 7), address 0x44, 100 kHz |

## 3. What changed

| Area | Files |
|---|---|
| Firmware | `firmware/pico_sht30/` — `include/{protocol,firmware_version,board_config,hal}.h`, `src/{main,cmd_parser,sht30,text,hal_pico,firmware_version}.c`, `CMakeLists.txt`, `pico_sdk_import.cmake`, `README.md` |
| Firmware tests | `firmware/pico_sht30/test/` — `test_{text,sht30,cmd_parser}.c`, `support/fake_hal.{c,h}`, `CMakeLists.txt` |
| Host driver | `benchtools/instruments/pico_sht30/{__init__,constants,thermometer,simulator,cli}.py`; registered in `runner/bench.py` as `pico-sht30` / `thermometer`, and as `benchtools thermo` in `cli.py` |
| Host tests | `tests/instruments/pico_sht30/{conftest,test_thermometer,test_simulator,test_cli,test_firmware_protocol}.py`; `PICO` prefix registered in `tests/test_traceability.py` |
| Example | `examples/11_pico_thermometer.py` |
| CI | `.github/workflows/firmware.yml` — jobs `pico-unit-tests` and `pico-firmware` (uploads the `.uf2`) |
| ASPICE (`docs/aspice/`, after merging `develop`) | ETB-SWE1-001 v0.7 (§15 PICO, STK-21/22, CON-09, ASM-10), ETB-SWE2-001 v0.4 (PICO-ARC-001, AD-24, interfaces), ETB-SWE3-001 v0.5 (§5.8, 14 design units), ETB-SWE4-001 v0.5 (§1.4b, five groups), ETB-SWE4-002 v0.4 (§13A, totals), ETB-RTM-001 v0.7 (§13, STK rows, OPEN-09); each with a revision-history row |
| Other docs | `docs/pico_sht30/{Pico_SHT30_Notes,References}.md`, `fetch_datasheets.sh`, `datasheets/pico-2-r4-pinout.svg`; `README.md`, `docs/README.md` |

## 4. Verification

| Check | Result |
|---|---|
| Firmware target build (Pico SDK 2.1.1, Arm GNU 14.2.1, `pico2`) | **Pass**, 0 warnings with `-Werror`. `pico_sht30.uf2` 60 928 B; text 29 996 B, bss 3 884 B |
| Firmware unit tests (Unity, ASan + UBSan) | **61 / 61 pass** (text 10, sht30 22, cmd_parser 29) |
| Python suite (merged with `develop`) | **2 497 pass, 1 skipped** (a `develop` GUI test needing `tkinter`), 73 of them new; 95% statement coverage |
| pylint against `.pylint-baseline.json` (`scripts/lint.py`) | **0 new findings** |
| CStyleCheck v1.5.1 over all Pico C code, tests included (PICO-NFR-006) | **0 errors, 0 warnings, 0 info**, with no baseline. The first run found 210, which were fixed in code or covered by a documented alias or exclusion |
| Traceability and layering tests | **Pass** |
| Simulator smoke test | `benchtools thermo ver` / `temp` / `status`, and `examples/11_pico_thermometer.py` |
| On hardware | **Not done.** No Pico 2 or module was available (CON-09, PICO-OPEN-01 … -03) |
| MISRA checker run | **Not done.** No checker was available (PICO-OPEN-04). Conformance is by construction and review; deviations are listed in the notes, §6 |

## 5. Reference documents — limitation

The environment's network policy returned HTTP 403 for
`datasheets.raspberrypi.com` and `sensirion.com`, so the PDFs **could not be
downloaded**. Committed so far: the official Pico 2 pinout (SVG, from
Raspberry Pi's documentation repository, CC BY-SA 4.0). `References.md` lists
every document with its official URL. `fetch_datasheets.sh` downloads them in
one step on any machine with normal internet access (PICO-OPEN-04).

DollaTek publishes no datasheet or schematic for the module. The Sensirion
SHT3x-DIS datasheet is the authority for everything the firmware does. The
command codes and CRC were cross-checked against Sensirion's own open-source
driver.

## 6. Target branch and corrections

The PR targets `develop`. `develop` had moved the ASPICE documents to
`docs/aspice/TestBench_*.md`, with new headers, revision histories and a DMM
element. The PICO additions were re-applied to that structure: sections were
inserted before RUN and the later ones renumbered, as `develop` did for DMM. The
example was renumbered to `examples/11_pico_thermometer.py` because `develop`
already uses 09 and 10.

Corrections made along the way:

* The matrix coverage analysis said 177 functional and 18 non-functional
  requirements. It now states the declared totals: 343 and 35.
* The SWE.4 report's execution summary now shows this run. Its per-group table
  was not regenerated for groups `develop` added earlier, and the report says so.

## 7. Open items

| ID | Item |
|---|---|
| PICO-OPEN-01 | Flash the UF2 and confirm `ver` on a real Pico 2 |
| PICO-OPEN-02 | Confirm `temp` with the module, and `err 4` with it removed |
| PICO-OPEN-03 | Accuracy against a reference thermometer (±0.2 °C typical) |
| PICO-OPEN-04 | Fetch and commit the reference PDFs; run a MISRA C:2012 checker |
