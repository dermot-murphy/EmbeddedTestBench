# #70: the J-Link path from the bench container, on the bench

The run was on 2026-11-15, on the bench PC, with the J-Link probe and sensor
5C1712. It is the J-Link half of the test plan in ETB-DOCK-001 §7
(`docs/docker/Bench_Container_Investigation.md`). The results and findings are
in that document's §7.1. This folder holds the record.

## Set-up

| Item | Value |
|---|---|
| Image | `etb-bench`, ID `sha256:5485c0a641f00ed031418eff520de8c442f87922e80cf2aaf0b0734e3125b644`, label `org.opencontainers.image.revision` `aa75c21` (develop, after #348) |
| In the image | Python 3.12.15, benchtools 0.02.0002, GNU gdb 15.2.90.20241130-git (Arm GNU Toolchain 14.2.Rel1) |
| Docker | 29.9.2, Docker Desktop on Windows 10 |
| GDB Server | SEGGER J-Link GDB Server V9.42 on the host, started by hand. `gdbserver_2331.log` is the one for steps 1 to 7 (`-port 2331 -rtttelnetport 19021 -strict`); `gdbserver_2341.log` is the one for step 8 (`-port 2341 -rtttelnetport 19031 -nohalt`). Each listened on `127.0.0.1` only |
| Probe | J-Link OB V8.00, S/N 682395790. Target nRF52840, VTref 3.28 V |
| Host tools | nrfjprog (`C:\tools\nrf-command-line-tools`); the dongle on COM10 for BLE scans, run with `C:\compilers\python\python311\python.exe -m benchtools` from this branch |

**Images.** They are Sensoteq's and are not in this repository. They were
copied from innovateuk-sensor's `software/output` into a folder on `U:` outside
the checkout, and mounted read-only at `/work`:

| File | SHA-256 |
|---|---|
| `KAPPAX_PCB_V4X_Production_APP_PLUS_SD_V10.01.2000.hex` (from `legacy_images/V10.01.2000`) | `e040246038c14ed899752c2ed7974f16589794b9ab46cc7fe270316122ccbcef` |
| `KAPPAX_APP_SDK17_PCB_V4X_RELEASE-plus-bl-and-softdevice.hex`, V11.03.0000-160-g046094e6c (from `KAPPAX_APP_SDK17_PCB_V4X_RELEASE/package`) | `18419f55221f1773714b9ae878c1d5d853bae5a597aeea5262ee1e67edba51bd` |
| `KAPPAX_APP_SDK17_PCB_V4X_RELEASE.elf`, the same build (from `.../exe`) | `a8741c77220c37d1df8798eedf078c527f07eb60b0b4e99654265b60932e9e18` |

The plan names no V11 version. V11.00.0000, the version #239 pins, was not
used because `legacy_images/V11.00.0000` holds no ELF, and step 7 needs one
from the same build as the image flashed in step 5.

**Backup.** Step 0's backup of 5C1712 (code flash and UICR, V10.01.2000) is
kept outside the repository, at
`C:\Users\dermot.murphy\Documents\bench_backups\5c1712\5c1712_V10.01.2000_2026-11-15.hex`
(SHA-256 `5f221ee4bb4c667d38e61434b0ab527bf2c7461a94984a83031a992b887cf680`).

## How each container step was run

`container_step.sh <label> <jlink arguments>` runs

```sh
docker run --rm -v <images>:/work:ro -v <this folder>:/out etb-bench \
    jlink --resource jlink://host.docker.internal:2331 --device nRF52840_xxAA <arguments>
```

and writes the output to `<label>.txt` and the time to `timings.txt`. The
times are wall-clock times on the host, so they include starting the container.

## Files

| Step | Files |
|---|---|
| 0 | None here (the backup is above). It was taken with `nrfjprog -f NRF52 --readcode <backup> --readuicr` and read `0x10001080: 12175C00` and `0x10001014: 000F8000 000FE000` |
| 1 | `step1_info.txt` |
| 2 | `step2_erase.txt`; `step2_read_flash.txt` and `step2_read_uicr.txt` show it blank |
| 3 | `step3_flash_v10.txt` |
| 4 | `step4_write.txt`, `step4_read.txt` |
| 5 | `step5_flash_v11.txt`, `step5_read_id.txt`, `step5_read_bl.txt` |
| 6 | `step6_reset.txt`, `step6_rtt.txt`, `step6_rtt.log` |
| 7 | First try, with no stop: `step7_var.txt`, `step7_var2.txt`, `step7_stack.txt`, `step7_info_after.txt`. With `halt`: `step7b_*.txt`. With a breakpoint: `step7c_run_until.txt`, `step7c_stack.txt`, `step7c_var.txt`. Then `step7_end_reset.txt`. The halt fault is #349 |
| 8 | `bench_container_rtt.yaml`, `step8_rtt.yaml`, `step8_run.txt`, `step8_report.md`, `step8_rtt.log`, `step8_ble_scan.txt`; the two failed attempts in `step8_attempt1/` and `step8_attempt2/` |
| 9 | `step9_reset.txt`, `step9_ble_scan.txt` |
| 10 | The first attempt, which failed verify: `step10_restore.txt`. The second: `step10_restore_attempt2.txt`, `step10_final_verify.txt`, `step10_ble_scan.txt` |
| Host comparison | `host_info.txt`, `host_read_*.txt` (the driver starting its own GDB Server); the host `var` and `stack` against the step 1-7 server are in `timings.txt` only |
| All | `timings.txt`, `container_step.sh`, `gdbserver_2331.log`, `gdbserver_2341.log` |

In `timings.txt`, the three `step8_rtt_alias` lines are attempts 1, 2 and 3 in
that order.

`bench_container_rtt.yaml` names the bench `Bench PC from a container (rtt
only, #70)`, but YAML reads `#70)` as a comment, so the report shows the name
cut short. The file is kept as it ran.

## Result

Every step passed. Step 7 needed a breakpoint, because the driver's `halt`
does not stop a core that a GDB Server already running lets run (#349).
Step 8's specification passed at the third attempt. Step 10 needed a separate
`--eraseall`. The sensor ended as it started, on V10.01.2000, advertising
`KAPPA_5C1712_V10.01.2000P`.
