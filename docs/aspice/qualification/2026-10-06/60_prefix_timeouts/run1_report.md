# BLE command and response results

| | |
|---|---|
| Result | **PASS** |
| Document | `U:/Temp/claude/U--GitHub-EmbeddedTestBench/8e5a5735-0595-4527-bb3b-8c1e42cfdb4d/scratchpad/hw233/prefix_timeouts.md` |
| Sensor | KAPPA_5C1712_V11.00.000 D1:8D:3B:4C:19:96 |
| Variables | RD_MS=20000, SENSOR_ID=D1:8D:3B:4C:19:96 |
| Timeouts by prefix | RD 20000 ms (document), rd version 5000 ms (document), RD ID 2000 ms (document), ECURESET 15000 ms (document) |
| Steps | 6 passed, 0 failed, 0 errors, 4 skipped |

Times are from the end of the command to the start of the response, quoted to 10 ms. The timeout is the longest a step waited, and why: its Timeout cell, the longest command prefix it starts with, or the run's default. Results, first that applies: ERROR when the system returned a failure code, SKIP when nothing was expected, FAIL when the reply differs, PASS when it matches.

| Test | Step | Command | Expected | Actual | Response time (ms) | Timeout | Result | Note |
|---|---|---|---|---|---|---|---|---|
| Prefixes | 1 | connect D1:8D:3B:4C:19:96 |  | linked to KAPPA_5C1712_V11.00.000 D1:8D:3B:4C:19:96 | 11250 | 30000 ms, Timeout cell | SKIP | linked to KAPPA_5C1712_V11.00.000 D1:8D:3B:4C:19:96 - prefix not applied |
| Prefixes | 2 | RD VERSION | /^ACK RD VERSION/ | ACK RD VERSION = V11.00.0000-95-gc051f3665 | 130 | 5000 ms, prefix rd version (document) | PASS | expect 5000, prefix rd version |
| Prefixes | 3 | RD TEMPERATURE | /^ACK RD TEMPERATURE = -?[0-9]+mC$/ | ACK RD TEMPERATURE = 21187mC | 60 | 20000 ms, prefix RD (document) | PASS | expect RD |
| Prefixes | 4 | RD BATTERY | /^ACK RD BATTERY/ | ACK RD BATTERY = 2789mV | 90 | 8000 ms, Timeout cell | PASS | expect Timeout cell |
| Prefixes | 5 | RD ID |  | ACK RD ID = 0x5C1712 | 40 | 2000 ms, prefix RD ID (document) | SKIP | the document gives no expected response - listening window 2000 |
| Prefixes | 6 | XX NOTHING | /^NACK/ | NACK Invalid Command | 40 | 3000 ms, run default (--timeout-s) | PASS | expect run default |
| Prefixes | 7 | ECURESET HARD | <disconnect> | <disconnect> | 4120 | 15000 ms, prefix ECURESET (document) | PASS | expect 15000 prefix |
| Prefixes | 8 | connect D1:8D:3B:4C:19:96 |  | linked to KAPPA_5C1712_V11.00.000 D1:8D:3B:4C:19:96 | 13010 | 30000 ms, Timeout cell | SKIP | linked to KAPPA_5C1712_V11.00.000 D1:8D:3B:4C:19:96 |
| Prefixes | 9 | rd version | /^ACK rd version/ | ACK rd version = V11.00.0000-95-gc051f3665 | 50 | 5000 ms, prefix rd version (document) | PASS |  |
| Prefixes | 10 | disconnect |  |  | - | - | SKIP | link closed |
