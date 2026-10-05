# TTi 1604 - Bench Findings

| Field | Value |
|---|---|
| Date | 2026-10-04T19:53:30 |
| Resource | `COM13` |
| Kind of run | Real instrument |
| References | none |

## Test outcomes

| Test | Outcome |
|---|---|
| `test_the_meter_answers_and_reads` | failed |
| `test_keys_are_acknowledged_promptly` | failed |
| `test_every_frame_decodes` | failed |
| `test_the_reading_rate_is_two_and_a_half_per_second` | passed |
| `test_the_raw_stream` | passed |
| `test_a_tour_of_the_safe_functions` | failed |
| `test_every_dc_voltage_range` | failed |
| `test_the_frequency_gate` | failed |
| `test_dc_voltage` | skipped: no DC voltage reference: set BENCHTOOLS_TTI1604_DCV |
| `test_resistance` | skipped: no resistor named: set BENCHTOOLS_TTI1604_OHMS |
| `test_dc_current` | skipped: no current reference: set BENCHTOOLS_TTI1604_DCI, with the leads in the mA and COM sockets and in series with the load |
| `test_frequency` | skipped: no frequency reference: set BENCHTOOLS_TTI1604_HZ, with a signal of at least 2,000 counts on an AC volts range |
| `test_an_open_input_on_ohms_is_an_overrange` | failed |
| `test_local_then_remote` | passed |

## Observations

| Item | Observation | Bears on |
|---|---|---|
| Reading rate | mean 0.398 s between readings on DC volts (manual: 0.4 s) | DMM-FR-031 |
| Raw stream | 59 bytes in 2 s; distances between carriage returns [10]; a NUL after 0 of 6 frames. First 40 bytes: `0d12c810fdfcfcfcfc0c0d12c810fdfcfcfcfc0c0d12c810fdfcfcfcfc0c0d12c810fdfcfcfcfc0c` | DMM-OPEN-01 |
| Open input on ohms | display `.`, overrange False | DMM-FR-018 |
| Local and remote | readings stopped in local mode and resumed in remote | DMM-FR-007 |
