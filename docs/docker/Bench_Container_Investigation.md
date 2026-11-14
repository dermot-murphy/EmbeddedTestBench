# Bench Tools in a Container: Investigation and Recommendation

| Field | Value |
|---|---|
| **Document ID** | ETB-DOCK-001 |
| **Version** | [latest, §2](#2-revision-history) |
| **Date** | [latest, §2](#2-revision-history) |
| **Question** | Should the bench tools and the toolchain move into a Docker image, and how would the bench's instruments be reached from it? |
| **Issue** | #70 |
| **Prototype** | `docker/bench/Dockerfile` |
| **Status** | Draft. Measured on the bench PC without instruments; the J-Link and serial paths are a test plan (§7), not results |

---

## 1. Answer

**Proceed, in part.** Put benchtools, its Python and an ARM GDB in an image, and
keep every USB device and every vendor tool that drives one on the host.

1. **Into the image:** Python 3.12, benchtools with the `spec` and `serial`
   extras at CI's pins, and `arm-none-eabi-gdb` from the same Arm GNU Toolchain
   release the bench PC uses. The prototype builds (§5). CI's test and lint
   legs are already in an image (`docker/ci/`, #282).
2. **On the host:** the J-Link GDB Server, the J-Link `segger` backend,
   the PicoScope, flashing the PICO2 Test Board and updating the dongle's
   firmware. Each needs the USB device itself or a Windows vendor program.
3. **Serial instruments** (dongle COM10, GPD-3303D COM11, TTi 1604 COM13,
   PICO2 Test Board COM14, S2-LP kit COM4) are reached through a host bridge
   that publishes each port over TCP. Every serial driver already accepts
   `serial://socket://host:port` (§4.1). Use RFC 2217, not raw TCP, for any
   instrument whose line rate or handshake lines matter. Do not use usbipd for
   evidence runs (§4.3).
4. **Not yet for evidence.** A bench report does not record the software it ran
   on (§5.3). Until it names the image, and until the test plan in §7 has
   passed on the bench, evidence runs stay on the host as they are now.
5. **Cost:** about 1 s to start a container, and small-file access through a
   bind mount of `U:` about 20 times slower than on the host. Neither matters to
   a bench run; the second matters to anything that walks a large tree (§6).

---

## 2. Revision History

| Version | Date | Author | Description of Change |
|---|---|---|---|
| 0.1 | 2026-11-14 | Claude | #70: first issue. What moves into an image and what stays on the host, how each instrument is reached, the prototype `docker/bench/Dockerfile`, measured costs, and the J-Link test plan. |

---

## 3. What is left of #70

Issue #70 lists five questions. #282 (PR #283) has answered part of them:

| #70 asks | State |
|---|---|
| Python, extras and `pylint` at CI's versions, and the suite giving CI's result | **Done by #282.** `docker/ci/Dockerfile` runs `tests.yml`'s 3.8, 3.9 and 3.12 legs and `lint.yml`'s pylint leg from `constraints/*.txt`, which CI installs from too (User Manual §2.6). The Windows-only lint and test failures named in #70 are what that image avoids; whether they still fail on the Windows host was not rechecked here |
| 1. What moves into an image | §4 and the table in §4.4 |
| 2. How USB instruments are reached | §4.1 to §4.3 |
| 3. The J-Link path end to end | A test plan for the owner (§7). It needs the probe, which another session held while this was written |
| 4. Image contents, versions, recording the image in a report | §5 |
| 5. Cost: start-up, file access on `U:`, the #69 GDB crash through a bind mount | §6. The crash needs a target to reproduce; §7 step 5 covers it |

The bench image here is a second image beside the CI one, not a change to it.
The CI image holds four Pythons and the test tools; a bench image needs one
Python, the package and a GDB, and nothing that a run on the bench does not use.

---

## 4. What runs where

### 4.1 Serial instruments: the drivers already accept a TCP port

Each serial driver turns a bare port name into `serial://<name>` and passes any
other resource with a scheme through unchanged (`_normalise_resource` in each
driver). `serial://` opens the port with pyserial's `serial_for_url`
(`benchtools/core/transport/serial_port.py`), so any pyserial URL works after
it.

Checked on 2026-11-14, against a TCP listener on the host and no instrument:

| Driver | `serial://socket://127.0.0.1:P` | `socket://127.0.0.1:P` | `serial://rfc2217://127.0.0.1:P` |
|---|---|---|---|
| `Gpd3303D` | `SerialTransport`, bytes arrive | `SocketTransport` (raw SCPI socket), bytes arrive | pyserial's RFC 2217 client; refused by a plain listener, as expected |
| `NordicDongle` | same | same | same |
| `S2lpDevkit` | same | same | same |
| `Pico2TestBoard` | same | same | same |
| `Tti1604` | same | same | same |
| `SerialCapture` | same | same | same |

From inside the prototype image, `SerialTransport("socket://host.docker.internal:42331")`
sent `PROBE` to an echo listener on the Windows host and read it back.

So the issue's "already supported by the BLE and PSU drivers" understates it:
all six serial drivers accept a published port. Two cautions follow from the
check:

- **Write `serial://socket://`, not `socket://`.** The bare form opens the raw
  SCPI socket transport instead of the serial one. Bytes still pass, but the
  driver no longer gets the serial transport's behaviour (line settings,
  handshake lines, input flushing at open).
- **pyserial's `socket://` ignores the line rate, DTR and RTS.** In pyserial
  3.5, `protocol_socket.py` says "all settings are ignored" in
  `_reconfigure_port`, and `_update_dtr_state` and `_update_rts_state` only log
  "ignored". The driver's settings therefore never reach the port; the bridge's
  do. That matters for two instruments on this bench:
  - the **TTi 1604** is powered through DTR asserted and RTS cleared
    (`tti1604/dmm.py`; TTi 1604 Notes). With `socket://` the bridge must set
    both lines itself, or the meter stays silent;
  - the **GPD-3303D** line rate must match its front panel (9600). With
    `socket://` it is whatever the bridge opened the port at.

  `rfc2217://` passes the line rate and the handshake lines through to the
  host port (pyserial's `rfc2217.py` sends DTR changes to the server). That is
  why RFC 2217 is recommended for evidence runs.

### 4.2 The host bridge

Something on the Windows host must hold each COM port and publish it on a TCP
port. Options, none tried with an instrument:

| Option | Line rate and DTR/RTS from the driver | Notes |
|---|---|---|
| An RFC 2217 server built on pyserial's `serial.rfc2217.PortManager` | Yes | pyserial ships the server class; its example server script is not installed by pip. A small `benchtools` host command around it is the likeliest follow-up, so the bridge is versioned with the drivers. **Unverified** |
| A raw TCP bridge (for example `com2tcp` from com0com/hub4com, or a few lines of pyserial) | No: fixed by the bridge | Enough for the dongle, the S2-LP kit and the PICO2 Test Board, whose CDC ports ignore the line rate. Not for the TTi 1604 or the GPD-3303D unless the bridge is configured for them. **Unverified** |
| `ser2net` | Yes, in its RFC 2217 mode | A Linux program. On this PC it would run in WSL, which needs the port there first: the usbipd problem below. **Unverified** |

Whatever bridge is used, it holds the port for as long as it runs. The rule in
User Manual §8.2, one port has one owner, then applies to the bridge: a host
program cannot use COM11 while the bridge has it, and two containers can both
connect to one published port unless the bridge refuses a second client.

### 4.3 usbipd

`usbipd-win` attaches a Windows USB device to the WSL 2 virtual machine, where
a container could be given `/dev/ttyUSB0` or the J-Link itself. It was not
installed or tried (the brief forbids changing WSL or Docker settings). Against
it, for evidence runs:

- it detaches the device from Windows, so the Windows tools that use the same
  device (nrfjprog, nrfutil, the PicoScope software, the J-Link tools) lose it
  while it is attached;
- several devices on this bench re-enumerate as a different USB device during
  normal use: the dongle in its bootloader (COM8, not COM10), the PICO2 Test
  Board as the `RP2350` drive, and a J-Link after a firmware update. Each is a
  new device to usbipd, which has to attach it again before the step that
  needs it;
- whether Docker Desktop's VM has the `ftdi_sio`, `cdc_acm` and USB/IP drivers
  these devices need was not checked. **Unverified.**

A host bridge (§4.2) keeps Windows the owner of every device and moves only
bytes, which is the property an evidence run needs.

### 4.4 Each instrument

| Instrument (bench alias) | Port today | From a container | Stays on the host |
|---|---|---|---|
| J-Link on 5C1712 (`probe`, `backend: gdb`) | USB, `jlink://` | `jlink://host.docker.internal:2331`; GDB in the image, RTT on 19021 (§7) | The J-Link GDB Server, started by hand. The driver refuses to start one on another host (checked, §6.4) |
| J-Link, RTT only (`rtt`) | `jlink://127.0.0.1:2341`, RTT 19031 | `jlink://host.docker.internal:2341`, `rtt_port: 19031` | A second GDB Server, started by hand with `-port 2341 -rtttelnetport 19031 -nohalt`. The driver adds `-nohalt` only to a server it starts itself |
| J-Link, `backend: segger` | USB | No | All of it: `JLink.exe` and `JLinkRTTLogger.exe` drive the USB probe directly (#71) |
| Nordic BLE dongle (`dongle`) | COM10 | `serial://socket://host.docker.internal:<port>` through a bridge | Firmware update: the bootloader appears as another port (COM8) and `nrfutil` runs on the host |
| GPD-3303D (`psu`) | COM11, FTDI | `serial://rfc2217://...` through a bridge, so 9600 baud comes from the driver | The bridge. The supply limits of User Manual §4.3 apply unchanged |
| TTi 1604 (`dmm`) | COM13, FTDI | `serial://rfc2217://...`, so DTR on and RTS off come from the driver | The bridge |
| S2-LP kit (`s2lp`) | COM4, ST-LINK VCP | `serial://socket://...` through a bridge | The bridge. Timing that the driver measures on the host clock gains the bridge's latency (§6.3) |
| PICO2 Test Board (`pico2`) | COM14 | `serial://socket://...` through a bridge | Flashing: a 1200-baud touch on the real port, then a copy to the `RP2350` drive (`pico2_test_board/flash.py`) |
| PicoScope 3405D | USB, `ps3000a` library | No | All of it: a USB device driven through Pico's Windows library (ETB-IF-002) |
| Network instruments (TDS3014B over VXI-11, raw SCPI sockets) | LAN | Yes, as they are: outbound TCP from the container reaches the LAN through Docker's NAT | Nothing. There is no network instrument on this bench, so this is **unverified** here |

---

## 5. The image

### 5.1 The prototype

`docker/bench/Dockerfile`, with `docker/bench/Dockerfile.dockerignore` so that
it does not change what the root `.dockerignore` gives the CI image. Build from
the repository root:

```sh
docker build -f docker/bench/Dockerfile --build-arg REVISION=<commit> -t etb-bench .
```

Built on 2026-11-14 at `2b03f91` (develop):

| Item | Version | Pinned by |
|---|---|---|
| Base image | `ubuntu:24.04` | Digest, the same as `docker/ci/Dockerfile` |
| uv | 0.13.0 | Image tag, the same as `docker/ci/Dockerfile` |
| Python | 3.12.15 (python-build-standalone) | `ARG PYTHON`, CI's 3.12 patch version |
| benchtools | 0.02.0002, from the checkout, extras `spec,serial` | The build context |
| Libraries | pyserial 3.5, PyYAML 6.0.3 and the rest of `constraints/py3.12.txt` | `-c constraints/py3.12.txt` |
| ARM GDB | Arm GNU Toolchain 14.2.Rel1, GNU gdb 15.2.90.20241130-git | Release name and the SHA-256 Arm publishes beside the archive |

The ARM GDB is the same build as the bench PC's
(a user-local zip install of the Arm GNU Toolchain 14.2.Rel1, the same
`--version` line), so a difference between a host run and a container run is not a
difference of GDB. Ubuntu's `gdb-multiarch` would also do, since the driver
accepts it (`_ARM_GDB_NAMES` in `jlink/server.py`), but it is a different GDB
(`15.1-1ubuntu1~24.04.1`, `apt-cache policy` on 2026-11-14) from the one the
J-Link work was verified with.

In the image, `find_gdb()` finds `/usr/local/bin/arm-none-eabi-gdb` with no
`--gdb` option, which is the first problem #70 names.

### 5.2 What the image does not hold

No J-Link software, no `nrfjprog` or `nrfutil`, no Pico tools, no PicoScope
library, no test tools. The tests run in `etb-ci`.

### 5.3 Recording the image in a bench report

ETB-SUP8-001 §9 answers "What produced this report?" with "spec revision,
bench, instrument identities, simulated or not". The run record
(`RunRecord.as_dict` in `benchtools/runner/results.py`) holds the suite, bench,
specification source, parameters, times, the instruments and plugins, but **not
the benchtools version, the Python version or the host**. A report from a
container would say no more about its software than a report from the host
does now.

Proposed, as a follow-up rather than in this investigation (#70 changes no
code):

1. The run record gains an `environment` entry: benchtools version, Python
   version, platform, and `ETB_IMAGE_REVISION` and `ETB_IMAGE` when set. The
   prototype already sets `ETB_IMAGE_REVISION` from `--build-arg REVISION` and
   the OCI label `org.opencontainers.image.revision`.
2. The image identity a report quotes is the image ID or registry digest, passed
   in at run time (`-e ETB_IMAGE=<id>`), because a container cannot read its own
   image ID. A tag such as `etb-bench:latest` is not an identity.
3. ETB-SUP8-001 §4 then lists the bench image as the configuration item that
   identifies the software of a containerised run, with the image ID as its
   identification. This change adds the prototype to §4 only as a file in git.

---

## 6. Cost

Measured on the bench PC, 2026-11-14: Windows 10 Pro 19045, Docker Engine
29.9.2 under Docker Desktop (WSL 2 kernel 6.18.58.1), 4 CPUs and 12.5 GB given
to the VM. `U:` is a local NTFS disk (drive type 3), not a network share.

### 6.1 Build and size

| What | Result |
|---|---|
| First build, base image already present | 87 s, including the 150 MB toolchain download |
| Rebuild after a change to the `apt-get` layer, base and toolchain cached | 35 s |
| Image size | 357 MB |

### 6.2 Start-up

Ten runs each:

| Command | Time |
|---|---|
| `docker run --rm etb-bench --version` | 1.03 to 1.20 s in nine runs; 13.8 s in one |
| `docker run --rm --entrypoint true etb-bench` | 0.99 to 1.20 s |
| `python -m benchtools --version` on the host | 87 to 100 ms |
| `run specs/qualification/qs03_supply.yaml --bench benches/simulated_bench.yaml`, checkout bind-mounted read-only | 3.6 s in the container, 1.0 s on the host (one run each) |

About 1 s is Docker's own start-up. The 13.8 s run was not explained; it
did not repeat in the next 19 starts. A bench session starts a container once,
so neither figure matters to a run, but a script that starts a container per
command pays it each time.

### 6.3 Network latency to the host

1000 round trips of a 6-byte message to an echo listener on the host, with
`TCP_NODELAY`:

| Path | Median | 99th percentile | Maximum |
|---|---|---|---|
| Host to host, loopback | 0.099 ms | 0.175 ms | 0.75 ms |
| Container to `host.docker.internal` (three runs) | 0.59 to 0.67 ms | 1.06 to 1.79 ms | 3.6 to 7.5 ms |

Docker Desktop delivered connections from `host.docker.internal` to a listener
bound to `127.0.0.1` on the host. So a host bridge or GDB Server listening on
loopback only would still be reachable from a container (inferred for the GDB
Server, which was not run).

The added half millisecond, with spikes of several, does not affect the
dongle's measurements, which the dongle timestamps itself (BLE Dongle Notes
§1). It is added to anything timed on the host clock: the J-Link's
`HOST_CLOCK` method, the serial capture instrument's line times, and the S2-LP
kit's polled receive gaps (#293 measured a 26 to 27 ms deaf gap). A test that
asserts on such a time from a container needs its limits checked against this.

### 6.4 File access through a bind mount of `U:`

Dummy files only: one 2.9 MB Intel HEX file and 2000 files of 2 KiB, three runs
each:

| Where | Read the HEX file | Read 2000 small files | Write 2000 small files |
|---|---|---|---|
| Host, on `U:` | 1.5 to 1.7 ms | 275 to 277 ms | 784 to 798 ms |
| Container, bind mount of `U:` | 17 to 19 ms | 5.73 to 5.86 s | 6.45 to 6.50 s |
| Container, its own file system | 0.4 to 1.5 ms | 35 to 41 ms | 109 to 116 ms |

Copying the 2000 files from the bind mount into the container took 9.0 s.
Opening a file through the bind mount costs about 3 ms. A bench run reads one
specification, a bench file and perhaps a HEX or ELF file, and writes four
records, so it pays a few tens of milliseconds. Walking a tree is another
matter, which is why `etb-ci` copies the checkout into the container first.

### 6.5 GDB and a HEX file on `U:`

#69 recorded GDB 15.2 exiting on `file` followed by `load` of a HEX file on
`U:`. Without a target, `load` cannot run, so the crash could not be
reproduced here. What was checked: GDB in the container, given the dummy HEX
through the bind mount, read it (`file type ihex`, the sections listed), and the
host GDB did the same from `U:`; both refused `load` with no target, as
expected. §7 step 5 is the real check.

### 6.6 J-Link resource from the container

`jlink --resource jlink://host.docker.internal:42339 --device nRF52840_xxAA
info` in the container, with nothing listening on that port, failed with "a GDB
Server cannot be started on another machine". The driver treats
`host.docker.internal` as remote and does not try to start a server, as AD-13
requires. Port 42339 was chosen so as not to touch the GDB Server's ports.

---

## 7. Test plan for the J-Link path (for the owner, on the bench)

Not run: it needs the probe and sensor 5C1712, and another session was using
them. This repeats the #69 sequence through the container. Follow User Manual
§4.3 and §8.2: back up the sensor first, and reset it after any run that
attaches.

**Set-up.**

1. Build the image at the commit under test:
   `docker build -f docker/bench/Dockerfile --build-arg REVISION=<commit> -t etb-bench .`
   and note the image ID (`docker image inspect -f "{{.Id}}" etb-bench`).
2. Start the GDB Server on the host, by hand, and leave it running:

   ```
   JLinkGDBServerCL -device nRF52840_xxAA -if SWD -speed 4000 -port 2331 ^
                    -rtttelnetport 19021 -nogui -strict
   ```

   Record whether it listens on loopback only or on every interface
   (`netstat -an | findstr 2331`); §6.3 suggests either works.
3. Copy the full images onto `U:` under the checkout: for V10,
   `KAPPAX_PCB_V4X_Production_APP_PLUS_SD_V10.01.2000.hex` (application and
   SoftDevice s140 6.1.0, as in the 2026-09-26 round trip); for V11, the merged
   `-plus-bl-and-softdevice.hex` image; and the V11 ELF. Mount the checkout:
   every path given to the driver is a container path
   (`/work/...`). A bench file used in the container must not name
   `gdb_executable`: the Windows path in `benches/bench_pc.yaml` is used as given
   and does not exist in the container.

**Sequence**, each with
`docker run --rm -v "${PWD}:/work" etb-bench jlink --resource jlink://host.docker.internal:2331 --device nRF52840_xxAA ...`:

**A chip erase clears UICR as well as flash** (seen on 5C1712 on 2026-11-14,
PR #337): CUSTOMER[0] at `0x10001080`, which holds the sensor ID, and the
bootloader address at `0x10001014`/`0x10001018`. So every image flashed after
step 2 must be a full image, with the SoftDevice and, for V11, the bootloader
and settings. After an application-only HEX the sensor may not boot, and steps
6 and 9 then fail. Step 0 takes the backup that step 10 restores.

| Step | Command | Pass if |
|---|---|---|
| 0 | On the host, before anything else: `nrfjprog -f NRF52 --readcode <backup>.hex --readuicr` | The file holds code flash and UICR. Copy it beside the images on `U:` |
| 1 | `info` | The probe and core are reported, as on the host |
| 2 | `erase` | Reported erased and blank-checked. Until step 10 the sensor has no ID and no bootloader address |
| 3 | `flash /work/KAPPAX_PCB_V4X_Production_APP_PLUS_SD_V10.01.2000.hex` | Flash and verify succeed |
| 4 | `write 0x10001080 005c1712` (the word `0x12175C00`), then `read 0x10001080 4` | Reads `005c1712` |
| 5 | `flash --preserve 0x10001080:4 /work/<V11>-plus-bl-and-softdevice.hex`, the HEX on `U:` through the bind mount | Succeeds; GDB does not exit (the #69 fault, §6.5) |
| 6 | `reset --run`, then `rtt --duration 10` | RTT shows `Sensor ID is: 0x5C1712` and the version of the HEX flashed in step 5 |
| 7 | With `--elf /work/<V11>.elf`: `var`, `stack` | Values and a call stack as on the host |
| 8 | The `rtt` alias: a second GDB Server on the host with `-port 2341 -rtttelnetport 19031 -nohalt`, and `jlink-rtt` at `jlink://host.docker.internal:2341`, `rtt_port: 19031`, while the dongle runs a BLE scan on the host | RTT lines arrive; the sensor keeps advertising (no attach, #95) |
| 9 | `nrfjprog -f NRF52 --reset` on the host; BLE scan | `KAPPA_5C1712_` advertises with the version of the HEX flashed in step 5 |
| 10 | Restore on the host, not through the container, so a fault in the container path cannot stop it: `nrfjprog -f NRF52 --program <backup>.hex --chiperase --verify`, then `nrfjprog -f NRF52 --memrd 0x10001080 --n 4` and `--memrd 0x10001014 --n 8`, then `nrfjprog -f NRF52 --reset` last, because `--memrd` leaves the core halted. The chip erase matters: after step 5 has written UICR, a load without an erase cannot set a UICR bit back from 0 to 1 | Reads `0x12175C00` (bytes `005c1712`), and `0x000F8000 0x000FE000` (bytes `00800f0000e00f00`); the sensor advertises the version it ran before step 0 | Reads `005c1712` and `00800f0000e00f00`; the sensor advertises the version it ran before step 0 |

For each step record the image ID, the GDB Server version, the time taken and
the time the same step takes on the host. A step that fails in the container
and passes on the host is a finding about the container path, not the driver.

**Serial instruments**, once a bridge is chosen (§4.2): run
`specs/qualification/qs10_bench_identity.yaml` from the container with a bench
file whose serial resources are `serial://rfc2217://host.docker.internal:<port>`,
and compare every identity line with the same run on the host. The TTi 1604 is
the first to try with `socket://`, because it is the one that shows whether the
handshake lines arrived.

---

## 8. Verified and not verified

| Claim | State |
|---|---|
| All six serial drivers accept `serial://socket://` and `serial://rfc2217://` and reach a TCP port | Verified, against a TCP listener |
| A bare `socket://` gives the raw SCPI socket transport | Verified |
| pyserial 3.5 `socket://` ignores line rate, DTR and RTS; `rfc2217://` sends them | Read in pyserial's source; not exercised with an RFC 2217 server |
| The prototype builds; GDB 15.2.90 from 14.2.Rel1 runs in it and `find_gdb()` finds it | Verified |
| A container reaches a loopback-only host listener at `host.docker.internal` | Verified, with an echo listener |
| The driver refuses to start a GDB Server on `host.docker.internal` | Verified |
| Start-up, latency and file access figures | Measured once on this PC; one unexplained 13.8 s start |
| The J-Link GDB Server reached from the container; the #69 sequence | **Not verified**: §7 |
| The #69 GDB exit with a HEX file on `U:` does not recur through a bind mount | **Not verified**: needs a target |
| Serial instruments through any host bridge | **Not verified**: no bridge was run against an instrument |
| usbipd with Docker Desktop | **Not verified**: not installed |
| VXI-11 and raw-socket instruments from a container | **Not verified**: none on this bench |
| `gdb-multiarch` in Ubuntu 24.04 is 15.1 | Verified with `apt-cache policy`; not installed or run |

---

## 9. Follow-up issues proposed

1. Record the software environment in the run record and report: benchtools
   version, Python, platform, image revision and ID (§5.3).
2. A host serial bridge command with RFC 2217, so the bridge is part of
   benchtools and its version is known (§4.2).
3. The bench test plan in §7, run by the owner, and its results added here.
4. A container bench file (`benches/bench_pc_container.yaml`) with
   `host.docker.internal` resources and no Windows paths, once 2 and 3 are done.
5. If the image is kept: build it in CI as `ci_image.yml` builds `docker/ci/`.
