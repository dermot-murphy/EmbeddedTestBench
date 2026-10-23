# #233 hardware check: timeouts by command prefix

## Variables

| Variable  | Default | Note |
|-----------|---------|------|
| SENSOR_ID |         | 5C1712 |
| RD_MS     | 20000   | |

## Timeouts by command prefix

| Command prefix | Timeout (ms) | Note |
|----------------|--------------|------|
| RD             | ${RD_MS}     | variable |
| rd version     | 5000         | longer prefix, other case |
| RD ID          | 2000         | listening window |
| ECURESET       | 15000        | wait for the drop |

## Prefixes

| Step | Command              | Expected response                   | Timeout (ms) | Note |
|------|----------------------|-------------------------------------|--------------|------|
| 1    | connect ${SENSOR_ID} |                                     | 30000        | prefix not applied |
| 2    | RD VERSION           | /^ACK RD VERSION/                   |              | expect 5000, prefix rd version |
| 3    | RD TEMPERATURE       | /^ACK RD TEMPERATURE = -?[0-9]+mC$/ |              | expect RD |
| 4    | RD BATTERY           | /^ACK RD BATTERY/                   | 8000         | expect Timeout cell |
| 5    | RD ID                |                                     |              | listening window 2000 |
| 6    | XX NOTHING           | /^NACK/                             |              | expect run default |
| 7    | ECURESET HARD        | <disconnect>                        |              | expect 15000 prefix |
| 8    | connect ${SENSOR_ID} |                                     | 30000        | |
| 9    | rd version           | /^ACK rd version/                   |              | |
| 10   | disconnect           |                                     |              | |
