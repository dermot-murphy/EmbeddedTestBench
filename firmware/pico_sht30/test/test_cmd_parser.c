/**
 * @file test_cmd_parser.c
 * @brief Line assembly and the command set, end to end through the fake HAL.
 *
 * Traces to: PICO-FR-001, PICO-FR-003, PICO-FR-004, PICO-FR-005,
 *            PICO-FR-006, PICO-FR-007, PICO-FR-020, PICO-FR-021,
 *            PICO-FR-023, PICO-FR-024, PICO-FR-025, PICO-FR-027,
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
	TEST_ASSERT_EQUAL(CMD_LINE_RESULT_PENDING, cmd_line_push(&line, 'r'));
	TEST_ASSERT_EQUAL(CMD_LINE_RESULT_PENDING, cmd_line_push(&line, 'd'));
	TEST_ASSERT_EQUAL(CMD_LINE_RESULT_READY, cmd_line_push(&line, '\n'));
	TEST_ASSERT_EQUAL_STRING("rd", line.text);
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
	test_feed("RD name\n");
	TEST_ASSERT_EQUAL_STRING("err 1 unknown command", fake_hal_last_line());
}

static void test_an_unexpected_argument_is_refused(void)
{
	test_feed("status now\n");
	TEST_ASSERT_EQUAL_STRING("err 2 wrong number of arguments", fake_hal_last_line());
	TEST_ASSERT_EQUAL_UINT32(0U, fake_hal_write_count());
}

static void test_more_tokens_than_are_stored_is_still_refused(void)
{
	test_feed("rd a b c d e f\n");
	TEST_ASSERT_EQUAL_STRING("err 2 wrong number of arguments", fake_hal_last_line());
}

static void test_surrounding_whitespace_is_ignored(void)
{
	fake_hal_queue_measurement(0x6666U, 0x6666U);
	test_feed("  \trd  temperature \r\n");
	TEST_ASSERT_EQUAL_STRING("ACK rd temperature = 25.00", fake_hal_last_line());
}

static void test_error_text_out_of_range(void)
{
	TEST_ASSERT_EQUAL_STRING("unknown error", proto_error_text(PROTO_ERR_LIMIT));
	TEST_ASSERT_EQUAL_STRING("ok", proto_error_text(PROTO_ERR_NONE));
}

/* --- commands removed in protocol 2.0 ------------------------------------ */
static void test_ver_temp_and_reset_are_no_longer_commands(void)
{
	/* Replaced by rd version, rd temperature and ecureset (#131). */
	test_feed("ver\n");
	TEST_ASSERT_EQUAL_STRING("err 1 unknown command", fake_hal_last_line());
	test_feed("temp\n");
	TEST_ASSERT_EQUAL_STRING("err 1 unknown command", fake_hal_last_line());
	test_feed("reset\n");
	TEST_ASSERT_EQUAL_STRING("err 1 unknown command", fake_hal_last_line());
	TEST_ASSERT_EQUAL_UINT32(3U, fake_hal_line_count());
	TEST_ASSERT_EQUAL_UINT32(0U, fake_hal_reboot_count());
	TEST_ASSERT_EQUAL_UINT32(0U, fake_hal_write_count());
}

/* --- rd: identity (PICO-FR-006) ------------------------------------------ */
static void test_rd_name(void)
{
	test_feed("rd name\n");
	TEST_ASSERT_EQUAL_UINT32(1U, fake_hal_line_count());
	TEST_ASSERT_EQUAL_STRING("ACK rd name = Pico 2 SHT30 Temperature Sensor",
				 fake_hal_last_line());
}

static void test_rd_copyright(void)
{
	test_feed("rd copyright\n");
	TEST_ASSERT_EQUAL_STRING("ACK rd copyright = (c) 2026 Dermot Murphy", fake_hal_last_line());
}

static void test_rd_version(void)
{
	test_feed("rd version\n");
	TEST_ASSERT_EQUAL_STRING("ACK rd version = V1.00.0000", fake_hal_last_line());
}

static void test_rd_sha_reports_the_injected_commit(void)
{
	/* The test build injects "0123abc", as the target build injects the
	 * output of git rev-parse --short=7 HEAD. */
	test_feed("rd sha\n");
	TEST_ASSERT_EQUAL_STRING("ACK rd sha = 0123abc", fake_hal_last_line());
	TEST_ASSERT_EQUAL_STRING(FIRMWARE_GIT_SHA, firmware_g_sha);
}

static void test_rd_identity_matches_the_header(void)
{
	TEST_ASSERT_EQUAL_STRING(FIRMWARE_NAME, firmware_g_name);
	TEST_ASSERT_EQUAL_STRING(FIRMWARE_COPYRIGHT, firmware_g_copyright);
	TEST_ASSERT_EQUAL_STRING(FIRMWARE_VERSION, firmware_g_version);
}

static void test_rd_identity_does_not_touch_the_sensor(void)
{
	/* A Pico with no sensor must still say what it is (PICO-FR-005). */
	test_feed("rd name\nrd copyright\nrd version\nrd sha\n");
	TEST_ASSERT_EQUAL_UINT32(4U, fake_hal_line_count());
	TEST_ASSERT_EQUAL_UINT32(0U, fake_hal_write_count());
	TEST_ASSERT_EQUAL_UINT32(0U, fake_hal_read_count());
}

/* --- rd: arguments and unknown options (PICO-FR-003, PICO-FR-007) -------- */
static void test_rd_without_an_option_is_refused(void)
{
	test_feed("rd\n");
	TEST_ASSERT_EQUAL_STRING("err 2 wrong number of arguments", fake_hal_last_line());
}

static void test_rd_with_two_options_is_refused(void)
{
	test_feed("rd name version\n");
	TEST_ASSERT_EQUAL_STRING("err 2 wrong number of arguments", fake_hal_last_line());
	TEST_ASSERT_EQUAL_UINT32(1U, fake_hal_line_count());
}

static void test_rd_unknown_option_is_a_nak(void)
{
	test_feed("rd humidity\n");
	TEST_ASSERT_EQUAL_STRING("NAK rd humidity = Error", fake_hal_last_line());
	TEST_ASSERT_EQUAL_UINT32(0U, fake_hal_write_count());
}

static void test_rd_options_are_case_sensitive(void)
{
	/* The NAK echoes the option exactly as it was received. */
	test_feed("rd Name\n");
	TEST_ASSERT_EQUAL_STRING("NAK rd Name = Error", fake_hal_last_line());
	test_feed("rd TEMPERATURE\n");
	TEST_ASSERT_EQUAL_STRING("NAK rd TEMPERATURE = Error", fake_hal_last_line());
	TEST_ASSERT_EQUAL_UINT32(0U, fake_hal_write_count());
}

static void test_rd_a_partial_option_is_a_nak(void)
{
	test_feed("rd temp\n");
	TEST_ASSERT_EQUAL_STRING("NAK rd temp = Error", fake_hal_last_line());
	test_feed("rd names\n");
	TEST_ASSERT_EQUAL_STRING("NAK rd names = Error", fake_hal_last_line());
}

static void test_rd_the_longest_option_is_echoed_whole(void)
{
	char		command[PROTO_MAX_LINE + 1U];
	char		expected[PROTO_MAX_REPLY];
	uint32_t	index;

	/* The longest line that fits: "rd " and an option filling the rest. */
	(void)strcpy(command, "rd ");
	for (index = 3U; index < (PROTO_MAX_LINE - 1U); index++)
	{
		command[index] = 'q';
	}
	command[PROTO_MAX_LINE - 1U] = '\n';
	command[PROTO_MAX_LINE] = '\0';
	(void)strcpy(expected, "NAK ");
	(void)strncat(expected, command, PROTO_MAX_LINE - 1U);
	(void)strcat(expected, " = Error");

	test_feed(command);
	TEST_ASSERT_EQUAL_STRING(expected, fake_hal_last_line());
}

/* --- rd temperature (PICO-FR-020, PICO-FR-027) --------------------------- */
static void test_rd_temperature_has_two_places(void)
{
	fake_hal_queue_measurement(0x6666U, 0x8000U);
	test_feed("rd temperature\n");
	TEST_ASSERT_EQUAL_STRING("ACK rd temperature = 25.00", fake_hal_last_line());
}

static void test_rd_temperature_is_rounded(void)
{
	/* 0x6340 converts to 22.848 degrees. */
	fake_hal_queue_measurement(0x6340U, 0x72F9U);
	test_feed("rd temperature\n");
	TEST_ASSERT_EQUAL_STRING("ACK rd temperature = 22.85", fake_hal_last_line());
}

static void test_rd_temperature_below_zero(void)
{
	/* 0x4000 converts to -1.249 degrees. */
	fake_hal_queue_measurement(0x4000U, 0x0000U);
	test_feed("rd temperature\n");
	TEST_ASSERT_EQUAL_STRING("ACK rd temperature = -1.25", fake_hal_last_line());
}

static void test_rd_temperature_just_below_zero_has_no_sign(void)
{
	/* 16851 ticks converts to -0.002 degrees, which rounds to zero. */
	fake_hal_queue_measurement(16851U, 0x0000U);
	test_feed("rd temperature\n");
	TEST_ASSERT_EQUAL_STRING("ACK rd temperature = 0.00", fake_hal_last_line());
}

static void test_rd_temperature_takes_one_measurement(void)
{
	fake_hal_queue_measurement(0x6666U, 0x8000U);
	test_feed("rd temperature\n");
	TEST_ASSERT_EQUAL_UINT32(1U, fake_hal_write_count());
	TEST_ASSERT_EQUAL_UINT32(1U, fake_hal_read_count());
}

static void test_rd_temperature_with_no_sensor(void)
{
	fake_hal_fail_next_write(HAL_STATUS_ERR_NACK);
	test_feed("rd temperature\n");
	TEST_ASSERT_EQUAL_STRING("ACK rd temperature = Error", fake_hal_last_line());
	TEST_ASSERT_EQUAL_UINT32(1U, fake_hal_line_count());
}

static void test_rd_temperature_with_no_answer_to_the_read(void)
{
	/* The command is acknowledged but the read is not: nothing is queued. */
	test_feed("rd temperature\n");
	TEST_ASSERT_EQUAL_STRING("ACK rd temperature = Error", fake_hal_last_line());
	TEST_ASSERT_EQUAL_UINT32(1U, fake_hal_read_count());
}

static void test_rd_temperature_with_a_corrupted_frame(void)
{
	static const uint8_t	frame[6] = { 0x66U, 0x66U, 0x00U, 0x66U, 0x66U, 0x93U };

	fake_hal_queue_read(frame, 6U, HAL_STATUS_OK);
	test_feed("rd temperature\n");
	TEST_ASSERT_EQUAL_STRING("ACK rd temperature = Error", fake_hal_last_line());
}

static void test_rd_temperature_with_a_bus_timeout(void)
{
	fake_hal_fail_next_write(HAL_STATUS_ERR_TIMEOUT);
	test_feed("rd temperature\n");
	TEST_ASSERT_EQUAL_STRING("ACK rd temperature = Error", fake_hal_last_line());
}

static void test_rd_temperature_with_a_bus_timeout_on_the_read(void)
{
	static const uint8_t	frame[6] = { 0U };

	fake_hal_queue_read(frame, 6U, HAL_STATUS_ERR_TIMEOUT);
	test_feed("rd temperature\n");
	TEST_ASSERT_EQUAL_STRING("ACK rd temperature = Error", fake_hal_last_line());
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

static void test_status_with_a_corrupted_word(void)
{
	static const uint8_t	word[3] = { 0x80U, 0x10U, 0x00U };

	fake_hal_queue_read(word, 3U, HAL_STATUS_OK);
	test_feed("status\n");
	TEST_ASSERT_EQUAL_STRING("err 5 the sensor checksum did not match", fake_hal_last_line());
}

static void test_status_with_a_bus_timeout(void)
{
	fake_hal_fail_next_write(HAL_STATUS_ERR_TIMEOUT);
	test_feed("status\n");
	TEST_ASSERT_EQUAL_STRING("err 6 I2C bus timeout", fake_hal_last_line());
}

static void test_sreset(void)
{
	test_feed("sreset\n");
	TEST_ASSERT_EQUAL_STRING("ok", fake_hal_last_line());
	TEST_ASSERT_EQUAL_HEX8(0x30U, fake_hal_write_bytes(0U)[0]);
	TEST_ASSERT_EQUAL_HEX8(0xA2U, fake_hal_write_bytes(0U)[1]);
}

static void test_sreset_with_no_sensor(void)
{
	fake_hal_fail_next_write(HAL_STATUS_ERR_NACK);
	test_feed("sreset\n");
	TEST_ASSERT_EQUAL_STRING("err 4 the sensor did not acknowledge", fake_hal_last_line());
	TEST_ASSERT_EQUAL_UINT32(1U, fake_hal_line_count());
}

/* --- ecureset and bootsel (PICO-FR-030) ---------------------------------- */
static void test_ecureset_replies_before_rebooting(void)
{
	test_feed("ecureset\n");
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

static void test_a_refused_ecureset_does_not_reboot(void)
{
	test_feed("ecureset now\n");
	TEST_ASSERT_EQUAL_STRING("err 2 wrong number of arguments", fake_hal_last_line());
	TEST_ASSERT_EQUAL_UINT32(0U, fake_hal_reboot_count());
	test_feed("rd version\n");
	TEST_ASSERT_EQUAL_UINT32(0U, fake_hal_reboot_count());
}

/* --- help --------------------------------------------------------------- */
static void test_help_lists_every_command_then_ok(void)
{
	test_feed("help\n");
	TEST_ASSERT_EQUAL_UINT32(7U, fake_hal_line_count());
	TEST_ASSERT_EQUAL_STRING_LEN("# help - ", fake_hal_line(0U), 9U);
	test_expect_in("# rd - ", fake_hal_line(1U));
	test_expect_in("# status - ", fake_hal_line(2U));
	test_expect_in("# sreset - ", fake_hal_line(3U));
	test_expect_in("# ecureset - ", fake_hal_line(4U));
	test_expect_in("# bootsel - ", fake_hal_line(5U));
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
	RUN_TEST(test_ver_temp_and_reset_are_no_longer_commands);
	RUN_TEST(test_rd_name);
	RUN_TEST(test_rd_copyright);
	RUN_TEST(test_rd_version);
	RUN_TEST(test_rd_sha_reports_the_injected_commit);
	RUN_TEST(test_rd_identity_matches_the_header);
	RUN_TEST(test_rd_identity_does_not_touch_the_sensor);
	RUN_TEST(test_rd_without_an_option_is_refused);
	RUN_TEST(test_rd_with_two_options_is_refused);
	RUN_TEST(test_rd_unknown_option_is_a_nak);
	RUN_TEST(test_rd_options_are_case_sensitive);
	RUN_TEST(test_rd_a_partial_option_is_a_nak);
	RUN_TEST(test_rd_the_longest_option_is_echoed_whole);
	RUN_TEST(test_rd_temperature_has_two_places);
	RUN_TEST(test_rd_temperature_is_rounded);
	RUN_TEST(test_rd_temperature_below_zero);
	RUN_TEST(test_rd_temperature_just_below_zero_has_no_sign);
	RUN_TEST(test_rd_temperature_takes_one_measurement);
	RUN_TEST(test_rd_temperature_with_no_sensor);
	RUN_TEST(test_rd_temperature_with_no_answer_to_the_read);
	RUN_TEST(test_rd_temperature_with_a_corrupted_frame);
	RUN_TEST(test_rd_temperature_with_a_bus_timeout);
	RUN_TEST(test_rd_temperature_with_a_bus_timeout_on_the_read);
	RUN_TEST(test_status_reports_the_register);
	RUN_TEST(test_status_with_no_sensor);
	RUN_TEST(test_status_with_a_corrupted_word);
	RUN_TEST(test_status_with_a_bus_timeout);
	RUN_TEST(test_sreset);
	RUN_TEST(test_sreset_with_no_sensor);
	RUN_TEST(test_ecureset_replies_before_rebooting);
	RUN_TEST(test_bootsel_replies_before_rebooting);
	RUN_TEST(test_a_refused_ecureset_does_not_reboot);
	RUN_TEST(test_help_lists_every_command_then_ok);
	return UNITY_END();
}
