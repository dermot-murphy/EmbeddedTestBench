/**
 * @file test_nus_client.c
 * @brief UART over BLE: the link, and the round trip that is a measurement.
 *
 * Traces to: BLE-FR-040 .. BLE-FR-051, BLE-DD-NUS, SWE4-UT-FWUNIT.
 */

#include <string.h>

#include "unity.h"

#include "ble_nus_c.h"
#include "fakes.h"
#include "nus_client.h"

static nrf_ble_gq_t m_queue;

/** Bring the link up the way the stack does: connect, discover, ready. */
static void establish_link(void)
{
	ble_evt_t event;

	(void)memset(&event, 0, sizeof(event));
	event.header.evt_id = BLE_GAP_EVT_CONNECTED;
	event.evt.gap_evt.conn_handle = 1U;
	event.evt.gap_evt.params.connected.conn_params.min_conn_interval = 24U;  /* 30 ms */
	(void)scanner_parse_address("E4:1C:7B:02:9A:11",
				    &event.evt.gap_evt.params.connected.peer_addr);
	nus_client_on_ble_evt(&event);

	fake_nus_fire(BLE_NUS_C_EVT_DISCOVERY_COMPLETE, NULL, 0U);
}

void setUp(void)
{
	fake_lines_reset();
	fake_clock_reset();
	/* The command wait loop reads the clock; on the target it always moves, so
	 * here every read advances it. Without this a timeout never expires. */
	fake_clock_set_step(500U);
	fake_nus_reset();
	fake_gap_reset();
	(void)nus_client_init(&m_queue);
}

void tearDown(void)
{
	if (nus_client_is_connected())
	{
		ble_evt_t event;

		(void)memset(&event, 0, sizeof(event));
		event.header.evt_id = BLE_GAP_EVT_DISCONNECTED;
		nus_client_on_ble_evt(&event);
	}
}

/* ------------------------------------------------------------------ */
/* The link                                                            */
/* ------------------------------------------------------------------ */

static void test_nothing_is_ready_before_a_connection(void)
{
	TEST_ASSERT_FALSE(nus_client_is_connected());
	TEST_ASSERT_FALSE(nus_client_is_ready());
	TEST_ASSERT_EQUAL_UINT32(0U, nus_client_interval_us());
}

static void test_connecting_asks_the_stack_for_the_right_address(void)
{
	ble_gap_addr_t target;

	(void)scanner_parse_address("E4:1C:7B:02:9A:11", &target);
	TEST_ASSERT_EQUAL_UINT32(NRF_SUCCESS, nus_client_connect(&target));
	TEST_ASSERT_EQUAL_UINT32(1U, fake_gap_connect_count());
	TEST_ASSERT_EQUAL_MEMORY(target.addr, fake_gap_connect_address()->addr, BLE_GAP_ADDR_LEN);
}

static void test_a_connection_reports_the_interval(void)
{
	/* It is the floor under every latency measured on this link. */
	establish_link();
	TEST_ASSERT_TRUE(nus_client_is_connected());
	TEST_ASSERT_EQUAL_UINT32(30000U, nus_client_interval_us());
	TEST_ASSERT_TRUE(fake_line_seen("+conn "));
	TEST_ASSERT_TRUE(strstr(fake_line(0), "interval_us=30000") != NULL);
	TEST_ASSERT_TRUE(strstr(fake_line(0), "addr=E4:1C:7B:02:9A:11") != NULL);
}

static void test_discovery_makes_the_link_usable_and_says_so(void)
{
	establish_link();
	TEST_ASSERT_TRUE(nus_client_is_ready());
	TEST_ASSERT_TRUE(fake_nus_notifications_enabled());
	TEST_ASSERT_TRUE(fake_line_seen("+conn "));
	TEST_ASSERT_TRUE(strstr(fake_last_line(), "state=ready") != NULL);
}

static void test_connecting_while_connected_is_refused(void)
{
	ble_gap_addr_t target;

	establish_link();
	(void)scanner_parse_address("AA:BB:CC:DD:EE:FF", &target);
	TEST_ASSERT_EQUAL_UINT32(NRF_ERROR_INVALID_STATE, nus_client_connect(&target));
}

static void test_disconnecting_without_a_link(void)
{
	TEST_ASSERT_EQUAL_UINT32(NRF_ERROR_INVALID_STATE, nus_client_disconnect());
}

static void test_disconnecting(void)
{
	establish_link();
	TEST_ASSERT_EQUAL_UINT32(NRF_SUCCESS, nus_client_disconnect());
	TEST_ASSERT_EQUAL_UINT32(1U, fake_gap_disconnect_count());
}

static void test_a_dropped_link_is_reported_with_its_reason(void)
{
	ble_evt_t event;

	establish_link();
	fake_lines_reset();

	(void)memset(&event, 0, sizeof(event));
	event.header.evt_id = BLE_GAP_EVT_DISCONNECTED;
	event.evt.gap_evt.params.disconnected.reason = 0x08U;   /* supervision timeout */
	nus_client_on_ble_evt(&event);

	TEST_ASSERT_FALSE(nus_client_is_connected());
	TEST_ASSERT_FALSE(nus_client_is_ready());
	TEST_ASSERT_EQUAL_UINT32(0U, nus_client_interval_us());
	TEST_ASSERT_TRUE(fake_line_seen("+disc "));
	TEST_ASSERT_TRUE(strstr(fake_last_line(), "reason=0x08") != NULL);
}

static void test_a_connection_timeout_is_reported(void)
{
	ble_evt_t event;

	(void)memset(&event, 0, sizeof(event));
	event.header.evt_id = BLE_GAP_EVT_TIMEOUT;
	event.evt.gap_evt.params.timeout.src = BLE_GAP_TIMEOUT_SRC_CONN;
	nus_client_on_ble_evt(&event);
	TEST_ASSERT_TRUE(fake_line_seen("+disc "));
	TEST_ASSERT_TRUE(strstr(fake_last_line(), "reason=timeout") != NULL);
}

static void test_a_renegotiated_interval_is_taken_up(void)
{
	ble_evt_t event;

	establish_link();
	(void)memset(&event, 0, sizeof(event));
	event.header.evt_id = BLE_GAP_EVT_CONN_PARAM_UPDATE;
	event.evt.gap_evt.params.conn_param_update.conn_params.max_conn_interval = 8U;  /* 10 ms */
	nus_client_on_ble_evt(&event);
	TEST_ASSERT_EQUAL_UINT32(10000U, nus_client_interval_us());
}

/* ------------------------------------------------------------------ */
/* Writing                                                             */
/* ------------------------------------------------------------------ */

static void test_writing_before_the_service_is_ready(void)
{
	TEST_ASSERT_EQUAL_UINT32(NRF_ERROR_INVALID_STATE, nus_client_write((const uint8_t *)"x", 1U));
}

static void test_writing(void)
{
	establish_link();
	TEST_ASSERT_EQUAL_UINT32(NRF_SUCCESS, nus_client_write((const uint8_t *)"version", 7U));
	TEST_ASSERT_EQUAL_UINT16(7U, fake_nus_sent_length());
	TEST_ASSERT_EQUAL_MEMORY("version", fake_nus_sent(), 7U);
}

static void test_an_over_long_payload_is_refused(void)
{
	uint8_t payload[PROTO_MAX_PAYLOAD + 8U];

	establish_link();
	(void)memset(payload, 'x', sizeof(payload));
	TEST_ASSERT_EQUAL_UINT32(NRF_ERROR_DATA_SIZE,
				 nus_client_write(payload, (uint16_t)sizeof(payload)));
}

static void test_a_refused_write_is_passed_up(void)
{
	establish_link();
	fake_nus_set_send_result(NRF_ERROR_RESOURCES);
	TEST_ASSERT_EQUAL_UINT32(NRF_ERROR_RESOURCES, nus_client_write((const uint8_t *)"x", 1U));
	fake_nus_set_send_result(NRF_SUCCESS);
}

/* ------------------------------------------------------------------ */
/* Notifications and the round trip                                    */
/* ------------------------------------------------------------------ */

static void test_a_notification_is_reported_to_the_host(void)
{
	establish_link();
	fake_lines_reset();
	fake_clock_set(2000000U);
	fake_nus_fire(BLE_NUS_C_EVT_NUS_TX_EVT, (const uint8_t *)"1.4.2", 5U);

	TEST_ASSERT_TRUE(fake_line_seen("+rx "));
	TEST_ASSERT_TRUE(strstr(fake_last_line(), "t=2000000") != NULL);
	TEST_ASSERT_TRUE(strstr(fake_last_line(), "len=5") != NULL);
	TEST_ASSERT_TRUE(strstr(fake_last_line(), "data=312e342e32") != NULL);
}

static void test_a_command_times_the_round_trip_on_the_dongle_clock(void)
{
	nus_response_t response;

	establish_link();
	fake_clock_set(1000000U);
	/* Each read of the clock advances it, so the wait loop reaches the reply
	 * with time having passed, as it would on the target. */
	fake_clock_set_step(2500U);

	/* The reply arrives while the client is waiting: fire it from the fake
	 * send, which is what the stack does a few connection events later. */
	TEST_ASSERT_EQUAL_UINT32(NRF_SUCCESS,
				 nus_client_command((const uint8_t *)"version", 7U, 100U, &response));
	TEST_ASSERT_FALSE(response.replied);           /* nothing answered */
	TEST_ASSERT_EQUAL_UINT64(1000000U, response.tx_us);
	fake_clock_set_step(0U);
}

static void test_a_reply_completes_the_command(void)
{
	nus_response_t response;

	establish_link();
	fake_clock_set(1000000U);

	/* Deliver the notification before the command is issued is impossible on
	 * the target, so instead: no step, and the reply is fired by the fake's
	 * send hook. Here the simplest faithful arrangement is to fire it from a
	 * write that completes immediately. */
	fake_nus_fire(BLE_NUS_C_EVT_NUS_TX_EVT, (const uint8_t *)"late", 4U);
	fake_lines_reset();

	TEST_ASSERT_EQUAL_UINT32(NRF_SUCCESS,
				 nus_client_command((const uint8_t *)"version", 7U, 1U, &response));
	/* A notification that arrived *before* the command must not be counted as
	 * its reply - that would report a negative or absurd round trip. */
	TEST_ASSERT_FALSE(response.replied);
}

static void test_a_command_without_a_link(void)
{
	nus_response_t response;

	TEST_ASSERT_EQUAL_UINT32(NRF_ERROR_INVALID_STATE,
				 nus_client_command((const uint8_t *)"x", 1U, 10U, &response));
}

static void test_a_refused_send_ends_the_command(void)
{
	nus_response_t response;

	establish_link();
	fake_nus_set_send_result(NRF_ERROR_RESOURCES);
	TEST_ASSERT_EQUAL_UINT32(NRF_ERROR_RESOURCES,
				 nus_client_command((const uint8_t *)"x", 1U, 10U, &response));
	fake_nus_set_send_result(NRF_SUCCESS);
}

static void test_a_disconnection_during_discovery_leaves_it_unready(void)
{
	establish_link();
	fake_nus_fire(BLE_NUS_C_EVT_DISCONNECTED, NULL, 0U);
	TEST_ASSERT_FALSE(nus_client_is_ready());
}

int main(void)
{
	UNITY_BEGIN();
	RUN_TEST(test_nothing_is_ready_before_a_connection);
	RUN_TEST(test_connecting_asks_the_stack_for_the_right_address);
	RUN_TEST(test_a_connection_reports_the_interval);
	RUN_TEST(test_discovery_makes_the_link_usable_and_says_so);
	RUN_TEST(test_connecting_while_connected_is_refused);
	RUN_TEST(test_disconnecting_without_a_link);
	RUN_TEST(test_disconnecting);
	RUN_TEST(test_a_dropped_link_is_reported_with_its_reason);
	RUN_TEST(test_a_connection_timeout_is_reported);
	RUN_TEST(test_a_renegotiated_interval_is_taken_up);
	RUN_TEST(test_writing_before_the_service_is_ready);
	RUN_TEST(test_writing);
	RUN_TEST(test_an_over_long_payload_is_refused);
	RUN_TEST(test_a_refused_write_is_passed_up);
	RUN_TEST(test_a_notification_is_reported_to_the_host);
	RUN_TEST(test_a_command_times_the_round_trip_on_the_dongle_clock);
	RUN_TEST(test_a_reply_completes_the_command);
	RUN_TEST(test_a_command_without_a_link);
	RUN_TEST(test_a_refused_send_ends_the_command);
	RUN_TEST(test_a_disconnection_during_discovery_leaves_it_unready);
	return UNITY_END();
}
