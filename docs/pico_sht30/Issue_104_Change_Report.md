# Change Report — Issue #104: Pico 2 + SHT30-D thermometer

| Field | Value |
|---|---|
| Document ID | BENCHTOOLS-CR-104 |
| Date | 2026-09-30 |
| Issue | [#104](https://github.com/dermot-murphy/TestTools/issues/104) — read the local temperature with a Raspberry Pi Pico 2 and a DollaTek SHT30-D |
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
| Example | `examples/09_pico_thermometer.py` |
| CI | `.github/workflows/firmware.yml` — jobs `pico-unit-tests` and `pico-firmware` (uploads the `.uf2`) |
| ASPICE | SWE.1 v4.3 (§12, STK-21/22, CON-09, ASM-10), SWE.2 v4.1 (PICO-ARC-001, AD-24, interfaces), SWE.3 v4.3 (14 design units), SWE.4 spec v4.3 (§1.4b, five groups), SWE.4 report v4.3 (§10A, totals), Traceability Matrix v4.3 (§9, STK rows, OPEN-09) |
| Other docs | `docs/pico_sht30/{Pico_SHT30_Notes,References}.md`, `fetch_datasheets.sh`, `datasheets/pico-2-r4-pinout.svg`; `README.md`, `docs/README.md` |

## 4. Verification

| Check | Result |
|---|---|
| Firmware target build (Pico SDK 2.1.1, Arm GNU 14.2.1, `pico2`) | **Pass**, 0 warnings with `-Werror`. `pico_sht30.uf2` 60 928 B; text 29 996 B, bss 3 884 B |
| Firmware unit tests (Unity, ASan + UBSan) | **61 / 61 pass** (text 10, sht30 22, cmd_parser 29) |
| Python suite | **1 956 / 1 956 pass**, 73 of them new; 95% statement coverage |
| Traceability and layering tests | **Pass** |
| Simulator smoke test | `benchtools thermo ver` / `temp` / `status`, and `examples/09_pico_thermometer.py` |
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

## 6. Corrections made to existing documents along the way

* The Traceability Matrix §12 said 177 functional and 18 non-functional
  requirements; SWE.1 already declared 258 and 26. It now states the actual
  282 and 31.
* In the SWE.4 report §2, two rows no longer matched the collected counts:
  `SWE4-UT-BLEFIRMWARE` (49 → 50) and `SWE4-UT-LAYERING` (81 → 88). Both are
  corrected. The report's §3 coverage-detail table (7 604 statements) also
  predates this change and was **not** regenerated.
* `README.md` said "eighteen architectural decisions"; there are 24.

## 7. Open items

| ID | Item |
|---|---|
| PICO-OPEN-01 | Flash the UF2 and confirm `ver` on a real Pico 2 |
| PICO-OPEN-02 | Confirm `temp` with the module, and `err 4` with it removed |
| PICO-OPEN-03 | Accuracy against a reference thermometer (±0.2 °C typical) |
| PICO-OPEN-04 | Fetch and commit the reference PDFs; run a MISRA C:2012 checker |
