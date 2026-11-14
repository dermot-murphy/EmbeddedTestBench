# Nordic PPK2 — Interface Notes

Working notes for the `ppk2` driver (#342): how the Power Profiler Kit II is
reached, the protocol command by command, where each fact came from, what the
bench's kit showed, and what has not been confirmed. They are in the form of
the other instruments' notes (`docs/dmm/TTi1604_Notes.md`,
`docs/picoscope3000/PicoScope3000_Notes.md`).

The bench's kit is a **Nordic Power Profiler Kit II**, USB serial number
`D527E1DA8DBA`, hardware number 59726, on COM5. Its bench entry is `ppk` in
`benches/bench_pc.yaml`, opened as `ppk2://D527E1DA8DBA`. As of 2026-11-14
nothing is wired to its VOUT, VIN, GND or logic inputs (the owner).

---

## 1. Sources

| Source | What it establishes | How it was read |
|---|---|---|
| Nordic's Power Profiler app, `NordicSemiconductor/pc-nrfconnect-ppk` on GitHub: `src/constants.ts`, `src/device/serialDevice.ts`, `src/device/abstractDevice.ts`, `src/actions/deviceActions.ts`, `worker/serialDevice.js` | The opcodes, the metadata text and how it is parsed, the sample word, the calibration formula and its defaults, the spike filter, the sample counter, the line rate, the regulator command, the modes | Read 2026-11-14. Licence: Nordic's own 4-clause licence. The facts were written down here and in `constants.py` and `protocol.py`; no code was copied (AD-31) |
| The bench's kit, 2026-11-14 | The metadata text; that it answers its metadata once per open; that it goes off USB when its port closes and keeps its settings; the stream rate; the mode and voltage taking effect | Measured (§4) |
| `ppk2-api` (IRNAS, GPL-2.0) | Nothing: not used, not copied | Its licence was read so that AD-31 could say why it is not a dependency |

---

## 2. How it is reached

| Layer | On the bench PC |
|---|---|
| USB device | `USB\VID_1915&PID_C00A`, a composite device: "nRF Connect USB CDC ACM (COM5)" and "nRF Connect DFU Trigger" |
| Windows driver | The standard USB CDC ACM driver; the kit is a serial port |
| Python | `benchtools/instruments/ppk2`, over the project's serial transport (pyserial). No Nordic package is used or needed (PPK-NFR-001) |

`ppk2://` finds the kit by its USB identity, and `ppk2://<serial number>` by
its USB serial number, so the COM port it lands on does not matter.
`benchtools ppk2 list` shows the kits the PC sees.

---

## 3. The protocol

The host writes one command per write: an opcode byte and its arguments. The
kit answers only `GET_METADATA`. The line rate is 115 200, as Nordic's app
opens it; a CDC port ignores it.

| Opcode | Name | Arguments | Effect |
|---|---|---|---|
| `0x19` | `GET_METADATA` | none | The kit sends its metadata text (§3.1) |
| `0x06` | `AVERAGE_START` | none | The kit streams samples (§3.2) until stopped |
| `0x07` | `AVERAGE_STOP` | none | The stream stops; a few milliseconds of samples may still be on the way |
| `0x11` | `SET_POWER_MODE` | `1` ammeter, `2` source | Selects the mode. Nordic's app switches the DUT power off before selecting source mode, and on after selecting ammeter mode; this driver switches it off before either and leaves it off |
| `0x0D` | `REGULATOR_SET` | millivolts, high byte then low byte | Sets the regulator, 800 to 5000 mV. In source mode this is the device's supply |
| `0x0C` | `DEVICE_RUNNING_SET` | `1` on, `0` off | The DUT power: the kit's supply in source mode, the path from VIN in ammeter mode. The kit does not report it |

Nordic's table has more opcodes (triggers, user gains, the spike filter on the
kit, reset); the driver does not send them.

### 3.1 The metadata

`Name: value` lines ending with `END`. On the bench kit (2026-11-14):

```
Calibrated: 0
R0: 1004.8547 … R4: 0.0566        shunt, per range
GS0: 0.0000 … GS4: 0.1159         gain slope
GI0: 1.0000 … GI4: 0.9358         gain intercept
O0: 172.5869 … O4: 138.2979       offset
VDD: 4000                         regulator, mV
HW: 59726
mode: 2                           1 ammeter, 2 source
S0 … S4, I0 … I4                  supply slope and intercept
UG0: 1.00 … UG4: 1.00             user gain
IA: 56
END
```

A value of zero, or `-nan`, or a missing one, keeps Nordic's default, as the
app does (`meta[key] || default`): on the bench kit `GS0` is zero, so its gain
slope in range 0 is 1.

### 3.2 A sample

Four bytes, little-endian, 100 000 a second:

| Bits | Field |
|---|---|
| 0 to 13 | ADC reading; multiplied by 4 before use |
| 14 to 16 | Current range, 0 (most sensitive) to 4; a value above 4 is read as 4 |
| 18 to 23 | Sample counter, modulo 64. A gap is samples lost |
| 24 to 31 | Logic inputs D0 (bit 24) to D7 |

The current in amps, for range *k*, ADC reading *a* and regulator voltage *V*
in millivolts:

```
raw     = (a − O[k]) × (1.8 / 163 840) / R[k]
current = UG[k] × (raw × (GS[k] × raw + GI[k]) + (S[k] × V / 1000 + I[k]))
```

After the kit changes range, Nordic's app replaces the next three samples with
a rolling average (weight 0.18; 0.06 in range 4, whose first two samples keep
the averages from before the change). The driver does the same unless
`spike_filter` is off.

---

## 4. What the bench's kit showed, 2026-11-14

With nothing wired. The script and its record are in
`2026-11-14_bench_check/`; ETB-SWE4-002 §13D has the table.

- **Metadata once per open.** The first `GET_METADATA` after the port opens is
  answered; a second in the same open is not, though the kit goes on streaming
  when asked. The driver asks once, on opening, and keeps the mode and voltage
  it sets itself from then on.
- **Closing the port takes the kit off USB** for about 0.7 s while it
  enumerates again. Its settings are kept: a voltage set before closing was
  still set after. The driver waits up to 3 s for a kit or port that is not
  there yet. (The record's "as found" step shows 1.8 V because a check just
  before it, made to find this out, left the kit at 1.8 V.)
- **The stream.** 10 000, 100 000 and 500 000 samples for 0.1, 1.0 and 5.0 s,
  none lost. Decoding in Python is slower than the stream, so the driver keeps
  the bytes and decodes after sampling stops; 5 s took 6.0 s in all.
- **Mode and voltage** took effect, each read back from the kit's metadata
  after reopening it.
- **Current with nothing wired**: within ±1 µA, except a peak of 0.72 mA when
  the DUT power was switched on at 1.8 V with VOUT open, taken to be the
  output's capacitance charging.
- **The logic inputs** read 255, all high, with nothing connected.
- The kit was left as found: source mode, 4.0 V, DUT power off.

---

## 5. Open items

| ID | Item | To close it |
|---|---|---|
| PPK-OPEN-01 | A current through a real load, against a reference, in each range: the calibration and the spike filter as the driver applies them | Wire a resistor across VOUT and GND (for example 3.3 kΩ, 330 Ω, 33 Ω at 3.3 V: 1 mA, 10 mA, 100 mA), measure with `benchtools ppk2` and with the TTi 1604 in series, and compare |
| PPK-OPEN-02 | The pulse figures on a real device's current | Power a sensor from the kit and measure its advertising pulses with `--threshold` |
| PPK-OPEN-03 | The logic inputs driven by a signal: which bit is which input, and their threshold | Drive D0 from the PICO2 Test Board's GP15 square wave and measure with `--line 0` |

---

## 6. Using it

```bash
python -m benchtools ppk2 list
python -m benchtools ppk2 -r ppk2:// info
python -m benchtools ppk2 -r ppk2:// measure --duration 1
python -m benchtools ppk2 -r ppk2:// --voltage-limit 3.3 voltage 3.0
python -m benchtools ppk2 -r ppk2:// mode source
python -m benchtools ppk2 -r ppk2:// power on
python -m benchtools ppk2 -r ppk2:// measure --duration 2 --threshold 0.001 --csv run.csv
```

`mode`, `voltage` and `power` change what the kit supplies: read what is wired
to it first. `specs/ppk2.yaml` is a worked specification, and
`docs/Bench_Runner_Guide.md` §5.6 lists the values a step reads.
