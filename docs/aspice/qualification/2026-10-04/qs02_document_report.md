# BLE command and response results

| | |
|---|---|
| Result | **PASS** |
| Document | `U:\GitHub\EmbeddedTestBench\specs\qualification\qs02_kepler_commands.md` |
| Sensor | KAPPA_5C1712_V11.00.000 D1:8D:3B:4C:19:96 |
| Variables | REPLY_MS=45000, SENSOR_ID=5C1712, SETTLE_MS=500 |
| Steps | 8 passed, 0 failed, 0 errors, 5 skipped |

Times are from the end of the command to the start of the response, quoted to 10 ms. Results, first that applies: ERROR when the system returned a failure code, SKIP when nothing was expected, FAIL when the reply differs, PASS when it matches.

| Test | Step | Command | Expected | Actual | Response time (ms) | Result | Note |
|---|---|---|---|---|---|---|---|
| Connect and identify | 1 | connect 5C1712 |  | linked to KAPPA_5C1712_V11.00.000 D1:8D:3B:4C:19:96 | 11640 | SKIP | linked to KAPPA_5C1712_V11.00.000 D1:8D:3B:4C:19:96 - Selected by part of its name |
| Connect and identify | 2 | delay 500 ms |  |  | 500 | SKIP | a delay makes no claim about the sensor - A delay is skipped, not passed |
| Connect and identify | 3 | RD VERSION | /^ACK RD VERSION = V[0-9]+\.[0-9]+\.[0-9]+/ | ACK RD VERSION = V11.00.0000-95-gc051f3665 | 40 | PASS | Any version of that shape |
| Connect and identify | 4 | RD ID | /(?i)^ACK RD ID = (0x)?5C1712$/ | ACK RD ID = 0x5C1712 | 40 | PASS | The identifier in its advertising name |
| Connect and identify | 5 | RD SHA | /^ACK RD SHA = [0-9a-f]{7,40}$/ | ACK RD SHA = c051f3665 | 40 | PASS |  |
| Readings | 1 | RD TEMPERATURE | /^ACK RD TEMPERATURE = -?[0-9]+mC$/ | ACK RD TEMPERATURE = 21000mC | 60 | PASS | Milli-degrees Celsius |
| Readings | 2 | RD BATTERY | /^ACK RD BATTERY = [0-9.]+ ?m?V$/ | ACK RD BATTERY = 2807mV | 90 | PASS | Volts or millivolts, as the firmware words it |
| Readings | 3 | RD BATTERY |  | ACK RD BATTERY = 2789mV | 70 | SKIP | the document gives no expected response - Nothing expected: recorded and skipped, with a timeout of its own |
| An unknown command is refused | 1 | RD NO-SUCH-ITEM | /^NACK/ | NACK Invalid Command | 40 | PASS | The refusal is the sensor's; the bench records it as a reply |
| A reset drops the link, and the time to the drop is measured | 1 | ECURESET HARD | <disconnect> | <disconnect> | 4120 | PASS | Passes when the sensor drops the link |
| A reset drops the link, and the time to the drop is measured | 2 | connect 5C1712 |  | linked to KAPPA_5C1712_V11.00.000 D1:8D:3B:4C:19:96 | 13360 | SKIP | linked to KAPPA_5C1712_V11.00.000 D1:8D:3B:4C:19:96 - It advertises again after the reset |
| A reset drops the link, and the time to the drop is measured | 3 | RD VERSION | /^ACK RD VERSION/ | ACK RD VERSION = V11.00.0000-95-gc051f3665 | 40 | PASS | And answers again |
| A reset drops the link, and the time to the drop is measured | 4 | disconnect |  |  | - | SKIP | link closed |
