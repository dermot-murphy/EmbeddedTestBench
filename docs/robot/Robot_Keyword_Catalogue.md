# Robot Framework Keyword Catalogue — Dongle, J-Link, GPD-3303D, S2-LP

| | |
|---|---|
| Scope | Keywords a Robot Framework library would offer over three drivers: the Nordic BLE dongle (`benchtools.instruments.nordic_dongle`), the SEGGER J-Link (`benchtools.instruments.jlink`) the GW Instek GPD-3303D supply (`benchtools.instruments.gpd3303d`), and the ST S2-LP kit (`benchtools.instruments.s2lp`, added for #77) |
| Status | **Proposal.** No keyword library exists, and no Robot Framework dependency is taken. Robot Framework itself is still undecided (STK-12, CON-06, OPEN-04) |
| Sources | The drivers as they stand on `develop` at `f7ca43f`; the BLE command-document work (#38–#59); the GPD-3303D bring-up (#61–#67); the J-Link bring-up (#69) |
| Issue | #74 |

This document lists the keywords before any are written. That gives the Robot
Framework decision (OPEN-04) something concrete to be made against, and it keeps
in one place what the hardware taught while the three drivers were brought up.
Each keyword table is followed by the behaviour that shaped it, because that
behaviour decided the keyword's defaults and its failure conditions. On all three
instruments, a keyword with the obvious defaults would have recorded a number
that was not true.

The keyword names for the dongle are the ones already promised by the
command-document template
([`specs/templates/ble_sensor_test.md`](../../specs/templates/ble_sensor_test.md),
"Converting to Robot Framework"). A translator from that format, if one is
written, emits these names.

---

## 1. Conventions for all three libraries

### 1.1 Shape

- **One library per instrument.** Each is imported under an alias (`Supply`,
  `Probe`, `Dongle`), and the keywords are written with the prefix wherever two
  libraries could share a name.
- **Library scope is `SUITE`.** Each library holds one driver instance for the
  whole suite. This is required, not a matter of taste:
  - The supply's per-channel "off" state exists only in the driver instance (§4.2).
  - The J-Link accepts one client at a time (§3.2).
- **Each keyword is a thin wrapper over one driver call**, except where the
  tables say *library logic*. Library logic marks behaviour that the driver does
  not have yet, but that a test on real hardware needs. Each such keyword is a
  candidate to move into the driver instead.

### 1.2 Arguments and units

- **Durations are Robot time strings**, such as `250 ms`, `30 s` or `1 min`. They
  are converted with `robot.utils.timestr_to_secs` and passed to the drivers as
  seconds.
  - Every driver API already takes seconds.
  - Milliseconds appear only in the markdown command document's Timeout,
    Command prefix timeout and delay cells, and on the dongle's own wire
    protocol.
  - Using Robot's time strings removes the one unit ambiguity the command
    documents had to solve.
- **Electrical values are plain numbers in SI units**: volts, amps, watts and
  hertz. The unit is part of the argument name wherever the table lists one.
- **Addresses** are accepted as `0x10001080` or as a decimal number.
- **Byte strings** are hex text, with spaces allowed (`00 5C 17 12`), the same
  form the J-Link command-line interface takes.
- **Channel `all`** is a valid channel wherever the table says so.
- **Booleans** take Robot's usual forms (`True`, `on`, `yes`, `${TRUE}`).

### 1.3 Returns

Every keyword returns a plain type, meaning a string, a number, a list or a
dictionary. Driver records are returned through their `as_dict()` method. Where a
driver record has no `as_dict()`, the library converts it:

| Driver record | Returned as |
|---|---|
| `HaltInfo`, `StackFrame`, `Breakpoint`, `Watchpoint` | A dictionary. The enumeration fields become their string values |
| `re.Match` from `rtt_expect` and `rtt_command` | The matched line, or the named group `value` if the pattern has one |
| `bytes` from `read_memory` | Hex text |

These four conversions are the places where the J-Link driver does not yet meet
AD-15 / JLINK-FR-081 (§7).

### 1.4 Failure

| Condition | Robot outcome |
|---|---|
| A `... Should ...` keyword whose check is false | FAIL, with a message stating what was expected and what was seen |
| `ConfigurationError` | FAIL. The keyword was called wrongly, and the message says how |
| `TransportError` or `InstrumentError`: timeout, refusal, lost link | FAIL, with the driver's message unchanged. The command documents call this ERROR; Robot has no separate status for it, so the reason carries the distinction (template, last paragraph) |
| A precondition that makes the test meaningless, such as a tracking mode the test did not ask for | `Skip`, only where the table says so |

A keyword never catches an error and returns a default value in its place. The
one exception is `Send Command`, whose documented job is to send a command and
record whatever comes back (§2.3).

### 1.5 Bench-level rules the libraries enforce

- **Select serial ports by what is attached, not by COM number.** On the lab PC:

  | Port | Device |
  |---|---|
  | COM10 | The dongle (VID `1915`) |
  | COM11 | The supply's FTDI cable (`0403:6001`) |
  | COM4 | An ST-LINK |

  During the supply's bring-up, `*IDN?` and `STATUS?` were once sent to the
  dongle by mistake, and it answered `err 1 unknown command`. Each `Open ...`
  keyword should therefore check the identity it gets back, and fail when that
  identity belongs to a different instrument.
- **Reject unknown options.** The drivers' `connect()` methods swallow unknown
  keyword arguments (`**_ignored`), so a misspelt bench option does nothing and
  nothing reports it. The libraries pass on only the names a driver declares, and
  fail on anything else.

---

## 2. Nordic BLE dongle — library `DongleLibrary`

The dongle is a PCA10059 running this repository's firmware (protocol 1.4,
firmware 1.4.0). It holds one BLE link at a time to a sensor that exposes the
Nordic UART Service. It does not support pairing, and it does not support more
than one link at a time.

### 2.1 Setup and firmware

| Keyword | Arguments | Action | Returns / fails |
|---|---|---|---|
| `Open Dongle` | `resource`, `firmware=None`, `require_firmware=False`, `log=None`, `timeout=5 s` | `NordicDongle.connect()`. `resource` is `COM10`, `/dev/ttyACM0`, `serial://…` or `sim://`. With `log`, every line in both directions is written to that file from the first `ver` onwards | Firmware and protocol versions as a dictionary. **Fails** on a different protocol major version. With `require_firmware`, also fails when the firmware does not match `firmware` |
| `Close Dongle` | — | `close()`. Sends `disconnect` first if a link is open. Never fails | — |
| `Dongle Firmware Should Match` | `firmware=None` | `check_firmware()` against a build directory or manifest | **Fails** unless the version and the build date both match. A build made locally has a build date that always fails the date comparison (`built=local:…`) |
| `Update Dongle Firmware` | `firmware`, `port`, `timeout=180 s` | `update_firmware()`: enter DFU, flash with nrfutil, reopen, check | Firmware status as a dictionary. **Fails** if the dongle comes back with a different build. `port` is the *bootloader's* port, which on Windows is usually a different COM number from the application's |
| `Get Dongle Firmware` | — | Reads the properties `firmware_version`, `firmware_built` and `protocol_version` | Dictionary |
| `Reset Dongle` | — | `reset()`. Forgets the scan results, the selection and the link | — |
| `Start Dongle Log` / `Stop Dongle Log` | `path` / — | `start_log()` / `stop_log()` | — |
| `Log Note` | `text` | `log_note()`. Writes a `#` line to the dongle log, so the log can be lined up with the Robot log | — |

### 2.2 Discovery and link

| Keyword | Arguments | Action | Returns / fails |
|---|---|---|---|
| `Scan For Sensors` | `duration=10 s`, `name=None`, `address=None`, `active=True`, `min_rssi=None` | `scan()`, filtered in the firmware | A list of sensor dictionaries: `address`, `name`, `rssi`, `index`. The `name` filter is **case-sensitive and cannot contain a space**, because the firmware applies it with `strstr`. For a case-insensitive match, use `Select Sensor` |
| `Select Sensor` | `sensor` | An address (optionally `/type`) goes to `select()`. Any other text goes to `select_by_name()`: case-insensitive, and the strongest match wins | Sensor dictionary. **Fails** listing every name heard |
| `Sensor Should Be Advertising` | `sensor`, `duration=10 s` | Scan, then select | Sensor dictionary. **Fails** if the sensor is not heard. This keyword is not evidence that the firmware is healthy (§2.6) |
| `Connect` | `target`, `timeout=15 s`, `scan=10 s`, `attempts=3` | *Library logic*, the same as a command document's `connect` step: close any open link, active scan for `scan`, select, then try `open_link(connect_timeout=timeout)` up to `attempts` times | Dictionary: sensor, `interval_us`, attempts used. **Fails** with the first sentence of the last error. Maps from `connect ${SENSOR_ID}` |
| `Disconnect` | — | `close_link()`. Idempotent, and consumes the `+disc` event that follows | — |
| `Link Should Be Up` | — | `check_link()`. Reads the lines already waiting and sends nothing | **Fails** with the disconnect reason and the dongle time when the link has dropped. `0x08` is a supervision timeout |
| `Get Connection Interval` | — | The `connection_interval_us` property | Integer, µs |

### 2.3 UART commands over BLE

| Keyword | Arguments | Action | Returns / fails |
|---|---|---|---|
| `Send Command` | `command`, `timeout=3 s`, `frame_window=0 s` | `command()`. If the sensor does not reply within `timeout`, the keyword returns an empty string instead of failing (`DongleError.TIMEOUT`) | Reply text. Maps from a row with an empty Expected cell. `${X}=    Send Command    …` maps from a Save cell. **Fails** only when the link is down or the dongle refuses the command |
| `Send Command And Expect` | `command`, `expected`, `timeout=3 s`, `frame_window=0 s` | Sends, then compares the reply with `expected` exactly, after trimming both | Reply text. **Fails** on a mismatch or on no reply |
| `Send Command And Expect Match` | `command`, `pattern`, `timeout=3 s`, `frame_window=0 s` | Sends, then tests the reply against `pattern` with `re.search`, which is unanchored unless the pattern uses `^` or `$` | The first named group that matched, or else the whole reply. **Fails** on no match or on no reply |
| `Send Command And Expect Disconnect` | `command`, `timeout=15 s` | `command_expecting_disconnect()`. Sends without waiting for a reply, then waits for the link to drop | The time from the write to the drop, in seconds on the dongle clock, plus the reason. **Fails** with "still connected" if the link does not drop. The driver only returns `disconnected=False`; the keyword is what turns that into a failure |
| `Reply Frames Should Be` | `count` | Checks `1 + len(extra_frames)` of the last reply | **Fails** on a different count, naming the extra frames. The command must have been sent with `frame_window` greater than 0; `0.5 s` is what command documents use, and a translator adds it to the send |
| `Write To Sensor` | `payload` | `write()`. Sends a `uart` line and does not wait for a reply | Bytes written |
| `Measure Response Time` | `command`, `repeat=1`, `timeout=3 s`, `source=DONGLE` | `measure_response_time()` | Timing dictionary, which includes `milliseconds`, `is_trustworthy` and `interval_us` |
| `Run Command Document` | `path`, `report=None`, `events=None`, `timeout=3 s`, `listen=0.5 s`, `timeouts=None`, `&{variables}` | `run_script()`. Runs a markdown command document as one Robot step; `timeouts` is a dictionary of command prefix to milliseconds, over the document's Command prefix table (#60) | Summary dictionary: result, passed, failed, errors and saved values. **Fails** unless the document's result is PASS |
| `Measure Advertising Profile` | `duration=30 s`, `address=None`, `expected_interval=None` | `measure_advertising_profile()` | Profile dictionary. **Fails** if fewer than two advertising events were heard, because no interval can be computed |

The command documents also have a delay step. It maps to Robot's own
`Sleep    250 ms`.

### 2.4 Arguments the dongle refuses before sending

The dongle refuses each of these before anything is sent, and the keyword fails
with `ConfigurationError`:

- a command payload over **244 bytes**
- a reply `timeout` outside **0.1–60 s**
- a connect `timeout` outside **1–60 s**
- a scan duration of zero or less

### 2.5 Commands a sensor treats specially

These facts about the Kappa sensor (5C1712) decide which keyword a step uses:

| Command | What the sensor does | Keyword and timeout |
|---|---|---|
| `wr mode …` | Resets the sensor. On hardware the link dropped 4 345 ms after `wr mode normal`, reason 0x08, and the sensor answered again after a reconnect | `Send Command And Expect Disconnect` with `timeout=15 s`, then `Connect` |
| `ECURESET HARD` | An MCU reset. It can stand in for a power cycle | `Send Command And Expect Disconnect` |
| `RD EOL START 60 30` | Crashes the sensor (`app_error_handler_bare`, error 8, from `HAL_SPI_Radio_Init`). The link drops about 34 s later, and routine state is lost on reboot | Only on 5C1712, which is approved for destructive tests. Follow it with `Link Should Be Up`, expecting a failure |
| `routine config start factory` | Replied after 265 ms | `timeout=30 s`, as the template gives it |
| A command sent while the sensor is busy | The sensor can take up to 45 s to wake, and it merges commands sent while busy into one line | Use `timeout=45 s` for every command on a sensor that may be busy, `RD` included. A 500 ms limit on `RD` let a stalled read merge into the next command. After `WR IGNORE-DURATION`, pause before the next command |
| An unknown or invalid command | Answers `NACK Invalid Command`. The simulator answers `ERR unknown command` instead | Write patterns against the real sensor's reply |

### 2.6 What the BLE work taught

- **Sensors advertise about every 9 s.**
  - The dongle's first connect window was a fixed 5 s, listened for only half of
    that, and missed them (#39).
  - Protocol 1.2 added `connect timeout=`. With it, all six attempts on hardware
    linked within 15 s, one of them after 7.8 s.
  - `Connect` therefore scans for 10 s and makes up to three attempts. A 9 s
    advertiser also means `Measure Advertising Profile` needs at least 30 s to
    see enough events to be worth reading.
- **Always release a failed link.**
  - A sensor that linked but whose UART service never became ready was left
    connected, and every later connect was refused with STATE (#40).
  - `open_link` now disconnects before raising, and `Disconnect` consumes the
    `+disc` event that follows. Without that, the next connect reads the old
    event as its own failure.
- **Check the link before every command, and stop after the first loss.**
  - One EOL crash once produced 85 errors, because every later step tried and
    failed on its own (#51).
  - Each command keyword should call `check_link()` before sending. Once the link
    is lost, each should fail with "not sent: link lost", naming where the link
    was lost, until a `Connect` succeeds.
  - This is library state kept across keywords, so it belongs in a `SUITE`-scoped
    library.
- **Count reply frames on any command whose reply matters.**
  - A sensor that answers twice leaves every later command reading the previous
    command's reply. This was defect TX-762 on the Kappa X (#53).
  - The firmware takes only the first notification as the reply. Later
    notifications become `+rx` events, and `frame_window` collects those stamped
    after the reply.
- **244 bytes is the payload limit.**
  - One Nordic UART write carries 244 bytes at an ATT MTU of 247. A 99-byte
    command (Kepler OT-A-13) needed protocol 1.4 (#52).
  - On hardware, a 111-byte NACK then arrived whole.
- **Use named groups to capture values.**
  - `/^ACK rd version = (?P<value>V[0-9.]+)$/` returns `V11.00.0000` by itself.
  - Robot's `Should Be Equal` then compares it with a later read (#54).
- **Advertising is not a health check.**
  - A sensor that crashes and reboots still advertises.
  - To show the firmware is healthy, read an answer over the link. Better still,
    read RTT through a reader that does not halt the core (§3.5).
- **Timing figures carry their own warning.**
  - `is_trustworthy` is false below 1.5 connection intervals.
  - Reports quote response times to 10 ms. The first real reply took 58.9 ms on
    the dongle clock.
  - The firmware requests a 7.5–30 ms connection interval, and the sensor may
    refuse it. Record `Get Connection Interval` with every timing result.

---

## 3. SEGGER J-Link — library `JLinkLibrary`

The J-Link driver works through the SEGGER GDB Server and `arm-none-eabi-gdb` in
MI mode. The bench:

| Item | Value |
|---|---|
| Probe | J-Link OB on the nRF52840 board, S/N 682395790 |
| J-Link software | V9.42 |
| GDB | 15.2, installed in the user's directory and **not on `PATH`** |
| Target | nRF52840 (`nRF52840_xxAA`), SWD at 4 000 kHz |

### 3.1 Setup and identity

| Keyword | Arguments | Action | Returns / fails |
|---|---|---|---|
| `Open Probe` | `resource=jlink://`, `device`, `elf=None`, `serial_number=None`, `gdb=None`, `speed_khz=4000`, `timeout=30 s` | `JLinkProbe.connect()`. Spawns the GDB Server if nothing is listening on 2331 | Identity dictionary. **Fails** if GDB is not found; give `gdb` on this bench. Also fails if the probe does not attach, with a message naming the probe, the power and the device |
| `Close Probe` | `leave_halted=False` | `close()`. Stops RTT, sends `monitor go` unless `leave_halted`, then detaches | — |
| `Get Probe Identity` | — | `identify()`. The serial number and firmware come from the server banner, which exists only if this probe spawned the server | Dictionary |
| `Get Image Build` | `path=None` | `image_build()`. Reads `firmware_manifest.json` beside the image | Build dictionary. This describes the **file**, not what is running on the part |

### 3.2 Erase, flash and verify

| Keyword | Arguments | Action | Returns / fails |
|---|---|---|---|
| `Erase Chip` | `preserve=0x10001080:4`, `timeout=120 s` | *Library logic around* `erase()`. Reads each preserved range, erases, blank-checks, writes the ranges back and reads them back. Pass `preserve=${NONE}` to erase everything | Server text. **Fails** if the blank check fails, or if a preserved range does not read back as it was saved. `erase()` has no preserve option of its own, and on an nRF52 it clears UICR |
| `Flash Firmware` | `path`, `verify=True`, `preserve=0x10001080:4`, `run=True`, `timeout=180 s` | `flash()` with the preserved ranges. Then `load_symbols(elf)` if an ELF was configured, and `reset(halt=False)` if `run` | Flash dictionary: sections, bytes, seconds, verified, preserved. **Fails** on no sections loaded, a verify mismatch, or a preserved range that did not stick |
| `Firmware Should Verify` | `path=None` | `verify()`, using `compare-sections` | Verify dictionary. **Fails** unless every section matched. An empty section list counts as a failure |

### 3.3 Run control and debugging

| Keyword | Arguments | Action | Returns / fails |
|---|---|---|---|
| `Reset Target` | `run=True`, `timeout=30 s` | `reset(halt=not run)` | — |
| `Halt Target` | `timeout=10 s` | `halt()` | Halt dictionary: reason, function, file, line, address |
| `Resume Target` | — | `run()`. Returns immediately | — |
| `Run To` | `location`, `timeout=30 s` | `run_to()`. Sets a temporary breakpoint, runs and waits. `location` is `file.c:123`, a function, or `*0x…` | Halt dictionary |
| `Set Breakpoint` | `location`, `temporary=False`, `hardware=False`, `condition=None` | `set_breakpoint()` | Breakpoint dictionary. **Fails** if the four hardware breakpoints are all in use |
| `Set Watchpoint` | `expression`, `kind=write` | `set_watchpoint()` | Watchpoint dictionary |
| `Clear Breakpoints` | — | `clear_breakpoints()` | — |
| `Wait For Halt` | `timeout=30 s` | `wait_for_halt()` | Halt dictionary. **Fails** on timeout |
| `Get Call Stack` | `limit=None` | `call_stack()`. The core must be halted | A list of frame dictionaries |
| `Get Program Counter` | — | `program_counter()` | Integer |
| `Monitor Command` | `command` | `monitor()`, sent unchanged to the GDB Server | Server text |

### 3.4 Memory, variables and the sensor ID

| Keyword | Arguments | Action | Returns / fails |
|---|---|---|---|
| `Read Memory` | `address`, `size` | `read_memory()` | Hex text |
| `Write Memory` | `address`, `data` (hex text) | `write_memory()` | — |
| `Read Word` / `Write Word` | `address` / `address`, `value` | `read_word()` / `write_word()`. 32-bit, little-endian | Integer / — |
| `Read Integer` | `address`, `size`, `byteorder=little`, `signed=False` | `read_integer()`, for 1–8 bytes | Integer |
| `Read Sensor ID` | — | *Library logic*. Checks that `read_u8(0x10001080)` is 0, the validity byte, then reads `read_integer(0x10001081, 3, byteorder=big)` | Six hex digits, for example `5C1712`. **Fails** if the validity byte is not 0 or the ID is `FFFFFF` |
| `Sensor ID Should Be` | `expected` | `Read Sensor ID`, then a comparison that ignores case | **Fails** on a mismatch |
| `Write Sensor ID` | `sensor_id` | *Library logic*. Writes `00` followed by the ID, big-endian, to `0x10001080`, then reads it back | **Fails** if CUSTOMER[0] already holds a *different* value, because changing it needs a UICR erase. Rewriting the same value is allowed |
| `Read Variable` | `name` | `read_variable()`. A structure comes back as a dictionary | A number, string, boolean or dictionary. **Fails** if no ELF is loaded |
| `Write Variable` | `name`, `value` | `write_variable()` | — |
| `Evaluate Expression` | `expression` | `evaluate()` | As for `Read Variable` |
| `Get Variable Address` | `name` | `variable_address()` | Integer |

### 3.5 RTT and timing

| Keyword | Arguments | Action | Returns / fails |
|---|---|---|---|
| `Start RTT` | `log=None` | `rtt_start()`. Only up-channel 0 is carried | — |
| `Stop RTT` | — | `rtt_stop()` | — |
| `Read RTT Lines` | — | `rtt_read_lines()`. Consumes the lines read | A list of strings |
| `Write RTT` | `text` | `rtt_write()`. Appends a newline | — |
| `Wait For RTT Line` | `pattern`, `timeout=5 s` | `rtt_expect()` | The matched line, or its `value` group. **Fails** on timeout, quoting the last 500 characters that arrived |
| `RTT Command` | `text`, `pattern=.+`, `timeout=5 s` | `rtt_command()`. Discards pending lines, writes, then waits for the pattern | As for `Wait For RTT Line` |
| `RTT Should Be Active` | `timeout=2 s` | `rtt_lines_within()` | Line count. **Fails** at zero. This proves that at least one line arrived; it does not count a whole window |
| `Measure Time Between` | `start`, `end`, `method=cycle_counter`, `repeat=1`, `timeout=30 s`, plus the timer options of `measure_time_between()` | `measure_time_between()` | Timing dictionary, always including `method`, `resolution_seconds` and `is_trustworthy` (JLINK-NFR-004) |
| `Timing Should Be Trustworthy` | `result` | Checks `is_trustworthy` in a dictionary returned by `Measure Time Between` | **Fails** when the interval is below 10× the method's resolution |

### 3.6 What the J-Link work taught (#69)

- **The GDB Server halts the core when it attaches and leaves it halted when it
  detaches.**
  - This silently broke a BLE run in another session: the sensor stopped
    answering.
  - `close()` now sends `monitor go`. `Close Probe` keeps that default, and
    `leave_halted=True` has to be asked for.
- **A SoftDevice target does not survive being halted.**
  - A short halt on attach while the SoftDevice is idle is survived. A halt at a
    breakpoint, a step, or a long halt is not.
  - After a breakpoint, resume with `Reset Target`, not `Resume Target`.
  - Set breakpoints and measure timing only on code that runs before the
    SoftDevice starts, and end each such test with `Reset Target`.
- **Erase only after a reset and halt, and check that it worked.**
  - While the firmware ran, `monitor flash erase` answered `Flash erase: O.K.`
    and erased nothing.
  - The driver now resets and halts first, then blank-checks.
- **Erasing clears UICR, and so does flashing a HEX that contains UICR records.**
  - The sensor ID is in UICR CUSTOMER[0] at `0x10001080` (`0x12175C00` for
    5C1712). The firmware reads it at boot.
  - Flashing the V11 HEX over a part that held the ID erased the ID, and the
    sensor came up as `KAPPA_FFFFFF_V11.00.00`.
  - This is why `preserve=0x10001080:4` is the default on `Erase Chip` and on
    `Flash Firmware`, not an option a test has to remember.
- **Load a HEX before reading its symbols.**
  - GDB 15.2 exited with status 3 after `file` then `load` of a HEX on the `U:`
    drive. The driver now loads first.
  - Loading a HEX also replaces the symbols with the HEX, so variables are no
    longer found by name. `Flash Firmware` reloads the configured ELF afterwards
    for that reason.
- **The two firmware lines use different SoftDevices.**

  | Firmware | SoftDevice | Bootloader | HEX writes UICR? |
  |---|---|---|---|
  | V10.01.2000 | s140 6.1.0 | none in the HEX | No |
  | V11.00.0000 | s140 7.2.0 | V1.01.0000 | Yes, `0x10001014` and `0x10001018` |

  - Moving between the two lines needs a full erase. Back up UICR and the NVM
    pages first.
  - After an erase, both lines boot with `NVM Memory: CLEARED`, which is
    expected.
- **Only one client may hold the probe.**
  - Running nrfjprog alongside this driver makes nrfjprog fail with a misleading
    "AP protection" error.
  - Do not use the probe while another session is testing the sensor over BLE.
- **Some things work that the tools claim do not.**
  - `monitor rtt start` answers "Target does not support this command" on V9.42.
    The server already serves RTT on port 19021, and the driver ignores the
    error.
  - `monitor version` is also unsupported, which is why the identity comes from
    the server banner.
- **Afterwards, check the sensor without halting it.**
  - Once, after a UICR write and a run-mode reset, the sensor restarted through
    its watchdog and logged `Fatal error`. The cause is not known.
  - A suite that has used the probe should finish by reading RTT through a reader
    that does not halt the core (JLinkRTTLogger), or by reading a reply over BLE.

  | Measured on 5C1712 | Figure |
  |---|---|
  | Flash and verify, V10 HEX | 14.2 s |
  | Flash and verify, V11 HEX | 16.2 s |
  | `HAL_Manager_PowerOnInit` to `API_Log_PowerOnInit` | 11 263 cycles (176 µs at 64 MHz) |

---

## 4. GW Instek GPD-3303D — library `Gpd3303DLibrary`

The unit on the bench:

| Item | Value |
|---|---|
| Serial number | GER916893 |
| Firmware | V1.09 |
| Port | COM11 through an FTDI cable, 9600 baud, 8N1 |
| Channels in scope | CH1 and CH2, each 0–30 V and 0–3 A |

CH3 is not in scope. Its 2.5 / 3.3 / 5 V selection is a front-panel switch that
no command reaches, so no keyword claims to set it or to read it.

### 4.1 Setup, setting and switching

| Keyword | Arguments | Action | Returns / fails |
|---|---|---|---|
| `Open Supply` | `resource`, `baudrate=9600`, `timeout=5 s`, `check_errors=False` | `Gpd3303D.connect()`, then `read_event_queue()` once to discard any stale error. Sends `*IDN?` and `STATUS?`, and changes no setting | Identity dictionary. **Fails** unless the model is GPD-3303D |
| `Close Supply` | `output=off` | `all_outputs_off()` unless `output=keep`, then `close()` | — |
| `Reset Supply` | `settle=200 ms` | `reset()`. Sets both channels to 0 V and switches the output off. This is **not** `*RST`, and the current limits are left as they are | — |
| `Set Voltage` | `channel`, `volts` | `set_voltage()` | The value sent, rounded to 1 mV. **Fails** outside 0–30 V, or on CH2 while the supply is tracking |
| `Set Current Limit` | `channel`, `amps` | `set_current_limit()` | The value sent, rounded to 1 mA. **Fails** outside 0–3 A |
| `Configure Channel` | `channel`, `volts`, `current_limit`, `output=None` | `configure_channel()`. Sets the limit first, then the voltage | Channel dictionary |
| `Supply Output On` | `channel=all` | For `all`, `all_outputs_on()`. For one channel, `output_on()`, which **also energises the other channel** unless that channel is switched off (§4.3) | — |
| `Supply Output Off` | `channel=all` | For `all`, `all_outputs_off()`: the real disconnect. For one channel, `output_off()`: that channel is set to 0 V and stays connected (§4.3) | — |

### 4.2 Reading and checking

| Keyword | Arguments | Action | Returns / fails |
|---|---|---|---|
| `Measure Voltage` / `Measure Current` / `Measure Power` | `channel` | `measure_voltage()` / `measure_current()` / `measure_power()`. Power is V × I from two reads taken one after the other | Number: V / A / W |
| `Read Channel` | `channel` | `read_channel()` | Dictionary: voltage, current, mode, `is_on`, setpoint, limit, `power`, `regulated`, `in_current_limit` |
| `Read Supply Status` | — | `status()` | Dictionary: modes, tracking, beep, output |
| `Voltage Should Be` | `channel`, `volts`, `tolerance=None` | `measure_voltage()`, compared with `volts` | **Fails** outside the tolerance. The default is the driver's own `max(0.15 V, 1 %)`. A tolerance tighter than 0.1 V is refused, because it is finer than the read-back step (§4.3) |
| `Wait For Voltage` | `channel`, `volts`, `tolerance=None`, `timeout=5 s`, `interval=200 ms` | *Library logic*. Polls `measure_voltage()` until the reading is within tolerance | Seconds taken. **Fails** at the timeout with the last reading. Nothing in the driver waits for the output to settle, and the settling time has not been measured (PSU-OPEN-04) |
| `Channel Should Be Regulated` | `channel` | `read_channel().regulated` | **Fails** if the output is off, the channel is in constant current, or the voltage is outside tolerance |
| `Channel Should Not Be In Current Limit` | `channel` | `read_channel().in_current_limit` | **Fails** when the output is on and the channel is in constant current |
| `Current Should Be Below` | `channel`, `amps` | `measure_current()` | **Fails** at or above `amps`. The reading resolution is 10 mA |
| `Tracking Should Be Independent` | — | The `tracking` property | **Skip** otherwise. A test written for independent channels is meaningless in series or parallel mode, and the tracking mode can only be changed on the front panel |
| `Supply Should Report No Error` | — | `read_event_queue()`, which sends `ERR?` | **Fails** with the supply's message. The supply holds only one error, and reading it clears it |
| `Send Raw` / `Query Raw` | `command` | `write_raw()` / `query_raw()`. The only way to reach `BEEP`, `SAV`/`RCL` and `LOCAL` | Reply text. Do **not** send `STATUS?` this way: its two legend lines are left unread, and they corrupt the next two replies |

These are not provided, deliberately:

- **Setting the tracking mode.** A remote change could put twice the intended
  voltage on a board.
- **The IEEE 488.2 commands other than `*IDN?`.** The supply does not implement
  them. `*CLS` records `Undefined Header.`, and the queries get no reply and time
  out.

### 4.3 What the GPD-3303D work taught (#61–#67)

- **A setting the supply cannot deliver is rejected, not clamped, and silently.**
  - `VSET1:35` gets no reply and leaves the previous setpoint in force. Only a
    later `ERR?` reports `Data out of range.`
  - The driver refuses out-of-range values before sending them, so a keyword
    fails at the call rather than measuring the old setpoint.
  - Errors also survive between sessions, which is why `Open Supply` discards the
    held error.
- **There is one output switch for both channels.**
  - `OUT1` and `OUT0` switch both channels at once.
  - The driver emulates "channel off" by setting that channel to 0 V. The
    channel's terminals stay connected and can sink current fed back from the
    board.
  - This per-channel state lives only in the driver instance. A new process sees
    that channel as on at 0 V (D-OPEN-01). This is one reason the library is
    `SUITE`-scoped.
- **The read-back is coarser than the setting, and reads low.**
  - The supply is programmed to 1 mV and 1 mA, but reads back to 0.1 V and
    0.01 A.
  - Unloaded, `VOUT` reads 0.1 V below the setpoint on every sample (3.3 V reads
    3.2 V). The front panel shows the same.
  - Any voltage check therefore needs at least one read-back step of tolerance.
    A check at ±0.05 V will fail against a supply that is working correctly.
- **With the output off, both channels report constant current.**
  - This does not mean the channels are limiting.
  - `Channel Should Not Be In Current Limit` therefore applies only while the
    output is on.
- **The output falls slowly with no load.**
  - 3.3 V took 2–3 s to reach 0 V, and `VOUT1?` still read 0.2 V after 1.5 s.
  - A test that switches the output off and then checks for 0 V needs
    `Wait For Voltage`, not a single reading.
  - The specifications sleep 0.5 s after switching on, for the board's soft
    start.
- **Suspect the host before the supply.**
  - On the Windows FTDI port, resetting pyserial's timeout before every read lost
    about one reply in five. The driver now sets it only when it changes, and
    108 of 108 exchanges succeeded.
  - Command spacing from 0 to 200 ms made no difference on the bench. The
    driver's 50 ms spacing is kept as a precaution (PSU-OPEN-03).
- **Queries are quick, except `STATUS?`.**
  - Replies begin within 17–43 ms.
  - The `STATUS?` reply is three lines, 137 bytes, and takes about 143 ms at
    9 600 baud.
  - A CH2 write re-reads `STATUS?` to check the tracking mode, which adds about
    190 ms.
- **Series and parallel tracking have never been seen on the real unit**
  (PSU-OPEN-05, -06). The tracking guard follows the manual.

---

## 5. ST S2-LP kit — library `S2lpLibrary`

The kit on the bench:

| Item | Value |
|---|---|
| Board | NUCLEO-L053R8 with the 433 MHz S2-LP board (STEVAL-FKI433V2) |
| Firmware | ST's CLI test application, unchanged; S2-LP library 1.3.5, silicon 0xC1 |
| Port | COM4 (ST-LINK virtual COM port), 115200 baud |
| Role | Receives the Kepler sensor's sub-GHz frames; can also transmit |

### 5.1 Setup

| Keyword | Arguments | Action | Returns / fails |
|---|---|---|---|
| `Open Radio` | `resource`, `board=STEVAL-FKI433V2`, `setup=None` | `S2lpDevkit.connect(board=...)`; applies the register file *setup* when given. Changes no radio setting otherwise | Identity dictionary |
| `Close Radio` | — | `close()` | — |
| `Configure For Kepler` | `setup=configs/s2lp_kepler_433_rx.regs` | `apply_configuration(setup, reset="defaults")`, then verifies it | Check dictionary. **Fails** on any register that did not take |
| `Configure Radio` | `frequency_hz`, `data_rate_bps`, `modulation`, `deviation_hz`, `bandwidth_hz` | `configure_radio()` | What the radio reads back. **Fails** outside the named board's band |
| `Configure Packets` | `preamble`, `sync_word`, `variable_length`, `crc`, `address` | `configure_packets()`. Also moves the TX source off the power-on PN9 pattern | Packet settings as read back |
| `Write Radio Register` / `Read Radio Register` | `name`, `value` | `write_register()` / `read_register()` | The value read. **Fails** on a read-only register |

### 5.2 Traffic

| Keyword | Arguments | Action | Returns / fails |
|---|---|---|---|
| `Transmit` | `payload`, `repeat=1`, `interval=100 ms` | `transmit()` or `transmit_batch()` | Packets sent. **Fails** while the TX source is PN9, or when the radio never reports the packet sent (the radio is aborted first) |
| `Receive Frames` | `count=None`, `timeout`, `registers=AFC_CORR,LINK_QUALIF2,LINK_QUALIF1,RSSI_LEVEL`, `decode=kepler` | `stream()`: one reception at a time, the registers read straight after each, each payload decoded, raw and decoded logged together | List of frame dictionaries. **Fails** only on a driver error; an empty list is a result |
| `Wait For Kepler Frame` | `sensor_id`, `type=None`, `timeout` | *Library logic*. `stream()` until a decoded frame from *sensor_id* (and of *type*) arrives | That frame. **Fails** at the timeout, saying how many other frames arrived |
| `Frame Should Have Link Quality` | `frame`, `min_rssi_dbm=None`, `min_pqi=None`, `min_sqi=None` | Compares the frame's registers | **Fails** below any limit given |
| `Stop Radio` | — | `stop()`. Safe with nothing running | — |

### 5.3 What the S2-LP work taught (#76, #77)

- **The board is not reported by the firmware**, so `Open Radio` takes it as an
  argument, and the frequency check depends on it.
- **Traffic needs three things set up.** These are the radio's interrupt routed
  to GPIO3, a TX source other than the power-on PN9 pattern, and PCKTLEN
  matching the payload. The driver does the first and third itself, and refuses
  to send without the second.
- **Every wait is the host's.** ST's receive waits indefinitely, so every
  receive keyword takes a timeout and stops the board when the timeout expires.
- **The radio is deaf while it is re-armed.** `Receive Frames` re-arms from the
  host after each frame. It is not evidence that a frame was *not* sent; a
  keyword asserting absence would need a statement of that gap.
- **Kepler sends each packet three times.** The frame count distinguishes them
  (repeat 0, 1, 2). A keyword counting packets should count repeat 0.

## 6. The first three together

The suite below powers the sensor, flashes it with its ID preserved, and checks
over BLE that it answers with the flashed version.

```robotframework
*** Settings ***
Library           benchtools.robot.Gpd3303DLibrary    AS    Supply
Library           benchtools.robot.JLinkLibrary       AS    Probe
Library           benchtools.robot.DongleLibrary      AS    Dongle
Suite Setup       Bring Up Bench
Suite Teardown    Tear Down Bench

*** Variables ***
${PSU_PORT}       COM11
${DONGLE_PORT}    COM10
${GDB}            C:/Users/dermot.murphy/tools/arm-gnu-toolchain-14.2/bin/arm-none-eabi-gdb.exe
${SENSOR_ID}      5C1712
${IMAGE}          V11.00.0000-plus-bl-and-softdevice.hex

*** Test Cases ***
Sensor Answers With The Flashed Version
    Probe.Flash Firmware    ${IMAGE}
    Probe.Sensor ID Should Be    ${SENSOR_ID}
    Dongle.Connect    ${SENSOR_ID}    timeout=30 s
    ${version}=    Dongle.Send Command And Expect Match
    ...    rd version    ^ACK rd version = (?P<value>V11\\.[0-9.]+)$    timeout=45 s
    Dongle.Reply Frames Should Be    1

*** Keywords ***
Bring Up Bench
    Supply.Open Supply    ${PSU_PORT}
    Supply.Tracking Should Be Independent
    Supply.Configure Channel    1    3.3    0.5    output=on
    Supply.Wait For Voltage    1    3.3
    Probe.Open Probe    jlink://    device=nRF52840_xxAA    gdb=${GDB}
    Dongle.Open Dongle    ${DONGLE_PORT}

Tear Down Bench
    Run Keyword And Ignore Error    Dongle.Close Dongle
    Run Keyword And Ignore Error    Probe.Close Probe
    Run Keyword And Ignore Error    Supply.Close Supply
```

This example carries decisions that are easy to get wrong:

- **Teardown order.** The dongle closes first, because it disconnects cleanly.
  The probe closes before the power goes off, because it resumes the core.
- **Voltage tolerance.** `Wait For Voltage    1    3.3` passes on a reading of
  3.2 V, because its default tolerance is 0.15 V.
- **Waiting for the sensor.** After the flash, the sensor is running (`run=True`),
  but it may take up to 9 s to advertise. `Connect`'s 10 s scan and three
  attempts cover that without a `Sleep`.
- **Two BLE checks.** `Reply Frames Should Be` catches a sensor that answers
  twice. Without it, the next test would read this test's second frame as its own
  reply.

---

## 7. Open points

1. **Whether to adopt Robot Framework** (OPEN-04). This catalogue does not decide
   that question.
   - If Robot Framework is adopted, the libraries would be a `ROBOT-` element in
     front of the existing drivers. That element would need its own requirements
     in SWE.1, and the traceability matrix would gain a row for it.
   - Robot Framework would be an optional extra (`pip install benchtools[robot]`),
     so that nothing else takes the dependency.
2. **Where the J-Link driver falls short of AD-15.**
   - `HaltInfo`, `StackFrame`, `Breakpoint` and `Watchpoint` have no `as_dict()`.
   - `rtt_expect` and `rtt_command` return `re.Match`.
   - `read_memory` returns `bytes`.
   - §1.3 has the library convert each of these. Fixing them in the driver would
     let the runner specifications use them too.
3. **A failed verify skips the preserve restore.** `JLinkProbe.flash()` raises on
   a verify mismatch *before* it writes the preserved ranges back
   (`probe.py:668-675`). A flash that fails verification can therefore leave the
   sensor with no ID. `Flash Firmware` should restore the ranges in a `finally`
   block until the driver does so itself.
4. **Library logic that belongs in the drivers.** These keywords are candidates to
   move into the drivers once the library exists:
   - `Connect`, with scan, select and retry
   - the link-lost state
   - `Erase Chip` with preserve
   - `Read Sensor ID` / `Write Sensor ID`
   - `Wait For Voltage`
   
   The command-document runner already implements the first two in
   `script_run.py`.
5. **Frames and the template.** The template maps a Frames cell to
   `Reply Frames Should Be` alone. With these keywords, a translator must also add
   `frame_window=0.5 s` to the send, and the template's mapping table should say
   so.
6. **Unmeasured figures.** Several defaults in this document are guesses:
   - `Wait For Voltage`'s 5 s timeout
   - the 15 s disconnect timeout
   - the 45 s reply timeout for a busy sensor

   The first rests on an unmeasured settling time (PSU-OPEN-04). The other two
   are single observations, not measured distributions.
