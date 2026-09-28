# ST S2-LP Development Kit — Integration Notes

| | |
|---|---|
| Hardware | STEVAL-FKI915V1 (915 MHz). The same driver serves FKI868V2, FKI433V2 and the X-NUCLEO-S2868A1/A2/S2915A1 expansion boards |
| Link | The kit's USB port, as a virtual COM port, 115200 8N1 |
| Firmware | **ST's own**, unchanged — the firmware the S2-LP DK GUI drives. Nothing from this repository runs on the board |
| Driver | `benchtools.instruments.s2lp.S2lpDevkit`, bench driver name `s2lp` |
| Status | Run against a kit on 2026-09-27 (#76): NUCLEO-L053R8, ST-LINK V2J47M34, ST's CLI firmware with S2-LP library 1.3.5, silicon 0xC1. Identification, every getter, register read and write, both resets, transmit and batch transmit (433.425 MHz, −10 dBm), and a receive or capture with nothing on the air were exercised. Reception of a real packet is still open (§7) |

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
against, are `u` (one byte), `v` (two), `w` (four) and `b` (a string). The power
level is read signed although ST declares it `w`, so the driver sends it with
its own letter `i`.

### 2.1 Replies, as a kit sends them

Recorded on 2026-09-27. The firmware echoes the command, answers, and prints a
`>` prompt with no line end:

```
S2LPRadioGetFrequencyBase
{{(S2LPRadioGetFrequencyBase)} API call...{value:31BF1BAD}}
>
```

A few replies run over several lines:

```
{{(SdkEvalSpiReadRegisters)} API callback...
{regs_list: 0x2E,0x20,0x2F,0x00}
{timer:055E5BB1}
}
```

What the driver relies on, each one learned from the kit or from a defect:

1. **A reply ends when the braces balance**, not after a fixed number of lines.
2. **Most getters answer in a tag called `value`.** A few name their fields, for
   example `S2LPRadioGetInfo` answers `{Frequency_base:…}{Modulation:…}{Data_rate:…}`.
   The tag names the driver was first written with (`frequency`, `board`,
   `xtal`, ...) came from reading ST's source, and were wrong.
3. **How a value is written depends on the command.** ST's `&tx`, `&t2x` and
   `&t4x` print 2, 4 and 8 hex digits with no `0x`. `&td` prints signed decimal,
   for example the PA level in **tenths** of a dBm (`{value:120}` is 12.0 dBm).
   `S2LPQiGetRssidBm` prints a float with its sign (`{value:-116.0}`). The
   driver picks the matching reader per command, because `{value:70}` is 0x70
   from one command and seventy from another.
4. **An interpreter error comes instead of a reply**, on one line:
   `no such command`, `wrong number of arguments`, `integer argument out of
   range`, `argument syntax error`, `string too long`, `invalid argument type`.
   The session fails at once, naming the command.
5. **The echo can run into the reply.** `SdkEvalRfboardIdentification`'s echo
   arrives cut short and without its line end, as in
   `SdkEvalRfboardIdo{{(SdkEvalRfboardIdentification)} API call...}`. The
   session splits the line at the reply's `{{`.
6. **The board timer is in microseconds.** It advanced 2,041,139 counts in
   2,043 ms of host time. It is 32 bits wide and wraps every 71.6 minutes.

One host-side fault looked like the firmware dropping characters. A stop's
acknowledgement arrived as `{{)} Acall...}`, and the next reply lost its opening
braces. The same exchange over a port left alone came back clean in 800 of 800
tries. The cause was the session setting the port's timeout on every read, which
reconfigures a serial port each time; on Windows that loses bytes, as it did for
the GPD-3303D in #61. The session now sets it once.

### 2.2 Stopping

A long-running command is stopped by sending the single character **`S`**, with
no terminator: the firmware polls the port for it inside its loops, and answers
`{{(StopCmd)} API call...}`. Two things about it were found on the kit:

* **An `S` sent to an idle board is not harmless.** It stays in the command
  buffer and turns the next command into `no such command`. The session waits
  for `StopCmd`; if none comes, it ends the line and swallows the error.
* **A stopped send acknowledges after the stop does:**
  `{{(StopCmd)} API call...}` then `{{(S2LPSendNBytes)} API call...}`. The
  session takes only the reply to the command it sent, and keeps any other as
  unclaimed.

---

## 3. Using it

### 3.1 From Python

```python
from benchtools.instruments.s2lp import S2lpDevkit

with S2lpDevkit.connect("/dev/ttyACM0",
                        board="STEVAL-FKI433V2",         # the firmware does not say
                        log_path="s2lp_session.log",
                        packet_log="s2lp_packets.jsonl") as radio:
    radio.configure_radio(frequency_hz=433_425_000, data_rate_bps=100_000,
                          modulation="2-fsk", deviation_hz=20_000,
                          bandwidth_hz=150_000)
    radio.set_power_dbm(-10)
    radio.configure_packets(preamble=64, sync_word=0xB19C0CA7, crc="16-8005",
                            variable_length=True)

    radio.transmit(b"ping")

    capture = radio.capture(count=20, timeout=60.0)
    print(capture.describe())
    for packet in capture.packets:
        print(packet)
```

Connecting identifies the firmware, the radio and its crystal, and **changes no
radio setting**: a kit somebody left configured is not retuned by a driver
attaching to it. The first send or receive routes the radio's interrupt (§4.4),
which does write two registers.

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
> `power_cycle()` goes through shutdown, which is the only thing that reaches
> bits a write cannot - though ST's firmware then sets ten registers on the way
> out (§4.5). This caught a
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
python -m benchtools s2lp -r /dev/ttyACM0 packets --sync 0xB19C0CA7 --crc 16-8005 --variable
python -m benchtools s2lp -r /dev/ttyACM0 tx 0x0102ff
python -m benchtools s2lp -r /dev/ttyACM0 --setup configs/s2lp_915_38k4_basic.regs tx ping
python -m benchtools s2lp -r /dev/ttyACM0 --board STEVAL-FKI433V2 info
python -m benchtools s2lp -r /dev/ttyACM0 --packet-log rx.jsonl capture --count 50
python -m benchtools s2lp -r sim:// registers                        # no kit needed
```

### 3.5 The two logs

They answer different questions, so both are kept.

| File | Contents | Question it answers |
|---|---|---|
| `--log` | Every line, both directions, host-timestamped, flushed per line — including lines the driver did not understand | What did the tooling actually do? |
| `--packet-log` | One JSON object per packet: direction, host time, board time in µs, length, hex, text, RSSI, error, and the firmware's extra fields | What did the radio carry? |

The packet log is JSON Lines rather than one document, so a capture interrupted
half way through is still readable — which is the usual case, since a capture is
usually interrupted on purpose. `radio.log_note(...)` writes into both.

---

### 3.6 Receiving the Kepler sensor

The Kepler (Kappa X) sensor transmits plaintext frames at 433.425 MHz. The bench
kit is the 433 MHz board (STEVAL-FKI433V2). `configs/s2lp_kepler_433_rx.regs`
holds the receive setup, captured from the kit after it was set up to the
sensor firmware's settings:

| | Value | Where the sensor sets it |
|---|---|---|
| Carrier | 433.425 MHz | `api_radio_transport_cfg.h` |
| Modulation | 2-FSK, 100 kbps, 20 kHz deviation, 150 kHz filter | same |
| Packet | basic; 32 bit-pairs of preamble (`S2LPPktBasicInit` argument 32); 32-bit sync `0xB19C0CA7`; variable length, one byte; one address byte; CRC-16 poly 0x8005 | same, and `api_radio_mac.c` |

```python
from benchtools.instruments.s2lp import S2lpDevkit
from benchtools.instruments.s2lp.kepler import decode_kepler_frame

with S2lpDevkit.connect("COM4", board="STEVAL-FKI433V2",
                        packet_log="kepler.jsonl") as radio:
    radio.apply_configuration("configs/s2lp_kepler_433_rx.regs", reset="defaults")
    for frame in radio.stream(decoder=decode_kepler_frame, timeout=900):
        print(frame)            # RX  35 bytes  -94.5 dBm  PQI 0 SQI 32  ALIVE  5c1712... (as seen)
```

```bash
python -m benchtools s2lp -r COM4 --board STEVAL-FKI433V2 --setup configs/s2lp_kepler_433_rx.regs stream --decode kepler --timeout 900 > frames.jsonl
```

`stream()` receives one frame at a time and reads registers straight after
each one: AFC correction, PQI, carrier sense with SQI, and RSSI by default, or
any set given with `registers=`. ST's firmware does not report PQI or SQI, so
reading them afterwards is the only way to get them. The cost is that the radio
is deaf while it is re-armed (§4.1). Each record in the packet log carries the
raw payload, the registers, the firmware's fields and the decode together.

**What the kit received on 2026-09-27.** Sensor 5C1712 sent ALIVE frames, each
packet three times (frame count repeat 0, 1 and 2), 33 ms and 130 ms apart, at
−94.5 dBm on the bench. The decode was coherent: 24.4 °C, 2540 mV, and SI-updated
set on the first repeat only, which matches the firmware clearing it once loaded.

Two points from the reference firmware were settled on the air:

* The payload in the FIFO starts at SENSOR_ID. The radio consumes the address
  byte and reports it separately.
* The address byte the sensor sends is **0xA7**. The reference project's own
  documents disagreed about this; it is the low byte of the secondary sync word
  sitting in PCKT_FLT_GOALS3.

**The polled stream's gap costs frames.** An 11-minute `stream` on the same
day received 5C1712's packet as all three repeats, 190 ms and 170 ms apart. For
5C314E it received repeats 0 and 1 only: repeat 2 fell in the re-arm gap. The
sensor spaces its repeats randomly, with gaps from 20 ms to 220 ms
(`api_radio_llc_cfg.h`). A 20 ms gap is shorter than the stream's register read
plus a command round trip, whereas ST's batch loop (`capture()`) caught all
three of 5C314E's repeats earlier the same day. So:

* use `stream()` when the per-frame registers matter;
* use `capture()` when missing a repeat matters more;
* in either case, count packets by repeat 0 or by any repeat, not by frames.

5C314E reports RF_CAP 4 (V10 firmware). Its ALIVE frames decode, with a warning
that the layouts are for RF_CAP 6.

**Frame types seen on the air (#85)**, all from 5C1712 on 2026-09-27, all
decoded without error:

| Type | How it was provoked | What it showed |
|---|---|---|
| ALIVE | periodic, every 10 minutes | as above |
| VERSION | BLE `ECURESET HARD`; arrived about 8 s after the ACK | `V11.00.0000`, SHA `bc97874`, reset reason 4 (RESETREAS.SREQ, a software reset), ticks 1 |
| CONFIG | follows a reset: 12 packets 45 s apart (mux 0 to 11), ahead of TWF | distance permutation; mux in order |
| TWF | BLE `WR TRIGGER`; started after the CONFIG cycle had finished | one packet every 45 s, packet count 256 (about 3.2 hours for a waveform). PARAM's SI type stepped 0, 1, 2, 3, 4 from packet to packet. The SI acceleration in packet 0 (145, 84, 93) agrees with the ALIVE RMS acceleration a minute later (147, 87, 95) |

Over a 15-minute polled stream, every one of 22 packets arrived at least once,
but only 14 arrived with all three repeats: 58 of 66 repeats in total. The
missed repeats were mostly the middle one, following the first too closely
(#84).

**Why rf_monitor misses so few frames (2026-09-28).** rf_monitor reads the log
written by ST's S2-LP DK GUI (`C:\Program Files\S2-LP_DK 1.3.5\GUI\S2-LP_DK.exe`).
The GUI's code is packed, so what it sends was read from the kit instead. The
firmware's input ring buffer was dumped from RAM over SWD
(`STM32_Programmer_CLI -c port=SWD mode=HOTPLUG -u 0x20000000 0x2000`), which
does not touch the COM port, while the GUI was receiving.

To start reception the GUI sends the following (reconstructed from the ring,
so the order is approximate):

```
S2LPPktBasicSetPayloadLength 20
S2LPTimerSetRxTimeoutUs 0            # no RX timeout
S2LPGetBatchLP 0                     # low-power receive off
SdkEvalLedHandler 3 1
S2LPGpioInit 3 3 0x00                # nIRQ on GPIO3, GPIO_MODE 3 (output, high power)
S2MGpioIrqConfiguration 3 1          # the board's interrupt on that line
S2LPIrq 0x00000001 1                 # RX data ready
S2LPIrq 0x00000002 1                 # RX data discarded
SdkEvalSpiWriteRegisters 0x18 {28}   # RSSI_TH, its reset value
S2LPGetNBytesBatch 0 4294967295      # ST's receive loop, effectively forever
```

After that it sends nothing: three RAM reads over 30 s found no new command.
The board re-arms the radio itself after every packet, and the only dead time
is the board printing its report (the GUI does not enable
`S2LPGetNBytesReportAll`, so the loop re-arms after printing).

| | Who re-arms | In each gap | Repeats received on the bench |
|---|---|---|---|
| GUI, feeding rf_monitor | the firmware loop | printing the report | "very few missed" (user) |
| `capture()` | the firmware loop, with ReportAll | less than the GUI: re-arms before printing | all, down to a 32 ms gap |
| `stream()` | the host, once per frame | report, a 14-17 ms register read, a new command | 58 of 66; shortest gap received 108 ms |

The losses come from `stream()` choosing per-frame PQI/SQI over the firmware
loop, not from the decoding. #87 bases `stream()` on the loop by default, and
#84 would give both through interrupt-driven firmware.

The GUI's setup also confirms two things this driver found independently:
nIRQ goes on GPIO3 with the register's own GPIO_MODE encoding, and the board's
interrupt is enabled on line 3.

FFT, FFT2, CMD and RESPONSE have not been seen on the air. They are tested
against frames built from the reference layouts.

---

## 4. What this firmware cannot do, and what the driver does about it

### 4.1 The radio is deaf while it is re-armed

`S2LPGetNBytes` arms the radio, waits, and returns. Between one call and the next
nothing is listening, and a packet arriving then is not merely lost — **nothing
anywhere records that it happened**.

ST's batch receive (`S2LPGetNBytesBatch`) is better but not gap-free: its loop
re-arms the radio after reading each packet out. The driver was first written
to call it continuous, and ST's source shows it is not. With
`S2LPGetNBytesReportAll 1`, which the driver turns on, the loop re-arms *before*
printing each report rather than after, so the gap no longer includes the time
the report takes to send.

So a capture records how often it re-armed, and who did it:

```python
capture = radio.capture(count=20, timeout=60.0)          # ST's batch loop
capture.rearm              # "firmware"
capture.gaps               # one fewer than the receptions
capture.rejected           # CRC and address-filter rejections, kept apart

polled = radio.capture(count=20, timeout=60.0, continuous=False)
polled.rearm               # "host": each gap includes a USB round trip
polled.describe()          # "... (19 host re-arm gap(s): not a complete record of the air)"
```

`is_continuous` is true only for a capture that never re-armed. A capture that
did supports "nothing was heard while listening", and nothing more.

### 4.2 Timestamps are microseconds, from the motherboard

`Packet.board_time_us` is the kit MCU's own timer, not a radio timestamp. It is
read when the firmware prints the report, after the packet has been read out of
the radio. It orders packets and times a sequence, and it is unwrapped across
the 32-bit counter's 71.6-minute wrap. It does not characterise a protocol's
timing. For timing at that level, the J-Link driver's four methods
(`docs/jlink/`) measure on the target instead.

### 4.3 A frequency the board cannot radiate is accepted by the radio

The S2-LP will tune anywhere in its range and report exactly what it was told,
while the board's filter and matching network pass only its own band. **The
firmware does not say which board it is on** (`SdkEvalRfboardIdentification`
answers with no tags), so the driver takes the board from the caller:

```python
radio = S2lpDevkit.connect("COM4", board="STEVAL-FKI915V1")
radio.set_frequency(868_000_000)
# ConfigurationError: 868.000 MHz is outside the STEVAL-FKI915V1 band this board
# is built for (902.0 to 928.0 MHz). ...
```

Without a board, only the synthesiser's own ranges (413–527 and 826–958 MHz)
are checked. The driver used to report `STEVAL-FKI915V1` for any kit that did
not say otherwise, which none does.

### 4.4 Sending and receiving need three things set up first

Each of these was found on the kit (#76). Each one on its own made a send wait
indefinitely.

1. **The radio's interrupt has to reach the board.** ST's send and receive wait
   for it, and out of reset nothing routes it. `prepare_traffic()` does so on the
   first send or receive:
   * it puts nIRQ on S2-LP GPIO3;
   * it unmasks the interrupts the firmware waits for;
   * it enables the board's input on that line (`S2MGpioIrqConfiguration 3 1`);
   * it checks that the board reads the line high.

   The GPIO mode is the register's own encoding, **2** for output. The CLI's help
   text numbers the modes one lower. Following the help made GPIO3 an input,
   which read back as `GPIO3_CONF = 0x01`, and no interrupt ever arrived. All
   four S2-LP GPIOs were confirmed to reach the board's pins one to one, by
   driving each high in turn and reading `S2MGpioGetValue`.
2. **The TX source has to be the FIFO.** PCKTCTRL1 powers up as 0x2C, with
   TXSOURCE = 3: a PN9 test pattern, which the radio sends for as long as it is
   left in TX, ignoring the FIFO. `configure_packets()` (ST's
   `S2LPPktBasicInit`) or a register file sets it to 0. Until then `transmit()`
   refuses. The shipped `configs/s2lp_915_38k4_basic.regs` set PCKTCTRL1 to
   0x2C, so it could never have transmitted; it now sets 0x20.
3. **PCKTLEN has to match the payload.** Given fewer bytes, the radio waits in
   TX for the rest. `transmit()` sets the length first when it differs.

A send that still never completes is stopped, the radio is aborted and its TX
FIFO flushed, and then the error is raised. The board is left usable.

Measured with all three in place, at 433.425 MHz, 100 kbps 2-FSK, −10 dBm:
five 8-byte sends at 24–33 ms each, host round trip included, and a batch of
five at 100 ms intervals in 0.53 s.

### 4.5 A power reset is not the datasheet's reset

`SdkEvalSdn 1` then `0` returns the radio's registers to power-on values, and
then ST's firmware writes ten of them on the way out of shutdown. On the kit
these were SYNT3, CLOCKREC1, FIFO_CONFIG3..0, CSMA_CONF3, FAST_RX_TIMER,
VCO_CONFIG and XO_RCO_CONF1 (`constants.AFTER_SHUTDOWN_EXIT`).
`apply_configuration(reset="power")` checks against that state.
`reset="defaults"` writes the datasheet values, including over those ten.

Reset checks look at writable registers only. RSSI, the interrupt flags and the
silicon version are never at a "reset value" on a live radio, and counting
them made every reset check fail on the kit.

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

| ID | Item | Status |
|---|---|---|
| S2LP-OPEN-01 | The **exact reply text** of each command on real firmware | **Closed**, 2026-09-27. Every getter, register read and write, strobe, identification, send, batch send, stop and interpreter error was recorded from the kit (§2). The simulator now answers with those shapes |
| S2LP-OPEN-02 | The **error codes** `S2LPGetNBytes` returns | **Partly closed.** ST's source gives 1 RX timeout, 2 CRC, 3 and 4 address filters, 6, and 0xFF for a stop. With nothing on the air the receive does not time out at all; it waits until stopped. The codes for a corrupted packet still need a transmitter |
| S2LP-OPEN-03 | Whether `SdkEvalRfboardIdentification` reports the **board name** | **Closed: it does not.** It answers with no tags. The board is now the caller's to name (`board=`, `--board`), and no default is assumed |
| S2LP-OPEN-04 | **`S2LPGetNBytesBatch`'s first argument** | Open. ST's source uses it as a reference timer in ms, with 0 meaning none; the driver passes 0. Needs traffic to confirm |
| S2LP-OPEN-05 | The **link budget in practice**: RSSI against a known transmitter, and the smallest re-arm gap | Partly closed, #77. The Kepler sensor on the bench arrives at −94.5 dBm, and ST's batch loop caught three repeats 33 ms apart. A register read takes 14–17 ms, which bounds a polled stream's gap from below. The gap of a polled stream has not been measured against a known sequence |
| S2LP-OPEN-07 | **PQI reads 0.** On 2026-09-27 a polled stream read LINK_QUALIF2 = 0 after each of three frames from 5C1712. The same frames gave SQI 32 (a full 32-bit sync match), RSSI_LEVEL 103 (-94.5 dBm) and AFC_CORR -12. It is not established whether PQI must be enabled or thresholded (QI register), or is not held after the packet the way RSSI is | Open. Check the datasheet's PQI definition, then read the QI register and PQI with a known preamble from the kit's own transmitter |
| S2LP-OPEN-06 | **Which board this kit is** | **Closed**, 2026-09-27: the 433 MHz board (STEVAL-FKI433V2), from its label. Recorded in `benches/lab1.yaml`. Reading it from the board is #80 |

---

## 8. What this driver does not do

Packet handler formats beyond basic (M-BUS and STACK), CSMA, auto-retransmission,
the low-duty-cycle and wake-up timer modes, and direct (unpacketised) RF are not
exposed as methods. All of them are **reachable through the registers**, which is
the point of holding the full map: `write_field` and `read_field` get to anything
the datasheet documents, without this driver having to grow an opinion about it
first.
