"""Names and arithmetic behind Kepler frames, checked against the firmware (#151).

Expected values are worked from the sensor firmware's own rules
(V11.00.0000-96-g25a54b97a): ``app_normal.c`` for the parameter order,
``api_radio_field.c`` for the CONFIG slot mapping, ``utils/permute.c`` for the
polynomial, ``API_Vibration_PacketGet`` for the waveform order and
``API_Vibration_CompressOdr`` for the ODR code.

Traces to: S2LP-FR-081 .. S2LP-FR-083, SWE4-UT-S2LPTABLES.
"""

from __future__ import annotations

import struct

import pytest

from benchtools.instruments.s2lp.kepler import decode_kepler_frame
from benchtools.instruments.s2lp.kepler_tables import (
    CONFIG_PARAMETERS, config_parameter, name_config, odr_hz, permute_poly,
    permute_poly_any_size, reset_reasons, twf_sample,
)

from .test_kepler import ALIVE_REPEATS, VERSION_FRAME


class TestParameters:
    def test_sixty_parameters_in_the_firmware_s_order(self):
        assert len(CONFIG_PARAMETERS) == 60
        names = [name for name, _unit, _kind in CONFIG_PARAMETERS]
        assert names[5:7] == ["Transit Max Time", "Transit Wait Time"]
        assert names[40] == "Alive Period"
        assert names[49] == "Preamble Length"
        assert names[59] == "FFT Machine Off Count"
        assert len(set(names)) == 60

    @pytest.mark.parametrize("method, mux, slot, expected", [
        ("none", 0, 0, 0), ("none", 2, 3, 13), ("none", 11, 4, 59),
        ("distance", 0, 0, 0), ("distance", 0, 1, 12), ("distance", 3, 4, 51),
    ])
    def test_which_parameter_a_slot_carries(self, method, mux, slot, expected):
        assert config_parameter(mux, slot, method, 0) == expected

    def test_the_polynomial_covers_every_parameter_once_per_version(self):
        for version in range(8):
            seen = [config_parameter(mux, slot, "polynomial", version)
                    for mux in range(12) for slot in range(5)]
            assert sorted(seen) == list(range(60)), version

    def test_out_of_range(self):
        assert config_parameter(12, 0, "none", 0) is None
        assert config_parameter(0, 0, "reserved", 0) is None
        assert permute_poly_any_size(60, 60, 0) is None
        assert permute_poly_any_size(60, 0, 8) is None

    def test_values_are_named_with_units_and_enumerations(self):
        named = name_config(5, [12, 3, 10, 1, 0], "none", 0)
        assert [(n["parameter"], n["name"], n["shown"], n["unit"]) for n in named] == [
            (25, "Machine VEL Threshold", 12, "mm/s"), (26, "Trigger Method", "VELRSS", ""),
            (27, "RMS Min Frequency", 10, "Hz"), (28, "TWFA Enable", "Enabled", ""),
            (29, "TWFB Enable", "Disabled", "")]


class TestPolynomial:
    def test_it_is_a_permutation_of_a_power_of_two(self):
        for version in (0, 3, 7):
            assert sorted(permute_poly(256, index, version) for index in range(256)) == \
                list(range(256))

    def test_out_of_range_is_the_identity(self):
        assert permute_poly(64, 70, 0) == 70
        assert permute_poly(64, 5, 9) == 5


class TestWaveform:
    def test_none_distance_and_polynomial(self):
        assert twf_sample("none", 2, 3, 2048) == 67
        assert twf_sample("distance", 2, 3, 2048) == 2 + 3 * 64
        assert twf_sample("polynomial", 2, 3, 2048, 1) == permute_poly(2048, 67, 1)

    def test_every_sample_once_under_each_method(self):
        for method in ("none", "distance", "polynomial"):
            seen = sorted(twf_sample(method, packet, slot, 256, 2)
                          for packet in range(8) for slot in range(32))
            assert seen == list(range(256)), method


def test_odr_codes():
    assert odr_hz(25600) == 25600
    assert odr_hz(0x8000 | 6400) == 64000


def test_reset_reasons():
    assert reset_reasons(0x4) == ["Soft reset"]
    assert reset_reasons(0x00010002) == ["Watchdog", "Wakeup from System OFF by GPIO"]
    assert reset_reasons(0x100) == ["unknown bits 0x00000100"]


class TestDecodedFrames:
    def test_a_config_frame_names_its_parameters(self):
        frame = bytearray(21)
        frame[0:8] = bytes.fromhex("5c171203060c0405")
        frame[8] = 0x08                         # permute method: none
        frame[9] = 0x13                         # repeat 1 of 3
        frame[10] = 8                           # mux 8: parameters 40..44
        frame[11:21] = struct.pack(">5H", 600, 1, 0, 2, 40)
        decoded = decode_kepler_frame(bytes(frame))
        assert [p["name"] for p in decoded["parameters"]] == [
            "Alive Period", "FFT Enable", "FFT3 Axis Enable", "FFT3 First Bin", "FFT3 Last Bin"]
        assert decoded["parameters"][1]["shown"] == "Enabled"

    def test_version_names_its_reset_reason_and_pcb(self):
        decoded = decode_kepler_frame(bytes.fromhex(VERSION_FRAME))
        assert decoded["reset_reasons"] == ["Soft reset"]
        assert decoded["pcb"] == "V4X"
        assert decoded["product"] == "Kappa GEN2"

    def test_alive_names_its_phase(self):
        decoded = decode_kepler_frame(bytes.fromhex(ALIVE_REPEATS[0]))
        assert decoded["status"]["phase"] == 1             # status 0x05
        assert decoded["status"]["phase_name"] == "Peaks"
