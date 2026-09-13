/**
 * @file test_ble_scanner.c
 * @brief Scanning: the sensor table, the filter, and the advertising report.
 *
 * Traces to: BLE-FR-020 .. BLE-FR-030, BLE-DD-SCANNER, SWE4-UT-FWUNIT.
 */

#include <string.h>

#include "unity.h"

#include "ble_scanner.h"
#include "fakes.h"
#include "nrf_ble_scan.h"

/** Build an advertising report event the way the stack delivers one. */
static ble_evt_t make_report(const char * address, int8_t rssi, uint8_t channel,
			     uint8_t * payload, uint16_t length)
{
	ble_evt_t event;

	(void)memset(&event, 0, sizeof(event));
	event.header.evt_id = BLE_GAP_EVT_ADV_REPORT;
	event.evt.gap_evt.params.adv_report.rssi       = rssi;
	event.evt.gap_evt.params.adv_report.ch_index   = channel;
	event.evt.gap_evt.params.adv_report.data.p_data = payload;
	event.evt.gap_evt.params.adv_report.data.len    = length;
	(void)scanner_parse_address(address, &event.evt.gap_evt.params.adv_report.peer_addr);

	return event;
}

/** Flags, then a complete local name - the usual shape of a sensor's payload. */
static uint16_t make_payload(uint8_t * buffer, const char * name)
{
	uint16_t length = 0U;

	buffer[length++] = 0x02U;
	buffer[length++] = 0x01U;                      /* flags */
	buffer[length++] = 0x06U;
	if ((name != NULL) && (name[0] != '\0'))
	{
		uint8_t size = (uint8_t)strlen(name);

		buffer[length++] = (uint8_t)(size + 1U);
		buffer[length++] = 0x09U;              /* complete local name */
		(void)memcpy(&buffer[length], name, size);
		length = (uint16_t)(length + size);
	}

	return length;
}

static void report(const char * address, int8_t rssi, const char * name)
{
	uint8_t		payload[31];
	uint16_t	length = make_payload(payload, name);
	ble_evt_t	event  = make_report(address, rssi, 37U, payload, length);

	scanner_on_ble_evt(&event);
}

void setUp(void)
{
	fake_lines_reset();
	fake_clock_reset();
	fake_scan_reset();
	scanner_profile_stop();
	(void)scanner_init();
	scanner_clear();
}

void tearDown(void)
{
}

/* ------------------------------------------------------------------ */
/* Addresses                                                           */
/* ------------------------------------------------------------------ */

static void test_an_address_is_written_most_significant_octet_first(void)
{
	/* The stack stores them the other way round, and getting this backwards
	 * produces an address that looks plausible and matches nothing. */
	ble_gap_addr_t	address;
	char		text[18];

	TEST_ASSERT_TRUE(scanner_parse_address("E4:1C:7B:02:9A:11", &address));
	TEST_ASSERT_EQUAL_HEX8(0x11U, address.addr[0]);
	TEST_ASSERT_EQUAL_HEX8(0xE4U, address.addr[5]);

	scanner_format_address(&address, text);
	TEST_ASSERT_EQUAL_STRING("E4:1C:7B:02:9A:11", text);
}

static void test_lower_case_is_accepted(void)
{
	ble_gap_addr_t	address;
	char		text[18];

	TEST_ASSERT_TRUE(scanner_parse_address("e4:1c:7b:02:9a:11", &address));
	scanner_format_address(&address, text);
	TEST_ASSERT_EQUAL_STRING("E4:1C:7B:02:9A:11", text);
}

static void test_the_address_type_can_be_given(void)
{
	ble_gap_addr_t address;

	TEST_ASSERT_TRUE(scanner_parse_address("E4:1C:7B:02:9A:11/0", &address));
	TEST_ASSERT_EQUAL_UINT8(BLE_GAP_ADDR_TYPE_PUBLIC, address.addr_type);

	TEST_ASSERT_TRUE(scanner_parse_address("E4:1C:7B:02:9A:11", &address));
	TEST_ASSERT_EQUAL_UINT8(BLE_GAP_ADDR_TYPE_RANDOM_STATIC, address.addr_type);
}

static void test_a_malformed_address_is_rejected(void)
{
	ble_gap_addr_t address;

	TEST_ASSERT_FALSE(scanner_parse_address("", &address));
	TEST_ASSERT_FALSE(scanner_parse_address("E4:1C:7B:02:9A", &address));
	TEST_ASSERT_FALSE(scanner_parse_address("not an address", &address));
	TEST_ASSERT_FALSE(scanner_parse_address("E4:1C:7B:02:9A:11/9", &address));
}

/* ------------------------------------------------------------------ */
/* Scanning                                                            */
/* ------------------------------------------------------------------ */

static void test_the_scan_is_continuous(void)
{
	/* A duty-cycled scan adds its own gaps to the sensor's, and afterwards
	 * the two are indistinguishable. */
	scanner_filter_t filter;

	(void)memset(&filter, 0, sizeof(filter));
	TEST_ASSERT_EQUAL_UINT32(NRF_SUCCESS, scanner_start(&filter, 1000U));
	TEST_ASSERT_EQUAL_UINT16(fake_scan_params()->interval, fake_scan_params()->window);
	TEST_ASSERT_TRUE(scanner_is_active());
}

static void test_the_duration_is_converted_to_the_gap_unit(void)
{
	/* GAP counts 10 ms units; passing milliseconds would scan 100x too long. */
	scanner_filter_t filter;

	(void)memset(&filter, 0, sizeof(filter));
	(void)scanner_start(&filter, 3000U);
	TEST_ASSERT_EQUAL_UINT16(300U, fake_scan_params()->timeout);
}

static void test_an_indefinite_scan(void)
{
	scanner_filter_t filter;

	(void)memset(&filter, 0, sizeof(filter));
	(void)scanner_start(&filter, 0U);
	TEST_ASSERT_EQUAL_UINT16(0U, fake_scan_params()->timeout);
}

static void test_active_scanning_is_requested_only_when_asked(void)
{
	scanner_filter_t filter;

	(void)memset(&filter, 0, sizeof(filter));
	(void)scanner_start(&filter, 1000U);
	TEST_ASSERT_EQUAL_UINT8(0U, fake_scan_params()->active);

	filter.active = true;
	(void)scanner_start(&filter, 1000U);
	TEST_ASSERT_EQUAL_UINT8(1U, fake_scan_params()->active);
}

static void test_starting_announces_itself(void)
{
	scanner_filter_t filter;

	(void)memset(&filter, 0, sizeof(filter));
	(void)scanner_start(&filter, 1000U);
	TEST_ASSERT_TRUE(fake_line_seen("+scan "));
	TEST_ASSERT_TRUE(strstr(fake_last_line(), "state=started") != NULL);
}

static void test_stopping_announces_itself_once(void)
{
	scanner_filter_t filter;

	(void)memset(&filter, 0, sizeof(filter));
	(void)scanner_start(&filter, 1000U);
	fake_lines_reset();
	(void)scanner_stop();
	TEST_ASSERT_TRUE(strstr(fake_last_line(), "state=stopped") != NULL);

	fake_lines_reset();
	(void)scanner_stop();                  /* already stopped */
	TEST_ASSERT_EQUAL_UINT32(0U, fake_line_count());
}

static void test_a_scan_timeout_is_reported(void)
{
	scanner_filter_t filter;

	(void)memset(&filter, 0, sizeof(filter));
	(void)scanner_start(&filter, 1000U);
	fake_lines_reset();
	fake_scan_fire(NRF_BLE_SCAN_EVT_SCAN_TIMEOUT);
	TEST_ASSERT_TRUE(strstr(fake_last_line(), "state=stopped") != NULL);
	TEST_ASSERT_FALSE(scanner_is_active());
}

/* ------------------------------------------------------------------ */
/* The sensor table                                                    */
/* ------------------------------------------------------------------ */

static void test_a_sensor_is_recorded_once_however_often_it_advertises(void)
{
	report("E4:1C:7B:02:9A:11", -62, "SENS-01");
	report("E4:1C:7B:02:9A:11", -64, "SENS-01");
	report("E4:1C:7B:02:9A:11", -60, "SENS-01");

	TEST_ASSERT_EQUAL_UINT32(1U, scanner_count());
	TEST_ASSERT_EQUAL_UINT32(3U, scanner_get(0U)->seen);
	TEST_ASSERT_EQUAL_INT8(-60, scanner_get(0U)->rssi);     /* the latest */
}

static void test_the_name_is_taken_from_the_payload(void)
{
	report("E4:1C:7B:02:9A:11", -62, "SENS-01");
	TEST_ASSERT_EQUAL_STRING("SENS-01", scanner_get(0U)->name);
}

static void test_a_sensor_that_advertises_no_name_is_still_recorded(void)
{
	report("F1:22:33:44:55:66", -91, "");
	TEST_ASSERT_EQUAL_UINT32(1U, scanner_count());
	TEST_ASSERT_EQUAL_STRING("", scanner_get(0U)->name);
}

static void test_a_name_once_seen_is_kept(void)
{
	/* A sensor that advertises its name only in a scan response must not
	 * appear to lose it on the next report. */
	report("E4:1C:7B:02:9A:11", -62, "SENS-01");
	report("E4:1C:7B:02:9A:11", -62, "");
	TEST_ASSERT_EQUAL_STRING("SENS-01", scanner_get(0U)->name);
}

static void test_several_sensors_are_kept_apart(void)
{
	report("E4:1C:7B:02:9A:11", -62, "SENS-01");
	report("C9:3A:51:0F:22:04", -78, "SENS-02");
	TEST_ASSERT_EQUAL_UINT32(2U, scanner_count());
	TEST_ASSERT_EQUAL_STRING("SENS-02", scanner_get(1U)->name);
}

static void test_the_table_is_bounded_and_does_not_evict(void)
{
	/* Once full, a new address is ignored rather than displacing one the host
	 * may already have selected. */
	char		address[18];
	uint32_t	index;

	for (index = 0U; index < (PROTO_MAX_SENSORS + 4U); index++)
	{
		(void)sprintf(address, "AA:BB:CC:DD:EE:%02X", (unsigned)index);
		report(address, -70, "X");
	}
	TEST_ASSERT_EQUAL_UINT32(PROTO_MAX_SENSORS, scanner_count());
	TEST_ASSERT_EQUAL_STRING("AA:BB:CC:DD:EE:00", (scanner_format_address(&scanner_get(0U)->address, address), address));
}

static void test_finding_by_address(void)
{
	ble_gap_addr_t wanted;

	report("E4:1C:7B:02:9A:11", -62, "SENS-01");
	(void)scanner_parse_address("E4:1C:7B:02:9A:11", &wanted);
	TEST_ASSERT_EQUAL_UINT32(0U, scanner_find(&wanted));

	(void)scanner_parse_address("AA:BB:CC:DD:EE:FF", &wanted);
	TEST_ASSERT_EQUAL_UINT32(PROTO_MAX_SENSORS, scanner_find(&wanted));
}

static void test_clearing(void)
{
	report("E4:1C:7B:02:9A:11", -62, "SENS-01");
	scanner_clear();
	TEST_ASSERT_EQUAL_UINT32(0U, scanner_count());
	TEST_ASSERT_NULL(scanner_get(0U));
}

/* ------------------------------------------------------------------ */
/* Filtering                                                           */
/* ------------------------------------------------------------------ */

static void test_filtering_by_name(void)
{
	scanner_filter_t filter;

	(void)memset(&filter, 0, sizeof(filter));
	filter.by_name = true;
	(void)strcpy(filter.name, "SENS");
	(void)scanner_start(&filter, 0U);

	report("E4:1C:7B:02:9A:11", -62, "SENS-01");
	report("F1:22:33:44:55:66", -70, "OTHER");
	TEST_ASSERT_EQUAL_UINT32(1U, scanner_count());
}

static void test_filtering_by_address(void)
{
	scanner_filter_t filter;

	(void)memset(&filter, 0, sizeof(filter));
	filter.by_address = true;
	(void)scanner_parse_address("E4:1C:7B:02:9A:11", &filter.address);
	(void)scanner_start(&filter, 0U);

	report("E4:1C:7B:02:9A:11", -62, "SENS-01");
	report("C9:3A:51:0F:22:04", -78, "SENS-02");
	TEST_ASSERT_EQUAL_UINT32(1U, scanner_count());
}

static void test_filtering_by_signal_strength(void)
{
	scanner_filter_t filter;

	(void)memset(&filter, 0, sizeof(filter));
	filter.min_rssi = -80;
	(void)scanner_start(&filter, 0U);

	report("E4:1C:7B:02:9A:11", -62, "SENS-01");
	report("F1:22:33:44:55:66", -91, "FAR");
	TEST_ASSERT_EQUAL_UINT32(1U, scanner_count());
}

/* ------------------------------------------------------------------ */
/* Profiling                                                           */
/* ------------------------------------------------------------------ */

static void test_no_advertising_events_until_profiling_starts(void)
{
	report("E4:1C:7B:02:9A:11", -62, "SENS-01");
	TEST_ASSERT_FALSE(fake_line_seen("+adv "));
}

static void test_an_advertising_event_carries_what_the_host_needs(void)
{
	ble_gap_addr_t	target;
	uint8_t		payload[31];
	uint16_t	length = make_payload(payload, "SENS-01");
	ble_evt_t	event  = make_report("E4:1C:7B:02:9A:11", -62, 38U, payload, length);

	(void)scanner_parse_address("E4:1C:7B:02:9A:11", &target);
	scanner_profile_start(&target);
	fake_clock_set(7654321U);

	scanner_on_ble_evt(&event);

	TEST_ASSERT_TRUE(fake_line_seen("+adv "));
	TEST_ASSERT_TRUE(strstr(fake_last_line(), "t=7654321") != NULL);
	TEST_ASSERT_TRUE(strstr(fake_last_line(), "addr=E4:1C:7B:02:9A:11") != NULL);
	TEST_ASSERT_TRUE(strstr(fake_last_line(), "rssi=-62") != NULL);
	TEST_ASSERT_TRUE(strstr(fake_last_line(), "ch=38") != NULL);
	TEST_ASSERT_TRUE(strstr(fake_last_line(), "name=SENS-01") != NULL);
	TEST_ASSERT_TRUE(strstr(fake_last_line(), "data=020106") != NULL);
}

static void test_only_the_profiled_address_is_reported(void)
{
	ble_gap_addr_t target;

	(void)scanner_parse_address("E4:1C:7B:02:9A:11", &target);
	scanner_profile_start(&target);

	report("C9:3A:51:0F:22:04", -78, "SENS-02");
	TEST_ASSERT_FALSE(fake_line_seen("+adv "));

	report("E4:1C:7B:02:9A:11", -62, "SENS-01");
	TEST_ASSERT_TRUE(fake_line_seen("+adv "));
}

static void test_profiling_every_address(void)
{
	scanner_profile_start(NULL);
	report("C9:3A:51:0F:22:04", -78, "SENS-02");
	TEST_ASSERT_TRUE(fake_line_seen("+adv "));
}

static void test_the_counters_reconcile_what_was_seen_and_sent(void)
{
	ble_gap_addr_t	target;
	uint32_t	received;
	uint32_t	reported;

	(void)scanner_parse_address("E4:1C:7B:02:9A:11", &target);
	scanner_profile_start(&target);
	report("E4:1C:7B:02:9A:11", -62, "SENS-01");
	report("E4:1C:7B:02:9A:11", -62, "SENS-01");

	scanner_profile_counters(&received, &reported);
	TEST_ASSERT_EQUAL_UINT32(2U, received);
	TEST_ASSERT_EQUAL_UINT32(2U, reported);
}

static void test_a_dropped_line_is_counted_as_not_reported(void)
{
	/* This difference is how the host tells a lossy link from a quiet sensor. */
	ble_gap_addr_t	target;
	uint32_t	received;
	uint32_t	reported;

	(void)scanner_parse_address("E4:1C:7B:02:9A:11", &target);
	scanner_profile_start(&target);
	fake_lines_set_full(true);
	report("E4:1C:7B:02:9A:11", -62, "SENS-01");

	scanner_profile_counters(&received, &reported);
	TEST_ASSERT_EQUAL_UINT32(1U, received);
	TEST_ASSERT_EQUAL_UINT32(0U, reported);
	fake_lines_set_full(false);
}

static void test_stopping_profiling(void)
{
	scanner_profile_start(NULL);
	TEST_ASSERT_TRUE(scanner_profile_is_active());
	scanner_profile_stop();
	TEST_ASSERT_FALSE(scanner_profile_is_active());
	report("E4:1C:7B:02:9A:11", -62, "SENS-01");
	TEST_ASSERT_FALSE(fake_line_seen("+adv "));
}

static void test_other_stack_events_are_ignored(void)
{
	ble_evt_t event;

	(void)memset(&event, 0, sizeof(event));
	event.header.evt_id = BLE_GAP_EVT_CONNECTED;
	scanner_on_ble_evt(&event);
	TEST_ASSERT_EQUAL_UINT32(0U, scanner_count());
}

int main(void)
{
	UNITY_BEGIN();
	RUN_TEST(test_an_address_is_written_most_significant_octet_first);
	RUN_TEST(test_lower_case_is_accepted);
	RUN_TEST(test_the_address_type_can_be_given);
	RUN_TEST(test_a_malformed_address_is_rejected);

	RUN_TEST(test_the_scan_is_continuous);
	RUN_TEST(test_the_duration_is_converted_to_the_gap_unit);
	RUN_TEST(test_an_indefinite_scan);
	RUN_TEST(test_active_scanning_is_requested_only_when_asked);
	RUN_TEST(test_starting_announces_itself);
	RUN_TEST(test_stopping_announces_itself_once);
	RUN_TEST(test_a_scan_timeout_is_reported);

	RUN_TEST(test_a_sensor_is_recorded_once_however_often_it_advertises);
	RUN_TEST(test_the_name_is_taken_from_the_payload);
	RUN_TEST(test_a_sensor_that_advertises_no_name_is_still_recorded);
	RUN_TEST(test_a_name_once_seen_is_kept);
	RUN_TEST(test_several_sensors_are_kept_apart);
	RUN_TEST(test_the_table_is_bounded_and_does_not_evict);
	RUN_TEST(test_finding_by_address);
	RUN_TEST(test_clearing);

	RUN_TEST(test_filtering_by_name);
	RUN_TEST(test_filtering_by_address);
	RUN_TEST(test_filtering_by_signal_strength);

	RUN_TEST(test_no_advertising_events_until_profiling_starts);
	RUN_TEST(test_an_advertising_event_carries_what_the_host_needs);
	RUN_TEST(test_only_the_profiled_address_is_reported);
	RUN_TEST(test_profiling_every_address);
	RUN_TEST(test_the_counters_reconcile_what_was_seen_and_sent);
	RUN_TEST(test_a_dropped_line_is_counted_as_not_reported);
	RUN_TEST(test_stopping_profiling);
	RUN_TEST(test_other_stack_events_are_ignored);
	return UNITY_END();
}
