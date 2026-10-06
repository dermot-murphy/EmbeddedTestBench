# #234 hardware check: connect step after resets

## Variables

| Variable  | Default | Note |
|-----------|---------|------|
| SENSOR_ID |         | 5C1712 |

## Cycles

| Step | Command              | Expected response | Timeout (ms) | Note |
|------|----------------------|-------------------|--------------|------|
| 1    | connect ${SENSOR_ID} |                   | 30000        | |
| 2    | RD VERSION           | /^ACK RD VERSION/ | 45000        | |
| 3    | ECURESET HARD        | <disconnect>      | 15000        | cycle 1 |
| 4    | connect ${SENSOR_ID} |                   | 30000        | |
| 5    | RD VERSION           | /^ACK RD VERSION/ | 45000        | |
| 6    | ECURESET HARD        | <disconnect>      | 15000        | cycle 2 |
| 7    | connect ${SENSOR_ID} |                   | 30000        | |
| 8    | RD VERSION           | /^ACK RD VERSION/ | 45000        | |
| 9    | ECURESET HARD        | <disconnect>      | 15000        | cycle 3 |
| 10    | connect ${SENSOR_ID} |                   | 30000        | |
| 11    | RD VERSION           | /^ACK RD VERSION/ | 45000        | |
| 12    | ECURESET HARD        | <disconnect>      | 15000        | cycle 4 |
| 13    | connect ${SENSOR_ID} |                   | 30000        | |
| 14    | RD VERSION           | /^ACK RD VERSION/ | 45000        | |
| 15    | ECURESET HARD        | <disconnect>      | 15000        | cycle 5 |
| 16    | connect ${SENSOR_ID} |                   | 30000        | |
| 17    | RD VERSION           | /^ACK RD VERSION/ | 45000        | |
| 18    | ECURESET HARD        | <disconnect>      | 15000        | cycle 6 |
| 19    | connect ${SENSOR_ID} |                   | 30000        | |
| 20    | RD VERSION           | /^ACK RD VERSION/ | 45000        | |
| 21    | ECURESET HARD        | <disconnect>      | 15000        | cycle 7 |
| 22    | connect ${SENSOR_ID} |                   | 30000        | |
| 23    | RD VERSION           | /^ACK RD VERSION/ | 45000        | |
| 24    | ECURESET HARD        | <disconnect>      | 15000        | cycle 8 |
| 25    | connect ${SENSOR_ID} |                   | 30000        | |
| 26    | RD VERSION           | /^ACK RD VERSION/ | 45000        | |
| 27    | disconnect           |                   |              | |
