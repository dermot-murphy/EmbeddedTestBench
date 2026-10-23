"""Nordic Secure DFU over the dongle: the procedure, packages and send_package (#244).

Lost data and its retries: #271. A bootloader link that fails to establish: #275.

Traces to: BLE-FR-121, SWE4-UT-BLEDFU.
"""

from __future__ import annotations

import json
import zipfile

import pytest

from benchtools.core.errors import ConfigurationError, InstrumentError
from benchtools.core.transport.mock import MockTransport
from benchtools.instruments.nordic_dongle import NordicDongle, SimulatedDongle
from benchtools.instruments.nordic_dongle.constants import CONNECT_ATTEMPTS
from benchtools.instruments.nordic_dongle.dongle import LinkLostError
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
                     packet=target.packet, chunk=chunk, sleep=lambda seconds: None)


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


def take(target: SimulatedBootloader):
    """The receipts the target has sent since the last call."""
    def receipts():
        sent = list(target.receipts)
        target.receipts.clear()
        return sent
    return receipts


def dfu_checking(target: SimulatedBootloader, pauses=None, **options) -> SecureDfu:
    """A procedure that checks the target's receipts, as send_package's does.

    Each pause it would wait is recorded in *pauses* rather than slept.
    """
    waited = pauses if pauses is not None else []
    return SecureDfu(control=lambda request, timeout: target.control(request),
                     packet=target.packet, receipts=take(target), sleep=waited.append,
                     **options)


class TestLostData:
    """An SDK 15.2 bootloader at the minimum MTU lost a 20-byte piece (#271)."""

    def test_receipts_that_match_need_no_retry(self):
        target = SimulatedBootloader(prn_supported=True)
        dfu = dfu_checking(target, prn=2)
        assert dfu.send_image(DfuImage("application", INIT, FIRMWARE))[0] == "done"
        assert dfu.retries == 0
        assert target.firmware == [FIRMWARE]

    def test_a_lost_packet_is_found_at_its_receipt_and_the_image_sent_again(self):
        target = SimulatedBootloader(prn_supported=True, lose=(3,), refuse_recreate=True)
        reasons = []
        dfu = dfu_checking(target, prn=2, on_retry=reasons.append)
        assert dfu.send_image(DfuImage("application", INIT, FIRMWARE))[0] == "done"
        assert target.firmware == [FIRMWARE] and target.init_packets == [INIT, INIT]
        assert dfu.retries == 1
        assert len(reasons) == 1 and "receipt" in reasons[0] and "retry 1 of 3" in reasons[0]

    def test_the_image_stops_at_the_first_bad_receipt(self):
        """Packet 3 is the second of the first data object: its receipt is the
        first, so nothing more is sent before the init packet again."""
        target = SimulatedBootloader(prn_supported=True, lose=(3,))
        dfu_checking(target, prn=2).send_image(DfuImage("application", INIT, FIRMWARE))
        whole = 1 + sum(-(-min(DATA_OBJECT_MAX, len(FIRMWARE) - o) // 244)
                        for o in range(0, len(FIRMWARE), DATA_OBJECT_MAX))
        assert target.packets == whole + 3

    def test_a_lost_object_is_not_created_again(self):
        """5C1712's SDK 15.2 bootloader refused that with InvalidObject."""
        target = SimulatedBootloader(prn_supported=True, lose=(3,), refuse_recreate=True)
        dfu_checking(target, prn=2).send_image(DfuImage("application", INIT, FIRMWARE))
        data_creates = [r[0] for r in target.requests if r[:2] == bytes([0x01, 0x02])]
        assert len(data_creates) == 1 + -(-len(FIRMWARE) // DATA_OBJECT_MAX)

    def test_each_retry_waits_longer_after_each_data_create(self):
        """Nothing is lost on 5C1712 with 0.15 s after each create (#271)."""
        pauses = []
        # Each attempt writes the init packet, then the one data packet, which is lost.
        dfu = dfu_checking(SimulatedBootloader(lose=(2, 4, 6, 8)), pauses=pauses)
        with pytest.raises(DfuError):
            dfu.send_image(DfuImage("application", INIT, b"x" * 100))
        assert pauses == [0.15, 0.3, 0.6]

    def test_no_pause_until_a_loss(self):
        pauses = []
        dfu = dfu_checking(SimulatedBootloader(), pauses=pauses)
        assert dfu.send_image(DfuImage("application", INIT, FIRMWARE))[0] == "done"
        assert not pauses and dfu.create_pause == 0.0

    def test_a_pause_can_be_asked_for_from_the_start(self):
        pauses = []
        dfu = dfu_checking(SimulatedBootloader(), pauses=pauses, create_pause=0.2)
        dfu.send_image(DfuImage("application", INIT, FIRMWARE))
        assert pauses == [0.2] * -(-len(FIRMWARE) // DATA_OBJECT_MAX)

    def test_without_receipts_the_object_s_crc_finds_the_loss(self):
        target = SimulatedBootloader(lose=(5,))
        dfu = SecureDfu(control=lambda request, timeout: target.control(request),
                        packet=target.packet, sleep=lambda seconds: None)
        assert dfu.send_image(DfuImage("application", INIT, FIRMWARE))[0] == "done"
        assert dfu.retries == 1
        assert target.firmware == [FIRMWARE]

    def test_a_lost_init_packet_is_sent_again(self):
        target = SimulatedBootloader(prn_supported=True, lose=(1,))
        dfu = dfu_checking(target, prn=1)
        assert dfu.send_image(DfuImage("application", INIT, FIRMWARE))[0] == "done"
        assert target.init_packets == [INIT] and dfu.retries == 1

    def test_a_receipt_that_goes_back_is_a_loss(self):
        """5C1712 answered offset 0 and CRC 0 after a good receipt, where it
        had lost a piece."""
        target = SimulatedBootloader(prn_supported=True, lose=(5,))
        reasons = []
        dfu = dfu_checking(target, prn=2, on_retry=reasons.append)
        assert dfu.send_image(DfuImage("application", INIT, FIRMWARE))[0] == "done"
        assert "offset 0 after offset 488" in reasons[0]

    def test_a_receipt_from_before_the_object_is_not_checked(self):
        target = SimulatedBootloader(prn_supported=True)
        dfu = dfu_checking(target, prn=1)
        target.receipts.append(bytes([0x60, 0x03, 0x01]) + bytes(8))
        assert dfu.send_image(DfuImage("application", INIT, b"x" * 600))[0] == "done"
        assert dfu.retries == 0

    def test_still_lost_after_every_retry_raises(self):
        with pytest.raises(DfuError, match="still lost after 3 retries"):
            dfu_checking(SimulatedBootloader(corrupt=True)).send_image(
                DfuImage("application", INIT, FIRMWARE))

    def test_no_retries_fails_at_the_first_loss(self):
        target = SimulatedBootloader(prn_supported=True, lose=(3,))
        with pytest.raises(DfuError, match="still lost after 0 retries"):
            dfu_checking(target, prn=2, retries=0).send_image(
                DfuImage("application", INIT, FIRMWARE))

    def test_retries_cannot_be_negative(self):
        with pytest.raises(ConfigurationError):
            SecureDfu(control=lambda r, t: b"", packet=lambda d: None, retries=-1)

    def test_a_pause_cannot_be_negative(self):
        with pytest.raises(ConfigurationError):
            SecureDfu(control=lambda r, t: b"", packet=lambda d: None, create_pause=-0.1)


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


def bootloader_sensor(simulator):
    """The simulated 5C1712 as its bootloader advertises it."""
    return next(s for s in simulator.sensors if s.address == KEPLER_5C1712_DFU_ADDRESS)


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

    def test_lost_data_is_sent_again_and_counted(self, kepler_dongle, tmp_path):
        """The receipts reach the host as +rx events (#271)."""
        dongle, simulator = kepler_dongle
        enter_bootloader(dongle)
        target = bootloader_of(simulator)
        target.prn_supported = True
        target.lose = (12,)
        package = make_package(tmp_path / "app.zip", [("application", INIT, FIRMWARE)])
        result = dongle.send_package(package, "KAPPA_5C1712")
        assert result.succeeded and result.retries == 1
        assert result.as_dict()["retries"] == 1
        assert target.firmware == [FIRMWARE]
        assert result.bytes_sent > len(INIT) + len(FIRMWARE)

    def test_a_bootloader_link_that_fails_to_establish_is_tried_again(
            self, kepler_dongle, tmp_path, caplog):
        """Seen twice in one Kepler run: linked, then lost with 0x3E (#275)."""
        dongle, simulator = kepler_dongle
        enter_bootloader(dongle)
        bootloader_sensor(simulator).not_established = 2
        package = make_package(tmp_path / "app.zip", [("application", INIT, FIRMWARE)])
        with caplog.at_level("WARNING"):
            result = dongle.send_package(package, "KAPPA_5C1712")
        assert result.succeeded and bootloader_of(simulator).firmware == [FIRMWARE]
        attempts = [record for record in caplog.records
                    if getattr(record, "event_kind", None) == "ble_connect_attempt"]
        assert [record.event_data["attempt"] for record in attempts] == [1, 2]
        assert all(record.event_data["address"] == KEPLER_5C1712_DFU_ADDRESS
                   and record.event_data["reason"] == "0x3e" for record in attempts)

    def test_each_failed_bootloader_link_is_in_the_session_log(self, kepler_dongle, tmp_path):
        dongle, simulator = kepler_dongle
        enter_bootloader(dongle)
        path = tmp_path / "ble.log"
        dongle.start_log(str(path))
        bootloader_sensor(simulator).not_established = 1
        package = make_package(tmp_path / "app.zip", [("application", INIT, b"abc")])
        assert dongle.send_package(package, "KAPPA_5C1712").succeeded
        dongle.stop_log()
        assert "attempt 1 of %d" % CONNECT_ATTEMPTS in path.read_text()

    def test_a_bootloader_link_gives_up_after_the_attempts_allowed(self, kepler_dongle, tmp_path):
        dongle, simulator = kepler_dongle
        enter_bootloader(dongle)
        bootloader_sensor(simulator).not_established = 5
        package = make_package(tmp_path / "app.zip", [("application", INIT, b"abc")])
        with pytest.raises(LinkLostError, match="reason 0x3e") as caught:
            dongle.send_package(package, "KAPPA_5C1712")
        assert caught.value.not_established
        assert bootloader_sensor(simulator).not_established == 5 - CONNECT_ATTEMPTS
        assert dongle.is_linked is False

    def test_the_bootloader_link_attempts_can_be_set(self, kepler_dongle, tmp_path):
        dongle, simulator = kepler_dongle
        enter_bootloader(dongle)
        bootloader_sensor(simulator).not_established = 1
        package = make_package(tmp_path / "app.zip", [("application", INIT, b"abc")])
        with pytest.raises(LinkLostError):
            dongle.send_package(package, "KAPPA_5C1712", connect_attempts=1)
        assert bootloader_sensor(simulator).not_established == 0

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
