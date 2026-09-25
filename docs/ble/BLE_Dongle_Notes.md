# Nordic BLE Bench Dongle — Integration Notes

| Field | Value |
|---|---|
| Document ID | BENCHTOOLS-BLE-001 |
| Version | 1.2 |
| Date | 2026-09-13 |
| Element | `BLE-` — `benchtools.instruments.nordic_dongle` + `firmware/nordic_dongle` |
| Firmware target | nRF52840 USB dongle (PCA10059), S140 7.2.0, nRF5 SDK 17.1.0, SEGGER Embedded Studio |
| Status | Host driver verified against a simulated dongle. Firmware has 131 unit tests (§5.1) and **compiles** against real SDK headers (§5.2); not yet linked, flashed or run |

The engineering note for the BLE dongle: why it needs firmware of its own, what
the protocol is, how to build and flash it, how to read the numbers it produces,
and what remains unproven.

---

## 1. Why custom firmware, and not `ble_connectivity`

Nordic ships a serialisation firmware (`ble_connectivity`) with a Python host
library (`pc-ble-driver-py`) that puts the whole BLE API on the host. It was
rejected, and the reason is the entire point of this element.

With that arrangement the BLE stack runs on the **host** side of a USB link. A
timestamp for an advertising report is taken when the host's Python gets around
to it: after USB polling (up to 1 ms), after the OS scheduler, after the
serialisation layer. That is a millisecond of noise with millisecond jitter, on
a quantity — the advertising interval — whose minimum legal value is 20 ms. The
measurement would be mostly instrument.

Custom firmware puts the timestamp in the radio event handler, on a 1 MHz timer,
a few microseconds after the packet arrived. The host then receives a figure it
cannot have distorted. Everything else about this element follows from that one
decision:

| Consequence | Why |
|---|---|
| A line protocol, not a serialised API | The host needs events with timestamps, not remote procedure calls |
| Filtering in the firmware | Forwarding a busy room over USB causes the drops that would be misread as a sensor missing beacons |
| Counters at both ends | So a lossy link is distinguishable from a quiet sensor |
| Queued output, never blocking the radio handler | Blocking would delay the next radio event, distorting the measurement being reported |

The cost is that this repository now contains embedded C. That cost is managed by
treating firmware and driver as one element with one interface artefact (AD-16):
`include/protocol.h` is the contract, and a test parses it.

## 2. The protocol

USB CDC ACM, 8N1, line-oriented, LF terminated. The rate is irrelevant (it is a
USB device) but is set anyway for the sake of converters that care.

```
host -> dongle    one command per line
dongle -> host    "ok ..." | "err <code> <text>" | "+<event> ..."
```

Every event carries `t=`, microseconds on the dongle's clock.

### 2.1 Commands

| Command | Meaning |
|---|---|
| `ver` | identity, **firmware version and build date**, protocol version, uptime, lines dropped |
| `scan start <ms> [name=] [addr=] [active=] [rssi=]` | scan, with firmware-side filtering |
| `scan stop` | stop scanning |
| `list` | one `+sensor` event per device found, then `ok sensors=<n>` |
| `select <index\|addr[/type]>` | choose the sensor for later commands |
| `selected` | report the selection |
| `connect [<addr[/type]>]` | connect to the selection, or to an address |
| `disconnect` | disconnect |
| `uart <hex>` | write to the sensor's UART service, no reply awaited |
| `cmd <hex>` | write, await the reply, report both timestamps and the round trip |
| `adv start [<addr>]` / `adv stop` / `adv stats` | advertising profile capture and its counters |
| `time` | the dongle's timestamp now, and its rate |
| `reset` | reset the dongle |
| `dfu` | answer, then restart into the bootloader so the host can refresh the firmware |

### 2.2 Events

| Event | Fields |
|---|---|
| `+adv` | `t addr type rssi pdu ch name data` — one advertising report |
| `+sensor` | `t idx addr type rssi seen name` — one entry of the scan result |
| `+rx` | `t len data` — bytes notified by the sensor |
| `+conn` | `t addr state interval_us` — `state=linked` then `state=ready` |
| `+disc` | `t reason` — HCI reason code |
| `+scan` | `t state` — `started` or `stopped` |
| `+drop` | `t count` — lines the dongle could not send |

`+drop` is the important one. It is how the host knows its stream was lossy
rather than the sensor quiet, and it is why `AdvertisingProfile.is_complete`
exists.

### 2.3 Errors

| Code | Meaning | Code | Meaning |
|---|---|---|---|
| 1 | unknown command | 6 | not connected |
| 2 | wrong number of arguments | 7 | busy |
| 3 | bad argument value | 8 | the sensor did not reply |
| 4 | not valid in this state | 9 | payload too long |
| 5 | no sensor selected | 10 | the BLE stack refused the request |

The definitive list is `PROTO_ERROR_TABLE` in `include/protocol.h`, which the
driver's `DongleError` mirrors and `test_firmware_protocol.py` checks.

## 3. Building and flashing

### 3.1 Build

Either open the SES project, or build headlessly with the Makefile:

```
cd firmware/nordic_dongle
make SDK_ROOT=/path/to/nRF5_SDK_17.1.0 -j
make SDK_ROOT=/path/to/nRF5_SDK_17.1.0 dfu      # and package it
```

SES remains the reference; the Makefile exists because CI cannot licence an IDE.

1. Install nRF5 SDK 17.1.0 and SEGGER Embedded Studio for ARM.
2. Open `firmware/nordic_dongle/ses/nordic_dongle_pca10059.emProject`.
3. Set `SDK_ROOT` (Tools → Options → Building → Global macros), or build headless:

```
emBuild -config Release -D SDK_ROOT=/path/to/nRF5_SDK_17.1.0 \
        nordic_dongle_pca10059.emProject
```

`SDK_ROOT` has no default in the project, so one of the two must be set. Point
it at the folder that directly contains `components/` and `modules/`; the SDK
zip unpacks into a folder of the same name, so check for an extra level.
Verified on 2026-09-25 with SES 5.10 and SES 7.32a against SDK 17.1.0; the
output lands in `ses/Output/Release/Exe/`.

The project produces an application hex only. The SoftDevice and bootloader come
from the factory, which is why the application is linked at 0x27000.

A dongle that has had other firmware loaded, such as the nRF Sniffer, may no
longer carry the SoftDevice. Package the SoftDevice with the application so the
bootloader accepts it either way. S140 7.2.0 is `0x100` in
`nrfutil nrf5sdk-tools pkg generate --help`:

```
nrfutil nrf5sdk-tools pkg generate --hw-version 52 --application-version 1 \
    --application ses/Output/Release/Exe/nordic_dongle_pca10059.hex \
    --softdevice $SDK_ROOT/components/softdevice/s140/hex/s140_nrf52_7.2.0_softdevice.hex \
    --sd-req 0x00,0x100 --sd-id 0x100 dongle_dfu.zip
```

The dongle's bootloader presents a serial port (`nRF52 SDFU USB`), not a USB
drive, so an image cannot be copied onto it; program it with
`nrfutil device program --firmware dongle_dfu.zip` after pressing RESET.

`make manifest` (which `dfu` runs for you) writes `_build/firmware_manifest.json`
beside the image: version, build instant, protocol, model, hex, package and
SHA-256. That file is what the host compares a dongle against, so keep it with
the build; CI uploads it with the artefacts.

```
make SDK_ROOT=... identity          # version=1.1.0 built=2026-09-13T12:00:00Z
SOURCE_DATE_EPOCH=1757764800 make SDK_ROOT=... manifest   # reproducible date
```

A build that injects no date - an IDE build - falls back to the compiler's
`__DATE__`/`__TIME__`, which the firmware tags `local:`. The host will not order
those: they are local time in an awkward format, and two dongles built in
different timezones would compare wrongly. Such a dongle reports a build date
and still fails a comparison, which is the honest answer.

### 3.2 Flash

A PCA10059 has no onboard debugger: it is programmed over USB through its
bootloader. Press the small RESET button on the side of the dongle — the red LED
pulses — then:

```
cd firmware/nordic_dongle/scripts
./package_dfu.sh /dev/ttyACM0          # or: package_dfu.bat COM5
```

The script wraps the hex with `nrfutil pkg generate` and flashes it with
`nrfutil dfu usb-serial`. `--sd-req 0x100` is S140 7.2.0 (`0xCA` is 7.0.1); if a DFU is refused as
incompatible, list the identifiers with `nrfutil pkg generate --help` and use the
one matching the SoftDevice on the dongle.

The dongle's factory bootloader does not verify signatures, so no key is needed.
Set `DFU_KEY` if flashing a bootloader that does.

Install `nrfutil` pinned:

```
pip install 'nrfutil==6.1.7'
```

6.1.7 is the last release of the Python `nrfutil` that packages for the nRF5
SDK 17 bootloader, and it supports Python 3.10 at the newest. On a newer
interpreter `pip install nrfutil` resolves backwards instead of refusing, and
lands on a Python 2 era release that fails inside `pkg generate` with
`'dict' object has no attribute 'iteritems'`. The firmware workflow pins both
the version and a 3.10 interpreter for that reason.

### 3.3 Keeping the dongle and the build in step

Measurements taken with a stale dongle look perfectly plausible and answer a
different question. The driver checks, and can fix it:

```
python -m benchtools ble --resource /dev/ttyACM0 firmware firmware/nordic_dongle/_build
python -m benchtools ble --resource /dev/ttyACM0 firmware firmware/nordic_dongle/_build --update
```

Without `--update` it reports and exits 1 on a mismatch, so a build step stops
rather than publishing numbers taken with the wrong image. With it, the dongle is
asked into its bootloader (`dfu`), flashed with `nrfutil`, reconnected and
**re-read**: "the tool reported success" and "the dongle is running the image"
are different facts, and only the second is recorded.

Both the version and the build date are compared. During development every image
is `1.1.0`; comparing versions alone would call a week-old dongle up to date,
which is the case this exists for.

From a bench file, so every suite gets it without asking:

```yaml
instruments:
  dongle:
    driver: ble-dongle
    resource: /dev/ttyACM0
    options:
      firmware: firmware/nordic_dongle/_build
      update_firmware: false      # true to refresh automatically
```

and from a specification, as a step like any other:

```yaml
setup:
  - do: dongle.check_firmware
    save: dongle_firmware
```

The version and build date of every instrument the run used are recorded in the
run's JSON record and in the **Instruments** table of its markdown report,
whether or not the suite checked them.

### 3.4 First contact

```
python -m benchtools ble --resource /dev/ttyACM0 info
python -m benchtools ble --resource /dev/ttyACM0 --log ble.log scan --duration 5
```

If `info` times out: check the port is the dongle's (it enumerates as
`Nordic Semiconductor BenchTools BLE dongle`), and that nothing else has it open.

## 4. Reading the numbers

### 4.1 Advertising interval

A conforming sensor does **not** advertise at a fixed interval. The Core
specification adds a random delay of 0 to 10 ms to every advertising interval
(advDelay), so:

| Quantity | A healthy 100 ms sensor |
|---|---|
| Mean interval | ~105 ms |
| Minimum | 100 ms |
| Maximum | ~110 ms |
| Standard deviation | ~2.9 ms (`10/sqrt(12)`) |

`AdvertisingProfile.expected_jitter_s` states that figure, and
`within_specification()` allows for it. A limit written as "100 ms ± 1 ms" will
fail every conforming sensor; write it against the minimum, or use
`within_specification`.

Three more things worth knowing:

- **One advertising event is up to three packets** (channels 37, 38, 39). Reports
  within 5 ms are coalesced into one event, so the interval measured is between
  beacons. Without that, a scanner that heard two channels would report a 300 µs
  interval.
- **Missed events are counted against a nominal interval.** Supply it
  (`expected_interval=0.1`) when the specification names one; otherwise it is
  inferred from the capture, and `interval_was_measured` says so.
- **`is_complete` gates everything.** If the dongle sent more reports than the
  host received, missed beacons cannot be attributed to the sensor. The CLI adds
  a `warning` key in that case.

### 4.2 Response time

A reply cannot arrive between connection events. With a 30 ms connection
interval, a sensor that answers instantly still answers up to 30 ms later, and
the figure measured says where in the interval the write landed — not what the
firmware did. `ResponseTiming.is_trustworthy` is false whenever the latency is
below 1.5 connection intervals, and the CLI explains it.

To measure firmware latency properly: request a shorter connection interval, or
measure something that takes materially longer than one interval, or measure the
same operation over a range of intervals and take the difference.

The host's own round trip is recorded beside the dongle's. It is not the
measurement; it is the cross-check that shows what the host link contributes.

## 4.1 The command set as its own test

The sensor's command set is written down before anyone tests it.
`specs/sensor_commands.md` is that document, and the driver runs it:

```python
dongle.open_link()
run = dongle.run_script("specs/sensor_commands.md", report="ble_commands.md")
print(run.result, run.passed, run.failed, run.skipped)
```

A heading per test, a row per step, three kinds of step:

| Row | What happens | Result |
|---|---|---|
| `rd version` with an expected response | sent, and the reply compared | **pass** or **fail** |
| `delay 250` | waits 250 ms | **skip** — waiting claims nothing |
| a command with an empty expected cell | sent; anything arriving within `listen` seconds is recorded | **skip** — the document claimed nothing |

An expected response matches exactly after trimming, or as a regular expression
when written `/like this/`. A step whose reply never arrives **fails** — the
document said the sensor would answer — while a step that promised nothing is
skipped whether or not anything comes back.

**A skipped step is not a passed one.** A document of delays and fire-and-forget
rows passes while checking nothing, which is why a run reports how many steps
passed, failed *and* were skipped, and why the specification that runs it
asserts `passed >= 1` beside `failed == 0`.

The time in each row is the dongle's own figure for the exchange — end of
command to start of response — quoted to 10 ms with the measured microseconds
kept beside it. Every command goes through the ordinary command path, so
`start_log` captures the whole exchange with both clocks, with a note marking
each test as it begins.

## 5. Bench confirmation items

### 5.1 Firmware unit tests

```
cmake -S firmware/nordic_dongle/test -B build/firmware-tests
cmake --build build/firmware-tests
ctest --test-dir build/firmware-tests --output-on-failure
```

128 cases across five binaries. Unity is fetched at configure time; pass
`-DUNITY_DIR=/path/to/Unity` to use a local copy instead. Nothing else is
needed - no SDK, no toolchain, no dongle - because fake SDK headers sit at the
SDK boundary and the firmware's own sources are what run.

They found two defects on their first run, both of which compile perfectly: an
advertising line the queue refused was still counted as *reported*, so the
host's loss detection could never fire; and the tail of an over-long command
became a command of its own.

`test_cmd_parser` is worth knowing about if you change the protocol: it asserts
the exact shape of every reply, and the host driver's tests assert the same
shapes from the other side.

### 5.2 What the compiler has already said

The firmware **has now been compiled**, in the `canembed/canembed-arm` container
image, which carries `arm-none-eabi-gcc` 10.2.1, SEGGER Embedded Studio 4.16 and
nRF5 SDK **15.2.0**. The firmware targets SDK 17.1.0, which is not in the image
and cannot be fetched here (Nordic's download hosts are blocked by the network
policy), so this is a cross-version check:

```
docker run --rm -v "$PWD":/work:ro canembed/canembed-arm \
       bash /work/firmware/nordic_dongle/scripts/compile_check.sh
```

On GitHub, `.github/workflows/firmware.yml` does all of this on every push and
pull request that touches `firmware/**`: the unit tests first, then a real
cross-compile against SDK 17.1.0 with the hex, elf, map and DFU package uploaded
as artefacts. That workflow is the first place SDK 17.1.0 is actually used, and
it is **green**: see §5.4.

All six units compile with `-Wall -Wextra -O2` and **zero warnings**, apart from
four lines using SDK 17's GATT queue, which SDK 15.2 has no equivalent for. The
script lists those lines rather than skipping them silently.

It found seven defects, recorded as D-20 to D-26 in the SWE.4 report. Two are
worth repeating here because they are the kind that survive review:

- `CRITICAL_REGION_ENTER()` and `CRITICAL_REGION_EXIT()` are a **brace pair**.
  A `return` between them leaves the scope unbalanced - and would have left
  interrupts disabled on that path had it compiled.
- SDK 17's `ble_nus_c` and `ble_db_discovery` require a **GATT queue**
  (`nrf_ble_gq`). The firmware created none. That compiles and then fails at run
  time on the first characteristic discovery.

**What this establishes:** syntax, types, every SDK call that exists in both
versions, and the `sdk_config.h` keys the SDK's headers assert on. **What it does
not:** that the firmware links, fits in flash, or runs. Linking and flash are
§5.4; running is still open.

### 5.3 What remains

Treat the first real build as part of the work, not as a formality.

| ID | Item | How to discharge |
|---|---|---|
| BLE-OPEN-01 | ~~**First build against SDK 17.1.0, linked.**~~ | **Discharged** — see §5.4. It builds, links, fits and packages. The remaining unknowns were all in the build configuration, not the sources |
| BLE-OPEN-02 | **Behaviour under load.** The outgoing queue is 32 lines; a busy room may overflow it. The drop counter will say so — the question is whether the figures stay usable. | Scan with no address filter in a busy area and watch `adv stats` |
| BLE-OPEN-03 | **Timestamp accuracy.** The timestamp is taken at the top of the radio event handler, which is some microseconds after the packet. The offset is constant and so does not affect intervals, but it does affect any absolute comparison with another instrument. | Advertise from a second dongle at a known interval and compare |
| BLE-OPEN-04 | **Connection parameters.** The firmware requests 7.5–30 ms; the sensor may refuse. `+conn interval_us` reports what was agreed, and every latency figure depends on it. | Read `interval_us` on first connection and record it with the results |

Two smaller unknowns, recorded here rather than in the code: whether
`ble_advdata_search` returns the offset this firmware assumes for a name in a
scan response, and whether the dongle's bootloader accepts an unsigned DFU
package (§3.2). Both fail loudly rather than silently.

### 5.4 The first real build

`.github/workflows/firmware.yml` run 12, on commit `f66a248`, is the first green
build against nRF5 SDK 17.1.0: `arm-none-eabi-gcc` 10.3-2021.10, linked, sized
and packaged as `nordic_dongle_dfu.zip`. Both jobs pass and all five artefacts -
`.hex`, `.out`, `.map`, the DFU zip and `firmware_manifest.json` - are uploaded.

| | Bytes | Region | Used |
|---|---|---|---|
| Flash (`text` + `data`) | 51 652 | 0xd9000 = 888 832 (0x27000 up to the factory bootloader) | 5.8% |
| Static RAM (`data` + `bss`) | 12 636 | 0x3d518 = 251 160 above the SoftDevice | 5.0% |

`text` 49 800, `data` 1 852, `bss` 10 784. The 8 KiB stack and 2 KiB heap come
from `__STACK_SIZE` and `__HEAP_SIZE` in the build; the `.map` in the artefact is
the authority on where they sit relative to those numbers. The headroom is large
either way, which is what BLE-OPEN-01 was asking.

Eleven runs failed before it, and all of it was in the build configuration:
a source named that nrfx 2.x does not have and three that were never compiled
(D-37), seven missing `sdk_config.h` keys (D-38), and a GATT queue sized for
20-byte writes against a protocol that sends 96 (D-36). None of that was
reachable by reading the sources, which is the argument for the workflow.

The build date is pinned to the commit (`SOURCE_DATE_EPOCH`), so the image, the
manifest and the DFU package carry one identity and rebuilding a commit
reproduces it.

## 6. What this element does not do

| Not supported | Reason |
|---|---|
| More than one sensor connected at a time | One radio, one link. Two dongles are two instruments in the bench configuration |
| Extended advertising, coded PHY, 2 Mbit/s scanning | Primary channels at 1 Mbit/s only; the sensors in scope advertise there |
| Pairing, bonding, encryption | The bench talks to development firmware over an open link |
| A sensor whose console is not Nordic's UART Service | Would need a different GATT client in the firmware, not a driver change |
| Sniffing another device's connection | A different tool entirely (and different silicon) |
| RSSI statistics over a capture | Each report carries its RSSI; aggregate statistics were not required |
