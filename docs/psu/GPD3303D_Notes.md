# GW Instek GPD-3303D — Integration Notes

| | |
|---|---|
| Instrument | GW Instek GPD-3303D: two programmable channels, 30 V / 3 A each, plus a fixed 2.5 / 3.3 / 5 V, 3 A rail |
| Link | RS-232 (DB-9) or the rear USB port, which enumerates as a serial port |
| Driver | `benchtools.instruments.gpd3303d.Gpd3303D`, bench driver name `gpd3303d` |
| Status | Driver verified against a simulated supply with a load model (SWE.4 §10). **No GPD-3303D has been attached**: six bench confirmation items remain, §5 |

This is the supply of STK-13, used to power the sensor board whose radio and
firmware timing the rest of this repository measures. It is worth reading §1
before using it: four properties of this particular instrument decide the shape
of the driver, and all four are ways a test can record a number that is not
true.

**The third channel is not in this driver.** The fixed 2.5 / 3.3 / 5 V rail is
selected by a front-panel switch, and no command reaches it: a driver could not
set it, and could not read back which position the switch is in. Anything it
reported about that rail would be a repetition of what someone had typed into a
bench file, dressed up as an instrument reading. Power a rail from CH3 if it
suits the bench and record the switch position by hand, as you would any other
piece of wiring.

---

## 1. Four things this supply does that will mislead a test

### 1.1 It clamps a setting it cannot deliver

Ask for 35 V and the supply accepts the command, outputs 30 V, and answers
`VSET1?` with `30.000`. Nothing anywhere says it refused. A test that set 35 V
and then measured would pass, against a condition it never applied.

The driver refuses out-of-range settings **before** they are sent:

```python
psu.set_voltage(1, 35.0)
# ConfigurationError: a voltage of 35 V is outside what a GPD-3303D can
# deliver (0 to 30 V); the supply would clamp it silently
```

### 1.2 A channel in current limit is not at the voltage it was set to

Every linear supply does this and it is not a fault: when the load demands more
than the current limit, the supply stops holding the voltage and holds the
current instead. The rail then sits wherever the load puts it.

A 3.3 V rail with a 500 mA limit into a board that wants 1.5 A reads **1.0 V**.
That figure is real, plausible, and describes a circuit nobody asked for. It is
also the usual cause of a board that "randomly" resets, of firmware timings that
drift, and of radio results that make no sense.

So the mode travels with the numbers:

```python
reading = psu.read_channel(1)
if not reading.regulated:            # energised, in CV, and at setpoint
    raise SystemExit("rail %g V, mode %s - fix this before believing anything"
                     % (reading.voltage, reading.mode))
```

`regulated` is the line to assert on in a specification. `in_current_limit`
tells you which way it failed.

### 1.3 One output switch, two channels

`OUT1` and `OUT0` switch **both** channels. There is no per-channel output
command in this instrument's command set.

The driver presents per-channel control anyway, because every specification
wants it, and emulates it by programming a channel to zero volts and remembering
its setpoint (AD-19). The consequences are worth stating plainly:

| | |
|---|---|
| `output_off(1)` gives you | channel 1 at **0 V**, current limit unchanged |
| It does **not** give you | an open circuit, isolation, or a safety interlock |
| A board powered from elsewhere | can still back-feed into a channel that is "off" |
| `output_off` on *every* channel | opens the supply's real switch, so "all off" means off |
| `all_outputs_off()` | opens the real switch directly, whatever the channels are doing |

If a procedure needs the board genuinely disconnected, use `all_outputs_off()`
or pull the lead. Do not use `output_off(channel)`.

### 1.4 In series or parallel tracking, channel 2 is not a channel

The front panel selects independent, series or parallel tracking. In series and
parallel the supply drives CH2 from CH1 - and it **accepts and discards**
anything addressed to CH2. No error, nothing in `STATUS?`, and `VSET2?` answers
with whatever CH1 is set to, so a read-back agrees with nothing you sent.

```python
psu.set_voltage(2, 3.3)
# ConfigurationError: channel 2 cannot be set or switched on its own while the
# supply is in series tracking: it follows channel 1, and the supply would
# accept the setting and discard it. Use channel 1, or switch the supply to
# independent tracking on the front panel.
```

| While tracking | |
|---|---|
| `set_voltage(2, ...)`, `set_current_limit(2, ...)` | refused, naming the mode |
| `output_on(2)`, `output_off(2)` | refused — the per-channel switch is emulated by programming the channel to zero, so it is discarded too |
| Channel 1 | works normally; it is the master in both modes |
| `all_outputs_on/off()`, `reset()` | work in every mode: they act on the real switch and on CH1 |

The mode is read from the supply at each setting rather than cached, because it
is a switch on the front panel: it can move between one command and the next.
A mode the status word does not decode is **warned about and allowed** - the bit
order is itself a confirmation item (PSU-OPEN-01, PSU-OPEN-06), and one
unconfirmed bit should not leave the driver unable to set anything.

---

## 2. The command set

Not SCPI. The supply answers `*IDN?` and nothing else from IEEE 488.2 - no
`*RST`, no `*CLS`, no `SYSTem:ERRor?`.

| Command | Meaning |
|---|---|
| `*IDN?` | `GW INSTEK,GPD-3303D,SN:EW000000,V2.00` |
| `VSET<n>:<volts>` / `VSET<n>?` | set and read a channel's voltage setpoint |
| `ISET<n>:<amps>` / `ISET<n>?` | set and read a channel's current limit |
| `VOUT<n>?` / `IOUT<n>?` | measure output voltage and current; the reply may carry its unit (`3.300V`) |
| `OUT1` / `OUT0` | close and open the one output switch |
| `STATUS?` | eight characters, `0` or `1` — see below |
| `ERR?` | the last complaint, cleared by reading it |
| `TRACK<n>` | `0` independent, `1` series, `2` parallel. Read through `STATUS?`, never sent: which rails are tied together is a wiring decision, and a driver that changed it remotely could energise a board at twice the voltage the operator set up |
| `BEEP0` / `BEEP1`, `SAV<n>` / `RCL<n>`, `BAUD<n>` | not used by this driver |

Commands are terminated with a line feed; replies come back CR LF.

### 2.1 The status word

| Bit | Meaning |
|---|---|
| 0 | channel 1: `1` = CV, `0` = CC |
| 1 | channel 2: `1` = CV, `0` = CC |
| 2, 3 | tracking: `01` independent, `11` series, `10` parallel |
| 4 | beeper |
| 5 | output switch |
| 6, 7 | line rate: `00` 115200, `01` 57600, `10` 9600 |

`SupplyStatus` decodes all of it and keeps the raw reply, because the **order**
of those characters is the one thing that cannot be settled without the
instrument (PSU-OPEN-01).

---

## 3. Using it

### 3.1 From Python

```python
from benchtools.instruments.gpd3303d import Gpd3303D

with Gpd3303D.connect("/dev/ttyUSB0") as psu:        # COM4 on Windows
    psu.configure_channel(1, volts=3.3, current_limit=0.5)
    psu.output_on(1)

    reading = psu.read_channel(1)
    print("%.3f V  %.3f A  %s" % (reading.voltage, reading.current, reading.mode))
    assert reading.regulated, "the board is pulling more than 500 mA"
```

`connect()` identifies the supply and reads its status and **changes nothing**:
attaching a driver to a supply that is powering a board must not disturb the
board.

### 3.2 From the command line

```bash
python -m benchtools psu -r /dev/ttyUSB0 info
python -m benchtools psu -r /dev/ttyUSB0 set 1 -V 3.3 -I 0.5 --on
python -m benchtools psu -r /dev/ttyUSB0 read            # both channels
python -m benchtools psu -r /dev/ttyUSB0 off             # the real switch
python -m benchtools psu -r sim:// status                # no supply needed
```

`set` programs a channel and does **not** energise it; `--on` does that,
explicitly. `read` adds a `warning` key when a channel it read is in current
limit.

### 3.3 From a bench and a specification

```yaml
# benches/lab1.yaml
psu:
  driver: gpd3303d
  resource: /dev/ttyUSB0
  options: {baudrate: 9600, command_interval: 0.05}
```

```yaml
# specs/sensor_rails.yaml
- do: psu.read_channel
  with: {channel: 1}
  expect:
    - {name: rail, measure: voltage, nominal: 3.3, tolerance_percent: 2.0}
    - {name: regulated, measure: regulated, equals: 1}
```

`specs/sensor_rails.yaml` is a complete example. Run it **first** on any bench
session: every other measurement is taken on a board this supply is powering.

---

## 4. The link

| | |
|---|---|
| Default rate | 9600 baud, 8N1, no flow control |
| Other rates | 57600 and 115200, selected on the supply's front panel (Utility > Baud) and reported by `STATUS?` |
| Resource forms | `/dev/ttyUSB0`, `COM4`, `serial://COM4:57600`, `socket://terminal-server:4002`, `sim://` |

**Pacing.** The supply has a small input buffer and no flow control. Commands
sent back to back are accepted and acted on partially, and the failure is
silent: the next query answers perfectly well while the rail is not where the
test believes it is. The driver holds 50 ms between commands on a real link
(`command_interval`), and none at all on a simulated one.

If `STATUS?` comes back the wrong length, the line rate is almost certainly
wrong; the driver says so rather than decoding four characters into a confident
wrong answer.

---

## 5. Bench confirmation items

Everything below needs the instrument. None of it blocks using the driver; each
is a specific, short check.

| ID | Item | How to discharge it |
|---|---|---|
| PSU-OPEN-01 | The **bit order** of `STATUS?`. The decode follows the programming manual, first character as bit 0 | Connect, `python -m benchtools psu -r <port> status`, note `raw`; switch the output on and repeat. The character that changes is bit 5. If it is the third from the end rather than the third from the start, the reply is bit 7 first and `Gpd3303D.status` needs its string reversed |
| PSU-OPEN-02 | The wording and behaviour of `ERR?` | Send a deliberately bad command (`VSET3:1.000`), then `ERR?` twice. Confirm the text, and that the second read is clean. The driver carries the text verbatim either way |
| PSU-OPEN-03 | The command interval a real supply needs | Run a long sweep at 50 ms, confirm no setpoint is missed, then bisect downward. 50 ms is a conservative default, not a measured one |
| PSU-OPEN-04 | Settling time after a setpoint change | Step 0 V to 5 V and watch on the oscilloscope already on this bench. The driver does not wait; a specification that measures immediately after `set_voltage` should state its own `sleep` |
| PSU-OPEN-05 | Whether the supply discards a setpoint sent to the slaved channel **silently**, as modelled here | Front panel to series, then `VSET1:5.000`, `VSET2:1.000`, `VSET2?`, `ERR?`. The expectation is `5.000` and no error. The driver refuses the command either way, so only the sentence describing the supply is at stake |
| PSU-OPEN-06 | Whether the tracking bits are ordered as decoded (bit 2 then bit 3; `01` independent, `11` series, `10` parallel) | The same check as PSU-OPEN-01: move the front-panel switch through its three positions and watch characters 3 and 4 of `raw` |

## 6. What this driver does not do

**The fixed 2.5 / 3.3 / 5 V rail.** See the header: it is a front-panel switch,
not a remote control, and there is nothing about it a driver could measure.

**Changing the tracking mode.** `TRACK<n>` is never sent. The mode is read from
`STATUS?` and acted on - a supply left in series by a previous user is refused
rather than silently obeyed (§1.4) - but which rails are tied together is a
wiring decision. A driver that changed it remotely could put a board across two
channels in series at twice the voltage the operator set up, from a test script,
with the lid on.

**Memory save and recall, the beeper, and the front-panel lock** are not
implemented. Nothing in the bench's use of this supply needs them.
