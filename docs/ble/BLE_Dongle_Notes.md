# Nordic BLE Bench Dongle — Integration Notes

| Field | Value |
|---|---|
| Document ID | BENCHTOOLS-BLE-001 |
| Version | 1.0 |
| Date | 2026-09-13 |
| Element | `BLE-` — `benchtools.instruments.nordic_dongle` + `firmware/nordic_dongle` |
| Firmware target | nRF52840 USB dongle (PCA10059), S140 7.2.0, nRF5 SDK 17.1.0, SEGGER Embedded Studio |
| Status | Host driver verified against a simulated dongle. **The firmware has never been compiled or run** — see §5 |

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
| `ver` | identity, protocol version, uptime, lines dropped |
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

1. Install nRF5 SDK 17.1.0 and SEGGER Embedded Studio for ARM.
2. Open `firmware/nordic_dongle/ses/nordic_dongle_pca10059.emProject`.
3. Set `SDK_ROOT` (Tools → Options → Building → Global macros), or build headless:

```
emBuild -config Release -D SDK_ROOT=/path/to/nRF5_SDK_17.1.0 \
        nordic_dongle_pca10059.emProject
```

The project produces an application hex only. The SoftDevice and bootloader come
from the factory, which is why the application is linked at 0x27000.

### 3.2 Flash

A PCA10059 has no onboard debugger: it is programmed over USB through its
bootloader. Press the small RESET button on the side of the dongle — the red LED
pulses — then:

```
cd firmware/nordic_dongle/scripts
./package_dfu.sh /dev/ttyACM0          # or: package_dfu.bat COM5
```

The script wraps the hex with `nrfutil pkg generate` and flashes it with
`nrfutil dfu usb-serial`. `--sd-req 0xCA` is S140 7.2.0; if a DFU is refused as
incompatible, list the identifiers with `nrfutil pkg generate --help` and use the
one matching the SoftDevice on the dongle.

The dongle's factory bootloader does not verify signatures, so no key is needed.
Set `DFU_KEY` if flashing a bootloader that does.

### 3.3 First contact

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

## 5. Bench confirmation items

**The firmware in this repository has never been compiled or run.** No SDK,
toolchain or dongle was available in the environment it was written in (CON-07).
It is written against SDK 17.1.0 APIs and verified only in the ways source can be
verified without a compiler: the protocol is checked against the driver, and the
hygiene rules (traces, no dynamic allocation, indentation) are enforced by tests.

Treat the first build as part of the work, not as a formality.

| ID | Item | How to discharge |
|---|---|---|
| BLE-OPEN-01 | **First build.** Expect to fix `sdk_config.h` keys: the configuration here is minimal by design, and a missing key appears as a compile error naming it. | Build in SES per §3.1; add keys until it compiles; commit the result |
| BLE-OPEN-02 | **Behaviour under load.** The outgoing queue is 32 lines; a busy room may overflow it. The drop counter will say so — the question is whether the figures stay usable. | Scan with no address filter in a busy area and watch `adv stats` |
| BLE-OPEN-03 | **Timestamp accuracy.** The timestamp is taken at the top of the radio event handler, which is some microseconds after the packet. The offset is constant and so does not affect intervals, but it does affect any absolute comparison with another instrument. | Advertise from a second dongle at a known interval and compare |
| BLE-OPEN-04 | **Connection parameters.** The firmware requests 7.5–30 ms; the sensor may refuse. `+conn interval_us` reports what was agreed, and every latency figure depends on it. | Read `interval_us` on first connection and record it with the results |

Two smaller unknowns, recorded here rather than in the code: whether
`ble_advdata_search` returns the offset this firmware assumes for a name in a
scan response, and whether the dongle's bootloader accepts an unsigned DFU
package (§3.2). Both fail loudly rather than silently.

## 6. What this element does not do

| Not supported | Reason |
|---|---|
| More than one sensor connected at a time | One radio, one link. Two dongles are two instruments in the bench configuration |
| Extended advertising, coded PHY, 2 Mbit/s scanning | Primary channels at 1 Mbit/s only; the sensors in scope advertise there |
| Pairing, bonding, encryption | The bench talks to development firmware over an open link |
| A sensor whose console is not Nordic's UART Service | Would need a different GATT client in the firmware, not a driver change |
| Sniffing another device's connection | A different tool entirely (and different silicon) |
| RSSI statistics over a capture | Each report carries its RSSI; aggregate statistics were not required |
