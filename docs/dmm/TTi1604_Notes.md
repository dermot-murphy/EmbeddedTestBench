# TTi 1604 — Integration Notes

| | |
|---|---|
| Instrument | Thurlby Thandar Instruments (TTi) 1604: 40,000-count bench multimeter, DC/AC volts, DC/AC current, resistance, frequency, continuity, diode test |
| Link | RS-232 on a 9-way D-type at the back, opto-isolated, 9600 baud, reached through a USB-RS232 converter |
| Driver | `benchtools.instruments.tti1604.Tti1604`, bench driver name `tti1604` (alias `dmm1604`), command line `benchtools dmm` |
| Requirements | STK-18; DMM-FR-001 … -060, DMM-NFR-001 … -003 (SWE.1 §11); CORE-FR-018, -019 |
| Status | Driver verified against a simulated meter built from the manufacturer's documents (SWE4-UT-DMM, -DMMFRAME, -DMMSIM, -DMMCLI). **No 1604 has been attached**: seven bench confirmation items remain, §5 |
| Reference documents | `reference/TTi_1604_Datasheet.pdf`, `reference/TTi_1604_Instruction_Manual.pdf`, `reference/TTi_1604_Remote_Control_Commands.pdf` (V.1 23.04.98, amended 03.08.01) |

This is the current meter of STK-18. It is worth reading §1 before using it:
three properties of this particular instrument decide the shape of the driver,
and each is a way a test can record a number that is not true.

## 1. Three things this meter does that will mislead a test

### 1.1 It is driven by pretending to press its keys

There is no command set. Each front-panel key has a character (`'f'` Volts,
`'m'` DC, `'c'` Auto/Man, …); the meter echoes the character to acknowledge it,
and the manufacturer's note says to resend a key whose echo does not arrive
within 300 ms.

Some keys toggle - Auto/Man for certain - and an echo can be lost *after* the
meter acted on the key. Resending a toggle then undoes it, and the echo of the
resend says all is well. Some keys are refused with a beep (Hz on a DC range)
and echoed all the same.

So the driver never believes a key press. After selecting a function or a
range it waits for a reading that **shows** the state it asked for, and raises
if none arrives (AD-24, DMM-FR-020). The readings carry the function, range,
coupling and every annunciator, so they are the evidence.

### 1.2 It streams whether or not anyone is reading

In remote mode the meter sends a ten-character reading after every
measurement, 2.5 times a second. Between readings, nobody is listening but the
operating system, which keeps them. The next reading on the line can be minutes
old, and nothing in it says so - the frame carries no timestamp.

So a reading on request discards everything already received, including what
the operating system is holding, then discards the next complete frame too
(it may have been measured partly before the request), and returns the one
after (AD-25, DMM-FR-030). A fresh reading costs 0.4 - 0.8 s.

### 1.3 A reading is a picture of the display

Each frame is the five display characters as seven-segment patterns, plus the
annunciators. That has three consequences:

* **Held, recalled and relative displays look like numbers.** Hold and T-Hold
  freeze the display; Min/Max recall shows a stored value; Null subtracts one.
  The driver decodes every annunciator and `measure()` refuses a held or
  recalled reading, and a Null reading unless `allow_relative=True`
  (DMM-FR-031).
* **OFL is not a number.** It decodes as an overload, and `measure()` raises.
  Returning infinity would pass every lower limit.
* **Kilo and mega are annunciators the frame does not carry.** On resistance
  the multiplier is derived from the range's resolution in the manual and the
  position of the decimal point; a display that fits none is refused
  (DMM-FR-012, DMM-OPEN-02).

## 2. The interface

### 2.1 Wiring

A straight-through 9-way D-type cable **with all pins connected**; the meter
nulls the PC out itself. Pins at the meter:

| Pin | Name | Description |
|---|---|---|
| 1 | DCD | Linked to DTR |
| 2 | TXD | Transmitted data from instrument |
| 3 | RXD | Received data to instrument |
| 4 | DTR | From the host: must be **+9 V** (logic 0) |
| 5 | GND | Signal ground |
| 6 | DSR | Linked to DTR |
| 7 | RTS | From the host: must be **-9 V** (logic 1) |
| 8 | CTS | Linked to RTS |
| 9 | GND | Signal ground |

The interface is opto-isolated from the measurement circuits and **powered by
the host's DTR and RTS lines**. The driver holds DTR asserted and RTS negated
from the moment the port opens (CORE-FR-018). Signal grounds are connected to
the instrument's safety ground. Use a screened cable with screened connectors.

The RS-232 circuit stays powered whenever the meter has mains power, even with
Operate off; a meter in standby echoes keys and sends no readings, which the
driver reports as such.

### 2.2 Keys

| Key | Char | | Key | Char |
|---|---|---|---|---|
| Up | `a` | | Hz | `j` |
| Down | `b` | | Shift | `k` |
| Auto/Man | `c` | | AC | `l` |
| A (10 A socket) | `d` | | DC | `m` |
| mA | `e` | | mV | `n` |
| V | `f` | | Remote mode | `u` |
| Operate | `g` | | Local mode | `v` |
| Ohms | `i` | | | |

### 2.3 The reading frame

| Char | Meaning |
|---|---|
| 0 | CR - start of frame |
| 1 | Range: bits 0-2 units (1 mV, 2 V, 3 mA, 4 A, 5 ohm, 6 continuity, 7 diode), bit 3 AC, bits 4-6 range code |
| 2 | Function: bit 1 T-Hold, 2 Min/Max, 4 Hz, 5 Null, 6 Auto |
| 3 | Bit 1: minus sign |
| 4 - 8 | Display characters as seven-segment patterns; bit 0 set on the character left of the decimal point |
| 9 | Status: bit 0 double beep, 1 auto range set, 3 continuity buzz, 4 Min shown, 5 Max shown, 6 Hold, 7 10 s gate |

The note's own example: a display of `12.345` is sent as `96 219 242 102 182`
(the `2` is 218 + 1 for the decimal point). `tests/instruments/tti1604/test_frame.py`
starts from it.

## 3. Using it

### 3.1 From Python

```python
from benchtools.instruments.tti1604 import Function, Tti1604

with Tti1604.connect("/dev/ttyUSB1") as dmm:       # COM6 on Windows
    amps = dmm.measure_dc_current()                  # mA socket, autoranged
    volts = dmm.measure_dc_voltage()                 # the leads must be moved!

    dmm.select_function(Function.DC_MILLIAMPS)
    dmm.set_range(0.4)                               # lock the 400 mA range
    log = dmm.read_many(25)                          # ten seconds of readings
    print([reading.value for reading in log])
```

`read()` returns a `Reading` with every annunciator; `measure()` and the
`measure_*` methods return a float, and only a live one.

**Current is measured through a different socket.** `measure_dc_current()`
uses the mA socket (to 400 mA); `measure_dc_current(socket="10A")` the 10 A
socket. The driver cannot see where the leads are. It never selects a current
function unless one is named (DMM-NFR-002), because a current function puts the
meter's shunt across its input.

### 3.2 From the command line

```
benchtools dmm -r /dev/ttyUSB1 info
benchtools dmm -r /dev/ttyUSB1 measure dc_milliamps
benchtools dmm -r /dev/ttyUSB1 range 0.4
benchtools dmm -r /dev/ttyUSB1 log -n 25 --json log.json
benchtools dmm -r sim:// measure dc_volts          # no meter attached
```

Every sub-command prints JSON. `read` adds a `warning` when the reading is not
live.

### 3.3 From a bench and a specification

```yaml
# bench
instruments:
  dmm:
    driver: tti1604
    resource: /dev/ttyUSB1        # COM6 on Windows
    timeout: 5.0
```

```yaml
# specification step
- do: dmm.measure_dc_current
  measure:
    sensor_current: {limit: {max: 0.015}, units: A}
```

## 4. Timing

| Operation | Typical duration |
|---|---|
| A reading | 0.4 s (2.5 per second) |
| A fresh reading (`read()`, `measure()`) | 0.4 - 0.8 s |
| A key press | One echo round trip; 0.3 s per resend, five sends at most |
| A function or range change | 1 - 2 s, most of it the meter's own |
| A frequency reading | 1 s gate on the 40 kHz range, 10 s on the 4 kHz range |

## 5. Bench confirmation items

None of these block use of the driver. Each is either guarded - the driver
accepts both possibilities, or refuses rather than guesses - or affects only a
function the driver does not select.

| ID | Question | What the driver does meanwhile | How to settle it |
|---|---|---|---|
| DMM-OPEN-01 | The note calls the ten-character frame "null-terminated". Is an eleventh byte, NUL, sent? | Accepts it if present, does not require it. | Capture a few frames raw (`benchtools dmm -vv read`) and look for `00` after each. |
| DMM-OPEN-02 | On resistance, is the display in ohms, kilohms or megohms per range? The frame does not carry the annunciator. | Derives the multiplier from the range resolution and the decimal point; refuses a display that fits none. | Measure a known resistor on each range and compare. |
| DMM-OPEN-03 | The note labels the AC current ranges "1 mA" and "100 mA"; the manual's specification says 4 mA and 400 mA. | Uses the manual's labels. The value is scaled from the display, not the label, so readings are unaffected. | Select AC mA on each range and read the front panel. |
| DMM-OPEN-04 | The manual's text gives the 4 kHz range the 10 s gate; its specification table has the gate times the other way round. | Follows the text: gate flag set = 4 kHz, 0.1 Hz resolution. | Select Hz, press Down, and check which range the display and the gate flag show. |
| DMM-OPEN-05 | The SHIFT combinations (Null, Hold, T-Hold, Min/Max, Continuity, Diode, Reset) are not listed in the note; whether Hz toggles off with a second press; whether the front panel stays live in remote mode. | Does not use SHIFT. Leaves Hz by selecting another function. Decodes all annunciators, whoever set them. | Try each from the host with the meter in view. |
| DMM-OPEN-06 | Can the echo of a key arrive inside a frame, between its characters? | Looks for the echo only between frames. A split frame would fail validation and be dropped; the key would be resent and confirmed from the readings. | Log raw bytes during a burst of key presses. |
| DMM-OPEN-07 | Does the bench's USB-RS232 converter drive DTR to about +9 V and RTS to about -9 V? Some reach only +/-5 V, which may not power the isolated interface. | Reports a meter that never echoes with this as a named cause. | Measure pins 4 and 7 against pin 5 with the port open, or try the meter: if it echoes, the levels are enough. |

## 6. What this driver does not do

* **Continuity, diode test, Null, Hold, T-Hold, Min/Max** are not selected from
  the host (DMM-OPEN-05). They are decoded when an operator selects them, and
  `measure()` refuses the readings they produce unless they are live.
* **Operate** (standby) is not pressed: it toggles, and the driver would have no
  reading to confirm the result by when switching off.
* **Accuracy.** The value is what the display shows, to the display's
  resolution. The manual's accuracy figures apply to readings between 400 and
  4,000 counts; the driver reports the range with every reading so that a
  reviewer can apply them.
* **Thermal settling after 10 A.** The manual asks for ten minutes before a
  sensitive DC measurement after heavy current. That is a test-procedure
  matter, not a driver one.
