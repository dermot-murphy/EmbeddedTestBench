# GPD-3303D Remote Control Interface Specification

*Automotive SPICE® PAM v4.0 | SYS.3 System Architectural Design (interface TB-SIF-02) and SWE.2 Software Architectural Design (interface specification)*

---

## 1. Document Identification & Control

| Field | Value | Field | Value |
|---|---|---|---|
| **Document ID** | TB-IF-001 | **Version** | 0.1 |
| **Project** | TestBench | **Date** | 2026-09-26 |
| **Status** | Draft | **Classification** | Internal |
| **Author** | Claude | **Reviewer** | Dermot Murphy |
| **Approver** | Dermot Murphy | **Related Process** | SYS.3, SWE.2 |

> **Note — Reviewer independence (TB-DEV-002):** The Reviewer and Approver are the same person (Dermot Murphy). This is accepted under deviation record **TB-DEV-002** (`docs/aspice/TestBench_DEV002_Independent_Review_Deviation.md`) on the basis that TestBench has a single human team member.

---

## 2. Revision History

| Version | Date | Author | Description of Change |
|---|---|---|---|
| 0.1 | 2026-09-26 | Claude | Initial. Written from a command-by-command capture of a real supply (#61, #64, #63). |

---

## 3. Purpose & Scope

### 3.1 Purpose

This document specifies the remote-control interface of the GW Instek
GPD-3303D bench power supply **as the instrument implements it**: the link, the
framing, every command TestBench uses, the replies the supply actually sends,
its error reporting, its resolution and its timing.

It exists because the first version of the driver was written from the
programming manual, and the manual's description differed from the instrument
in five places. Each one made the driver either fail outright or report a wrong
value. A driver passed 160 unit tests against a simulator built from the same
description and could not exchange one command with the real supply. The
specification below is the corrected description, and it records the evidence
for each statement.

It is the interface specification for system interface **TB-SIF-02**
(SE-HOST ↔ SE-PSU, TB-SYS3-001) and for the software element **PSU-ARC-001**
(TB-SWE2-001).

### 3.2 Scope

In scope: the serial command set of the two programmable channels, CH1 and CH2.

Out of scope: the fixed 2.5 / 3.3 / 5 V output. A front-panel switch selects
it, and no command reaches it. Also out of scope are commands TestBench never
sends (`TRACK<n>`, `SAV<n>`, `RCL<n>`, `BAUD<n>`), and the front panel itself.

### 3.3 Referenced Documents

| Document ID | Title | Version |
|---|---|---|
| TB-SYS3-001 | TestBench System Architecture | 0.1 |
| TB-SWE1-001 | TestBench Software Requirements Specification | 0.1 |
| TB-SWE2-001 | TestBench Software Architecture Description | 0.1 |
| TB-SWE3-001 | TestBench Software Detailed Design | 0.4 |
| TB-SWE3-002 | GPD-3303D Driver Design and Lessons Learned | 0.1 |
| — | GW Instek GPD-X303S Series User Manual, remote-control chapter | Manufacturer's |
| — | `docs/psu/GPD3303D_Notes.md` — usage notes for the driver | — |

### 3.4 Unit Under Observation

| Item | Value |
|---|---|
| Model | GPD-3303D |
| Identity string | `GW INSTEK,GPD-3303D,SN:GER916893,V1.09` |
| Firmware | V1.09 |
| Host port | `COM11`, enumerated as FTDI `VID_0403 PID_6001`, serial `A105X5XCA` |
| Line settings | 9600 baud, 8 data bits, no parity, 1 stop bit, no flow control |
| Front panel | Tracking INDEPENDENT; beeper off |
| Load | None. Nothing was connected to either output. |
| Date | 2026-09-26 |
| Capture tool | pyserial 3.5, with the port timeout set once and never reassigned (§10.2) |

### 3.5 Evidence Classes

Every behavioural statement carries one of these tags.

| Tag | Meaning |
|---|---|
| **[O]** | Observed on the unit in §3.4. The raw exchange is in Annex A. |
| **[M]** | Taken from the manufacturer's manual and not yet observed. |
| **[U]** | Unverified. Neither observed nor documented clearly enough to rely on. |

A statement tagged [M] or [U] is a candidate for a bench confirmation item
(§12), not a fact.

---

## 4. Physical and Link Layer

| Property | Value | Evidence |
|---|---|---|
| Electrical | USB, presenting a virtual COM port | [O] |
| USB identity on this bench | FTDI FT232-class, `VID_0403 PID_6001` | [O] |
| Line rate | 9600 baud | [O] |
| Other rates | 57600 and 115200, selected on the front panel (Utility > Baud) | [M] |
| Framing | 8N1 | [O] |
| Flow control | None, hardware or software | [O] (none configured; exchanges succeed) |
| Handshake lines | Not required: DTR and RTS were left as the driver found them | [O] |
| Line rate reported by the instrument | **No.** `STATUS?` does not carry it (§7). | [O] |

Whether the FTDI device is inside the supply or is an external USB-to-RS-232
adapter was not established. It makes no difference to this specification.

> **Identify the port before sending anything.** The bench host also carries a
> Nordic dongle (`VID_1915`) and an ST-LINK virtual COM port. During the
> investigation `*IDN?` and `STATUS?` were sent to the dongle's port by
> mistake; it answered `err 1 unknown command`. Select the port by USB identity.

---

## 5. Message Framing

| Rule | Detail | Evidence |
|---|---|---|
| Command terminator | Line feed, `0x0A` | [O] |
| CR LF | Also accepted as a terminator | [O] |
| CR alone | **Not** a terminator. A command ending in `0x0D` alone is not answered. | [O] |
| Reply terminator | **Carriage return alone, `0x0D`.** No line feed follows. | [O] |
| Echo | None | [O] |
| Case | Headers are case-insensitive: `vset1?` answers like `VSET1?` | [O] |
| Reply to a setting command | **None**, whether the setting was accepted or rejected | [O] |
| Reply to an unrecognised command | **None**. The error is recorded for `ERR?` (§8). | [O] |
| Multi-line reply | `STATUS?` only: three CR-terminated lines (§7) | [O] |
| Several commands on one line | Not tested | [U] |

**Consequence for a host.** A reader that waits for a line feed never receives
one, and every query times out. The host must send LF and read to CR. In
TestBench, `Transport.read_terminator` is set to `b"\r"` by the driver.

---

## 6. Command Reference

`<n>` is a channel number, `1` or `2`. Values are decimal ASCII, with no sign
and no exponent.

### 6.1 Identification

| Command | Reply (observed) | Evidence |
|---|---|---|
| `*IDN?` | `GW INSTEK,GPD-3303D,SN:GER916893,V1.09` | [O] |

The serial-number field carries the label `SN:`, which is part of the text and
not part of the number. No other IEEE 488.2 common command is implemented:
`*RST` and `*CLS` are unrecognised headers [O] (§8).

### 6.2 Setting

| Command | Effect | Reply | Evidence |
|---|---|---|---|
| `VSET<n>:<volts>` | Sets the channel's voltage setpoint, 0 to 30 V | none | [O] |
| `ISET<n>:<amps>` | Sets the channel's current limit, 0 to 3 A | none | [O] |
| `OUT1` | Closes the output switch — **both** channels | none | [O] |
| `OUT0` | Opens the output switch — both channels | none | [O] |
| `BEEP1` / `BEEP0` | Beeper on / off | none | [O] |

Observed values:

| Sent | `VSET1?` / `ISET1?` afterwards | `ERR?` afterwards | Evidence |
|---|---|---|---|
| `VSET1:1.234` | `1.2V` | — | [O] |
| `VSET1:12.345` | `12.3V` | — | [O] |
| `VSET1:5` | `5.0V` (integer form accepted) | — | [O] |
| `VSET1:30.000` | `30.0V` | `No Error.` | [O] |
| `VSET1:30.001` | `30.0V` | `No Error.` | [O] |
| `VSET1:5.000` then `VSET1:35.000` | `5.0V` — **unchanged** | `Data out of range.` | [O] |
| `VSET1:-1` | unchanged | `Invalid Character.` | [O] |
| `ISET1:0.200` then `ISET1:3.500` | `0.20A` — **unchanged** | `Data out of range.` | [O] |
| `ISET1:3.000` | `3.00A` | — | [O] |
| `ISET1:0.000` | `0.00A` | `No Error.` | [O] |
| `VSET3:1.000` | — | `Invalid Character.` | [O] |

**An out-of-range setting is rejected, not clamped.** The supply keeps its
previous setpoint, sends no reply, and reports the rejection only through
`ERR?`. A host that does not poll `ERR?` after every setting cannot tell. The
TestBench driver therefore refuses such a value before sending it (PSU-FR-002).

### 6.3 Reading back and measuring

| Command | Reply format | Example (observed) | Evidence |
|---|---|---|---|
| `VSET<n>?` | volts, one decimal, unit `V` | `3.6V` | [O] |
| `ISET<n>?` | amps, two decimals, unit `A` | `0.80A` | [O] |
| `VOUT<n>?` | measured volts, one decimal, unit `V` | `4.9V` | [O] |
| `IOUT<n>?` | measured amps, two decimals, unit `A` | `0.00A` | [O] |

The unit letter is always present in these replies [O]. A host should strip it
rather than assume it is absent.

### 6.4 Status and errors

| Command | Reply | Evidence |
|---|---|---|
| `STATUS?` | Three lines — see §7 | [O] |
| `ERR?` | One line of text — see §8 | [O] |

### 6.5 Not used by TestBench

| Command | Reason not used |
|---|---|
| `TRACK<n>` | Wiring the channels in series or parallel is the operator's decision. Changing it remotely could put twice the intended voltage on a board. The mode is only read, through `STATUS?`. |
| `SAV<n>`, `RCL<n>` | Stored front-panel setups: a hidden state that a test specification cannot see |
| `BAUD<n>` | Changing the line rate from the host cuts the link the command arrived on |
| `LOCAL`, `REMOTE` | Not tested [U] |

---

## 7. The Status Word

### 7.1 Reply format

Firmware V1.09 answers `STATUS?` with three CR-terminated lines [O]:

```text
0 0 0 1 0 X 0 X<CR>
bit0:(CH1)0=CC,1=CV;bit1:(CH2)0=CC,1=CV;bit23=(TRACK)01=INDEP,11=SER,10=PAR;<CR>
bit4:(BEEP)0=OFF,1=ON;bit6:(OUT)0=OFF,1=ON;<CR>
```

The first line holds eight fields separated by single spaces, one per bit,
**bit 0 first**. The second and third lines are the instrument's own legend,
sent every time. The whole reply is 137 bytes: about 143 ms at 9600 baud.

The manual prints the reply as eight characters with no spaces and no legend
[M]. A host should accept both forms. It must read the legend when it is sent:
left in the port, the two legend lines are taken as the replies to the next
two queries.

### 7.2 Bit assignments

| Bit | Field | Values | Evidence |
|---|---|---|---|
| 0 | CH1 mode | `1` CV, `0` CC | [O] |
| 1 | CH2 mode | `1` CV, `0` CC | [O] |
| 2, 3 | Tracking | written **bit 2 first**: `01` independent, `11` series, `10` parallel | [O] independent; [M] series and parallel |
| 4 | Beeper | `1` on, `0` off | [O] |
| 5 | — | always `X` | [O] |
| 6 | Output switch | `1` closed (on), `0` open (off) | [O] |
| 7 | — | always `X` | [O] |

### 7.3 Observed transitions

| State | Line 1 | Evidence |
|---|---|---|
| Output off, beeper off, independent | `0 0 0 1 0 X 0 X` | [O] |
| After `BEEP1` | `0 0 0 1 1 X 0 X` | [O] |
| After `OUT1`, no load | `1 1 0 1 0 X 1 X` | [O] |
| After `OUT0` | `0 0 0 1 0 X 0 X` | [O] |

**Mode bits while the output is off.** Both channels report `0` — CC — whenever
the output switch is open [O]. That is not a channel in current limit, and a
host must not report it as one. TestBench's `ChannelReading.in_current_limit`
requires the channel to be on.

**Reading the tracking bits.** The legend writes the pair as a two-digit
string, bit 2 on the left. Read as a binary number with bit 2 as the least
significant digit, which is how the first driver read it, independent (`01`)
decodes as parallel. The driver would then refuse every CH2 command on a
supply that was correctly set up.

---

## 8. Error Reporting

### 8.1 Mechanism

`ERR?` returns the most recent error as one line of text and clears it: a
second `ERR?` returns `No Error.` [O]. An error is held until it is read, so an
error from an earlier session can still be there when the next one starts [O].
There is no error queue, and there is no status byte.

### 8.2 Observed error texts

| Text | Raised by (observed) | Evidence |
|---|---|---|
| `No Error.` | Nothing outstanding | [O] |
| `Invalid Character.` | A channel number the supply does not have in a setting (`VSET3:1.000`); a minus sign in a value (`VSET1:-1`) | [O] |
| `Data out of range.` | A value above the channel's rating (`VSET1:35.000`, `ISET1:3.500`) | [O] |
| `Undefined Header.` | An unknown header (`NONSENSE`); a query naming a channel the supply does not have (`VOUT3?`); `*RST`; `*CLS`; `SYST:ERR?` | [O] |

In every case above the supply sends **nothing** in reply to the offending
command, and it leaves its settings unchanged [O]. A host that sends an
unrecognised query waits out its timeout.

### 8.3 Settings the supply accepts and discards

In series and parallel tracking the manual has CH2 follow CH1 [M]. Whether a
`VSET2:`/`ISET2:` sent in those modes is discarded silently or leaves an error
has not been observed [U] (PSU-OPEN-05). TestBench refuses such a setting
whatever the answer.

---

## 9. Resolution and Rounding

### 9.1 Programming

Values are accepted with up to three decimals [O]. The setting resolution
inside the supply is not directly observable: the supply reads values back more
coarsely than it accepts them (§9.2), and nothing was connected to measure
against. It is recorded as [U] for current, where 1 mA and 10 mA both fit what
was seen.

### 9.2 Read-back

| Quantity | Read-back step | Rounding observed | Evidence |
|---|---|---|---|
| `VSET<n>?` | 0.1 V | Half up: `3.25` → `3.3V`, `3.249` → `3.2V`, `3.35` → `3.4V` | [O] |
| `ISET<n>?` | 0.01 A | `0.123` → `0.12A`, `0.005` → `0.01A`, `0.004` → `0.00A`, `0.015` → `0.02A`, `0.019` → `0.02A` | [O] |
| `VOUT<n>?` | 0.1 V | Unloaded, it reads 0.1 V below the read-back setpoint on every sample: 3.6 → `3.5V`, 5.0 → `4.9V`, 3.3 → `3.2V`, 3.25 → `3.2V` | [O] |
| `IOUT<n>?` | 0.01 A | Only `0.00A` seen: no load was connected | [O] |

Whether `VOUT` truncates or the output genuinely sits just below its setpoint
cannot be told without an independent meter [U]. Either way a host comparing a
measurement with a setpoint must allow at least one read-back step. TestBench
allows 1.5 steps or 1 %, whichever is larger (`ChannelReading.regulated`).

---

## 10. Timing

### 10.1 Reply latency

Measured from the end of the host's write to the first reply byte, including
the time on the wire (about 1.04 ms per character at 9600 baud) [O]:

| Query | Reply length | Latency to first byte |
|---|---|---|
| `VSET<n>?`, `ISET<n>?`, `VOUT<n>?`, `IOUT<n>?` | 5–6 bytes | 17–30 ms |
| `ERR?` | 10–19 bytes | 25–43 ms |
| `STATUS?` | 137 bytes | 28–41 ms to the first byte, about 143 ms to the last |
| `*IDN?` | 39 bytes | 58 ms |

### 10.2 Command spacing

With the host fixed as described below, the supply took the next command at
every spacing tried, from 0 ms to 200 ms after the end of the previous reply:
108 of 108 exchanges, across `*IDN?`, `STATUS?` and `VSET1?` [O]. A
**minimum** spacing has therefore not been found. The TestBench driver keeps its
conservative 50 ms (`DEFAULT_COMMAND_INTERVAL`) until a long sweep establishes
otherwise (PSU-OPEN-03).

> **A host-side fault that looks like the instrument dropping commands.**
> pyserial reconfigures the port every time its `timeout` attribute is
> assigned, even to the value it already has. On Windows, through this FTDI
> port, doing that before each read lost about one reply in five. The loss
> looked random and did not depend on command spacing. An earlier TestBench
> transport did exactly this, and the symptom was blamed on the supply until a
> raw capture changed only that one variable. With the timeout set once,
> 108/108 exchanges succeeded; with it set before each read, about 80 %.
> Hosts must set the timeout only when it changes.

### 10.3 Settling

Settling time after a setpoint change has not been measured (PSU-OPEN-04). The
supply does not signal when an output has settled.

---

## 11. Interface Requirements on a Host

These follow from §§5–10 and are the constraints the TestBench driver meets.

| # | A host shall … | Because | Met by |
|---|---|---|---|
| IF-01 | send LF-terminated commands and read CR-terminated replies | §5 | `Transport.read_terminator`, set in `Gpd3303D.__init__` |
| IF-02 | read the whole `STATUS?` reply, including the legend | §7.1 | `Gpd3303D._read_status_legend` |
| IF-03 | decode the output switch from bit 6, and the tracking pair bit 2 first | §7.2 | `Gpd3303D.status` |
| IF-04 | not treat the CC bits as current limiting while the output is off | §7.3 | `ChannelReading.in_current_limit` |
| IF-05 | refuse out-of-range values itself, or poll `ERR?` after each setting | §6.2 | `Gpd3303D._check_range` (PSU-FR-002) |
| IF-06 | compare measurements with setpoints to at least one read-back step | §9.2 | `ChannelReading.regulated` (PSU-FR-023) |
| IF-07 | not wait for a reply to a setting command | §5 | `Gpd3303D._write` |
| IF-08 | not reassign the serial timeout on every read | §10.2 | `SerialTransport._recv_chunk` |
| IF-09 | treat the output switch as common to both channels | §6.2 | per-channel emulation, AD-19 |

---

## 12. Open Items

| ID | Item | Status |
|---|---|---|
| PSU-OPEN-01 | Bit order of `STATUS?` | **Closed 2026-09-26** — bit 0 first; output at bit 6 (§7) |
| PSU-OPEN-02 | Text and behaviour of `ERR?` | **Closed 2026-09-26** — §8 |
| PSU-OPEN-03 | Minimum command spacing | Open. No failure seen from 0 ms up (§10.2); a long sweep still to be run |
| PSU-OPEN-04 | Settling time after a setpoint change | Open |
| PSU-OPEN-05 | Whether a setting sent to the slaved channel leaves an error | Open — needs the front panel in series |
| PSU-OPEN-06 | Tracking bit pattern | Independent confirmed; series and parallel open |
| IF-OPEN-07 | Current programming resolution: 1 mA or 10 mA | Open — needs a load and a meter (§9.1) |
| IF-OPEN-08 | Whether `VOUT` truncates or the output sits below setpoint | Open — needs an independent meter (§9.2) |
| IF-OPEN-09 | Behaviour of other firmware versions | Open — only V1.09 has been seen. The driver accepts both `STATUS?` forms. |

---

## Annex A — Captured Exchange

Captured on the unit in §3.4, 2026-09-26, with outputs off except for the
`OUT1` / `OUT0` pair and nothing connected. `-` means no reply within 600 ms.
Replies are shown as Python byte literals: `\r` is the carriage return that ends
each one. Latency is to the first reply byte.

```text
Command          Latency  Reply
OUT0             -        b''
ERR?             43 ms    b'Invalid Character.\r'        <- held over from an earlier session
*IDN?            58 ms    b'GW INSTEK,GPD-3303D,SN:GER916893,V1.09\r'
STATUS?          41 ms    b'0 0 0 1 0 X 0 X\rbit0:(CH1)0=CC,1=CV;bit1:(CH2)0=CC,1=CV;bit23=(TRACK)01=INDEP,11=SER,10=PAR;\rbit4:(BEEP)0=OFF,1=ON;bit6:(OUT)0=OFF,1=ON;\r'
VSET1?           25 ms    b'0.0V\r'
VSET2?           25 ms    b'3.3V\r'
ISET1?           25 ms    b'0.20A\r'
ISET2?           25 ms    b'0.10A\r'
VOUT1?           25 ms    b'0.0V\r'
VOUT2?           24 ms    b'0.0V\r'
IOUT1?           26 ms    b'0.00A\r'
IOUT2?           25 ms    b'0.00A\r'
VSET1:1.234      -        b''
VSET1?           20 ms    b'1.2V\r'
VSET1:12.345     -        b''
VSET1?           30 ms    b'12.3V\r'
VSET1:30.000     -        b''
VSET1?           17 ms    b'30.0V\r'
VSET1:-1         -        b''
VSET1?           22 ms    b'30.0V\r'
ERR?             41 ms    b'Invalid Character.\r'
ISET1:0.005      -        b''
ISET1?           20 ms    b'0.01A\r'
ISET1:3.000      -        b''
ISET1?           29 ms    b'3.00A\r'
VSET1:5          -        b''
VSET1?           19 ms    b'5.0V\r'
vset1?           25 ms    b'5.0V\r'
VSET3:1.000      -        b''
ERR?             33 ms    b'Invalid Character.\r'
ERR?             25 ms    b'No Error.\r'
VOUT3?           -        b''
ERR?             31 ms    b'Undefined Header.\r'
NONSENSE         -        b''
ERR?             37 ms    b'Undefined Header.\r'
*RST             -        b''
ERR?             29 ms    b'Undefined Header.\r'
*CLS             -        b''
ERR?             36 ms    b'Undefined Header.\r'
SYST:ERR?        -        b''
ERR?             32 ms    b'Undefined Header.\r'
BEEP1            -        b''
STATUS?          38 ms    b'0 0 0 1 1 X 0 X\r...legend...\r'
BEEP0            -        b''
STATUS?          38 ms    b'0 0 0 1 0 X 0 X\r...legend...\r'
VSET1:5.000      -        b''
ISET1:0.200      -        b''
VSET2:3.300      -        b''
ISET2:0.100      -        b''
OUT1             -        b''
STATUS?          28 ms    b'1 1 0 1 0 X 1 X\r...legend...\r'
VOUT1?           25 ms    b'4.9V\r'
VOUT2?           25 ms    b'3.2V\r'
IOUT1?           25 ms    b'0.00A\r'
IOUT2?           25 ms    b'0.00A\r'
OUT0             -        b''
STATUS?          29 ms    b'0 0 0 1 0 X 0 X\r...legend...\r'
VOUT1?           25 ms    b'0.0V\r'
ERR?             25 ms    b'No Error.\r'
```

Out-of-range behaviour, captured separately so that the previous setpoint was
distinguishable from the limit:

```text
ERR?           b'No Error.\r'
VSET1:5.000    (no reply)
VSET1?         b'5.0V\r'
VSET1:35.000   (no reply)
VSET1?         b'5.0V\r'
ERR?           b'Data out of range.\r'
VSET1:30.001   (no reply)
VSET1?         b'30.0V\r'
ERR?           b'No Error.\r'
ISET1:0.200    (no reply)
ISET1?         b'0.20A\r'
ISET1:3.500    (no reply)
ISET1?         b'0.20A\r'
ERR?           b'Data out of range.\r'
ISET1:0.004    (no reply)
ISET1?         b'0.00A\r'
ISET1:0.015    (no reply)
ISET1?         b'0.02A\r'
ISET1:0.019    (no reply)
ISET1?         b'0.02A\r'
VSET1:3.25     (no reply)
VSET1?         b'3.3V\r'
VSET1:3.35     (no reply)
VSET1?         b'3.4V\r'
```

An earlier capture, in which `VSET1:35.000` followed a setting of exactly
30 V, read back `30.0V`. That reading fits both "clamped" and "rejected", and
it nearly confirmed the wrong one. The capture above starts from 5 V so that the
two outcomes differ.
