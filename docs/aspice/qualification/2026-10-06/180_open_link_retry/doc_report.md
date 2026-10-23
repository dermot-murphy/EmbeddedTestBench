# BLE command and response results

| | |
|---|---|
| Result | **PASS** |
| Document | `U:/Temp/claude/U--GitHub-EmbeddedTestBench/8e5a5735-0595-4527-bb3b-8c1e42cfdb4d/scratchpad/hw234/connect_after_reset.md` |
| Sensor | KAPPA_5C1712_V11.00.000 D1:8D:3B:4C:19:96 |
| Variables | SENSOR_ID=D1:8D:3B:4C:19:96 |
| Steps | 17 passed, 0 failed, 0 errors, 10 skipped |

Times are from the end of the command to the start of the response, quoted to 10 ms. Results, first that applies: ERROR when the system returned a failure code, SKIP when nothing was expected, FAIL when the reply differs, PASS when it matches.

| Test | Step | Command | Expected | Actual | Response time (ms) | Result | Note |
|---|---|---|---|---|---|---|---|
| Cycles | 1 | connect D1:8D:3B:4C:19:96 |  | linked to KAPPA_5C1712_V11.00.000 D1:8D:3B:4C:19:96 | 12740 | SKIP | linked to KAPPA_5C1712_V11.00.000 D1:8D:3B:4C:19:96 |
| Cycles | 2 | RD VERSION | /^ACK RD VERSION/ | ACK RD VERSION = V11.00.0000-95-gc051f3665 | 40 | PASS |  |
| Cycles | 3 | ECURESET HARD | <disconnect> | <disconnect> | 4120 | PASS | cycle 1 |
| Cycles | 4 | connect D1:8D:3B:4C:19:96 |  | linked to KAPPA_5C1712_V11.00.000 D1:8D:3B:4C:19:96 | 12890 | SKIP | linked to KAPPA_5C1712_V11.00.000 D1:8D:3B:4C:19:96 |
| Cycles | 5 | RD VERSION | /^ACK RD VERSION/ | ACK RD VERSION = V11.00.0000-95-gc051f3665 | 40 | PASS |  |
| Cycles | 6 | ECURESET HARD | <disconnect> | <disconnect> | 4120 | PASS | cycle 2 |
| Cycles | 7 | connect D1:8D:3B:4C:19:96 |  | linked to KAPPA_5C1712_V11.00.000 D1:8D:3B:4C:19:96 | 14400 | SKIP | linked to KAPPA_5C1712_V11.00.000 D1:8D:3B:4C:19:96 |
| Cycles | 8 | RD VERSION | /^ACK RD VERSION/ | ACK RD VERSION = V11.00.0000-95-gc051f3665 | 640 | PASS |  |
| Cycles | 9 | ECURESET HARD | <disconnect> | <disconnect> | 4140 | PASS | cycle 3 |
| Cycles | 10 | connect D1:8D:3B:4C:19:96 |  | linked to KAPPA_5C1712_V11.00.000 D1:8D:3B:4C:19:96 | 13330 | SKIP | linked to KAPPA_5C1712_V11.00.000 D1:8D:3B:4C:19:96 |
| Cycles | 11 | RD VERSION | /^ACK RD VERSION/ | ACK RD VERSION = V11.00.0000-95-gc051f3665 | 40 | PASS |  |
| Cycles | 12 | ECURESET HARD | <disconnect> | <disconnect> | 4110 | PASS | cycle 4 |
| Cycles | 13 | connect D1:8D:3B:4C:19:96 |  | linked to KAPPA_5C1712_V11.00.000 D1:8D:3B:4C:19:96 | 14530 | SKIP | linked to KAPPA_5C1712_V11.00.000 D1:8D:3B:4C:19:96 |
| Cycles | 14 | RD VERSION | /^ACK RD VERSION/ | ACK RD VERSION = V11.00.0000-95-gc051f3665 | 630 | PASS |  |
| Cycles | 15 | ECURESET HARD | <disconnect> | <disconnect> | 4140 | PASS | cycle 5 |
| Cycles | 16 | connect D1:8D:3B:4C:19:96 |  | linked to KAPPA_5C1712_V11.00.000 D1:8D:3B:4C:19:96 | 14440 | SKIP | linked to KAPPA_5C1712_V11.00.000 D1:8D:3B:4C:19:96 |
| Cycles | 17 | RD VERSION | /^ACK RD VERSION/ | ACK RD VERSION = V11.00.0000-95-gc051f3665 | 640 | PASS |  |
| Cycles | 18 | ECURESET HARD | <disconnect> | <disconnect> | 4120 | PASS | cycle 6 |
| Cycles | 19 | connect D1:8D:3B:4C:19:96 |  | linked to KAPPA_5C1712_V11.00.000 D1:8D:3B:4C:19:96 | 14410 | SKIP | linked to KAPPA_5C1712_V11.00.000 D1:8D:3B:4C:19:96 |
| Cycles | 20 | RD VERSION | /^ACK RD VERSION/ | ACK RD VERSION = V11.00.0000-95-gc051f3665 | 640 | PASS |  |
| Cycles | 21 | ECURESET HARD | <disconnect> | <disconnect> | 4120 | PASS | cycle 7 |
| Cycles | 22 | connect D1:8D:3B:4C:19:96 |  | linked to KAPPA_5C1712_V11.00.000 D1:8D:3B:4C:19:96 | 12970 | SKIP | linked to KAPPA_5C1712_V11.00.000 D1:8D:3B:4C:19:96 |
| Cycles | 23 | RD VERSION | /^ACK RD VERSION/ | ACK RD VERSION = V11.00.0000-95-gc051f3665 | 30 | PASS |  |
| Cycles | 24 | ECURESET HARD | <disconnect> | <disconnect> | 4140 | PASS | cycle 8 |
| Cycles | 25 | connect D1:8D:3B:4C:19:96 |  | linked to KAPPA_5C1712_V11.00.000 D1:8D:3B:4C:19:96 | 14380 | SKIP | linked to KAPPA_5C1712_V11.00.000 D1:8D:3B:4C:19:96 |
| Cycles | 26 | RD VERSION | /^ACK RD VERSION/ | ACK RD VERSION = V11.00.0000-95-gc051f3665 | 640 | PASS |  |
| Cycles | 27 | disconnect |  |  | - | SKIP | link closed |
