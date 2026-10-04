# Bench test report: QS-06a An instrument missing from the bench

| Field | Value |
|---|---|
| Result | **ERROR** |
| Bench | Bench PC (Windows) |
| Specification | specs/qualification/qs06a_missing_instrument.yaml |
| Started | 2026-10-04T18:41:12+00:00 |
| Duration | 0.00 s |
| Tests | 0 passed, 0 failed, 0 errored, 0 skipped (of 0) |

## Suite setup failed

```
the specification uses instrument(s) 'scope', which the bench 'Bench PC (Windows)' does not define; it provides dmm, dongle, probe, psu, rtt, s2lp, temp
```

No test was run: every measurement after an unknown setup would be meaningless.

