# #352 on the bench: a variable at address 0 is refused

The run was on 2026-11-15, on the bench PC, with the J-Link probe and sensor 5C1712.

## Set-up

- **Sensor:** 5C1712 was running V10.01.2000.
- **ELF:** each call loaded the ELF of the V11.03.0000-160-g046094e6c release build. Its SHA-256 is `a8741c77…cf2aaf0b`, as in `../70_jlink_container/README.md`. It does not match the image the sensor runs, and it does not need to:
  - GDB finds `&m_freq` in the ELF alone, at `0x0`, so the refusal happens before anything is read from the target;
  - develop's driver reads address 0, which holds the initial stack pointer, `0x20000400`, in both images.
- **Driver:** run on the host, `C:\compilers\python\python311\python.exe -m benchtools jlink -r jlink:// -d nRF52840_xxAA --gdb <arm-none-eabi-gdb> -e <ELF> ...`. The driver started its own GDB Server for each call.
- **01:** run with `develop`'s `probe.py` (`f7ab974`) in place of this branch's.
- **02 to 04:** run with this branch.

## Results

| File | Call | Result |
|---|---|---|
| `01_develop_var_m_freq.txt` | `var m_freq`, `develop` | Exit 0; `"address": "0x00000000"`, `"value": 536871936` (`0x20000400`). **The fault** |
| `02_fix_var_m_freq.txt` | `var m_freq` | Exit 1: `cannot read 'm_freq': GDB places it at address 0 ...` |
| `03_fix_var_m_freq_set.txt` | `var m_freq --set 5` | Exit 1: `cannot write 'm_freq' ...`. Nothing was written |
| `04_fix_read_0.txt` | `read 0x0 4` | Exit 0; `00040020`. A raw memory read of address 0 is still allowed, as it should be |
| `05_nrfjprog_reset.txt`, `06_ble_scan.txt` | Host reset, BLE scan | 5C1712 advertised `KAPPA_5C1712_V10.01.2000P` |
