# Running the Bench Self-Check

How to set up a machine — Windows or Linux — to run `specs/bench_self_check.yaml`
against real instruments.

The self-check answers one question: *can this bench be reached and driven?* Run
it before a session, so that a broken link is found as a broken link rather than
as a confusing result about a board three tests later.

---

## 1. Before anything else: disconnect

> **DISCONNECT EVERYTHING FROM THE INSTRUMENTS BEFORE RUNNING THIS TEST.**
>
> Remove every sensor, board and lead from the supply, the multimeter, the
> oscilloscope and the debug probe.

The check energises the supply output and puts the meter on a current range,
which is a near short circuit across whatever it is connected to. Anything still
wired up is at risk.

The runner prints this warning before it opens the bench, and on real hardware it
**will not start** until you acknowledge it — see §6. The supply is driven to 1 V
at 100 mA, the gentlest setting it has, but that is a mitigation and not a
substitute for disconnecting.

---

## 2. What you need

| | |
|---|---|
| Python | 3.8 or later (`requires-python = ">=3.8"`) |
| This package | installed with the `spec` and `serial` extras |
| SEGGER J-Link software | only if the bench declares a `probe` |
| An ARM GDB | only if the bench declares a `probe` |

Nothing else. In particular **no VISA installation is required** — the
oscilloscope is reached over the built-in VXI-11 transport — and no vendor Python
package is needed for the debug probe.

### Install

```sh
python -m pip install -e ".[spec,serial]"
```

`spec` brings PyYAML, without which a `.yaml` specification cannot be read.
`serial` brings pyserial, without which the supply, the meter and the BLE dongle
cannot be opened. Both are optional extras precisely so that a machine using only
the LAN-connected oscilloscope need not install them.

---

## 3. Find the ports

This is the step that most often goes wrong, on both platforms, and it is worth
doing deliberately rather than guessing. The supply, the meter, the dongle and
the S2-LP kit are all serial devices, and on a machine with several attached
there is nothing in a port name that says which is which.

List what is present:

```sh
python -m serial.tools.list_ports -v
```

The `-v` matters: it prints the USB vendor/product strings and serial numbers
alongside each port, which is how you tell one USB-to-serial adapter from
another.

### Linux

Ports appear as `/dev/ttyUSB0`, `/dev/ttyUSB1`, … for USB-to-RS-232 adapters, and
`/dev/ttyACM0`, `/dev/ttyACM1`, … for devices presenting a USB CDC interface —
the Nordic dongle and the S2-LP kit among them.

**The numbering is assigned in the order devices are enumerated**, so it can
change between reboots, or if you unplug and replug something. If you intend to
run this regularly, bind the names with a `udev` rule keyed on the adapter's
serial number rather than relying on `ttyUSB0` staying the same device.

### Windows

Ports appear as `COM3`, `COM4`, … Device Manager lists them under *Ports (COM &
LPT)*, and the same caution applies: the number is assigned per adapter, and a
different USB socket can produce a different number.

`mode` at a command prompt also lists the COM ports that exist, though without
the USB identification that `list_ports -v` gives.

---

## 4. Permissions and drivers

### Linux: permission to open the port

Opening a serial port needs membership of the group that owns it. Check which
group that is rather than assuming — it is usually `dialout`, but not on every
distribution:

```sh
ls -l /dev/ttyUSB0
```

Then add yourself to whatever group the listing names, and **log out and back in**
for it to take effect:

```sh
sudo usermod -a -G <group> "$USER"
```

Without this, opening the port fails with a permission error that reads like the
device is missing.

### Linux: the J-Link probe

SEGGER's Linux package installs the `udev` rules that let a non-root user reach
the probe. If the probe is visible to `lsusb` but the GDB server cannot open it,
those rules are the usual reason.

### Windows: USB-to-serial drivers

Most adapters are FTDI or Silicon Labs CP210x and install from Windows Update. If
a device shows in Device Manager with a warning triangle rather than under *Ports
(COM & LPT)*, its driver is missing — install the one for that chipset before
going further.

### Both: the J-Link executables

The driver spawns a GDB server and an ARM GDB, and searches `PATH` for them by
name:

| Role | Names searched, in order |
|---|---|
| GDB server | `JLinkGDBServerCL.exe`, `JLinkGDBServer.exe`, `JLinkGDBServerCLExe`, `JLinkGDBServer` |
| GDB | `arm-none-eabi-gdb`, `arm-none-eabi-gdb.exe`, `gdb-multiarch`, `gdb` |

Confirm they are reachable:

```sh
# Linux
which JLinkGDBServer arm-none-eabi-gdb

# Windows (PowerShell)
Get-Command JLinkGDBServerCL.exe, arm-none-eabi-gdb.exe
```

On Windows the SEGGER installer does not always add its directory to `PATH`; add
it, or give the server's full path in the bench file.

---

## 5. Write the bench file

Copy `benches/lab1.yaml` and change the addresses to your own. The self-check
declares five aliases, and every one it names must exist in the bench file:

```yaml
name: My bench
instruments:
  psu:
    driver: gpd3303d
    resource: /dev/ttyUSB0        # COM4 on Windows
    timeout: 5.0
    options:
      baudrate: 9600              # must match the supply's front panel

  dmm:
    driver: tti1604
    resource: /dev/ttyUSB1        # COM5 on Windows
    timeout: 5.0

  scope:
    driver: tek3014b
    resource: 192.168.1.50
    timeout: 15.0

  probe:
    driver: jlink
    resource: jlink://
    timeout: 30.0
    options:
      device: nRF52840_xxAA       # required to start a GDB server

  dongle:
    driver: ble-dongle
    resource: /dev/ttyACM0        # COM5 on Windows
    timeout: 10.0
```

Three things to get right:

**Every serial device needs its own port.** Two aliases pointing at the same port
cannot both be opened. Use §3 to establish which adapter is which.

**The supply's baud rate must match its front panel** (*Utility > Baud*). The
driver reports what the supply thinks it is, but it cannot talk to it in the
first place at the wrong rate.

**The supply must be in INDEPENDENT tracking mode.** In series or parallel it
drives CH2 from CH1 and discards anything sent to CH2.

---

## 6. Run it

On a real bench the run stops until you confirm the warning:

```sh
python -m benchtools run specs/bench_self_check.yaml --bench benches/my_bench.yaml
```

The warning prints, then a prompt. **Only the full word `yes` continues** — `y`
does not, deliberately, because this is a warning about damaging equipment.

To run unattended — from a script, or where there is no terminal to answer at —
confirm up front:

```sh
python -m benchtools run specs/bench_self_check.yaml \
       --bench benches/my_bench.yaml --acknowledge
```

Without a terminal and without `--acknowledge`, the run **refuses to start** and
exits 3. Nothing is opened and nothing is energised.

### Try it with no hardware first

Worth doing before touching the bench, to prove the software side is sound:

```sh
python -m benchtools run specs/bench_self_check.yaml \
       --bench benches/simulated_bench.yaml
```

A simulated run is never gated, because nothing is energised. It should report
`PASS - 5 passed`.

### Keep the record

```sh
python -m benchtools run specs/bench_self_check.yaml \
       --bench benches/my_bench.yaml --acknowledge \
       --markdown self_check.md --json self_check.json
```

The report names every instrument that answered, with its identity — which is
what makes the check evidence rather than a green light.

---

## 7. Exit status

| Code | Meaning |
|---|---|
| 0 | Everything passed |
| 1 | A test failed or errored |
| 2 | Usage or specification error |
| 3 | The safety warning was not acknowledged; nothing was energised |

---

## 8. When it fails

| Symptom | Where to look |
|---|---|
| `could not open port` / permission denied | §4 — group membership on Linux, driver on Windows |
| The supply answers nothing | Baud rate against the front panel (§5) |
| **The meter answers nothing** | Its interface is powered by the handshake lines. The driver asserts DTR and clears RTS, so a working cable passes all nine pins straight through; a three-wire cable will not do. See `docs/dmm/TTi1604_Notes.md` §2.1 |
| `supply_regulating` fails | The supply left constant voltage, which means current is flowing — something is still connected. This is the check doing its job |
| The scope is unreachable | It is on the LAN, not USB: ping the address in the bench file |
| The probe fails to open | See the note below |

### The probe, with nothing attached

This is the one instrument whose behaviour with no target connected has **not
been confirmed**. The self-check asserts only that the probe link is open,
precisely so that it does not demand a target — but whether a J-Link GDB server
will start and stay up with no target attached is untested here.

If the probe alias is what fails, either attach the target board (with its
sensors still removed) or drop the `probe` alias from your bench file and from
the specification's `instruments` block. The other four instruments are
unaffected.

---

## 9. Related

* `docs/Bench_Runner_Guide.md` — the specification and bench formats in full,
  including `warning` and the acknowledgement gate
* `docs/dmm/TTi1604_Notes.md` — the multimeter's interface, pinout and open items
* `docs/psu/GPD3303D_Notes.md` — the supply's behaviour and open items
* `specs/bench_self_check.yaml` — the specification this document sets up
