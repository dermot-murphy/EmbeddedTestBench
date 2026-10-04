"""
test_bench.py

Test Bench
==========

Based on the Kepler reference project's rf_monitor (v1.1.0, 2026-09-15),
copied unchanged in the first commit of #82 so every change since is visible.

FROZEN since 2026-10-04 (#142): the test run viewer, `benchtools view`,
replaces this monitor. Change it only to fix a defect. What it still does that
the viewer does not (--port, --log, --simulate, all without a test run) is
listed in docs/test_bench/Test_Bench_Monitor.md.

What changed from rf_monitor
----------------------------
- The S2-LP kit is read directly through the benchtools driver (--port),
  receiving with the firmware's own loop as ST's GUI does, instead of from a
  log file written by ST's GUI. A log file can still be read (--log).
- "ST GUI" page: each packet as ST's GUI shows it - time, bytes, RSSI, hex.
- "Events" page: the run's events from every part of the bench - ST RF, PSU,
  BLE, J-Link and the test runner - each source in its own colour, followed
  live from a bench event log (--event-log; `benchtools run --event-log`).
- Every other page is rf_monitor's, fed the same decoded frames.

Features (from rf_monitor)
--------------------------
- Latest packet decode, environment and short-interval trending, TWF,
  CONFIG decode with units, sensor filtering, raw packet highlighting,
  VERSION decoding, identification panel, diagnostics, sync, reports

Dependencies
------------
pip install matplotlib numpy pyserial

Run
---
python tools/test_bench/test_bench.py --port COM4 --event-log events.jsonl
python tools/test_bench/test_bench.py --simulate
python tools/test_bench/test_bench.py --log rf_log.txt
"""

from __future__ import annotations

import argparse
import os
import pathlib
import re
import sys
import time
import tkinter as tk

from collections import deque
from tkinter import ttk

import numpy as np

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.transforms import blended_transform_factory

# benchtools lives two directories up; sources.py beside this file.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from sources import (  # noqa: E402  pylint: disable=wrong-import-position
    SOURCE_ORDER,
    SOURCE_STYLES,
    style_of,
    JlinkPanel,
    LiveRadio,
    PsuPanel,
    SimulatedAir,
    event_row,
    register_rows,
    regs_text,
    rf_event,
    rf_setup_rows,
    spirit_line,
    st_gui_row,
)


# =============================================================================
# APPLICATION VERSION
# =============================================================================

APP_TITLE = "Test Bench"

APP_VERSION = "2.0.0"

APP_DATE = "2026-09-28"


# =============================================================================
# CONSTANTS
# =============================================================================

POLL_INTERVAL_MS = 1000

# Live radio and event-log polling, and how much each new page keeps.
RADIO_POLL_MS = 200
EVENT_POLL_MS = 500
ST_GUI_MAX_ROWS = 5000
EVENTS_MAX = 20000
LIVE_HISTORY_MAX = 200000

MAX_POINTS = 1000

HEADER_SIZE = 8

# RF Capability 6 (TX-563): multi-packet APDUs carry a Permute Control byte at
# offset 8, which moves the frame counter and every payload item along one
# byte.  Bits 4:3 are the method; bits 2:0 are reserved.  A frame's polynomial
# version is its frame number minus one, so no version is carried on air.
# See KEP-SWE3-006 sections 6 and 7.
RF_CAP_PERMUTED        = 6
PERMUTED_FRAME_TYPES   = {4, 5}         # TWF, CONFIG - the multi-packet APDUs
PERMUTE_CONTROL_OFFSET = 8

# Permute Control bits 4:3 value 11b: no method is defined for it
PERMUTE_METHOD_RESERVED = 3

# The other method values, as carried in Permute Control bits 4:3
PERMUTE_METHOD_DISTANCE = 0
PERMUTE_METHOD_NONE     = 1
PERMUTE_METHOD_POLY     = 2

# CONFIG geometry (api_radio_transport_cfg.h): 12 multiplexes of 5 parameters
CONFIG_NUM_MUX          = 12
CONFIG_PARAMS_PER_FRAME = 5
CONFIG_NUM_PARAMS       = CONFIG_NUM_MUX * CONFIG_PARAMS_PER_FRAME

FRAME_TYPES = {
    0: "STARTUP",
    2: "VERSION",
    3: "ALIVE",
    4: "TWF",
    5: "CONFIG",
    6: "FFT1",
    7: "FFT2",
    8: "CMD",
    9: "RESPONSE",
}

PROD_ID_TABLE = {
    0: "Kappa GEN1",
    1: "Tau GEN1",
    2: "Chi GEN1",
    3: "Kappa GEN2",
    4: "Tau GEN2",
    5: "Chi GEN2",
    6: "Tempus",
}

RF_CAP_TABLE = {
    0: "RF-01",
    1: "RF-01B",
    2: "RF-02",
}

RESET_REASON_TABLE = {
    # nRF52840 POWER_RESETREAS bitfield – from hal_mcu.c / nrf52840_bitfields.h
    0x00000001: "Reset pin",                                    # RESETPIN (bit 0)
    0x00000002: "Watchdog",                                     # DOG      (bit 1)
    0x00000004: "Soft reset",                                   # SREQ     (bit 2)
    0x00000008: "CPU lockup",                                   # LOCKUP   (bit 3)
    0x00010000: "System OFF wakeup by GPIO-DETECT",             # OFF      (bit 16)
    0x00020000: "System OFF wakeup by ANADETECT-LPCOMP",        # LPCOMP   (bit 17)
    0x00040000: "System OFF wakeup by debug interface mode",    # DIF      (bit 18)
    0x00080000: "System OFF wakeup by NFC field detect",        # NFC      (bit 19)
    0x00100000: "System OFF wakeup by VBUS rising into valid range",  # VBUS (bit 20)
}

PCB_VERSION_TABLE = {
    0: "V2",
    1: "V3",
    2: "V4",
    3: "V4X",
    4: "V5",
}

# From ENUMERATIONS sheet
SI_FACTOR_ENUM = {
    0: "±8g",
    1: "±16g",
    2: "±32g",
    3: "±64g",
}

SENSOR_STATE_ENUM = {
    0: "Init",
    1: "Peaks",
    2: "Detect",
    3: "Delay",
    4: "Confirm",
    5: "Transmit",
    6: "Wait",
    7: "Test",
    8: "Transit",
}

TWF_AXIS_ENUM   = {0: "X", 1: "Y", 2: "Z"}
LI_TYPE_ENUM    = {0: "Low", 1: "High", 2: "Custom"}
SI_TYPE_ENUM    = {0: "ACC_RMS", 1: "VEL_RSS", 2: "ACC_P2P", 3: "MAG_FREQ", 4: "MAG_AMP"}
PERMUTE_ENUM    = {0: "Distance", 1: "None", 2: "Polynomial", 3: "Reserved"}

# TWFA / TWFB / FFT scaling setting, CONFIG slots 15, 52 and 56 (TX-773,
# TX-928). The slot carries the stored value: 0 is autoscale, 1..4 a fixed
# accelerometer scale.
# See API_PARAM_VALUE_TWF_SCALING_* in api_param_cfg.h.
SCALING_ENUM    = {0: "AUTO", 1: "LOWEST", 2: "LOW", 3: "MEDIUM", 4: "HIGHEST"}

# Short interval capture, CONFIG slot 58 (TX-934): 0 takes a separate RMS
# capture, 1 takes one capture with the FFT settings for everything.
# See API_PARAM_VALUE_SHORT_CAPTURE_* in api_param_cfg.h. Slot 59 is the
# FFT machine-off count, where 0 sends the FFT whatever the machine state.
SHORT_CAPTURE_ENUM = {0: "RMS", 1: "FFT"}

TRIGGER_METHOD_ENUM = {
    0: "ALWAYS",
    1: "ACCWAVE",
    2: "ACCRMS",
    3: "VELRSS",
    4: "PK2PK",
}

DETECT_METHOD_ENUM = {
    # Values to be defined
}

# CMD_PARAM values (CMD frame, PL_TYPE=8, sensor -> gateway).
# See API_RADIO_TRANSPORT_CMD_PARAM_* in api_radio_transport_cfg.h.
CMD_PARAM_ENUM = {
    0x0001: "REQ_LORES",
    0x0002: "REQ_HIRES",
    0x0003: "GENERAL",
    0x8001: "ACK_SYNC_LORES",
    0x8002: "ACK_SYNC_HIRES",
    0x8003: "ACK_CONFIG",
    0x7F01: "NACK_SYNC_LORES",
    0x7F02: "NACK_SYNC_HIRES",
    0x7F03: "NACK_CONFIG",
}

# RESPONSE_PARAM values (RESPONSE frame, PL_TYPE=9, gateway -> sensor).
# See API_RADIO_TRANSPORT_RESPONSE_PARAM_* in api_radio_transport_cfg.h.
RESPONSE_PARAM_ENUM = {
    0x0001: "SYNC_LORES",
    0x0002: "SYNC_HIRES",
    0x0003: "CONFIG",
}

# CMD / RESPONSE field offsets — shared position for CMD_SENSOR_ID (CMD frame)
# and the echoed Sensor Id (RESPONSE frame); see API_RADIO_TRANSPORT_CONTENT_TABLE.
CMD_SENSOR_ID_OFFSET      = 9    # 3 bytes
CMD_PARAM_OFFSET          = 12   # 2 bytes, uint16 BE
CMD_RETRY_OFFSET          = 14   # 1 byte
RESPONSE_PARAM_OFFSET     = 12   # 2 bytes, uint16 BE
RESPONSE_PAYLOAD_OFFSET   = 14   # 4-byte timer (SYNC_LORES/HIRES) or {id,value} pairs (CONFIG)
RESPONSE_CONFIG_PAIR_SIZE = 6    # 2-byte id + 4-byte value
RESPONSE_CONFIG_MAX_PAIRS = 10


# =============================================================================
# VISUAL THEME
# =============================================================================

DARK_BG      = "#1a1d2e"   # window / notebook background
PANEL_BG     = "#252840"   # panel / card background
PLOT_BG      = "#13162a"   # matplotlib axes background
TEXT_MAIN    = "#dce1f0"   # primary text / labels
TEXT_DIM     = "#7a8a9e"   # secondary text / axis labels
BORDER_COL   = "#374060"   # borders, spines, grid lines
ACCENT_BLUE  = "#4a9eff"   # selected tab, primary buttons
ACCENT_CYAN  = "#26c6da"   # column headings, section labels

# Per frame-type palette used in Latest Data title bars: (fg, bg)
FRAME_PALETTE = {
    "ALIVE":   ("#a5d6a7", "#1b5e20"),
    "VERSION": ("#90caf9", "#0d47a1"),
    "CONFIG": ("#ffcc80", "#bf360c"),
    "TWF":     ("#ce93d8", "#4a148c"),
    "FFT1":    ("#fff176", "#f57f17"),
    "FFT2":    ("#fff176", "#f57f17"),
    "CMD":       ("#80cbc4", "#004d40"),
    "RESPONSE":  ("#f48fb1", "#880e4f"),
    "STARTUP": ("#b0bec5", "#37474f"),
    "UNKNOWN": ("#b0bec5", "#37474f"),
}

# Treeview alternating row backgrounds
TREE_ROW_ODD  = PANEL_BG
TREE_ROW_EVEN = "#1e2240"


# =============================================================================
# CONFIG TABLE
# =============================================================================

CONFIG_MUX_TABLE = {

    0: [
        "Seek Machine On",
        "Delay Confirm",
        "Confirm Machine",
        "Transmit TWF",
        "Return Idle",
    ],

    1: [
        "Transit Wait Time",
        "Transit Wake Time",
        "TWFA ODR",
        "TWFA X Sampling",
        "TWFA Y Sampling",
    ],

    2: [
        "TWFA Z Sampling",
        "TWFB ODR",
        "TWFB X Sampling",
        "TWFB Y Sampling",
        "TWFB Z Sampling",
    ],

    3: [
        "TWFA Scaling",
        "Machine ACC Threshold",
        "Machine Peaks Threshold",
        "Machine ACC Detect",
        "Wakeup Idle Count",
    ],

    4: [
        "Sample Delay Count",
        "Machine ON Confirm Count",
        "Machine Pk2Pk Threshold",
        "Post Sample Interval",
        "Battery Sample Delay",
    ],

    5: [
        "Machine VEL Threshold",
        "Trigger Method",
        "RMS Min Frequency",
        "TWFA Enable",
        "TWFB Enable",
    ],

    6: [
        "TWFB Samples",
        "TWFA Samples",
        "RMS ODR",
        "RMS Samples",
        "TWFA X Enable",
    ],

    7: [
        "TWFA Y Enable",
        "TWFA Z Enable",
        "TWFB X Enable",
        "TWFB Y Enable",
        "TWFB Z Enable",
    ],

    8: [
        "Alive Period",
        "FFT Enable",
        "FFT3 Axis Enable",
        "FFT3 First Bin",
        "FFT3 Last Bin",
    ],

    9: [
        "Sync Enable",
        "Sync Retry",
        "Sync Max Wait",
        "DC Offset Enable",
        "Preamble Length",
    ],

    10: [
        "Ignore Duration",
        "Frames Per Packet",
        "TWFB Scaling",
        "Permute Method",
        "FFT ODR",
    ],

    11: [
        "FFT Samples",
        "FFT Scaling",
        "Listen Enable",
        "Short Capture",
        "FFT Machine Off Count",
    ],
}

CONFIG_MUX_UNITS = {
    0: ["s",     "s",     "s",   "s",   "s"  ],
    1: ["s",     "s",     "Hz",  "",    ""   ],
    2: ["",      "Hz",    "",    "",    ""   ],
    3: ["",      "",      "mg",  "",    ""   ],
    4: ["",      "",      "",    "s",   "ms" ],
    5: ["mm/s",  "",      "Hz",  "",    ""   ],
    6: ["",      "",      "Hz",  "",    ""   ],
    7: ["",      "",      "",    "",    ""   ],
    8: ["secs",  "",      "",    "",    ""   ],
    9: ["",      "",      "×10mS", "",  "pairs"],
    10: ["s",    "frames","",    "",    "Hz" ],
    11: ["",     "",      "",    "",    ""   ],
}

# The same tables flattened so that index p is parameter p of the APDU, which
# is what a permuted CONFIG slot names (TX-564). A multiplex's own row is only
# the right label when the method is None.
CONFIG_PARAM_NAMES = [
    name for mux in sorted(CONFIG_MUX_TABLE) for name in CONFIG_MUX_TABLE[mux]
]
CONFIG_PARAM_UNITS = [
    unit for mux in sorted(CONFIG_MUX_UNITS) for unit in CONFIG_MUX_UNITS[mux]
]


# Parameters referenced in the Trigger Settings, Operation Timings, or Sampling
# Configuration detail tables.  Config params NOT in this set are highlighted
# in the main parameter trees to flag that they have no dedicated display.
CONFIG_DETAIL_PARAMS = {
    # Trigger Settings
    "TWFA Scaling", "TWFB Scaling", "Trigger Method",
    "Machine Pk2Pk Threshold", "Machine VEL Threshold",
    "Machine ACC Threshold", "Machine Peaks Threshold", "Machine ACC Detect",
    # Operation Timings
    "Wakeup Idle Count", "Sample Delay Count", "Post Sample Interval",
    "Seek Machine On", "Delay Confirm", "Confirm Machine", "Transmit TWF", "Return Idle",
    "Machine ON Confirm Count",
    # FFT
    "FFT Enable", "FFT3 Axis Enable", "FFT3 First Bin", "FFT3 Last Bin",
    "FFT ODR", "FFT Samples", "FFT Scaling",
    "Short Capture", "FFT Machine Off Count",
    "RMS Min Frequency",
    # Sync
    "Sync Enable", "Sync Retry", "Sync Max Wait", "Listen Enable",
    # RF
    "Preamble Length", "Frames Per Packet",
    # Post-abort debounce
    "Ignore Duration",
    # Other
    "Alive Period", "Battery Sample Delay", "Permute Method",
    "Transit Wait Time", "Transit Wake Time",
    # Sampling Configuration
    "TWFA Enable", "TWFB Enable",
    "TWFA X Enable", "TWFA Y Enable", "TWFA Z Enable",
    "TWFB X Enable", "TWFB Y Enable", "TWFB Z Enable",
    "TWFA ODR", "TWFB ODR", "RMS ODR",
    "TWFA Samples", "TWFB Samples", "RMS Samples",
    "TWFA X Sampling", "TWFA Y Sampling", "TWFA Z Sampling",
    "TWFB X Sampling", "TWFB Y Sampling", "TWFB Z Sampling",
}


# =============================================================================
# ALIVE CONTENT TABLE
# =============================================================================

CONTENT_TABLE = {

    "ALIVE": [

        ("TEMPERATURE",         9,  2),
        ("VBATT",              11,  1),
        ("TICK_COUNT_SHORT",   12,  2),
        ("SI_FACTOR",          14,  1),

        ("ACC_RMS_X",          15,  2),
        ("ACC_RMS_Y",          17,  2),
        ("ACC_RMS_Z",          19,  2),

        ("VEL_RSS_X",          21,  2),
        ("VEL_RSS_Y",          23,  2),
        ("VEL_RSS_Z",          25,  2),

        ("ACC_P2P_X",          27,  2),
        ("ACC_P2P_Y",          29,  2),
        ("ACC_P2P_Z",          31,  2),

        ("BLE_CONN",           33,  1),
        ("ALIVE_STATUS",       34,  1),
    ],

    "VERSION": [

        ("VERSION_SHA",      9,  9),
        ("VERSION_STRING",  18, 57),
        ("RESET_REASON",    75,  4),
        ("BATTERY_LOADED",  79,  1),
        ("PCB_VERSION",     80,  1),
        ("TEMPERATURE",     81,  2),
        ("TICKS",           83,  4),
    ]
}

ALIVE_UNITS = {
    "TEMPERATURE":       "°C",
    "VBATT":             "V",
    "TICK_COUNT_SHORT":  "ticks",
    "SI_FACTOR":         "",
    "ACC_RMS_X":         "",
    "ACC_RMS_Y":         "",
    "ACC_RMS_Z":         "",
    "VEL_RSS_X":         "mm/s",
    "VEL_RSS_Y":         "mm/s",
    "VEL_RSS_Z":         "mm/s",
    "ACC_P2P_X":         "",
    "ACC_P2P_Y":         "",
    "ACC_P2P_Z":         "",
    "BLE_CONN":          "count",
    "ALIVE_STATUS":      "",
}


# =============================================================================
# HELPERS
# =============================================================================

def print_version():

    print(f"{APP_TITLE}")
    print(f"Version : {APP_VERSION}")
    print(f"Date    : {APP_DATE}")


def print_help():

    print_version()

    print("")
    print("Usage:")
    print("  python test_bench.py --port COM4 [--event-log events.jsonl]")
    print("  python test_bench.py --simulate")
    print("  python test_bench.py --log <logfile>")
    print("")
    print("Options:")
    print("  --help             Display help information")
    print("  --version          Display program version")
    print("  --port PORT        Read the S2-LP kit directly (e.g. COM4)")
    print("  --board NAME       Kit board name (optional; the EEPROM is read anyway)")
    print("  --setup REGS       Register file to receive with")
    print("                     (default configs/s2lp_kepler_433_rx.regs)")
    print("  --packet-log PATH  Also write every packet, raw and decoded, as JSON Lines")
    print("  --event-log PATH   Follow a bench event log on the Events page")
    print("  --simulate         A simulated kit with a sensor on the air")
    print("  --log FILE         An RF log file written by ST's GUI, as rf_monitor read")
    print("")


def u16_be(data, offset):

    return (
        (data[offset] << 8) |
        data[offset + 1]
    )


def s16_be(data, offset):

    value = u16_be(data, offset)

    if value & 0x8000:
        value -= 65536

    return value


def u16_le(data, offset):

    return (
        data[offset] |
        (data[offset + 1] << 8)
    )


def s16_le(data, offset):

    value = u16_le(data, offset)

    if value & 0x8000:
        value -= 65536

    return value


def u32_le(data, offset):

    return (
        data[offset] |
        (data[offset + 1] << 8) |
        (data[offset + 2] << 16) |
        (data[offset + 3] << 24)
    )


def u32_be(data, offset):

    return (
        (data[offset]     << 24) |
        (data[offset + 1] << 16) |
        (data[offset + 2] <<  8) |
        data[offset + 3]
    )


def decode_temperature(raw):

    return round(raw / 10.0, 1)


def decode_battery(raw):

    return round(raw * 0.02, 2)


def format_elapsed_time(seconds):

    seconds = int(seconds)

    days = seconds // 86400

    seconds %= 86400

    hours = seconds // 3600

    seconds %= 3600

    minutes = seconds // 60

    seconds %= 60

    return (
        f"{days:02d}:"
        f"{hours:02d}:"
        f"{minutes:02d}:"
        f"{seconds:02d}"
    )


def permute_poly(sequence_size, sequence_index, version=0):
    """
    Port of Permute_Poly() from permute.c.

    Maps a transmitted slot index -> the original sample index it carries
    (API_Vibration_PacketGet loads sample Permute_Poly(N, slot) into each slot).
    sequence_size must be a power of 2 (e.g. 2048, 4096).
    version selects polynomial constants.  RF Capability 5 frames always used
    version 0; under RF Capability 6 frame N of a packet uses version N - 1.
    """
    POLY_A0 = [1735, 1730, 1729, 1733, 1731, 1743, 1734, 1736]
    POLY_A1 = [5059, 5077, 6151, 6607, 5051, 8179, 4093, 8081]
    POLY_A2 = 2
    POLY_A3 = 6

    if version >= len(POLY_A0) or sequence_index >= sequence_size:
        return sequence_index  # error case: return identity

    mask = sequence_size - 1

    xn     = sequence_index
    result = (POLY_A1[version] * xn + POLY_A0[version]) & mask

    xn     = (xn * sequence_index) & mask
    result += POLY_A2 * xn

    xn     = (xn * sequence_index) & mask
    result += POLY_A3 * xn

    return result & mask


def permute_poly_any_size(sequence_size, sequence_index, version=0):
    """
    Port of Permute_PolyAnySize() from permute.c.

    Permutes a sequence whose size need not be a power of two by rounding up
    to the next power of two and walking the polynomial's cycle until the
    value lands inside the sequence (KEP-SWE3-006 section 5.7). Returns None
    when the firmware would have rejected the lookup.
    """
    if sequence_index >= sequence_size or version >= 8:
        return None

    rounded = 1
    while rounded < sequence_size:
        rounded *= 2

    if rounded > 16384:
        return None

    candidate = sequence_index
    for _ in range(rounded):
        candidate = permute_poly(rounded, candidate, version)
        if candidate < sequence_size:
            return candidate

    return None


def config_param_index(mux, slot, method, version):
    """
    Which parameter of the APDU a CONFIG slot carries (TX-564).

    `method` is Permute Control bits 4:3, or None for an RF Capability 5 frame,
    which has no Permute Control byte and is always in order. Returns None when
    the parameter cannot be identified, so the caller shows nothing rather than
    a plausible wrong label.
    """
    linear = (mux * CONFIG_PARAMS_PER_FRAME) + slot

    if linear >= CONFIG_NUM_PARAMS:
        return None

    if method is None or method == PERMUTE_METHOD_NONE:
        return linear

    if method == PERMUTE_METHOD_DISTANCE:
        # delta = N / E, as for the waveform: the multiplex index is ignored
        return mux + (slot * (CONFIG_NUM_PARAMS // CONFIG_PARAMS_PER_FRAME))

    if method == PERMUTE_METHOD_POLY:
        return permute_poly_any_size(CONFIG_NUM_PARAMS, linear, version)

    return None


def build_received_mask(received_pkt_nums, total_pkts, permute, samples_per_pkt=32,
                        received_frames=None):
    """
    Return a boolean numpy array of length total_pkts*samples_per_pkt where
    True means that sample position was covered by a received packet.

    permute values:
        0 = DISTANCE     (stride interleave)
        1 = NONE         (sequential)
        2 = POLYNOMIAL   (slot p of a frame carries sample permute_poly(N, p,
                          version), where version is the frame number minus
                          one; received_frames holds (packet, version) pairs
                          and defaults to version 0 per packet)
    """
    N        = total_pkts * samples_per_pkt
    has_data = np.zeros(N, dtype=bool)

    if permute == 0:  # DISTANCE: pkt k, sample j → original = k + j*total_pkts
        for pkt_num in received_pkt_nums:
            positions = pkt_num + np.arange(samples_per_pkt) * total_pkts
            valid = positions[(positions >= 0) & (positions < N)]
            has_data[valid] = True

    elif permute == 2:  # POLYNOMIAL: slot p carries sample permute_poly(N, p, version)
        if received_frames is None:
            received_frames = {(pkt_num, 0) for pkt_num in received_pkt_nums}
        for pkt_num, version in received_frames:
            base = pkt_num * samples_per_pkt
            for j in range(samples_per_pkt):
                if base + j < N:
                    has_data[permute_poly(N, base + j, version)] = True

    else:  # NONE: pkt k covers original positions k*32 … (k+1)*32-1
        for pkt_num in received_pkt_nums:
            start = pkt_num * samples_per_pkt
            end   = min(start + samples_per_pkt, N)
            has_data[start:end] = True

    return has_data


def interpolate_missing(waveform_arr, has_data):
    """
    Linearly interpolate waveform positions where has_data is False.
    Positions before the first received sample and after the last are held
    at the nearest edge value (np.interp extrapolation behaviour).
    Returns the array unchanged if all positions have data.
    """
    if has_data.all():
        return waveform_arr

    x_known = np.where(has_data)[0]

    if len(x_known) < 2:
        return waveform_arr   # not enough points to interpolate

    y_known = waveform_arr[x_known]
    x_all   = np.arange(len(waveform_arr))

    result           = waveform_arr.copy()
    result[~has_data] = np.interp(x_all, x_known, y_known)[~has_data]

    return result


def apply_fig_style(fig, axes):
    """
    Apply the application dark theme to a matplotlib Figure and a list of Axes.
    Call once after subplot creation; styling persists through data updates.
    """
    fig.patch.set_facecolor(DARK_BG)

    for ax in axes:

        ax.set_facecolor(PLOT_BG)

        ax.tick_params(colors=TEXT_DIM, which="both", labelsize=9)

        ax.xaxis.label.set_color(TEXT_DIM)
        ax.yaxis.label.set_color(TEXT_DIM)

        ax.title.set_color(TEXT_MAIN)
        ax.title.set_fontsize(10)
        ax.title.set_fontweight("bold")

        for spine in ax.spines.values():
            spine.set_edgecolor(BORDER_COL)
            spine.set_linewidth(0.8)

        ax.grid(True, color=BORDER_COL, alpha=0.55, linewidth=0.5)
        ax.set_axisbelow(True)


def decode_reset_reason(value):

    reasons = []

    for mask, label in RESET_REASON_TABLE.items():

        if value & mask:
            reasons.append(label)

    return ", ".join(reasons) if reasons else f"0x{value:08X}"


def _parse_time_s(time_str):
    """Parse 'HH:MM:SS.CC' log timestamp to float seconds since midnight."""
    try:
        h, m, s_cs = time_str.split(":")
        s, cs = s_cs.split(".")
        return int(h) * 3600 + int(m) * 60 + int(s) + int(cs) / 100.0
    except Exception:
        return 0.0


def _fmt_time_s(t):
    """Format float seconds to a graph label.

    For times within a single day (t < 86400) the format is HH:MM:SS.
    For multi-day logs the format is +Nd HH:MM:SS so the day boundary is
    visible on the axis (e.g. '+1d 00:09:27').
    """
    if t is None:
        return "--:--:--.--"
    day = int(t // 86400)
    rem = t % 86400
    h   = int(rem / 3600)
    m   = int((rem % 3600) / 60)
    s   = int(rem % 60)
    if day == 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"+{day}d {h:02d}:{m:02d}:{s:02d}"


def _style_twin_ax(ax, label):
    """Apply dark-theme styling to a twinx secondary y-axis."""
    ax.set_ylabel(label, color=TEXT_DIM, fontsize=9)
    ax.tick_params(axis="y", colors=TEXT_DIM, labelsize=8)
    ax.spines["right"].set_color(BORDER_COL)
    ax.spines["right"].set_linewidth(0.8)
    for sp in ("left", "top", "bottom"):
        ax.spines[sp].set_visible(False)
    ax.set_facecolor("none")


def _fmt_delta(delta_s):
    """Format a duration in seconds as a human-readable string."""
    if delta_s < 60:
        return f"{delta_s:.1f} s"
    elif delta_s < 3600:
        return f"{delta_s / 60:.1f} min"
    else:
        return f"{delta_s / 3600:.1f} hr"


def _fmt_period(val_s):
    """Format a period (seconds) for the Diagnostics table.

    Returns a fixed-width string  '  NNNNN.NNN  (HH:MM:SS)'  so that, with
    right-alignment in a monospace Treeview column, the decimal points of all
    rows sit in the same pixel column.
    """
    h = int(val_s / 3600)
    m = int((val_s % 3600) / 60)
    s = int(val_s % 60)
    return f"{val_s:9.3f}  ({h:02d}:{m:02d}:{s:02d})"


def decode_frame_counter(byte_val):

    frame_num = (byte_val >> 4) & 0x0F

    total_frames = byte_val & 0x0F

    return frame_num, total_frames


def format_ticks(ticks, label="Ticks"):

    return f"{ticks} ({format_elapsed_time(ticks * 60)})"


# =============================================================================
# FRAME
# =============================================================================

class RFFrame:

    def __init__(self):

        self.time_string = ""

        self.packet_length = 0

        self.rssi = 0

        self.raw_bytes = []

        self.sensor_id = ""

        self.prod_id = 0

        self.rf_cap = 0

        self.hw_cap = 0

        self.frame_version = 0

        self.fw_cap = 0

        self.frame_name = "UNKNOWN"

        self.frame_type = 0

        self.frame_num = 0

        self.total_frames = 0

        self.permute_shift = 0        # 1 when a Permute Control byte is present

        self.permute_control = None

        self.permute_method = None

        self.decoded = {}

        # Absolute time in seconds, accounting for midnight rollovers across
        # multi-day logs.  Set by RFMonitor.process_frame before any update.
        self.abs_time_s: float = 0.0

        self.config_mux = None
        # One (slot, parameter index, name, raw offset) per decoded CONFIG slot
        self.config_slots = []
        # Parameter name -> the multiplex block it belongs to. Under
        # permutation that is not the multiplex of the frame carrying it.
        self.config_param_block = {}

        self.twf_meta = {}   # populated by _decode_twf for waveform reassembly


# =============================================================================
# PARSER
# =============================================================================

def parse_packet_line(line):

    pattern = (
        r"^(\d{2}:\d{2}:\d{2}\.\d{2})\s+"
        r"Packet received\s+\((\d+)\s+bytes\)\s+"
        r"(-?\d+)\s+"
        r"(.+)$"
    )

    match = re.match(pattern, line)

    if not match:
        return None

    frame = RFFrame()

    frame.time_string = match.group(1)

    frame.packet_length = int(match.group(2))

    frame.rssi = int(match.group(3))

    try:

        frame.raw_bytes = [
            int(x, 16)
            for x in match.group(4).split()
        ]

    except Exception:
        return None

    if len(frame.raw_bytes) < HEADER_SIZE:
        return None

    frame.sensor_id = "".join(
        f"{x:02X}"
        for x in frame.raw_bytes[0:3]
    )

    frame.prod_id = frame.raw_bytes[3]

    frame.rf_cap = frame.raw_bytes[4]

    frame.hw_cap = frame.raw_bytes[5] & 0x07

    frame.frame_version = (frame.raw_bytes[5] >> 3) & 0x1F

    frame.fw_cap = frame.raw_bytes[6]

    frame.frame_type = frame.raw_bytes[7]

    frame.frame_name = FRAME_TYPES.get(
        frame.frame_type,
        "UNKNOWN"
    )

    if (
        frame.rf_cap >= RF_CAP_PERMUTED
        and frame.frame_type in PERMUTED_FRAME_TYPES
        and len(frame.raw_bytes) > PERMUTE_CONTROL_OFFSET
    ):
        frame.permute_shift   = 1
        frame.permute_control = frame.raw_bytes[PERMUTE_CONTROL_OFFSET]
        frame.permute_method  = (frame.permute_control >> 3) & 0x03

    counter_offset = HEADER_SIZE + frame.permute_shift

    if len(frame.raw_bytes) > counter_offset:

        frame.frame_num, frame.total_frames = decode_frame_counter(
            frame.raw_bytes[counter_offset]
        )

    decode_frame(frame)

    return frame


# =============================================================================
# DECODER
# =============================================================================

def decode_frame(frame):

    if frame.frame_name == "ALIVE":

        _decode_alive(frame)

    elif frame.frame_name == "CONFIG":

        _decode_config(frame)

    elif frame.frame_name == "VERSION":

        _decode_version(frame)

    elif frame.frame_name == "TWF":

        _decode_twf(frame)

    elif frame.frame_name in ("FFT1", "FFT2"):

        _decode_fft(frame)

    elif frame.frame_name == "CMD":

        _decode_cmd(frame)

    elif frame.frame_name == "RESPONSE":

        _decode_response(frame)


def _decode_alive(frame):

    raw = frame.raw_bytes

    for item, offset, size in CONTENT_TABLE["ALIVE"]:

        if offset + size > len(raw):
            continue

        if item == "TICK_COUNT_SHORT":

            # uint16 big-endian (REQ-FLD-011)
            value = u16_be(raw, offset)

        elif size == 1:

            value = raw[offset]

        else:

            value = s16_be(raw, offset)

        if item == "TEMPERATURE":

            value = decode_temperature(value)

        elif item == "VBATT":

            value = decode_battery(value)

        elif item == "SI_FACTOR":

            frame.decoded["_SI_FACTOR_BITS"] = value   # raw int, used for scaling
            label = SI_FACTOR_ENUM.get(value, str(value))
            value = f"{value}  ({label})"

        elif item == "ALIVE_STATUS":

            si_updated   = value & 0x01
            live_data    = (value >> 1) & 0x01
            sensor_state = (value >> 2) & 0x3F
            state_name   = SENSOR_STATE_ENUM.get(sensor_state, f"State {sensor_state}")
            value = (
                f"{state_name}"
                f"  Live={'Y' if live_data else 'N'}"
                f"  SI={'Y' if si_updated else 'N'}"
            )

        frame.decoded[item] = value


def _decode_config(frame):

    raw = frame.raw_bytes

    s = frame.permute_shift

    if len(raw) < 20 + s:
        return

    mux = raw[9 + s]

    frame.config_mux = mux

    method = frame.permute_method

    # Frame N of a packet uses version N - 1 (KEP-SWE3-006 section 7)
    version = frame.frame_num - 1 if frame.frame_num > 0 else None

    if method == PERMUTE_METHOD_RESERVED:
        frame.decoded["Permute Control"] = (
            f"Method=Reserved ({method})  frame discarded", ""
        )
        return

    if method == PERMUTE_METHOD_POLY and version is None:
        frame.decoded["Permute Control"] = (
            "Method=Polynomial  no frame number, parameters not identified", ""
        )
        return

    if method is not None:
        frame.decoded["Permute Control"] = (
            f"Method={PERMUTE_ENUM.get(method, '?')}"
            + (f"  Version={version}" if method == PERMUTE_METHOD_POLY else ""),
            "",
        )

    for index in range(CONFIG_PARAMS_PER_FRAME):

        offset = 10 + s + (index * 2)

        if offset + 1 >= len(raw):
            continue

        position = config_param_index(mux, index, method, version or 0)

        if position is None:
            continue

        value = u16_be(raw, offset)

        name = CONFIG_PARAM_NAMES[position]

        unit = CONFIG_PARAM_UNITS[position]

        frame.config_slots.append((index, position, name, offset))

        frame.config_param_block[name] = position // CONFIG_PARAMS_PER_FRAME

        # Decode enumerated fields
        if name == "Trigger Method":
            display = TRIGGER_METHOD_ENUM.get(value, str(value))
            frame.decoded[name] = (display, unit)
        elif name == "Machine ACC Detect":
            display = DETECT_METHOD_ENUM.get(value, str(value))
            frame.decoded[name] = (display, unit)
        elif name == "Permute Method":
            display = PERMUTE_ENUM.get(value, str(value))
            frame.decoded[name] = (display, unit)
        elif name in ("TWFA Scaling", "TWFB Scaling", "FFT Scaling"):
            display = SCALING_ENUM.get(value, str(value))
            frame.decoded[name] = (display, unit)
        elif name == "Short Capture":
            display = SHORT_CAPTURE_ENUM.get(value, str(value))
            frame.decoded[name] = (display, unit)
        elif name == "FFT Machine Off Count":
            display = "Always" if value == 0 else str(value)
            frame.decoded[name] = (display, unit)
        else:
            frame.decoded[name] = (value, unit)


def _decode_version(frame):

    raw = frame.raw_bytes

    # VERSION_V1 layout (frame_version >= 1):
    #   SHA-SHORT  : raw[9:16]   7 bytes ASCII
    #   FW-VER     : raw[16:73]  57 bytes null-terminated ASCII
    #   RESET      : raw[73:77]  4 bytes big-endian
    #   VBATT      : raw[77]     1 byte  20 mV/lsb
    #   PCB-VERS   : raw[78]     1 byte  lookup
    #   TEMP       : raw[79:81]  2 bytes signed big-endian  0.1 °C/lsb
    #   TICKS      : raw[81:85]  4 bytes uint32 big-endian (REQ-FLD-042)

    frame.decoded["SHA"] = bytes(raw[9:16]).decode(
        "ascii", errors="ignore"
    )

    string_bytes = []

    for b in raw[16:73]:

        if b == 0:
            break

        string_bytes.append(b)

    frame.decoded["FW Version"] = bytes(
        string_bytes
    ).decode("ascii", errors="ignore")

    if len(raw) >= 77:

        reset_reason = (
            (raw[73] << 24) |
            (raw[74] << 16) |
            (raw[75] << 8) |
            raw[76]
        )

        frame.decoded["Reset Reason"] = decode_reset_reason(reset_reason)

    if len(raw) >= 78:

        _vbatt_val = decode_battery(raw[77])
        frame.decoded["Battery Voltage"] = f"{_vbatt_val:.3f} V"
        frame.decoded["VBATT"]           = _vbatt_val   # numeric for graphs

    if len(raw) >= 79:

        pcb_raw = raw[78]

        if frame.prod_id == 3:
            pcb_str = PCB_VERSION_TABLE.get(pcb_raw, f"Unknown ({pcb_raw})")
        else:
            pcb_str = f"Unknown ({pcb_raw})"

        frame.decoded["PCB Version"] = pcb_str

    if len(raw) >= 81:

        temp = s16_be(raw, 79)
        _temp_val = decode_temperature(temp)
        frame.decoded["Temperature"]  = f"{_temp_val:.1f} °C"
        frame.decoded["TEMPERATURE"]  = _temp_val   # numeric for graphs

    if len(raw) >= 85:

        ticks = u32_be(raw, 81)

        frame.decoded["Ticks Since Reset"] = (
            f"{ticks}  ({format_elapsed_time(ticks * 60)})"
        )


def _decode_twf(frame):

    raw = frame.raw_bytes
    s   = frame.permute_shift   # 1 under RF Capability 6, else 0

    if len(raw) < 9 + s:
        return

    # Common PDU fields: TEMP (raw[9:11]), VBATT (raw[11]), each shifted by s
    if len(raw) >= 12 + s:
        _temp_val  = decode_temperature(s16_be(raw, 9 + s))
        _vbatt_val = decode_battery(raw[11 + s])
        frame.decoded["Temperature"]      = f"{_temp_val:.1f} °C"
        frame.decoded["Battery Voltage"]  = f"{_vbatt_val:.3f} V"
        # Numeric counterparts used by update_environment / update_short_interval_data
        frame.decoded["TEMPERATURE"]      = _temp_val
        frame.decoded["VBATT"]            = _vbatt_val

    # TWF fields (PDU byte_offset 4+ = raw[12+])
    twf_param      = u16_be(raw, 12 + s) if len(raw) >= 14 + s else 0
    axis_bits      = (twf_param >> 14) & 0x03
    li_factor_bits = (twf_param >> 12) & 0x03
    si_factor_bits = (twf_param >> 10) & 0x03
    li_type_bits   = (twf_param >> 8)  & 0x03
    si_type_bits   = (twf_param >> 5)  & 0x07
    permute_bits   = (twf_param >> 2)  & 0x03
    rescaled       = twf_param & 0x03

    # Under RF Capability 6 the method comes from Permute Control, which
    # PARAM[3:2] only mirrors (KEP-SWE3-006 section 10)
    if frame.permute_method is not None:
        permute_bits = frame.permute_method

    # Method 11b is reserved. A receiver cannot know how the samples were
    # ordered, so the frame is discarded rather than reassembled under a
    # guess - decoding it as sequential would put samples in the wrong
    # places and look plausible (KEP-SWE3-006 section 14).
    if permute_bits == PERMUTE_METHOD_RESERVED:
        frame.decoded["Permute Control"] = (
            f"Method=Reserved ({permute_bits})  frame discarded"
        )
        return

    if len(raw) >= 14 + s:
        frame.decoded["TWF Param"] = (
            f"Axis={TWF_AXIS_ENUM.get(axis_bits, '?')}"
            f"  Scale={SI_FACTOR_ENUM.get(si_factor_bits, '?')}"
            f"  Type={LI_TYPE_ENUM.get(li_type_bits, '?')}"
            f"  SI={SI_TYPE_ENUM.get(si_type_bits, '?')}"
            f"  Permute={PERMUTE_ENUM.get(permute_bits, '?')}"
            f"  Rescaled={rescaled}"
        )
        # Numeric SI factor — stored under the same key as ALIVE so
        # update_short_interval_data can read it uniformly.
        frame.decoded["_SI_FACTOR_BITS"] = si_factor_bits

    sample_odr = u16_be(raw, 14 + s) if len(raw) >= 16 + s else 0

    if len(raw) >= 16 + s:
        frame.decoded["Sample ODR"] = f"{sample_odr} Hz"

    pkt_number = u16_be(raw, 16 + s) if len(raw) >= 18 + s else 0
    pkt_total  = u16_be(raw, 18 + s) if len(raw) >= 20 + s else 0

    if len(raw) >= 20 + s:
        frame.decoded["Packet"] = f"{pkt_number} of {pkt_total}"

    if len(raw) >= 22 + s:
        frame.decoded["Ticks"] = format_ticks(u16_be(raw, 20 + s))

    if len(raw) >= 28 + s:
        frame.decoded["SI X"] = u16_be(raw, 22 + s)
        frame.decoded["SI Y"] = u16_be(raw, 24 + s)
        frame.decoded["SI Z"] = u16_be(raw, 26 + s)

    # Extract LI_DATA: 32 signed int16 big-endian samples at raw[28:92]
    li_data = []
    for i in range(32):
        off = 28 + s + i * 2
        if off + 2 > len(raw):
            break
        li_data.append(s16_be(raw, off))

    # Polynomial version this frame used: N - 1, where N is the 1-based frame
    # number (KEP-SWE3-006 section 7).  Nothing is carried on air for this.
    # RF Capability 5 frames always used version 0.
    version = 0

    if frame.permute_method is not None and frame.frame_num > 0:
        version = frame.frame_num - 1

    if frame.permute_control is not None:
        frame.decoded["Permute Control"] = (
            f"Method={PERMUTE_ENUM.get(permute_bits, '?')}"
            f"  Version={version}"
        )

    # Store reassembly metadata separately (not shown in Payload text)
    frame.twf_meta = {
        "pkt_number":     pkt_number,
        "version":        version,         # polynomial version of this frame
        "pkt_total":      pkt_total,
        "permute":        permute_bits,    # 0=Distance, 1=None, 2=Polynomial
        "si_factor_bits": si_factor_bits,  # 0=±8g … 3=±64g
        "si_type":        si_type_bits,    # SI_TYPE_ENUM value for SI X/Y/Z fields
        "axis":           TWF_AXIS_ENUM.get(axis_bits, "?"),
        "sample_odr":     sample_odr,
        "li_data":        li_data,
    }


def _decode_fft(frame):

    raw = frame.raw_bytes

    if len(raw) < 9:
        return

    frame.decoded["Frame"] = (
        f"{frame.frame_num} of {frame.total_frames}"
    )

    frame.decoded["Payload Bytes"] = frame.packet_length - HEADER_SIZE - 1

    if len(raw) >= 12:

        frame.decoded["FFT Header"] = " ".join(
            f"{x:02X}" for x in raw[9:min(13, len(raw))]
        )


def _decode_cmd(frame):
    """CMD frame (PL_TYPE=8): sensor -> gateway sample-sync request.
    Layout: header(0-7) + frame counter(8) + CMD_SENSOR_ID(9-11) +
    CMD_PARAM(12-13) + CMD_RETRY(14).  See api_radio_transport_cfg.h."""

    raw = frame.raw_bytes

    if len(raw) <= CMD_RETRY_OFFSET:
        return

    id_bytes = raw[CMD_SENSOR_ID_OFFSET:CMD_SENSOR_ID_OFFSET + 3]
    frame.decoded["CMD_SENSOR_ID"] = "".join(f"{b:02X}" for b in id_bytes)

    cmd_param = u16_be(raw, CMD_PARAM_OFFSET)
    frame.decoded["_CMD_PARAM_RAW"] = cmd_param
    frame.decoded["CMD_PARAM"] = (
        f"0x{cmd_param:04X}  ({CMD_PARAM_ENUM.get(cmd_param, 'UNKNOWN')})"
    )

    frame.decoded["CMD_RETRY"] = raw[CMD_RETRY_OFFSET]


def _decode_response(frame):
    """RESPONSE frame (PL_TYPE=9): gateway -> sensor sample-sync reply.
    Layout: header(0-7) + reserved(8) + echoed CMD_SENSOR_ID(9-11) +
    RESPONSE_PARAM(12-13) + variable payload(14+): a 4-byte BE timer for
    SYNC_LORES (milliseconds remaining) / SYNC_HIRES (microseconds remaining)
    followed by a 1-byte slot index (0..N-1), or up to 10 {id:u16, value:u32}
    CONFIG pairs.  See api_radio_transport_cfg.h."""

    raw = frame.raw_bytes

    if len(raw) < RESPONSE_PARAM_OFFSET + 2:
        return

    id_bytes = raw[CMD_SENSOR_ID_OFFSET:CMD_SENSOR_ID_OFFSET + 3]
    frame.decoded["Echoed Sensor ID"] = "".join(f"{b:02X}" for b in id_bytes)

    response_param = u16_be(raw, RESPONSE_PARAM_OFFSET)
    frame.decoded["_RESPONSE_PARAM_RAW"] = response_param
    frame.decoded["RESPONSE_PARAM"] = (
        f"0x{response_param:04X}  ({RESPONSE_PARAM_ENUM.get(response_param, 'UNKNOWN')})"
    )

    if response_param in (0x0001, 0x0002) and len(raw) >= RESPONSE_PAYLOAD_OFFSET + 4:

        timer_value = u32_be(raw, RESPONSE_PAYLOAD_OFFSET)
        unit = "ms" if response_param == 0x0001 else "usec"
        frame.decoded["_TIMER_RAW"] = timer_value
        frame.decoded["Timer"] = f"{timer_value} {unit} remaining"

        # 1-byte slot index immediately after the 4-byte timer, if present
        slot_offset = RESPONSE_PAYLOAD_OFFSET + 4
        if len(raw) >= slot_offset + 1:
            slot = raw[slot_offset]
            frame.decoded["_SLOT_RAW"] = slot
            frame.decoded["Slot"] = str(slot)

    elif response_param == 0x0003:

        pairs = []
        offset = RESPONSE_PAYLOAD_OFFSET

        for _ in range(RESPONSE_CONFIG_MAX_PAIRS):

            if offset + RESPONSE_CONFIG_PAIR_SIZE > len(raw):
                break

            config_id = u16_be(raw, offset)
            value     = u32_be(raw, offset + 2)
            pairs.append((config_id, value))
            offset += RESPONSE_CONFIG_PAIR_SIZE

        frame.decoded["Config Pairs"] = (
            "  ".join(f"[id=0x{cid:04X} val={val}]" for cid, val in pairs)
            if pairs else "(none pending)"
        )


# =============================================================================
# MAIN APPLICATION
# =============================================================================

class TestBenchMonitor:

    def __init__(self, root, logfile=None, initial_sensor_id: str | None = None,
                 radio=None, event_log=None, air=None):

        self.root = root

        self.logfile = logfile

        # The S2-LP kit, read directly (sources.LiveRadio), or None for a log.
        self.radio = radio

        # A simulated sensor on the air, when running without hardware.
        self.air = air

        # Every packet received live, as the log line ST's GUI would write, so
        # a change of sensor filter can replay them as rf_monitor replays a log.
        self._live_lines = deque(maxlen=LIVE_HISTORY_MAX)

        # The bench event log followed by the Events page, if any.
        from benchtools.core.events import EventTail
        self.event_tail = EventTail(event_log) if event_log else None

        self.root.title(APP_TITLE)

        self.root.geometry("1900x1100")

        self.root.configure(bg=DARK_BG)

        self._setup_ttk_styles()

        self.file_position = 0

        self.filter_sensor_id = tk.StringVar(value="323334")

        # Ordered list of sensor IDs seen so far (used to populate the combobox)
        self._seen_sensor_ids: list[str] = []

        self.latest_filtered_only = tk.BooleanVar(value=False)

        # Banner label text shown at the top of every filtered tab.
        # Updated whenever apply_settings() is called.
        self._filter_header_var = tk.StringVar(value="")
        # Latest Data's own banner label — tracked separately from the list
        # below since it reflects the Show All / Show Filtered Only toggle,
        # not just the Settings-tab Sensor ID filter. Set by create_latest_tab().
        self._latest_filter_banner = None
        # List of (label_widget,) tuples — one entry per tab that shows the banner
        self._filter_header_labels: list = []

        self.paused = False

        self.paused_frames = []

        # TWF waveform reassembly buffers (in-progress) — one per axis so that
        # interleaved X/Y/Z packets don't reset each other's sequences.
        self.twf_buffers = {"X": None, "Y": None, "Z": None}

        # Last time _update_twf_display was called for each axis (monotonic seconds).
        # Used to throttle mid-sequence renders to at most once every 5 seconds.
        self.twf_last_render = {"X": 0.0, "Y": 0.0, "Z": 0.0}

        # Suppress mid-sequence graph renders while replaying log history on
        # startup; cleared after the initial bulk read so live updates render normally.
        self._loading_history = True

        # Rolling buffer of the most recent frames seen during history load.
        # Displayed on Latest Data once the splash closes so the tab shows
        # the tail of the log rather than being empty.
        self._history_tail = deque(maxlen=50)

        # ALL frames received (sensor-unfiltered) — used to re-render Latest Data
        # when the Show All / Show Filtered button is clicked or after a replay.
        self._latest_frame_buffer: deque = deque(maxlen=500)

        # Completed waveform store: slot A or B, per axis
        # Each entry: {waveform, time_ms, odr, full_scale_g, permute_name, axis}
        self.twf_store = {
            "A": {"X": None, "Y": None, "Z": None},
            "B": {"X": None, "Y": None, "Z": None},
        }

        # Next slot to fill for each axis (alternates A→B→A after each completion)
        self.twf_next_slot = {"X": "A", "Y": "A", "Z": "A"}

        # Display selection (set before create_twf_tab is called)
        self.twf_display_ab   = tk.StringVar(value="A")
        self.twf_display_axis = tk.StringVar(value="X")   # default X-Axis

        # TWF cursor position (ms) and diagnostics StringVar
        self.twf_cursor_pos  = 0.0
        self.twf_diag_var    = tk.StringVar(value="")
        self.twf_cursor_var  = tk.StringVar(value="")

        self.axis_selection = tk.StringVar(value="Z")

        self.config_latest = {}

        self.config_update_time = {}

        self.latest_version_frame = None

        self.temperature_history = deque(maxlen=MAX_POINTS)
        self.battery_history     = deque(maxlen=MAX_POINTS)
        # Parallel timestamps (float seconds since midnight) for environment
        self.temp_time_history   = deque(maxlen=MAX_POINTS)
        self.batt_time_history   = deque(maxlen=MAX_POINTS)

        def _axis_deques():
            return {"X": deque(maxlen=MAX_POINTS),
                    "Y": deque(maxlen=MAX_POINTS),
                    "Z": deque(maxlen=MAX_POINTS)}

        self.acc_history = _axis_deques()
        self.vel_history = _axis_deques()
        self.pk_history  = _axis_deques()
        # Independent timestamp deque per series — same pattern as env temp/batt.
        # Each is appended only when its companion value deque is appended.
        self.acc_time_history = _axis_deques()
        self.vel_time_history = _axis_deques()
        self.pk_time_history  = _axis_deques()
        # Keep si_time_history as an alias for acc_time_history so that any
        # remaining references (cursor step, zoom) still compile without change.
        self.si_time_history  = self.acc_time_history

        # Magnetometer SI data from TWF frames
        self.mag_freq_history      = _axis_deques()
        self.mag_amp_history       = _axis_deques()
        self.mag_freq_time_history = _axis_deques()
        self.mag_amp_time_history  = _axis_deques()

        # Ticks counter history (from ALIVE TICK_COUNT_SHORT, 1 unit = 1 min)
        self.ticks_time_history  = deque(maxlen=MAX_POINTS)
        self.ticks_value_history = deque(maxlen=MAX_POINTS)

        # Latest SI scale factor bits (0=±8g … 3=±64g), updated from ALIVE frames
        self.si_factor_bits_latest = 0

        # Cursor positions (float seconds).  None = no cursor yet.
        self.env_cursor_t = None
        self.si_cursor_t  = None

        # X-view windows (lo, hi seconds).  None = full/auto.
        self.env_x_range = None
        self.si_x_range  = None

        # StringVars for cursor value display labels
        self.env_cursor_var = tk.StringVar(value="")
        self.si_cursor_var  = tk.StringVar(value="")

        # ── Diagnostics statistics ──────────────────────────────────────────
        # Keyed by frame_name (e.g. "ALIVE", "TWF" …).
        # Each entry: {"packets": int, "frame_times": deque(maxlen=500)}
        # "packets"     = every raw RF copy received (all frame_num values)
        # "frame_times" = timestamp (float s) of each frame_num==0 arrival,
        #                 used to compute inter-frame period statistics.
        self.diag_stats: dict = {
            name: {
                "packets":        0,
                "frame_times":    deque(maxlen=500),
                "last_seen":      "",
                # ── Drop tracking ──────────────────────────────────────────
                # A "burst" is one logical frame transmission (N RF copies).
                # burst_packets collects the copy numbers (frame_num) seen so
                # far for the current in-flight burst.  When the burst is
                # closed (new burst starts, or 1 s inactivity) the number of
                # missing copies is added to dropped_total / expected_total.
                "burst_packets":   set(),
                "burst_total":     0,
                "burst_last_wall": None,
                "dropped_total":   0,
                "expected_total":  0,
                # Last 10 logical-frame arrivals: list of (time_str, delta_s|None)
                "recent_frames":   deque(maxlen=10),
                # Parallel log-timestamp strings for frame_times (same indexing)
                "frame_time_strings": deque(maxlen=500),
                # (t_prev_str, t_curr_str) for the gap with the current min/max period
                "min_gap_info":    None,
                "max_gap_info":    None,
            }
            for name in FRAME_TYPES.values()
        }

        # StringVar for the overall success % label at the top of the Diagnostics tab
        self._diag_overall_var = tk.StringVar(value="Overall Success:  —")

        # ── Diagnostics detail table state ───────────────────────────────────
        # Frame type currently shown in the detail table ("" until first frame)
        self.diag_detail_type = ""
        # "Auto" — detail follows last received type; "Hold" — locked to selection
        self.diag_mode = tk.StringVar(value="Auto")
        # Header label StringVar for the detail table
        self.diag_detail_label_var = tk.StringVar(value="No frames received yet")

        # ── Status-bar tracking ──────────────────────────────────────────────
        # Wall-clock time (time.time()) when the most recent frame arrived,
        # plus the frame's own log timestamp string.
        self._last_frame_wall_time: float | None = None
        self._last_frame_time_str:  str           = ""

        # StringVars updated by _tick_status_bar every second
        self._status_clock_var      = tk.StringVar(value="")
        self._status_update_var     = tk.StringVar(value="No data received")
        # Captured just before _last_frame_wall_time resets on each new frame
        self._status_last_delta_var = tk.StringVar(value="")

        # Cumulative day offset for multi-day log files.  _parse_time_s returns
        # seconds-since-midnight; when a new frame's raw time is more than 1 hour
        # less than the previous frame's, we crossed midnight and add 86400 s.
        self._day_offset:      float = 0.0
        self._prev_raw_time_s: float = -1.0

        # ── Sync tab state ───────────────────────────────────────────────────
        # Keyed by sensor_id hex string.  Populated from CMD/RESPONSE frames
        # only (see _update_sync_state), unfiltered by the Sensor ID filter,
        # so every sensor actively engaged in a LORES/HIRES sync exchange is
        # visible at once — sensors that never touch the sync protocol never
        # appear here, unlike Latest Data which can only filter one sensor at
        # a time or show everything.
        # Each entry: {"phase": str, "retry": int, "time_str": str,
        #              "last_seen": float (wall time),
        #              "lores_deadline": float|None (wall time countdown reaches 0),
        #              "hires_deadline": float|None (wall time countdown reaches 0)}
        self.sync_sensors: dict = {}

        # Status bar must be packed to BOTTOM before the notebook so that
        # pack's geometry manager reserves space for it underneath.
        self._create_status_bar()

        self.notebook = ttk.Notebook(root)

        self.notebook.pack(fill=tk.BOTH, expand=True)

        self.psu_panel = PsuPanel()
        self.jlink_panel = JlinkPanel()

        self.create_latest_tab()

        self.create_st_gui_tab()

        self.create_events_tab()

        self.create_psu_tab()

        self.create_jlink_tab()

        self.create_environment_tab()

        self.create_short_interval_tab()

        self.create_twf_tab()

        self.create_ticks_tab()

        self.create_config_tab()

        self.create_diagnostics_tab()

        self.create_sync_tab()

        self.create_notes_tab()

        self.create_settings_tab()

        # Load persisted sensor IDs and apply CLI / file-based default filter
        self._load_sensor_ids(initial_sensor_id)

        # Populate filter banners with the initial sensor ID
        self._update_filter_header()

        # Save sensor IDs when the window is closed
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # Brief delay so the main window renders before history load begins
        self.root.after(100, self._start_history_load)

        self.root.after(1000, self.update_config_tab)

        self.root.after(60_000, self.update_twf_fft)

        # Status bar clock — fires every second regardless of data arrival
        self.root.after(1000, self._tick_status_bar)

        if self.event_tail is not None:
            self.root.after(EVENT_POLL_MS, self.poll_events)

    # =========================================================================
    # SETTINGS
    # =========================================================================

    # =========================================================================
    # STATUS BAR
    # =========================================================================

    def _create_status_bar(self):
        """Build the persistent status bar packed at the bottom of the root window."""

        import datetime as _dt

        bar = tk.Frame(self.root, bg=PANEL_BG, height=26)
        bar.pack(side=tk.BOTTOM, fill=tk.X)
        bar.pack_propagate(False)

        # Thin top border to separate from the notebook
        tk.Frame(bar, bg=BORDER_COL, height=1).place(relx=0, rely=0, relwidth=1)

        # ── Left: application title + version ────────────────────────────────
        tk.Label(
            bar,
            text=f"  {APP_TITLE}   v{APP_VERSION}  {APP_DATE}",
            bg=PANEL_BG, fg=TEXT_DIM,
            font=("Segoe UI", 9),
            anchor=tk.W,
        ).pack(side=tk.LEFT, padx=(8, 0))

        # ── Right: live wall-clock ────────────────────────────────────────────
        tk.Label(
            bar,
            textvariable=self._status_clock_var,
            bg=PANEL_BG, fg=TEXT_DIM,
            font=("Segoe UI", 9),
            anchor=tk.E,
        ).pack(side=tk.RIGHT, padx=(0, 10))

        # ── Right of centre: last delta (gap frozen at the moment of last arrival)
        tk.Label(
            bar,
            textvariable=self._status_last_delta_var,
            bg=PANEL_BG, fg=ACCENT_CYAN,
            font=("Segoe UI", 9),
            anchor=tk.E,
        ).pack(side=tk.RIGHT, padx=(0, 24))

        # ── Centre: last-update time + live delta ────────────────────────────
        tk.Label(
            bar,
            textvariable=self._status_update_var,
            bg=PANEL_BG, fg=TEXT_MAIN,
            font=("Segoe UI", 9),
            anchor=tk.CENTER,
        ).pack(side=tk.LEFT, expand=True)

    # ─────────────────────────────────────────────────────────────────────────

    def _tick_status_bar(self):
        """Update the status-bar clock and last-update delta once per second."""

        import datetime as _dt

        now_wall = time.time()
        now_dt   = _dt.datetime.now()
        self._status_clock_var.set(now_dt.strftime("%Y-%m-%d  %H:%M:%S"))

        if self._last_frame_wall_time is not None:
            delta_s = now_wall - self._last_frame_wall_time
            self._status_update_var.set(
                f"Last Update:  {self._last_frame_time_str}"
                f"    Δ {_fmt_delta(delta_s)}"
            )

        # Refresh diagnostics every tick so stale bursts are closed promptly
        # even when no new log lines have arrived.
        self.update_diagnostics_tab()

        self.root.after(1000, self._tick_status_bar)

    # =========================================================================
    # THEME
    # =========================================================================

    def _setup_ttk_styles(self):

        s = ttk.Style()

        try:
            s.theme_use("clam")
        except tk.TclError:
            pass

        # ── Base ─────────────────────────────────────────────────────────────
        s.configure(".",
            background=DARK_BG,
            foreground=TEXT_MAIN,
            font=("Segoe UI", 10),
            borderwidth=0,
        )

        # ── Notebook ─────────────────────────────────────────────────────────
        s.configure("TNotebook",
            background=DARK_BG,
            borderwidth=0,
            tabmargins=[2, 4, 2, 0],
        )
        s.configure("TNotebook.Tab",
            background=PANEL_BG,
            foreground=TEXT_DIM,
            padding=[14, 6],
            font=("Segoe UI", 10, "bold"),
        )
        s.map("TNotebook.Tab",
            background=[("selected", ACCENT_BLUE), ("active", BORDER_COL)],
            foreground=[("selected", "#ffffff"),   ("active", TEXT_MAIN)],
        )

        # ── Frames ───────────────────────────────────────────────────────────
        s.configure("TFrame",      background=DARK_BG)
        s.configure("TLabelframe",
            background=DARK_BG,
            bordercolor=BORDER_COL,
            relief="solid",
        )
        s.configure("TLabelframe.Label",
            background=DARK_BG,
            foreground=ACCENT_CYAN,
            font=("Segoe UI", 10, "bold"),
        )

        # ── Labels ───────────────────────────────────────────────────────────
        s.configure("TLabel",      background=DARK_BG, foreground=TEXT_MAIN)

        # ── Buttons ──────────────────────────────────────────────────────────
        s.configure("TButton",
            background=PANEL_BG,
            foreground=TEXT_MAIN,
            relief="flat",
            padding=[10, 5],
            borderwidth=1,
            bordercolor=BORDER_COL,
        )
        s.map("TButton",
            background=[("active", ACCENT_BLUE), ("pressed", "#1565c0")],
            foreground=[("active", "#ffffff")],
        )

        # ── Accent button (used for Auto/Hold toggle — teal when Auto) ────────
        s.configure("Accent.TButton",
            background=ACCENT_CYAN,
            foreground=DARK_BG,
            relief="flat",
            padding=[10, 5],
            font=("Segoe UI", 10, "bold"),
            borderwidth=0,
        )
        s.map("Accent.TButton",
            background=[("active", "#00acc1"), ("pressed", "#00838f")],
            foreground=[("active", DARK_BG)],
        )

        # Hold variant — amber to signal the locked state
        s.configure("Hold.TButton",
            background="#f9a825",
            foreground=DARK_BG,
            relief="flat",
            padding=[10, 5],
            font=("Segoe UI", 10, "bold"),
            borderwidth=0,
        )
        s.map("Hold.TButton",
            background=[("active", "#f57f17"), ("pressed", "#e65100")],
            foreground=[("active", DARK_BG)],
        )

        # ── Radio buttons ────────────────────────────────────────────────────
        s.configure("TRadiobutton",
            background=DARK_BG,
            foreground=TEXT_MAIN,
            indicatorcolor=PANEL_BG,
        )
        s.map("TRadiobutton",
            background=[("active", DARK_BG)],
            foreground=[("active", ACCENT_CYAN)],
            indicatorcolor=[("selected", ACCENT_BLUE)],
        )

        # ── Entry ────────────────────────────────────────────────────────────
        s.configure("TEntry",
            fieldbackground=PANEL_BG,
            foreground=TEXT_MAIN,
            insertcolor=TEXT_MAIN,
            bordercolor=BORDER_COL,
            lightcolor=BORDER_COL,
            darkcolor=BORDER_COL,
        )

        # ── Treeview ─────────────────────────────────────────────────────────
        s.configure("Treeview",
            background=PANEL_BG,
            foreground=TEXT_MAIN,
            fieldbackground=PANEL_BG,
            rowheight=24,
            font=("Consolas", 9),
            borderwidth=0,
        )
        s.configure("Treeview.Heading",
            background=DARK_BG,
            foreground=ACCENT_CYAN,
            font=("Segoe UI", 10, "bold"),
            relief="flat",
            padding=[4, 6],
        )
        s.map("Treeview",
            background=[("selected", ACCENT_BLUE)],
            foreground=[("selected", "#ffffff")],
        )
        s.map("Treeview.Heading",
            background=[("active", PANEL_BG)],
            foreground=[("active", ACCENT_BLUE)],
        )

        # ── Separator / Scrollbar ────────────────────────────────────────────
        s.configure("TSeparator",  background=BORDER_COL)
        s.configure("TScrollbar",
            background=PANEL_BG,
            troughcolor=DARK_BG,
            bordercolor=BORDER_COL,
            arrowcolor=TEXT_DIM,
            relief="flat",
        )

    def _update_filter_header(self):
        """Refresh the filter banner text and colour on every filtered tab.

        Environment/Short Interval/TWF/Config/Diagnostics always apply the
        Settings-tab Sensor ID filter (see process_frame's early-return), so
        their banner reflects that filter alone. Latest Data is different: it
        has its own Show All / Show Filtered Only toggle (latest_filtered_only)
        that can override the Settings filter for that tab only, so its banner
        must reflect the toggle, not just whether a filter Sensor ID is set.
        """

        sid = self.filter_sensor_id.get().upper().replace(" ", "").replace("0X", "")

        if sid:
            filtered_text = f"  Filtered  —  Sensor 0x{sid}  "
            filtered_bg   = "#1a3a1a"   # dark green tint — active filter
            filtered_fg   = "#a5d6a7"
        else:
            filtered_text = "  No filter active — showing all sensors  "
            filtered_bg   = PANEL_BG
            filtered_fg   = TEXT_DIM

        for lbl in self._filter_header_labels:
            lbl.configure(text=filtered_text, bg=filtered_bg, fg=filtered_fg)

        if self._latest_filter_banner is not None:

            if self.latest_filtered_only.get():
                lbl_text, lbl_bg, lbl_fg = filtered_text, filtered_bg, filtered_fg
            else:
                lbl_text = "  Showing ALL sensors (Show Filtered Only is off)  "
                lbl_bg   = "#1a2a3a"   # dark blue tint — Show All active
                lbl_fg   = "#90caf9"

            self._latest_filter_banner.configure(text=lbl_text, bg=lbl_bg, fg=lbl_fg)

    def _make_filter_banner(self, parent, is_latest_data=False) -> tk.Label:
        """Create and register a filter-status banner label in *parent*.

        Call once per tab immediately after the tab frame is created.
        Returns the label so the caller can pack it in the right position.

        Pass is_latest_data=True for the Latest Data tab only: that banner is
        tracked separately so it can reflect the Show All / Show Filtered Only
        toggle instead of just the Settings-tab Sensor ID filter.
        """
        lbl = tk.Label(
            parent,
            text="",
            font=("Segoe UI", 9),
            anchor=tk.W,
            padx=8, pady=2,
        )

        if is_latest_data:
            self._latest_filter_banner = lbl
        else:
            self._filter_header_labels.append(lbl)

        return lbl

    def _reset_all_data(self):
        """Clear every accumulated data deque/dict so a fresh replay can start."""

        # ── Environment ───────────────────────────────────────────────────────
        self.temperature_history.clear()
        self.battery_history.clear()
        self.temp_time_history.clear()
        self.batt_time_history.clear()

        # ── Short Interval ────────────────────────────────────────────────────
        for axis in ("X", "Y", "Z"):
            self.acc_history[axis].clear()
            self.vel_history[axis].clear()
            self.pk_history[axis].clear()
            self.acc_time_history[axis].clear()
            self.vel_time_history[axis].clear()
            self.pk_time_history[axis].clear()
            self.mag_freq_history[axis].clear()
            self.mag_amp_history[axis].clear()
            self.mag_freq_time_history[axis].clear()
            self.mag_amp_time_history[axis].clear()

        # ── Ticks ─────────────────────────────────────────────────────────────
        self.ticks_time_history.clear()
        self.ticks_value_history.clear()

        # ── TWF ───────────────────────────────────────────────────────────────
        self.twf_buffers   = {"X": None, "Y": None, "Z": None}
        self.twf_last_render = {"X": 0.0, "Y": 0.0, "Z": 0.0}
        self.twf_store     = {
            "A": {"X": None, "Y": None, "Z": None},
            "B": {"X": None, "Y": None, "Z": None},
        }
        self.twf_next_slot = {"X": "A", "Y": "A", "Z": "A"}

        # ── Config ────────────────────────────────────────────────────────────
        self.config_latest.clear()
        self.config_update_time.clear()
        self.latest_version_frame = None

        # ── Diagnostics ───────────────────────────────────────────────────────
        for entry in self.diag_stats.values():
            entry["packets"]         = 0
            entry["frame_times"].clear()
            entry["frame_time_strings"].clear()
            entry["last_seen"]       = ""
            entry["burst_packets"]   = set()
            entry["burst_total"]     = 0
            entry["burst_last_wall"] = None
            entry["dropped_total"]   = 0
            entry["expected_total"]  = 0
            entry["recent_frames"].clear()
            entry["min_gap_info"]    = None
            entry["max_gap_info"]    = None
        self.diag_detail_type = ""

        # ── Latest Data buffer ────────────────────────────────────────────────
        self._latest_frame_buffer.clear()

        # ── Status bar ────────────────────────────────────────────────────────
        self._last_frame_wall_time = None
        self._last_frame_time_str  = ""
        self._status_update_var.set("No data received")
        self._status_last_delta_var.set("")
        self._day_offset      = 0.0
        self._prev_raw_time_s = -1.0

    def _refresh_all_tabs(self):
        """Trigger a full UI refresh of every data tab after a replay."""

        self.update_environment_graphs()
        self.update_short_interval()
        self.update_ticks_graphs()
        self._update_twf_display()
        self.update_config_tab()
        self.update_diagnostics_tab()
        self._refresh_detail_table()

    def _replay_log(self):
        """Re-read the entire log file from scratch using the current sensor filter,
        then refresh every tab.  Called on filter change."""

        if self.radio is None and (not self.logfile or not os.path.exists(self.logfile)):
            self._refresh_all_tabs()
            return

        self._reset_all_data()
        self._loading_history = True
        self._history_tail.clear()

        try:
            if self.radio is not None:
                # Live from the kit: replay what has been received so far.
                for line in list(self._live_lines):
                    frame = parse_packet_line(line)
                    if frame:
                        self.process_frame(frame)
            else:
                with open(self.logfile, "r") as f:
                    f.readline()           # skip the opening header line
                    for line in f:
                        frame = parse_packet_line(line)
                        if frame:
                            self.process_frame(frame)
                    self.file_position = f.tell()
        finally:
            self._loading_history = False

        # Populate buffer from the frames accumulated during replay, then
        # re-render Latest Data so it reflects the new sensor filter.
        for frame in self._history_tail:
            self._latest_frame_buffer.append(frame)
        self._history_tail.clear()
        self._redisplay_latest()

        self._refresh_all_tabs()

    def apply_settings(self):

        self._update_filter_header()
        self._replay_log()
        print(
            f"Filter Sensor ID = "
            f"{self.filter_sensor_id.get()}"
        )

    # ── Sensor-ID persistence ─────────────────────────────────────────────────

    def _sensor_id_file(self) -> str:
        """Path to the sensor-ID list file: beside the log file, or in the
        current directory when reading the kit directly."""
        base = os.path.dirname(os.path.abspath(self.logfile)) if self.logfile else os.getcwd()
        return os.path.join(base, "sensor_ids.txt")

    def _load_sensor_ids(self, initial_filter: str | None = None):
        """Load sensor IDs from file and populate the combobox.

        *initial_filter* (from --sensor-id CLI flag) takes priority.
        If omitted, the last line of the file is used as the starting filter.
        """
        path = self._sensor_id_file()
        ids: list[str] = []
        if os.path.exists(path):
            try:
                with open(path, "r") as fh:
                    ids = [ln.strip() for ln in fh if ln.strip()]
            except OSError:
                pass

        for sid in ids:
            if sid not in self._seen_sensor_ids:
                self._seen_sensor_ids.append(sid)

        if hasattr(self, "filter_combo"):
            self.filter_combo["values"] = self._seen_sensor_ids

        # Decide the starting filter value
        if initial_filter:
            self.filter_sensor_id.set(
                initial_filter.upper().replace(" ", "").replace("0X", "")
            )
        elif ids:
            self.filter_sensor_id.set(ids[-1])

    def _save_sensor_ids(self):
        """Write the seen sensor IDs to file, newest at the bottom."""
        path = self._sensor_id_file()
        try:
            with open(path, "w") as fh:
                fh.write("\n".join(self._seen_sensor_ids))
                if self._seen_sensor_ids:
                    fh.write("\n")
        except OSError:
            pass

    def _on_close(self):
        """Save sensor IDs, stop the radio, then destroy the window."""
        self._save_sensor_ids()
        if self.air is not None:
            self.air.stop()
        if self.radio is not None:
            self.radio.close()
        self.root.destroy()

    def _register_sensor_id(self, sid: str):
        """Add *sid* to the seen-IDs list and refresh the combobox values.

        Does not change the current filter; merely makes the ID available
        in the dropdown for the user to select.
        """
        if sid not in self._seen_sensor_ids:
            self._seen_sensor_ids.append(sid)
            if hasattr(self, "filter_combo"):
                self.filter_combo["values"] = self._seen_sensor_ids

    def sensor_matches_filter(self, frame):

        filter_value = (
            self.filter_sensor_id.get()
            .upper()
            .replace(" ", "")
            .replace("0X", "")
        )

        return frame.sensor_id.upper() == filter_value

    def _redisplay_latest(self):
        """Clear the Latest Data text widget and re-render from the frame buffer
        applying the current Show All / Show Filtered setting."""

        self.latest_text.delete("1.0", tk.END)
        for frame in self._latest_frame_buffer:
            if not self.latest_filtered_only.get() or self.sensor_matches_filter(frame):
                self.display_latest_frame(frame)

    def set_latest_filter(self, enabled):

        self.latest_filtered_only.set(enabled)
        self._update_filter_header()
        self._redisplay_latest()

    def toggle_pause(self):

        self.paused = not self.paused

        if self.paused:

            self.pause_btn.config(text="Resume")

        else:

            self.pause_btn.config(text="Pause")

            for frame in self.paused_frames:
                self.process_frame(frame)

            self.paused_frames.clear()

            self.latest_text.see(tk.END)

    # =========================================================================
    # TABS
    # =========================================================================

    def create_latest_tab(self):

        tab = ttk.Frame(self.notebook)

        self.notebook.add(tab, text="Latest Data")

        self._make_filter_banner(tab, is_latest_data=True).pack(fill=tk.X)

        button_frame = ttk.Frame(tab)

        button_frame.pack(fill=tk.X, pady=5)

        ttk.Button(
            button_frame,
            text="Show All",
            command=lambda: self.set_latest_filter(False)
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            button_frame,
            text="Show Filtered Only",
            command=lambda: self.set_latest_filter(True)
        ).pack(side=tk.LEFT, padx=5)

        self.pause_btn = ttk.Button(
            button_frame,
            text="Pause",
            command=self.toggle_pause
        )
        self.pause_btn.pack(side=tk.LEFT, padx=5)

        self.latest_text = tk.Text(
            tab,
            font=("Consolas", 10),
            wrap=tk.NONE,
            bg=PLOT_BG,
            fg=TEXT_MAIN,
            insertbackground=TEXT_MAIN,
            selectbackground=ACCENT_BLUE,
            selectforeground="#ffffff",
            relief="flat",
            borderwidth=0,
        )

        self.latest_text.pack(fill=tk.BOTH, expand=True)

        # ── Raw-byte highlight tags ───────────────────────────────────────────
        self.latest_text.tag_configure(
            "header_blue",
            foreground="#90caf9",
            background="#0d47a1",
            font=("Consolas", 10, "bold"),
        )
        self.latest_text.tag_configure(
            "header_green",
            foreground="#a5d6a7",
            background="#1b5e20",
            font=("Consolas", 10, "bold"),
        )
        self.latest_text.tag_configure(
            "counter_orange",
            foreground="#ffcc80",
            background="#bf360c",
            font=("Consolas", 10, "bold"),
        )

        # ── Per-frame-type title bar tags ─────────────────────────────────────
        for frame_name, (fg, bg) in FRAME_PALETTE.items():
            self.latest_text.tag_configure(
                f"frame_{frame_name.lower()}",
                background=bg,
                foreground=fg,
                font=("Consolas", 10, "bold"),
            )

        # ── Section heading (Packet Header / Payload) ─────────────────────────
        self.latest_text.tag_configure(
            "section_hdr",
            foreground=ACCENT_CYAN,
            font=("Consolas", 10, "bold"),
        )

        # ── Separator line ────────────────────────────────────────────────────
        self.latest_text.tag_configure(
            "separator",
            foreground=BORDER_COL,
        )

    # =========================================================================
    # SYNC TAB
    # =========================================================================

    # A sensor row is dropped if no CMD/RESPONSE sync activity is seen for it
    # for this long (well past the ~10 minute default LORES window, so a
    # genuinely abandoned sequence eventually clears itself).
    _SYNC_ROW_STALE_SECS = 1200.0

    # Redraw interval for the countdown display.  Independent of log-file
    # polling (POLL_INTERVAL_MS) so the countdowns animate smoothly.
    _SYNC_TICK_MS = 200

    def create_sync_tab(self):
        """Build the Sync tab: one row per sensor actively engaged in a
        LORES/HIRES sample-sync exchange, with live countdowns.

        Unlike Latest Data (which can only filter to one sensor at a time,
        or show every sensor's traffic unfiltered), this tab tracks CMD/
        RESPONSE frames for every sensor regardless of the Sensor ID filter,
        and only ever shows sensors that are actually taking part in sync —
        so unrelated sensor traffic in the log never clutters the view.
        """

        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Sync")

        tk.Label(
            tab,
            text=(
                "Live sample-sync — one row per sensor currently exchanging "
                "CMD/RESPONSE LORES or HIRES frames with the gateway. "
                "Not affected by the Settings tab Sensor ID filter."
            ),
            bg=DARK_BG, fg=TEXT_DIM,
            font=("Segoe UI", 9),
            anchor=tk.W, justify=tk.LEFT, wraplength=1700,
        ).pack(fill=tk.X, padx=8, pady=(8, 4))

        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

        cols = ("sensor_id", "slot", "phase", "retry", "lores_remaining", "hires_remaining", "last_seen")

        self.sync_tree = ttk.Treeview(
            tree_frame,
            columns=cols,
            show="headings",
            height=20,
        )

        self.sync_tree.heading("sensor_id",       text="Sensor ID",        anchor=tk.W)
        self.sync_tree.heading("slot",             text="Slot",             anchor=tk.E)
        self.sync_tree.heading("phase",            text="Phase",            anchor=tk.W)
        self.sync_tree.heading("retry",             text="Retry",            anchor=tk.E)
        self.sync_tree.heading("lores_remaining",  text="LORES Remaining", anchor=tk.E)
        self.sync_tree.heading("hires_remaining",  text="HIRES Remaining", anchor=tk.E)
        self.sync_tree.heading("last_seen",         text="Last Seen",        anchor=tk.E)

        self.sync_tree.column("sensor_id",      width=110, anchor=tk.W)
        self.sync_tree.column("slot",            width=50,  anchor=tk.E)
        self.sync_tree.column("phase",           width=220, anchor=tk.W)
        self.sync_tree.column("retry",            width=70,  anchor=tk.E)
        self.sync_tree.column("lores_remaining", width=160, anchor=tk.E)
        self.sync_tree.column("hires_remaining", width=160, anchor=tk.E)
        self.sync_tree.column("last_seen",        width=100, anchor=tk.E)

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.sync_tree.yview)
        self.sync_tree.configure(yscrollcommand=vsb.set)
        self.sync_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        self.sync_tree.tag_configure("odd",         background=TREE_ROW_ODD,  foreground=TEXT_MAIN)
        self.sync_tree.tag_configure("even",        background=TREE_ROW_EVEN, foreground=TEXT_MAIN)
        self.sync_tree.tag_configure("hires_active", background=TREE_ROW_EVEN, foreground="#80cbc4")
        self.sync_tree.tag_configure("fired",        background=TREE_ROW_EVEN, foreground="#a5d6a7")
        self.sync_tree.tag_configure("nack",         background=TREE_ROW_EVEN, foreground="#ef5350")

        # Start the countdown redraw loop
        self.root.after(self._SYNC_TICK_MS, self._tick_sync_tab)

    def _update_sync_state(self, frame):
        """Update per-sensor sync state from one CMD or RESPONSE frame.

        Called for every CMD/RESPONSE frame regardless of the Sensor ID
        filter — see create_sync_tab() docstring for why.  Deadlines are
        anchored to wall-clock time.time() at the moment each frame is
        processed (same approach _update_diag_stats already uses for the
        status bar), so countdowns are only meaningful while live-monitoring
        an actively growing log; replaying an old log will show each
        countdown as if it started just now.
        """

        now = time.time()

        if frame.frame_name == "CMD":

            cmd_param = frame.decoded.get("_CMD_PARAM_RAW")

            if cmd_param is None:
                return

            sid   = frame.sensor_id
            entry = self.sync_sensors.get(sid)

            if cmd_param == 0x0001:  # REQ_LORES — fresh sync cycle, reset state

                entry = {
                    "phase":           "REQ_LORES sent",
                    "retry":           frame.decoded.get("CMD_RETRY", 0),
                    "time_str":        frame.time_string,
                    "last_seen":       now,
                    "lores_deadline":  None,
                    "hires_deadline":  None,
                    "slot":            None,
                }
                self.sync_sensors[sid] = entry
                return

            if entry is None:
                # REQ_HIRES/ACK/NACK/GENERAL seen with no prior REQ_LORES on
                # this sensor (e.g. tool started mid-cycle) — start tracking it.
                entry = {
                    "phase": "", "retry": 0, "time_str": frame.time_string,
                    "last_seen": now, "lores_deadline": None, "hires_deadline": None,
                    "slot": None,
                }
                self.sync_sensors[sid] = entry

            entry["retry"]     = frame.decoded.get("CMD_RETRY", entry.get("retry", 0))
            entry["time_str"]  = frame.time_string
            entry["last_seen"] = now

            if cmd_param == 0x0002:      # REQ_HIRES
                entry["phase"] = "REQ_HIRES sent"
            elif cmd_param == 0x8001:    # ACK_SYNC_LORES
                entry["phase"] = "ACK_LORES -> escalating to HIRES"
            elif cmd_param == 0x8002:    # ACK_SYNC_HIRES
                entry["phase"] = "ACK_HIRES"
            elif cmd_param == 0x8003:    # ACK_CONFIG
                entry["phase"] = "ACK_CONFIG"
            elif cmd_param == 0x0003:    # GENERAL — sync cycle idle/ended
                entry["phase"] = "Idle (GENERAL)"
            elif cmd_param in (0x7F01, 0x7F02, 0x7F03):  # NACK_*
                entry["phase"] = "NACK"

        elif frame.frame_name == "RESPONSE":

            response_param = frame.decoded.get("_RESPONSE_PARAM_RAW")
            sid            = frame.decoded.get("Echoed Sensor ID")
            timer_raw      = frame.decoded.get("_TIMER_RAW")

            if sid is None or response_param not in (0x0001, 0x0002) or timer_raw is None:
                return

            entry = self.sync_sensors.setdefault(sid, {
                "phase": "", "retry": 0, "time_str": frame.time_string,
                "last_seen": now, "lores_deadline": None, "hires_deadline": None,
                "slot": None,
            })

            entry["time_str"]  = frame.time_string
            entry["last_seen"] = now

            # SYNC_LORES/HIRES both carry the slot byte (see rf_monitor decoder);
            # cache it on the entry for the Sync-tab Slot column.
            slot_raw = frame.decoded.get("_SLOT_RAW")
            if slot_raw is not None:
                entry["slot"] = slot_raw

            if response_param == 0x0001:   # SYNC_LORES — remaining time is in MILLISECONDS
                entry["phase"]          = "LORES: counting down"
                entry["lores_deadline"] = now + (timer_raw / 1_000.0)

            else:                          # SYNC_HIRES — remaining time is in MICROSECONDS
                entry["phase"]          = "HIRES: counting down"
                entry["hires_deadline"] = now + (timer_raw / 1_000_000.0)

    def _tick_sync_tab(self):
        """Redraw the Sync tab countdowns, then reschedule."""

        self._render_sync_tab()
        self.root.after(self._SYNC_TICK_MS, self._tick_sync_tab)

    def _render_sync_tab(self):

        now = time.time()

        # Drop rows with no sync activity for a long time
        stale = [sid for sid, e in self.sync_sensors.items()
                 if (now - e.get("last_seen", now)) > self._SYNC_ROW_STALE_SECS]
        for sid in stale:
            del self.sync_sensors[sid]

        # Clear LORES/HIRES remaining fields for sensors that have returned to
        # ACK_CONFIG or the GENERAL idle phase AND fired at least 10 seconds
        # ago. Keeps the "FIRED" indication visible for a moment after each
        # sync completes, then wipes the stale countdowns so the row no longer
        # implies an active sync. Sensor slot is preserved (it identifies the
        # last window slot the sensor was assigned, still useful post-sync).
        for entry in self.sync_sensors.values():
            fire_time = entry.get("hires_deadline")
            phase     = entry.get("phase", "")
            if (fire_time is not None
                    and (now - fire_time) > 10.0
                    and phase in ("Idle (GENERAL)", "ACK_CONFIG")):
                entry["lores_deadline"] = None
                entry["hires_deadline"] = None

        tree = self.sync_tree

        for item in tree.get_children():
            tree.delete(item)

        def _fmt_lores(entry):
            deadline = entry.get("lores_deadline")
            if deadline is None:
                return "—"
            remaining = deadline - now
            if remaining <= 0:
                return "0:00 (expired)"
            m, s = divmod(int(remaining), 60)
            return f"{m}:{s:02d}"

        def _fmt_hires(entry):
            deadline = entry.get("hires_deadline")
            if deadline is None:
                return "—"
            remaining = deadline - now
            if remaining <= 0:
                return "0.000 s  (FIRED)"
            return f"{remaining:.3f} s"

        def _fmt_slot(entry):
            slot = entry.get("slot")
            return "—" if slot is None else str(slot)

        for index, (sid, entry) in enumerate(sorted(self.sync_sensors.items())):

            tag = "even" if (index % 2 == 0) else "odd"

            hires_deadline = entry.get("hires_deadline")
            if entry.get("phase") == "NACK":
                tag = "nack"
            elif hires_deadline is not None:
                tag = "fired" if (hires_deadline - now) <= 0 else "hires_active"

            tree.insert(
                "", tk.END,
                values=(
                    f"0x{sid}",
                    _fmt_slot(entry),
                    entry.get("phase", ""),
                    entry.get("retry", ""),
                    _fmt_lores(entry),
                    _fmt_hires(entry),
                    entry.get("time_str", ""),
                ),
                tags=(tag,),
            )

    def create_environment_tab(self):

        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Environment")

        self._make_filter_banner(tab).pack(fill=tk.X)

        # ── Control bar ──────────────────────────────────────────────────────
        ctrl = ttk.Frame(tab)
        ctrl.pack(fill=tk.X, padx=5, pady=3)

        ttk.Label(ctrl, text="Cursor:").pack(side=tk.LEFT, padx=(0, 4))
        for lbl, n in [("◀◀", -10), ("◀", -1), ("▶", 1), ("▶▶", 10)]:
            ttk.Button(ctrl, text=lbl, width=4,
                       command=lambda s=n: self._env_cursor_step(s)
                       ).pack(side=tk.LEFT, padx=1)

        ttk.Separator(ctrl, orient=tk.VERTICAL).pack(
            side=tk.LEFT, fill=tk.Y, padx=8)
        ttk.Label(ctrl, text="Zoom:").pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(ctrl, text="In",    width=4,
                   command=lambda: self._env_zoom(0.5)).pack(side=tk.LEFT, padx=1)
        ttk.Button(ctrl, text="Out",   width=4,
                   command=lambda: self._env_zoom(2.0)).pack(side=tk.LEFT, padx=1)
        ttk.Button(ctrl, text="Reset", width=6,
                   command=self._env_zoom_reset).pack(side=tk.LEFT, padx=1)

        tk.Label(
            tab, textvariable=self.env_cursor_var,
            bg=DARK_BG, fg=ACCENT_CYAN,
            font=("Consolas", 9), anchor=tk.W,
        ).pack(fill=tk.X, padx=5, pady=1)

        # ── Figure ───────────────────────────────────────────────────────────
        fig = Figure(figsize=(10, 8), dpi=100)
        fig.subplots_adjust(hspace=0.50)

        self.temp_ax = fig.add_subplot(211)
        self.batt_ax = fig.add_subplot(212)

        self.temp_line, = self.temp_ax.plot([], [], color="#ff8f00", linewidth=1.2)
        self.batt_line, = self.batt_ax.plot([], [], color="#66bb6a", linewidth=1.2)

        self.temp_ax.set_title("Temperature")
        self.temp_ax.set_ylabel("°C")

        self.batt_ax.set_title("Battery Voltage")
        self.batt_ax.set_ylabel("V")
        self.batt_ax.set_xlabel("Time")

        apply_fig_style(fig, [self.temp_ax, self.batt_ax])

        # Cursor lines (one per subplot, hidden until data arrives)
        from matplotlib.lines import Line2D
        from matplotlib.transforms import blended_transform_factory
        for ax, store in [(self.temp_ax, "env_temp_cursor"),
                          (self.batt_ax, "env_batt_cursor")]:
            bl = blended_transform_factory(ax.transData, ax.transAxes)
            cur = Line2D([0, 0], [0, 1], transform=bl,
                         color=ACCENT_CYAN, linewidth=1.0,
                         linestyle="--", alpha=0.85, visible=False, zorder=5)
            ax.add_line(cur)
            setattr(self, store, cur)

        self.env_canvas = FigureCanvasTkAgg(fig, master=tab)
        self.env_canvas.get_tk_widget().configure(bg=DARK_BG, highlightthickness=0)
        self.env_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # Click on graph moves cursor
        self.env_canvas.mpl_connect(
            "button_press_event",
            lambda e: self._env_cursor_click(e)
        )

    def create_short_interval_tab(self):

        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Short Interval")

        self._make_filter_banner(tab).pack(fill=tk.X)

        # ── Axis selector + cursor controls ──────────────────────────────────
        topbar = ttk.Frame(tab)
        topbar.pack(fill=tk.X, padx=5, pady=3)

        ttk.Label(topbar, text="Axis:").pack(side=tk.LEFT, padx=(0, 4))
        for axis in ["X", "Y", "Z"]:
            ttk.Radiobutton(
                topbar, text=axis,
                variable=self.axis_selection, value=axis,
                command=self.update_short_interval,
            ).pack(side=tk.LEFT)

        ttk.Separator(topbar, orient=tk.VERTICAL).pack(
            side=tk.LEFT, fill=tk.Y, padx=8)
        ttk.Label(topbar, text="Cursor:").pack(side=tk.LEFT, padx=(0, 4))
        for lbl, n in [("◀◀", -10), ("◀", -1), ("▶", 1), ("▶▶", 10)]:
            ttk.Button(topbar, text=lbl, width=4,
                       command=lambda s=n: self._si_cursor_step(s)
                       ).pack(side=tk.LEFT, padx=1)

        ttk.Separator(topbar, orient=tk.VERTICAL).pack(
            side=tk.LEFT, fill=tk.Y, padx=8)
        ttk.Label(topbar, text="Zoom:").pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(topbar, text="In",    width=4,
                   command=lambda: self._si_zoom(0.5)).pack(side=tk.LEFT, padx=1)
        ttk.Button(topbar, text="Out",   width=4,
                   command=lambda: self._si_zoom(2.0)).pack(side=tk.LEFT, padx=1)
        ttk.Button(topbar, text="Reset", width=6,
                   command=self._si_zoom_reset).pack(side=tk.LEFT, padx=1)

        tk.Label(
            tab, textvariable=self.si_cursor_var,
            bg=DARK_BG, fg=ACCENT_CYAN,
            font=("Consolas", 9), anchor=tk.W,
        ).pack(fill=tk.X, padx=5, pady=1)

        # ── Figure ───────────────────────────────────────────────────────────
        fig = Figure(figsize=(10, 11), dpi=100)
        fig.subplots_adjust(hspace=0.70, right=0.88)

        self.acc_ax = fig.add_subplot(411)
        self.vel_ax = fig.add_subplot(412)
        self.pk_ax  = fig.add_subplot(413)
        self.mag_ax = fig.add_subplot(414)

        self.acc_line, = self.acc_ax.plot([], [], color="#42a5f5", linewidth=1.2)
        self.vel_line, = self.vel_ax.plot([], [], color="#4caf50", linewidth=1.2)
        self.pk_line,  = self.pk_ax.plot( [], [], color="#ff9800", linewidth=1.2)
        self.mag_freq_line, = self.mag_ax.plot(
            [], [], color="#e040fb", linewidth=1.2, label="MAG FREQ")
        self.mag_amp_line, = self.mag_ax.plot(
            [], [], color="#69f0ae", linewidth=1.2, linestyle="--", label="MAG AMP")

        self.acc_ax.set_title("Acceleration RMS")
        self.acc_ax.set_ylabel("Raw")

        self.vel_ax.set_title("Velocity RMS")
        self.vel_ax.set_ylabel("Velocity")

        self.pk_ax.set_title("Peak To Peak")
        self.pk_ax.set_ylabel("Raw")

        self.mag_ax.set_title("Magnetometer")
        self.mag_ax.set_ylabel("Raw")
        self.mag_ax.set_xlabel("Time")   # only the bottom subplot needs a label

        # Right-hand conversion axes (SI-factor dependent; labels updated in update_short_interval)
        self.acc_ax_r = self.acc_ax.twinx()
        self.vel_ax_r = self.vel_ax.twinx()
        self.pk_ax_r  = self.pk_ax.twinx()
        self.mag_ax_r = self.mag_ax.twinx()
        _style_twin_ax(self.acc_ax_r, "mg")
        _style_twin_ax(self.vel_ax_r, "mm/s")
        _style_twin_ax(self.pk_ax_r,  "mg")
        _style_twin_ax(self.mag_ax_r, "")

        apply_fig_style(fig, [self.acc_ax, self.vel_ax, self.pk_ax, self.mag_ax])

        self.mag_ax.legend(
            facecolor=PANEL_BG, edgecolor=BORDER_COL,
            labelcolor=TEXT_MAIN, fontsize=8, loc="upper right",
        )

        # Cursor lines (one per subplot)
        from matplotlib.lines import Line2D
        from matplotlib.transforms import blended_transform_factory
        self.si_cursors = []
        for ax in [self.acc_ax, self.vel_ax, self.pk_ax, self.mag_ax]:
            bl = blended_transform_factory(ax.transData, ax.transAxes)
            cur = Line2D([0, 0], [0, 1], transform=bl,
                         color=ACCENT_CYAN, linewidth=1.0,
                         linestyle="--", alpha=0.85, visible=False, zorder=5)
            ax.add_line(cur)
            self.si_cursors.append(cur)

        self.si_canvas = FigureCanvasTkAgg(fig, master=tab)
        self.si_canvas.get_tk_widget().configure(bg=DARK_BG, highlightthickness=0)
        self.si_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # Click on graph moves cursor
        self.si_canvas.mpl_connect(
            "button_press_event",
            lambda e: self._si_cursor_click(e)
        )

    def create_twf_tab(self):

        tab = ttk.Frame(self.notebook)

        self.notebook.add(tab, text="TWF")

        self._make_filter_banner(tab).pack(fill=tk.X)

        # ── Button bar ───────────────────────────────────────────────────────
        btn_bar = ttk.Frame(tab)

        btn_bar.pack(fill=tk.X, padx=5, pady=3)

        ttk.Label(btn_bar, text="Buffer:").pack(side=tk.LEFT, padx=(0, 4))

        for ab in ("A", "B"):

            ttk.Radiobutton(
                btn_bar,
                text=f"TWF{ab}",
                variable=self.twf_display_ab,
                value=ab,
                command=self._update_twf_display,
            ).pack(side=tk.LEFT, padx=2)

        ttk.Separator(btn_bar, orient=tk.VERTICAL).pack(
            side=tk.LEFT, fill=tk.Y, padx=8
        )

        ttk.Label(btn_bar, text="Axis:").pack(side=tk.LEFT, padx=(0, 4))

        for ax in ("X", "Y", "Z"):

            ttk.Radiobutton(
                btn_bar,
                text=f"{ax}-Axis",
                variable=self.twf_display_axis,
                value=ax,
                command=self._update_twf_display,
            ).pack(side=tk.LEFT, padx=2)

        # ── Cursor / Zoom button row ─────────────────────────────────────────
        ctrl_bar = ttk.Frame(tab)

        ctrl_bar.pack(fill=tk.X, padx=5, pady=2)

        ttk.Label(ctrl_bar, text="Cursor:").pack(side=tk.LEFT, padx=(0, 4))

        for label, steps in [("◀◀", -100), ("◀", -10), ("▶", 10), ("▶▶", 100)]:
            ttk.Button(
                ctrl_bar,
                text=label,
                width=4,
                command=lambda n=steps: self._cursor_step(n),
            ).pack(side=tk.LEFT, padx=1)

        ttk.Separator(ctrl_bar, orient=tk.VERTICAL).pack(
            side=tk.LEFT, fill=tk.Y, padx=8
        )

        ttk.Label(ctrl_bar, text="Zoom:").pack(side=tk.LEFT, padx=(0, 4))

        ttk.Button(
            ctrl_bar, text="In",
            width=4, command=lambda: self._zoom_twf(2.0)
        ).pack(side=tk.LEFT, padx=1)

        ttk.Button(
            ctrl_bar, text="Out",
            width=4, command=lambda: self._zoom_twf(0.5)
        ).pack(side=tk.LEFT, padx=1)

        ttk.Button(
            ctrl_bar, text="Reset",
            width=5, command=self._zoom_reset_twf
        ).pack(side=tk.LEFT, padx=1)

        # ── Cursor value display ─────────────────────────────────────────────
        ttk.Label(
            tab,
            textvariable=self.twf_cursor_var,
            font=("Consolas", 10),
            foreground=ACCENT_CYAN,
            anchor=tk.W,
        ).pack(fill=tk.X, padx=5)

        # ── Status label ────────────────────────────────────────────────────
        self.twf_status_var = tk.StringVar(value="No TWF data received")

        ttk.Label(
            tab,
            textvariable=self.twf_status_var,
            font=("Consolas", 10),
            anchor=tk.W
        ).pack(fill=tk.X, padx=5, pady=1)

        # ── Diagnostics label ────────────────────────────────────────────────
        ttk.Label(
            tab,
            textvariable=self.twf_diag_var,
            font=("Consolas", 10),
            foreground="#ff8f00",
            anchor=tk.W,
        ).pack(fill=tk.X, padx=5, pady=1)

        # ── Split figure: TWF (top) + FFT (bottom) ───────────────────────────
        fig = Figure(figsize=(10, 8), dpi=100)

        fig.subplots_adjust(hspace=0.45)

        # Time-domain waveform (top half)
        self.twf_ax = fig.add_subplot(211)

        self.twf_line, = self.twf_ax.plot(
            [], [], linewidth=0.7, color="#4fc3f7"
        )

        # Cursor: a Line2D with a blended transform so x is in data coords
        # (milliseconds) while y always spans 0→1 in axes-fraction coords.
        # Using Line2D + add_line avoids the visible=False→True render artefact
        # that axvline produces with the TkAgg backend.
        _blend = blended_transform_factory(
            self.twf_ax.transData,
            self.twf_ax.transAxes,
        )
        self.twf_cursor_line = Line2D(
            [0, 0], [0, 1],
            transform=_blend,
            color=ACCENT_CYAN,
            linewidth=1.0,
            linestyle="--",
            alpha=0.85,
            visible=False,
            zorder=5,
        )
        self.twf_ax.add_line(self.twf_cursor_line)

        self.twf_cursor_ann = self.twf_ax.text(
            0.01, 0.97, "",
            transform=self.twf_ax.transAxes,
            color=ACCENT_CYAN, fontsize=8,
            verticalalignment="top",
            fontfamily="monospace",
        )

        self.twf_ax.set_title("Time Waveform")
        self.twf_ax.set_xlabel("Time (ms)")
        self.twf_ax.set_ylabel("Acceleration (mg)")

        # Frequency-domain FFT (bottom half)
        self.fft_ax = fig.add_subplot(212)

        self.fft_line, = self.fft_ax.plot(
            [], [], linewidth=0.8, color="#ffa726"
        )
        self.fft_ax.set_title("FFT  (not yet computed)")
        self.fft_ax.set_xlabel("Frequency (Hz)")
        self.fft_ax.set_ylabel("Amplitude (mg)")

        apply_fig_style(fig, [self.twf_ax, self.fft_ax])

        self.twf_canvas = FigureCanvasTkAgg(fig, master=tab)

        self.twf_canvas.get_tk_widget().configure(
            bg=DARK_BG, highlightthickness=0
        )
        self.twf_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    # =========================================================================
    # TICKS TAB
    # =========================================================================

    def create_ticks_tab(self):
        """Two-subplot graph: raw ticks counter value and per-frame delta."""

        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Ticks")

        self._make_filter_banner(tab).pack(fill=tk.X)

        fig = Figure(figsize=(10, 7), dpi=100)
        fig.subplots_adjust(hspace=0.50)

        self.ticks_val_ax   = fig.add_subplot(211)
        self.ticks_delta_ax = fig.add_subplot(212)

        self.ticks_val_line,   = self.ticks_val_ax.plot(
            [], [], color="#42a5f5", linewidth=1.2, marker="o", markersize=3)
        self.ticks_delta_line, = self.ticks_delta_ax.plot(
            [], [], color="#66bb6a", linewidth=1.2, marker="o", markersize=3)

        self.ticks_val_ax.set_title("Ticks Counter")
        self.ticks_val_ax.set_ylabel("Ticks (1 tick = 1 min)")

        self.ticks_delta_ax.set_title("Tick Delta (frame-to-frame interval)")
        self.ticks_delta_ax.set_ylabel("Δ Ticks")
        self.ticks_delta_ax.set_xlabel("Time")

        apply_fig_style(fig, [self.ticks_val_ax, self.ticks_delta_ax])

        self.ticks_canvas = FigureCanvasTkAgg(fig, master=tab)
        self.ticks_canvas.get_tk_widget().configure(bg=DARK_BG, highlightthickness=0)
        self.ticks_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def update_ticks_data(self, frame):
        """Extract TICK_COUNT_SHORT from an ALIVE frame and store for graphing.

        Only the first RF copy of each logical frame is recorded; duplicate
        copies carry the same tick value and would produce spurious 0-deltas.
        """

        if frame.frame_num > 1:
            return

        ticks = frame.decoded.get("TICK_COUNT_SHORT")
        if ticks is None:
            return

        t = frame.abs_time_s
        self.ticks_time_history.append(t)
        self.ticks_value_history.append(ticks)

        if not self._loading_history:
            self.update_ticks_graphs()

    def update_ticks_graphs(self):
        """Redraw the ticks value and delta subplots."""

        from matplotlib.ticker import FuncFormatter
        time_fmt = FuncFormatter(lambda x, _: _fmt_time_s(x))

        t_vals = list(self.ticks_time_history)
        v_vals = list(self.ticks_value_history)

        self.ticks_val_line.set_data(t_vals, v_vals)

        # Delta: difference between consecutive values; skip negative (counter reset)
        if len(v_vals) >= 2:
            d_t   = t_vals[1:]
            d_v   = [v_vals[k + 1] - v_vals[k] for k in range(len(v_vals) - 1)]
            # Treat negative deltas as 0 (reset or out-of-order)
            d_v   = [max(0, d) for d in d_v]
        else:
            d_t, d_v = [], []

        self.ticks_delta_line.set_data(d_t, d_v)

        # Show the active sensor filter in the titles so the user can confirm
        # which sensor's data is being displayed (sensors can have similar tick ranges).
        sid = self.filter_sensor_id.get().upper().replace(" ", "").replace("0X", "")
        sensor_label = f"  [0x{sid}]" if sid else "  [all sensors]"
        n = len(v_vals)
        self.ticks_val_ax.set_title(f"Ticks Counter{sensor_label}  ({n} frames)")
        self.ticks_delta_ax.set_title(f"Tick Delta (frame-to-frame interval){sensor_label}")

        for ax in (self.ticks_val_ax, self.ticks_delta_ax):
            ax.relim()
            ax.autoscale_view()
            ax.xaxis.set_major_formatter(time_fmt)
            for lbl in ax.get_xticklabels():
                lbl.set_rotation(30); lbl.set_ha("right"); lbl.set_fontsize(8)

        self.ticks_canvas.draw()

    def create_config_tab(self):

        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Config")

        self._make_filter_banner(tab).pack(fill=tk.X)

        # ── Three side-by-side parameter tables ──────────────────────────────
        main_frame = ttk.Frame(tab)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=(5, 2))

        _cols = ("block", "param_id", "description", "value", "units")

        def _make_cfg_tree(parent):
            tree = ttk.Treeview(parent, columns=_cols, show="headings", height=20)
            tree.heading("block",       text="Block",       anchor=tk.CENTER)
            tree.heading("param_id",    text="Param",       anchor=tk.CENTER)
            tree.heading("description", text="Description", anchor=tk.W)
            tree.heading("value",       text="Value",       anchor=tk.CENTER)
            tree.heading("units",       text="Units",       anchor=tk.W)
            tree.column("block",       width=50,  anchor=tk.CENTER, stretch=False)
            tree.column("param_id",    width=45,  anchor=tk.CENTER, stretch=False)
            tree.column("description", width=185, anchor=tk.W)
            tree.column("value",       width=65,  anchor=tk.CENTER, stretch=False)
            tree.column("units",       width=55,  anchor=tk.W,      stretch=False)
            tree.tag_configure("odd",      background=TREE_ROW_ODD,  foreground=TEXT_MAIN)
            tree.tag_configure("even",     background=TREE_ROW_EVEN, foreground=TEXT_MAIN)
            tree.tag_configure("disabled", background=TREE_ROW_ODD,  foreground="#546e7a")
            # Amber highlight: parameter exists but has no dedicated detail table entry
            tree.tag_configure("unused",   background=TREE_ROW_ODD,  foreground="#ffa726")
            return tree

        for col_idx, attr in enumerate(
            ("config_tree_left", "config_tree_mid", "config_tree_right")
        ):
            col_frame = ttk.Frame(main_frame)
            col_frame.pack(
                side=tk.LEFT, fill=tk.BOTH, expand=True,
                padx=(0, 4) if col_idx < 2 else (0, 0),
            )
            tree = _make_cfg_tree(col_frame)
            tree.pack(fill=tk.BOTH, expand=True)
            setattr(self, attr, tree)

        # ── Bottom row: detail summary tables side-by-side ───────────────────
        # Order (left→right): Block Last Update | Operation Timings |
        #                     Trigger Settings | Sampling Configuration
        bottom_row = ttk.Frame(tab)
        bottom_row.pack(fill=tk.X, expand=False, padx=5, pady=(0, 3))

        # ── 1. Block last-update summary ──────────────────────────────────────
        sum_outer = ttk.LabelFrame(bottom_row, text="Block Last Update")
        sum_outer.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 4))

        sum_cols = ("block", "last_seen", "age")
        self.config_summary_tree = ttk.Treeview(
            sum_outer, columns=sum_cols, show="headings", height=5,
        )
        self.config_summary_tree.heading("block",     text="Block",      anchor=tk.CENTER)
        self.config_summary_tree.heading("last_seen", text="Last Seen",  anchor=tk.W)
        self.config_summary_tree.heading("age",       text="Time Since", anchor=tk.W)
        self.config_summary_tree.column("block",     width=45,  anchor=tk.CENTER, stretch=False)
        self.config_summary_tree.column("last_seen", width=90,  anchor=tk.W,  stretch=False)
        self.config_summary_tree.column("age",       width=100, anchor=tk.W,  stretch=False)
        self.config_summary_tree.tag_configure("odd",  background=TREE_ROW_ODD,  foreground=TEXT_MAIN)
        self.config_summary_tree.tag_configure("even", background=TREE_ROW_EVEN, foreground=TEXT_MAIN)
        self.config_summary_tree.pack()

        # ── 2. Operation Timings ──────────────────────────────────────────────
        tim_outer = ttk.LabelFrame(bottom_row, text="Operation Timings")
        tim_outer.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 4))

        tim_cols = ("parameter", "value")
        self.config_timings_tree = ttk.Treeview(
            tim_outer, columns=tim_cols, show="headings", height=9,
        )
        self.config_timings_tree.heading("parameter", text="Item",  anchor=tk.W)
        self.config_timings_tree.heading("value",     text="Value", anchor=tk.W)
        self.config_timings_tree.column("parameter", width=160, anchor=tk.W,  stretch=False)
        self.config_timings_tree.column("value",     width=80,  anchor=tk.W,  stretch=False)
        self.config_timings_tree.tag_configure("odd",  background=TREE_ROW_ODD,  foreground=TEXT_MAIN)
        self.config_timings_tree.tag_configure("even", background=TREE_ROW_EVEN, foreground=TEXT_MAIN)
        for _j, _iid in enumerate((
            "wakeup_idle", "sample_delay", "post_sample",
            "seek_machine", "delay_confirm", "confirm_machine",
            "transmit_twf", "return_idle", "machine_on_confirm",
        )):
            self.config_timings_tree.insert(
                "", tk.END, iid=_iid, values=("", ""),
                tags=("odd" if _j % 2 == 0 else "even",),
            )
        self.config_timings_tree.pack()

        # ── 3. Trigger Settings ───────────────────────────────────────────────
        trig_outer = ttk.LabelFrame(bottom_row, text="Trigger Settings")
        trig_outer.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 4))

        trig_cols = ("parameter", "value")
        self.config_trigger_tree = ttk.Treeview(
            trig_outer, columns=trig_cols, show="headings", height=5,
        )
        self.config_trigger_tree.heading("parameter", text="Item",  anchor=tk.W)
        self.config_trigger_tree.heading("value",     text="Value", anchor=tk.W)
        self.config_trigger_tree.column("parameter", width=90,  anchor=tk.W,  stretch=False)
        self.config_trigger_tree.column("value",     width=180, anchor=tk.W,  stretch=False)
        self.config_trigger_tree.tag_configure("odd",  background=TREE_ROW_ODD,  foreground=TEXT_MAIN)
        self.config_trigger_tree.tag_configure("even", background=TREE_ROW_EVEN, foreground=TEXT_MAIN)
        for _j, _iid in enumerate(("scaling", "method", "threshold", "tr4", "tr5")):
            self.config_trigger_tree.insert("", tk.END, iid=_iid,
                values=("", ""), tags=("odd" if _j % 2 == 0 else "even",))
        self.config_trigger_tree.pack()

        # ── 4. Sampling Configuration ─────────────────────────────────────────
        samp_outer = ttk.LabelFrame(bottom_row, text="Sampling Configuration")
        samp_outer.pack(side=tk.LEFT, fill=tk.Y)

        samp_cols = ("parameter", "twfa", "twfb", "rms")
        self.config_sampling_tree = ttk.Treeview(
            samp_outer, columns=samp_cols, show="headings", height=5,
        )
        self.config_sampling_tree.heading("parameter", text="Item",        anchor=tk.W)
        self.config_sampling_tree.heading("twfa",      text="TWFA",       anchor=tk.CENTER)
        self.config_sampling_tree.heading("twfb",      text="TWFB",       anchor=tk.CENTER)
        self.config_sampling_tree.heading("rms",       text="RMS",        anchor=tk.CENTER)
        self.config_sampling_tree.column("parameter", width=95,  anchor=tk.W,      stretch=False)
        self.config_sampling_tree.column("twfa",      width=120, anchor=tk.CENTER, stretch=False)
        self.config_sampling_tree.column("twfb",      width=120, anchor=tk.CENTER, stretch=False)
        self.config_sampling_tree.column("rms",       width=80,  anchor=tk.CENTER, stretch=False)
        self.config_sampling_tree.tag_configure("odd",  background=TREE_ROW_ODD,  foreground=TEXT_MAIN)
        self.config_sampling_tree.tag_configure("even", background=TREE_ROW_EVEN, foreground=TEXT_MAIN)
        _samp_row_ids = ("enable", "axis_en", "odr", "samples", "samples_tx")
        for _j, _iid in enumerate(_samp_row_ids):
            self.config_sampling_tree.insert("", tk.END, iid=_iid,
                values=("", "", "", ""),
                tags=("odd" if _j % 2 == 0 else "even",))
        self.config_sampling_tree.pack()

        # ── 5. Sync ───────────────────────────────────────────────────────────
        sync_outer = ttk.LabelFrame(bottom_row, text="Sync")
        sync_outer.pack(side=tk.LEFT, fill=tk.Y, padx=(4, 0))

        sync_cols = ("parameter", "value")
        self.config_sync_tree = ttk.Treeview(
            sync_outer, columns=sync_cols, show="headings", height=5,
        )
        self.config_sync_tree.heading("parameter", text="Item",  anchor=tk.W)
        self.config_sync_tree.heading("value",     text="Value", anchor=tk.W)
        self.config_sync_tree.column("parameter", width=100, anchor=tk.W,  stretch=False)
        self.config_sync_tree.column("value",     width=55,  anchor=tk.W,  stretch=False)
        self.config_sync_tree.tag_configure("odd",  background=TREE_ROW_ODD,  foreground=TEXT_MAIN)
        self.config_sync_tree.tag_configure("even", background=TREE_ROW_EVEN, foreground=TEXT_MAIN)
        for _j, _iid in enumerate(("sync_en", "sync_retry", "sync_max", "listen_en", "s5")):
            self.config_sync_tree.insert("", tk.END, iid=_iid, values=("", ""),
                tags=("odd" if _j % 2 == 0 else "even",))
        self.config_sync_tree.pack()

        # ── 6. FFT ────────────────────────────────────────────────────────────
        fft_outer = ttk.LabelFrame(bottom_row, text="FFT")
        fft_outer.pack(side=tk.LEFT, fill=tk.Y, padx=(4, 0))

        fft_cols = ("parameter", "value")
        self.config_fft_tree = ttk.Treeview(
            fft_outer, columns=fft_cols, show="headings", height=10,
        )
        self.config_fft_tree.heading("parameter", text="Item",  anchor=tk.W)
        self.config_fft_tree.heading("value",     text="Value", anchor=tk.W)
        self.config_fft_tree.column("parameter", width=130, anchor=tk.W,  stretch=False)
        self.config_fft_tree.column("value",     width=55,  anchor=tk.W,  stretch=False)
        self.config_fft_tree.tag_configure("odd",  background=TREE_ROW_ODD,  foreground=TEXT_MAIN)
        self.config_fft_tree.tag_configure("even", background=TREE_ROW_EVEN, foreground=TEXT_MAIN)
        for _j, _iid in enumerate(("fft_en", "fft3_ax", "fft3_f1", "fft3_f2", "rms_min_freq",
                                   "fft_odr", "fft_samples", "fft_scaling", "short_capture", "fft_off_count")):
            self.config_fft_tree.insert("", tk.END, iid=_iid, values=("", ""),
                tags=("odd" if _j % 2 == 0 else "even",))
        self.config_fft_tree.pack()

        # ── 7. Other ──────────────────────────────────────────────────────────
        oth_outer = ttk.LabelFrame(bottom_row, text="Other")
        oth_outer.pack(side=tk.LEFT, fill=tk.Y, padx=(4, 0))

        oth_cols = ("parameter", "value")
        self.config_other_tree = ttk.Treeview(
            oth_outer, columns=oth_cols, show="headings", height=5,
        )
        self.config_other_tree.heading("parameter", text="Item",  anchor=tk.W)
        self.config_other_tree.heading("value",     text="Value", anchor=tk.W)
        self.config_other_tree.column("parameter", width=140, anchor=tk.W,  stretch=False)
        self.config_other_tree.column("value",     width=55,  anchor=tk.W,  stretch=False)
        self.config_other_tree.tag_configure("odd",  background=TREE_ROW_ODD,  foreground=TEXT_MAIN)
        self.config_other_tree.tag_configure("even", background=TREE_ROW_EVEN, foreground=TEXT_MAIN)
        for _j, _iid in enumerate(
            ("alive_period", "batt_delay", "transit_wait", "transit_wake", "o5")
        ):
            self.config_other_tree.insert("", tk.END, iid=_iid, values=("", ""),
                tags=("odd" if _j % 2 == 0 else "even",))
        self.config_other_tree.pack()

        # ── Identification ────────────────────────────────────────────────────
        id_frame = ttk.LabelFrame(tab, text="Identification")
        id_frame.pack(fill=tk.BOTH, expand=False, padx=5, pady=(0, 5))

        self.id_text = tk.Text(
            id_frame,
            height=6,
            font=("Consolas", 10),
            bg=PLOT_BG,
            fg=TEXT_MAIN,
            insertbackground=TEXT_MAIN,
            selectbackground=ACCENT_BLUE,
            selectforeground="#ffffff",
            relief="flat",
            borderwidth=0,
        )
        self.id_text.pack(fill=tk.BOTH, expand=True)

    # =========================================================================
    # DIAGNOSTICS TAB
    # =========================================================================

    def create_diagnostics_tab(self):
        """Build the Diagnostics tab with a Period statistics table."""

        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Diagnostics")

        self._make_filter_banner(tab).pack(fill=tk.X)

        # ── Header bar ───────────────────────────────────────────────────────
        hdr = tk.Frame(tab, bg=PANEL_BG)
        hdr.pack(fill=tk.X, padx=6, pady=(6, 0))

        tk.Label(
            hdr, text="Period Statistics",
            bg=PANEL_BG, fg=TEXT_MAIN,
            font=("Segoe UI", 11, "bold"),
        ).pack(side=tk.LEFT, padx=(8, 16), pady=6)

        # Overall success % — updated by update_diagnostics_tab
        tk.Label(
            hdr, textvariable=self._diag_overall_var,
            bg=PANEL_BG, fg=ACCENT_CYAN,
            font=("Segoe UI", 10),
        ).pack(side=tk.LEFT, padx=4, pady=6)

        ttk.Button(
            hdr, text="Reset",
            command=self._diag_reset,
        ).pack(side=tk.RIGHT, padx=(4, 8), pady=4)

        # Auto / Hold toggle — packed to the right of Reset
        self._diag_mode_btn = ttk.Button(
            hdr, text="Auto",
            command=self._diag_toggle_mode,
            style="Accent.TButton",
        )
        self._diag_mode_btn.pack(side=tk.RIGHT, padx=4, pady=4)

        # ── Period table ─────────────────────────────────────────────────────
        # Column order: Frame Type | Frames | Packets | Dropped | Success %
        #               | Avg Period | Std Dev | Min | Max | Last Seen
        cols = (
            "frame_type",
            "frames",
            "packets",
            "dropped",
            "success_pct",
            "avg_period",
            "std_dev",
            "min_period",
            "max_period",
            "last_seen",
        )

        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        self.diag_tree = ttk.Treeview(
            tree_frame,
            columns=cols,
            show="headings",
            height=len(FRAME_TYPES) + 2,
        )

        # Headings — Frame Type left-aligned, all others right-aligned
        self.diag_tree.heading("frame_type",  text="Frame Type",   anchor=tk.W)
        self.diag_tree.heading("frames",      text="Frames",       anchor=tk.E)
        self.diag_tree.heading("packets",     text="Packets",      anchor=tk.E)
        self.diag_tree.heading("dropped",     text="Dropped",      anchor=tk.E)
        self.diag_tree.heading("success_pct", text="Success %",    anchor=tk.E)
        self.diag_tree.heading("avg_period",  text="Avg Period (s)", anchor=tk.E)
        self.diag_tree.heading("std_dev",     text="Std Dev (s)",  anchor=tk.E)
        self.diag_tree.heading("min_period",  text="Min (s)",      anchor=tk.E)
        self.diag_tree.heading("max_period",  text="Max (s)",      anchor=tk.E)
        self.diag_tree.heading("last_seen",   text="Last Seen",    anchor=tk.E)

        # Column widths and cell alignment
        self.diag_tree.column("frame_type",  width=110, anchor=tk.W)
        self.diag_tree.column("frames",      width=75,  anchor=tk.E)
        self.diag_tree.column("packets",     width=75,  anchor=tk.E)
        self.diag_tree.column("dropped",     width=75,  anchor=tk.E)
        self.diag_tree.column("success_pct", width=85,  anchor=tk.E)
        self.diag_tree.column("avg_period",  width=190, anchor=tk.E)
        self.diag_tree.column("std_dev",     width=190, anchor=tk.E)
        self.diag_tree.column("min_period",  width=190, anchor=tk.E)
        self.diag_tree.column("max_period",  width=190, anchor=tk.E)
        self.diag_tree.column("last_seen",   width=120, anchor=tk.E)

        self.diag_tree.tag_configure("odd",  background=TREE_ROW_ODD,  foreground=TEXT_MAIN)
        self.diag_tree.tag_configure("even", background=TREE_ROW_EVEN, foreground=TEXT_MAIN)
        self.diag_tree.tag_configure("zero", background=TREE_ROW_ODD,  foreground=TEXT_DIM)

        sb = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.diag_tree.yview)
        self.diag_tree.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.diag_tree.pack(fill=tk.BOTH, expand=True)

        # Clicking a row in the period table selects that type for the detail table
        self.diag_tree.bind("<<TreeviewSelect>>", self._diag_row_clicked)

        # Hover tooltip for Min / Max period cells — shows the two frame timestamps
        self._diag_tooltip = None   # active Toplevel or None
        self.diag_tree.bind("<Motion>",  self._diag_tree_motion)
        self.diag_tree.bind("<Leave>",   lambda _e: self._hide_diag_tooltip())

        # Pre-populate one row per known frame type so the order is stable
        _blank = (0, 0, 0, "—", "—", "—", "—", "—", "—", "")
        for i, name in enumerate(FRAME_TYPES.values()):
            tag = "odd" if i % 2 else "even"
            self.diag_tree.insert(
                "", tk.END, iid=name, tags=(tag,),
                values=(name, *_blank),
            )

        # ── Detail table ─────────────────────────────────────────────────────
        detail_outer = tk.Frame(tab, bg=PANEL_BG)
        detail_outer.pack(fill=tk.X, padx=6, pady=(0, 6))

        # Header row for the detail table
        det_hdr = tk.Frame(detail_outer, bg=PANEL_BG)
        det_hdr.pack(fill=tk.X)
        tk.Label(
            det_hdr, textvariable=self.diag_detail_label_var,
            bg=PANEL_BG, fg=TEXT_MAIN,
            font=("Segoe UI", 10, "bold"),
            anchor=tk.W,
        ).pack(side=tk.LEFT, padx=8, pady=(6, 2))

        # The detail treeview — fixed at 10 rows, no scrollbar needed
        det_cols = ("time", "delta")
        self.diag_detail_tree = ttk.Treeview(
            detail_outer,
            columns=det_cols,
            show="headings",
            height=10,
        )
        self.diag_detail_tree.heading("time",  text="Time",       anchor=tk.E)
        self.diag_detail_tree.heading("delta", text="Delta (s)",  anchor=tk.E)
        self.diag_detail_tree.column("time",   width=100, anchor=tk.E, stretch=False)
        self.diag_detail_tree.column("delta",  width=165, anchor=tk.E, stretch=False)

        self.diag_detail_tree.tag_configure("odd",  background=TREE_ROW_ODD,  foreground=TEXT_MAIN)
        self.diag_detail_tree.tag_configure("even", background=TREE_ROW_EVEN, foreground=TEXT_MAIN)
        self.diag_detail_tree.pack(side=tk.LEFT, anchor=tk.NW, padx=0, pady=(0, 4))

        # Pre-populate 10 blank rows with stable iids so item() updates are cheap
        for j in range(10):
            tag = "odd" if j % 2 else "even"
            self.diag_detail_tree.insert(
                "", tk.END, iid=f"d{j}", tags=(tag,), values=("", ""),
            )

    # ─────────────────────────────────────────────────────────────────────────

    def _update_diag_stats(self, frame):
        """Accumulate raw packet counts, period timestamps, and burst drop data."""

        name = frame.frame_name
        if name not in self.diag_stats:
            # Unknown frame type — create a slot on the fly
            self.diag_stats[name] = {
                "packets":         0,
                "frame_times":     deque(maxlen=500),
                "last_seen":       "",
                "burst_packets":   set(),
                "burst_total":     0,
                "burst_last_wall": None,
                "dropped_total":   0,
                "expected_total":  0,
                "recent_frames":   deque(maxlen=10),
            }

        entry  = self.diag_stats[name]
        now_wt = time.time()

        entry["packets"]  += 1
        entry["last_seen"] = frame.time_string

        # Capture the elapsed time since the previous frame as "Last Delta"
        # before resetting the wall-clock reference to now.
        if self._last_frame_wall_time is not None:
            elapsed = now_wt - self._last_frame_wall_time
            self._status_last_delta_var.set(
                f"Last Δ  {_fmt_delta(elapsed)}"
            )

        # Track most-recent frame arrival for the status bar
        self._last_frame_wall_time = now_wt
        self._last_frame_time_str  = frame.time_string

        # ── Period statistics & recent-frame history ──────────────────────
        # Record once per logical frame (first copy only).
        if frame.frame_num <= 1:
            t = frame.abs_time_s
            # Delta to the previous logical frame of this type
            if entry["frame_times"]:
                raw_delta = t - entry["frame_times"][-1]
                delta_s   = raw_delta if raw_delta > 0 else None
            else:
                delta_s = None
            entry["frame_times"].append(t)
            entry["frame_time_strings"].append(frame.time_string)
            entry["recent_frames"].append((frame.time_string, delta_s))

            # In Auto mode track the latest type so the detail table follows it.
            # The actual UI refresh happens below (outside loading suppression).
            self.diag_detail_type = name

        # ── Detail table refresh (suppressed during history load) ─────────
        if not self._loading_history:
            mode = self.diag_mode.get()
            if mode == "Auto" and frame.frame_num <= 1:
                self._refresh_detail_table()
            elif mode == "Hold" and name == self.diag_detail_type and frame.frame_num <= 1:
                self._refresh_detail_table()

        # ── Burst / drop tracking ─────────────────────────────────────────
        fn = frame.frame_num    # 1-based copy index (1, 2, 3 …)
        ft = frame.total_frames # total copies expected for this burst

        if ft > 0:
            # Seeing copy 1 while a burst is already open means a new logical
            # frame has started — close the previous burst before opening a new one.
            if fn == 1 and entry["burst_packets"]:
                self._close_burst(entry)

            entry["burst_packets"].add(fn)
            entry["burst_total"]      = ft
            entry["burst_last_wall"]  = now_wt

    # ─────────────────────────────────────────────────────────────────────────

    def _close_burst(self, entry):
        """Close an in-progress burst, tallying expected vs received copies."""

        ft = entry.get("burst_total", 0)
        bp = entry.get("burst_packets", set())

        if ft > 0 and bp:
            received = len(bp)
            dropped  = max(0, ft - received)
            entry["expected_total"] += ft
            entry["dropped_total"]  += dropped

        entry["burst_packets"]   = set()
        entry["burst_total"]     = 0
        entry["burst_last_wall"] = None

    # ─────────────────────────────────────────────────────────────────────────

    def _close_stale_bursts(self):
        """Close any burst that has seen no new packets for ≥ 1 second."""

        cutoff = time.time() - 1.0
        for entry in self.diag_stats.values():
            last_wall = entry.get("burst_last_wall")
            if last_wall is not None and last_wall <= cutoff:
                self._close_burst(entry)

    # ─────────────────────────────────────────────────────────────────────────

    def _refresh_detail_table(self):
        """Populate the detail table with the last 10 frames of the selected type."""

        name  = self.diag_detail_type
        entry = self.diag_stats.get(name)

        # Update the header label
        if name:
            self.diag_detail_label_var.set(
                f"Last 10 Frames  —  {name}"
                + ("  [Hold]" if self.diag_mode.get() == "Hold" else "")
            )
        else:
            self.diag_detail_label_var.set("No frames received yet")

        # Build list most-recent first
        recent = list(entry["recent_frames"]) if entry else []
        recent_rev = list(reversed(recent))   # index 0 = most recent

        for j in range(10):
            tag = "odd" if j % 2 else "even"
            if j < len(recent_rev):
                t_str, delta_s = recent_rev[j]
                delta_fmt = _fmt_period(delta_s) if delta_s is not None else "—"
            else:
                t_str, delta_fmt = "", ""
            self.diag_detail_tree.item(f"d{j}", values=(t_str, delta_fmt), tags=(tag,))

    # ─────────────────────────────────────────────────────────────────────────

    def _diag_row_clicked(self, _event):
        """Handle selection in the period table — switch detail view to that type."""

        sel = self.diag_tree.selection()
        if sel:
            self.diag_detail_type = sel[0]   # iid == frame type name
            self._refresh_detail_table()

    # ─────────────────────────────────────────────────────────────────────────

    def _diag_toggle_mode(self):
        """Toggle between Auto and Hold modes for the detail table."""

        if self.diag_mode.get() == "Auto":
            self.diag_mode.set("Hold")
            self._diag_mode_btn.configure(text="Hold", style="Hold.TButton")
        else:
            self.diag_mode.set("Auto")
            self._diag_mode_btn.configure(text="Auto", style="Accent.TButton")
        # Refresh label to show/hide [Hold] indicator
        self._refresh_detail_table()

    # ─────────────────────────────────────────────────────────────────────────

    def update_diagnostics_tab(self):
        """Close stale bursts, recompute statistics, and refresh the treeview."""

        self._close_stale_bursts()

        total_expected_all = 0
        total_dropped_all  = 0

        for i, name in enumerate(FRAME_TYPES.values()):
            if name not in self.diag_stats:
                continue

            entry     = self.diag_stats[name]
            pkts      = entry["packets"]
            times     = list(entry["frame_times"])
            frames    = len(times)
            last_seen = entry.get("last_seen", "")
            exp       = entry.get("expected_total", 0)
            drp       = entry.get("dropped_total",  0)

            total_expected_all += exp
            total_dropped_all  += drp

            tag = "zero" if pkts == 0 else ("odd" if i % 2 else "even")

            # ── Drop columns ─────────────────────────────────────────────
            if exp > 0:
                pct_s = f"{100.0 * (exp - drp) / exp:.1f}%"
            else:
                pct_s = "—"
            drp_s = str(drp) if exp > 0 else "—"

            # ── Period statistics ─────────────────────────────────────────
            avg_s = std_s = mn_s = mx_s = "—"
            time_strs = list(entry.get("frame_time_strings", []))

            if frames >= 2:
                gaps = []
                min_g = max_g = None
                min_info = max_info = None

                for k in range(len(times) - 1):
                    g = times[k + 1] - times[k]
                    if g <= 0:
                        continue
                    gaps.append(g)
                    t_prev = time_strs[k]     if k     < len(time_strs) else "?"
                    t_curr = time_strs[k + 1] if k + 1 < len(time_strs) else "?"
                    if min_g is None or g < min_g:
                        min_g, min_info = g, (t_prev, t_curr)
                    if max_g is None or g > max_g:
                        max_g, max_info = g, (t_prev, t_curr)

                entry["min_gap_info"] = min_info
                entry["max_gap_info"] = max_info

                if gaps:
                    avg      = sum(gaps) / len(gaps)
                    variance = sum((g - avg) ** 2 for g in gaps) / len(gaps)
                    std      = variance ** 0.5
                    avg_s    = _fmt_period(avg)
                    std_s    = _fmt_period(std)
                    mn_s     = _fmt_period(min(gaps))
                    mx_s     = _fmt_period(max(gaps))

            self.diag_tree.item(
                name,
                tags=(tag,),
                values=(
                    name, frames, pkts, drp_s, pct_s,
                    avg_s, std_s, mn_s, mx_s,
                    last_seen,
                ),
            )

        # ── Overall success % label ───────────────────────────────────────
        if total_expected_all > 0:
            rcv_all = total_expected_all - total_dropped_all
            pct_all = 100.0 * rcv_all / total_expected_all
            self._diag_overall_var.set(
                f"Overall Success:  {pct_all:.1f}%"
                f"   ({rcv_all} / {total_expected_all}"
                f"   dropped: {total_dropped_all})"
            )
        else:
            self._diag_overall_var.set("Overall Success:  —")

    # ─────────────────────────────────────────────────────────────────────────

    # ── Diagnostics tooltip ───────────────────────────────────────────────────

    # Map Treeview column identifiers to the diag_stats key holding gap info
    _DIAG_TOOLTIP_COLS = {
        "#8": "min_gap_info",
        "#9": "max_gap_info",
    }

    def _hide_diag_tooltip(self):
        if self._diag_tooltip is not None:
            try:
                self._diag_tooltip.destroy()
            except tk.TclError:
                pass
            self._diag_tooltip = None

    def _diag_tree_motion(self, event):
        tree = self.diag_tree
        row  = tree.identify_row(event.y)
        col  = tree.identify_column(event.x)

        key = self._DIAG_TOOLTIP_COLS.get(col)
        if not key or not row:
            self._hide_diag_tooltip()
            return

        entry = self.diag_stats.get(row)
        info  = entry.get(key) if entry else None
        if not info:
            self._hide_diag_tooltip()
            return

        t_prev, t_curr = info
        label = "Min period" if key == "min_gap_info" else "Max period"
        text  = (
            f"{label}\n"
            f"  Previous frame : {t_prev}\n"
            f"  This frame     : {t_curr}"
        )

        # Reuse existing tooltip window if already visible
        if self._diag_tooltip is not None:
            try:
                self._diag_tooltip.wm_geometry(
                    f"+{event.x_root + 16}+{event.y_root + 8}")
                for w in self._diag_tooltip.winfo_children():
                    w.configure(text=text)
                return
            except tk.TclError:
                self._diag_tooltip = None

        tip = tk.Toplevel(self.root)
        tip.wm_overrideredirect(True)
        tip.wm_geometry(f"+{event.x_root + 16}+{event.y_root + 8}")
        tip.configure(bg=BORDER_COL)
        tk.Label(
            tip, text=text,
            bg=PANEL_BG, fg=TEXT_MAIN,
            font=("Consolas", 9),
            justify=tk.LEFT,
            padx=8, pady=4,
        ).pack()
        self._diag_tooltip = tip

    # ─────────────────────────────────────────────────────────────────────────

    def _diag_reset(self):
        """Clear all diagnostics statistics."""

        for entry in self.diag_stats.values():
            entry["packets"]         = 0
            entry["frame_times"].clear()
            entry["frame_time_strings"].clear()
            entry["last_seen"]       = ""
            entry["burst_packets"]   = set()
            entry["burst_total"]     = 0
            entry["burst_last_wall"] = None
            entry["dropped_total"]   = 0
            entry["expected_total"]  = 0
            entry["recent_frames"].clear()
            entry["min_gap_info"]    = None
            entry["max_gap_info"]    = None

        self.update_diagnostics_tab()
        self._refresh_detail_table()

    # =========================================================================
    # SETTINGS TAB
    # =========================================================================

    def create_notes_tab(self):
        """Notes tab — Fault Description and Findings text for the exported report."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Notes")

        for row_idx, (label_text, attr) in enumerate([
            ("Fault Description", "notes_fault_text"),
            ("Findings",          "notes_findings_text"),
        ]):
            outer = ttk.LabelFrame(tab, text=label_text)
            outer.grid(row=row_idx, column=0, sticky="nsew", padx=16, pady=(12, 4))
            tab.grid_rowconfigure(row_idx, weight=1)

            txt = tk.Text(
                outer,
                wrap=tk.WORD,
                font=("Segoe UI", 10),
                bg=PANEL_BG, fg=TEXT_MAIN,
                insertbackground=TEXT_MAIN,
                relief=tk.FLAT,
                bd=0,
                padx=8, pady=6,
            )
            vsb = ttk.Scrollbar(outer, orient=tk.VERTICAL, command=txt.yview)
            txt.configure(yscrollcommand=vsb.set)
            txt.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            vsb.pack(side=tk.RIGHT, fill=tk.Y)
            setattr(self, attr, txt)

        tab.grid_columnconfigure(0, weight=1)

    def create_settings_tab(self):

        tab = ttk.Frame(self.notebook)

        self.notebook.add(tab, text="Settings")

        # ── Sensor Filter ─────────────────────────────────────────────────────
        frame = ttk.Frame(tab)
        frame.pack(anchor=tk.NW, padx=20, pady=20)

        ttk.Label(
            frame,
            text="Filter Sensor Id:"
        ).grid(row=0, column=0, padx=10, pady=10)

        ttk.Label(
            frame,
            text="0x"
        ).grid(row=0, column=1, sticky=tk.E, padx=(10, 0), pady=10)

        self.filter_combo = ttk.Combobox(
            frame,
            width=18,
            textvariable=self.filter_sensor_id,
            values=self._seen_sensor_ids,
        )
        # Keep the field fully editable (default state for Combobox is "normal")
        self.filter_combo.grid(
            row=0, column=2, padx=(0, 10), pady=10
        )

        ttk.Button(
            frame,
            text="Apply",
            command=self.apply_settings
        ).grid(row=0, column=3, padx=10, pady=10)

        # ── Export Report ─────────────────────────────────────────────────────
        exp_outer = ttk.LabelFrame(tab, text="Export Report")
        exp_outer.pack(anchor=tk.NW, padx=20, pady=(0, 10))

        self.export_format = tk.StringVar(value="html")

        fmt_row = ttk.Frame(exp_outer)
        fmt_row.pack(anchor=tk.W, padx=10, pady=(8, 4))
        ttk.Label(fmt_row, text="Format:").pack(side=tk.LEFT, padx=(0, 10))
        ttk.Radiobutton(
            fmt_row, text="HTML (single file)",
            variable=self.export_format, value="html",
        ).pack(side=tk.LEFT, padx=(0, 16))
        ttk.Radiobutton(
            fmt_row, text="PDF",
            variable=self.export_format, value="pdf",
        ).pack(side=tk.LEFT)

        btn_row = ttk.Frame(exp_outer)
        btn_row.pack(anchor=tk.W, padx=10, pady=(4, 10))
        ttk.Button(
            btn_row, text="Export Report…",
            command=self.export_report,
        ).pack(side=tk.LEFT, padx=(0, 14))
        self._export_status_var = tk.StringVar(value="")
        tk.Label(
            btn_row, textvariable=self._export_status_var,
            bg=DARK_BG, fg=ACCENT_CYAN,
            font=("Segoe UI", 9),
        ).pack(side=tk.LEFT)

    # =========================================================================
    # EXPORT
    # =========================================================================

    def export_report(self):
        """Open a save dialog and export to HTML or PDF."""
        from tkinter import filedialog
        fmt = self.export_format.get()
        if fmt == "html":
            path = filedialog.asksaveasfilename(
                defaultextension=".html",
                filetypes=[("HTML files", "*.html"), ("All files", "*.*")],
                title="Export HTML Report",
            )
            if path:
                try:
                    self._export_html(path)
                    self._export_status_var.set(f"Saved: {os.path.basename(path)}")
                except Exception as exc:
                    self._export_status_var.set(f"Error: {exc}")
        else:
            path = filedialog.asksaveasfilename(
                defaultextension=".pdf",
                filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
                title="Export PDF Report",
            )
            if path:
                try:
                    self._export_pdf(path)
                    self._export_status_var.set(f"Saved: {os.path.basename(path)}")
                except Exception as exc:
                    self._export_status_var.set(f"Error: {exc}")

    # ── Shared helpers ────────────────────────────────────────────────────────

    def _fig_to_base64(self, fig):
        """Return a PNG render of *fig* as a base64-encoded ASCII string."""
        from io import BytesIO
        import base64
        buf = BytesIO()
        fig.savefig(buf, format="png", dpi=100, bbox_inches="tight",
                    facecolor=fig.get_facecolor())
        buf.seek(0)
        return base64.b64encode(buf.read()).decode("ascii")

    def _report_header_info(self):
        """Return (timestamp_str, sensor_id_str) for report headers."""
        import datetime
        now = datetime.datetime.now().strftime("%Y-%m-%d  %H:%M:%S")
        sid = self.filter_sensor_id.get().upper().replace(" ", "").replace("0X", "")
        return now, sid

    # ── HTML export ───────────────────────────────────────────────────────────

    _HTML_CSS = """
body { font-family: 'Segoe UI', Consolas, sans-serif;
       background:#1a1d2e; color:#dce1f0; margin:24px; }
h1   { color:#26c6da; margin-bottom:4px; }
h2   { color:#26c6da; margin-top:32px; border-bottom:1px solid #374060;
       padding-bottom:4px; }
p    { color:#7a8a9e; margin:4px 0; }
img  { max-width:100%; border:1px solid #374060; margin:8px 0; display:block; }
table{ border-collapse:collapse; width:100%; margin:8px 0 16px; font-size:12px; }
th   { background:#252840; color:#26c6da; padding:6px 10px; text-align:left; }
td   { padding:5px 10px; border-bottom:1px solid #374060;
       font-family:Consolas,monospace; }
tr:nth-child(odd)  td { background:#252840; }
tr:nth-child(even) td { background:#1e2240; }
pre  { background:#13162a; color:#dce1f0; padding:12px;
       font-size:10px; overflow-x:auto; white-space:pre; }
"""

    def _config_html_table(self):
        """Build an HTML table of all received config parameters."""
        def _sort_key(item):
            (blk, k), _ = item
            names = CONFIG_MUX_TABLE.get(blk, [])
            try:    idx = names.index(k)
            except ValueError: idx = 999
            return (blk, idx)

        rows = sorted(self.config_latest.items(), key=_sort_key)
        if not rows:
            return "<p><em>No configuration data received.</em></p>"

        html = ["<table>",
                "<tr><th>Block</th><th>Parameter</th><th>Value</th><th>Units</th></tr>"]
        for (blk, key), val in rows:
            if isinstance(val, tuple):
                value, unit = val
            else:
                value, unit = val, ""
            html.append(
                f"<tr><td>{blk}</td><td>{key}</td>"
                f"<td>{value}</td><td>{unit}</td></tr>"
            )
        html.append("</table>")
        return "\n".join(html)

    def _diag_html_table(self):
        """Build an HTML table of period statistics from diag_stats."""
        hdrs = ("Frame Type", "Frames", "Packets", "Dropped", "Success %",
                "Avg Period", "Std Dev", "Min Period", "Max Period", "Last Seen")
        html = ["<table>",
                "<tr>" + "".join(f"<th>{h}</th>" for h in hdrs) + "</tr>"]

        for name in FRAME_TYPES.values():
            entry = self.diag_stats.get(name)
            if not entry:
                continue
            pkts   = entry["packets"]
            times  = list(entry["frame_times"])
            frames = len(times)
            exp    = entry.get("expected_total", 0)
            drp    = entry.get("dropped_total",  0)
            ls     = entry.get("last_seen", "")

            pct_s = f"{100.0*(exp-drp)/exp:.1f}%" if exp > 0 else "—"
            drp_s = str(drp) if exp > 0 else "—"
            avg_s = std_s = mn_s = mx_s = "—"

            if frames >= 2:
                gaps = [times[k+1]-times[k] for k in range(len(times)-1)
                        if times[k+1]-times[k] > 0]
                if gaps:
                    avg   = sum(gaps)/len(gaps)
                    std   = (sum((g-avg)**2 for g in gaps)/len(gaps))**0.5
                    avg_s = _fmt_period(avg)
                    std_s = _fmt_period(std)
                    mn_s  = _fmt_period(min(gaps))
                    mx_s  = _fmt_period(max(gaps))

            cells = (name, frames, pkts, drp_s, pct_s,
                     avg_s, std_s, mn_s, mx_s, ls)
            html.append("<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>")

        html.append("</table>")
        return "\n".join(html)

    def _export_html(self, path):
        """Write a single-file HTML report to *path*."""
        import datetime
        now, sid = self._report_header_info()

        # Graphs
        graph_sections = []
        for title, canvas in [
            ("Environment",    self.env_canvas),
            ("Short Interval", self.si_canvas),
            ("Ticks",          self.ticks_canvas),
            ("TWF",            self.twf_canvas),
        ]:
            b64 = self._fig_to_base64(canvas.figure)
            graph_sections.append(
                f"<h2>{title}</h2>\n"
                f'<img src="data:image/png;base64,{b64}" alt="{title}"/>'
            )

        import html as _html_mod

        # Latest Data log text
        log_text    = self.latest_text.get("1.0", tk.END)
        log_escaped = _html_mod.escape(log_text)

        fault_text    = self.notes_fault_text.get("1.0", tk.END).strip()
        findings_text = self.notes_findings_text.get("1.0", tk.END).strip()

        notes_sections = []
        for heading, text in [("Fault Description", fault_text),
                               ("Findings",          findings_text)]:
            if text:
                notes_sections.append(
                    f"<h2>{heading}</h2>\n"
                    f"<p style='white-space:pre-wrap'>{_html_mod.escape(text)}</p>"
                )

        body = "\n".join([
            f"<h1>{APP_TITLE}</h1>",
            f"<p><b>Generated:</b> {now} &nbsp;&nbsp; "
            f"<b>Version:</b> {APP_VERSION} ({APP_DATE})</p>",
            f"<p><b>Sensor Filter:</b> 0x{sid}</p>",
            *notes_sections,
            *graph_sections,
            "<h2>Configuration</h2>",
            self._config_html_table(),
            "<h2>Diagnostics — Period Statistics</h2>",
            self._diag_html_table(),
            "<h2>Latest Data Log</h2>",
            f"<pre>{log_escaped}</pre>",
        ])

        html_doc = (
            "<!DOCTYPE html>\n<html>\n<head>\n"
            f'<meta charset="utf-8">\n'
            f"<title>{APP_TITLE} Report</title>\n"
            f"<style>{self._HTML_CSS}</style>\n"
            "</head>\n<body>\n"
            f"{body}\n"
            "</body>\n</html>"
        )

        with open(path, "w", encoding="utf-8") as fh:
            fh.write(html_doc)

    # ── PDF export ────────────────────────────────────────────────────────────

    def _pdf_table_page(self, pdf, title, col_headers, rows):
        """Render a list of string rows as a matplotlib table page and add to pdf."""
        from matplotlib.figure import Figure as _Fig

        fig = _Fig(figsize=(11.69, 8.27))   # A4 landscape
        fig.patch.set_facecolor(DARK_BG)
        ax = fig.add_axes([0.02, 0.05, 0.96, 0.88])
        ax.axis("off")
        ax.set_title(title, color=ACCENT_CYAN, fontsize=13, fontweight="bold",
                     pad=10, loc="left")

        if not rows:
            ax.text(0.5, 0.5, "No data", ha="center", va="center",
                    color=TEXT_DIM, fontsize=11, transform=ax.transAxes)
        else:
            n_cols = len(col_headers)
            col_w  = [1.0 / n_cols] * n_cols
            tbl = ax.table(
                cellText=rows,
                colLabels=col_headers,
                cellLoc="left",
                loc="upper left",
                colWidths=col_w,
            )
            tbl.auto_set_font_size(False)
            tbl.set_fontsize(7)
            for (r, c), cell in tbl.get_celld().items():
                cell.set_edgecolor(BORDER_COL)
                if r == 0:
                    cell.set_facecolor(PANEL_BG)
                    cell.get_text().set_color(ACCENT_CYAN)
                    cell.get_text().set_fontweight("bold")
                else:
                    cell.set_facecolor(TREE_ROW_ODD if r % 2 else TREE_ROW_EVEN)
                    cell.get_text().set_color(TEXT_MAIN)

        pdf.savefig(fig, facecolor=DARK_BG)
        fig.clf()

    def _pdf_text_pages(self, pdf, title, text):
        """Split *text* into 60-line chunks and render each as a PDF page."""
        from matplotlib.figure import Figure as _Fig

        LINES_PER_PAGE = 60
        lines = text.splitlines()
        pages = [lines[i:i + LINES_PER_PAGE]
                 for i in range(0, max(len(lines), 1), LINES_PER_PAGE)]

        for page_idx, page_lines in enumerate(pages):
            fig = _Fig(figsize=(11.69, 8.27))
            fig.patch.set_facecolor(DARK_BG)
            ax  = fig.add_axes([0.02, 0.02, 0.96, 0.94])
            ax.axis("off")
            hdr = title if page_idx == 0 else f"{title}  (cont.)"
            ax.set_title(hdr, color=ACCENT_CYAN, fontsize=11, fontweight="bold",
                         pad=6, loc="left")
            content = "\n".join(page_lines)
            ax.text(0, 1, content, transform=ax.transAxes,
                    va="top", ha="left",
                    fontfamily="monospace", fontsize=6.5,
                    color=TEXT_MAIN, wrap=False)
            pdf.savefig(fig, facecolor=DARK_BG)
            fig.clf()

    def _export_pdf(self, path):
        """Write a multi-page PDF report to *path* using matplotlib PdfPages."""
        from matplotlib.backends.backend_pdf import PdfPages
        from matplotlib.figure import Figure as _Fig
        import datetime

        now, sid = self._report_header_info()

        with PdfPages(path) as pdf:

            # ── Cover page ────────────────────────────────────────────────────
            fig = _Fig(figsize=(8.27, 11.69))   # A4 portrait
            fig.patch.set_facecolor(DARK_BG)
            ax = fig.add_axes([0, 0, 1, 1])
            ax.axis("off")
            ax.text(0.5, 0.72, APP_TITLE,
                    ha="center", va="center", fontsize=26, fontweight="bold",
                    color=ACCENT_CYAN, transform=ax.transAxes)
            ax.text(0.5, 0.63, f"v{APP_VERSION}  ·  {APP_DATE}",
                    ha="center", va="center", fontsize=13, color=TEXT_DIM,
                    transform=ax.transAxes)
            ax.text(0.5, 0.54, f"Generated:  {now}",
                    ha="center", va="center", fontsize=12, color=TEXT_MAIN,
                    transform=ax.transAxes)
            ax.text(0.5, 0.46, f"Sensor:  0x{sid}",
                    ha="center", va="center", fontsize=14,
                    color=TEXT_MAIN, transform=ax.transAxes)
            pdf.savefig(fig, facecolor=DARK_BG)
            fig.clf()

            # ── Notes page (Fault Description + Findings) ─────────────────────
            fault_txt    = self.notes_fault_text.get("1.0", tk.END).strip()
            findings_txt = self.notes_findings_text.get("1.0", tk.END).strip()
            if fault_txt or findings_txt:
                fig_n = _Fig(figsize=(8.27, 11.69))   # A4 portrait
                fig_n.patch.set_facecolor(DARK_BG)
                ax_n = fig_n.add_axes([0.05, 0.05, 0.90, 0.90])
                ax_n.axis("off")
                y = 0.97
                for section_title, section_text in [
                    ("Fault Description", fault_txt),
                    ("Findings",          findings_txt),
                ]:
                    if not section_text:
                        continue
                    ax_n.text(0, y, section_title, transform=ax_n.transAxes,
                              va="top", ha="left", fontsize=13, fontweight="bold",
                              color=ACCENT_CYAN)
                    y -= 0.04
                    ax_n.text(0, y, section_text, transform=ax_n.transAxes,
                              va="top", ha="left", fontsize=10,
                              color=TEXT_MAIN, wrap=True,
                              fontfamily="Segoe UI")
                    # Estimate lines used (rough: 80 chars per line at this font size)
                    lines_used = max(1, len(section_text) // 80 + section_text.count("\n"))
                    y -= 0.025 * lines_used + 0.06
                pdf.savefig(fig_n, facecolor=DARK_BG)
                fig_n.clf()

            # ── Graph pages (one per canvas) ──────────────────────────────────
            for label, canvas in [
                ("Environment",    self.env_canvas),
                ("Short Interval", self.si_canvas),
                ("Ticks",          self.ticks_canvas),
                ("TWF",            self.twf_canvas),
            ]:
                fig2 = _Fig(figsize=(11.69, 8.27))
                fig2.patch.set_facecolor(DARK_BG)
                ax2 = fig2.add_axes([0, 0.95, 1, 0.05])
                ax2.axis("off")
                ax2.text(0.02, 0.5, label, color=ACCENT_CYAN,
                         fontsize=13, fontweight="bold",
                         va="center", transform=ax2.transAxes)
                # Render the live canvas figure into the new figure as an image
                from io import BytesIO
                buf = BytesIO()
                canvas.figure.savefig(buf, format="png", dpi=100,
                                       bbox_inches="tight",
                                       facecolor=canvas.figure.get_facecolor())
                buf.seek(0)
                import matplotlib.image as mpimg
                img = mpimg.imread(buf)
                img_ax = fig2.add_axes([0, 0, 1, 0.94])
                img_ax.imshow(img)
                img_ax.axis("off")
                pdf.savefig(fig2, facecolor=DARK_BG)
                fig2.clf()

            # ── Config table page ─────────────────────────────────────────────
            def _sort_key(item):
                (blk, k), _ = item
                names = CONFIG_MUX_TABLE.get(blk, [])
                try:    idx = names.index(k)
                except ValueError: idx = 999
                return (blk, idx)

            cfg_rows = []
            for (blk, key), val in sorted(self.config_latest.items(), key=_sort_key):
                if isinstance(val, tuple):
                    value, unit = val
                else:
                    value, unit = val, ""
                cfg_rows.append([str(blk), key, str(value), unit])

            self._pdf_table_page(
                pdf, "Configuration",
                ["Block", "Parameter", "Value", "Units"],
                cfg_rows,
            )

            # ── Diagnostics table page ────────────────────────────────────────
            diag_rows = []
            for name in FRAME_TYPES.values():
                entry = self.diag_stats.get(name)
                if not entry:
                    continue
                pkts   = entry["packets"]
                times  = list(entry["frame_times"])
                frames = len(times)
                exp    = entry.get("expected_total", 0)
                drp    = entry.get("dropped_total",  0)
                ls     = entry.get("last_seen", "")
                pct_s  = f"{100.0*(exp-drp)/exp:.1f}%" if exp > 0 else "—"
                drp_s  = str(drp) if exp > 0 else "—"
                avg_s  = std_s = mn_s = mx_s = "—"
                if frames >= 2:
                    gaps = [times[k+1]-times[k] for k in range(len(times)-1)
                            if times[k+1]-times[k] > 0]
                    if gaps:
                        avg   = sum(gaps)/len(gaps)
                        std   = (sum((g-avg)**2 for g in gaps)/len(gaps))**0.5
                        avg_s = _fmt_period(avg)
                        std_s = _fmt_period(std)
                        mn_s  = _fmt_period(min(gaps))
                        mx_s  = _fmt_period(max(gaps))
                diag_rows.append([name, str(frames), str(pkts), drp_s, pct_s,
                                   avg_s, std_s, mn_s, mx_s, ls])

            self._pdf_table_page(
                pdf, "Diagnostics — Period Statistics",
                ["Frame", "Frames", "Pkts", "Dropped", "Success%",
                 "Avg Period", "Std Dev", "Min", "Max", "Last Seen"],
                diag_rows,
            )

            # ── Latest Data log pages ─────────────────────────────────────────
            log_text = self.latest_text.get("1.0", tk.END)
            self._pdf_text_pages(pdf, "Latest Data Log", log_text)

    # =========================================================================
    # =========================================================================
    # STARTUP HISTORY LOAD  (chunked so the splash screen can update)
    # =========================================================================

    _HISTORY_CHUNK = 50      # log lines processed per Tkinter iteration

    def _start_history_load(self):
        """Show a progress splash and begin replaying existing log data."""

        if self.radio is not None:
            # Live from the kit: there is no history to replay.
            self._loading_history = False
            self.latest_text.insert(tk.END, "Receiving from %s\n\n" % self.radio.description)
            self._st_read_setup()
            self.root.after(RADIO_POLL_MS, self.poll_radio)
            return

        if not self.logfile or not os.path.exists(self.logfile):
            self._loading_history = False
            self.root.after(POLL_INTERVAL_MS, self.poll_log)
            return

        self._history_total  = max(1, os.path.getsize(self.logfile))
        self._history_file   = open(self.logfile, "r")

        first = self._history_file.readline()
        self.latest_text.insert(tk.END, f"Log Opened: {first}\n\n")

        # ── Splash window ────────────────────────────────────────────────────
        splash = tk.Toplevel(self.root)
        splash.title("RF Monitor — Loading")
        splash.resizable(False, False)
        splash.configure(bg=DARK_BG)

        # Centre over the main window
        self.root.update_idletasks()
        rx = self.root.winfo_x() + self.root.winfo_width()  // 2
        ry = self.root.winfo_y() + self.root.winfo_height() // 2
        splash.geometry(f"420x140+{rx - 210}+{ry - 70}")

        tk.Label(
            splash, text="Loading log file history…",
            bg=DARK_BG, fg=TEXT_MAIN, font=("Segoe UI", 11),
        ).pack(pady=(20, 4))

        self._splash_pct_var = tk.StringVar(value="0 %")
        tk.Label(
            splash, textvariable=self._splash_pct_var,
            bg=DARK_BG, fg=ACCENT_CYAN, font=("Segoe UI", 14, "bold"),
        ).pack(pady=(0, 8))

        self._splash_bar = ttk.Progressbar(
            splash, orient=tk.HORIZONTAL, length=380, mode="determinate",
        )
        self._splash_bar.pack(padx=20)

        self._splash = splash

        # Force the splash to fully paint before chunk processing begins
        splash.update()

        # Kick off chunk processing
        self.root.after(10, self._load_history_chunk)

    def _load_history_chunk(self):
        """Process one chunk of log lines then yield back to the event loop."""

        f = self._history_file

        for _ in range(self._HISTORY_CHUNK):
            line = f.readline()
            if not line:                          # EOF
                self._finish_history_load()
                return
            frame = parse_packet_line(line)
            if frame:
                self.process_frame(frame)

        # Update progress
        pos = f.tell()
        self.file_position = pos
        pct = int(100 * pos / self._history_total)
        self._splash_pct_var.set(f"{pct} %")
        self._splash_bar["value"] = pct

        # Schedule next chunk; 10 ms gap lets Tkinter repaint the progress bar
        self.root.after(10, self._load_history_chunk)

    def _finish_history_load(self):
        """Called when every existing log line has been processed."""

        self.file_position = self._history_file.tell()
        self._history_file.close()

        self._splash_pct_var.set("100 %")
        self._splash_bar["value"] = 100
        self._splash.update_idletasks()

        self._splash.destroy()

        # Lift all suppression and do one final render of every tab
        self._loading_history = False

        # Populate the Latest Data buffer and render with current display filter.
        # All frames (sensor-unfiltered) go into the buffer so toggling
        # Show All / Show Filtered later can re-render without re-reading the file.
        for frame in self._history_tail:
            self._latest_frame_buffer.append(frame)
        self._history_tail.clear()
        self._redisplay_latest()

        self._refresh_all_tabs()

        self.root.after(POLL_INTERVAL_MS, self.poll_log)

    # =========================================================================
    # LOG POLL  (live updates only — history is handled by _start_history_load)
    # =========================================================================

    def poll_log(self):

        try:

            if self.logfile and os.path.exists(self.logfile):

                with open(self.logfile, "r") as f:

                    f.seek(self.file_position)

                    lines = f.readlines()

                    self.file_position = f.tell()

                    for line in lines:

                        frame = parse_packet_line(line)

                        if frame:
                            self.process_frame(frame)

                    if lines:
                        self.update_diagnostics_tab()

        except Exception as e:

            print(e)

        self.root.after(POLL_INTERVAL_MS, self.poll_log)

    # =========================================================================
    # RADIO POLL  (live from the kit through the benchtools driver)
    # =========================================================================

    def poll_radio(self):
        """Take the packets the radio thread received and feed every page."""

        packets = self.radio.drain()

        for packet in packets:

            self._st_gui_add(packet)

            decoded = None

            if packet.ok:
                line = spirit_line(packet)
                self._live_lines.append(line)
                frame = parse_packet_line(line)
                if frame:
                    self.process_frame(frame)
                    decoded = {"sensor_id": frame.sensor_id, "type": frame.frame_name,
                               "frame_of": (frame.frame_num, frame.total_frames)}

            self._events_add(rf_event(packet, decoded))

        if packets:
            self.update_diagnostics_tab()

        if self.radio.error:
            self._events_add({"t": time.time(), "source": "RF", "level": "ERROR",
                              "text": "radio stopped: %s" % self.radio.error})
            self.radio.error = None
            return

        self.root.after(RADIO_POLL_MS, self.poll_radio)

    # =========================================================================
    # ST GUI TAB  (packets as ST's S2-LP DK GUI shows them)
    # =========================================================================

    def create_st_gui_tab(self):
        """ST's S2-LP DK GUI as it is laid out: the RF setup top left, the
        registers table on the right, received frames in hex bottom left."""

        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="ST GUI")

        outer = ttk.PanedWindow(tab, orient=tk.HORIZONTAL)
        outer.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        left = ttk.PanedWindow(outer, orient=tk.VERTICAL)
        outer.add(left, weight=3)

        # -- RF setup (top left) -----------------------------------------------
        setup = ttk.LabelFrame(left, text="RF setup")
        left.add(setup, weight=2)
        self.st_setup_var = tk.StringVar(
            value="Not connected to a kit" if self.radio is None else "Not read yet")
        ttk.Label(setup, textvariable=self.st_setup_var).pack(anchor=tk.W, padx=6, pady=(2, 4))
        self.st_setup = ttk.Treeview(setup, columns=("value",), show="tree headings", height=12)
        self.st_setup.heading("#0", text="Setting")
        self.st_setup.heading("value", text="Value")
        self.st_setup.column("#0", width=220, stretch=False)
        self.st_setup.column("value", width=320, stretch=True)
        vsb = ttk.Scrollbar(setup, orient=tk.VERTICAL, command=self.st_setup.yview)
        self.st_setup.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.st_setup.pack(fill=tk.BOTH, expand=True)

        # -- Received frames (bottom left) -------------------------------------
        frames = ttk.LabelFrame(left, text="Received frames")
        left.add(frames, weight=3)
        bar = ttk.Frame(frames)
        bar.pack(fill=tk.X, pady=(2, 4))
        self.st_count_var = tk.StringVar(value="Packets: 0")
        ttk.Label(bar, textvariable=self.st_count_var).pack(side=tk.LEFT, padx=8)
        self.st_paused = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Pause", variable=self.st_paused).pack(side=tk.LEFT, padx=8)
        self.st_follow = tk.BooleanVar(value=True)
        ttk.Checkbutton(bar, text="Follow", variable=self.st_follow).pack(side=tk.LEFT, padx=8)
        ttk.Button(bar, text="Clear", command=self._st_gui_clear).pack(side=tk.LEFT, padx=8)

        grid = ttk.Frame(frames)
        grid.pack(fill=tk.BOTH, expand=True)
        columns = ("time", "bytes", "rssi", "data")
        self.st_tree = ttk.Treeview(grid, columns=columns, show="headings")
        for column, heading, width, anchor in (
            ("time", "Timestamp", 100, tk.W),
            ("bytes", "Bytes", 55, tk.E),
            ("rssi", "RSSI (dBm)", 80, tk.E),
            ("data", "Data (hex)", 500, tk.W),
        ):
            self.st_tree.heading(column, text=heading)
            self.st_tree.column(column, width=width, anchor=anchor, stretch=column == "data")
        self.st_tree.tag_configure("lost", foreground="#ef5350")
        vsb = ttk.Scrollbar(grid, orient=tk.VERTICAL, command=self.st_tree.yview)
        hsb = ttk.Scrollbar(grid, orient=tk.HORIZONTAL, command=self.st_tree.xview)
        self.st_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.st_tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        grid.grid_rowconfigure(0, weight=1)
        grid.grid_columnconfigure(0, weight=1)

        # -- Registers table (right) -------------------------------------------
        regs = ttk.LabelFrame(outer, text="Registers table")
        outer.add(regs, weight=2)
        grid = ttk.Frame(regs)
        grid.pack(fill=tk.BOTH, expand=True)
        self.st_regs = ttk.Treeview(grid, columns=("register", "value", "default"),
                                    show="tree headings")
        self.st_regs.heading("#0", text="Address")
        self.st_regs.column("#0", width=90, stretch=False)
        for column, heading, width in (("register", "Register", 170), ("value", "Value", 70),
                                       ("default", "Default", 70)):
            self.st_regs.heading(column, text=heading)
            self.st_regs.column(column, width=width, anchor=tk.W, stretch=column == "register")
        self.st_regs.tag_configure("changed", foreground="#ef5350")
        vsb = ttk.Scrollbar(grid, orient=tk.VERTICAL, command=self.st_regs.yview)
        self.st_regs.configure(yscrollcommand=vsb.set)
        self.st_regs.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        grid.grid_rowconfigure(0, weight=1)
        grid.grid_columnconfigure(0, weight=1)

        bar = ttk.Frame(regs)
        bar.pack(fill=tk.X, pady=4)
        self.st_refresh_btn = ttk.Button(bar, text="Refresh", command=self._st_read_setup)
        self.st_refresh_btn.pack(side=tk.LEFT, padx=4)
        ttk.Button(bar, text="Expand", command=lambda: self._st_expand(True)).pack(
            side=tk.LEFT, padx=4)
        ttk.Button(bar, text="Collapse", command=lambda: self._st_expand(False)).pack(
            side=tk.LEFT, padx=4)
        self.st_export_btn = ttk.Button(bar, text="Export", command=self._st_export)
        self.st_export_btn.pack(side=tk.RIGHT, padx=4)
        if self.radio is None:
            self.st_refresh_btn.state(["disabled"])
        self.st_export_btn.state(["disabled"])

        # Registers get about 40 % of the width, as in ST's GUI, once it is known.
        def place_sash(_event=None):
            outer.unbind("<Map>")
            outer.after(50, lambda: outer.sashpos(0, int(outer.winfo_width() * 0.6)))
        outer.bind("<Map>", place_sash)

        self.st_packets = 0
        self._st_snapshot = None
        self._st_snapshot_result = None

    def _st_read_setup(self):
        """Read the RF setup and registers on a worker thread. Reception pauses
        while they are read: the receive loop and the read share the kit's port."""
        if self.radio is None:
            return
        import threading

        self.st_refresh_btn.state(["disabled"])
        self.st_setup_var.set("Reading... (reception paused)")

        def work():
            try:
                self._st_snapshot_result = ("ok", self.radio.snapshot())
            except Exception as error:                  # pylint: disable=broad-except
                self._st_snapshot_result = ("error", "%s: %s" % (type(error).__name__, error))

        threading.Thread(target=work, name="st-gui-read", daemon=True).start()
        self.root.after(100, self._st_wait_setup)

    def _st_wait_setup(self):
        if self._st_snapshot_result is None:
            self.root.after(100, self._st_wait_setup)
            return
        status, result = self._st_snapshot_result
        self._st_snapshot_result = None
        self.st_refresh_btn.state(["!disabled"])
        if status != "ok":
            self.st_setup_var.set("Read failed: %s" % result)
            self._events_add({"t": time.time(), "source": "RF", "level": "ERROR",
                              "text": "Reading the RF setup failed: %s" % result})
            return
        self._st_snapshot = result
        self.st_export_btn.state(["!disabled"])
        self.st_setup_var.set("Read at %s (reception paused %.1f s)"
                              % (time.strftime("%H:%M:%S"), result["paused_s"]))
        self._events_add({"t": time.time(), "source": "RF", "level": "INFO",
                          "text": "RF setup and registers read; reception paused %.1f s"
                                  % result["paused_s"]})

        self.st_setup.delete(*self.st_setup.get_children())
        sections = {}
        for section, label, value in rf_setup_rows(result):
            if section not in sections:
                sections[section] = self.st_setup.insert("", tk.END, text=section, open=True)
            self.st_setup.insert(sections[section], tk.END, text=label, values=(value,))

        self.st_regs.delete(*self.st_regs.get_children())
        for addr, name, value, default, fields, changed in register_rows(result["registers"]):
            tags = ("changed",) if changed else ()
            row = self.st_regs.insert("", tk.END, text=addr, values=(name, value, default),
                                      tags=tags)
            for field, field_value in fields:
                self.st_regs.insert(row, tk.END, text="", values=(field, field_value, ""),
                                    tags=tags)

    def _st_expand(self, open_):
        for row in self.st_regs.get_children():
            self.st_regs.item(row, open=open_)

    def _st_export(self):
        """Save the registers read as a register file the driver's --setup reads."""
        if not self._st_snapshot:
            return
        from tkinter import filedialog

        path = filedialog.asksaveasfilename(
            title="Export registers", defaultextension=".regs",
            filetypes=[("Register files", "*.regs"), ("All files", "*.*")])
        if path:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(regs_text(self._st_snapshot["registers"]))
            self.st_setup_var.set("Registers exported to %s" % path)

    def _st_gui_add(self, packet):
        self.st_packets += 1
        self.st_count_var.set("Packets: %d" % self.st_packets)
        if self.st_paused.get():
            return
        row = st_gui_row(packet)
        self.st_tree.insert("", tk.END, values=row, tags=("lost",) if not packet.ok else ())
        children = self.st_tree.get_children()
        if len(children) > ST_GUI_MAX_ROWS:
            self.st_tree.delete(*children[:len(children) - ST_GUI_MAX_ROWS])
        if self.st_follow.get():
            self.st_tree.yview_moveto(1.0)

    def _st_gui_clear(self):
        self.st_tree.delete(*self.st_tree.get_children())
        self.st_packets = 0
        self.st_count_var.set("Packets: 0")

    # =========================================================================
    # EVENTS TAB  (the whole bench, one colour per source)
    # =========================================================================

    def create_events_tab(self):
        """Events from every part of the bench, each source in its own colour."""

        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Events")

        bar = tk.Frame(tab, bg=DARK_BG)
        bar.pack(fill=tk.X, pady=5)

        self.events_paused = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Pause", variable=self.events_paused).pack(side=tk.RIGHT, padx=12)
        ttk.Button(bar, text="Clear", command=self._events_clear).pack(side=tk.RIGHT, padx=6)

        # One check box per source: the defaults now, and any other name a
        # specification or bench declared as it first appears (#126).
        self.events_bar = bar
        self.event_show = {}
        for source in SOURCE_ORDER:
            self._events_add_source(source)

        self.events_count_var = tk.StringVar(
            value="No event log" if self.event_tail is None else "Events: 0")
        ttk.Label(bar, textvariable=self.events_count_var).pack(side=tk.RIGHT, padx=8)

        frame = ttk.Frame(tab)
        frame.pack(fill=tk.BOTH, expand=True)
        self.events_text = tk.Text(
            frame, font=("Consolas", 10), wrap=tk.NONE, bg=PLOT_BG, fg=TEXT_MAIN,
            insertbackground=TEXT_MAIN, selectbackground=ACCENT_BLUE, relief="flat",
            borderwidth=0,
        )
        vsb = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self.events_text.yview)
        self.events_text.configure(yscrollcommand=vsb.set)
        self.events_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        for source in self.event_show:
            self.events_text.tag_configure(source, foreground=style_of(source)[1])
        self.events_text.tag_configure("error", background="#4a1a1a")
        self.events_text.configure(state=tk.DISABLED)

        self.events = deque(maxlen=EVENTS_MAX)

    def _events_add_source(self, source):
        """A check box for *source*, and its colour in the text once there is one."""
        label, colour = style_of(source)
        variable = tk.BooleanVar(value=True)
        self.event_show[source] = variable
        tk.Checkbutton(
            self.events_bar, text=label, variable=variable, command=self._events_redraw,
            bg=DARK_BG, fg=colour, selectcolor=PANEL_BG, activebackground=DARK_BG,
            activeforeground=colour, font=("Segoe UI", 10, "bold"),
        ).pack(side=tk.LEFT, padx=6)
        if getattr(self, "events_text", None) is not None:
            self.events_text.tag_configure(source, foreground=colour)

    def _events_line(self, record):
        when, source, label, text = event_row(record)
        tags = (source, "error") if record.get("level") in ("ERROR", "CRITICAL") else (source,)
        return "%-12s %-7s %s\n" % (when, label, text), tags, source

    def _events_add(self, record):
        self.events.append(record)
        self.events_count_var.set("Events: %d" % len(self.events))
        if self.events_paused.get():
            return
        line, tags, source = self._events_line(record)
        if source not in self.event_show:
            self._events_add_source(source)
        if not self.event_show[source].get():
            return
        self.events_text.configure(state=tk.NORMAL)
        self.events_text.insert(tk.END, line, tags)
        if int(self.events_text.index("end-1c").split(".")[0]) > EVENTS_MAX:
            self.events_text.delete("1.0", "2.0")
        self.events_text.configure(state=tk.DISABLED)
        self.events_text.see(tk.END)

    def _events_redraw(self):
        self.events_text.configure(state=tk.NORMAL)
        self.events_text.delete("1.0", tk.END)
        for record in self.events:
            line, tags, source = self._events_line(record)
            if source not in self.event_show:
                self._events_add_source(source)
            if self.event_show[source].get():
                self.events_text.insert(tk.END, line, tags)
        self.events_text.configure(state=tk.DISABLED)
        self.events_text.see(tk.END)

    def _events_clear(self):
        self.events.clear()
        self.events_count_var.set("Events: 0")
        self._events_redraw()

    # =========================================================================
    # PSU AND J-LINK TABS  (their panels, rebuilt from the event log)
    # =========================================================================

    def create_psu_tab(self):
        """The supply's front panel on top, its last ten commands below."""

        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="PSU")
        colour = SOURCE_STYLES["PSU"][1]

        panel = ttk.LabelFrame(tab, text="GPD-3303D")
        panel.pack(fill=tk.BOTH, expand=True, padx=6, pady=(6, 3))
        self.psu_ident_var = tk.StringVar(value="Nothing from the supply yet")
        ttk.Label(panel, textvariable=self.psu_ident_var).pack(anchor=tk.W, padx=8, pady=(4, 8))

        channels = ttk.Frame(panel)
        channels.pack(fill=tk.BOTH, expand=True)
        self.psu_vars = {}
        for column, channel in enumerate((1, 2)):
            box = tk.Frame(channels, bg=PANEL_BG, highlightthickness=1,
                           highlightbackground=BORDER_COL)
            box.grid(row=0, column=column, sticky="nsew", padx=8, pady=4)
            channels.grid_columnconfigure(column, weight=1)
            tk.Label(box, text="CH%d" % channel, bg=PANEL_BG, fg=colour,
                     font=("Segoe UI", 14, "bold")).grid(row=0, column=0, columnspan=2,
                                                         sticky=tk.W, padx=10, pady=(6, 0))
            mode = tk.StringVar(value="--")
            tk.Label(box, textvariable=mode, bg=PANEL_BG, fg=ACCENT_CYAN,
                     font=("Segoe UI", 14, "bold")).grid(row=0, column=2, sticky=tk.E, padx=10)
            vout, iout = tk.StringVar(value="--.--- V"), tk.StringVar(value="-.---- A")
            for row, var in ((1, vout), (2, iout)):
                tk.Label(box, textvariable=var, bg=PANEL_BG, fg=TEXT_MAIN,
                         font=("Consolas", 30, "bold")).grid(row=row, column=0, columnspan=3,
                                                             sticky=tk.E, padx=10)
            vset, iset = tk.StringVar(value="set -"), tk.StringVar(value="limit -")
            tk.Label(box, textvariable=vset, bg=PANEL_BG, fg=TEXT_DIM).grid(
                row=3, column=0, sticky=tk.W, padx=10, pady=(0, 8))
            tk.Label(box, textvariable=iset, bg=PANEL_BG, fg=TEXT_DIM).grid(
                row=3, column=2, sticky=tk.E, padx=10, pady=(0, 8))
            box.grid_columnconfigure(1, weight=1)
            self.psu_vars[channel] = {"mode": mode, "vout": vout, "iout": iout,
                                      "vset": vset, "iset": iset}

        state = ttk.Frame(panel)
        state.pack(fill=tk.X, padx=8, pady=6)
        self.psu_output_label = tk.Label(state, text="OUTPUT --", bg=PANEL_BG, fg=TEXT_DIM,
                                         font=("Segoe UI", 12, "bold"), padx=12, pady=4)
        self.psu_output_label.pack(side=tk.LEFT)
        self.psu_state_var = tk.StringVar(value="")
        ttk.Label(state, textvariable=self.psu_state_var).pack(side=tk.LEFT, padx=12)

        recent = ttk.LabelFrame(tab, text="Last %d commands" % PsuPanel.RECENT)
        recent.pack(fill=tk.BOTH, expand=True, padx=6, pady=(3, 6))
        self.psu_tree = ttk.Treeview(recent, columns=("time", "command", "reply"),
                                     show="headings", height=PsuPanel.RECENT)
        for column, heading, width in (("time", "Time", 110), ("command", "Command", 260),
                                       ("reply", "Reply", 600)):
            self.psu_tree.heading(column, text=heading)
            self.psu_tree.column(column, width=width, anchor=tk.W, stretch=column == "reply")
        self.psu_tree.tag_configure("psu", foreground=colour)
        self.psu_tree.pack(fill=tk.BOTH, expand=True)

    def _psu_redraw(self):
        panel = self.psu_panel

        def number(value, unit, digits):
            return "--" if value is None else "%.*f %s" % (digits, value, unit)

        self.psu_ident_var.set(panel.identity or "Supply not identified yet")
        for channel, var in self.psu_vars.items():
            values = panel.channels[channel]
            var["mode"].set(values["mode"] or "--")
            var["vout"].set(number(values["vout"], "V", 3))
            var["iout"].set(number(values["iout"], "A", 4))
            var["vset"].set("set %s" % number(values["vset"], "V", 3))
            var["iset"].set("limit %s" % number(values["iset"], "A", 3))
        if panel.output is None:
            self.psu_output_label.configure(text="OUTPUT --", fg=TEXT_DIM, bg=PANEL_BG)
        elif panel.output:
            self.psu_output_label.configure(text="OUTPUT ON", fg="#101418", bg="#81c784")
        else:
            self.psu_output_label.configure(text="OUTPUT OFF", fg=TEXT_MAIN, bg="#5d4037")
        parts = []
        if panel.tracking:
            parts.append("Tracking: %s" % panel.tracking)
        if panel.beep is not None:
            parts.append("Beep: %s" % ("on" if panel.beep else "off"))
        if panel.status_raw:
            parts.append("STATUS? %s" % panel.status_raw)
        if panel.problem:
            parts.append("Last problem: %s" % panel.problem)
        self.psu_state_var.set("    ".join(parts))
        self.psu_tree.delete(*self.psu_tree.get_children())
        for when, command, reply in panel.recent:
            self.psu_tree.insert("", tk.END, values=(event_row({"t": when})[0], command, reply),
                                 tags=("psu",))

    def create_jlink_tab(self):
        """The probe's state on top, its latest traffic and log below."""

        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="J-Link")

        panes = ttk.PanedWindow(tab, orient=tk.VERTICAL)
        panes.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        state = ttk.LabelFrame(panes, text="J-Link state")
        panes.add(state, weight=1)
        self.jlink_state = ttk.Treeview(state, columns=("value",), show="tree", height=13)
        self.jlink_state.column("#0", width=180, stretch=False)
        self.jlink_state.column("value", width=900, stretch=True)
        self.jlink_state.tag_configure("problem", foreground="#ef5350")
        self.jlink_state.pack(fill=tk.BOTH, expand=True)

        log = ttk.LabelFrame(panes, text="Comms and log")
        panes.add(log, weight=1)
        bar = ttk.Frame(log)
        bar.pack(fill=tk.X, pady=(2, 4))
        self.jlink_follow = tk.BooleanVar(value=True)
        ttk.Checkbutton(bar, text="Follow", variable=self.jlink_follow).pack(side=tk.LEFT, padx=8)
        ttk.Label(bar, text="commands >>, console, async, RTT, probe reports").pack(
            side=tk.LEFT, padx=8)
        frame = ttk.Frame(log)
        frame.pack(fill=tk.BOTH, expand=True)
        self.jlink_text = tk.Text(frame, bg=DARK_BG, fg=TEXT_MAIN, font=("Consolas", 10),
                                  wrap=tk.NONE, state=tk.DISABLED, borderwidth=0)
        for kind, colour in (("command", SOURCE_STYLES["JLINK"][1]), ("console", TEXT_MAIN),
                             ("async", ACCENT_CYAN), ("rtt", "#fff176"),
                             ("info", TEXT_DIM), ("problem", "#ef5350")):
            self.jlink_text.tag_configure(kind, foreground=colour)
        vsb = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self.jlink_text.yview)
        self.jlink_text.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.jlink_text.pack(fill=tk.BOTH, expand=True)
        self._jlink_shown = 0

    def _jlink_redraw(self, new_records):
        self.jlink_state.delete(*self.jlink_state.get_children())
        for label, value in self.jlink_panel.rows():
            tags = ("problem",) if label == "Last problem" and value != "-" else ()
            if label == "Verify" and value.startswith("MISMATCH"):
                tags = ("problem",)
            self.jlink_state.insert("", tk.END, text=label, values=(value,), tags=tags)
        if not new_records:
            return
        self.jlink_text.configure(state=tk.NORMAL)
        for when, kind, text in new_records:
            self.jlink_text.insert(tk.END, "%s  %s\n" % (event_row({"t": when})[0], text), kind)
        excess = int(self.jlink_text.index("end-1c").split(".")[0]) - JlinkPanel.RECENT
        if excess > 0:
            self.jlink_text.delete("1.0", "%d.0" % (excess + 1))
        self.jlink_text.configure(state=tk.DISABLED)
        if self.jlink_follow.get():
            self.jlink_text.see(tk.END)

    def _panels_feed(self, records):
        """Give the event log's supply and probe records to their panels."""
        psu = jlink = False
        new_jlink = []
        for record in records:
            if self.psu_panel.feed(record):
                psu = True
            elif self.jlink_panel.feed(record):
                jlink = True
                new_jlink.append(self.jlink_panel.recent[-1])
        if psu:
            self._psu_redraw()
        if jlink:
            self._jlink_redraw(new_jlink[-JlinkPanel.RECENT:])

    def poll_events(self):
        """Follow the bench event log."""
        try:
            records = self.event_tail.read()
            for record in records:
                # The radio this monitor owns reports its frames itself; the
                # log's S2-LP lines are the command traffic, kept as RF too.
                self._events_add(record)
            self._panels_feed(records)
        except OSError as error:
            print(error)
        self.root.after(EVENT_POLL_MS, self.poll_events)

    # =========================================================================
    # PROCESS FRAME
    # =========================================================================

    def process_frame(self, frame):

        if self.paused:

            self.paused_frames.append(frame)

            return

        # Compute absolute time, handling midnight rollover for multi-day logs.
        # Must run for every frame (before the sensor filter) so the offset
        # accumulates correctly even during gaps of non-matching sensor traffic.
        _t_raw = _parse_time_s(frame.time_string)
        if self._prev_raw_time_s >= 0 and _t_raw < self._prev_raw_time_s - 3600:
            self._day_offset += 86400.0
        self._prev_raw_time_s = _t_raw
        frame.abs_time_s = _t_raw + self._day_offset

        # Register the sensor ID in the dropdown (never changes the active filter)
        if frame.sensor_id:
            self._register_sensor_id(frame.sensor_id)

        # Sync tab tracking — every CMD/RESPONSE frame, unfiltered by the
        # Sensor ID filter and regardless of history-load state, so the Sync
        # tab reflects whichever sensors are actually mid-sync as soon as the
        # splash closes (see create_sync_tab() docstring).
        if frame.frame_name in ("CMD", "RESPONSE"):
            self._update_sync_state(frame)

        # During the initial history load all rendering is suppressed so the
        # splash progress bar runs at full speed.  Data is accumulated into the
        # history deques and buffers normally; every tab gets one final render
        # in _finish_history_load once the splash closes.
        if self._loading_history:
            # Keep a rolling window of the most recent frames so Latest Data
            # can show the tail of the log after the splash closes.
            self._history_tail.append(frame)

        else:
            # Accumulate ALL frames (sensor-unfiltered) so _redisplay_latest()
            # can re-render with either Show All or Show Filtered at any time.
            self._latest_frame_buffer.append(frame)

            if self.latest_filtered_only.get():

                if self.sensor_matches_filter(frame):
                    self.display_latest_frame(frame)

            else:

                self.display_latest_frame(frame)

        if not self.sensor_matches_filter(frame):
            return

        # Diagnostics stats — filtered sensor only
        self._update_diag_stats(frame)

        if frame.frame_name == "ALIVE":

            self.update_environment(frame)
            self.update_short_interval_data(frame)
            self.update_ticks_data(frame)

        elif frame.frame_name == "TWF":

            self.process_twf_frame(frame)
            # TWF packets carry temperature, battery, and typed SI data
            self.update_environment(frame)
            self.update_short_interval_data(frame)

        elif frame.frame_name == "VERSION":

            self.latest_version_frame = frame
            # VERSION packets carry temperature and battery
            self.update_environment(frame)

        elif frame.frame_name == "CONFIG":

            self.update_config(frame)

    # =========================================================================
    # DISPLAY LATEST
    # =========================================================================

    # Column widths for the aligned payload table
    # _RAW_W is sized for exactly 7 bytes: "XX XX XX XX XX XX XX" = 20 chars.
    # Fields with fewer bytes are left-padded to the same width so the
    # decoded-value column stays aligned across all field types.
    _NAME_W = 30
    _RAW_W  = 20

    def _tx(self, text, tag=None):
        """Insert text with optional tag using the atomic form to preserve colour."""
        if tag:
            self.latest_text.insert(tk.END, text, (tag,))
        else:
            self.latest_text.insert(tk.END, text)

    def _field(self, name, raw_hex, decoded_str):
        """Insert one aligned payload field line."""
        self.latest_text.insert(
            tk.END,
            f"  {name:<{self._NAME_W}}: "
            f"{raw_hex:<{self._RAW_W}}  "
            f"{decoded_str}\n"
        )

    @staticmethod
    def _raw_hex(raw_bytes, offset, size):
        """
        Return a hex string for `size` bytes starting at `offset`.

        Width is always exactly _RAW_W (20) characters when padded by _field:
          ≤ 7 bytes  →  "XX XX XX XX XX XX XX"   (left-padded by _field to 20)
          > 7 bytes  →  "XX XX XX .. XX XX XX"   (first 3 + '..' + last 3 = 20 chars)
        """
        end = offset + size
        if end > len(raw_bytes):
            return "?"
        data = raw_bytes[offset:end]
        if len(data) > 7:
            first = " ".join(f"{b:02X}" for b in data[:3])
            last  = " ".join(f"{b:02X}" for b in data[-3:])
            return f"{first} .. {last}"
        return " ".join(f"{b:02X}" for b in data)

    @staticmethod
    def _fmt_enable(value):
        if value == 1:
            return "Enabled"
        if value == 0:
            return "Disabled"
        return str(value)

    def display_latest_frame(self, frame):

        r = frame.raw_bytes

        prod = PROD_ID_TABLE.get(frame.prod_id, f"Unknown ({frame.prod_id})")

        rf   = RF_CAP_TABLE.get(frame.rf_cap,   f"Unknown ({frame.rf_cap})")

        # ── Title line (highlighted by frame type) ──────────────────────────
        title_tag = f"frame_{frame.frame_name.lower()}"
        self._tx(
            f"  Time: {frame.time_string}    "
            f"Sensor: 0x{frame.sensor_id}    "
            f"Frame: {frame.frame_name}    "
            f"RSSI: {frame.rssi} dBm  ",
            title_tag
        )
        self._tx("\n")

        # ── Raw bytes line (coloured) ────────────────────────────────────────
        self._tx(f"Raw ({frame.packet_length} bytes):  ")

        self._tx(
            " ".join(f"{x:02X}" for x in r[0:7]),
            "header_blue"
        )
        self._tx(" ")
        self._tx(f"{r[7]:02X}", "header_green")

        counter = HEADER_SIZE + frame.permute_shift

        if frame.permute_shift and len(r) > PERMUTE_CONTROL_OFFSET:
            self._tx(" ")
            self._tx(f"{r[PERMUTE_CONTROL_OFFSET]:02X}", "header_green")

        if len(r) > counter:
            self._tx(" ")
            self._tx(f"{r[counter]:02X}", "counter_orange")

        if len(r) > counter + 1:
            self._tx(" " + " ".join(f"{x:02X}" for x in r[counter + 1:]))

        self._tx("\n")

        # ── Packet Header ───────────────────────────────────────────────────
        self._tx("Packet Header:\n", "section_hdr")

        self._field(
            "Sensor ID",
            f"{r[0]:02X} {r[1]:02X} {r[2]:02X}",
            f"0x{frame.sensor_id}"
        )
        self._field(
            "Product",
            f"{r[3]:02X}",
            prod
        )
        self._field(
            "RF Capability",
            f"{r[4]:02X}",
            f"RF02 (Issue {frame.rf_cap})"
        )
        self._field(
            "HW Cap / Frame Vers",
            f"{r[5]:02X}",
            f"HW={frame.hw_cap}  Frame Vers={frame.frame_version}"
        )
        self._field(
            "FW Capability",
            f"{r[6]:02X}",
            str(frame.fw_cap)
        )
        if frame.permute_control is not None:
            self._field(
                "Permute Control",
                f"{frame.permute_control:02X}",
                f"Method={PERMUTE_ENUM.get(frame.permute_method, '?')}"
            )
        if len(r) > counter:
            self._field(
                "Frame Counter",
                f"{r[counter]:02X}",
                f"{frame.frame_num} of {frame.total_frames}"
            )

        # ── Payload ─────────────────────────────────────────────────────────
        if frame.decoded:

            self._tx("Payload:\n", "section_hdr")

            self._insert_payload(frame)

        self._tx("─" * 110 + "\n\n", "separator")

        self.latest_text.see(tk.END)

    def _insert_payload(self, frame):

        r = frame.raw_bytes

        if frame.frame_name == "ALIVE":

            for name, offset, size in CONTENT_TABLE["ALIVE"]:

                value = frame.decoded.get(name)

                if value is None:
                    continue

                raw_hex = self._raw_hex(r, offset, size)

                if name == "TEMPERATURE":
                    decoded = f"{value} °C"

                elif name == "VBATT":
                    decoded = f"{value} V"

                elif name == "TICK_COUNT_SHORT":
                    # value is an int here; elapsed time
                    elapsed = format_elapsed_time(value * 60)
                    decoded = f"{value} ticks ({elapsed})"

                elif name in ("SI_FACTOR", "ALIVE_STATUS"):
                    # already decoded to a descriptive string in _decode_alive
                    decoded = str(value)

                elif "Enable" in name:
                    decoded = self._fmt_enable(value)

                else:
                    unit = ALIVE_UNITS.get(name, "")
                    decoded = f"{value} {unit}".rstrip()

                self._field(name, raw_hex, decoded)

        elif frame.frame_name == "CONFIG":

            control = frame.decoded.get("Permute Control")

            if control is not None:
                self._field("Permute Control",
                            self._raw_hex(r, PERMUTE_CONTROL_OFFSET, 1),
                            control[0])

            # The slot offsets already include the Permute Control shift
            for _slot, _position, name, offset in frame.config_slots:

                val = frame.decoded.get(name)

                if val is None:
                    continue

                raw_hex = self._raw_hex(r, offset, 2)

                value, unit = val if isinstance(val, tuple) else (val, "")

                if "Enable" in name:
                    decoded = self._fmt_enable(value)
                elif unit:
                    decoded = f"{value} {unit}"
                else:
                    decoded = str(value)

                self._field(name, raw_hex, decoded)

        elif frame.frame_name == "VERSION":

            # Fields in display order with their (offset, size) in raw_bytes
            version_fields = [
                ("SHA",              9,  7),
                ("FW Version",      16, 57),
                ("Reset Reason",    73,  4),
                ("Battery Voltage", 77,  1),
                ("PCB Version",     78,  1),
                ("Temperature",     79,  2),
                ("Ticks Since Reset", 81, 4),
            ]

            for name, offset, size in version_fields:

                value = frame.decoded.get(name)

                if value is None:
                    continue

                raw_hex = self._raw_hex(r, offset, size)

                self._field(name, raw_hex, str(value))

        elif frame.frame_name == "TWF":

            meta = frame.twf_meta or {}
            si_type        = meta.get("si_type", -1)
            si_factor_bits = meta.get("si_factor_bits", 0)
            full_scale_g   = 8 << si_factor_bits
            counts_per_g   = 32767.0 / full_scale_g

            _SI_LABEL = {
                0: "Acc RMS",
                1: "Vel RSS",
                2: "PK2PK",
                3: "Magnetometer",
                4: "Magnetometer",
            }
            si_suffix = _SI_LABEL.get(si_type, "")

            def _fmt_si(raw_val):
                """Return fixed-width decimal + converted value so decimal points align.

                Layout (decoded column):
                  col 0-4  : raw integer,  right-justified in 5 chars
                  col 5-6  : two spaces
                  col 7-13 : converted value, right-justified (decimal always at col 12)
                  col 14+  : unit string
                """
                if si_type in (0, 2):           # ACC_RMS, PK2PK → mg
                    return f"{raw_val:5d}  {raw_val * 1000.0 / counts_per_g:9.1f} mg"
                elif si_type == 1:              # VEL_RSS → mm/s (sensor scales ×100 before tx)
                    return f"{raw_val:5d}  {raw_val * 1000.0 / counts_per_g / 100.0:11.3f} mm/s"
                else:                           # MAG — raw counts, no calibration
                    return f"{raw_val:5d}"

            # (display_name, decoded_key, byte_offset, byte_size)
            # decoded_key=None → show raw bytes only, no decoded text
            twf_fields = [
                ("Temperature",     "Temperature",    9,  2),
                ("Battery Voltage", "Battery Voltage",11,  1),
                ("TWF Param",       "TWF Param",      12,  2),
                ("Sample ODR",      "Sample ODR",     14,  2),
                ("Packet",          "Packet",         16,  4),
                ("Ticks",           "Ticks",          20,  2),
                (f"SI X {si_suffix}".strip(), "SI X", 22,  2),
                (f"SI Y {si_suffix}".strip(), "SI Y", 24,  2),
                (f"SI Z {si_suffix}".strip(), "SI Z", 26,  2),
                ("LI Data",         None,             28, 64),
            ]

            for disp_name, decoded_key, offset, size in twf_fields:

                raw_hex = self._raw_hex(r, offset, size)

                if decoded_key is None:
                    self._field(disp_name, raw_hex, "")
                    continue

                value = frame.decoded.get(decoded_key)
                if value is None:
                    continue

                # Convert SI X/Y/Z raw integers to physical units
                if decoded_key in ("SI X", "SI Y", "SI Z") and isinstance(value, int):
                    self._field(disp_name, raw_hex, _fmt_si(value))
                else:
                    self._field(disp_name, raw_hex, str(value))

        elif frame.frame_name == "CMD":

            raw_hex = self._raw_hex(r, CMD_SENSOR_ID_OFFSET, 3)
            self._field("CMD_SENSOR_ID", raw_hex, frame.decoded.get("CMD_SENSOR_ID", "?"))

            raw_hex = self._raw_hex(r, CMD_PARAM_OFFSET, 2)
            self._field("CMD_PARAM", raw_hex, frame.decoded.get("CMD_PARAM", "?"))

            raw_hex = self._raw_hex(r, CMD_RETRY_OFFSET, 1)
            self._field("CMD_RETRY", raw_hex, str(frame.decoded.get("CMD_RETRY", "?")))

        elif frame.frame_name == "RESPONSE":

            raw_hex = self._raw_hex(r, CMD_SENSOR_ID_OFFSET, 3)
            self._field("Echoed Sensor ID", raw_hex, frame.decoded.get("Echoed Sensor ID", "?"))

            raw_hex = self._raw_hex(r, RESPONSE_PARAM_OFFSET, 2)
            self._field("RESPONSE_PARAM", raw_hex, frame.decoded.get("RESPONSE_PARAM", "?"))

            if "Timer" in frame.decoded:

                raw_hex = self._raw_hex(r, RESPONSE_PAYLOAD_OFFSET, 4)
                self._field("Timer", raw_hex, frame.decoded["Timer"])

            elif "Config Pairs" in frame.decoded:

                payload_len = max(0, len(r) - RESPONSE_PAYLOAD_OFFSET)
                raw_hex = self._raw_hex(r, RESPONSE_PAYLOAD_OFFSET, payload_len)
                self._field("Config Pairs", raw_hex, frame.decoded["Config Pairs"])

        else:

            for key, value in frame.decoded.items():

                self._field(key, "", str(value))

    # =========================================================================
    # ENVIRONMENT
    # =========================================================================

    def update_environment(self, frame):

        t = frame.abs_time_s

        if "TEMPERATURE" in frame.decoded:
            self.temperature_history.append(frame.decoded["TEMPERATURE"])
            self.temp_time_history.append(t)

        if "VBATT" in frame.decoded:
            self.battery_history.append(frame.decoded["VBATT"])
            self.batt_time_history.append(t)

        if not self._loading_history:
            self.update_environment_graphs()

    def update_environment_graphs(self):

        from matplotlib.ticker import FuncFormatter
        time_fmt = FuncFormatter(lambda x, _: _fmt_time_s(x))

        t_temp = list(self.temp_time_history)
        t_batt = list(self.batt_time_history)

        self.temp_line.set_data(t_temp, list(self.temperature_history))
        self.batt_line.set_data(t_batt, list(self.battery_history))

        # Hide cursors before relim to avoid distorting axis limits
        self.env_temp_cursor.set_visible(False)
        self.env_batt_cursor.set_visible(False)

        for ax, t_data in [(self.temp_ax, t_temp), (self.batt_ax, t_batt)]:
            ax.relim(); ax.autoscale_view()
            ax.xaxis.set_major_formatter(time_fmt)
            for lbl in ax.get_xticklabels():
                lbl.set_rotation(30); lbl.set_ha("right"); lbl.set_fontsize(8)

        # Apply view window if set
        if self.env_x_range:
            for ax in (self.temp_ax, self.batt_ax):
                ax.set_xlim(*self.env_x_range)

        self._refresh_env_cursor()
        self.env_canvas.draw()

    # =========================================================================
    # SHORT INTERVAL
    # =========================================================================

    def update_short_interval_data(self, frame):

        t = frame.abs_time_s

        # Track latest SI scale factor for right-hand axis conversion.
        # Both ALIVE and TWF now store this under "_SI_FACTOR_BITS".
        sf = frame.decoded.get("_SI_FACTOR_BITS")
        if sf is not None:
            self.si_factor_bits_latest = sf

        # ── ALIVE-style SI data: separate key per axis per type ──────────
        for axis in ["X", "Y", "Z"]:

            acc = frame.decoded.get(f"ACC_RMS_{axis}")
            vel = frame.decoded.get(f"VEL_RSS_{axis}")
            pk  = frame.decoded.get(f"ACC_P2P_{axis}")

            if acc is not None:
                self.acc_history[axis].append(acc)
                self.acc_time_history[axis].append(t)

            if vel is not None:
                self.vel_history[axis].append(vel)
                self.vel_time_history[axis].append(t)

            if pk is not None:
                self.pk_history[axis].append(pk)
                self.pk_time_history[axis].append(t)

        # ── TWF-style SI data: "SI X/Y/Z" typed by twf_meta["si_type"] ──
        meta = frame.twf_meta
        if meta:
            si_type = meta.get("si_type", -1)
            _axis_keys = [("X", "SI X"), ("Y", "SI Y"), ("Z", "SI Z")]
            for axis, key in _axis_keys:
                val = frame.decoded.get(key)
                if val is None:
                    continue
                if si_type == 0:          # ACC_RMS
                    self.acc_history[axis].append(val)
                    self.acc_time_history[axis].append(t)
                elif si_type == 1:        # VEL_RSS
                    self.vel_history[axis].append(val)
                    self.vel_time_history[axis].append(t)
                elif si_type == 2:        # ACC_P2P / PK2PK
                    self.pk_history[axis].append(val)
                    self.pk_time_history[axis].append(t)
                elif si_type == 3:        # MAG_FREQ
                    self.mag_freq_history[axis].append(val)
                    self.mag_freq_time_history[axis].append(t)
                elif si_type == 4:        # MAG_AMP
                    self.mag_amp_history[axis].append(val)
                    self.mag_amp_time_history[axis].append(t)

        if not self._loading_history:
            self.update_short_interval()

    def update_short_interval(self):

        from matplotlib.ticker import FuncFormatter
        time_fmt = FuncFormatter(lambda x, _: _fmt_time_s(x))

        axis = self.axis_selection.get()
        sf   = self.si_factor_bits_latest
        fsg  = 8 << sf                          # full scale g (8/16/32/64)
        cpg  = 32767.0 / fsg                    # counts per g

        acc      = list(self.acc_history[axis])
        vel      = list(self.vel_history[axis])
        pk       = list(self.pk_history[axis])
        mag_freq = list(self.mag_freq_history[axis])
        mag_amp  = list(self.mag_amp_history[axis])

        # Each series carries its own independent timestamp list — same approach
        # as the environment graphs.  Values and timestamps are always appended
        # together so lengths are always equal; no fallback needed.
        t_acc = list(self.acc_time_history[axis])
        t_vel = list(self.vel_time_history[axis])
        t_pk  = list(self.pk_time_history[axis])
        t_mf  = list(self.mag_freq_time_history[axis])
        t_ma  = list(self.mag_amp_time_history[axis])

        self.acc_line.set_data(t_acc, acc)
        self.vel_line.set_data(t_vel, vel)
        self.pk_line.set_data( t_pk,  pk)
        self.mag_freq_line.set_data(t_mf, mag_freq)
        self.mag_amp_line.set_data( t_ma, mag_amp)

        self.acc_ax.set_title(f"Acceleration RMS ({axis})")
        self.vel_ax.set_title(f"Velocity RMS ({axis})")
        self.pk_ax.set_title( f"Peak To Peak ({axis})")
        self.mag_ax.set_title(f"Magnetometer ({axis})")

        # Hide cursors before relim so their dummy xdata=[0,0] doesn't distort
        # the axis limits, then restore visibility via _refresh_si_cursor.
        for c in self.si_cursors:
            c.set_visible(False)

        for ax in [self.acc_ax, self.vel_ax, self.pk_ax, self.mag_ax]:
            ax.relim(); ax.autoscale_view()
            ax.xaxis.set_major_formatter(time_fmt)
            for lbl in ax.get_xticklabels():
                lbl.set_rotation(30); lbl.set_ha("right"); lbl.set_fontsize(8)

        if self.si_x_range:
            for ax in (self.acc_ax, self.vel_ax, self.pk_ax, self.mag_ax):
                ax.set_xlim(*self.si_x_range)

        # Sync right-hand conversion axes
        def _sync(ax_l, ax_r, factor, offset=0.0):
            lo, hi = ax_l.get_ylim()
            ax_r.set_ylim(lo * factor + offset, hi * factor + offset)

        mg_factor   = 1000.0 / cpg
        mms_factor  = 10.0   / cpg        # ×1000/cpg/100
        _sync(self.acc_ax, self.acc_ax_r, mg_factor)
        _sync(self.vel_ax, self.vel_ax_r, mms_factor)
        _sync(self.pk_ax,  self.pk_ax_r,  mg_factor)
        _sync(self.mag_ax, self.mag_ax_r, 1.0)

        # Update right-axis labels to reflect current scale
        self.acc_ax_r.set_ylabel(f"mg  (±{fsg}g scale)", color=TEXT_DIM, fontsize=8)
        self.vel_ax_r.set_ylabel("mm/s",                  color=TEXT_DIM, fontsize=8)
        self.pk_ax_r.set_ylabel( f"mg  (±{fsg}g scale)", color=TEXT_DIM, fontsize=8)

        self._refresh_si_cursor()
        self.si_canvas.draw()

    # =========================================================================
    # ENVIRONMENT CURSOR & ZOOM
    # =========================================================================

    def _env_cursor_click(self, event):
        if event.inaxes in (self.temp_ax, self.batt_ax) and event.xdata is not None:
            self.env_cursor_t = event.xdata
            self._refresh_env_cursor()
            self.env_canvas.draw_idle()

    def _env_cursor_step(self, steps):
        t_data = list(self.temp_time_history)
        if not t_data:
            return
        if self.env_cursor_t is None:
            idx = len(t_data) - 1
        else:
            dists = [abs(t - self.env_cursor_t) for t in t_data]
            idx   = dists.index(min(dists))
        idx = max(0, min(len(t_data) - 1, idx + steps))
        self.env_cursor_t = t_data[idx]
        self._refresh_env_cursor()
        self.env_canvas.draw_idle()

    def _env_zoom(self, factor):
        t_data = list(self.temp_time_history)
        if not t_data:
            return
        centre = self.env_cursor_t if self.env_cursor_t is not None else t_data[-1]
        lo, hi = self.temp_ax.get_xlim()
        span   = (hi - lo) * factor / 2
        self.env_x_range = (centre - span, centre + span)
        for ax in (self.temp_ax, self.batt_ax):
            ax.set_xlim(*self.env_x_range)
        self.env_canvas.draw_idle()

    def _env_zoom_reset(self):
        self.env_x_range = None
        for ax in (self.temp_ax, self.batt_ax):
            ax.autoscale_view()
        self._refresh_env_cursor()
        self.env_canvas.draw()

    def _refresh_env_cursor(self):
        t_temp = list(self.temp_time_history)
        t_batt = list(self.batt_time_history)

        def _nearest(t_list, val_list, t_cur):
            if not t_list or t_cur is None:
                return None, None
            dists = [abs(t - t_cur) for t in t_list]
            i     = dists.index(min(dists))
            return t_list[i], list(val_list)[i]

        t = self.env_cursor_t
        _t, temp_val = _nearest(t_temp, self.temperature_history, t)
        _t, batt_val = _nearest(t_batt, self.battery_history,     t)

        for cur, ax, t_list in [(self.env_temp_cursor, self.temp_ax, t_temp),
                                 (self.env_batt_cursor, self.batt_ax, t_batt)]:
            if t_list and t is not None:
                cur.set_xdata([t, t])
                cur.set_visible(True)
            else:
                cur.set_visible(False)

        parts = [f"t = {_fmt_time_s(t)}"]
        if temp_val is not None:
            parts.append(f"Temp: {temp_val:.1f} °C  ({temp_val*1.8+32:.1f} °F)")
        if batt_val is not None:
            parts.append(f"Batt: {batt_val:.3f} V  ({batt_val*1000:.0f} mV)")
        self.env_cursor_var.set("  |  ".join(parts))

    # =========================================================================
    # SI CURSOR & ZOOM
    # =========================================================================

    def _si_cursor_click(self, event):
        si_axes = (self.acc_ax, self.vel_ax, self.pk_ax, self.mag_ax)
        if event.inaxes in si_axes and event.xdata is not None:
            self.si_cursor_t = event.xdata
            self._refresh_si_cursor()
            self.si_canvas.draw_idle()

    def _si_cursor_step(self, steps):
        axis   = self.axis_selection.get()
        t_data = list(self.si_time_history[axis])
        if not t_data:
            return
        if self.si_cursor_t is None:
            idx = len(t_data) - 1
        else:
            dists = [abs(t - self.si_cursor_t) for t in t_data]
            idx   = dists.index(min(dists))
        idx = max(0, min(len(t_data) - 1, idx + steps))
        self.si_cursor_t = t_data[idx]
        self._refresh_si_cursor()
        self.si_canvas.draw_idle()

    def _si_zoom(self, factor):
        axis   = self.axis_selection.get()
        t_data = list(self.si_time_history[axis])
        if not t_data:
            return
        centre = self.si_cursor_t if self.si_cursor_t is not None else t_data[-1]
        lo, hi = self.acc_ax.get_xlim()
        span   = (hi - lo) * factor / 2
        self.si_x_range = (centre - span, centre + span)
        for ax in (self.acc_ax, self.vel_ax, self.pk_ax, self.mag_ax):
            ax.set_xlim(*self.si_x_range)
        self.si_canvas.draw_idle()

    def _si_zoom_reset(self):
        self.si_x_range = None
        for ax in (self.acc_ax, self.vel_ax, self.pk_ax, self.mag_ax):
            ax.autoscale_view()
        self._refresh_si_cursor()
        self.si_canvas.draw()

    def _refresh_si_cursor(self):
        axis = self.axis_selection.get()
        t    = self.si_cursor_t
        sf   = self.si_factor_bits_latest
        fsg  = 8 << sf
        cpg  = 32767.0 / fsg

        def _nearest(t_list, val_list, t_cur):
            t_list = list(t_list); val_list = list(val_list)
            if not t_list or t_cur is None:
                return None
            dists = [abs(tv - t_cur) for tv in t_list]
            return val_list[dists.index(min(dists))]

        t_acc = list(self.acc_time_history[axis])
        t_vel = list(self.vel_time_history[axis])
        t_pk  = list(self.pk_time_history[axis])
        t_mf  = list(self.mag_freq_time_history[axis])
        t_ma  = list(self.mag_amp_time_history[axis])

        acc_v = _nearest(t_acc, self.acc_history[axis], t)
        vel_v = _nearest(t_vel, self.vel_history[axis], t)
        pk_v  = _nearest(t_pk,  self.pk_history[axis],  t)
        mf_v  = _nearest(t_mf,  self.mag_freq_history[axis], t)
        ma_v  = _nearest(t_ma,  self.mag_amp_history[axis],  t)

        # Move cursor lines on each subplot — each uses its own time axis
        t_mag = t_mf or t_ma
        for cur, t_list in zip(self.si_cursors, [t_acc, t_vel, t_pk, t_mag]):
            if t_list and t is not None:
                cur.set_xdata([t, t]); cur.set_visible(True)
            else:
                cur.set_visible(False)

        parts = [f"t = {_fmt_time_s(t)}"]
        if acc_v is not None:
            parts.append(
                f"Acc: {acc_v}  ({acc_v*1000.0/cpg:.1f} mg)")
        if vel_v is not None:
            parts.append(
                f"Vel: {vel_v}  ({vel_v*10.0/cpg:.3f} mm/s)")
        if pk_v is not None:
            parts.append(
                f"PK: {pk_v}  ({pk_v*1000.0/cpg:.1f} mg)")
        if mf_v is not None:
            parts.append(f"Mag Freq: {mf_v}")
        if ma_v is not None:
            parts.append(f"Mag Amp: {ma_v}")
        self.si_cursor_var.set("  |  ".join(parts))

    # =========================================================================
    # TWF
    # =========================================================================

    def process_twf_frame(self, frame):

        meta = frame.twf_meta

        if not meta or not meta.get("li_data"):
            return

        pkt_number = meta["pkt_number"]
        pkt_total  = meta["pkt_total"]
        axis       = meta["axis"]

        if pkt_total == 0:
            return

        buf = self.twf_buffers.get(axis)

        # Decide whether to start a new buffer for this axis.
        # Reset when: no buffer yet, pkt_total changed (new sequence length),
        # or pkt_number==0 and we haven't seen pkt 0 yet (true sequence start).
        start_new = (
            buf is None
            or buf.get("total") != pkt_total
            or (pkt_number == 0 and 0 not in buf.get("packets", {}))
        )

        if start_new:
            slot = self.twf_next_slot.get(axis, "A")
            self.twf_buffers[axis] = {
                "packets":        {},
                "total":          pkt_total,
                "permute":        meta["permute"],
                "si_factor_bits": meta["si_factor_bits"],
                "sample_odr":     meta["sample_odr"],
                "axis":           axis,
                "slot":           slot,
            }

        buf = self.twf_buffers[axis]

        # A packet counts as received once any of its repeats arrives.  Each
        # repeat is also kept under the polynomial version it used; under RF
        # Capability 5, or any method but Polynomial, every repeat carries
        # version 0 and identical data, so the repeats overwrite one slot.
        buf["packets"][pkt_number] = meta["li_data"]
        buf.setdefault("frames", {})[(pkt_number, meta.get("version", 0))] = meta["li_data"]

        received = len(buf["packets"])
        total    = buf["total"]

        is_complete = (pkt_number == pkt_total - 1 or received >= total)

        pct = int(100 * received / total) if total else 0

        self.twf_status_var.set(
            f"{'Complete' if is_complete else 'Receiving'}"
            f"  TWF{buf['slot']}"
            f"  Axis: {axis}"
            f"  ODR: {buf['sample_odr']} Hz"
            f"  Packets: {received} / {total}  ({pct}%)"
        )

        # ── Update magnetometer history from this packet's SI data ───────────
        si_type = meta.get("si_type", -1)

        if si_type in (3, 4):    # 3=MAG_FREQ  4=MAG_AMP

            seen = buf.setdefault("seen_mag_pkts", set())

            if pkt_number not in seen:

                seen.add(pkt_number)

                t_mag = frame.abs_time_s

                for a, key in [("X", "SI X"), ("Y", "SI Y"), ("Z", "SI Z")]:

                    val = frame.decoded.get(key)

                    if val is None:
                        continue

                    if si_type == 3:
                        self.mag_freq_history[a].append(val)
                        self.mag_freq_time_history[a].append(t_mag)
                    else:
                        self.mag_amp_history[a].append(val)
                        self.mag_amp_time_history[a].append(t_mag)

                self.update_short_interval()

        # ── Update TWF/FFT graphs on every packet, throttled to 5 s ─────────────
        # Assembly (waveform + NaN mask) runs on every packet — it is cheap.
        # The render (_update_twf_display / canvas.draw) is suppressed if the
        # last render for this axis was less than TWF_RENDER_INTERVAL_S seconds
        # ago, UNLESS the sequence is complete (always render the final result).
        TWF_RENDER_INTERVAL_S = 5.0
        now = time.monotonic()
        due = is_complete or (
            now - self.twf_last_render[axis] >= TWF_RENDER_INTERVAL_S
        )
        if due:
            self.twf_last_render[axis] = now
            try:
                self._assemble_and_plot_twf(axis=axis, is_complete=is_complete)
            except Exception:
                import traceback
                traceback.print_exc()

    def _assemble_and_plot_twf(self, axis, is_complete=True):

        buf            = self.twf_buffers[axis]
        packets        = buf["packets"]
        total_pkts     = buf["total"]
        permute        = buf["permute"]
        si_factor_bits = buf["si_factor_bits"]
        sample_odr     = buf["sample_odr"]
        slot           = buf["slot"]

        samples_per_pkt = 32
        total_samples   = total_pkts * samples_per_pkt
        full_scale_g    = 8 << si_factor_bits
        scale           = full_scale_g * 1000.0 / 32767.0   # raw → mg

        # Step 1 — flatten received packets into transmitted-position order
        received_flat = [0] * total_samples

        for pkt_num, pkt_samples in packets.items():
            for j, raw_sample in enumerate(pkt_samples):
                tx_pos = pkt_num * samples_per_pkt + j
                if 0 <= tx_pos < total_samples:
                    received_flat[tx_pos] = raw_sample

        # Step 2 — invert permutation to recover original sample order
        waveform = [0.0] * total_samples

        if permute == 0:      # DISTANCE
            for p, raw in enumerate(received_flat):
                pkt_k = p // samples_per_pkt
                j     = p %  samples_per_pkt
                orig  = pkt_k + j * total_pkts
                if 0 <= orig < total_samples:
                    waveform[orig] = raw * scale

        elif permute == 2:    # POLYNOMIAL: slot p carries sample permute_poly(N, p, version)
            frames = buf.get("frames") or {
                (pkt_num, 0): pkt_samples
                for pkt_num, pkt_samples in packets.items()
            }
            for (pkt_num, version), pkt_samples in frames.items():
                for j, raw_sample in enumerate(pkt_samples):
                    tx_pos = pkt_num * samples_per_pkt + j
                    if 0 <= tx_pos < total_samples:
                        orig = permute_poly(total_samples, tx_pos, version)
                        waveform[orig] = raw_sample * scale

        else:                 # NONE
            for p, raw in enumerate(received_flat):
                if p < total_samples:
                    waveform[p] = raw * scale

        # Build time axis: sample N occurs at N / ODR seconds = N*1000/ODR ms
        dt          = (1000.0 / sample_odr) if sample_odr > 0 else 1.0
        time_ms     = [i * dt for i in range(total_samples)]
        duration_ms = time_ms[-1] if time_ms else 0.0
        permute_name = PERMUTE_ENUM.get(permute, str(permute))

        n_received = len(packets)

        # Replace missing-data positions with NaN so matplotlib draws genuine
        # gaps in the plot rather than misleading vertical spikes from the
        # signal value down to the zero placeholder and back up again.
        # _compute_and_draw_fft uses interpolate_missing() on the stored NaN
        # values before computing the FFT, so the spectrum is unaffected.
        # Under Polynomial a sample is missing only if every repeat that
        # carried it was lost, which a packet count cannot show.
        if n_received < total_pkts or permute == 2:
            _mask = build_received_mask(
                set(packets.keys()), total_pkts, permute,
                received_frames=set(buf.get("frames", {}).keys()),
            )
            _wf          = np.array(waveform, dtype=float)
            _wf[~_mask]  = np.nan
            waveform     = _wf.tolist()
        pct        = int(100 * n_received / total_pkts) if total_pkts else 0

        # Always store the current state so the display can show partial data.
        # The "received_pkts" set lets _compute_and_draw_fft interpolate gaps.
        self.twf_store[slot][axis] = {
            "waveform":      waveform,
            "time_ms":       time_ms,
            "odr":           sample_odr,
            "full_scale_g":  full_scale_g,
            "permute_name":  permute_name,
            "permute_code":  permute,
            "axis":          axis,
            "slot":          slot,
            "duration_ms":   duration_ms,
            "total_pkts":    total_pkts,
            "received_pkts": set(packets.keys()),
            "received_frames": set(buf.get("frames", {}).keys()),
            "is_complete":   is_complete,
        }

        # Only advance the slot when the sequence is complete so that
        # mid-reception partial updates keep writing to the same slot.
        if is_complete:
            self.twf_next_slot[axis] = "B" if slot == "A" else "A"

        # Refresh graph if the display is showing this slot/axis
        if not self._loading_history:
            try:
                self._update_twf_display()
            except Exception:
                import traceback
                traceback.print_exc()

        if is_complete:
            self.twf_status_var.set(
                f"TWF{slot} complete  Axis: {axis}  ODR: {sample_odr} Hz"
                f"  ±{full_scale_g * 1000} mg  {total_samples} samples"
                f"  Duration: {duration_ms:.1f} ms  Permute: {permute_name}"
            )
        else:
            self.twf_status_var.set(
                f"Receiving  TWF{slot}  Axis: {axis}"
                f"  ODR: {sample_odr} Hz"
                f"  Packets: {n_received} / {total_pkts}  ({pct}%)"
            )

    def _update_twf_display(self):
        """Refresh the TWF and FFT plots from the currently selected slot/axis."""

        ab   = self.twf_display_ab.get()
        axis = self.twf_display_axis.get()
        data = self.twf_store[ab].get(axis)

        # If the selected slot has no data for this axis, try the other slot
        # (handles the case where history replay ends on an odd or even sequence)
        if data is None:
            other = "B" if ab == "A" else "A"
            if self.twf_store[other].get(axis) is not None:
                self.twf_display_ab.set(other)
                ab   = other
                data = self.twf_store[ab].get(axis)

        if data is None:
            self.twf_ax.set_title(f"TWF{ab} / {axis}-Axis  (no data)")
            self.twf_line.set_data([], [])
            self.twf_cursor_line.set_visible(False)
            self.twf_cursor_ann.set_text("")
            self.twf_diag_var.set("")
            self.twf_cursor_var.set("")
            self.twf_ax.relim()
            self.twf_ax.autoscale_view()
            self.twf_canvas.draw()
            return

        # ── Diagnostics ──────────────────────────────────────────────────────
        total_pkts = data.get("total_pkts", 0)
        received   = len(data.get("received_pkts") or [])
        missed     = max(0, total_pkts - received)
        pct_ok     = (100.0 * received / total_pkts) if total_pkts else 0.0
        quality    = ("Excellent" if pct_ok >= 99 else
                      "Good"      if pct_ok >= 95 else
                      "Fair"      if pct_ok >= 80 else "Poor")
        complete   = "Complete" if data.get("is_complete") else "Partial"

        self.twf_diag_var.set(
            f"{complete}  |  "
            f"Received: {received} / {total_pkts}  ({pct_ok:.1f}%)  |  "
            f"Missed: {missed}  |  "
            f"Signal: {quality}"
        )

        # ── TWF time-domain ──────────────────────────────────────────────────
        self.twf_line.set_data(data["time_ms"], data["waveform"])

        self.twf_ax.relim()
        self.twf_ax.autoscale_view()
        self.twf_ax.set_xlim(left=0)

        self.twf_ax.set_title(
            f"TWF{ab}  {axis}-Axis  ODR: {data['odr']} Hz  "
            f"±{data['full_scale_g'] * 1000} mg  "
            f"{len(data['waveform'])} samples  "
            f"Duration: {data['duration_ms']:.1f} ms  "
            f"Permute: {data['permute_name']}"
        )
        self.twf_ax.set_xlabel("Time (ms)")
        self.twf_ax.set_ylabel("Acceleration (mg)")

        # ── Cursor ───────────────────────────────────────────────────────────
        self.twf_cursor_pos = max(
            0.0, min(self.twf_cursor_pos, data["duration_ms"])
        )
        self._refresh_cursor(data)

        # ── FFT (compute immediately on display change too) ──────────────────
        self._compute_and_draw_fft(data)

        self.twf_canvas.draw()

    # =========================================================================
    # TWF CURSOR & ZOOM
    # =========================================================================

    def _get_twf_data(self):
        """Return the currently displayed TWF data dict, or None."""
        return self.twf_store[self.twf_display_ab.get()].get(
            self.twf_display_axis.get()
        )

    def _refresh_cursor(self, data=None):
        """Update the cursor vertical line and value annotation."""
        if data is None:
            data = self._get_twf_data()
        if data is None:
            return

        waveform = data["waveform"]
        odr      = data["odr"]
        duration = data["duration_ms"]

        if not waveform or odr <= 0:
            return

        t   = max(0.0, min(self.twf_cursor_pos, duration))
        dt  = 1000.0 / odr
        idx = min(int(round(t / dt)), len(waveform) - 1)
        val = waveform[idx]

        self.twf_cursor_line.set_xdata([t, t])  # data coords (ms)
        self.twf_cursor_line.set_ydata([0, 1])  # axes-fraction: full height
        self.twf_cursor_line.set_visible(True)

        self.twf_cursor_ann.set_text(
            f"t = {t:.3f} ms   Sample [{idx}]"
        )

        self.twf_cursor_var.set(
            f"Cursor  ▶  t = {t:.4f} ms   "
            f"Sample [{idx} / {len(waveform) - 1}]   "
            f"Value = {val:.1f} mg"
        )

        self.twf_canvas.draw_idle()

    def _cursor_step(self, steps):
        """Move the cursor by `steps` samples (-ve = left, +ve = right)."""
        data = self._get_twf_data()
        if data is None:
            return

        odr = data["odr"]
        dt  = (1000.0 / odr) if odr > 0 else 1.0

        self.twf_cursor_pos = max(
            0.0,
            min(self.twf_cursor_pos + steps * dt, data["duration_ms"])
        )
        self._refresh_cursor(data)

    def _zoom_twf(self, factor):
        """
        Zoom the TWF time-axis by `factor` centred on the cursor.
        factor > 1  →  zoom in (smaller time window)
        factor < 1  →  zoom out (larger time window)
        """
        data = self._get_twf_data()
        if data is None:
            return

        lo, hi     = self.twf_ax.get_xlim()
        span       = hi - lo
        new_span   = max(span / factor, 1.0)     # never narrower than 1 ms
        max_t      = data["duration_ms"]
        centre     = max(lo, min(hi, self.twf_cursor_pos))

        new_lo = max(0.0,   centre - new_span / 2)
        new_hi = min(max_t, new_lo  + new_span)
        new_lo = max(0.0,   new_hi  - new_span)   # re-clamp left after right clamp

        self.twf_ax.set_xlim(new_lo, new_hi)
        self.twf_canvas.draw_idle()

    def _zoom_reset_twf(self):
        """Restore the full time range of the current waveform."""
        data = self._get_twf_data()
        if data is None:
            return
        self.twf_ax.set_xlim(0.0, data["duration_ms"])
        self.twf_canvas.draw_idle()

    def _compute_and_draw_fft(self, data):
        """Compute FFT from waveform data and update the FFT plot."""

        waveform = data["waveform"]
        odr      = data["odr"]
        N        = len(waveform)

        if N < 4 or odr <= 0:
            return

        arr = np.array(waveform, dtype=float)

        # Interpolate across sample positions that were not yet received so
        # that missing packets don't corrupt the spectrum with artificial zeros.
        received_pkts = data.get("received_pkts")
        total_pkts    = data.get("total_pkts", 0)
        permute_code  = data.get("permute_code", 1)   # default NONE

        if received_pkts is not None and total_pkts > 0:
            n_missing = total_pkts - len(received_pkts)
            if n_missing > 0 or permute_code == 2:
                has_data = build_received_mask(
                    received_pkts, total_pkts, permute_code,
                    received_frames=data.get("received_frames"),
                )
                arr = interpolate_missing(arr, has_data)

        # Hanning window to reduce spectral leakage
        arr *= np.hanning(N)

        # rfft returns the single-sided (positive-frequency) complex spectrum.
        # Take the magnitude (sqrt(re² + im²)) to discard phase / imaginary
        # component; magnitude is always ≥ 0 so both axes remain positive.
        fft_complex = np.fft.rfft(arr)
        fft_mag     = np.abs(fft_complex) * 2.0 / N   # always ≥ 0
        freqs       = np.fft.rfftfreq(N, d=1.0 / odr) # always ≥ 0

        self.fft_line.set_data(freqs, fft_mag)

        self.fft_ax.relim()
        self.fft_ax.autoscale_view()

        # Lock both axes to start at 0 so they remain strictly positive
        # after matplotlib's autoscale padding.
        self.fft_ax.set_xlim(left=0)
        self.fft_ax.set_ylim(bottom=0)

        ab   = self.twf_display_ab.get()
        axis = self.twf_display_axis.get()

        self.fft_ax.set_title(
            f"FFT  TWF{ab}  {axis}-Axis  ODR: {odr} Hz  "
            f"Resolution: {odr / N:.2f} Hz/bin"
        )
        self.fft_ax.set_xlabel("Frequency (Hz)")
        self.fft_ax.set_ylabel("Amplitude (mg)")

    def update_twf_fft(self):
        """Periodic 1-minute FFT refresh from the currently displayed waveform."""

        ab   = self.twf_display_ab.get()
        axis = self.twf_display_axis.get()
        data = self.twf_store[ab].get(axis)

        if data is not None:
            self._compute_and_draw_fft(data)
            self.twf_canvas.draw()

        # Reschedule
        self.root.after(60_000, self.update_twf_fft)

    # =========================================================================
    # CONFIG
    # =========================================================================

    def update_config(self, frame):

        now = time.time()

        # Only parameters go in the table, each under its own block, which
        # under permutation is not the multiplex of the frame that carried it
        for key, block in frame.config_param_block.items():

            self.config_latest[(block, key)] = frame.decoded[key]

            self.config_update_time[(block, key)] = now

    def update_config_tab(self):

        trees = [self.config_tree_left, self.config_tree_mid, self.config_tree_right]
        for tree in trees:
            for item in tree.get_children():
                tree.delete(item)

        now = time.time()

        # ── Sort all config rows: (block, param_index) ───────────────────────
        def _sort_key(item):
            (blk, k), _ = item
            names = CONFIG_MUX_TABLE.get(blk, [])
            try:
                idx = names.index(k)
            except ValueError:
                idx = 999
            return (blk, idx)

        sorted_rows = sorted(self.config_latest.items(), key=_sort_key)

        # Distribute rows across three trees in bands of 20
        counts = [0, 0, 0]
        _ROWS_PER_TREE = 20

        for global_idx, ((block, key), val) in enumerate(sorted_rows):
            tree_idx  = min(global_idx // _ROWS_PER_TREE, 2)
            local_row = counts[tree_idx]

            if isinstance(val, tuple):
                value, unit = val
            else:
                value, unit = val, ""

            is_disabled  = ("Enable" in key and value == 0)
            is_reserved  = "Reserved" in key
            is_unused    = (key not in CONFIG_DETAIL_PARAMS) and not is_reserved

            if is_disabled:
                row_tag = "disabled"
            elif is_unused:
                row_tag = "unused"
            else:
                row_tag = "odd" if local_row % 2 == 0 else "even"

            trees[tree_idx].insert(
                "", tk.END,
                values=(block, global_idx, key, value, unit),
                tags=(row_tag,),
            )
            counts[tree_idx] += 1

        # ── Block last-update summary ─────────────────────────────────────────
        # Compute the most recent update wall-time for each block
        block_last: dict[int, float] = {}
        for (blk, _key), wall_t in self.config_update_time.items():
            if blk not in block_last or wall_t > block_last[blk]:
                block_last[blk] = wall_t

        for item in self.config_summary_tree.get_children():
            self.config_summary_tree.delete(item)

        for i, (blk, wall_t) in enumerate(sorted(block_last.items())):
            age_s    = now - wall_t
            last_str = _fmt_time_s(wall_t % 86400)    # HH:MM:SS
            age_str  = format_elapsed_time(age_s)
            row_tag  = "odd" if i % 2 == 0 else "even"
            self.config_summary_tree.insert(
                "", tk.END,
                values=(blk, last_str, age_str),
                tags=(row_tag,),
            )

        # ── Build flat name→value lookup (used by all detail tables) ─────────
        cfg: dict = {}
        for (_blk, k), v in self.config_latest.items():
            cfg[k] = v[0] if isinstance(v, tuple) else v

        # ── Helper functions (must be defined before any detail table uses them)
        def _yn(key):
            """Return 'Yes' / 'No' / '—' for a boolean config key."""
            v = cfg.get(key)
            if v is None:
                return "—"
            return "Yes" if v else "No"

        def _val(key):
            """Return the numeric value as a string, or '—' if absent."""
            v = cfg.get(key)
            return str(v) if v is not None else "—"

        def _axis_enable(x_key, y_key, z_key):
            """Return 'X Y Z' / 'X Z' / 'None' from three boolean enable keys."""
            parts = []
            if cfg.get(x_key): parts.append("X")
            if cfg.get(y_key): parts.append("Y")
            if cfg.get(z_key): parts.append("Z")
            return " ".join(parts) if parts else "None"

        def _samples_tx(x_key, y_key, z_key):
            """Return 'X:N Y:M Z:P' from per-axis sampling count keys."""
            parts = []
            for axis, key in (("X", x_key), ("Y", y_key), ("Z", z_key)):
                v = cfg.get(key)
                if v is not None:
                    parts.append(f"{axis}:{v}")
            return " ".join(parts) if parts else "—"

        # ── Operation Timings ─────────────────────────────────────────────────
        tim_rows = {
            "wakeup_idle":        ("Wakeup Idle Count",      _val("Wakeup Idle Count")),
            "sample_delay":       ("Sample Delay Count",     _val("Sample Delay Count")),
            "post_sample":        ("Post Sample Interval",   _val("Post Sample Interval")),
            "seek_machine":       ("Seek Machine On",        _val("Seek Machine On")),
            "delay_confirm":      ("Delay Confirm",          _val("Delay Confirm")),
            "confirm_machine":    ("Confirm Machine",        _val("Confirm Machine")),
            "transmit_twf":       ("Transmit TWF",           _val("Transmit TWF")),
            "return_idle":        ("Return Idle",            _val("Return Idle")),
            "machine_on_confirm": ("Machine ON Confirm Count", _val("Machine ON Confirm Count")),
        }
        for iid, vals in tim_rows.items():
            self.config_timings_tree.item(iid, values=vals)

        # ── Sampling Configuration ────────────────────────────────────────────
        samp_rows = {
            "enable":     ("Enable",
                           _yn("TWFA Enable"),
                           _yn("TWFB Enable"),
                           ""),
            "axis_en":    ("Axis Enable",
                           _axis_enable("TWFA X Enable", "TWFA Y Enable", "TWFA Z Enable"),
                           _axis_enable("TWFB X Enable", "TWFB Y Enable", "TWFB Z Enable"),
                           ""),
            "odr":        ("ODR",
                           _val("TWFA ODR"),
                           _val("TWFB ODR"),
                           _val("RMS ODR")),
            "samples":    ("#Samples",
                           _val("TWFA Samples"),
                           _val("TWFB Samples"),
                           _val("RMS Samples")),
            "samples_tx": ("Samples TX",
                           _samples_tx("TWFA X Sampling", "TWFA Y Sampling", "TWFA Z Sampling"),
                           _samples_tx("TWFB X Sampling", "TWFB Y Sampling", "TWFB Z Sampling"),
                           ""),
        }

        for iid, vals in samp_rows.items():
            self.config_sampling_tree.item(iid, values=vals)

        # ── Trigger Settings table ────────────────────────────────────────────
        # Already decoded strings (AUTO, LOWEST, ...)
        scaling_str = (
            f"A:{cfg.get('TWFA Scaling', '—')}  "
            f"B:{cfg.get('TWFB Scaling', '—')}"
        )

        method_str = cfg.get("Trigger Method", "—")   # already decoded string

        # Threshold value(s) depend on the trigger method
        if method_str == "PK2PK":
            threshold_str = _val("Machine Pk2Pk Threshold")
        elif method_str == "VELRSS":
            threshold_str = _val("Machine VEL Threshold")
        elif method_str == "ACCRMS":
            threshold_str = _val("Machine ACC Threshold")
        elif method_str == "ACCWAVE":
            threshold_str = ", ".join([
                _val("Machine ACC Threshold"),
                _val("Machine Peaks Threshold"),
                _val("Machine ACC Detect"),
            ])
        else:
            threshold_str = "—"

        trig_rows = {
            "scaling":   ("Scaling",   scaling_str),
            "method":    ("Method",    str(method_str)),
            "threshold": ("Threshold", threshold_str),
            "tr4":       ("", ""),
            "tr5":       ("", ""),
        }
        for iid, vals in trig_rows.items():
            self.config_trigger_tree.item(iid, values=vals)

        # ── Sync ──────────────────────────────────────────────────────────────
        sync_rows = {
            "sync_en":    ("Sync Enable",   _yn("Sync Enable")),
            "sync_retry": ("Sync Retry",    _val("Sync Retry")),
            "sync_max":   ("Sync Max Wait", _val("Sync Max Wait")),
            "listen_en":  ("Listen Enable", _yn("Listen Enable")),
            "s5":         ("", ""),
        }
        for iid, vals in sync_rows.items():
            self.config_sync_tree.item(iid, values=vals)

        # ── FFT ───────────────────────────────────────────────────────────────
        fft_rows = {
            "fft_en":       ("FFT Enable",       _yn("FFT Enable")),
            "fft3_ax":      ("FFT3 Axis Enable", _val("FFT3 Axis Enable")),
            "fft3_f1":      ("FFT3 First Bin",   _val("FFT3 First Bin")),
            "fft3_f2":      ("FFT3 Last Bin",    _val("FFT3 Last Bin")),
            "rms_min_freq": ("RMS Min Freq",     _val("RMS Min Frequency")),
            "fft_odr":      ("FFT ODR",          _val("FFT ODR")),
            "fft_samples":  ("FFT Samples",      _val("FFT Samples")),
            "fft_scaling":  ("FFT Scaling",      _val("FFT Scaling")),
            "short_capture": ("Short Capture",   _val("Short Capture")),
            "fft_off_count": ("FFT Off Count",   _val("FFT Machine Off Count")),
        }
        for iid, vals in fft_rows.items():
            self.config_fft_tree.item(iid, values=vals)

        # ── Other ─────────────────────────────────────────────────────────────
        other_rows = {
            "alive_period": ("Alive Period",       _val("Alive Period")),
            "batt_delay":   ("Batt Sample Delay",  _val("Battery Sample Delay")),
            "transit_wait": ("Transit Wait Time",  _val("Transit Wait Time")),
            "transit_wake": ("Transit Wake Time",  _val("Transit Wake Time")),
            "o5":           ("Permute Method",     str(cfg.get("Permute Method", "—"))),
        }
        for iid, vals in other_rows.items():
            self.config_other_tree.item(iid, values=vals)

        self._update_identification()

        self.root.after(1000, self.update_config_tab)

    def _update_identification(self):

        self.id_text.delete("1.0", tk.END)

        vf = self.latest_version_frame

        if vf is None:

            self.id_text.insert(
                tk.END,
                "No VERSION frame received yet.\n"
            )

            return

        d = vf.decoded

        lines = [
            f"Received:      {vf.time_string}",
            f"Sensor ID:     0x{vf.sensor_id}  "
            f"Product: {PROD_ID_TABLE.get(vf.prod_id, str(vf.prod_id))}",
            f"FW Version:    {d.get('FW Version', '')}",
            f"SHA:           {d.get('SHA', '')}",
            f"RF Capability: {RF_CAP_TABLE.get(vf.rf_cap, str(vf.rf_cap))}  "
            f"HW Capability: {vf.hw_cap}  "
            f"FW Capability: {vf.fw_cap}  "
            f"Frame Version: {vf.frame_version}  "
            f"PCB Version: {d.get('PCB Version', '')}",
            f"Temperature:   {d.get('Temperature', '')}  "
            f"Battery: {d.get('Battery Voltage', '')}",
            f"Ticks:         {d.get('Ticks Since Reset', '')}",
            f"Reset Reason:  {d.get('Reset Reason', '')}",
        ]

        self.id_text.insert(tk.END, "\n".join(lines))


# =============================================================================
# MAIN
# =============================================================================

def main():

    if "--version" in sys.argv:
        print_version()
        sys.exit(0)

    if "--help" in sys.argv:
        print_help()
        sys.exit(0)

    parser = argparse.ArgumentParser(add_help=False)

    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--port", help="read the S2-LP kit directly, e.g. COM4")
    source.add_argument("--simulate", action="store_true",
                        help="a simulated kit with a sensor on the air")
    source.add_argument("--log", help="RF log file written by ST's GUI, as rf_monitor read")

    parser.add_argument("--board", default="", help="kit board name (optional)")
    parser.add_argument(
        "--setup",
        default=str(pathlib.Path(__file__).resolve().parents[2]
                    / "configs" / "s2lp_kepler_433_rx.regs"),
        help="register file to receive with",
    )
    parser.add_argument("--packet-log", default=None,
                        help="also write every packet, raw and decoded, as JSON Lines")
    parser.add_argument("--event-log", default=None,
                        help="bench event log to follow on the Events page")
    parser.add_argument(
        "--sensor-id",
        default=None,
        metavar="HEX",
        help=(
            "Sensor ID to filter on startup (e.g. 5C1705). "
            "If omitted the last ID from sensor_ids.txt is used."
        ),
    )

    args = parser.parse_args()

    radio = None
    air = None
    if args.port or args.simulate:
        from benchtools.instruments.s2lp.kepler import decode_kepler_frame
        radio = LiveRadio("sim://" if args.simulate else args.port, board=args.board,
                          setup=args.setup, packet_log=args.packet_log,
                          decoder=decode_kepler_frame)
        if args.simulate:
            air = SimulatedAir(radio.radio)
            air.start()
        radio.start()

    root = tk.Tk()

    TestBenchMonitor(root, args.log, initial_sensor_id=args.sensor_id,
                     radio=radio, event_log=args.event_log, air=air)

    root.mainloop()


if __name__ == "__main__":

    main()
