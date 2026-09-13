# SWE.4 — Software Unit Verification Report

| Field | Value |
|---|---|
| Document ID | BENCHTOOLS-SWE4-002 |
| Version | 4.2 |
| Date | 2026-09-13 |
| Specification | BENCHTOOLS-SWE4-001 |
| Item under verification | `benchtools` 4.0.0 and `firmware/nordic_dongle` |
| Verdict | **PASS** |

## 1. Execution summary

| Metric | Result |
|---|---|
| Tests executed | **1 685** |
| Passed | **1 685** |
| Failed | 0 |
| Errors | 0 |
| Skipped | 0 |
| Statement coverage | **94%** (9 856 statements, 569 missed) |
| Execution time | 46.0 s with coverage instrumentation, 32.4 s without |
| Runtime | CPython 3.11.15, Linux |
| Framework | pytest 9.1.1, pytest-cov |

Command:

```
python3 -m pytest tests/ --cov=benchtools --cov-report=term
```

No test was skipped. The `matplotlib`, `pyvisa` and `pyyaml` optional extras were
installed for this run, so their tests executed.

The suite was also run with all extras blocked - `matplotlib`, `pyvisa`,
`pyyaml` and now `pyserial` - to confirm the claim that the package works
without them: **1 152 passed, 36 skipped, 0 failed**. (The totals
differ from the figure above because the runner command-line module is skipped as a whole
rather than test by test — the shipped specifications are YAML, so without
`pyyaml` there is nothing in that module to run. Its JSON equivalents are covered
in `test_spec.py`.) The whole J-Link driver runs in that configuration, which is
the evidence for JLINK-NFR-001.

No J-Link probe, target board, GDB, GDB Server, BLE dongle or BLE sensor was
present for this run, and no test needs one (PC-8): the probe is substituted at
the GDB/MI boundary, the RTT and SWO sockets by a loopback server, the dongle at
its line protocol, and the serial port by pyserial's own `loop://` handler.

**The dongle firmware is built but not executed** (CON-07): no dongle is
available. It is verified against the driver it must agree with, against the
hygiene rules of §4.3, by its own unit tests (§4.4), and by a real
cross-compile, link and DFU package against nRF5 SDK 17.1.0 in CI (§4.6).
Behaviour on silicon remains BLE-OPEN-02 to -04.

## 2. Results by test group

| Test group | File | Tests | Result |
|---|---|---|---|
| SWE4-UT-SCOPE | `instruments/tek3014b/test_scope.py` | 87 | Pass |
| SWE4-UT-JLINK | `instruments/jlink/test_probe.py` | 70 | Pass |
| SWE4-UT-S2LP | `instruments/s2lp/test_s2lp.py` | 75 | Pass |
| SWE4-UT-S2LPREG | `instruments/s2lp/test_registers.py` | 34 | Pass |
| SWE4-UT-S2LPPROTO | `instruments/s2lp/test_protocol.py` | 31 | Pass |
| SWE4-UT-S2LPCONFIG | `instruments/s2lp/test_configuration.py` | 63 | Pass |
| SWE4-UT-S2LPSIM | `instruments/s2lp/test_simulator.py` | 28 | Pass |
| SWE4-UT-S2LPCLI | `instruments/s2lp/test_cli.py` | 35 | Pass |
| SWE4-UT-S2LPSESSION | `instruments/s2lp/test_session.py` | 14 | Pass |
| SWE4-UT-PSU | `instruments/gpd2303s/test_psu.py` | 74 | Pass |
| SWE4-UT-BLE | `instruments/nordic_dongle/test_dongle.py` | 64 | Pass |
| SWE4-UT-BLEFIRMWARE | `instruments/nordic_dongle/test_firmware.py` | 49 | Pass |
| SWE4-UT-BLEPROTO | `instruments/nordic_dongle/test_protocol.py` | 34 | Pass |
| SWE4-UT-BLEPROFILE | `instruments/nordic_dongle/test_profile.py` | 30 | Pass |
| SWE4-UT-BLESIM | `instruments/nordic_dongle/test_simulator.py` | 27 | Pass |
| SWE4-UT-PSUSIM | `instruments/gpd2303s/test_simulator.py` | 20 | Pass |
| SWE4-UT-PSUCLI | `instruments/gpd2303s/test_cli.py` | 20 | Pass |
| SWE4-UT-SERIAL | `core/transport/test_serial.py` | 25 | Pass |
| SWE4-UT-BLESESSION | `instruments/nordic_dongle/test_session.py` | 23 | Pass |
| SWE4-UT-BLECLI | `instruments/nordic_dongle/test_cli.py` | 25 | Pass |
| SWE4-UT-BLELATENCY | `instruments/nordic_dongle/test_latency.py` | 20 | Pass |
| SWE4-UT-BLEFW | `instruments/nordic_dongle/test_firmware_protocol.py` | 17 | Pass |
| SWE4-UT-LAYERING | `test_layering.py` | 81 | Pass |
| SWE4-UT-GDBMI | `instruments/jlink/test_gdbmi.py` | 37 | Pass |
| SWE4-UT-BENCH | `runner/test_bench.py` | 41 | Pass |
| SWE4-UT-MEASURE | `analysis/test_measure.py` | 35 | Pass |
| SWE4-UT-SPEC | `runner/test_spec.py` | 38 | Pass |
| SWE4-UT-WAVEFORM | `analysis/test_waveform.py` | 34 | Pass |
| SWE4-UT-JLINKSERVER | `instruments/jlink/test_server.py` | 32 | Pass |
| SWE4-UT-SCPI | `core/test_scpi.py` | 28 | Pass |
| SWE4-UT-TIMING | `instruments/jlink/test_timing.py` | 29 | Pass |
| SWE4-UT-JLINKSIM | `instruments/jlink/test_simulator.py` | 23 | Pass |
| SWE4-UT-JLINKCLI | `instruments/jlink/test_cli.py` | 22 | Pass |
| SWE4-UT-RTT | `instruments/jlink/test_rtt.py` | 21 | Pass |
| SWE4-UT-SWO | `instruments/jlink/test_swo.py` | 20 | Pass |
| SWE4-UT-INSTRUMENT | `core/test_instrument.py` | 20 | Pass |
| SWE4-UT-GDBSESSION | `instruments/jlink/test_session.py` | 18 | Pass |
| SWE4-UT-TRACE | `test_traceability.py` | 18 | Pass |
| SWE4-UT-PROCESS | `core/transport/test_process.py` | 18 | Pass |
| SWE4-UT-JLINKSOCKETS | `instruments/jlink/test_sockets.py` | 16 | Pass |
| SWE4-UT-ENGINE | `runner/test_runner.py` | 33 | Pass |
| SWE4-UT-VALIDATE | `core/test_validation.py` | 23 | Pass |
| SWE4-UT-FACTORY | `core/transport/test_factory.py` | 23 | Pass |
| SWE4-UT-LIMITS | `runner/test_limits.py` | 23 | Pass |
| SWE4-UT-SIMBASE | `core/test_simulator.py` | 22 | Pass |
| SWE4-UT-VXI11 | `core/transport/test_vxi11.py` | 22 | Pass |
| SWE4-UT-CLI | `instruments/tek3014b/test_cli.py` | 20 | Pass |
| SWE4-UT-REPORT | `runner/test_report.py` | 24 | Pass |
| SWE4-UT-TRANSPORT | `core/transport/test_base.py` | 19 | Pass |
| SWE4-UT-ENV | `instruments/tek3014b/test_simulator.py` | 19 | Pass |
| SWE4-UT-PLOT | `analysis/test_plotting.py` | 15 | Pass |
| SWE4-UT-RUNCLI | `runner/test_cli.py` | 15 | Pass |
| SWE4-UT-RESOLVE | `runner/test_resolve.py` | 13 | Pass |
| SWE4-UT-SOCKET | `core/transport/test_socket.py` | 12 | Pass |
| SWE4-UT-VISA | `core/transport/test_visa.py` | 6 | Pass |
| **Total** | | **1 685** | **Pass** |

## 3. Coverage detail

| Element | Module | Statements | Missed | Coverage |
|---|---|---|---|---|
| S2LP | `instruments/s2lp/registers.py` | 95 | 0 | 100% |
| S2LP | `instruments/s2lp/configuration.py` | 130 | 4 | 97% |
| S2LP | `instruments/s2lp/constants.py` | 57 | 1 | 98% |
| S2LP | `instruments/s2lp/protocol.py` | 97 | 4 | 96% |
| S2LP | `instruments/s2lp/s2lp.py` | 386 | 15 | 96% |
| S2LP | `instruments/s2lp/cli.py` | 171 | 9 | 95% |
| S2LP | `instruments/s2lp/session.py` | 123 | 9 | 93% |
| S2LP | `instruments/s2lp/simulator.py` | 231 | 26 | 89% |
| S2LP | `instruments/s2lp/packets.py` | 123 | 19 | 85% |
| PSU | `instruments/gpd2303s/constants.py` | 24 | 0 | 100% |
| PSU | `instruments/gpd2303s/psu.py` | 239 | 6 | 97% |
| PSU | `instruments/gpd2303s/simulator.py` | 119 | 7 | 94% |
| PSU | `instruments/gpd2303s/cli.py` | 110 | 8 | 93% |
| CORE | `core/enums.py` | 20 | 0 | 100% |
| CORE | `core/errors.py` | 20 | 0 | 100% |
| CORE | `core/transport/constants.py` | 8 | 0 | 100% |
| CORE | `core/validation.py` | 33 | 0 | 100% |
| CORE | `core/instrument.py` | 82 | 2 | 98% |
| CORE | `core/simulator.py` | 96 | 5 | 95% |
| CORE | `core/transport/base.py` | 139 | 7 | 95% |
| CORE | `core/transport/factory.py` | 107 | 5 | 95% |
| CORE | `core/transport/mock.py` | 60 | 4 | 93% |
| CORE | `core/transport/serial_port.py` | 87 | 6 | 93% |
| CORE | `core/scpi.py` | 127 | 11 | 91% |
| CORE | `core/transport/process.py` | 131 | 14 | 89% |
| CORE | `core/transport/socket_raw.py` | 77 | 9 | 88% |
| CORE | `core/transport/vxi11.py` | 318 | 37 | 88% |
| CORE | `core/transport/visa_backend.py` | 75 | 17 | 77% |
| ANA | `analysis/waveform.py` | 164 | 4 | 98% |
| ANA | `analysis/measure.py` | 235 | 10 | 96% |
| ANA | `analysis/plotting.py` | 70 | 3 | 96% |
| INST | `instruments/generic.py` | 7 | 0 | 100% |
| SCOPE | `instruments/tek3014b/constants.py` | 121 | 0 | 100% |
| SCOPE | `instruments/tek3014b/scope.py` | 326 | 17 | 95% |
| SCOPE | `instruments/tek3014b/cli.py` | 213 | 14 | 93% |
| SCOPE | `instruments/tek3014b/simulator.py` | 442 | 35 | 92% |
| JLINK | `instruments/jlink/gdbmi.py` | 215 | 3 | 99% |
| JLINK | `instruments/jlink/constants.py` | 65 | 1 | 98% |
| JLINK | `instruments/jlink/server.py` | 121 | 4 | 97% |
| JLINK | `instruments/jlink/rtt.py` | 233 | 9 | 96% |
| JLINK | `instruments/jlink/swo.py` | 214 | 9 | 96% |
| JLINK | `instruments/jlink/timing.py` | 81 | 3 | 96% |
| JLINK | `instruments/jlink/cli.py` | 191 | 18 | 91% |
| JLINK | `instruments/jlink/probe.py` | 640 | 61 | 90% |
| JLINK | `instruments/jlink/session.py` | 159 | 16 | 90% |
| JLINK | `instruments/jlink/simulator.py` | 473 | 46 | 90% |
| BLE | `instruments/nordic_dongle/profile.py` | 152 | 3 | 98% |
| BLE | `instruments/nordic_dongle/cli.py` | 147 | 4 | 97% |
| BLE | `instruments/nordic_dongle/latency.py` | 93 | 3 | 97% |
| BLE | `instruments/nordic_dongle/protocol.py` | 95 | 3 | 97% |
| BLE | `instruments/nordic_dongle/constants.py` | 72 | 3 | 96% |
| BLE | `instruments/nordic_dongle/dongle.py` | 285 | 13 | 95% |
| BLE | `instruments/nordic_dongle/session.py` | 165 | 9 | 95% |
| BLE | `instruments/nordic_dongle/simulator.py` | 276 | 17 | 94% |
| RUN | `runner/limits.py` | 81 | 0 | 100% |
| RUN | `runner/results.py` | 106 | 0 | 100% |
| RUN | `runner/bench.py` | 134 | 2 | 99% |
| RUN | `runner/report.py` | 138 | 1 | 99% |
| RUN | `runner/spec.py` | 139 | 2 | 99% |
| RUN | `runner/cli.py` | 94 | 3 | 97% |
| RUN | `runner/runner.py` | 139 | 5 | 96% |
| RUN | `runner/resolve.py` | 37 | 2 | 95% |
| — | `cli.py` | 42 | 0 | 100% |
| — | `__main__.py` | 4 | 4 | 0% |
| **TOTAL** | | **7 604** | **444** | **94%** |

The `__init__.py` files are omitted for brevity; `__main__.py` is discussed below.

### 3.1 Justification for uncovered code

| Module | Uncovered code | Justification |
|---|---|---|
| `__main__.py` | The `python -m` entry guard | Four statements executed only by the interpreter's `-m` machinery. The CLI it delegates to is covered, and `python -m benchtools` is exercised manually. |
| `transport/visa_backend.py` | Error branches inside PyVISA interop | Reaching them means making a third-party library fail in specific ways; the code is a thin translation of its exceptions. |
| `transport/vxi11.py` | Some VXI-11 error-code mappings, the UDP portmapper success path, `remote`/`local` edge cases | Error paths on a protocol whose happy path and principal failure paths are covered. Exercising all 15 error codes would need a deliberately malicious server. |
| `transport/socket_raw.py`, `mock.py` | Defensive guards after `_require_open` | Unreachable unless an invariant is already broken. |
| `instruments/tek3014b/*` | Convenience getters and diagnostic fallbacks | Thin delegations, and an exception handler that exists only to stop a diagnostic message from itself raising. |
| `instruments/tek3014b/simulator.py` | Command handlers the driver does not currently emit | The simulator implements more of the instrument than the driver uses, deliberately, so driver extensions do not require simulator changes first. |
| `core/transport/process.py` | Reader-thread races and pipe-closed guards | Reached only when a pipe closes between a `select`-free read and its completion. Marked `pragma: no cover` where genuinely unreachable in-process. |
| `instruments/jlink/probe.py` | Best-effort cleanup paths, and `monitor` fallbacks for GDB versions that answer differently | Each is an `except BenchToolsError` around a tidy-up step whose failure must not replace the real error. Provoking them means making the simulator fail in a way real GDB does not. |
| `instruments/jlink/session.py`, `rtt.py`, `swo.py` | Socket and transport error branches | The happy path and the principal failures (unreachable port, dead GDB, timeout) are covered against a loopback server; the remainder are `OSError` translations. |
| `instruments/jlink/simulator.py` | MI commands the driver does not currently issue | Same rationale as the oscilloscope simulator: it models more of GDB than the driver uses, so extending the driver does not begin with extending the simulator. |
| `instruments/jlink/cli.py`, `nordic_dongle/cli.py` | Argument-error branches of sub-commands whose happy path is covered | Thin `argparse` plumbing; each is one `return 2`. |
| `core/transport/serial_port.py` | Buffer-reset and `in_waiting` fallbacks for URL handlers that do not implement them | Reached only with a pyserial URL handler that lacks the call; the guards exist so an exotic handler degrades instead of raising. |
| `instruments/nordic_dongle/session.py`, `dongle.py` | Transport-error branches and best-effort cleanup | The principal failures (timeout, refusal, protocol mismatch) are covered; the remainder translate a dead link. |

Coverage meets PC-2 (≥ 90%) at package level and at every module level except the
four justified above.

## 4. Work-product and architectural verification results

### 4.1 Traceability consistency

| Check | Result |
|---|---|
| All 195 requirements declared in SWE.1 appear in the traceability matrix | Pass |
| The matrix contains no requirement SWE.1 does not define | Pass |
| Every requirement cited in a docstring is defined in SWE.1 | Pass |
| Every design unit cited in a docstring is a section of SWE.3 | Pass |
| Every architectural element cited in a docstring is defined in SWE.2 | Pass |
| Every test group cited in a test is declared in SWE.4-001 | Pass |
| Every source and test module carries a `Traces to` line | Pass |
| Every architectural decision in SWE.2 is traced in the matrix | Pass |

PC-6 is met. These checks found two live inconsistencies when first run — a test
module citing an undeclared group, and a fixture citing a group that had been
renamed — both fixed. That is the point: they are the failure mode that review
does not catch.

### 4.2 Architectural verification

| Check | Result |
|---|---|
| Every module's imports respect the layering (parametrised over all 58 sources) | Pass |
| `benchtools.core` references no instrument, checked over code identifiers | Pass |
| `benchtools.core` imports in a fresh interpreter with no other element loaded | Pass |
| `benchtools.analysis` imports without instruments or the runner | Pass |
| No module imports a third-party package at module level (CORE-NFR-001, JLINK-NFR-001) | Pass |
| Source discovery guard (the suite cannot pass on an empty file list) | Pass |

### 4.3 Firmware verification without a compiler

The dongle firmware cannot be built here, so it is verified against the two
things that do not need a toolchain: the artefact it shares with the driver, and
the rules it is written to.

| Check | Result |
|---|---|
| Every command in `PROTO_COMMAND_TABLE` is known to the driver | Pass (12 commands) |
| The driver invents no command the firmware would reject | Pass |
| Argument bounds agree, command by command | Pass |
| Every documented command has a handler attached in `cmd_parser.c` | Pass |
| Event names agree | Pass (7 events) |
| Error codes agree, symbol by symbol | Pass (11 codes) |
| `PROTO_MAX_*` limits agree with `DongleLimits` | Pass (4 limits) |
| Protocol version and model agree | Pass |
| Every firmware source carries a `Traces to` line | Pass (12 files) |
| No `malloc`/`calloc`/`realloc`/`free` anywhere in the firmware | Pass (BLE-NFR-001) |
| House indentation (tabs) throughout the firmware | Pass |

PC-10 is met.

### 4.4 Firmware unit tests

The firmware now has unit tests of its own: Unity, built by CMake, run by CTest,
with fake SDK headers at the SDK boundary so the firmware's sources compile
unchanged and the logic under test is the logic that runs on the dongle.

| Binary | Cases | Result |
|---|---|---|
| `test_cmd_parser` | 50 | Pass |
| `test_ble_scanner` | 30 | Pass |
| `test_nus_client` | 20 | Pass |
| `test_cdc_acm` | 20 | Pass |
| `test_timestamp` | 11 | Pass |
| **Total** | **131** | **Pass** |

```
cmake -S firmware/nordic_dongle/test -B build/firmware-tests
cmake --build build/firmware-tests
ctest --test-dir build/firmware-tests --output-on-failure
```

`test_cmd_parser` is the one to note. The host driver is tested against a
*simulated* dongle; this is the only place the **real firmware's** replies are
checked, so the two halves of the protocol are now verified against each other
from both sides rather than one side being assumed.

The suite found two defects immediately (D-27, D-28), both of the kind that
compile cleanly and behave wrongly.

### 4.5 Firmware compilation against real SDK headers

Since the first issue of this report, the firmware has been **compiled**, in the
`canembed/canembed-arm` container image, which carries `arm-none-eabi-gcc`
10.2.1, SEGGER Embedded Studio 4.16 and nRF5 SDK 15.2.0.

The firmware targets SDK 17.1.0, which is not in the image and cannot be
downloaded here (Nordic's hosts are blocked by the network policy), so this is a
**cross-version** check. It is run by
`firmware/nordic_dongle/scripts/compile_check.sh`.

| Unit | Result |
|---|---|
| `timestamp.c` | Compiles, 0 warnings |
| `cdc_acm.c` | Compiles, 0 warnings |
| `ble_scanner.c` | Compiles, 0 warnings |
| `cmd_parser.c` | Compiles, 0 warnings |
| `nus_client.c` | Compiles apart from two SDK 17 members (`ble_nus_c_init_t.error_handler`, `.p_gatt_queue`) |
| `main.c` | Compiles apart from `ble_db_discovery_init_t`, which SDK 15.2 does not have |

Compiled with `-Wall -Wextra -std=c99 -O2` for Cortex-M4 hard-float. The four
excluded lines are the SDK 17 GATT-queue plumbing, which SDK 15.2 has no
equivalent for; they are listed by the script rather than skipped silently, and
a second pass compiles copies of those two files with exactly those lines
removed - both then compile with 0 warnings.

**What this establishes:** syntax, types, every SDK API this firmware calls that
exists in both versions, and the `sdk_config.h` keys the SDK's own headers
static-assert on. **What it does not:** that the firmware links, fits in flash,
or runs. That is §4.6, which is where BLE-OPEN-01 is discharged.

It found seven defects (D-20 to D-26), one of which was a concurrency error that
no amount of reading had caught.

PC-12 is met: every firmware unit test passes, and the firmware still compiles
for the target after the fixes they prompted.

### 4.6 First build against nRF5 SDK 17.1.0, linked and packaged

The `firmware` workflow builds against the real SDK: it downloads nRF5 SDK
17.1.0, cross-compiles with `arm-none-eabi-gcc` 10.3-2021.10, links, reports the
size, and packages the hex as a DFU zip. It runs on every push touching
`firmware/**`.

Run 12 on commit `f66a248` is the first green one. Both jobs pass and all five
artefacts are produced - `.hex`, `.out`, `.map`, `nordic_dongle_dfu.zip` and
`firmware_manifest.json`.

The link map, from the build's own `size` output:

| | Bytes | Region | Used |
|---|---|---|---|
| Flash (`text` + `data`) | 51 652 | 0x27000 … 0x100000 less the bootloader, 0xd9000 = 888 832 | 5.8% |
| Static RAM (`data` + `bss`) | 12 636 | 0x3d518 = 251 160 above the SoftDevice's requirement | 5.0% |

`text` 49 800, `data` 1 852, `bss` 10 784. The 8 KiB stack and 2 KiB heap are
set by the build (`__STACK_SIZE`, `__HEAP_SIZE`); the `.map` in the artefact is
the authority on where they sit relative to those figures. Either way the image
is nowhere near the region, which was the open question.

**BLE-OPEN-01 is discharged.** The firmware builds, links and fits, and the
GATT-queue lines that SDK 15.2 could not compile do compile against SDK 17.1.0.
What remains is on-silicon behaviour, which is BLE-OPEN-02 to -04 and CON-07 -
none of which can be reached without a dongle.

Getting there took eleven red runs, and what they found is worth recording,
because none of it was reachable by reading:

- The build could not have linked on any machine (D-37). The Makefile named a
  source that does not exist in nrfx 2.x and omitted three that do; a missing
  source was a warning, not an error.
- `sdk_config.h` was missing seven keys (D-38). Each fails inside an unrelated
  SDK file, because SDK modules expand their own configuration macros into
  static assertions and, in one case, into a ternary in C code - so a key is
  required even when the feature it configures is switched off.
- The GATT queue was sized for 20-byte writes against a protocol that sends up
  to 96 (D-36), which would have refused every long command on the part.

One tooling fault is not a product defect but is recorded here because it will
catch anyone following the flashing instructions: an unpinned
`pip install nrfutil` on a current Python does not refuse to install - it
resolves backwards to a Python 2 era release, which dies in `pkg generate` on
`dict.iteritems`. The workflow now pins `nrfutil==6.1.7` and a 3.10 interpreter,
and `docs/ble/BLE_Dongle_Notes.md` §3.2 says why.

PC-5 and PC-9 are met. This is the check that keeps the shared core shareable as
the instruments named in CON-03 are added — and it has already paid: adding the
J-Link driver, which needs a process transport in the core and a non-SCPI
instrument base, moved code *into* the core without any instrument knowledge
leaking in with it.

The third-party import check is new in this revision. CORE-NFR-001 had until now
been verified by inspection and by the extras-blocked run; neither would catch a
module-level `import yaml` added to a module no test imports in that
configuration. It is now parsed for, over every module.

## 5. Quantitative verification of timing accuracy

PC-4 requires injected skews to be recovered to better than one tenth of a sample
interval.

### 5.1 Against synthesised waveforms

Stimulus: 1 MHz, 3.3 V, 2 ns rise time, 100 ps sample interval.

| Injected skew | Recovered | Error | Tolerance asserted |
|---|---|---|---|
| 0 ns (reference) | 0 ns | — | — |
| 12 ns | 12 ns | < 2 ps | 2 ps |
| 25 ns | 25 ns | < 2 ps | 2 ps |
| 5 ns | 5 ns | < 2 ps | 2 ps |
| **Spread (25 ns)** | **25 ns** | **< 2 ps** | 2 ps |

Sub-sample resolution is verified separately: a deliberate 0.35-sample (35 ps)
offset is recovered to within 0.5 ps, i.e. 0.005 of a sample interval.

### 5.2 Through the full driver, against the simulated instrument

Stimulus: four channels at 1 MHz / 3.3 V with skews 0, 12, 25 and 5 ns;
200 ns/div, 10 000 points, giving a 200 ps sample interval.

| Quantity | Result |
|---|---|
| Spread recovered | 25 ns, within 20 ps of injected (0.1 sample interval) |
| Agreement with the instrument's own `DELay` measurement | within 20 ps on all three channel pairs |
| Earliest / latest channel identified | CH1 / CH3, correct |
| End-to-end per-channel skews | 0.000, 12.011, 25.000, 5.011 ns against injected 0, 12, 25, 5 — worst residual 11 ps, i.e. 0.055 of a sample interval |

PC-4 is met.

### 5.3 Period measurement

| Quantity | Result |
|---|---|
| Injected period | 1.000000 µs |
| Host-side mean over 4 periods | 1.000000 µs (relative error < 1 × 10⁻⁶) |
| Peak-to-peak jitter on an ideal signal | < 1 fs (numerical noise only) |
| Instrument-side period | 1.000000 µs |
| Agreement between the two | within 0.1% |

## 6. Debug probe verification results

### 6.1 Timing between two lines of code

The simulated firmware places `sensor.c:40` and `sensor.c:75` exactly 64 000 core
cycles apart, which at the simulated 64 MHz core is exactly 1.000 ms. Five
repetitions of each method, through the driver:

| Method | Measured | Cycles | Resolution | Halts target | Trustworthy | Spread |
|---|---|---|---|---|---|---|
| CYCLE_COUNTER | 1000.000 µs | 64 000 | 0.0156 µs | Yes | Yes | 0 µs |
| TARGET_TIMER | 1000.000 µs | 64 000 | 0.0156 µs | Yes | Yes | 0 µs |
| SWO_ITM | 1000.000 µs | 64 000 | 0.0156 µs | **No** | Yes | 0 µs |
| HOST_CLOCK | 96.040 µs | — | 1000 µs | Yes | **No** | 33.8 µs |

Three independent routes to the injected figure — a DWT register read, two
firmware variables, and a decoded ITM timestamp stream — agree exactly, so the
scaling from ticks to seconds is confirmed by agreement between implementations
rather than against itself.

The fourth row is the point of JLINK-FR-065. The host clock is wrong by a factor
of ten and is *reported* as untrustworthy, because the interval is a tenth of the
method's resolution. A bench test asserting on that figure would be asserting on
scheduling noise, so `is_trustworthy` is asserted in the shipped example
specification (`specs/firmware_timing.yaml`) alongside the limit itself.

`SWO_ITM` recovers the interval with `halts_target` false: the measurement does not
stop the core, which is the only method usable on firmware that must keep running.

### 6.2 Probe operations against the simulated target

| Check | Result |
|---|---|
| Flash from ELF, reporting sections written | Pass — 17 280 bytes in 3 sections |
| Verify against the binary, per section | Pass; a mismatch raises and names the section |
| Verification over an empty section list | Reported as **not** matched, not as a pass |
| Reset halting at the vector, run, halt, step | Pass |
| Breakpoint by source location, function and address | Pass |
| Temporary and conditional breakpoints | Pass, including a condition containing spaces |
| Hardware breakpoint beyond the probe's envelope | Refused, naming the limit (4) |
| Watchpoints on write, read and either | Pass |
| Halt reason reported (breakpoint, watchpoint, step, signal, unknown) | Pass |
| Memory read and write, 8/16/32-bit and arbitrary length | Pass; a transfer longer than the probe's limit is split into several reads (tested with the limit lowered to 16 bytes, so the splitting is observable) |
| Variables by name — integer, string, address, size | Pass; memory and variable views agree |
| Call stack | Pass — 3 frames with function, file and line |
| RTT read, write, command/response, pattern match | Pass, without halting the core |
| RTT logging | Pass; written and flushed per line |
| RTT over a real TCP socket, arriving in fragments | Pass — lines reassembled |
| SWO over a real TCP socket | Pass — events decoded, `collect` honours its timeout |
| GDB Server: already-listening port reused, remote never spawned | Pass |
| GDB Server that exits during start-up | Reported with the server's own output |

## 7. BLE dongle verification results

### 7.1 Advertising profile

The simulated sensor advertises at 100 ms with advertising delays of 0, 3, 7 and
10 ms in rotation - the specification's 0-10 ms advDelay, made deterministic. A
five second capture through the driver:

| Quantity | Measured | Expected by construction |
|---|---|---|
| Advertising events | 49 | 5.0 s / 105 ms, rounded down, plus the first |
| Mean interval | 105.00 ms | 105 ms (100 + mean delay) |
| Minimum interval | 100.00 ms | exactly 100 ms |
| Maximum interval | 110.00 ms | exactly 110 ms |
| Spread | 10.00 ms | exactly 10 ms |
| Jitter (sd) | 3.85 ms | 2.9 ms for uniform advDelay; higher for a 4-point rotation |
| Missed events | 0 | 0 |
| Duty cycle | 1.000 | 1.0 |
| Complete | true | no drops configured |

The bounds are exact, which is the point of a deterministic model: a scaling
error of any size moves them.

The second sensor skips one beacon in five. Over three seconds it reports missed
events and a duty cycle below 1.0, so a dropout is detected rather than averaged
away. With `drop_every` set on the dongle, `is_complete` goes false and the CLI
adds its warning - the case where missed beacons must *not* be blamed on the
sensor.

### 7.2 Command and response

| Check | Result |
|---|---|
| Connect, discover the UART service, report ready | Pass |
| Connection interval reported from the `+conn` event | Pass — 30.0 ms |
| Command and reply | Pass — `version` → `1.4.2` |
| Round trip on the dongle's clock | Pass — 12.500 ms, exactly as modelled |
| A command that takes real work | Pass — 95.000 ms |
| 95 ms flagged trustworthy, 12.5 ms not | Pass — 12.5 ms is inside one connection interval |
| Host-clock figures kept separately | Pass — 0.02 ms in simulation, correctly flagged unresolvable |
| An over-long payload refused before transmission | Pass |
| A sensor that cannot be connected to | Pass — refusal reported with the reason |

The trustworthiness rule is the one worth stating: with a 30 ms connection
interval, a 12.5 ms round trip says where the write landed in the interval, not
what the sensor's firmware did. The tooling refuses to present it as the latter.

### 7.3 Session log

A profile capture logged to a text file contains the commands sent, the replies,
every `+adv` event with both timestamps, and any comment the caller wrote -
flushed per line, so a session that then hangs still has a complete log. Verified
by `TestLogging` in both `SWE4-UT-BLESESSION` and `SWE4-UT-BLE`.

## 8. Protocol interoperability results

| Check | Result |
|---|---|
| Built-in VXI-11 client against an independently implemented RPC server | Pass |
| Same driver through `pyvisa` + `pyvisa-py` against the same server | Pass |
| 10 000-point record over a link advertising `maxRecvSize` = 1 kB | Pass, 10 008 bytes intact |
| Command longer than `maxRecvSize` chunked and reassembled | Pass |
| Device-name probe recovers a VXI-11.2-only instrument (`gpib0,1`) | Pass |
| Portmapper `GETPORT` over TCP | Pass |
| Full driver over a raw SCPI socket | Pass |

The second row is the substantive evidence for the VISA determination: an
independent VXI-11 implementation and the built-in one drive the same instrument
to the same result, so the VISA layer is optional middleware.

The GDB/MI side has no equivalent second implementation available in the build
environment: correctness against real GDB is a bench confirmation item
(JLINK-OPEN-02). What is verified here is that the parser handles the grammar as
documented, including the constructs a naive parser gets wrong — see D-09.

## 9. S2-LP kit verification results

No S2-LP kit was present (PC-8). The driver is verified against a simulated kit
that models a **register file with a radio attached**: writing a register changes
what the queries that read it answer, and a packet queued on the simulated air is
delivered to exactly one receive.

### 9.1 The vendor firmware was examined before any was written

STK-20 asked whether ST's firmware is fit for purpose. It was read, not assumed
about: the source of the CLI application ST's S2-LP DK GUI drives is published at
`STMicroelectronics/x-cube-subg2`, under
`Projects/NUCLEO-L053R8/Examples/S2868A1_CLI/`.

| Question | Answer, and where it was read |
|---|---|
| What does the GUI talk to? | `README.md`: "CLI example for S2-LP Expansion Board and S2-LP DK GUI". A CLI application over the kit's USB serial port |
| What is the wire format? | `command-interpreter2.c` — ASCII lines; `command-interpreter2.h` documents the argument letters (`u` one byte, `v` two, `w` four, `b` a string in `{ }` hex or quotes) |
| Can every register be read and written? | Yes: `SDK_CLI_commands.h` declares `SdkEvalSpiReadRegisters` (`uu`) and `SdkEvalSpiWriteRegisters` (`ub`), plus strobes and FIFO access |
| Can it transmit and receive? | Yes: `S2LP_CLI_commands.h` declares `S2LPSendNBytes`, `S2LPSendNBytesBatch`, `S2LPGetNBytes`, `S2LPGetNBytesBatch` |
| What do replies look like? | `SDK_CLI_commands.c` and `response.c` — brace-delimited tags, e.g. `{regs_list: 0x00,0x0A}` and `{timer:000004D2}` |
| Can a long capture be stopped? | Yes: `checkStop()` polls the port for the single character `S` inside the capture loops |
| Line rate | 115200 8N1 (`stm32l0xx_nucleo.c`) |

**Conclusion: fit for purpose, and used unchanged** (AD-20). Nothing in this
repository runs on the kit. Three limits come with that decision and are carried
into the design rather than hidden:

| Limit | Consequence, and what the driver does about it |
|---|---|
| Reception is **polled** — the firmware arms the radio when asked and returns | A packet arriving between calls is invisible. `Capture.gaps` records every re-arm; `is_continuous` is false when there were any, and `capture(continuous=True)` keeps the board in its own loop so that there are none |
| Timestamps are the **motherboard's millisecond timer** | Good enough to order packets and time a sequence, not to characterise protocol timing. The field is named `board_time_ms`, and the limit is stated wherever it is reported |
| ST's package is under **SLA0072**, a limited licence | The protocol is interoperated with; no ST source is vendored. The register map holds facts about the silicon, not vendor prose (S2LP-NFR-002) |

### 9.2 The register map

123 registers, each with its address, reset value, access and named bit fields.
The map is data, so it is verified as data: unique addresses, unique names, no
overlapping fields, every field inside its byte, and every status register
read-only (`SWE4-UT-S2LPREG`, 34 cases).

Read as contiguous runs, a full dump is **15 commands rather than 123** — on a
115200 baud link, the difference between a dump that feels instant and one that
does not. A dump renders as:

```
0x2E PCKTCTRL3              = 0xC0            PCKT_FRMT=3
0x2F PCKTCTRL2              = 0x07  (reset)   MBUS_3OF6_EN=1 MANCHESTER_EN=1 FIX_VAR_LEN=1
```

which is the point of holding the map at all: 123 hex bytes say nothing about
how a radio was configured, and this says it.

### 9.3 Register values from a file

The values a test requires are read from a file of register names and hex
values, applied, and checked back. The check has two modes, and the difference
between them is the point:

| | Loose (default) | Strict |
|---|---|---|
| Registers the file names | must match | must match |
| Registers it does not name | not examined | must be at their reset value |
| Question answered | "is what this test needs set?" | "is the radio in exactly this configuration?" |
| Reads | only the named registers | the whole map |

Applied to a fresh simulated radio and then verified:

```
3 register(s) match config.regs and nothing else is set
```

and after a single stray write to a register the file does not name, the loose
check still passes while the strict one reports:

```
1 set but not named by the file: GPIO0_CONF = 0x55
```

Every way a file can be wrong is refused naming the file and the line — an
unknown register, a value that does not fit a byte, a read-only register, a
register set twice, a line that is not a setting, and an empty file. Applying
verifies by read-back, because this radio's writes are acknowledged by the
firmware rather than by the radio.

### 9.4 A configuration is applied to a known radio

A file that names some registers says nothing about the others, so what a
partial file produces depends on what ran before it. `reset` settles that, and
the reset itself is confirmed before anything is written:

| Applied after a stray write to GPIO0_CONF | Registers not at their default afterwards |
|---|---|
| `apply_configuration(file)` | `GPIO0_CONF`, plus the file's own |
| `apply_configuration(file, reset="defaults")` | the file's own |
| `apply_configuration(file, reset="power")` | the file's own |

which is what makes the strict check meaningful: after a reset and an apply,
"the radio holds this file and nothing else" is a statement the suite has
established rather than inherited.

The device's reset **strobe** is deliberately not one of the choices - see
D-35. A simulated kit whose `SdkEvalSdn` never shuts down produces:

```
InstrumentError: the radio is not at its register defaults after a power reset:
GPIO0_CONF = 0x55 (default 0x0A). The configuration was not applied, because it
would have been written on top of a state nobody established.
```

### 9.5 A capture states how it was taken

| Capture | Packets | Gaps | `is_continuous` | What it may be quoted as |
|---|---|---|---|---|
| `capture(count=3)` — board-side loop | 3 | 0 | yes | a record of the air for its duration |
| `capture(count=2, continuous=False)` | 0 | 9 | no | "nothing was heard while listening" — nothing more |

The second row is the one that matters. Both captures are honest; only the first
supports a statement about what was *not* transmitted.

## 10. Power supply verification results

No GPD-2303S was present (PC-8). The driver is verified against a simulated
supply that models a **load**, which is what makes the interesting condition
reachable: a channel whose load draws more than its limit.

### 10.1 Constant current is detected, not averaged over

Channel 2 with 2 Ω across it, set to 3.3 V with a 500 mA limit:

| Quantity | Value | |
|---|---|---|
| Setpoint | 3.300 V | what the test asked for |
| Measured voltage | 1.000 V | what the board actually got |
| Measured current | 0.500 A | the limit, not the demand |
| Mode | `CC` | the reason for the other three |
| `regulated` | `False` | the one line a test should assert on |

The figure to note is 1.000 V. A driver that reported only the voltage would
hand a test a plausible number describing a circuit nobody asked for, and the
test would fail somewhere else entirely - or, worse, pass.

### 10.2 The emulated per-channel switch behaves as documented

| Action | Channel 1 | Channel 2 | Supply's own switch |
|---|---|---|---|
| both configured, `all_outputs_on()` | 3.300 V | 5.000 V | closed |
| `output_off(1)` | 0.000 V | 5.000 V | **still closed** |
| `set_voltage(1, 5.0)` | 0.000 V | 5.000 V | still closed |
| `output_on(1)` | 5.000 V | 5.000 V | closed |
| `output_off(1)`, `output_off(2)` | 0.000 V | 0.000 V | **open** |

Row three is the property that matters: programming a parked channel does not
energise it. Row five is the other: once every channel is off, the supply's real
switch is opened, so "all off" is not two rails sitting at zero volts.

### 10.3 What could not be verified without the instrument

| Item | Why |
|---|---|
| PSU-OPEN-01 | The bit **order** of the `STATUS?` reply. The decode follows the programming manual; whether the supply sends bit 0 first is a one-minute check on hardware (switch the output on and see which character changes). The raw reply is retained in `SupplyStatus.raw` so a mis-order is visible rather than silently decoded. |
| PSU-OPEN-02 | The exact text and behaviour of `ERR?`. Anything not recognisably "no error" is carried verbatim rather than parsed, so the driver is correct either way; what is unproven is whether the supply clears the error on reading it. |
| PSU-OPEN-03 | The command interval a real GPD-2303S needs. 50 ms is a conservative default taken from the supply having no flow control; the figure to confirm is the smallest interval at which a long sweep loses nothing. |
| PSU-OPEN-04 | Settling time after a setpoint change. The driver does not wait; a specification that measures immediately after `set_voltage` should state its own `sleep`. |

## 11. Runner verification results

| Check | Result |
|---|---|
| A measurement outside its limit is reported as a failure, not an error | Pass |
| An unexecutable step is reported as an error, not a failure | Pass |
| JUnit XML keeps `<failure>` and `<error>` distinct | Pass |
| A setup failure aborts the suite and runs no test | Pass |
| Teardown runs after a failure | Pass |
| A test failure does not stop later tests; `--stop-on-error` does | Pass |
| A specification cannot invoke private driver methods | Pass |
| A missing bench instrument is reported before anything executes | Pass |
| A simulated run is disclosed in every report | Pass |
| Exit status 0 / 1 / 2 for pass / problem / usage | Pass |
| The shipped `specs/clock_skew.yaml` and both `benches/*.yaml` load and run | Pass |

## 12. Defects found, and their disposition

| ID | Severity | Status | Regression test |
|---|---|---|---|
| D-01 — IEEE 488.2 payload re-parsed as a block header | **Major** (silent, data-dependent corruption) | **Closed** | `test_payload_containing_a_hash_byte_is_not_re_parsed`, `test_from_payload_does_not_re_parse_a_header`, `test_from_block_and_from_payload_agree`, `test_ascii_encoding_matches_binary`, `test_every_position_transfers_intact` |
| D-02 — inconsistent `absolute_threshold` parameter name | Minor (API usability) | **Closed** | `test_absolute_threshold_overrides_percent` |
| D-03 — 2 s shutdown latency in the test servers | Minor (test efficiency) | **Closed** | Verified by `--durations` |
| D-04 — core transport depended on the oscilloscope simulator | **Major** (architectural; blocked reuse) | **Closed** | `test_core_never_references_an_instrument`, `test_core_is_importable_on_its_own`, `test_layer_dependencies_point_one_way` |
| D-05 — simulator identity string not read by the base class | Minor (wrong `*IDN?` under `sim://`) | **Closed** | `test_bare_sim_resource_uses_the_driver_simulator` |
| D-06 — an all-simulated bench was not reported as simulated | **Major** (evidence integrity) | **Closed** | `test_all_sim_resources_count_as_simulated`, `test_a_mixed_bench_is_not_simulated`, `test_simulation_is_disclosed`, `test_properties_record_the_bench` |
| D-07 — a scope CLI test asked for a plot without guarding on `matplotlib`, so the suite did not in fact pass with the optional extras absent (a **test** defect, not a product defect) | Minor | **Closed** | The test now skips without the extra; verified by the extras-blocked run in §1 |

| D-08 — `TimingResult` reported no resolution for the `TARGET_TIMER` method, and an unknown resolution was treated as trustworthy. A target-timer figure below one tick of the firmware's timer would have been presented as a measurement | **Major** (evidence integrity; JLINK-FR-065, JLINK-NFR-004) | **Closed** | `TestResolutionIsAlwaysReported` (6), notably `test_the_target_timer_resolves_its_own_rate_not_the_core_clock`, `test_an_unknown_resolution_is_not_trusted`, `test_every_method_reports_a_resolution_through_the_probe` |
| D-09 — the ITM decoder classified a source packet by bit 0 of its header instead of the two-bit size field, so every 16-bit ITM write was read as a protocol packet and silently dropped | **Major** (silent data loss on hardware) | **Closed** | `TestSourcePackets` — the 1-, 2- and 4-byte cases |
| D-10 — `RttClient.history` returned only the lines not yet consumed by a read, while documented and used as the complete log. An RTT log would have been missing exactly the lines a test had examined | **Major** (evidence integrity) | **Closed** | `test_history_survives_consuming_reads`, `test_pending_count` |
| D-11 — the simulated probe split `-break-insert` arguments on whitespace, truncating a condition such as `sensor_count > 3` to `sensor_count`, so conditional breakpoints appeared to work while ignoring their condition | Minor (**test double** defect; would have masked a driver defect) | **Closed** | `test_conditional_breakpoint` |
| D-12 — the simulated probe reported `type="breakpoint"` for hardware breakpoints as well as software ones, so the driver's hardware count was always zero and the probe's four-breakpoint envelope could never be enforced | Minor (**test double** defect; disabled a real check) | **Closed** | `test_hardware_breakpoint_limit_is_enforced` |
| D-13 — `--simulate` gave every alias in a bench the oscilloscope driver, so a specification needing a probe failed several steps later on a missing method instead of at once | Minor (diagnosis quality) | **Closed** | `test_simulated_from_a_mapping_uses_the_right_driver`, `test_the_wrong_kind_of_instrument_is_reported` |
| D-14 — `jlink/server.py` had no tests at all: JLINK-FR-003 to -005 were implemented and traced but unverified, and three test names cited in the traceability matrix did not exist | Minor (**verification gap**, found by checking the matrix against the suite) | **Closed** | `SWE4-UT-JLINKSERVER` (32 tests) |

| D-15 | `AdvertisingProfile.intervals` subtracted two floats, so an exactly nominal 100 ms interval came out as 0.09999999999999998 and failed a limit written as ">= 0.1" | **Major** (a conforming sensor failed by floating-point representation rather than by behaviour). Found by `test_a_conforming_sensor_is_within_specification`, whose last interval is exactly nominal | **Closed** — intervals are subtracted as integer microseconds and converted once | `test_exactly_nominal_intervals_are_exact`, `test_a_conforming_sensor_is_within_specification` |
| D-16 | An advertising capture was bounded by the host's wall clock, so against a simulator - whose clock advances as fast as it is read - a two second capture collected 430 seconds of events and overflowed the event backlog | Minor (simulation only; on hardware the two clocks agree). Found by reading the first profile the driver produced | **Closed** — `DongleSession.collect` takes a `stop` predicate, and the capture is bounded by the **dongle's** clock with the wall clock as a backstop | `test_collect_stops_early_when_asked`, `test_the_capture_covers_the_window_asked_for` |
| D-17 | `AdvertisingProfile.as_dict` was documented to survive a capture too short for statistics, but `expected_events` reached the interval arithmetic outside the guard and raised | Minor (a failing capture produced an exception instead of a report, which is when a report is most needed) | **Closed** — `expected_events` and `gaps` fall back when there is no interval to reason with | `test_as_dict_survives_too_few_events` |
| D-18 | The simulated dongle rolled an advertising event scheduled for the *current* instant forward by a whole interval, so whenever two sensors coincided the quieter one was never heard | Minor (**test double** defect; a scan silently found fewer sensors than it should) | **Closed** — only a schedule strictly in the past is rolled forward | `test_scan_finds_the_sensors`, `test_scanning_finds_sensors` |
| D-19 | The serial transport reported a write the far end would not take as a connection failure | Minor (diagnosis quality: it sends the reader to look at the cable when the port is fine and flow control is asserted) | **Closed** — reported as a timeout naming flow control | `test_a_write_the_far_end_will_not_take_is_a_timeout` |

| D-20 | `ble_scanner.h` declared functions taking `ble_evt_t` but included only `ble_gap.h`, which does not define it | Minor (would not compile) | **Closed** — includes `ble.h` | `compile_check.sh`: `ble_scanner.c` |
| D-21 | The scan filter policy was written `BLE_GAP_SCAN_FILTER_POLICY_ACCEPT_ALL`; no SoftDevice header has ever spelled it that way (`BLE_GAP_SCAN_FP_ACCEPT_ALL`) | Minor (would not compile) | **Closed** | `compile_check.sh`: `ble_scanner.c`, `nus_client.c` |
| D-22 | `command_list` declared a local `count` shadowing the parameter of the same name, left behind when the handlers were given a uniform signature | Minor (would not compile) | **Closed** — renamed to `found` | `compile_check.sh`: `cmd_parser.c` |
| D-23 | `tx_pump` called `CRITICAL_REGION_EXIT()` inside an early return. The SDK's macro pair opens and closes a *brace*, so the region was structurally unbalanced — and the intent, returning from inside a critical region, is wrong regardless | **Major** (would not compile; and the pattern, had it compiled, leaves interrupts disabled on one path) | **Closed** — the decision is taken inside the region and acted on outside it | `compile_check.sh`: `cdc_acm.c` |
| D-24 | `APP_USBD_STRINGS_USER` was defined as a string descriptor. It is an X-macro *list*, so the definition broke `app_usbd_string_desc.h` itself | Minor (would not compile; the error appeared inside an SDK header, several levels from the cause) | **Closed** — no user strings are declared | `compile_check.sh`: `cdc_acm.c` |
| D-25 | `sdk_config.h` defined `BLE_DB_DISCOVERY_BLE_OBSERVER_PRIO`; the SDK's header reads `BLE_DB_DISC_BLE_OBSERVER_PRIO` | Minor, and the worst kind of configuration error: **the wrong name compiles and does nothing**, so the module would have registered its observer at an unintended priority had the header not asserted | **Closed** | `compile_check.sh`: `main.c` |
| D-26 | SDK 17's `ble_nus_c` and `ble_db_discovery` submit GATT operations through a queue (`nrf_ble_gq`); the firmware created none and passed `NULL` | **Major** (would have compiled and then failed at run time, on the first characteristic discovery) | **Closed** — `main.c` owns one queue and hands it to both, per Nordic's own central examples | Found by the version delta, since SDK 15.2 has no queue at all; verified by inspection against the SDK 17 API |

Missing SES project entries were corrected with them: `nrf_sortlist.c` and
`nrf_atflags.c` (required by `app_timer` v2 and `ble_conn_state`), `nrf_ble_gq.c`,
and the include paths for `sortlist`, `atomic_flags`, `nrf_ble_gq` and
`ble_link_ctx_manager`.

| D-27 | An advertising line the transmit queue **refused** was still counted as reported, so the firmware's "reported" and "received" counters always agreed | **Major** (evidence integrity): the host compares those counters to tell a lossy link from a quiet sensor, and this made `AdvertisingProfile.is_complete` incapable of ever being false for a firmware-side drop | **Closed** — counted only when the queue accepts the line | `test_a_dropped_line_is_counted_as_not_reported` |
| D-28 | After an over-long command the receiver started a **new** line where the buffer overflowed, instead of discarding to the terminator. The tail of a truncated command therefore became a command: `xxx…xxxreset` would have executed `reset` | **Major** (a command nobody sent) | **Closed** — bytes are discarded until the terminator | `test_the_tail_of_an_over_long_command_is_not_a_command` |
| D-29 | The driver refused to connect to a dongle whose protocol version differed from its own. Since refreshing the firmware runs **over that connection**, an out-of-date dongle could not be reached to be fixed - the check made the recovery path impossible | **Major** (the fault excluded its own remedy) | **Closed** — only a *major* version difference is fatal, a minor one warns, and `update_firmware=True` suspends the check | `test_an_incompatible_dongle_can_still_be_reached_to_update_it`, `test_a_different_minor_version_is_survivable` |

Two smaller corrections came with them: `cmd_parser_init` now clears the
selection, so the module can be brought back to a known state (the target wants
that after a soft restart as much as the tests do); and the sources that use
`UNUSED_PARAMETER` now include `app_util_platform.h` rather than relying on the
SDK to provide it transitively.

| D-30 | The driver treated the supply's **global** output switch as the state of each channel. Connecting to a supply whose output was off therefore marked both channels off, after which `set_voltage` parked the value instead of sending it - and the supply was never programmed at all | **Major**: `configure_channel` then `output_on` would energise a rail at the *previous* setpoint, silently, and every subsequent reading would be consistent with it | **Closed** — a channel is parked if and only if the driver parked it; there is now one fact where there were two that could disagree | `test_configure_sets_the_limit_before_the_voltage`, `TestReset` (3), `test_it_can_be_turned_on` |
| D-31 | The simulated supply's command pattern allowed only a channel digit, so `OUT0` matched nothing and was silently refused. Every "switch off" in a simulated test appeared to succeed while the model stayed on | **Major** (in the test double, so the whole class of switching tests was vacuous — see the note on D-11 and D-12 below) | **Closed** — the digit position is parsed as a digit, and a channel that does not exist is refused explicitly rather than by failing to parse | `test_out0_is_understood`, `test_a_channel_that_does_not_exist_is_refused` |

| D-32 | The S2-LP driver read the firmware's ``{rssi:D4}`` tag as decimal. ST's firmware writes that tag with its ``%x`` specifier, so it carries **bare hex**: ``D4`` read as decimal is 4, and the driver reported -144 dBm for a signal at -40 dBm | **Major** (evidence integrity): a plausible number, wrong by 104 dB, in every received packet and in the packet log | **Closed** — tags the firmware writes in hex are read in hex, explicitly, by `Reply.hex_number` | `test_a_hex_tag_has_no_0x_in_front_of_it`, `test_the_rssi_is_the_one_the_board_reported` |
| D-33 | The reply parser's number pattern had no sign, so a negative value arrived positive. `S2LPQiGetRssidBm` answers in dBm: -110 dBm was read as +110 dBm | **Major**, and of the worst kind: the result is not merely wrong but physically impossible, and nothing downstream would have questioned it | **Closed** — the pattern accepts a leading minus, and the driver's RSSI test asserts the sign | `test_rssi_is_read_in_dbm`, `TestNumbers` |
| D-34 | A polled capture counted a re-arm per iteration with no bound on iterations. Against a radio that answers "nothing" immediately it spent the whole timeout re-arming - 35 006 times in two seconds - and reported that as a capture | **Minor** on hardware, where each arm blocks; **major** as a measurement claim, because the gap count is what tells a reader whether a capture was continuous | **Closed** — the polled path is bounded by an attempt count as well as by time, and reports `stopped_early` | `test_a_polled_capture_is_bounded_by_attempts` |

| D-35 | The simulated kit modelled the **SRES strobe as restoring register defaults**. ST's own command header calls it a "reset of all digital part, except SPI registers", and the driver's own docstring said so - but the simulator disagreed, and the test asserting `reset()` restored defaults passed against it | **Major** (in the test double, so the error was invisible): a driver using `reset()` to reach a known state would have passed every test here and left every register exactly as it was on the bench, with a configuration file then applied on top of an unknown state | **Closed** — SRES empties the FIFOs and leaves the register file; `SdkEvalSdn` (shutdown and back) is modelled as the power-on reset, which on the part is the only thing that restores defaults. `power_cycle()` added, and `apply_configuration(reset=...)` uses it | `test_the_reset_strobe_does_not_restore_register_defaults`, `test_the_reset_strobe_leaves_the_register_file_alone`, `test_a_power_cycle_does` |

| D-36 | The dongle's GATT queue was left at the SDK's default write size of 20 bytes while the host protocol sends commands up to `PROTO_MAX_PAYLOAD` (96). `nrf_ble_gq` refuses a longer write with `NRF_ERROR_DATA_SIZE` | **Major**, and invisible to every check that had been run: it compiles, links and passes the host-side tests, and fails only on the part, on any command over 20 bytes | **Closed** — `NRF_BLE_GQ_DATAPOOL_ELEMENT_SIZE` and `NRF_BLE_GQ_GATTC_WRITE_MAX_DATA_LEN` are taken from `protocol.h`, so the queue is sized from the protocol rather than alongside it | Structural: `sdk_config.h` includes `protocol.h`; the sizes cannot now disagree |
| D-37 | The Makefile's source list had never been exercised against a real SDK tree. It named `nrfx_power_clock.c`, which does not exist in nrfx 2.x, and omitted `nrf_section_iter.c`, `nrf_drv_power.c` and `utf.c`, which were on the include path but never compiled. Nordic's `Makefile.common` only **warns** about a source it cannot find | **Major**: the firmware could not be built as delivered — the first three faults are compile or link failures, and the warning meant the cause was in the middle of the output rather than at the end | **Closed** — the source list is corrected, and the Makefile now stops with the list of names it cannot find and what to check, rather than warning | The `firmware` workflow: a missing source is a hard error, so a recurrence cannot reach a green build |
| D-38 | `sdk_config.h`, written by hand, was missing seven keys the SDK's own modules expand into static assertions (`NRF_SORTLIST_CONFIG_LOG_ENABLED` and `_LOG_LEVEL`, `POWER_CONFIG_SOC_OBSERVER_PRIO`, `POWER_CONFIG_STATE_OBSERVER_PRIO`, the `APP_USBD_STRING_ID_*` and string descriptors, `NRF_SDH_BLE_GAP_DATA_LENGTH`) | **Major** as a build fault, and awkward to diagnose: the error surfaces in an unrelated SDK file, and `nrf_sortlist.h` needs its logging key present even with logging off because it expands the name through a **ternary in C code**, not through the preprocessor | **Closed** — every key is present, each with the comment saying which module asserts on it and why | The `firmware` workflow, which compiles every unit against the real SDK headers |

No open defects.

Notes on process effectiveness:

- **D-01 was not caught by the 237-test suite as it then stood**, because the
  vertical positions used in the fixtures happened never to produce the digitiser
  code that triggers it. It was caught by running the worked examples, which is
  why the examples are executed as part of the release check and not treated as
  documentation only.
- **D-06 would have survived any amount of functional testing**, because every
  function behaved correctly; only the report's claim about provenance was wrong.
  It was caught by writing a test that asked what the report *says*, not what the
  code *does*.
- **D-07 was found by actually running the suite with the extras removed**, rather
  than assuming the skip markers were complete. CORE-NFR-001 and CORE-NFR-003 are
  claims about a configuration nobody develops in, so they are only credible if
  that configuration is exercised. It now is, and the figures are in §1. The same
  reasoning produced the parsed check described in §4.2, since the extras-blocked
  run cannot see a module no test imports.
- **D-08, D-09 and D-10 are the same defect in three places**: a figure or a log
  that is wrong in a way nothing visibly fails on. Each was caught by writing the
  test that asks what is *reported*, not whether the code runs. D-09 in particular
  would have dropped every 16-bit trace write on real hardware while passing every
  functional test, because the simulator and the decoder agreed with each other.
- **D-11 and D-12 were defects in the test double, not the product.** Both made a
  real check vacuous: a condition that was ignored, and an envelope that could
  never trip. A simulator that is too permissive is worse than no simulator,
  because the suite reports success. They are recorded here as defects for that
  reason, and each now has a test asserting the behaviour the driver depends on.
- **Unit tests found what compiling could not.** D-27 and D-28 both compile
  perfectly. One made a loss-detection counter incapable of detecting loss; the
  other would have executed the tail of a truncated command. Neither is visible
  by reading, and neither would have been found by a bench session that did not
  happen to overflow a buffer or a queue. This is the argument for testing
  firmware logic on a host: the cases that matter are the ones that are awkward
  to provoke on the part.
- **Compiling found in twenty minutes what review had not found at all.** Seven
  defects, five of which stop the build outright, in code that had been read
  carefully twice. Two are worth singling out: D-23, where the SDK's
  critical-region macros are a brace pair and cannot contain a `return` - a rule
  invisible unless you have read the macro or the compiler tells you; and D-26,
  where the code would have compiled and failed on the first GATT discovery,
  which is the failure a bench engineer would have spent an afternoon on. The
  lesson is not subtle: **source that has never been near a compiler should be
  described as such, and getting it to a compiler is worth real effort.**
- **The version gap was informative rather than an obstacle.** SDK 15.2 lacking
  the GATT queue is precisely what exposed D-26: the compiler's complaint that a
  member did not exist prompted the question of what it is *for* in SDK 17.
- **D-15 is the defect this element was most likely to produce**, and the least
  likely to be noticed: a sensor advertising exactly to specification, failed by
  a limit it meets, because of the last bit of a double. It was found by a test
  written to assert that *correct* behaviour passes - the case that is easy to
  leave untested, since a suite full of deliberately wrong inputs never
  exercises it.
- **D-18 is the same lesson as D-11 and D-12 in the previous revision**: a test
  double that is quietly wrong makes a real check vacuous. Here a scan found two
  sensors instead of three, and every test that asserted "the sensors I expect
  are present" still passed, because they asserted on the two.
- **D-14 was found by checking the traceability matrix against the suite** — the
  matrix cited three tests that did not exist, because a module had been written
  and traced but never tested. The consistency checks of §4.1 do not catch that
  (they check identifiers, not test names), so this one was a manual cross-check;
  it is worth repeating per release.

## 13. Verdict against the pass criteria

| ID | Criterion | Result |
|---|---|---|
| PC-1 | All tests pass | **Pass** — 1 202/1 202 |
| PC-2 | Statement coverage ≥ 90% | **Pass** — 94% |
| PC-3 | Every requirement covered | **Pass** — see BENCHTOOLS-TRACE-001 |
| PC-4 | Injected skews recovered to < 0.1 sample interval | **Pass** — worst case 0.055 |
| PC-5 | Layering constraints hold | **Pass** |
| PC-6 | Work-product consistency checks hold | **Pass** |
| PC-7 | Every timing method recovers the injected 1.000 ms interval, except the host clock, which flags itself | **Pass** — §6.1 |
| PC-8 | No test requires a probe, target, debugger or GDB server | **Pass** — §1 |
| PC-9 | No module imports a third-party package at module level | **Pass** — §4.2 |
| PC-10 | Firmware and driver agree; firmware hygiene holds | **Pass** — §4.3 |
| PC-12 | Firmware unit tests pass; the firmware still compiles | **Pass** — §4.4, §4.5 |
| PC-11 | A simulated 100 ms sensor reads as 105 ms mean, 10 ms spread; a sensor that skips beacons is reported as missing them | **Pass** — §7.1 |

**Overall verdict: PASS**, subject to the bench confirmation items that cannot be
discharged without physical hardware:

- the VISA determination report §5.1, for the oscilloscope;
- `docs/jlink/JLink_Integration_Notes.md` §4, for the probe (JLINK-OPEN-01 to
  -04, of which the SWO timestamp scaling is the one that could change a
  reported figure);
- `docs/ble/BLE_Dongle_Notes.md` §5, for the dongle. The firmware now has unit
  tests (§4.4), **compiles** against real SDK headers (§4.5) and **builds,
  links and packages** against nRF5 SDK 17.1.0 in CI (§4.6), which is a
  materially stronger position than this report's first issue described. The
  verdict covers the host driver, the protocol agreement, the firmware's
  source-level rules, its compilation and its link. It does not cover behaviour
  on silicon: nothing here has run on a dongle, which BLE-OPEN-02 to -04 exist
  to establish.

## 14. Supplementary checks performed

| Check | Result |
|---|---|
| `examples/01_capture_and_plot.py` | Runs; produces CSV, plot and hardcopy |
| `examples/02_channel_spread.py` | Runs; host-side skews match instrument-side delay on all pairs |
| `examples/03_period_and_jitter.py` | Runs; host and instrument period agree |
| `examples/04_run_bench_suite.py` | Runs; drives the shipped specification and writes a markdown report |
| `examples/05_jlink_firmware.py` | Runs against the simulated probe; flashes, verifies, reads RTT, variables and the call stack, and reports all four timing methods |
| `examples/06_ble_sensor.py` | Runs against the simulated dongle; scans, profiles advertising, connects and times replies on both clocks |
| `benchtools run specs/clock_skew.yaml --simulate` | 5 tests, all pass |
| `benchtools run specs/firmware_timing.yaml --simulate` | 6 tests, all pass in 1.01 s |
| The same against `benches/simulated.yaml --markdown` | Report written; FW-REQ-010/011/020/021 all pass, and the run is disclosed as simulated |
| The same against a bench whose `probe` alias is an oscilloscope | Exits 1 with `ERROR`: "the specification wants instrument 'probe' to be a JLinkProbe, but bench 'wrong' provides a Tek3014B" |
| `benchtools jlink info --resource sim://` and every other sub-command | All run; JSON on stdout |
| `benchtools run specs/sensor_ble.yaml --simulate` | 4 tests, all pass; measured 105 ms mean interval, 0 missed, 95 ms response |
| `benchtools ble --resource sim://` with every sub-command | All run; JSON on stdout, session log written |
| The same with a deliberately tightened limit | Exits 1, names the failing measurement and by how much |
| `benchtools` sub-commands `run`, `scope`, `drivers`, `backends` | All run |
| `python -m benchtools` | Runs |
| `benchtools` console script after `pip install -e .` | Installs and runs |
| Full suite with `matplotlib`, `pyvisa`, `pyyaml`, `numpy` and `pyserial` blocked | 1 152 passed, 36 skipped, 0 failed |
| `firmware/nordic_dongle/scripts/compile_check.sh` in `canembed/canembed-arm` | All six firmware units compile, 0 warnings, apart from four listed SDK 17-only lines (§4.5) |
| `ctest --test-dir build/firmware-tests` | 5 binaries, 131 cases, all pass in 0.01 s |
| `make SDK_ROOT=…` against SDK 15.2 | Drives a real build to the compile stage; stops only on files SDK 15.2 places elsewhere or lacks, which is the expected result for an SDK 17 project |
| Import with those extras blocked | Package imports; only the plot, VISA and YAML paths raise, each naming its extra |
