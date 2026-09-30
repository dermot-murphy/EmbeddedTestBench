/**
 * @file test_cmd_parser.c
 * @brief Line assembly and the command set, end to end through the fake HAL.
 *
 * Traces to: PICO-FR-001 .. PICO-FR-005, PICO-FR-020, PICO-FR-024,
 *            PICO-FR-030, PICO-DD-PARSER, SWE4-UT-PICOFW.
 */

#include "unity.h"

#include <string.h>

#include "cmd_parser.h"
#include "fake_hal.h"
#include "firmware_version.h"
#include "sht30.h"

static cmd_line_t	line;

void setUp(void)
{
	fake_hal_reset();
	cmd_line_init(&line);
}

void tearDown(void)
{
}

/* Feed @p text through line assembly, executing each complete line. */
static void test_feed(const char *text)
{
	const char	*cursor = text;

	while (*cursor != '\0')
	{
		cmd_line_result_t	result = cmd_line_push(&line, *cursor);

		if (result == CMD_LINE_RESULT_READY)
		{
			cmd_execute(line.text);
		}
		else if (result == CMD_LINE_RESULT_OVERFLOW)
		{
			cmd_report_overflow();
		}
		else
		{
			/* Assembling. */
		}
		cursor++;
	}
}

static void test_expect_in(const char *needle, const char *haystack)
{
	if (strstr(haystack, needle) == NULL)
	{
		char	message[FAKE_MAX_LINE + 64];

		(void)strcpy(message, "expected \"");
		(void)strcat(message, needle);
		(void)strcat(message, "\" in the reply");
		TEST_FAIL_MESSAGE(message);
	}
}

/* --- line assembly ------------------------------------------------------ */
static void test_a_line_is_ready_at_lf(void)
{
	TEST_ASSERT_EQUAL(CMD_LINE_RESULT_PENDING, cmd_line_push(&line, 'v'));
	TEST_ASSERT_EQUAL(CMD_LINE_RESULT_PENDING, cmd_line_push(&line, 'e'));
	TEST_ASSERT_EQUAL(CMD_LINE_RESULT_PENDING, cmd_line_push(&line, 'r'));
	TEST_ASSERT_EQUAL(CMD_LINE_RESULT_READY, cmd_line_push(&line, '\n'));
	TEST_ASSERT_EQUAL_STRING("ver", line.text);
}

static void test_cr_is_ignored(void)
{
	TEST_ASSERT_EQUAL(CMD_LINE_RESULT_PENDING, cmd_line_push(&line, 'a'));
	TEST_ASSERT_EQUAL(CMD_LINE_RESULT_PENDING, cmd_line_push(&line, '\r'));
	TEST_ASSERT_EQUAL(CMD_LINE_RESULT_READY, cmd_line_push(&line, '\n'));
	TEST_ASSERT_EQUAL_STRING("a", line.text);
}

static void test_an_over_length_line_is_dropped_whole(void)
{
	uint32_t	index;

	for (index = 0U; index < (PROTO_MAX_LINE + 10U); index++)
	{
		TEST_ASSERT_EQUAL(CMD_LINE_RESULT_PENDING, cmd_line_push(&line, 't'));
	}
	TEST_ASSERT_EQUAL(CMD_LINE_RESULT_OVERFLOW, cmd_line_push(&line, '\n'));
	TEST_ASSERT_EQUAL_STRING("", line.text);
}

static void test_the_line_after_an_overflow_is_accepted(void)
{
	uint32_t	index;

	for (index = 0U; index < (PROTO_MAX_LINE * 2U); index++)
	{
		(void)cmd_line_push(&line, 'x');
	}
	(void)cmd_line_push(&line, '\n');
	(void)cmd_line_push(&line, 'o');
	TEST_ASSERT_EQUAL(CMD_LINE_RESULT_READY, cmd_line_push(&line, '\n'));
	TEST_ASSERT_EQUAL_STRING("o", line.text);
}

static void test_the_longest_line_that_fits_is_ready(void)
{
	uint32_t	index;

	for (index = 0U; index < (PROTO_MAX_LINE - 1U); index++)
	{
		(void)cmd_line_push(&line, 'y');
	}
	TEST_ASSERT_EQUAL(CMD_LINE_RESULT_READY, cmd_line_push(&line, '\n'));
	TEST_ASSERT_EQUAL_UINT32(PROTO_MAX_LINE - 1U, (uint32_t)strlen(line.text));
}

static void test_an_overflow_is_reported(void)
{
	uint32_t	index;

	for (index = 0U; index < PROTO_MAX_LINE; index++)
	{
		test_feed("z");
	}
	test_feed("\n");
	TEST_ASSERT_EQUAL_STRING("err 3 line too long", fake_hal_last_line());
}

/* --- dispatch ----------------------------------------------------------- */
static void test_a_blank_line_has_no_reply(void)
{
	test_feed("\n   \n\t\n");
	TEST_ASSERT_EQUAL_UINT32(0U, fake_hal_line_count());
}

static void test_an_unknown_command_is_refused(void)
{
	test_feed("fly\n");
	TEST_ASSERT_EQUAL_STRING("err 1 unknown command", fake_hal_last_line());
}

static void test_commands_are_case_sensitive(void)
{
	test_feed("VER\n");
	TEST_ASSERT_EQUAL_STRING("err 1 unknown command", fake_hal_last_line());
}

static void test_an_unexpected_argument_is_refused(void)
{
	test_feed("temp now\n");
	TEST_ASSERT_EQUAL_STRING("err 2 wrong number of arguments", fake_hal_last_line());
	TEST_ASSERT_EQUAL_UINT32(0U, fake_hal_write_count());
}

static void test_more_tokens_than_are_stored_is_still_refused(void)
{
	test_feed("temp a b c d e f\n");
	TEST_ASSERT_EQUAL_STRING("err 2 wrong number of arguments", fake_hal_last_line());
}

static void test_surrounding_whitespace_is_ignored(void)
{
	fake_hal_queue_measurement(0x6666U, 0x6666U);
	test_feed("  \ttemp  \r\n");
	test_expect_in("ok t=25.000", fake_hal_last_line());
}

static void test_error_text_out_of_range(void)
{
	TEST_ASSERT_EQUAL_STRING("unknown error", proto_error_text(PROTO_ERR_LIMIT));
	TEST_ASSERT_EQUAL_STRING("ok", proto_error_text(PROTO_ERR_NONE));
}

/* --- ver ---------------------------------------------------------------- */
static void test_ver_reports_title_and_version(void)
{
	test_feed("ver\n");
	TEST_ASSERT_EQUAL_UINT32(1U, fake_hal_line_count());
	TEST_ASSERT_EQUAL_STRING_LEN("ok title=", fake_hal_last_line(), 9U);
	test_expect_in("title=" FIRMWARE_TITLE " ", fake_hal_last_line());
	test_expect_in(" fw=" FIRMWARE_VERSION " ", fake_hal_last_line());
}

static void test_ver_reports_the_rest_of_the_identity(void)
{
	fake_hal_set_uptime_us(90500000ULL);
	test_feed("ver\n");
	test_expect_in(" built=", fake_hal_last_line());
	test_expect_in(" proto=" PROTO_VERSION " ", fake_hal_last_line());
	test_expect_in(" board=pico2 ", fake_hal_last_line());
	test_expect_in(" serial=" FAKE_BOARD_ID " ", fake_hal_last_line());
	test_expect_in(" sensor=SHT30-DIS ", fake_hal_last_line());
	test_expect_in(" addr=0x44 ", fake_hal_last_line());
	test_expect_in(" uptime_s=90", fake_hal_last_line());
}

static void test_ver_does_not_touch_the_sensor(void)
{
	/* A Pico with no sensor must still say what it is. */
	test_feed("ver\n");
	TEST_ASSERT_EQUAL_UINT32(0U, fake_hal_write_count());
	TEST_ASSERT_EQUAL_UINT32(0U, fake_hal_read_count());
}

static void test_ver_has_no_spaces_inside_values(void)
{
	const char	*reply;
	uint32_t	equals = 0U;
	uint32_t	spaces = 0U;

	test_feed("ver\n");
	reply = fake_hal_last_line();
	for (; *reply != '\0'; reply++)
	{
		equals += (*reply == '=') ? 1U : 0U;
		spaces += (*reply == ' ') ? 1U : 0U;
	}
	/* "ok" then one space before each key=value token. */
	TEST_ASSERT_EQUAL_UINT32(equals, spaces);
}

/* --- temp --------------------------------------------------------------- */
static void test_temp_reports_temperature_and_humidity(void)
{
	fake_hal_queue_measurement(0x6666U, 0x8000U);
	test_feed("temp\n");
	TEST_ASSERT_EQUAL_STRING("ok t=25.000 rh=50.001 raw_t=0x6666 raw_rh=0x8000",
				 fake_hal_last_line());
}

static void test_temp_below_zero(void)
{
	fake_hal_queue_measurement(0x4000U, 0x0000U);
	test_feed("temp\n");
	TEST_ASSERT_EQUAL_STRING("ok t=-1.249 rh=0.000 raw_t=0x4000 raw_rh=0x0000",
				 fake_hal_last_line());
}

static void test_temp_with_no_sensor(void)
{
	fake_hal_fail_next_write(HAL_STATUS_ERR_NACK);
	test_feed("temp\n");
	TEST_ASSERT_EQUAL_STRING("err 4 the sensor did not acknowledge", fake_hal_last_line());
}

static void test_temp_with_a_corrupted_frame(void)
{
	static const uint8_t	frame[6] = { 0x66U, 0x66U, 0x00U, 0x66U, 0x66U, 0x93U };

	fake_hal_queue_read(frame, 6U, HAL_STATUS_OK);
	test_feed("temp\n");
	TEST_ASSERT_EQUAL_STRING("err 5 the sensor checksum did not match", fake_hal_last_line());
}

static void test_temp_with_a_bus_timeout(void)
{
	fake_hal_fail_next_write(HAL_STATUS_ERR_TIMEOUT);
	test_feed("temp\n");
	TEST_ASSERT_EQUAL_STRING("err 6 I2C bus timeout", fake_hal_last_line());
}

/* --- status and sreset -------------------------------------------------- */
static void test_status_reports_the_register(void)
{
	uint8_t	word[3] = { 0x80U, 0x10U, 0x00U };

	word[2] = sht30_crc8(word, 2U);
	fake_hal_queue_read(word, 3U, HAL_STATUS_OK);
	test_feed("status\n");
	TEST_ASSERT_EQUAL_STRING("ok status=0x8010", fake_hal_last_line());
}

static void test_status_with_no_sensor(void)
{
	fake_hal_fail_next_write(HAL_STATUS_ERR_NACK);
	test_feed("status\n");
	TEST_ASSERT_EQUAL_STRING("err 4 the sensor did not acknowledge", fake_hal_last_line());
}

static void test_sreset(void)
{
	test_feed("sreset\n");
	TEST_ASSERT_EQUAL_STRING("ok", fake_hal_last_line());
	TEST_ASSERT_EQUAL_HEX8(0x30U, fake_hal_write_bytes(0U)[0]);
	TEST_ASSERT_EQUAL_HEX8(0xA2U, fake_hal_write_bytes(0U)[1]);
}

/* --- reset and bootsel -------------------------------------------------- */
static void test_reset_replies_before_rebooting(void)
{
	test_feed("reset\n");
	TEST_ASSERT_EQUAL_STRING("ok", fake_hal_last_line());
	TEST_ASSERT_EQUAL_UINT32(1U, fake_hal_reboot_count());
	TEST_ASSERT_EQUAL_UINT32(1U, fake_hal_lines_at_reboot());
	TEST_ASSERT_EQUAL_UINT32(0U, fake_hal_bootloader_count());
}

static void test_bootsel_replies_before_rebooting(void)
{
	test_feed("bootsel\n");
	TEST_ASSERT_EQUAL_STRING("ok", fake_hal_last_line());
	TEST_ASSERT_EQUAL_UINT32(1U, fake_hal_bootloader_count());
	TEST_ASSERT_EQUAL_UINT32(1U, fake_hal_lines_at_reboot());
	TEST_ASSERT_EQUAL_UINT32(0U, fake_hal_reboot_count());
}

static void test_a_refused_reset_does_not_reboot(void)
{
	test_feed("reset now\n");
	TEST_ASSERT_EQUAL_UINT32(0U, fake_hal_reboot_count());
	test_feed("ver\n");
	TEST_ASSERT_EQUAL_UINT32(0U, fake_hal_reboot_count());
}

/* --- help --------------------------------------------------------------- */
static void test_help_lists_every_command_then_ok(void)
{
	test_feed("help\n");
	TEST_ASSERT_EQUAL_UINT32(8U, fake_hal_line_count());
	TEST_ASSERT_EQUAL_STRING_LEN("# help - ", fake_hal_line(0U), 9U);
	test_expect_in("# ver - ", fake_hal_line(1U));
	test_expect_in("# temp - ", fake_hal_line(2U));
	test_expect_in("# bootsel - ", fake_hal_line(6U));
	TEST_ASSERT_EQUAL_STRING("ok", fake_hal_last_line());
}

int main(void)
{
	UNITY_BEGIN();
	RUN_TEST(test_a_line_is_ready_at_lf);
	RUN_TEST(test_cr_is_ignored);
	RUN_TEST(test_an_over_length_line_is_dropped_whole);
	RUN_TEST(test_the_line_after_an_overflow_is_accepted);
	RUN_TEST(test_the_longest_line_that_fits_is_ready);
	RUN_TEST(test_an_overflow_is_reported);
	RUN_TEST(test_a_blank_line_has_no_reply);
	RUN_TEST(test_an_unknown_command_is_refused);
	RUN_TEST(test_commands_are_case_sensitive);
	RUN_TEST(test_an_unexpected_argument_is_refused);
	RUN_TEST(test_more_tokens_than_are_stored_is_still_refused);
	RUN_TEST(test_surrounding_whitespace_is_ignored);
	RUN_TEST(test_error_text_out_of_range);
	RUN_TEST(test_ver_reports_title_and_version);
	RUN_TEST(test_ver_reports_the_rest_of_the_identity);
	RUN_TEST(test_ver_does_not_touch_the_sensor);
	RUN_TEST(test_ver_has_no_spaces_inside_values);
	RUN_TEST(test_temp_reports_temperature_and_humidity);
	RUN_TEST(test_temp_below_zero);
	RUN_TEST(test_temp_with_no_sensor);
	RUN_TEST(test_temp_with_a_corrupted_frame);
	RUN_TEST(test_temp_with_a_bus_timeout);
	RUN_TEST(test_status_reports_the_register);
	RUN_TEST(test_status_with_no_sensor);
	RUN_TEST(test_sreset);
	RUN_TEST(test_reset_replies_before_rebooting);
	RUN_TEST(test_bootsel_replies_before_rebooting);
	RUN_TEST(test_a_refused_reset_does_not_reboot);
	RUN_TEST(test_help_lists_every_command_then_ok);
	return UNITY_END();
}
