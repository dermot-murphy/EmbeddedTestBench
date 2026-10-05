# System Qualification Test Report

*Automotive SPICE® PAM v4.0 | SYS.5 — System Qualification Test*

---

## 1. Document Identification & Control

| Field | Value | Field | Value |
|---|---|---|---|
| **Document ID** | ETB-SYS5-002 | **Version** | 1.1 |
| **Project** | Embedded Test Bench | **Date** | 2026-10-04 |
| **Status** | Draft — for review | **Classification** | Internal |
| **Author** | Claude | **Reviewer** | Dermot Murphy |
| **Approver** | Dermot Murphy | **Related Process** | SYS.5 |

> Reviewer and Approver are the same person; see ETB-DEV-002. The author is an
> AI assistant; see ETB-DEV-001.

---

## 2. Revision History

| Version | Date | Author | Description of Change |
|---|---|---|---|
| 1.0 | 2026-10-04 | Claude | #176: first hardware qualification campaign of the bench, run on the Windows bench PC. |
| 1.1 | 2026-10-04 | Claude | #183: product renamed to Embedded Test Bench - document file name prefix `EmbeddedTestBench_`, identifier prefix `ETB-` (was `TB-`), product name in prose. Earlier revision rows keep the names in use when they were written. |

---

## 3. Purpose & Scope

### 3.1 Purpose

This report records the first run of ETB-SYS5-001's qualification scenarios on
real hardware. For each of the 64 requirements in ETB-SYS2-001 it states
whether the requirement is **qualified**, and on what evidence. ETB-SYS5-001
says how qualification is done; this report says what happened when it was.

### 3.2 Referenced Documents

| Document ID | Title | Version |
|---|---|---|
| ETB-SYS2-001 | Embedded Test Bench System Requirements Specification | 0.2 |
| ETB-SYS5-001 | Embedded Test Bench System Qualification Test | 0.3 |
| ETB-SWE4-002 | Embedded Test Bench Unit Verification Report | 1.18 |
| ETB-SUP9-001 | Embedded Test Bench Problem Resolution Management Plan | 0.1 |
| `specs/qualification/README.md` | Hardware qualification procedure | — |

### 3.3 Scope

**In scope:** the assembled bench on the Windows bench PC:
- the Nordic PCA10059 BLE dongle;
- the S2-LP kit;
- the GPD-3303D supply;
- the TTi 1604 multimeter;
- the J-Link on Kepler sensor 5C1712;
- the Raspberry Pi Pico 2 thermometer (identity only);
- the runner and the reports it writes.

**Out of scope**, by the owner's ruling on 2026-10-04 (#176):

| Excluded | Why | Affects |
|---|---|---|
| Oscilloscope, TDS3014B | Not yet live on the bench | QS-04; ETB-SYS2-060 to -064; OPEN-01, OPEN-02 |
| SHT30-D temperature measurement | The module is not yet wired | PICO-OPEN-02, -03 |
| The content of the Kepler sensor's radio frames | Sensor firmware behaviour, not the bench's | `specs/kepler_version.yaml`, which fails against firmware V11.00.0000-95 because the VERSION frame appends the SHA to the version |

---

## 4. Test Environment and Configuration

### 4.1 Bench

`benches/bench_pc.yaml`. The ports were matched to USB serial numbers before
the first run.

| Alias | Instrument | Identity recorded in the reports | Resource |
|---|---|---|---|
| `probe` | SEGGER J-Link OB-SAM3U128-V2-NordicSem | S/N 682395790, firmware "J-Link ARM V8 compiled Nov 28 2014", hardware V8.00 | `jlink://` (GDB Server V9.42) |
| `dongle` | Nordic PCA10059 | firmware 1.4.0, built local:Sep-29-2026T11:41:48, protocol 1.4 | COM10, USB `D7FA0F34C85A` |
| `psu` | GW Instek GPD-3303D | SN GER916893, firmware V1.09 | COM11, FTDI `A105X5XCA` |
| `dmm` | TTi 1604 | (the meter reports no identity) | COM13, FTDI `A9LQ0R81A` |
| `s2lp` | NUCLEO-L053R8 with STEVAL-FKI433V2, ST CLI firmware | board STEVAL-FKI433V2, firmware 80 | COM4, ST-LINK `066CFF515055657867182645` |
| `temp` | Raspberry Pi Pico 2, `firmware/pico_sht30` | V1.00.0000 (5c80ae7) | COM14, USB `AC5483CD0798FB0B` |

### 4.2 Target

Kepler sensor **5C1712**, nRF52840 AAD0, BLE address `D1:8D:3B:4C:19:96`. It is
the sensor approved for destructive tests. Its firmware on arrival was
`V11.00.0000-95-gc051f3665`.

Before QS-01 the whole code flash and UICR were read back with nrfjprog
(SHA-256 `9b2b5406…dc1d`). After QS-01b they were restored from that backup,
and the readback was compared byte for byte with it: **identical**. The sensor
then answered `RD VERSION` with `V11.00.0000-95-gc051f3665` again.

| Image | Used by | Manifest |
|---|---|---|
| `KAPPAX_PCB_V4X_Production_APP_PLUS_SD_V10.01.2000.hex` (archive) | QS-01 | `specs/qualification/firmware/v10.01.2000` |
| `KAPPAX_APP_SDK17_PCB_V4X_RELEASE-plus-bl-and-softdevice.hex`, `V11.00.0000-96-g25a54b97a`, with its ELF | QS-01b | `specs/qualification/firmware/v11.00.0000-96` |

### 4.3 Host and software

| Item | Value |
|---|---|
| Host | Windows 10 Pro 10.0.19045, bench PC |
| Python | 3.11 (`C:\compilers\python\python311`) |
| benchtools | `develop` at 8745599, plus the qualification specifications of #176 |
| GDB | Arm GNU Toolchain 14.2 `arm-none-eabi-gdb` |
| J-Link software / nrfjprog | V9.42 / 10.24.2 |

### 4.4 Constraints imposed during the campaign

Kepler sensor 5C1712 is wired to the supply's outputs, so the owner set these
limits:
- no supply output is switched on;
- the supply stays in INDEPENDENT tracking;
- every setpoint stays between 2.8 V and 3.3 V.

The limits were first stated as "no output energised", before QS-01. The
tracking and setpoint limits followed during QS-03, when the owner stopped a
request to set series tracking. One earlier QS-03 run had written 1.5 V,
2.5 V and 0 V setpoints, all with the outputs off. It is kept as
`attempts/qs03_attempt1_outofrange_setpoints.*` and is **not** used as
evidence. The supply was left at CH1 3.3 V and CH2 3.0 V, outputs off, as the
owner asked.

---

## 5. Verification Measures

### 5.1 Strategy

As ETB-SYS5-001 §4: end-to-end scenarios, each qualifying several requirements.
A requirement is qualified only by the hardware configuration. Requirements
whose method in ETB-SYS2-001 is Inspection (I) or Analysis (A) are qualified by
that method, recorded in §7.

Where a requirement is that the bench **refuses**, the test is written to end
in ERROR, and its name says "(expected ERROR)". Such an ERROR, with a message
naming what was asked and why, is the pass. A specification cannot assert
"this step errors", so §6 reads each one.

### 5.2 Scenarios run

QS-01b, QS-09 and QS-10 are new; ETB-SYS5-001 version 0.3 adds them. QS-01b
was added because QS-01's image has no ELF. QS-09 was added because no
scenario covered the multimeter. QS-10 was added because no scenario recorded
every instrument's identity in one report.

| Scenario | Specification | Configuration |
|---|---|---|
| QS-01 Sensor bring-up | `specs/qualification/qs01_bringup.yaml` | Hardware |
| QS-01b Debug control and firmware state | `specs/qualification/qs01b_debug.yaml` | Hardware |
| QS-02 BLE command document | `specs/qualification/qs02_kepler_commands.yaml` and `.md` | Hardware |
| QS-03 Supply state and safe state | `specs/qualification/qs03_supply.yaml` | Hardware, independent only (§4.4) |
| QS-04 Scope measurement | — | Out of scope (§3.3) |
| QS-05 Evidence sufficiency | — | Not performed (§6.6) |
| QS-06 Refuse rather than invent | `qs06a_missing_instrument.yaml`, `qs06b_refusals.yaml` | Hardware |
| QS-07 Sub-GHz link | `specs/qualification/qs07_subghz_link.yaml` | Hardware |
| QS-08 Build and standards | CI, `.github/workflows/` | CI on `develop` |
| QS-09 Multimeter | `tests/bench/tti1604` (opt-in bench test, DMM-FR-080) | Hardware, inputs open |
| QS-10 Bench identity | `specs/qualification/qs10_bench_identity.yaml` | Hardware **and** simulated |

### 5.3 Evidence

Everything is in `docs/aspice/qualification/2026-10-04/`. For each run there
are an event log (`.events.jsonl`), a markdown report (`.md`), JSON (`.json`)
and JUnit XML (`.junit.xml`). Runs that were repeated keep their earlier
attempts under `attempts/`, with the reason in §6. The JSON `started` times are
UTC; the campaign ran from 17:35 to 19:56 BST.

---

## 6. Results by Scenario

### 6.1 QS-01 — Sensor bring-up: **PASS** (7 of 7)

Evidence: `qs01.*`.

| Measurement | Value | Limit |
|---|---|---|
| Identity valid before erase | 0 | = 0 |
| Sensor ID, read from UICR | 5C1712 | 000001 to FFFFFE |
| Validity byte after chip erase | 255 | = 255 (an invalid record, ETB-SYS2-049) |
| Image verified after flashing | 1 | = 1 (flash 14.7 s) |
| Sensor ID after restoring the record | 5C1712 | = 5C1712 |
| RTT lines within 20 s of reset and run | ≥ 1 (V10 banner, "VERSION: V10.01.2000 (08ba964c)") | ≥ 1 |
| Boards advertising that ID | 1 (`KAPPA_5C1712_V10.01.200`) | = 1 |
| `RD VERSION` over BLE | `V10.01.2000` | = manifest `V10.01.2000` |

**Attempts 1 to 3** (`attempts/qs01_attempt1..3.*`) ended in ERROR: nothing
was found on the air. Erase, flash, verify, identity restore and RTT passed
each time. With a 5 s, then 30 s, then 90 s scan, nothing advertised, though
RTT showed the sensor booting and then going quiet. An experiment
(`attempts/exp177_reset_run.*`) showed the cause:
- `probe.reset {halt: false}` leaves the core **halted** on a real J-Link;
- reset-and-halt followed by `probe.run` keeps it running: 28 RTT lines, and
  found by the scan with the probe still attached.

This is defect **#177**. The final QS-01 resets halted and then runs, a
workaround recorded in the specification.

### 6.2 QS-01b — Debug control and firmware state: **FAIL** (4 of 5; 12 of 13 measurements)

Evidence: `qs01b.*`.

| Measurement | Value | Limit | Result |
|---|---|---|---|
| Image verified | 1 (flash 17.0 s) | = 1 | PASS |
| Identity record kept | 0x12175C00 | as before | PASS |
| PC after `reset {halt: true}` | **0x00000000** | flash range | PASS (but wrong, see below) |
| PC after one instruction step | 0x00000A82 | reset PC ± 4 | **FAIL** |
| Halt at breakpoint on `main` | `main` | = main | PASS |
| Call stack: frames, innermost | 1, `main` | ≥ 1, `main` | PASS |
| `SystemCoreClock`, read by name | 64 000 000 Hz | = 64 000 000 | PASS |
| `SystemInit` to `main`, cycle counter | 22.359 ms, 1 430 990 cycles | 0.1 µs to 1 s | PASS |
| Resolution stated | 15.625 ns (one cycle at 64 MHz) | 1 ns to 1 µs | PASS |
| Found on the air after run | 1 | = 1 | PASS |
| `RD VERSION` over BLE | `V11.00.0000-96-g25a54b97a` | = manifest | PASS |

The reset vector in flash is `0x00000A81`. So the core's PC after reset is
0x00000A80, and the step to 0x00000A82 is correct. The first read, 0x00000000,
is stale: defect **#178**. The test is right to fail, and the failure is the
bench's. `attempts/qs01b_attempt1.*` passed only because it did not yet check
the PC.

### 6.3 QS-02 — BLE command document: **PASS**

Evidence: `qs02.*`, and the document's own report `qs02_document_report.md`.

The document returned 8 passed, 0 failed, 0 errors and 5 skipped. The skips
were one delay, two connects, one disconnect and one command with nothing
expected; each is recorded as skipped, not passed.

| Step | Result | Time (10 ms) |
|---|---|---|
| `RD VERSION`, `RD ID`, `RD SHA` | PASS | 40, 40, 30 ms |
| `RD TEMPERATURE`, `RD BATTERY` | PASS | 60, 90 ms |
| `RD BATTERY`, nothing expected, its own 2 s timeout | SKIP, reply recorded | 90 ms |
| `RD NO-SUCH-ITEM` | PASS (`NACK Invalid Command`) | 40 ms |
| `ECURESET HARD` → `<disconnect>` | PASS, drop timed | 4 120 ms |
| Reconnect, `RD VERSION` | PASS | 40 ms |

`attempts/qs02_attempt1.*` failed one check, `steps_skipped`, because the
specification expected six skips where the document has five: an error in
the specification, corrected before the final run.

### 6.4 QS-03 — Supply: **PASS** (4 of 4), independent tracking only

Evidence: `qs03.*`.

Every setpoint was read back from the supply itself (`VSET?` and `ISET?`), not
from the driver's memory. The only settings sent were `ISET1:0.100`,
`VSET1:2.800`, `VSET1:3.300`, `ISET2:0.200`, `VSET2:2.800`, `VSET2:3.000` and
`OUT0`.

| Check | Value |
|---|---|
| Tracking in force, read from `STATUS?` | independent |
| Output switch | off throughout |
| CH1: 2.8 V then 3.3 V, limit 0.1 A, read back | 2.8 V, 3.3 V, 0.10 A |
| CH2: 2.8 V then 3.0 V, limit 0.2 A, read back | 2.8 V, 3.0 V, 0.20 A |
| Output voltage and current, both channels | 0.0 V, 0.00 A (outputs off) |
| Safe state: output switch open, still independent | yes |

**Not performed, by owner decision (§4.4):** the series and parallel
refusals; the safe state reached from each tracking mode; switching an output
on.

### 6.5 QS-04 — Scope measurement: **out of scope** (§3.3)

### 6.6 QS-05 — Evidence sufficiency: **not performed**

This scenario needs someone who was not present to reproduce a run from its
report alone. No such person was available during the campaign. The
material for it exists: the QS-01 report names the specification, the bench,
every parameter, the image and manifest paths, and each instrument's identity,
and `specs/qualification/README.md` gives the procedure.

### 6.7 QS-06 — Refuse rather than invent: **PASS** (every outcome as required)

Evidence: `qs06a.*`, `qs06b.*`.

| Provocation | Outcome | Message (abridged) |
|---|---|---|
| A specification using `scope`, which the bench lacks | ERROR at setup, no step run | "uses instrument(s) 'scope', which the bench 'Bench PC (Windows)' does not define; it provides dmm, dongle, probe, psu, rtt, s2lp, temp" |
| The multimeter returned to local mode mid-session, then read | ERROR, no value | "no measurement from the 1604 within 3.0 s…" |
| `read_integer` of 16 bytes | ERROR | "read_integer takes 1 to 8 bytes, not 16" |
| `read_integer` with byte order `middle` | ERROR | "byteorder must be 'little' or 'big', not 'middle'" |
| Dongle firmware against a manifest saying 9.9.9, updating forbidden | ERROR | "not running the expected firmware and updating was not permitted: dongle runs 1.4.0…; the build is 9.9.9" |
| The same mismatch, compared and asserted | **FAIL**, not ERROR | `dongle_matches_manifest: 0 != required 1` (ETB-SYS2-003) |
| An RTT command nothing answers | ERROR | "RTT did not produce '^NEVER-ANSWERED$' within 3.0 s. Received: …" |

`attempts/qs06b_attempt1.*` had an argument name wrong in the specification:
`expected=` for `firmware=`. The bench refused it with a clear message
("could not be called as specified"). Corrected.

After QS-06b detached the probe, the sensor stopped advertising until
`nrfjprog --reset`. #95 already recorded this behaviour of a GDB attach to a
SoftDevice target. The procedure now ends any run that attaches the probe with
a reset.

### 6.8 QS-07 — Sub-GHz link: **ERROR** (4 of 5)

Evidence: `qs07.*`, `attempts/qs07_rx_only.*`.

| Check | Value | Result |
|---|---|---|
| Register file applied with reset to defaults, verified | 28 checked, 0 mismatched | PASS |
| Every register read | 123 registers | PASS |
| `SYNC0` written, read back, restored | 0x4E → 0x5A → 0x4E | PASS |
| Packet transmitted | 17 bytes, firmware error 0 | PASS |
| Receive after the transmit | ERROR: GPIO3 reads 0 after clearing IRQ_STATUS | **ERROR** |
| Receive alone (`--test`, no transmit first) | VERSION frame from 5C1712 | PASS |

The receive failure repeats whenever a transmit has come first: defect
**#179**. The two attempts that ended in a BLE connect error (reason 0x3E,
`attempts/qs07_attempt2.*` and `attempts/qs07_rx_only_attempt1.*`) are defect
**#180**: `open_link` makes a single attempt.

There is one S2-LP kit on the bench. The transmitted packet is shown to be
sent and logged, **not to arrive**: no second receiver was available.

### 6.9 QS-08 — Build and standards: **PASS**

GitHub Actions on `develop` at 8745599 (2026-10-04): `firmware`, `style`,
`lint`, `tests` and `bench` all succeeded. The `firmware` workflow also
succeeded on `main` at 7079bed.

### 6.10 QS-09 — Multimeter: **FAIL**

Evidence: `qs09.junit.xml`, `qs09_tti1604_bench_findings.md`, `attempts/qs09_*`.
Inputs were open; no references were wired, so the four reference tests
skipped.

| Run | Passed | Failed |
|---|---|---|
| 1 | 6: link, keys acknowledged, frames decode, reading rate, raw stream, local/remote | 4: function tour (frequency), every DC range, frequency gate, open ohms |
| 2, after a power cycle | 3: reading rate, raw stream, local/remote | 7 |

**Confirmed:**
- 0.398 s between readings;
- 10-byte frames between carriage returns;
- no NUL after a frame;
- remote and local mode behave as documented;
- keys echoed promptly in run 1, so the converter powers the interface.

**Failed:**
- The driver did not recognise the frequency function, though the meter's
  panel showed AC V Hz.
- After that the meter went silent or stopped echoing keys for the rest of
  the session.
- An open input on ohms was decoded as a blank display (`.`), not as
  overrange.

Defect **#181**.

### 6.11 QS-10 — Bench identity: **PASS** on hardware and simulated

Evidence: `qs10.*`, `qs10_simulated.*`.

The same specification ran on both benches. In the hardware report every
connected instrument is identified (§4.1). The simulated run is labelled
"(simulated)", with "Run against simulated instruments…" in markdown,
`"simulated": true` in JSON and the label in JUnit.
`attempts/qs10_attempt1..2.*` failed on two expectations of mine that were
wrong: a result path, and a frequency band expected of a radio with no receive
setup. Both corrected; the instruments were not at fault.

---

## 7. Results by Requirement

Results:
- **Q**: qualified.
- **P**: partially qualified; what is missing is stated.
- **NQ**: not qualified.
- **NP**: not performed.
- **OOS**: out of scope.

| Requirement | Method | Result | Evidence | Note |
|---|---|---|---|---|
| ETB-SYS2-001 | D | NQ | QS-01, QS-05 | Describe once and run: shown. Reproduction by another engineer (QS-05) not performed |
| ETB-SYS2-002 | T | Q | QS-01, QS-01b | RTT, memory and a named variable asserted in the same run as BLE results |
| ETB-SYS2-003 | T | Q | QS-06b, QS-02 | The same firmware mismatch is ERROR when refused, FAIL when asserted |
| ETB-SYS2-004 | T | NQ | QS-06b; #178 | Silence errors rather than repeating a value. But a stale PC was reported as read (#178) |
| ETB-SYS2-010 | T | NQ | QS-10 | Every listed instrument but the oscilloscope is on the bench and works |
| ETB-SYS2-011 | T | Q | QS-06a, all | Each run used a subset; a missing instrument stopped the run naming it |
| ETB-SYS2-012 | T | Q | QS-10 simulated; QS-01, QS-01b dry runs | |
| ETB-SYS2-013 | I | Q | `gpd3303d/simulator.py` | Models tracking and its refusals. Observation O1 |
| ETB-SYS2-014 | I | Q | `benches/bench_pc.yaml` | |
| ETB-SYS2-015 | T | Q | QS-10, QS-01 JSON | Model, serial number and firmware where reported. Observation O2 |
| ETB-SYS2-016 | T | Q | QS-10 simulated | Labelled in markdown, JSON and JUnit |
| ETB-SYS2-020 | T | NQ | QS-03 | Voltage and current limit set and read back. Switching an output on not exercised (owner, §4.4) |
| ETB-SYS2-021 | T | Q | QS-03 | Output voltage and current read back. 0 V, 0 A with outputs off |
| ETB-SYS2-022 | T | P | QS-03 | CC/CV and independent tracking read. Series and parallel decode unconfirmed (PSU-OPEN-06) |
| ETB-SYS2-023 | T | NP | — | Needs series or parallel tracking (owner, §4.4) |
| ETB-SYS2-024 | T | P | QS-03 | Safe state (output off) reached in independent. Not from the other modes, and not the 0 V setpoints of `reset()` |
| ETB-SYS2-025 | I | Q | `gpd3303d/psu.py` | Channels 1 and 2 only. Any other channel is refused |
| ETB-SYS2-030 | T | Q | QS-01, QS-01b | Two images programmed and verified |
| ETB-SYS2-031 | T | NQ | QS-01, QS-01b; #177, #178 | Halt, step, breakpoint and run work. Reset without halting leaves the core halted (#177). Registers read just after a reset are stale (#178) |
| ETB-SYS2-032 | T | Q | QS-01, QS-06b | Read and written by address, width and byte order. Bad width and order refused |
| ETB-SYS2-033 | T | Q | QS-01b | `SystemCoreClock` by name; call stack at `main` |
| ETB-SYS2-034 | T | Q | QS-01, QS-06b | RTT read and written. RTT lines logged in the run's event log |
| ETB-SYS2-035 | T | Q | QS-01b | 22.359 ms on the cycle counter, resolution 15.6 ns |
| ETB-SYS2-036 | T | Q | QS-01, QS-01b, QS-06b | Two images against their manifests, and a mismatch refused |
| ETB-SYS2-040 | T | P | QS-01, QS-10 | Address and name reported. Advertising data not part of the scan result in this campaign |
| ETB-SYS2-041 | T | Q | QS-01, QS-01b, QS-02 | |
| ETB-SYS2-042 | T | Q | QS-02 | |
| ETB-SYS2-043 | T | Q | QS-01 JSON | `dongle_us` with `host_us` kept |
| ETB-SYS2-044 | T | Q | QS-02 | Session in the event log and the document report |
| ETB-SYS2-045 | T | Q | QS-01 | Scanned for the ID read from UICR. Exactly one board |
| ETB-SYS2-046 | T | NQ | QS-07; #179 | Registers programmed, read and written; transmit sent; receive works alone. Receive after transmit fails (#179). Transmit not received (one kit) |
| ETB-SYS2-047 | I | Q | QS-07, QS-10 | The kit runs ST's CLI firmware; the bench never programmes it |
| ETB-SYS2-048 | T | Q | QS-01 | |
| ETB-SYS2-049 | T | Q | QS-01; ETB-SWE4-002 | An erased part reads 0xFF. Its rejection is unit-verified |
| ETB-SYS2-050 | T | Q | QS-01 | `5C1712` |
| ETB-SYS2-051 | T | NQ | QS-09; #181 | Volts in SI. Frequency failed; current and resistance not referenced |
| ETB-SYS2-052 | T | NP | — | Needs the front-panel Hold key with the meter in remote (DMM-OPEN-05) |
| ETB-SYS2-053 | T | NQ | QS-09; #181 | An open input on ohms read as blank, not overrange |
| ETB-SYS2-060 to -064 | T | OOS | — | Oscilloscope not live |
| ETB-SYS2-070 | T | Q | QS-10 | One specification, hardware and simulated benches |
| ETB-SYS2-071 | T | Q | QS-01 | Sensor ID read in one step, scanned for in a later one |
| ETB-SYS2-072 | T | Q | QS-01, QS-03 | Limit, tolerance and exact text, each shown as such |
| ETB-SYS2-073 | T | Q | QS-02 | |
| ETB-SYS2-074 | T | Q | QS-02 | 5 skipped, none counted as passed |
| ETB-SYS2-075 | T | Q | QS-02, QS-06b, QS-07 | PASS, FAIL and ERROR runs each as the rule says |
| ETB-SYS2-076 | T | Q | QS-02 document report | |
| ETB-SYS2-077 | T | Q | QS-02 | 10 ms in the report; microseconds in the event log |
| ETB-SYS2-078 | T | Q | all | Specification and bench named. Written to file |
| ETB-SYS2-079 | T | Q | all `.junit.xml` | |
| ETB-SYS2-080 | T | Q | QS-02 | |
| ETB-SYS2-081 | T | Q | QS-02 | `SENSOR_ID` variable; connect and disconnect as steps |
| ETB-SYS2-082 | T | Q | QS-02 | 2 s and 60 s step timeouts |
| ETB-SYS2-083 | T | Q | QS-02 | Disconnection after `ECURESET HARD` timed at 4.12 s |
| ETB-SYS2-084 | T | Q | all `.events.jsonl` | |
| ETB-SYS2-090 | A | NQ | §4.3 | Windows shown. Linux and a container on hardware not attempted |
| ETB-SYS2-091 | T | Q | QS-08 | |
| ETB-SYS2-092 | T | Q | QS-08 | |
| ETB-SYS2-093 | I | Q | header scan | No vendor copyright header in tracked source outside `docs/` |
| ETB-SYS2-094 | T | Q | QS-06 | Every refusal named what was asked and why |
| ETB-SYS2-095 | A | NQ | ETB-SYS2-001 §14; ETB-RTM-001 | Downward trace is by requirement group, not per requirement. ETB-RTM-001 has no ETB-SYS2 rows. This table is the first per-requirement trace to tests |

### 7.1 Summary

| Result | Count |
|---|---|
| Qualified | **44** |
| Partially qualified | 3 |
| Not qualified | 10 |
| Not performed | 2 |
| Out of scope | 5 |
| **Total** | **64** |

Before this campaign, 2 were qualified (ETB-SYS2-091 and -092).

---

## 8. Problems Found

Each problem is raised for resolution under ETB-SUP9-001.

| Issue | Severity | Problem | Blocks |
|---|---|---|---|
| #177 | Major | J-Link: `reset(halt=False)` leaves the target halted | ETB-SYS2-031 |
| #178 | Major | J-Link: registers read just after `reset(halt=True)` are stale (PC reads 0) | ETB-SYS2-004, -031 |
| #179 | Major | S2-LP: receive refused after a transmit in the same session (GPIO3 reads 0) | ETB-SYS2-046 |
| #180 | Minor | BLE dongle: `open_link` does not retry a link that fails to establish (0x3E) | — |
| #181 | Major | TTi 1604: frequency not recognised, meter lost afterwards, open ohms not reported as overrange | ETB-SYS2-051, -053 |

**Observations**, not raised as issues:
- **O1.** The simulated probe models neither defect #177 nor #178, and its
  chip erase does not clear UICR (QS-01 dry run). A simulator that does not
  share a real fault cannot catch it. This is how #177 and #178 passed SWE.4.
- **O2.** The markdown report's Instruments table has no serial-number column,
  though the JSON records the serial numbers (the J-Link's 682395790, the
  supply's GER916893).
- **O3.** Kepler sensor firmware V11.00.0000-95 appends its SHA to the version
  in the VERSION frame (§3.3). This is a finding for the sensor project, not
  the bench.

---

## 9. Bench-Confirmation Items Answered

Updated in each element's notes:

| Item | Before | After this campaign |
|---|---|---|
| JLINK-OPEN-01, Windows execution | Open | **Closed**: every probe scenario ran on Windows 10 |
| JLINK-OPEN-02, GDB/MI of the installed GDB | Open | **Closed**: `info`, stack, variable, breakpoint and step parsed from GDB 14.2 against a real target |
| JLINK-OPEN-04, RTT discovery and flash timing | Open | **Figures recorded**: flash and verify 14.7 s (V10) and 17.0 s (V11-96); chip erase 0.6 s; RTT output within 20 s of reset |
| BLE-OPEN-04, connection parameters | Open | **Closed**: `interval_us=30000` agreed with 5C1712 |
| DMM-OPEN-01, frame and terminator | Open | **Partly**: 10-byte frames between CRs, no NUL. Segment patterns beyond the digits still open (#181) |
| DMM-OPEN-07, the converter powers the interface | Open | **Closed**: keys acknowledged promptly (run 1) |
| PSU-OPEN-05, -06, series and parallel | Open | Not performed (owner, §4.4) |

---

## 10. Exit Criteria (ETB-SYS5-001 §8)

| # | Criterion | State |
|---|---|---|
| X1 | Every scenario in §5 passes in the hardware configuration | **Not met.** QS-01, -02, -03 (independent), -06, -08 and -10 pass. QS-01b, -07 and -09 do not. QS-04 is out of scope and QS-05 was not performed |
| X2 | Every system requirement traces to a passing scenario | **Not met.** 44 of 64 qualified (§7.1) |
| X3 | Every item in §7 is closed by a recorded run | **Not met.** 4 closed, 2 partly answered (§9) |
| X4 | No open Critical or Major problem against a qualified requirement | **Met.** The four Major problems block requirements that are recorded as not qualified (§8) |

## 11. Conclusion

The bench is qualified on hardware for:
- test definition, execution and evidence;
- programming, identifying and talking to a target over BLE;
- reading and setting the supply within the owner's limits;
- refusing what it cannot do.

It is **not yet qualified** for:
- reset-dependent probe control (#177, #178);
- transmit-then-receive on the S2-LP (#179);
- the multimeter beyond DC volts (#181).

Also outstanding:
- the scope and the SHT30, when they are live;
- the series and parallel supply checks, when the sensor is not wired to it;
- reproduction by an independent engineer (QS-05).

Once #177, #178, #179 and #181 are fixed, rerun QS-01b, QS-07 and QS-09 to
close their requirements.

---

## 12. Review & Approval

| Role | Name | Signature / Electronic Approval | Date |
|---|---|---|---|
| Author | Claude | Approved | 2026-10-04 |
| Reviewer | Dermot Murphy | — | *pending* |
| Approver | Dermot Murphy | — | *pending* |
