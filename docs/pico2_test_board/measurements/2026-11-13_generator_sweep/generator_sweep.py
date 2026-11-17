"""Generator ch1 -> PicoScope A: capture (auto-ranged), save raw, then analyse.
usage: siggen_sweep3.py OUT capture|analyse"""
import json
import math
import sys

import numpy as np

OUT, MODE = sys.argv[1], sys.argv[2]

CASES = [
    ("sine 1 kHz 100%", "sine", 1000, 100, {}),
    ("sine 100 Hz 50%", "sine", 100, 50, {}),
    ("sine 10 kHz 25%", "sine", 10000, 25, {}),
    ("sine 20 Hz 75%", "sine", 20, 75, {}),
    ("square 1 kHz 100%", "square", 1000, 100, {"duty": 50}),
    ("square 5 kHz 60%", "square", 5000, 60, {"duty": 50}),
    ("PWM 1 kHz 10%", "square", 1000, 80, {"duty": 10}),
    ("PWM 1 kHz 25%", "square", 1000, 80, {"duty": 25}),
    ("PWM 2 kHz 75%", "square", 2000, 80, {"duty": 75}),
    ("PWM 500 Hz 90%", "square", 500, 80, {"duty": 90}),
    ("triangle 2 kHz 80%", "triangle", 2000, 80, {}),
    ("triangle 500 Hz 40%", "triangle", 500, 40, {}),
    ("sawtooth 3 kHz 70%", "sawtooth", 3000, 70, {}),
    ("sine2 1k+3k r0.5 90%", "sine2", 1000, 90, {"freq2": 3000, "ratio": 0.5}),
    ("sine2 500+7k r1 100%", "sine2", 500, 100, {"freq2": 7000, "ratio": 1.0}),
] + [("amp sweep 1 kHz %d%%" % a, "sine", 1000, a, {}) for a in (10, 20, 30, 40, 50, 60, 70, 80, 90)] \
  + [("freq sweep %g Hz 50%%" % f, "sine", f, 50, {})
     for f in (10, 50, 200, 2000, 5000, 7000, 10000, 12000)]

SAMPLES = 20000
RANGES = (0.02, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0)


def capture():
    from benchtools.instruments.pico2_test_board import Pico2TestBoard
    from benchtools.instruments.picoscope3000 import PicoScope3000
    data = {}
    with Pico2TestBoard.connect("COM14") as board, \
            PicoScope3000.connect("pico://HT415/0202") as scope:
        saved = {s: board.rd(s, 1) for s in ("wave", "freq", "amp", "duty", "freq2", "ratio")}
        meta = []
        for number, (name, wave, freq, amp, extra) in enumerate(CASES):
            board.abort_freq(1)
            board.start_freq(1, freq, wave=wave, amp=amp, **extra)
            status = board.freq_status(1)
            scope.set_sample_interval(20.0 / freq / SAMPLES)
            scope.set_record_length(SAMPLES, pre_trigger=0.1)
            span = 2.0
            for _ in range(2):           # first at +/-2 V, then the range that fits
                scope.configure_channel("A", range_volts=span)
                scope.configure_edge_trigger("A", level=0.0, auto_ms=500)
                record = scope.capture().analog[1]
                peak = max(abs(record.minimum), abs(record.maximum))
                span = next(r for r in RANGES if r >= peak * 1.25)
            data["t%d" % number] = np.array(record.times)
            data["v%d" % number] = np.array(record.volts)
            meta.append({"case": name, "wave": wave, "freq": freq, "amp": amp, "extra": extra,
                         "board_hz": status.frequency,
                         "range_v": scope.get_channel_setup("A").range_volts,
                         "clipped": record.is_clipped})
            print(name, "range", meta[-1]["range_v"], file=sys.stderr)
        board.abort_freq(1)
        for setting, value in saved.items():
            board.wr(setting, value, 1)
        meta.append({"restored": {s: board.rd(s, 1) for s in saved}})
    np.savez_compressed(OUT + ".npz", **data)
    json.dump(meta, open(OUT + ".meta.json", "w"), indent=1)


def tone(t, v, f0):
    """Refine frequency by zero-padded Hann FFT near f0, then fit a sine there."""
    t = np.asarray(t); v = np.asarray(v); ac = v - v.mean()
    dt = t[1] - t[0]
    n = len(ac) * 16
    spec = np.abs(np.fft.rfft(ac * np.hanning(len(ac)), n))
    freqs = np.fft.rfftfreq(n, dt)
    window = (freqs > f0 * 0.8) & (freqs < f0 * 1.2)
    k = np.flatnonzero(window)[np.argmax(spec[window])]
    a, b, c = spec[k - 1], spec[k], spec[k + 1]
    f = freqs[k] + 0.5 * (a - c) / (a - 2 * b + c) * (freqs[1] - freqs[0])
    basis = np.column_stack([np.sin(2 * np.pi * f * t), np.cos(2 * np.pi * f * t), np.ones_like(t)])
    coef, *_ = np.linalg.lstsq(basis, v, rcond=None)
    return float(f), float(2 * math.hypot(coef[0], coef[1]))   # Vpp of that component


def analyse():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    data = np.load(OUT + ".npz")
    meta = json.load(open(OUT + ".meta.json"))
    rows = []
    fig, axes = plt.subplots(11, 3, figsize=(16, 36))
    for number, (m, axis) in enumerate(zip(meta[:-1], axes.flat)):
        t, v = data["t%d" % number], data["v%d" % number]
        f, fund_vpp = tone(t, v, m["freq"])
        lo, hi = np.percentile(v, 2), np.percentile(v, 98)
        row = {"case": m["case"], "range_v": m["range_v"], "set_hz": m["freq"],
               "meas_hz": round(f, 3), "ppm": round((f / m["board_hz"] - 1) * 1e6),
               "vpp": round(float(v.max() - v.min()), 4), "fund_vpp": round(fund_vpp, 4),
               "mean": round(float(v.mean()), 4), "clipped": m["clipped"]}
        if m["wave"] == "square":
            row["duty_pct"] = round(100 * float(np.mean(v > (lo + hi) / 2)), 2)
        if m["wave"] == "sine2":
            f2, vpp2 = tone(t, v, m["extra"]["freq2"])
            row["f2_hz"] = round(f2, 2)
            row["ratio_meas"] = round(vpp2 / fund_vpp, 3)
        rows.append(row)
        show = int(min(len(t), 4.0 / m["freq"] / (t[1] - t[0])))
        axis.plot((t[:show] - t[0]) * 1e3, v[:show], lw=0.8)
        axis.set_title("%s  (+/-%g V)\n%.2f Hz, %.3f Vpp" % (m["case"], m["range_v"], f, row["vpp"]),
                       fontsize=9)
        axis.set_xlabel("ms", fontsize=8)
        axis.grid(alpha=0.3)
    for axis in axes.flat[len(meta) - 1:]:
        axis.axis("off")
    fig.suptitle("PICO2 Test Board generator ch 1 -> PicoScope 3405D MSO ch A (DC, auto-ranged)")
    fig.tight_layout(rect=(0, 0, 1, 0.99))
    fig.savefig(OUT + ".png", dpi=80)
    json.dump(rows, open(OUT + ".json", "w"), indent=1)
    for row in rows:
        print(json.dumps(row))
    print(meta[-1])


capture() if MODE == "capture" else analyse()
