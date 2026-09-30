# TTi 1604 Multimeter — Interface Notes

Working notes for the `tti1604` driver: what the meter's interface is, where
each fact came from, and what has not been confirmed.

These notes exist because the 1604's protocol is not in its instruction manual.
The manual documents the *interface* — connector, pinout, line rate — and says
only that remote control is done with "optional Windows software". The command
set is in a separate document.

---

## 1. Sources

| Source | What it establishes | How it was read |
|---|---|---|
| *1604 Instruction Manual*, Issue 12 | Pinout and handshake requirement, 9600 baud, 2.5 readings/sec, 40 000 counts, `OFL` on overrange, that the RS-232 circuit stays powered when Operate is off | Read directly |
| *TTi 1604 Serial Control* | Key characters, the ten-byte frame layout, field bit positions, the echo-and-resend rule | Summary supplied by the project owner, not the manufacturer's text |
| `ddland/pythoncode`, `tti1604/tti1604.py` | Corroborates the segment patterns, the field bit positions and the DTR/RTS requirement | Read directly. MIT licence, Copyright (c) 2022 Derek Land |

No code from the third source is reproduced here. The protocol facts it
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
| Framing | 8 data bits, no parity, 1 stop bit |
| Connector | 9-way D-type, all connections made, screened cable for EMC |
| Flow control | None on the data path |
| Reading rate | 2.5 per second |

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

### 2.2 The interface is alive when the meter is "off"

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

---

## 4. The measurement frame

Ten bytes, emitted after every measurement while in remote mode.

| Byte | Contents |
|---|---|
| 0 | Carriage return — the only marker of where a frame begins |
| 1 | bits 0–2 measurement type, bit 3 AC, bits 4–6 range |
| 2 | T-Hold bit 0, Min-Max bit 2, Hz bit 4, Null bit 5, Auto bit 6 |
| 3 | bit 1 minus sign |
| 4–8 | Five display digits, seven-segment patterns |
| 9 | Double beep 0, auto-range 2, continuity buzzer 3, min 4, max 5, hold 6, gate 10 s 7 |

Measurement types: 1 mV, 2 V, 3 mA, 4 A, 5 ohms, 6 continuity, 7 diode test.

Ranges: 0 = 400 Ω; 1 = 4 kΩ / 4 V / 4 mA dc / 1 mA ac; 2 = 40 kΩ / 40 V / 10 A;
3 = 400 kΩ / 400 V / 400 mA / 400 mV; 4 = 4 MΩ / 750 V ac / 1000 V dc;
5 = 40 MΩ.

### 4.1 The digits are a segment bitmap

Bit 0 is the decimal point; bits 1–7 are the seven segments, arranged bit 7
top, 6 top-right, 5 bottom-right, 4 bottom, 3 bottom-left, 2 top-left, 1
middle.

The relationship that identifies the layout: `8` is `0xFE`, every segment lit,
and `0` is `0xFC`, that less the middle. `9` is drawn without its bottom
segment. Because it is a bitmap rather than a character code, the same five
bytes can carry letters — which is how `OFL` arrives, and why a decoder must
be ready for a reading that is not a number.

### 4.2 Ohms is displayed in kilohms

On every range but the 400 Ω one, the display reads kilohms — including the top
range, where 40 MΩ appears as `40000` kΩ. A single factor of 1000 therefore
covers ranges 1 to 5, which is only obviously right once the 40 000-count
display is taken into account. This was checked against the manual's count
rather than assumed from the reference implementation.

### 4.3 Frames and echoes share the link

Command echoes arrive interleaved with the measurement stream. They cannot be
found by scanning for the echoed character, because the seven-segment patterns
collide with the key characters exactly: `0x61` is the pattern for a `1`
carrying its decimal point, and it is also `a`, the Up key. An ordinary reading
of 1.0 volts contains one.

The driver therefore extracts complete frames first — self-delimiting, ten
bytes from a carriage return — and treats whatever remains as echo. Structure,
not value.

---

## 5. Not confirmed

Nothing below has been checked against a physical 1604. The driver has only
been run against its own simulator, which was written from the same
documentation and therefore cannot independently confirm any of it
(TB-RISK-001).

| ID | Open item |
|---|---|
| DMM-OPEN-01 | The segment patterns for characters beyond the ten digits and the letters listed. The table covers what the sources show; an unlisted pattern decodes to `?`. |
| DMM-OPEN-02 | The reading format in continuity and diode-test modes. Continuity is assumed to read ohms and diode test to read volts; neither is stated in the sources. |
| DMM-OPEN-03 | The echo's timing relative to the measurement stream, and whether an echo can be split across frames. The driver tolerates either, but the 300 ms resend window is taken from the summary, not measured. |
| DMM-OPEN-04 | Whether a range or function change emits one frame taken under the previous setting. `measure()` discards a reading on that assumption; if it is wrong, the discard costs 400 ms and nothing else. |
| DMM-OPEN-05 | Whether the data-bit framing is as stated. The instruction manual gives only the rate; 8N1 comes from the summary. |

Each of these is a reason a reading could be wrong in a way the test suite
cannot detect, because the simulator shares the driver's assumptions.

---

## 6. Using it

```sh
benchtools dmm -r /dev/ttyUSB0 read
benchtools dmm -r /dev/ttyUSB0 press ohms auto
benchtools dmm -r sim:// read -n 5 --reject-held
```

In a bench configuration:

```yaml
  dmm:
    driver: tti1604
    resource: /dev/ttyUSB0
    timeout: 5.0
```
