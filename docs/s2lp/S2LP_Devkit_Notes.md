# ST S2-LP Development Kit — Integration Notes

| | |
|---|---|
| Hardware | STEVAL-FKI915V1 (915 MHz). The same driver serves FKI868V2, FKI433V2 and the X-NUCLEO-S2868A1/A2/S2915A1 expansion boards |
| Link | The kit's USB port, as a virtual COM port, 115200 8N1 |
| Firmware | **ST's own**, unchanged — the firmware the S2-LP DK GUI drives. Nothing from this repository runs on the board |
| Driver | `benchtools.instruments.s2lp.S2lpDevkit`, bench driver name `s2lp` |
| Status | Verified against a simulated kit with a register file and a modelled air interface (SWE.4 §9). **No kit has been attached**: five bench confirmation items remain, §7 |

---

## 1. The firmware question, answered first

The instruction was to check ST's firmware before writing any. It was read
rather than assumed about, and it is fit for purpose.

The GUI does not talk to the S2-LP directly: it drives a **CLI application** on
the kit's MCU over the USB serial port. ST publishes that application's source at
[`STMicroelectronics/x-cube-subg2`](https://github.com/STMicroelectronics/x-cube-subg2),
under `Projects/NUCLEO-L053R8/Examples/S2868A1_CLI/`, whose README says it plainly:
"CLI example for S2-LP Expansion Board and S2-LP DK GUI."

Everything this project needs is already a command:

| Requirement | ST's command |
|---|---|
| Read any register | `SdkEvalSpiReadRegisters <addr> <count>` |
| Write any register | `SdkEvalSpiWriteRegisters <addr> { .. }` |
| Command strobes, FIFO access | `SdkEvalSpiCommandStrobes`, `SdkEvalSpiReadFifo`, `SdkEvalSpiWriteFifo` |
| Transmit | `S2LPSendNBytes { .. }`, `S2LPSendNBytesBatch <ms> <n> { .. }` |
| Receive | `S2LPGetNBytes <n>`, `S2LPGetNBytesBatch <ref> <n>` |
| Configure the radio | `S2LPRadioInit`, `S2LPRadioSetFrequencyBase`, `S2LPRadioSetModulation`, `S2LPRadioSetPALeveldBm`, … |
| Identify the board | `SdkEvalRfboardIdentification <xtal or 0>` |

So the decision (AD-20) was to use it unchanged and write only the host side.
Writing firmware would have added a build, a flashing procedure, a licence
question and a second thing to keep in step with the datasheet, in exchange for
nothing the measurement needs. It also means the kit works with ST's GUI and with
this driver without reflashing between them.

**What comes with that decision** is in §4. The limits are the firmware's, and
the driver's job is to be honest about them rather than to hide them.

---

## 2. The protocol

ASCII, one line per command, built on Ember's `command-interpreter2`.

```
SdkEvalSpiReadRegisters 46 4
S2LPSendNBytes {48 65 6C 6C 6F}
S2LPSendNBytes "Hello"
```

Integers are decimal or `0x`-prefixed. A byte string is `{ 08 A1 F2 }` in hex or
`"text"` in ASCII. ST's argument letters, which this driver checks every command
against, are `u` (one byte), `v` (two), `w` (four) and `b` (a string).

Replies are brace-delimited tags:

```
{{SdkEvalSpiReadRegisters} API callback...
{regs_list: 0x00,0x0A,0x01,0xA2}
{timer:000004D2}
}
```

Three things about replies are worth knowing, because two of them caused defects
here (D-32, D-33):

1. **A reply ends when the braces balance**, not after a fixed number of lines.
   Some commands answer on one line, some over six.
2. **Some tags are bare hex.** The firmware writes `{rssi:D4}` with a `%x`
   specifier and no `0x`. Read as decimal, `D4` is 4 — an RSSI wrong by 104 dB,
   and entirely plausible-looking.
3. **Some values are negative.** `S2LPQiGetRssidBm` answers in dBm, so `-110`
   arrives with its sign, and dropping it gives +110 dBm — impossible, and
   nothing downstream would question it.

A long-running command is stopped by sending the single character **`S`**, with
no terminator: the firmware polls the port for it inside its capture loops.

---

## 3. Using it

### 3.1 From Python

```python
from benchtools.instruments.s2lp import S2lpDevkit

with S2lpDevkit.connect("/dev/ttyACM0",
                        log_path="s2lp_session.log",
                        packet_log="s2lp_packets.jsonl") as radio:
    radio.configure_radio(frequency_hz=915_000_000, data_rate_bps=38_400,
                          modulation="2-gfsk-bt1")
    radio.set_payload_length(16)

    radio.transmit(b"ping")

    capture = radio.capture(count=20, timeout=60.0)
    print(capture.describe())
    for packet in capture.packets:
        print(packet)
```

Connecting identifies the board and **changes no radio setting**: a kit somebody
left configured is not retuned by a driver attaching to it.

### 3.2 Registers

```python
radio.read_register("PCKTCTRL3")            # by name
radio.read_register(0x2E)                   # or by address
radio.write_field("PCKTCTRL3", "PCKT_FRMT", 3)   # one field, rest untouched
print(radio.dump_registers())               # all 123, named and decoded
radio.registers_differing_from_reset()      # what has been configured
radio.strobe("flush_rx")
```

`write_field` reads, modifies and writes, so the register's other fields keep
their values — writing a field's value to the whole register is the mistake it
exists to prevent. A write to a read-only register is **refused**, because the
radio would accept it, discard it, and read back the old value, which looks like
the driver losing a setting.

### 3.3 Register values from a file

A test's required register values live in a file, not in the test. The person
who works out the settings is rarely the person writing the specification, and a
setting that moves should not need a code change.

```
# 915 MHz, 38.4 kbps, basic packets
PCKTCTRL3   0x20        # a space, '=', ':' or ',' all work
PCKTCTRL2 = 0x00
MOD2: 27                ; values are hexadecimal, 0x optional
0x11, 5A                // an address instead of a name
```

`configs/s2lp_915_38k4_basic.regs` is a worked example.

```python
radio.apply_configuration("configs/s2lp_915_38k4_basic.regs")     # write, then read back
check = radio.verify_configuration("configs/...", strict=False)   # check without writing
radio.save_configuration("captured.regs")                         # capture this radio
```

```bash
python -m benchtools s2lp -r /dev/ttyACM0 config configs/s2lp_915_38k4_basic.regs
python -m benchtools s2lp -r /dev/ttyACM0 config configs/s2lp_915_38k4_basic.regs --apply
python -m benchtools s2lp -r /dev/ttyACM0 config configs/s2lp_915_38k4_basic.regs --strict
python -m benchtools s2lp -r /dev/ttyACM0 config --save captured.regs
```

Verifying exits 1 on a mismatch, so a build step stops rather than measuring a
radio set up differently from the one the test specifies.

**Starting from a known radio.** A file that names some registers says nothing
about the others, so a partial file applied onto whatever was there before is
not deterministic:

```python
radio.apply_configuration(path, reset="defaults")   # write every default, then the file
radio.apply_configuration(path, reset="power")      # shutdown and back, then the file
```

```bash
python -m benchtools s2lp -r /dev/ttyACM0 config file.regs --apply --reset defaults
```

The reset is **confirmed by read-back** before the file is written: "the reset
was commanded" and "the radio is at defaults" are different facts, and the file
is written on top of the second one.

> **The `SRES` strobe does not do this.** ST's command header calls it a "reset
> of all digital part, except SPI registers", so `radio.reset()` leaves the
> radio configured exactly as it was. `restore_defaults()` writes the defaults;
> `power_cycle()` goes through shutdown, which is the only thing that genuinely
> returns every register - including bits a write cannot reach. This caught a
> defect in the simulator here (D-35), where SRES was modelled as a register
> reset and the tests agreed with it.

**Two checks, asking different questions:**

| | Loose (default) | Strict |
|---|---|---|
| Registers the file names | must match | must match |
| Registers it does not name | not examined | must be at their reset value |
| Answers | "is what this test needs set?" | "is the radio in exactly this configuration?" |

The strict check is what catches a register left set by whatever ran before it.
The loose one lets a file cover one aspect of a configuration without having to
describe the whole radio.

**What the file will not let you do**, each refused naming the file and the
line: name a register that does not exist, give a value that does not fit a
byte, set a read-only register (the radio would ignore the write and read back
its own value), set a register twice, or write a line that is not a setting. An
empty file is refused too — it would be applied and verified without doing
anything, and without saying so.

A `#define` line is **not** accepted, deliberately: distinguishing it from a
comment would mean `#` sometimes starting a comment and sometimes not, and a
format in which a typo turns a setting into a comment silently is worse than one
that refuses the line.

From a specification:

```yaml
setup:
  - do: s2lp.apply_configuration
    with: {source: configs/s2lp_915_38k4_basic.regs}

tests:
  - name: The radio holds the values this suite requires
    steps:
      - do: s2lp.verify_configuration
        with: {source: configs/s2lp_915_38k4_basic.regs, strict: true}
        expect: [{name: configured, measure: matches, equals: 1}]
```

`specs/radio_link.yaml` runs exactly that. Paths are relative to where the
runner is invoked, as bench paths are.

### 3.4 From the command line

```bash
python -m benchtools s2lp -r /dev/ttyACM0 info
python -m benchtools s2lp -r /dev/ttyACM0 registers --plain          # the whole map
python -m benchtools s2lp -r /dev/ttyACM0 registers PCKTCTRL3
python -m benchtools s2lp -r /dev/ttyACM0 registers PCKTCTRL3 --write 0xC0
python -m benchtools s2lp -r /dev/ttyACM0 config configs/s2lp_915_38k4_basic.regs --apply
python -m benchtools s2lp -r /dev/ttyACM0 radio --frequency 915000000 --rate 38400
python -m benchtools s2lp -r /dev/ttyACM0 tx 0x0102ff
python -m benchtools s2lp -r /dev/ttyACM0 --packet-log rx.jsonl capture --count 50
python -m benchtools s2lp -r sim:// registers                        # no kit needed
```

### 3.5 The two logs

They answer different questions, so both are kept.

| File | Contents | Question it answers |
|---|---|---|
| `--log` | Every line, both directions, host-timestamped, flushed per line — including lines the driver did not understand | What did the tooling actually do? |
| `--packet-log` | One JSON object per packet: direction, both clocks, length, hex, text, RSSI, error | What did the radio carry? |

The packet log is JSON Lines rather than one document, so a capture interrupted
half way through is still readable — which is the usual case, since a capture is
usually interrupted on purpose. `radio.log_note(...)` writes into both.

---

## 4. What this firmware cannot do, and what the driver does about it

### 4.1 Reception is polled, so the radio is deaf between calls

`S2LPGetNBytes` arms the radio, waits, and returns. Between one call and the next
nothing is listening, and a packet arriving then is not merely lost — **nothing
anywhere records that it happened**.

So a capture records how it was taken:

```python
capture = radio.capture(count=20, timeout=60.0)          # board-side loop
capture.is_continuous      # True: no re-arms during the capture
capture.gaps               # 0

polled = radio.capture(count=20, timeout=60.0, continuous=False)
polled.is_continuous       # False
polled.describe()          # "... (19 re-arm gap(s): not a complete record of the air)"
```

Only a continuous capture supports a statement about what was *not* transmitted.
A polled one supports "nothing was heard while listening", and nothing more.
Prefer `continuous=True`; it is the default.

### 4.2 Timestamps are milliseconds, from the motherboard

`Packet.board_time_ms` is the kit MCU's own timer, not a radio timestamp. It
orders packets and times a sequence. It does not characterise a protocol's
timing, and the field is named for its unit so that nobody quotes it as if it
did. For timing at that level, the J-Link driver's four methods
(`docs/jlink/`) measure on the target instead.

### 4.3 A frequency the board cannot radiate is accepted by the radio

The S2-LP will tune anywhere in its range and report exactly what it was told —
while the board's filter and matching network pass only its own band. The driver
refuses a frequency outside the band the **board reported**, rather than one
named in configuration:

```python
radio.set_frequency(868_000_000)
# ConfigurationError: 868.000 MHz is outside the STEVAL-FKI915V1 band this board
# is built for (902.0 to 928.0 MHz). The radio would accept it and transmit into
# a filter and matching network that do not pass it.
```

---

## 5. The register map

123 registers by name and address, with reset values, access and named bit
fields, in `benchtools/instruments/s2lp/registers.py`.

```
0x2E PCKTCTRL3              = 0xC0            PCKT_FRMT=3
0x2F PCKTCTRL2              = 0x07  (reset)   MBUS_3OF6_EN=1 MANCHESTER_EN=1 FIX_VAR_LEN=1
```

Reserved bits are not fields: anything the map names, the datasheet names. Field
descriptions are deliberately absent — they are the datasheet's prose, and the
datasheet is where they belong.

A full dump reads the map as **contiguous runs**: 15 commands instead of 123,
which at 115200 baud is the difference between instant and not.

---

## 6. Licence, and what is not in this repository

ST's software package is under **SLA0072**, a limited licence — not a permissive
one. This matters for what may be kept here:

* **Interoperating with the protocol is not redistribution.** The command names
  and argument shapes are recorded in `constants.COMMANDS` as the interface this
  driver targets, which is also what makes a drifted command fail in a test.
* **No ST source is vendored.** There is no copy of ST's headers, library or
  firmware in this repository.
* **The register map holds facts, not prose**: addresses, reset values, field
  names and bit positions, which are properties of the silicon published in the
  S2-LP datasheet. It was cross-checked against ST's published register header
  during development — 123 addresses, no collisions — and one register
  (`PA_CONFIG0`, 0x64) is listed with its address and no decoded fields, because
  the reference table documents none for it.

---

## 7. Bench confirmation items

Everything below needs a kit. None blocks using the driver.

| ID | Item | How to discharge it |
|---|---|---|
| S2LP-OPEN-01 | The **exact reply text** of each command on real firmware. The parser reads tags by name and keeps every line, so an extra or renamed tag is visible rather than fatal — but the tag names used here (`regs_list`, `bytes`, `rssi`, `error`, `timer`, `board`, `xtal`) come from ST's source, not from a board | Connect and run `python -m benchtools s2lp -r <port> -v -v info`, then compare the logged lines against `protocol.py`'s expectations |
| S2LP-OPEN-02 | The **error codes** `S2LPGetNBytes` returns. The driver treats any non-zero code as "nothing received" and records the code | Run a receive with no transmitter, and one with a deliberately corrupted packet; record both codes |
| S2LP-OPEN-03 | Whether `SdkEvalRfboardIdentification` reports the **board name** this driver expects. If it answers differently, `constants.BOARDS` needs that string — the band check depends on it | `python -m benchtools s2lp -r <port> info` and read `board` |
| S2LP-OPEN-04 | **`S2LPGetNBytesBatch`'s first argument.** ST's source takes it as a reference timer in ms, used by the low-power modes; this driver passes 0. Confirm 0 means "no reference timer" on hardware | Capture with 0, then with a value, and compare what arrives |
| S2LP-OPEN-05 | The **link budget in practice**: RSSI against a known transmitter, and the smallest re-arm gap a polled capture really has | Two kits, or one kit and a signal generator |

---

## 8. What this driver does not do

Packet handler formats beyond basic (M-BUS and STACK), CSMA, auto-retransmission,
the low-duty-cycle and wake-up timer modes, and direct (unpacketised) RF are not
exposed as methods. All of them are **reachable through the registers**, which is
the point of holding the full map: `write_field` and `read_field` get to anything
the datasheet documents, without this driver having to grow an opinion about it
first.
