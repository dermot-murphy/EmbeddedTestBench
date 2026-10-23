/**
 * @file test_cmd_dfu.c
 * @brief The dfucp and dfupkt commands, through the dispatcher (#244).
 *
 * Kept apart from test_cmd_parser.c, which they would take past the 800-line
 * limit (ETB-STY-001 6.4). The client underneath is a fake; it is tested in
 * test_dfu_client.c.
 *
 * Traces to: BLE-FR-121, BLE-DD-DFU, SWE4-UT-BLEDFU.
 */

#include <stdio.h>
#include <string.h>

#include "unity.h"

#include "cmd_parser.h"
#include "fakes.h"
#include "nrf_error.h"
#include "protocol.h"

/** Run a command line through the parser, as the main loop would. */
static void test_handle(const char * line)
{
	char buffer[PROTO_MAX_LINE];

	(void)strncpy(buffer, line, sizeof(buffer) - 1U);
	buffer[sizeof(buffer) - 1U] = '\0';
	cmd_parser_handle(buffer);
}

/** The reply is the last line, since events precede it. */
static const char * test_reply(void)
{
	return fake_last_line();
}

void setUp(void)
{
	fake_lines_reset();
	fake_clock_reset();
	fake_scanner_reset();
	fake_nus_client_reset();
	fake_dfu_reset();
	TEST_ASSERT_TRUE_MESSAGE(cmd_parser_init(),
				 "every documented command must have a handler");
}

void tearDown(void)
{
}

static void test_dfucp_reports_the_control_point_response(void)
{
	static const uint8_t answer[] = { 0x60U, 0x06U, 0x01U };

	fake_dfu_set_ready(true);
	fake_dfu_set_response(answer, sizeof(answer));
	test_handle("dfucp 0601");
	TEST_ASSERT_EQUAL_STRING("ok len=3 data=600601", test_reply());
	TEST_ASSERT_EQUAL_UINT16(2U, fake_dfu_last_length());
	TEST_ASSERT_EQUAL_HEX8(0x06U, fake_dfu_last()[0]);
	TEST_ASSERT_EQUAL_UINT32(2000U, fake_dfu_last_timeout_ms());
}

static void test_dfucp_takes_a_timeout(void)
{
	static const uint8_t answer[] = { 0x60U, 0x04U, 0x01U };

	fake_dfu_set_ready(true);
	fake_dfu_set_response(answer, sizeof(answer));
	test_handle("dfucp 04 timeout=30000");
	TEST_ASSERT_EQUAL_UINT32(30000U, fake_dfu_last_timeout_ms());
	test_handle("dfucp 04 timeout=ten");
	TEST_ASSERT_EQUAL_STRING("err 3 bad argument value", test_reply());
}

static void test_dfucp_with_no_response_is_a_timeout(void)
{
	fake_dfu_set_ready(true);
	test_handle("dfucp 04");
	TEST_ASSERT_EQUAL_STRING("err 8 the sensor did not reply", test_reply());
}

static void test_dfu_commands_need_a_dfu_service(void)
{
	test_handle("dfucp 0601");
	TEST_ASSERT_EQUAL_STRING("err 4 not valid in this state", test_reply());
	test_handle("dfupkt 00");
	TEST_ASSERT_EQUAL_STRING("err 4 not valid in this state", test_reply());
}

static void test_dfupkt_writes_the_packet(void)
{
	fake_dfu_set_ready(true);
	test_handle("dfupkt 010203");
	TEST_ASSERT_EQUAL_STRING("ok len=3", test_reply());
	TEST_ASSERT_EQUAL_UINT32(1U, fake_dfu_packets());
}

static void test_dfupkt_reports_a_full_queue_as_busy(void)
{
	fake_dfu_set_ready(true);
	fake_dfu_set_packet_result(NRF_ERROR_RESOURCES);
	test_handle("dfupkt 01");
	TEST_ASSERT_EQUAL_STRING("err 7 busy", test_reply());
}

static void test_dfu_commands_refuse_bad_hex(void)
{
	fake_dfu_set_ready(true);
	test_handle("dfupkt zz");
	TEST_ASSERT_EQUAL_STRING("err 9 payload too long", test_reply());
	test_handle("dfucp 123");
	TEST_ASSERT_EQUAL_STRING("err 9 payload too long", test_reply());
}

int main(void)
{
	UNITY_BEGIN();
	RUN_TEST(test_dfucp_reports_the_control_point_response);
	RUN_TEST(test_dfucp_takes_a_timeout);
	RUN_TEST(test_dfucp_with_no_response_is_a_timeout);
	RUN_TEST(test_dfu_commands_need_a_dfu_service);
	RUN_TEST(test_dfupkt_writes_the_packet);
	RUN_TEST(test_dfupkt_reports_a_full_queue_as_busy);
	RUN_TEST(test_dfu_commands_refuse_bad_hex);
	return UNITY_END();
}
