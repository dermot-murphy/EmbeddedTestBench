# TTi 1604 Multimeter — Interface Notes

Working notes for the `tti1604` driver: what the meter's interface is, where
each fact came from, and what has not been confirmed.

These notes exist because the 1604's protocol is not in its instruction manual.
The manual documents the *interface* — connector, pinout, line rate — and says
only that remote control is done with "optional Windows software". The command
set is in a separate document, the manufacturer's *Remote Control Commands and
Logging Data Format* note, now kept in `reference/` beside these notes.

---

## 1. Sources

| Source | What it establishes | How it was read |
|---|---|---|
| *1604 Instruction Manual*, Issue 12 — `reference/TTi_1604_Instruction_Manual.pdf` | Pinout and handshake requirement, 9600 baud, 2.5 readings/sec, 40 000 counts, `OFL` on overrange, that the RS-232 circuit stays powered when Operate is off; the full scale and resolution of every range; the frequency gate | Read directly |
| *1604 Remote Control Commands and Logging Data Format*, V.1 23.04.98, amended 03.08.01 — `reference/TTi_1604_Remote_Control_Commands.pdf` | Key characters, the ten-byte frame layout, every field's bit positions, 8 data bits / 1 stop bit, the 300 ms echo-and-resend rule, and the worked example `12.345` = `96 219 242 102 182` | Read directly. The manufacturer's own text; it supersedes the summary below where they differ |
| *1604 Datasheet* — `reference/TTi_1604_Datasheet.pdf` | Ranges and accuracy, for reference | Read directly |
| *TTi 1604 Serial Control* | Key characters, the ten-byte frame layout, field bit positions, the echo-and-resend rule | Summary supplied by the project owner, not the manufacturer's text. Two of its bit positions were wrong (§4) |
| `ddland/pythoncode`, `tti1604/tti1604.py` | Corroborates the segment patterns, the field bit positions and the DTR/RTS requirement | Read directly. MIT licence, Copyright (c) 2022 Derek Land |

No code from the third-party source is reproduced here. The protocol facts it
demonstrates are recorded below in this project's own form, which is what
`DMM-NFR-004` requires.

Two sources agree independently on the load-bearing detail — the manual's
pinout requires DTR at +9 V and RTS at −9 V, and the reference implementation
sets `dtr = 1` and `rts = 0`. That agreement is why the driver states it as
fact rather than as a guess.

---

## 2. The link

| Property | Value |
|---|---|
| Rate | 9600 baud, fixed |
| Framing | 8 data bits, no parity, 1 stop bit (the remote-control note) |
| Connector | 9-way D-type on the back, straight-through cable with all connections made, screened for EMC |
| Flow control | None on the data path |
| Reading rate | 2.5 per second; once per gate (1 s or 10 s) measuring frequency |

### 2.1 The handshake lines are interface power

The RS-232 side is fully opto-isolated from the measurement system and is
powered by the host:

| Pin | Name | Description |
|---|---|---|
| 1 | DCD | Linked to DTR |
| 2 | TXD | Transmitted data from instrument |
| 3 | RXD | Received data to instrument |
| 4 | DTR | **Must be set to +9 V (logic 0)** |
| 5 | GND | Signal ground |
| 6 | DSR | Linked to DTR |
| 7 | RTS | **Must be set to −9 V (logic 1)** |
| 8 | CTS | Linked to RTS |
| 9 | GND | Signal ground |

A port opened with a serial library's defaults leaves the interface unpowered.
The meter then answers nothing, and every obvious diagnosis — wrong rate, bad
cable, dead instrument — is wrong. This is why `SerialTransport` grew `dtr` and
`rts` parameters rather than the driver setting them behind the transport's
back.

### 2.2 A USB converter may not reach the levels

The manual asks for ±9 V. Many USB-to-RS-232 converters drive the control
lines to only about ±5 V to ±6 V, which may or may not power the interface
(DMM-OPEN-07). If the meter never echoes, measure pins 4 and 7 against pin 5
with the port open before suspecting anything else.

### 2.3 The interface is alive when the meter is "off"

The Operate key switches DC power to the measurement circuits only. It does not
switch the AC supply, so the isolated RS-232 circuit stays powered. A meter
that is switched off still accepts key presses and echoes them; it simply never
produces a measurement.

The driver never presses Operate on the caller's behalf. The key toggles, so a
driver pressing it to "make sure the meter is on" switches off a meter that
already was — and because the link stays alive, that mistake does not present
as one.

---

## 3. Commands

Single ASCII characters, each standing for a front-panel key. Each is echoed;
an unechoed command was dropped and is resent after 300 ms.

| Key | Char | Key | Char |
|---|---|---|---|
| Up | `a` | Shift | `k` |
| Down | `b` | AC | `l` |
| Auto | `c` | DC | `m` |
| A | `d` | mV | `n` |
| mA | `e` | set remote | `u` |
| V | `f` | set local | `v` |
| Operate | `g` | | |
| Ohm | `i` | | |
| Hz | `j` | | |

There is no `h`. Nothing is streamed until `u` is sent.

### 3.1 An echo is not evidence

Some keys toggle — Auto/Man for certain — and an echo can be lost *after* the
meter acted on the key. Resending a toggle then undoes it, and the echo of the
resend says all is well. A key the meter refuses with a beep (Hz on a DC range)
is echoed all the same.

So the driver uses the echo only to pace keys. Every `select_*`,
`select_auto_range` and `set_range` call then waits for a *reading* that shows
the state asked for, and raises naming what the readings show if none does
(AD-25, DMM-FR-029, -030). `select_auto_range` presses nothing if the meter is
already auto-ranging; until #115 it toggled.

---

## 4. The measurement frame

Ten bytes, emitted after every measurement while in remote mode.

| Byte | Contents |
|---|---|
| 0 | Carriage return — the only marker of where a frame begins |
| 1 | bits 0–2 measurement type, bit 3 AC, bits 4–6 range |
| 2 | T-Hold **bit 1**, Min-Max bit 2, Hz bit 4, Null bit 5, Auto bit 6 |
| 3 | bit 1 minus sign |
| 4–8 | Five display digits, seven-segment patterns |
| 9 | Double beep 0, auto-range-set **bit 1**, continuity buzzer 3, min 4, max 5, hold 6, gate 10 s 7 |

The two bits in bold are as the manufacturer's note gives them. The driver had
T-Hold at bit 0 and auto-range-set at bit 2, from the summary; #115 corrected
both. A T-Hold display was therefore not reported as held.

Measurement types: 1 mV, 2 V, 3 mA, 4 A, 5 ohms, 6 continuity, 7 diode test.

Ranges: 0 = 400 Ω; 1 = 4 kΩ / 4 V / 4 mA dc / 1 mA ac; 2 = 40 kΩ / 40 V / 10 A;
3 = 400 kΩ / 400 V / 400 mA / 400 mV; 4 = 4 MΩ / 750 V ac / 1000 V dc;
5 = 40 MΩ. The note's AC current labels (1 mA, 100 mA) disagree with the
manual's specification (4 mA, 400 mA); the driver uses the manual's, and scales
from the display, so readings are unaffected.

### 4.1 The digits are a segment bitmap

Bit 0 is the decimal point; bits 1–7 are the seven segments, arranged bit 7
top, 6 top-right, 5 bottom-right, 4 bottom, 3 bottom-left, 2 top-left, 1
middle.

The relationship that identifies the layout: `8` is `0xFE`, every segment lit,
and `0` is `0xFC`, that less the middle. `9` is drawn without its bottom
segment. Because it is a bitmap rather than a character code, the same five
bytes can carry letters — which is how `OFL` arrives, and why a decoder must
be ready for a reading that is not a number.

### 4.2 The resistance multiplier is derived, not assumed

The frame says which resistance range is selected but not whether the display
is in ohms, kilohms or megohms. The driver divides the range's resolution in
the instruction manual by the value of the last displayed digit; the ratio must
be 1, 1 000 or 1 000 000. For example the 4 kΩ range resolves 0.1 Ω: `1.2345`
(four decimals) gives 1 000, kilohms; `1234.5` (one decimal) gives 1, ohms.
Either way the value is 1 234.5 Ω. A display that fits no multiplier carries no
value, and `Reading.problem` says why.

Until #115 the driver assumed kilohms on every range above 400 Ω. That is right
if the meter displays that way, and wrong by a factor of 1 000 if it shows
megohms on the top two ranges. Deriving it is right either way (DMM-OPEN-08).

### 4.3 Frames and echoes share the link

Command echoes arrive interleaved with the measurement stream. They cannot be
found by scanning for the echoed character, because the seven-segment patterns
collide with the key characters exactly: `0x61` is the pattern for a `1`
carrying its decimal point, and it is also `a`, the Up key; `0x66`, the
pattern for `4`, is `f`, the Volts key. An ordinary reading contains them.

The driver therefore extracts complete frames first — self-delimiting, ten
bytes from a carriage return — and treats whatever remains as echo. Structure,
not value. A frame candidate is also *validated*: every display byte must be a
pattern the meter draws, the units field must name a measurement, and there is
at most one decimal point. A carriage return that does not start such a frame
is passed over, so a reader that joins the stream part-way through a frame
resynchronises instead of decoding a plausible wrong number.

### 4.4 The link is a stream (#115)

Nothing the meter sends ends a message, so the driver reads whatever has
arrived (`Transport.read_available()`) and loops to its own deadline. Until
#115 it read with `read_raw()`, which waits for an end-of-message a serial port
never signals: on a real meter every read timed out with the bytes left unread,
and connecting always failed — with an error that blamed DTR and RTS.

The meter keeps streaming while nobody reads, and the operating system keeps
what it sends. `measure()` therefore discards everything waiting, the
operating system's buffer included, and the next frame too, and returns the one
after (AD-26).

The driver sets the serial timeout to a fixed short poll once and never varies
it: pyserial on Windows loses bytes whenever the timeout changes (LL-07).

---

## 5. Not confirmed

Nothing below has been checked against a physical 1604. The driver has been run
against its own simulator and over a serial loopback, which cannot
independently confirm any of it (TB-RISK-001). The bench test and the
front-panel check (§6.3, §6.4) exist to close these.

| ID | Open item | How to settle it |
|---|---|---|
| DMM-OPEN-01 | The segment patterns for characters beyond the ten digits and the letters listed, and whether a NUL follows each frame (the note calls the frame "null-terminated"). An unlisted pattern decodes to `?`; a NUL is ignored. | **Partly answered 2026-10-04** (TB-SYS5-002 §6.10): frames are 10 bytes between carriage returns, with **no** NUL after them. The overrange pattern is still unknown: an open input on ohms decoded as a blank `.` (#181) |
| DMM-OPEN-02 | The reading format in continuity and diode-test modes. Continuity is assumed to read ohms and diode test to read volts; neither is stated in the sources. | Select each by hand, then `benchtools dmm read` |
| DMM-OPEN-03 | The echo's timing relative to the measurement stream, and whether an echo can arrive inside a frame. The driver tolerates either: a split frame fails validation and is passed over, and the key is confirmed from the readings anyway. | The bench test's raw-stream record during key presses |
| DMM-OPEN-04 | Whether a range or function change emits one frame taken under the previous setting. `measure()` discards a frame on that assumption; if it is wrong, the discard costs 400 ms and nothing else. | The bench test's function tour timings |
| DMM-OPEN-05 | Whether the keys still work from the front panel in remote mode, whether there is a remote indicator, and the SHIFT combinations (Null, Hold, T-Hold, Min-Max, continuity, diode), which the note does not map. | Front-panel check, steps 1 and 12 |
| DMM-OPEN-06 | The frequency gate times. The manual's text gives the 4 kHz range the 10 s gate; its specification table has the gate times the other way round. The driver follows the text and waits long enough for either. | Bench test `test_the_frequency_gate`; front-panel check steps 9 and 10 |
| DMM-OPEN-07 | Whether the bench's USB-to-RS-232 converter drives DTR and RTS far enough to power the interface (§2.2). | **Closed 2026-10-04** (TB-SYS5-002 §6.10): with FTDI converter A9LQ0R81A, `test_keys_are_acknowledged_promptly` passed |
| DMM-OPEN-08 | Which display convention the meter uses on each resistance range. The driver derives the multiplier and so reads right either way; this records which it is. | Bench test `test_resistance` with a known resistor, which records the display |

The data-bit framing (8N1), formerly an open item, is stated in the
manufacturer's note and is closed.

---

## 6. Using it

### 6.1 From Python

```python
from benchtools.instruments.tti1604 import Tti1604

with Tti1604.connect("/dev/ttyUSB0") as dmm:      # COM6 on Windows
    dmm.select_milliamps()                        # confirmed from the readings
    dmm.select_dc()
    reading = dmm.measure()                       # measured after this call
    if not reading.is_live:
        raise SystemExit("overrange or frozen display: %s" % reading.text)
    print(reading.value, reading.unit, reading.range_label)

    dmm.set_range(0.4)                            # lock the 400 mA range
    dmm.select_auto_range()                       # and back; never toggles
```

Selecting a current function puts the meter's shunt across its input; the
driver never does so unless asked.

### 6.2 From the command line and a bench file

```sh
benchtools dmm -r /dev/ttyUSB0 read
benchtools dmm -r /dev/ttyUSB0 press ohms auto
benchtools dmm -r sim:// read -n 5 --reject-held
```

```yaml
  dmm:
    driver: tti1604
    resource: /dev/ttyUSB0
    timeout: 5.0
```

### 6.3 The bench test

`tests/bench/tti1604` exercises the driver against the real meter
(DMM-FR-080, SWE4-UT-DMMBENCH). It is outside the default test run and skips
unless the meter is named:

```sh
BENCHTOOLS_TTI1604=/dev/ttyUSB0 python -m pytest tests/bench/tti1604 -v
```

With the inputs open it checks the link, key echo, the raw stream and reading
rate, every frame decoding, the functions safe on an open input, every DC
voltage range, the frequency gate, OFL on open-circuit ohms, and local and
remote. Naming one wired reference — `BENCHTOOLS_TTI1604_DCV`, `_OHMS`, `_HZ`,
or `_DCI`, the only one that selects a current function — adds a measurement
against it. It writes `tti1604_bench_findings.md`, the record to attach when
closing DMM-OPEN items. See `tests/bench/tti1604/README.md`.

### 6.4 The front-panel check

```sh
python examples/12_dmm_front_panel_check.py /dev/ttyUSB0      # COM6 on Windows
```

Twelve steps, each changing the meter through the driver and saying what the
front panel should show; press Enter if it does, or type what it shows
instead. The answers and the driver's read-back go to a JSON log (DMM-FR-081).
The meter is left on DC volts, auto-ranging, in local mode however the run
ends. `sim://` dry-runs it.

### 6.5 Timing

| Operation | Typical duration |
|---|---|
| A reading | 0.4 s |
| `measure()` | 0.4 – 0.8 s |
| A key press | One echo round trip; 0.3 s per resend, three sends at most |
| A function or range change, confirmed | 1 – 2 s, most of it the meter's own |
| A frequency reading | 1 s on the 40 kHz range, 10 s on the 4 kHz range |
