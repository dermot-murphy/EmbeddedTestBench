/**
 * @file test_cmd_parser.c
 * @brief The command dispatcher: the firmware's half of the host contract.
 *
 * These tests matter more than their size suggests. The host driver is tested
 * against a *simulated* dongle; this is the only place the real firmware's
 * replies are checked, and the two must agree or the simulation is fiction.
 * Where a reply's shape is asserted here, the same shape is asserted on the
 * host side in ``tests/instruments/nordic_dongle/``.
 *
 * Traces to: BLE-FR-002, BLE-FR-020 .. BLE-FR-053, BLE-DD-CMD, SWE4-UT-FWUNIT.
 */

#include <stdio.h>
#include <string.h>

#include "unity.h"

#include "cmd_parser.h"
#include "ble_scanner.h"
#include "fakes.h"
#include "firmware_version.h"
#include "nrf_delay.h"
#include "nrf_gpio.h"
#include "nrf_soc.h"
#include "nus_client.h"
#include "protocol.h"
#include "timestamp.h"

/** Run a command line through the parser, as the main loop would. */
static void handle(const char * line)
{
	char buffer[PROTO_MAX_LINE];

	(void)strncpy(buffer, line, sizeof(buffer) - 1U);
	buffer[sizeof(buffer) - 1U] = '\0';
	cmd_parser_handle(buffer);
}

/** The reply is the last line, since events precede it. */
static const char * reply(void)
{
	return fake_last_line();
}

static bool reply_has(const char * text)
{
	return strstr(reply(), text) != NULL;
}

void setUp(void)
{
	fake_lines_reset();
	fake_clock_reset();
	fake_scanner_reset();
	fake_nus_client_reset();
	TEST_ASSERT_TRUE_MESSAGE(cmd_parser_init(),
				 "every documented command must have a handler");
}

void tearDown(void)
{
}

/* ------------------------------------------------------------------ */
/* Dispatch                                                            */
/* ------------------------------------------------------------------ */

static void test_every_command_answers_exactly_once(void)
{
	/* A command that does not reply looks to the host like a hung dongle. */
	const char * commands[] = {
		"ver", "time", "list", "selected", "scan stop", "adv stats",
		"disconnect", "uart 00", "cmd 00", "select 0", "connect", "nonsense",
		/* dfu and reset are exercised on their own: they reset the part. */
	};
	uint32_t index;

	for (index = 0U; index < (sizeof(commands) / sizeof(commands[0])); index++)
	{
		fake_lines_reset();
		handle(commands[index]);
		TEST_ASSERT_GREATER_THAN_MESSAGE(0U, fake_line_count(), commands[index]);
		TEST_ASSERT_TRUE_MESSAGE((strncmp(reply(), "ok", 2) == 0) ||
					 (strncmp(reply(), "err", 3) == 0),
					 commands[index]);
	}
}

static void test_an_unknown_command_is_refused(void)
{
	handle("fly");
	TEST_ASSERT_EQUAL_STRING("err 1 unknown command", reply());
}

static void test_a_blank_line_is_not_a_command(void)
{
	handle("");
	TEST_ASSERT_EQUAL_UINT32(0U, fake_line_count());
	handle("   ");
	TEST_ASSERT_EQUAL_UINT32(0U, fake_line_count());
}

static void test_too_few_arguments(void)
{
	handle("select");
	TEST_ASSERT_EQUAL_STRING("err 2 wrong number of arguments", reply());
}

static void test_too_many_arguments(void)
{
	handle("ver please");
	TEST_ASSERT_EQUAL_STRING("err 2 wrong number of arguments", reply());
}

static void test_extra_spaces_are_tolerated(void)
{
	handle("  scan   stop  ");
	TEST_ASSERT_TRUE(reply_has("ok"));
}

static void test_the_error_text_matches_the_table(void)
{
	TEST_ASSERT_EQUAL_STRING("unknown command", proto_error_text(PROTO_ERR_UNKNOWN));
	TEST_ASSERT_EQUAL_STRING("the sensor did not reply", proto_error_text(PROTO_ERR_TIMEOUT));
	TEST_ASSERT_EQUAL_STRING("unspecified", proto_error_text((proto_error_t)99));
}

/* ------------------------------------------------------------------ */
/* Identity and time                                                   */
/* ------------------------------------------------------------------ */

static void test_ver_reports_the_protocol_and_uptime(void)
{
	fake_clock_set(1234567U);
	handle("ver");
	TEST_ASSERT_TRUE(reply_has(PROTO_MANUFACTURER));
	TEST_ASSERT_TRUE(reply_has(PROTO_MODEL));
	TEST_ASSERT_TRUE(reply_has("proto=" PROTO_VERSION));
	TEST_ASSERT_TRUE(reply_has("uptime_us=1234567"));
	TEST_ASSERT_TRUE(reply_has("dropped="));
}

static void test_ver_reports_which_build_is_on_the_dongle(void)
{
	/* The host compares both against what it built: the version for a
	 * deliberate change, the date for a rebuild of the same version. */
	handle("ver");
	TEST_ASSERT_TRUE(reply_has("fw=" FIRMWARE_VERSION));
	TEST_ASSERT_TRUE(reply_has("built="));
	TEST_ASSERT_TRUE(strstr(reply(), "built=") > strstr(reply(), "fw="));
}

static void test_the_build_date_carries_no_spaces(void)
{
	/* The link is a space-separated line protocol, so a date with a space in
	 * it would arrive as two fields and silently lose its time of day. The
	 * build injects an ISO 8601 instant for exactly this reason; the test
	 * build injects the same shape (see CMakeLists.txt). */
	char		expected[64];

	handle("ver");
	snprintf(expected, sizeof expected, "built=%s ", FIRMWARE_BUILD_DATE);
	TEST_ASSERT_NOT_NULL_MESSAGE(strstr(reply(), expected),
				     "the whole build date must be one field");
}

static void test_dfu_answers_before_it_resets(void)
{
	/* A host waiting for a reply it will never get cannot tell a dongle in
	 * the bootloader from one that has crashed. */
	fake_retained_register_reset();
	fake_system_resets = 0U;
	fake_clock_set_step(1000U);

	handle("dfu");

	TEST_ASSERT_TRUE(reply_has("dfu=1"));
	TEST_ASSERT_TRUE(reply_has("fw=" FIRMWARE_VERSION));
	TEST_ASSERT_EQUAL_HEX32(0xB1U, fake_retained_register());

	fake_system_resets = 0U;
	fake_retained_register_reset();
}

static void test_dfu_keeps_servicing_usb_after_its_reply_has_left(void)
{
	/* Observed on a PCA10059 under Windows: resetting as soon as the transmit
	 * queue emptied still lost the reply. The command keeps the link up for a
	 * grace period after that - and gives up at a limit rather than waiting
	 * for ever on a host that has stopped reading. */
	uint64_t	before;
	uint64_t	waited;

	fake_clock_set_step(1000U);
	before = timestamp_now_us();

	handle("dfu");

	waited = timestamp_now_us() - before;
	TEST_ASSERT_TRUE_MESSAGE(waited >= 50000U, "the grace period was cut short");
	TEST_ASSERT_TRUE_MESSAGE(waited <= 260000U, "the wait is not bounded");

	fake_system_resets = 0U;
	fake_retained_register_reset();
	fake_gpio_reset();
}

static void test_dfu_pulls_the_dongles_own_reset_pin(void)
{
	/* The PCA10059 open bootloader enters DFU only after a pin reset; a soft
	 * reset brings the application straight back. P0.19 is wired to nRESET. */
	fake_gpio_reset();
	fake_system_resets = 0U;
	fake_clock_set_step(1000U);

	handle("dfu");

	TEST_ASSERT_EQUAL_UINT32(19U, fake_gpio_output_pin());
	TEST_ASSERT_EQUAL_UINT32(19U, fake_gpio_cleared_pin());
	TEST_ASSERT_TRUE(fake_delay_total_ms() > 0U);
	/* The soft reset is the fallback for a board where the pin is not wired;
	 * on the fake nothing resets, so it is reached. */
	TEST_ASSERT_EQUAL_UINT32(1U, fake_system_resets);

	fake_gpio_reset();
	fake_system_resets = 0U;
	fake_retained_register_reset();
}

static void test_time_reports_the_clock_and_its_rate(void)
{
	fake_clock_set(42U);
	handle("time");
	TEST_ASSERT_EQUAL_STRING("ok t=42 hz=1000000", reply());
}

/* ------------------------------------------------------------------ */
/* Scanning                                                            */
/* ------------------------------------------------------------------ */

static void test_scan_start_clears_the_table_first(void)
{
	fake_scanner_add("E4:1C:7B:02:9A:11", 1, "SENS-01", -62);
	handle("scan start 3000");
	TEST_ASSERT_EQUAL_UINT32(1U, fake_scanner_clears());
	TEST_ASSERT_EQUAL_UINT32(1U, fake_scanner_starts());
	TEST_ASSERT_EQUAL_UINT32(3000U, fake_scanner_last_duration_ms());
	TEST_ASSERT_TRUE(reply_has("scanning=1"));
}

static void test_scan_filters_are_passed_to_the_scanner(void)
{
	handle("scan start 1000 name=SENS active=1 rssi=-80");
	TEST_ASSERT_EQUAL_STRING("SENS", fake_scanner_filter_name());
	TEST_ASSERT_TRUE(fake_scanner_filter_active());
	TEST_ASSERT_EQUAL_INT8(-80, fake_scanner_filter_rssi());
}

static void test_an_unknown_filter_key_is_refused(void)
{
	handle("scan start 1000 colour=blue");
	TEST_ASSERT_EQUAL_STRING("err 3 bad argument value", reply());
}

static void test_a_malformed_filter_address_is_refused(void)
{
	handle("scan start 1000 addr=nonsense");
	TEST_ASSERT_EQUAL_STRING("err 3 bad argument value", reply());
}

static void test_scan_stop_reports_what_was_found(void)
{
	fake_scanner_add("E4:1C:7B:02:9A:11", 1, "SENS-01", -62);
	handle("scan stop");
	TEST_ASSERT_EQUAL_UINT32(1U, fake_scanner_stops());
	TEST_ASSERT_TRUE(reply_has("scanning=0"));
	TEST_ASSERT_TRUE(reply_has("sensors=1"));
}

static void test_a_scan_the_stack_refuses_is_reported(void)
{
	fake_scanner_set_start_result(NRF_ERROR_INVALID_STATE);
	handle("scan start 1000");
	TEST_ASSERT_EQUAL_STRING("err 10 the BLE stack refused the request", reply());
}

static void test_scan_without_a_subcommand_is_refused(void)
{
	handle("scan sideways");
	TEST_ASSERT_EQUAL_STRING("err 3 bad argument value", reply());
}

static void test_scan_start_without_a_duration_is_refused(void)
{
	handle("scan start");
	TEST_ASSERT_EQUAL_STRING("err 2 wrong number of arguments", reply());
}

/* ------------------------------------------------------------------ */
/* Listing and selection                                               */
/* ------------------------------------------------------------------ */

static void test_list_emits_one_event_per_sensor_then_a_count(void)
{
	fake_scanner_add("E4:1C:7B:02:9A:11", 1, "SENS-01", -62);
	fake_scanner_add("C9:3A:51:0F:22:04", 1, "SENS-02", -78);
	handle("list");

	TEST_ASSERT_EQUAL_UINT32(3U, fake_line_count());
	TEST_ASSERT_TRUE(strstr(fake_line(0), "+sensor ") == fake_line(0));
	TEST_ASSERT_TRUE(strstr(fake_line(0), "idx=0") != NULL);
	TEST_ASSERT_TRUE(strstr(fake_line(0), "addr=E4:1C:7B:02:9A:11") != NULL);
	TEST_ASSERT_TRUE(strstr(fake_line(0), "rssi=-62") != NULL);
	TEST_ASSERT_TRUE(strstr(fake_line(0), "name=SENS-01") != NULL);
	TEST_ASSERT_TRUE(strstr(fake_line(1), "idx=1") != NULL);
	TEST_ASSERT_EQUAL_STRING("ok sensors=2", reply());
}

static void test_list_with_nothing_found(void)
{
	handle("list");
	TEST_ASSERT_EQUAL_STRING("ok sensors=0", reply());
}

static void test_a_sensor_with_no_name_still_appears(void)
{
	fake_scanner_add("F1:22:33:44:55:66", 1, "", -91);
	handle("list");
	TEST_ASSERT_TRUE(strstr(fake_line(0), "name=") != NULL);
	TEST_ASSERT_EQUAL_STRING("ok sensors=1", reply());
}

static void test_select_by_index(void)
{
	fake_scanner_add("E4:1C:7B:02:9A:11", 1, "SENS-01", -62);
	handle("select 0");
	TEST_ASSERT_TRUE(reply_has("addr=E4:1C:7B:02:9A:11"));
	TEST_ASSERT_TRUE(reply_has("name=SENS-01"));
	TEST_ASSERT_TRUE(reply_has("known=1"));
}

static void test_select_by_address(void)
{
	fake_scanner_add("E4:1C:7B:02:9A:11", 1, "SENS-01", -62);
	handle("select E4:1C:7B:02:9A:11");
	TEST_ASSERT_TRUE(reply_has("known=1"));
	TEST_ASSERT_TRUE(reply_has("name=SENS-01"));
}

static void test_selecting_an_unseen_address_is_allowed(void)
{
	/* The host may know the address from an earlier run; requiring a scan
	 * first would make every suite start with one. */
	handle("select AA:BB:CC:DD:EE:FF/0");
	TEST_ASSERT_TRUE(reply_has("addr=AA:BB:CC:DD:EE:FF"));
	TEST_ASSERT_TRUE(reply_has("type=0"));
	TEST_ASSERT_TRUE(reply_has("known=0"));
}

static void test_selecting_an_index_past_the_end_is_refused(void)
{
	handle("select 7");
	TEST_ASSERT_EQUAL_STRING("err 3 bad argument value", reply());
}

static void test_selected_before_selecting(void)
{
	handle("selected");
	TEST_ASSERT_EQUAL_STRING("err 5 no sensor selected", reply());
}

static void test_selected_reports_the_choice_and_the_link(void)
{
	fake_scanner_add("E4:1C:7B:02:9A:11", 1, "SENS-01", -62);
	handle("select 0");
	handle("selected");
	TEST_ASSERT_TRUE(reply_has("addr=E4:1C:7B:02:9A:11"));
	TEST_ASSERT_TRUE(reply_has("connected=0"));

	fake_nus_client_set_ready(true);
	handle("selected");
	TEST_ASSERT_TRUE(reply_has("connected=1"));
}

/* ------------------------------------------------------------------ */
/* Connecting                                                          */
/* ------------------------------------------------------------------ */

static void test_connect_needs_a_sensor(void)
{
	handle("connect");
	TEST_ASSERT_EQUAL_STRING("err 5 no sensor selected", reply());
}

static void test_connect_stops_scanning_first(void)
{
	/* One radio: a connection attempt while scanning is refused for a reason
	 * the host cannot see. */
	fake_scanner_add("E4:1C:7B:02:9A:11", 1, "SENS-01", -62);
	handle("select 0");
	fake_scanner_set_active(true);
	handle("connect");
	TEST_ASSERT_EQUAL_UINT32(1U, fake_scanner_stops());
	TEST_ASSERT_EQUAL_UINT32(1U, fake_nus_client_connects());
	TEST_ASSERT_TRUE(reply_has("connecting=1"));
}

static void test_connecting_twice_is_refused(void)
{
	fake_scanner_add("E4:1C:7B:02:9A:11", 1, "SENS-01", -62);
	handle("select 0");
	fake_nus_client_set_connected(true);
	handle("connect");
	TEST_ASSERT_EQUAL_STRING("err 4 not valid in this state", reply());
}

static void test_connect_to_a_given_address(void)
{
	handle("connect AA:BB:CC:DD:EE:FF");
	TEST_ASSERT_EQUAL_UINT32(1U, fake_nus_client_connects());
	TEST_ASSERT_TRUE(reply_has("addr=AA:BB:CC:DD:EE:FF"));
}

static void test_connect_listens_for_fifteen_seconds_by_default(void)
{
	handle("connect AA:BB:CC:DD:EE:FF");
	TEST_ASSERT_EQUAL_UINT32(15000U, fake_nus_client_connect_timeout_ms());
	TEST_ASSERT_TRUE(reply_has("timeout_ms=15000"));
}

static void test_connect_takes_a_timeout_before_or_after_the_address(void)
{
	handle("connect AA:BB:CC:DD:EE:FF timeout=20000");
	TEST_ASSERT_EQUAL_UINT32(20000U, fake_nus_client_connect_timeout_ms());
	TEST_ASSERT_TRUE(reply_has("addr=AA:BB:CC:DD:EE:FF"));

	fake_nus_client_set_connected(false);
	handle("connect timeout=2000 AA:BB:CC:DD:EE:FF");
	TEST_ASSERT_EQUAL_UINT32(2000U, fake_nus_client_connect_timeout_ms());
}

static void test_connect_uses_the_selection_with_only_a_timeout(void)
{
	fake_scanner_add("E4:1C:7B:02:9A:11", 1, "SENS-01", -62);
	handle("select 0");
	handle("connect timeout=30000");
	TEST_ASSERT_EQUAL_UINT32(30000U, fake_nus_client_connect_timeout_ms());
	TEST_ASSERT_TRUE(reply_has("addr=E4:1C:7B:02:9A:11"));
}

static void test_connect_refuses_a_bad_timeout(void)
{
	handle("connect AA:BB:CC:DD:EE:FF timeout=999");
	TEST_ASSERT_EQUAL_STRING("err 3 bad argument value", reply());
	handle("connect AA:BB:CC:DD:EE:FF timeout=60001");
	TEST_ASSERT_EQUAL_STRING("err 3 bad argument value", reply());
	handle("connect AA:BB:CC:DD:EE:FF timeout=ten");
	TEST_ASSERT_EQUAL_STRING("err 3 bad argument value", reply());
	handle("connect AA:BB:CC:DD:EE:FF 11:22:33:44:55:66");
	TEST_ASSERT_EQUAL_STRING("err 3 bad argument value", reply());
	TEST_ASSERT_EQUAL_UINT32(0U, fake_nus_client_connects());
}

static void test_a_refused_connection_is_reported(void)
{
	handle("connect AA:BB:CC:DD:EE:FF");
	fake_nus_client_set_connect_result(NRF_ERROR_INVALID_STATE);
	handle("connect AA:BB:CC:DD:EE:FF");
	TEST_ASSERT_EQUAL_STRING("err 10 the BLE stack refused the request", reply());
}

static void test_disconnect_without_a_link(void)
{
	handle("disconnect");
	TEST_ASSERT_EQUAL_STRING("err 6 not connected", reply());
}

static void test_disconnect(void)
{
	fake_nus_client_set_connected(true);
	handle("disconnect");
	TEST_ASSERT_EQUAL_STRING("ok", reply());
	TEST_ASSERT_EQUAL_UINT32(1U, fake_nus_client_disconnects());
}

/* ------------------------------------------------------------------ */
/* UART                                                                */
/* ------------------------------------------------------------------ */

static void test_uart_decodes_hex_and_reports_the_length(void)
{
	fake_nus_client_set_ready(true);
	handle("uart 76657273696f6e");                 /* "version" */
	TEST_ASSERT_EQUAL_UINT32(1U, fake_nus_client_writes());
	TEST_ASSERT_EQUAL_UINT16(7U, fake_nus_client_last_length());
	TEST_ASSERT_EQUAL_MEMORY("version", fake_nus_client_last_payload(), 7U);
	TEST_ASSERT_TRUE(reply_has("len=7"));
}

static void test_uart_without_a_link(void)
{
	handle("uart 00");
	TEST_ASSERT_EQUAL_STRING("err 6 not connected", reply());
}

static void test_odd_length_hex_is_refused(void)
{
	fake_nus_client_set_ready(true);
	handle("uart abc");
	TEST_ASSERT_EQUAL_STRING("err 9 payload too long", reply());
}

static void test_non_hex_is_refused(void)
{
	fake_nus_client_set_ready(true);
	handle("uart zzzz");
	TEST_ASSERT_EQUAL_STRING("err 9 payload too long", reply());
}

static void test_cmd_reports_both_timestamps_and_the_round_trip(void)
{
	fake_nus_client_set_ready(true);
	fake_nus_client_set_interval_us(30000U);
	fake_nus_client_set_reply("1.4.2", 12500U);
	fake_clock_set(5000000U);

	handle("cmd 76657273696f6e");

	TEST_ASSERT_EQUAL_UINT32(1U, fake_nus_client_commands());
	TEST_ASSERT_TRUE(reply_has("t_tx=5000000"));
	TEST_ASSERT_TRUE(reply_has("t_rx=5012500"));
	TEST_ASSERT_TRUE(reply_has("dt_us=12500"));
	TEST_ASSERT_TRUE(reply_has("interval_us=30000"));
	TEST_ASSERT_TRUE(reply_has("len=5"));
	TEST_ASSERT_TRUE(reply_has("data=312e342e32"));      /* "1.4.2" */
}

static void test_cmd_waits_two_seconds_by_default(void)
{
	fake_nus_client_set_ready(true);
	fake_nus_client_set_reply("1.4.2", 12500U);
	handle("cmd 00");
	TEST_ASSERT_EQUAL_UINT32(2000U, fake_nus_client_command_timeout_ms());
}

static void test_cmd_takes_a_timeout_for_a_slow_command(void)
{
	/* Some commands take longer than others (#46). */
	fake_nus_client_set_ready(true);
	fake_nus_client_set_reply("1.4.2", 12500U);
	handle("cmd 00 timeout=15000");
	TEST_ASSERT_EQUAL_UINT32(15000U, fake_nus_client_command_timeout_ms());
	TEST_ASSERT_TRUE(reply_has("dt_us=12500"));
}

static void test_cmd_refuses_a_bad_timeout(void)
{
	fake_nus_client_set_ready(true);
	handle("cmd 00 timeout=99");
	TEST_ASSERT_EQUAL_STRING("err 3 bad argument value", reply());
	handle("cmd 00 timeout=60001");
	TEST_ASSERT_EQUAL_STRING("err 3 bad argument value", reply());
	handle("cmd 00 wait=5");
	TEST_ASSERT_EQUAL_STRING("err 3 bad argument value", reply());
	TEST_ASSERT_EQUAL_UINT32(0U, fake_nus_client_commands());
}

static void test_cmd_carries_a_full_payload_both_ways(void)
{
	/* 244 bytes out - the ATT MTU less the write header - and a long reply
	 * back whole: at 192 characters the reply line cut off anything over about
	 * 60 bytes (#52). */
	char		command[PROTO_MAX_LINE];
	char		text[241];
	char		expected[(240U * 2U) + 8U];
	uint32_t	index;

	(void)memset(text, 'A', 240U);
	text[240] = '\0';
	(void)strcpy(command, "cmd ");
	for (index = 0U; index < PROTO_MAX_PAYLOAD; index++)
	{
		(void)strcat(command, "42");
	}
	(void)strcpy(expected, "data=");
	for (index = 0U; index < 240U; index++)
	{
		(void)strcat(expected, "41");
	}

	fake_nus_client_set_ready(true);
	fake_nus_client_set_reply(text, 12500U);
	handle(command);

	TEST_ASSERT_EQUAL_UINT32(1U, fake_nus_client_commands());
	TEST_ASSERT_EQUAL_HEX8(0x42U, fake_nus_client_last_payload()[PROTO_MAX_PAYLOAD - 1U]);
	TEST_ASSERT_TRUE(reply_has("len=240"));
	TEST_ASSERT_TRUE(reply_has(expected));
}

static void test_a_sensor_that_does_not_reply_is_a_timeout_not_a_measurement(void)
{
	/* Reporting the timeout as a round trip would put a fiction in the log. */
	fake_nus_client_set_ready(true);
	fake_nus_client_set_no_reply();
	handle("cmd 00");
	TEST_ASSERT_EQUAL_STRING("err 8 the sensor did not reply", reply());
}

static void test_cmd_without_a_link(void)
{
	handle("cmd 00");
	TEST_ASSERT_EQUAL_STRING("err 6 not connected", reply());
}

/* ------------------------------------------------------------------ */
/* Advertising profile                                                 */
/* ------------------------------------------------------------------ */

static void test_adv_start_uses_the_selected_sensor(void)
{
	fake_scanner_add("E4:1C:7B:02:9A:11", 1, "SENS-01", -62);
	handle("select 0");
	handle("adv start");
	TEST_ASSERT_TRUE(scanner_profile_is_active());
	TEST_ASSERT_EQUAL_STRING("E4:1C:7B:02:9A:11", fake_scanner_profile_address());
	TEST_ASSERT_TRUE(reply_has("profiling=1"));
}

static void test_adv_start_with_an_address(void)
{
	handle("adv start AA:BB:CC:DD:EE:FF");
	TEST_ASSERT_EQUAL_STRING("AA:BB:CC:DD:EE:FF", fake_scanner_profile_address());
}

static void test_adv_start_needs_a_sensor(void)
{
	handle("adv start");
	TEST_ASSERT_EQUAL_STRING("err 5 no sensor selected", reply());
}

static void test_adv_stats_reconcile_what_was_seen_and_sent(void)
{
	/* The host uses these to tell a lossy link from a quiet sensor. */
	fake_scanner_set_counters(120U, 118U);
	fake_scanner_set_profiling(true);
	handle("adv stats");
	TEST_ASSERT_TRUE(reply_has("received=120"));
	TEST_ASSERT_TRUE(reply_has("reported=118"));
	TEST_ASSERT_TRUE(reply_has("dropped="));
	TEST_ASSERT_TRUE(reply_has("profiling=1"));
}

static void test_adv_stop_reports_the_totals(void)
{
	fake_scanner_set_counters(50U, 50U);
	fake_scanner_set_profiling(true);
	handle("adv stop");
	TEST_ASSERT_FALSE(scanner_profile_is_active());
	TEST_ASSERT_TRUE(reply_has("profiling=0"));
	TEST_ASSERT_TRUE(reply_has("received=50"));
}

static void test_adv_with_a_bad_subcommand(void)
{
	handle("adv sideways");
	TEST_ASSERT_EQUAL_STRING("err 3 bad argument value", reply());
}

/* ------------------------------------------------------------------ */
/* Reset                                                               */
/* ------------------------------------------------------------------ */

static void test_reset_answers_before_resetting(void)
{
	/* The host must see the reply; the reset takes the USB link down. */
	handle("reset");
	TEST_ASSERT_TRUE(reply_has("resetting=1"));
	TEST_ASSERT_EQUAL_UINT32(1U, fake_system_resets);
	fake_system_resets = 0U;
}

int main(void)
{
	UNITY_BEGIN();

	RUN_TEST(test_every_command_answers_exactly_once);
	RUN_TEST(test_an_unknown_command_is_refused);
	RUN_TEST(test_a_blank_line_is_not_a_command);
	RUN_TEST(test_too_few_arguments);
	RUN_TEST(test_too_many_arguments);
	RUN_TEST(test_extra_spaces_are_tolerated);
	RUN_TEST(test_the_error_text_matches_the_table);

	RUN_TEST(test_ver_reports_the_protocol_and_uptime);
	RUN_TEST(test_ver_reports_which_build_is_on_the_dongle);
	RUN_TEST(test_the_build_date_carries_no_spaces);
	RUN_TEST(test_dfu_answers_before_it_resets);
	RUN_TEST(test_dfu_keeps_servicing_usb_after_its_reply_has_left);
	RUN_TEST(test_dfu_pulls_the_dongles_own_reset_pin);
	RUN_TEST(test_time_reports_the_clock_and_its_rate);

	RUN_TEST(test_scan_start_clears_the_table_first);
	RUN_TEST(test_scan_filters_are_passed_to_the_scanner);
	RUN_TEST(test_an_unknown_filter_key_is_refused);
	RUN_TEST(test_a_malformed_filter_address_is_refused);
	RUN_TEST(test_scan_stop_reports_what_was_found);
	RUN_TEST(test_a_scan_the_stack_refuses_is_reported);
	RUN_TEST(test_scan_without_a_subcommand_is_refused);
	RUN_TEST(test_scan_start_without_a_duration_is_refused);

	RUN_TEST(test_list_emits_one_event_per_sensor_then_a_count);
	RUN_TEST(test_list_with_nothing_found);
	RUN_TEST(test_a_sensor_with_no_name_still_appears);
	RUN_TEST(test_select_by_index);
	RUN_TEST(test_select_by_address);
	RUN_TEST(test_selecting_an_unseen_address_is_allowed);
	RUN_TEST(test_selecting_an_index_past_the_end_is_refused);
	RUN_TEST(test_selected_before_selecting);
	RUN_TEST(test_selected_reports_the_choice_and_the_link);

	RUN_TEST(test_connect_needs_a_sensor);
	RUN_TEST(test_connect_stops_scanning_first);
	RUN_TEST(test_connecting_twice_is_refused);
	RUN_TEST(test_connect_to_a_given_address);
	RUN_TEST(test_connect_listens_for_fifteen_seconds_by_default);
	RUN_TEST(test_connect_takes_a_timeout_before_or_after_the_address);
	RUN_TEST(test_connect_uses_the_selection_with_only_a_timeout);
	RUN_TEST(test_connect_refuses_a_bad_timeout);
	RUN_TEST(test_a_refused_connection_is_reported);
	RUN_TEST(test_disconnect_without_a_link);
	RUN_TEST(test_disconnect);

	RUN_TEST(test_uart_decodes_hex_and_reports_the_length);
	RUN_TEST(test_uart_without_a_link);
	RUN_TEST(test_odd_length_hex_is_refused);
	RUN_TEST(test_non_hex_is_refused);
	RUN_TEST(test_cmd_reports_both_timestamps_and_the_round_trip);
	RUN_TEST(test_cmd_carries_a_full_payload_both_ways);
	RUN_TEST(test_cmd_waits_two_seconds_by_default);
	RUN_TEST(test_cmd_takes_a_timeout_for_a_slow_command);
	RUN_TEST(test_cmd_refuses_a_bad_timeout);
	RUN_TEST(test_a_sensor_that_does_not_reply_is_a_timeout_not_a_measurement);
	RUN_TEST(test_cmd_without_a_link);

	RUN_TEST(test_adv_start_uses_the_selected_sensor);
	RUN_TEST(test_adv_start_with_an_address);
	RUN_TEST(test_adv_start_needs_a_sensor);
	RUN_TEST(test_adv_stats_reconcile_what_was_seen_and_sent);
	RUN_TEST(test_adv_stop_reports_the_totals);
	RUN_TEST(test_adv_with_a_bad_subcommand);

	RUN_TEST(test_reset_answers_before_resetting);

	return UNITY_END();
}
