"""PPK2 hardware check, #342. Nothing wired to VOUT, VIN, GND or the logic
inputs (owner, 2026-11-14). Each setting is read back by reopening the kit:
it answers its metadata once per open."""
import json, sys, time
sys.path.insert(0, ".")
from benchtools.instruments.ppk2 import Ppk2

RES = "ppk2://D527E1DA8DBA"
log = []
def record(name, kit=None, measure=None, **extra):
    entry = {"step": name}
    entry.update(extra)
    if kit is not None:
        entry.update({"mode": kit.mode, "volts": kit.volts, "powered": kit.powered})
        if measure:
            m = kit.measure(measure)
            entry.update({"samples": m.samples, "lost": m.lost, "average_a": m.average,
                          "peak_a": m.peak, "minimum_a": m.minimum,
                          "logic_values": sorted(set(m.logic))})
    log.append(entry); print(json.dumps(entry))

def readback(name):
    t0 = time.monotonic()
    with Ppk2.connect(RES, voltage_limit=5.0) as kit:
        record(name, reopened_in_s=round(time.monotonic() - t0, 2),
               kit_mode=kit.metadata.get("mode"), kit_vdd_mv=kit.metadata.get("vdd"))

readback("as found")
with Ppk2.connect(RES, voltage_limit=3.3) as kit:
    record("connected", kit, 1.0)
    kit.set_mode("source"); kit.set_voltage(1.8); kit.power_on(); time.sleep(0.2)
    record("source 1.8 V, DUT on, VOUT open", kit, 1.0)
readback("read back after source 1.8 V")
with Ppk2.connect(RES, voltage_limit=3.3) as kit:
    kit.set_voltage(3.0); time.sleep(0.2)
    record("source 3.0 V, DUT on as left", kit, 1.0)
    try:
        kit.set_voltage(3.4)
    except Exception as exc:
        record("3.4 V refused", error=str(exc))
    kit.power_off(); record("source 3.0 V, DUT off", kit, 0.5)
readback("read back after source 3.0 V and a refused 3.4 V")
with Ppk2.connect(RES, voltage_limit=3.3) as kit:
    kit.set_mode("ammeter"); kit.power_on(); time.sleep(0.2)
    record("ammeter, DUT on, nothing on VIN", kit, 1.0)
    kit.power_off(); record("ammeter, DUT off", kit, 0.5)
readback("read back after ammeter")
with Ppk2.connect(RES, voltage_limit=5.0) as kit:
    kit.set_mode("source"); kit.set_voltage(4.0); record("restore: source 4.0 V, DUT off", kit)
readback("read back after restoring")
json.dump(log, open(sys.argv[1], "w"), indent=2)
