"""SWO / ITM stream decoding.

Traces to: JLINK-FR-064, SWE4-UT-SWO.
"""

from __future__ import annotations

import pytest

from benchtools.instruments.jlink.swo import ItmDecoder

SYNC = b"\x00" * 5 + b"\x80"


class TestSourcePackets:
    @pytest.mark.parametrize("size,value", [(1, 0xAA), (2, 0xBEEF), (4, 0x12345678)])
    def test_every_payload_width(self, size, value):
        """A 2-byte packet has size bits 10, so bit 0 is clear.

        Classifying on bit 0 alone - an easy mistake - would treat it as a
        protocol packet and silently drop every 16-bit instrumentation write.
        """
        decoder = ItmDecoder()
        events = decoder.feed(ItmDecoder.encode_software_event(5, value, size))
        assert len(events) == 1
        assert events[0].value == value and events[0].size == size

    def test_port_is_decoded(self):
        events = ItmDecoder().feed(ItmDecoder.encode_software_event(17, 1, 1))
        assert events[0].port == 17

    def test_hardware_source_is_skipped_without_desynchronising(self):
        decoder = ItmDecoder()
        hardware = bytes([(0 << 3) | 0x04 | 0x01, 0x99])     # DWT event packet
        events = decoder.feed(hardware + ItmDecoder.encode_software_event(1, 7, 1))
        assert [event.value for event in events] == [7]

    def test_events_on_port_filters(self):
        decoder = ItmDecoder()
        decoder.feed(
            ItmDecoder.encode_software_event(1, 10, 1)
            + ItmDecoder.encode_software_event(2, 20, 1)
        )
        assert [event.value for event in decoder.events_on_port(2)] == [20]


class TestTimestamps:
    def test_format_2_single_byte(self):
        decoder = ItmDecoder()
        decoder.feed(ItmDecoder.encode_local_timestamp(6) + ItmDecoder.encode_software_event(1, 1, 1))
        assert decoder.events[0].timestamp == 6

    def test_format_1_multi_byte(self):
        decoder = ItmDecoder()
        decoder.feed(
            ItmDecoder.encode_local_timestamp(64_000)
            + ItmDecoder.encode_software_event(1, 1, 1)
        )
        assert decoder.events[0].timestamp == 64_000

    def test_timestamps_accumulate_as_deltas(self):
        decoder = ItmDecoder()
        events = decoder.feed(
            ItmDecoder.encode_software_event(1, 1, 1)
            + ItmDecoder.encode_local_timestamp(64_000)
            + ItmDecoder.encode_software_event(1, 2, 1)
        )
        assert events[0].timestamp == 0
        assert events[1].timestamp == 64_000

    def test_prescaler_scales_to_cycles(self):
        decoder = ItmDecoder(prescaler=16)
        decoder.feed(ItmDecoder.encode_local_timestamp(100))
        assert decoder.timestamp_ticks == 100
        assert decoder.timestamp_cycles == 1600

    def test_prescaler_must_be_positive(self):
        with pytest.raises(ValueError, match="prescaler"):
            ItmDecoder(prescaler=0)


class TestFramingRobustness:
    def test_incremental_feeding_matches_one_shot(self):
        """SWO arrives in arbitrary chunks and a packet is routinely split."""
        stream = (
            SYNC
            + ItmDecoder.encode_software_event(1, 0xAA, 1)
            + ItmDecoder.encode_local_timestamp(64_000)
            + ItmDecoder.encode_software_event(1, 0x12345678, 4)
        )
        whole = ItmDecoder().feed(stream)
        piecemeal = ItmDecoder()
        collected = []
        for index in range(len(stream)):
            collected += piecemeal.feed(stream[index : index + 1])
        assert [(e.value, e.timestamp) for e in collected] == [
            (e.value, e.timestamp) for e in whole
        ]

    def test_synchronisation_packet_is_consumed(self):
        decoder = ItmDecoder()
        events = decoder.feed(SYNC + ItmDecoder.encode_software_event(1, 5, 1))
        assert [event.value for event in events] == [5]

    def test_zeros_not_followed_by_sync_are_discarded(self):
        """A partial zero run must be dropped, not treated as a packet.

        The byte after the zeros is 0x04 - an unrecognised protocol header, so
        unambiguously not a source packet. (0x41, say, would be a *valid* 1-byte
        source packet on port 8, which is a different case.)
        """
        decoder = ItmDecoder()
        events = decoder.feed(b"\x00\x00\x04" + ItmDecoder.encode_software_event(1, 5, 1))
        assert [event.value for event in events] == [5]

    def test_overflow_is_recorded_and_flagged(self):
        """A dropped packet invalidates the timestamps after it."""
        decoder = ItmDecoder()
        events = decoder.feed(b"\x70" + ItmDecoder.encode_software_event(1, 5, 1))
        assert decoder.overflows == 1
        assert events[0].after_overflow is True

    def test_overflow_flag_clears_after_one_event(self):
        decoder = ItmDecoder()
        decoder.feed(
            b"\x70"
            + ItmDecoder.encode_software_event(1, 5, 1)
            + ItmDecoder.encode_software_event(1, 6, 1)
        )
        assert [event.after_overflow for event in decoder.events] == [True, False]

    def test_extension_and_global_timestamp_are_skipped(self):
        decoder = ItmDecoder()
        events = decoder.feed(
            b"\x08" + b"\x94\x81\x01" + ItmDecoder.encode_software_event(3, 9, 1)
        )
        assert [event.value for event in events] == [9]

    def test_unrecognised_protocol_byte_costs_one_byte(self):
        decoder = ItmDecoder()
        events = decoder.feed(b"\x04" + ItmDecoder.encode_software_event(1, 5, 1))
        assert [event.value for event in events] == [5]

    def test_reset_clears_state(self):
        decoder = ItmDecoder()
        decoder.feed(b"\x70" + ItmDecoder.encode_software_event(1, 5, 1))
        decoder.reset()
        assert decoder.events == [] and decoder.overflows == 0
        assert decoder.timestamp_ticks == 0

    def test_encoder_rejects_a_bad_width(self):
        with pytest.raises(ValueError, match="size"):
            ItmDecoder.encode_software_event(1, 1, 3)
