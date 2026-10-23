"""Nordic Secure DFU over the dongle: the procedure, packages and send_package (#244).

Traces to: BLE-FR-121, SWE4-UT-BLEDFU.
"""

from __future__ import annotations

import json
import zipfile

import pytest

from benchtools.core.errors import ConfigurationError, InstrumentError
from benchtools.core.transport.mock import MockTransport
from benchtools.instruments.nordic_dongle import NordicDongle, SimulatedDongle
from benchtools.instruments.nordic_dongle.dfu import (
    DfuError,
    DfuImage,
    ExtendedError,
    ResultCode,
    SecureDfu,
    load_package,
    result_text,
)
from benchtools.instruments.nordic_dongle.dfu_target import DATA_OBJECT_MAX, SimulatedBootloader
from benchtools.simulated import kepler_sensor, reset_world
from benchtools.simulated.kepler import KEPLER_5C1712_DFU_ADDRESS, KEPLER_5C1712_DFU_NAME

INIT = bytes(range(141))                        # a signed init packet is ~141 bytes
FIRMWARE = bytes((i * 7) & 0xFF for i in range(10_000))   # three data objects


def make_package(path, images):
    """A package as ``nrfutil pkg generate`` writes one."""
    manifest = {}
    with zipfile.ZipFile(path, "w") as package:
        for kind, init, firmware in images:
            package.writestr(kind + ".dat", init)
            package.writestr(kind + ".bin", firmware)
            manifest[kind] = {"dat_file": kind + ".dat", "bin_file": kind + ".bin"}
        package.writestr("manifest.json", json.dumps({"manifest": manifest}))
    return str(path)


def dfu_over(target: SimulatedBootloader, chunk: int = 244) -> SecureDfu:
    return SecureDfu(control=lambda request, timeout: target.control(request),
                     packet=target.packet, chunk=chunk)


class TestTheProcedure:
    def test_an_image_arrives_whole(self):
        target = SimulatedBootloader()
        stage, code, extended = dfu_over(target).send_image(DfuImage("application", INIT, FIRMWARE))
        assert (stage, code, extended) == ("done", ResultCode.SUCCESS, None)
        assert target.init_packets == [INIT]
        assert target.firmware == [FIRMWARE]

    def test_the_firmware_goes_in_objects_of_the_bootloader_s_size(self):
        target = SimulatedBootloader()
        dfu_over(target).send_image(DfuImage("application", INIT, FIRMWARE))
        creates = [r for r in target.requests if r[0] == 0x01 and r[1] == 0x02]
        assert len(creates) == -(-len(FIRMWARE) // DATA_OBJECT_MAX)
        assert target.packets == 1 + sum(-(-min(DATA_OBJECT_MAX, len(FIRMWARE) - o) // 244)
                                         for o in range(0, len(FIRMWARE), DATA_OBJECT_MAX))

    def test_a_refused_init_packet_is_a_result(self):
        """A wrong key: OT-K-02, -03 and -09 expect InvalidObject."""
        target = SimulatedBootloader(refuse_init=(ResultCode.INVALID_OBJECT, None))
        stage, code, extended = dfu_over(target).send_image(DfuImage("application", INIT, FIRMWARE))
        assert (stage, code, extended) == ("init", ResultCode.INVALID_OBJECT, None)
        assert target.firmware == []

    @pytest.mark.parametrize("extended,text", [
        (0x05, "FwVersionFailure"),         # OT-K-10, a downgrade
        (0x06, "HwVersionFailure"),         # OT-K-08, another PCB
        (0x07, "SdVersionFailure"),         # OT-K-11, --sd-req 0xAE
    ])
    def test_an_extended_error_is_named(self, extended, text):
        target = SimulatedBootloader(refuse_init=(ResultCode.EXTENDED_ERROR, extended))
        stage, code, got = dfu_over(target).send_image(DfuImage("application", INIT, FIRMWARE))
        assert stage == "init" and got == extended
        assert result_text(code, got) == ("ExtendedError", text)

    def test_a_crc_that_does_not_match_raises(self):
        """A lost byte is a broken transfer, not a verdict on the package."""
        with pytest.raises(DfuError, match="CRC"):
            dfu_over(SimulatedBootloader(corrupt=True)).send_image(
                DfuImage("application", INIT, FIRMWARE))

    def test_an_answer_to_another_request_raises(self):
        with pytest.raises(DfuError, match="answered"):
            SecureDfu(control=lambda request, timeout: bytes([0x60, 0x99, 0x01]),
                      packet=lambda data: None).send_image(DfuImage("application", INIT, b"x"))

    def test_a_receipt_notification_setting_is_optional(self):
        """The reduced protocol may refuse it; the transfer goes on."""
        target = SimulatedBootloader(prn_supported=False)
        assert dfu_over(target).send_image(DfuImage("application", INIT, b"abc"))[0] == "done"

    def test_the_result_texts(self):
        assert ResultCode.SUCCESS.text == "Success"
        assert ResultCode.INVALID_OBJECT.text == "InvalidObject"
        assert ResultCode.OP_CODE_NOT_SUPPORTED.text == "OpcodeNotSupported"
        assert ExtendedError.HW_VERSION_FAILURE.text == "HwVersionFailure"
        assert result_text(0x77, None) == ("Unknown(0x77)", "")

    def test_a_chunk_beyond_a_write_is_refused(self):
        with pytest.raises(ConfigurationError):
            SecureDfu(control=lambda r, t: b"", packet=lambda d: None, chunk=245)


class TestPackages:
    def test_images_are_sent_in_nrfutil_s_order(self, tmp_path):
        path = make_package(tmp_path / "p.zip", [("application", b"a", b"A"),
                                                 ("softdevice_bootloader", b"s", b"S")])
        assert [image.kind for image in load_package(path)] == [
            "softdevice_bootloader", "application"]

    def test_a_file_that_is_not_a_package_is_refused(self, tmp_path):
        (tmp_path / "not.zip").write_text("hello")
        with pytest.raises(ConfigurationError, match="not a DFU package"):
            load_package(str(tmp_path / "not.zip"))


@pytest.fixture
def kepler_dongle():
    reset_world()
    simulator = SimulatedDongle()
    dongle = NordicDongle(MockTransport(responder=simulator), timeout=5.0)
    dongle.initialise()
    yield dongle, simulator
    dongle.close()
    reset_world()


def bootloader_of(simulator) -> SimulatedBootloader:
    return next(s for s in simulator.sensors if s.address == KEPLER_5C1712_DFU_ADDRESS).bootloader


def enter_bootloader(dongle):
    """SESSION SWDL over the application's link, as a Kepler spec does."""
    dongle.scan(5.0)
    dongle.select("D1:8D:3B:4C:19:96")
    dongle.open_link()
    assert dongle.command("SESSION SWDL", timeout=45.0).text == "ACK SESSION SWDL"
    dongle.close_link()


class TestSendPackage:
    def test_an_application_package_is_sent(self, kepler_dongle, tmp_path):
        dongle, simulator = kepler_dongle
        enter_bootloader(dongle)
        package = make_package(tmp_path / "app.zip", [("application", INIT, FIRMWARE)])
        result = dongle.send_package(package, "KAPPA_5C1712")
        assert result.result == "Success" and result.succeeded
        assert result.bytes_sent == len(INIT) + len(FIRMWARE)
        assert KEPLER_5C1712_DFU_NAME in result.target
        assert bootloader_of(simulator).firmware == [FIRMWARE]
        assert dongle.is_linked is False

    def test_a_refusal_is_reported_not_raised(self, kepler_dongle, tmp_path):
        dongle, simulator = kepler_dongle
        enter_bootloader(dongle)
        bootloader_of(simulator).refuse_init = (ResultCode.EXTENDED_ERROR, 0x06)
        package = make_package(tmp_path / "v5.zip", [("application", INIT, FIRMWARE)])
        result = dongle.send_package(package, "KAPPA_5C1712")
        assert (result.result, result.extended_error, result.stage) == (
            "ExtendedError", "HwVersionFailure", "init")
        assert not result.succeeded

    def test_each_image_of_a_package_has_its_own_link(self, kepler_dongle, tmp_path):
        dongle, simulator = kepler_dongle
        enter_bootloader(dongle)
        before = len(simulator.command_log)
        package = make_package(tmp_path / "bl.zip", [("softdevice_bootloader", INIT, b"S" * 5000),
                                                     ("application", INIT, FIRMWARE)])
        result = dongle.send_package(package, "KAPPA_5C1712")
        assert result.succeeded and result.images == ["softdevice_bootloader", "application"]
        connects = [line for line in simulator.command_log[before:] if line.startswith("connect")]
        assert len(connects) == 2
        assert bootloader_of(simulator).firmware == [b"S" * 5000, FIRMWARE]

    def test_the_target_can_be_its_address(self, kepler_dongle, tmp_path):
        dongle, _ = kepler_dongle
        enter_bootloader(dongle)
        package = make_package(tmp_path / "app.zip", [("application", INIT, b"abc")])
        assert dongle.send_package(package, KEPLER_5C1712_DFU_ADDRESS).succeeded

    def test_a_sensor_not_in_its_bootloader_is_not_found(self, kepler_dongle, tmp_path):
        dongle, _ = kepler_dongle
        package = make_package(tmp_path / "app.zip", [("application", INIT, b"abc")])
        with pytest.raises(InstrumentError, match="no bootloader matching 'KAPPA_5C1712'"):
            dongle.send_package(package, "KAPPA_5C1712", scan_seconds=2.0)

    def test_the_application_cannot_be_updated_over_its_uart_link(self, kepler_dongle):
        """dfucp needs a DFU service on the link: the application has none."""
        dongle, _ = kepler_dongle
        dongle.scan(5.0)
        dongle.select("D1:8D:3B:4C:19:96")
        dongle.open_link()
        reply = dongle.session.execute("dfucp", "0601", allow_error=True)
        assert not reply.ok and reply.error.name == "STATE"

    def test_entering_the_bootloader_is_a_kepler_command(self):
        reset_world()
        model = kepler_sensor()
        assert not model.in_bootloader
        assert model.respond("SESSION SWDL") == "ACK SESSION SWDL"
        reset_world()
