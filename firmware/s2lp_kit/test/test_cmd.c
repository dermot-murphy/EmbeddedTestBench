/**
 * @file test_cmd.c
 * @brief The host's commands and the record lines (#84).
 */

#include <string.h>

#include "unity.h"

#include "cmd.h"
#include "fake_hal.h"
#include "ring.h"
#include "rx.h"
#include "s2lp.h"

void setUp(void)
{
	fake_hal_reset();
	ring_reset();
}

void tearDown(void)
{
	rx_stop();
}

static void test_cmd_run(const char *command)
{
	char line[PROTO_LINE_MAX + 1U];

	(void)strncpy(line, command, PROTO_LINE_MAX);
	line[PROTO_LINE_MAX] = '\0';
	fake_hal_clear_output();
	cmd_handle_line(line);
}

static void test_id_names_firmware_protocol_and_silicon(void)
{
	test_cmd_run("id");
	TEST_ASSERT_EQUAL_STRING("ok etb-s2lp-kit V1.00.0000 proto=1 silicon=c1\r\n",
		fake_hal_output());
}

static void test_wr_then_rd(void)
{
	test_cmd_run("wr 50 0000aa43");
	TEST_ASSERT_EQUAL_STRING("ok\r\n", fake_hal_output());
	TEST_ASSERT_EQUAL_HEX8(0xAAU, fake_hal_register(0x52U));
	test_cmd_run("rd 50 4");
	TEST_ASSERT_EQUAL_STRING("ok 0000aa43\r\n", fake_hal_output());
	test_cmd_run("rd 0x50 4");
	TEST_ASSERT_EQUAL_STRING("err bad argument\r\n", fake_hal_output());
}

static void test_bad_arguments_are_refused(void)
{
	static const char *const bad[] = {
		"rd 50", "rd 50 0", "rd 50 129", "rd 1ff 1", "rd zz 1",
		"wr 50", "wr 50 abc", "wr 50 0g", "cmd", "cmd 100",
		"sdn 2", "rx", "rx go", "rx start 1,2,3,4,5,6,7,8,9", "rx start a2,,9f",
		"rd 50 4 extra extra",
	};
	uint32_t index;

	for (index = 0U; index < (sizeof(bad) / sizeof(bad[0])); index++)
	{
		test_cmd_run(bad[index]);
		TEST_ASSERT_EQUAL_STRING_MESSAGE("err bad argument\r\n", fake_hal_output(), bad[index]);
	}
	test_cmd_run("help");
	TEST_ASSERT_EQUAL_STRING("err unknown command\r\n", fake_hal_output());
	test_cmd_run("   ");
	TEST_ASSERT_EQUAL_STRING("", fake_hal_output());
}

static void test_cmd_strobes_and_reports_status(void)
{
	test_cmd_run("cmd 62");
	TEST_ASSERT_EQUAL_STRING("ok 5207\r\n", fake_hal_output());
	TEST_ASSERT_EQUAL_HEX8(0x62U, fake_hal_command(0U));
}

static void test_sdn(void)
{
	test_cmd_run("sdn 1");
	TEST_ASSERT_TRUE(fake_hal_shutdown());
	test_cmd_run("sdn 0");
	TEST_ASSERT_FALSE(fake_hal_shutdown());
	TEST_ASSERT_EQUAL_STRING("ok\r\n", fake_hal_output());
}

static void test_receiving_refuses_register_access_but_answers_stat(void)
{
	test_cmd_run("rx start a2,9f");
	TEST_ASSERT_EQUAL_STRING("ok\r\n", fake_hal_output());
	test_cmd_run("rd 50 1");
	TEST_ASSERT_EQUAL_STRING("err receiving\r\n", fake_hal_output());
	test_cmd_run("stat");
	TEST_ASSERT_EQUAL_STRING(
		"ok running=1 frames=0 rejects=0 overflows=0 deaf_max_us=0 queued=0 uart_overruns=0\r\n",
		fake_hal_output());
	test_cmd_run("rx stop");
	TEST_ASSERT_EQUAL_STRING("ok frames=0 rejects=0 overflows=0 deaf_max_us=0\r\n",
		fake_hal_output());
	test_cmd_run("rd 50 1");
	TEST_ASSERT_EQUAL_STRING("ok 00\r\n", fake_hal_output());
}

static void test_rx_stop_sends_what_is_queued_before_its_answer(void)
{
	const uint8_t payload[] = {0x5CU, 0x17U};

	test_cmd_run("rx start");
	fake_hal_set_time(5U);
	fake_hal_queue_frame(payload, 2U);
	fake_hal_raise_irq(S2LP_IRQ_RX_DATA_READY);
	rx_on_irq();
	fake_hal_raise_irq(S2LP_IRQ_RX_DATA_DISC);
	rx_on_irq();
	test_cmd_run("rx stop");
	/* The fake board takes 1 us per SPI byte: the frame's interrupt, at 5 us,
	   takes 17 bytes, so the rejection's is at 22 us. */
	TEST_ASSERT_EQUAL_STRING("f 0 5 2 - 5c17\r\nr 1 22 00000002\r\n"
		"ok frames=1 rejects=1 overflows=0 deaf_max_us=17\r\n", fake_hal_output());
	TEST_ASSERT_EQUAL_UINT32(0U, ring_count());
}

static void test_a_line_too_long_is_refused(void)
{
	fake_hal_clear_output();
	cmd_line_too_long();
	TEST_ASSERT_EQUAL_STRING("err line too long\r\n", fake_hal_output());
}

static void test_record_lines(void)
{
	char out[CMD_OUT_MAX];
	ring_record_t record;
	uint32_t length;

	(void)memset(&record, 0, sizeof(record));
	record.kind = PROTO_KIND_FRAME;
	record.seq = 7U;
	record.time_us = 4000000123U;
	record.length = 3U;
	record.payload[0] = 0x5CU;
	record.payload[1] = 0x17U;
	record.payload[2] = 0x12U;
	record.register_count = 2U;
	record.registers[0] = 0x41U;
	record.registers[1] = 0x30U;
	length = cmd_format_record(&record, out);
	out[length] = '\0';
	TEST_ASSERT_EQUAL_STRING("f 7 4000000123 3 4130 5c1712\r\n", out);

	record.register_count = 0U;
	length = cmd_format_record(&record, out);
	out[length] = '\0';
	TEST_ASSERT_EQUAL_STRING("f 7 4000000123 3 - 5c1712\r\n", out);

	record.kind = PROTO_KIND_REJECT;
	record.irq = 0x12U;
	length = cmd_format_record(&record, out);
	out[length] = '\0';
	TEST_ASSERT_EQUAL_STRING("r 7 4000000123 00000012\r\n", out);
}

static void test_a_full_frame_fits_the_line(void)
{
	char out[CMD_OUT_MAX];
	ring_record_t record;
	uint32_t length;

	(void)memset(&record, 0xFF, sizeof(record));
	record.kind = PROTO_KIND_FRAME;
	record.length = PROTO_MAX_PAYLOAD;
	record.register_count = PROTO_MAX_REGISTERS;
	length = cmd_format_record(&record, out);
	TEST_ASSERT_EQUAL_INT('\n', out[length - 1U]);
	/* "f " 2, seq 10, " " 1, time 10, " " 1, length 3, " " 1, registers 16, " " 1, payload 256, CRLF 2 */
	TEST_ASSERT_EQUAL_UINT32(303U, length);
}

int main(void)
{
	UNITY_BEGIN();
	RUN_TEST(test_id_names_firmware_protocol_and_silicon);
	RUN_TEST(test_wr_then_rd);
	RUN_TEST(test_bad_arguments_are_refused);
	RUN_TEST(test_cmd_strobes_and_reports_status);
	RUN_TEST(test_sdn);
	RUN_TEST(test_receiving_refuses_register_access_but_answers_stat);
	RUN_TEST(test_rx_stop_sends_what_is_queued_before_its_answer);
	RUN_TEST(test_a_line_too_long_is_refused);
	RUN_TEST(test_record_lines);
	RUN_TEST(test_a_full_frame_fits_the_line);
	return UNITY_END();
}
