# #271 on hardware: DFU data lost on an SDK 15.2 bootloader

Evidence for ETB-SWE4-002 §10.7. Run on 2026-10-23 on the bench PC with the
Kepler bench description `bench_kepler.yaml` (innovateuk-sensor TX-1184): the
PCA10059 dongle on COM10 with firmware 1.7.0, the GPD-3303D on COM11 (CH2
3.3 V, CH1 off) and the J-Link on sensor 5C1712 (D1:8D:3B:4C:19:96). CPython
3.14.7 on Windows 10, with `benchtools` imported from this repository's
working tree on `hotfix/v0.02.0001` (`PYTHONPATH`), version 0.02.0001.

Each run's setup puts 5C1712 on Kepler V10.00.0000 with bootloader V1.01.0000
(nRF5 SDK 15.2) through the J-Link, keeping UICR, and each run ends by
restoring the DEBUG combined image, NORMAL mode and FACTORY; every restore
passed and the supply was switched off at the end of each. The packages are
Kepler's: `KAPPAX_Release_BL_V2.00.0000_UPGRADE_OTA.zip` (SoftDevice and
bootloader V2.00.0000), `KAPPAX_APP_SDK17_PCB_V4X_RELEASE_OTA.zip` and the V5
DEBUG application (for a refusal). The specifications name those files in the
innovateuk-sensor checkout, so they do not run from this repository alone.

## Runs

| Folder | Code | Result |
|---|---|---|
| `271_dfu_lost_data/attempt_1_object_retry/` | 5e0bdd6: receipts checked, the lost object created again | The receipt after offset 160 reported offset 0 and CRC 0; the object created again was refused with `60 01 05` (`InvalidObject`). Upgrade failed after 641 bytes |
| `271_experiments/e1_pause_0_5/` | 5e0bdd6 plus `create_pause` and `prn` parameters | SoftDevice and bootloader package with 0.5 s after each data create: `Success`, 177 869 bytes in 68.5 s, no loss |
| `271_experiments/e5_pause_0_15/` | as e1 | The same with 0.15 s: `Success`, 177 869 bytes in 53.4 s, no loss |
| `271_dfu_lost_data/attempt_2_image_retry/` | the committed fix: the image sent again from its init packet, 0.15 s after each data create on the first retry | Package 1 lost data, then `Success` on retry 1 (178 510 bytes, 53.7 s). Package 2 not attempted: the new bootloader was not heard within the specification's 5 s scan |
| `271_dfu_lost_data/attempt_3_image_retry_scan30/` | as attempt 2 | `release_legacy_ota_scan30.yaml`, Kepler's V10-F-01 specification with only `scan_seconds: 30.0` added to package 2: **PASS**, 3 of 3. Package 1 and package 2 each lost data and succeeded on retry 1 (178 510 bytes in 53.6 s; 299 136 bytes in 111.6 s); the V5 package was refused with `ExtendedError` / `HwVersionFailure` |

Attempt 1, attempt 2 and the experiments ran on uncommitted changes to the
working tree; `console.log` gives the commit it was on (and, for the
experiments, the files changed). The code of attempts 2 and 3 is the code of
the hotfix's second commit.

In every run without a pause the loss is at the same place: the first receipt
of the first data object (offset 160) is right, and the next, due at 304,
reports offset 0 and CRC 0. With a pause after each data create nothing was
lost. That writes are lost while the object's flash page is erased is the
inference, not a traced cause.

## Files

Each run folder holds the runner's console output (`console.log`), its JSON
and markdown reports, the event log (every dongle line, with the receipts as
`+rx` and each retry as a warning) and the dongle session log
(`ble_session.log`, with each retry as a `#` note).

| File | What it is |
|---|---|
| `271_experiments/exp_271.yaml` | The experiment specification: Kepler's setup and restore, and one SoftDevice and bootloader transfer per variant (E1 to E5; E2 to E4 were not run) |
| `271_dfu_lost_data/release_legacy_ota_scan30.yaml` | Kepler's `release_legacy_ota.yaml` with absolute package paths and `scan_seconds: 30.0` on package 2 |

The runs were started with:

```
python -m benchtools run <specification> --bench bench_kepler.yaml --acknowledge \
    [--test "E1 pause 0.5 s after each data create" \
     --test "Restore 5C1712 - sensor ID, DEBUG image, NORMAL mode, FACTORY"] \
    --markdown <report>.md --json <result>.json --event-log <events>.log
```

`--acknowledge` confirms the specification's warning (reflash, supply on), on
the owner's instruction for this run.
