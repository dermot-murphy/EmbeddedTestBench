# #349 on the bench: attaching to a core that a running GDB Server left running

The run was on 2026-11-15, on the bench PC, with the J-Link probe and sensor
5C1712 running V10.01.2000.

## Set-up

- **GDB Server:** one J-Link GDB Server V9.42 on the host, started by hand, and
  left running for the whole check (`-port 2331 -rtttelnetport 19021 -strict`,
  no `-nohalt`). Its log is `gdbserver_2331.log`.
- **Clients:** each numbered file is one CLI call, connecting to that server as
  a new client.
  - `etb-bench` is the image built at `aa75c21` (develop), ID `sha256:5485c0a6…`. This is the driver before the fix.
  - `etb-bench:349` is built from this branch. Files 05 to 09 used a first build, `sha256:8e201857…`, made before `halt` reported the core's location. Files 20 to 25 used the final build, `sha256:33ddb8d4…` (`image_349.txt`).
  - Files 10 and 11 ran the fixed driver on the host, as `jlink://127.0.0.1:2331`.
- **Container calls:** `docker run --rm <image> jlink --resource jlink://host.docker.internal:2331 --device nRF52840_xxAA <command>`.

## What triggers the fault

What the next client finds depends on how the last one ended. The server log
shows this:

- **The last client ended with the driver's `monitor go`** (`info`, `read`, `halt` then close). GDB did not see that the core was resumed, so it detached from what it believed was a stopped core. The next client finds the core **running**, and the server answers `Cannot read register 15 (R15) while CPU is running`.
- **The last client ended after `-exec-continue`** (`reset --run`). GDB knew the core was running, and the core was **halted** at the detach. The next client finds it halted.

So the fault shows on the second of two calls that each end with `monitor go`.

## Results

| Files | Image | Sequence | Result |
|---|---|---|---|
| 12, 13, 14 | develop | `info`, `info`, `halt` | 13: `"halted": true`, PC **`0xdeadbeef`**. 14: `halt` returned at once with address `0x00000000`, and the core kept running (the next attach read `0xDEADBEEF`). **The fault.** |
| 02, 03 | develop | `info` after `reset --run`, then `halt` | 02 found the core halted (see above); 03 shows the same false `halt` as 14 |
| 16, 17, 18 | fixed (first build) | `info`, `info`, `halt` | 17: PC `0x00015f5a`. The log shows the attach finding the core running, then `monitor halt`. 18 really halted the core: log line 1014 reads PC `0x0002764E` after its `monitor halt`. But it reported address `0x00000000`, because that build's `halt` did not yet report the location |
| 20 to 24 | fixed (final) | `info` three times, `halt`, `info` | Every PC read is real (`0x0002764e`, then `0x00015f5a`). 23: `halt` reports `0x00015f5a`. Server log lines 1169 to 1421: each `Cannot read register 15` is followed by `Received monitor command: halt` |
| 05 to 11 | fixed | `info`, `reset --run`, `halt`, `info`, `reset --run`; host `info`, `reset --run` | All succeed. 06 and 09 attached to a running core and halted it before the reset |

At the end the server was stopped, 5C1712 was reset with `nrfjprog -f NRF52
--reset` (`26_nrfjprog_reset.txt`), and it advertised `KAPPA_5C1712_V10.01.2000P`
(`27_ble_scan.txt`).

## Not covered

- **The call stack.** No ELF matches V10.01.2000, so `stack` was not run here. The #70 run on 2026-11-15 (`../70_jlink_container/`, step 7) showed a running core giving `?? at 0xdeadbeee`, and a real stop giving a 5-frame stack.
- **The fix's attach after `-exec-continue`.** The core was already halted in that case. `monitor halt` on a halted core changed nothing (05, 07).
