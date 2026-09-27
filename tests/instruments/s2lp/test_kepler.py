"""Decoding the Kepler sensor's frames.

The ALIVE frames are the ones sensor 5C1712 sent on 2026-09-27, received by the
S2-LP kit. The other types have not been seen on the air yet, so they are built
here from the reference firmware's layouts - which checks the decoder against
the table it was written from, not against a sensor.

Traces to: S2LP-FR-070, SWE4-UT-S2LPKEPLER.
"""

from __future__ import annotations

import struct

import pytest

from benchtools.instruments.s2lp.kepler import (
    FRAME_TYPES,
    KeplerFrameError,
    decode_kepler_frame,
)

#: Received from sensor 5C1712: one ALIVE packet, its three repeats.
ALIVE_REPEATS = [
    "5c171203060c04031300f47f018400008a0056005a00db0051007f02ed0233025c0005",
    "5c171203060c04032300f47f018400008a0056005a00db0051007f02ed0233025c0004",
    "5c171203060c04033300f47f018400008a0056005a00db0051007f02ed0233025c0004",
]


def header(pl_type: int, size: int, type_cap: int = 1) -> bytearray:
    frame = bytearray(size)
    frame[0:8] = bytes([0xAB, 0xCD, 0xEF, 3, 6, (type_cap << 3) | 4, 4, pl_type])
    return frame


class TestAFrameFromTheAir:
    def test_the_header(self):
        decoded = decode_kepler_frame(bytes.fromhex(ALIVE_REPEATS[0]))
        assert decoded["type"] == "ALIVE"
        assert decoded["sensor_id"] == "5C1712"
        assert (decoded["product_id"], decoded["rf_capability"]) == (3, 6)
        assert (decoded["type_capability"], decoded["hw_capability"]) == (1, 4)
        assert decoded["fw_capability"] == 4

    def test_the_repeats_count_up(self):
        repeats = [decode_kepler_frame(bytes.fromhex(h))["frame"] for h in ALIVE_REPEATS]
        assert repeats == [{"repeat": index, "frames_per_packet": 3} for index in range(3)]

    def test_the_environment(self):
        decoded = decode_kepler_frame(bytes.fromhex(ALIVE_REPEATS[0]))
        assert decoded["temperature_c"] == 24.4
        assert decoded["battery_mv"] == 127 * 20
        assert decoded["ticks"] == 388

    def test_the_vibration_figures_stay_as_sent(self):
        decoded = decode_kepler_frame(bytes.fromhex(ALIVE_REPEATS[0]))
        assert decoded["acc_rms"] == [138, 86, 90]
        assert decoded["velocity"] == [219, 81, 127]
        assert decoded["peak_to_peak"] == [749, 563, 604]

    def test_si_updated_is_set_on_the_first_repeat_only(self):
        """The firmware clears it once it has been loaded."""
        flags = [decode_kepler_frame(bytes.fromhex(h))["status"]["si_updated"]
                 for h in ALIVE_REPEATS]
        assert flags == [True, False, False]

    def test_a_current_frame_has_no_warnings(self):
        assert "warnings" not in decode_kepler_frame(bytes.fromhex(ALIVE_REPEATS[0]))


class TestLayoutsFromTheReference:
    def test_version(self):
        frame = header(2, 83)
        frame[8] = 0x13
        frame[9:16] = b"abc1234"
        frame[16:26] = b"V11.00.00\x00"
        frame[73:77] = struct.pack(">I", 0x00000004)
        frame[77], frame[78] = 150, 4
        frame[79:81] = struct.pack(">h", -52)
        frame[81:83] = struct.pack(">H", 7)
        decoded = decode_kepler_frame(bytes(frame))
        assert (decoded["sha"], decoded["version"]) == ("abc1234", "V11.00.00")
        assert decoded["reset_reason"] == 4
        assert decoded["battery_loaded_mv"] == 3000
        assert decoded["temperature_c"] == -5.2
        assert decoded["ticks"] == 7

    def test_install_assist_is_an_alive_frame_with_bit_7(self):
        frame = bytearray(bytes.fromhex(ALIVE_REPEATS[0]))
        frame[34] = 0x80
        decoded = decode_kepler_frame(bytes(frame))
        assert decoded["apdu"] == "INSTALL_ASSIST" and decoded["status"]["install_assist"]

    def test_twf(self):
        frame = header(4, 100)
        frame[8], frame[9] = 0x10, 0x23                  # polynomial permute, repeat 1 of 3
        frame[13:15] = struct.pack(">H", (2 << 14) | (1 << 12) | (5 << 5) | 3)
        frame[17:21] = struct.pack(">HH", 3, 12)
        frame[29:31] = struct.pack(">h", -300)
        frame[93:97] = struct.pack(">I", 123456)
        frame[97] = 9
        decoded = decode_kepler_frame(bytes(frame))
        assert decoded["permute_method"] == "polynomial"
        assert decoded["frame"] == {"repeat": 1, "frames_per_packet": 3}
        assert decoded["param"]["axis"] == 2 and decoded["param"]["si_type"] == 5
        assert (decoded["packet_number"], decoded["packet_count"]) == (3, 12)
        assert decoded["samples"][0] == -300 and len(decoded["samples"]) == 32
        assert decoded["time_taken_us"] == 123456 and decoded["group_id"] == 9

    def test_config(self):
        frame = header(5, 21)
        frame[8], frame[9], frame[10] = 0x08, 0x13, 11
        frame[11:21] = struct.pack(">5H", 1, 2, 3, 4, 65535)
        decoded = decode_kepler_frame(bytes(frame))
        assert decoded["permute_method"] == "none"
        assert decoded["mux"] == 11 and decoded["values"] == [1, 2, 3, 4, 65535]

    def test_fft2_amplitude_is_little_endian(self):
        frame = header(7, 105)
        frame[17:21] = struct.pack("<f", 1.5)
        frame[21] = 100
        decoded = decode_kepler_frame(bytes(frame))
        assert decoded["max_bin_amplitude"] == 1.5
        assert decoded["bins"].startswith("64")

    def test_fft(self):
        decoded = decode_kepler_frame(bytes(header(6, 97)))
        assert decoded["type"] == "FFT" and len(bytes.fromhex(decoded["bins"])) == 78

    def test_cmd(self):
        frame = header(8, 15, type_cap=0)
        frame[8] = 0x11
        frame[9:12] = bytes.fromhex("5C1712")
        frame[12:14] = struct.pack(">H", 0x0003)
        frame[14] = 2
        decoded = decode_kepler_frame(bytes(frame))
        assert (decoded["cmd"], decoded["retry"], decoded["for_sensor"]) == ("GENERAL", 2, "5C1712")

    def test_response(self):
        frame = header(9, 19, type_cap=0)
        frame[0:3] = bytes.fromhex("F00000")
        frame[12] = 1
        decoded = decode_kepler_frame(bytes(frame))
        assert (decoded["gateway_id"], decoded["response"]) == ("F00000", "SYNC_LORES")

    def test_every_type_has_a_decoder(self):
        for pl_type, (_name, size) in FRAME_TYPES.items():
            assert decode_kepler_frame(bytes(header(pl_type, size)))["pl_type"] == pl_type


class TestWhatCannotBeDecoded:
    def test_a_short_header(self):
        with pytest.raises(KeplerFrameError, match="8-byte header"):
            decode_kepler_frame(b"\x01\x02")

    def test_an_unknown_type(self):
        with pytest.raises(KeplerFrameError, match="PL_TYPE 42"):
            decode_kepler_frame(bytes(header(42, 35)))

    def test_a_truncated_frame(self):
        with pytest.raises(KeplerFrameError, match="ALIVE frame is 35 bytes; this payload is 20"):
            decode_kepler_frame(bytes.fromhex(ALIVE_REPEATS[0])[:20])

    def test_extra_bytes_are_noted_not_refused(self):
        decoded = decode_kepler_frame(bytes.fromhex(ALIVE_REPEATS[0]) + b"\x00")
        assert decoded["warnings"] == ["1 byte(s) beyond the ALIVE layout"]

    def test_another_rf_capability_is_decoded_with_a_warning(self):
        frame = bytearray(bytes.fromhex(ALIVE_REPEATS[0]))
        frame[4] = 4
        assert "RF_CAP 4" in decode_kepler_frame(bytes(frame))["warnings"][0]
