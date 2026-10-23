/**
 * @file test_dfu_client.c
 * @brief The DFU client: finding a target's DFU service, and carrying bytes (#244).
 *
 * Traces to: BLE-FR-121, BLE-DD-DFU, SWE4-UT-FWUNIT.
 */

#include <string.h>

#include "unity.h"

#include "ble.h"
#include "ble_db_discovery.h"
#include "dfu_client.h"
#include "fakes.h"
#include "nrf_ble_gq.h"

#define TEST_CONN		4U
#define TEST_CONTROL		0x0010U
#define TEST_CONTROL_CCCD	0x0011U
#define TEST_PACKET		0x0013U
/** The vendor UUID type the fake gives the DFU base. */
#define TEST_DFU_TYPE	3U

static nrf_ble_gq_t	m_queue;
static nrf_ble_gatt_t	m_gatt;
static bool		m_answer_pending;
static uint8_t		m_answer[8];
static uint16_t		m_answer_len;

/** Discovery's report of a bootloader's DFU service. */
static void test_discover(bool with_packet)
{
	ble_db_discovery_evt_t evt;

	(void)memset(&evt, 0, sizeof(evt));
	evt.evt_type                             = BLE_DB_DISCOVERY_COMPLETE;
	evt.conn_handle                          = TEST_CONN;
	evt.params.discovered_db.srv_uuid.uuid   = 0xFE59U;
	evt.params.discovered_db.srv_uuid.type   = BLE_UUID_TYPE_BLE;
	evt.params.discovered_db.char_count      = with_packet ? 2U : 1U;
	evt.params.discovered_db.charateristics[0].characteristic.uuid.uuid = 0x0001U;
	evt.params.discovered_db.charateristics[0].characteristic.uuid.type = TEST_DFU_TYPE;
	evt.params.discovered_db.charateristics[0].characteristic.handle_value = TEST_CONTROL;
	evt.params.discovered_db.charateristics[0].cccd_handle = TEST_CONTROL_CCCD;
	evt.params.discovered_db.charateristics[1].characteristic.uuid.uuid = 0x0002U;
	evt.params.discovered_db.charateristics[1].characteristic.uuid.type = TEST_DFU_TYPE;
	evt.params.discovered_db.charateristics[1].characteristic.handle_value = TEST_PACKET;
	dfu_client_on_db_disc_evt(&evt);
}

/** The target notifies the Control Point, as a bootloader answers. */
static void test_notify(uint16_t handle, const uint8_t * data, uint16_t length)
{
	ble_evt_t evt;

	(void)memset(&evt, 0, sizeof(evt));
	evt.header.evt_id                   = BLE_GATTC_EVT_HVX;
	evt.evt.gattc_evt.conn_handle       = TEST_CONN;
	evt.evt.gattc_evt.params.hvx.handle = handle;
	evt.evt.gattc_evt.params.hvx.type   = BLE_GATT_HVX_NOTIFICATION;
	evt.evt.gattc_evt.params.hvx.len    = length;
	(void)memcpy(evt.evt.gattc_evt.params.hvx.data, data, length);
	dfu_client_on_ble_evt(&evt);
}

/** Answer once, while the client waits: the bootloader's response arrives. */
static void test_answer_hook(void)
{
	if (m_answer_pending)
	{
		m_answer_pending = false;
		test_notify(TEST_CONTROL, m_answer, m_answer_len);
	}
}

static void test_disconnect(void)
{
	ble_evt_t evt;

	(void)memset(&evt, 0, sizeof(evt));
	evt.header.evt_id           = BLE_GAP_EVT_DISCONNECTED;
	evt.evt.gap_evt.conn_handle = TEST_CONN;
	dfu_client_on_ble_evt(&evt);
}

void setUp(void)
{
	fake_lines_reset();
	fake_clock_reset();
	fake_clock_set_step(500U);
	fake_gq_reset();
	fake_host_set_process_hook(test_answer_hook);
	m_answer_pending = false;
	(void)dfu_client_init(&m_queue, &m_gatt);
}

void tearDown(void)
{
	test_disconnect();
	fake_host_set_process_hook(NULL);
}

/* ------------------------------------------------------------------ */

static void test_the_dfu_service_is_registered_with_discovery(void)
{
	TEST_ASSERT_EQUAL_UINT32(1U, fake_db_discovery_registered_count());
	TEST_ASSERT_EQUAL_HEX16(0xFE59U, fake_db_discovery_registered(0U)->uuid);
	TEST_ASSERT_EQUAL_UINT8(BLE_UUID_TYPE_BLE, fake_db_discovery_registered(0U)->type);
}

static void test_a_found_service_turns_notifications_on_and_says_so(void)
{
	test_discover(true);
	TEST_ASSERT_TRUE(dfu_client_is_ready());
	TEST_ASSERT_EQUAL_UINT32(1U, fake_gq_write_count());
	TEST_ASSERT_EQUAL_HEX16(TEST_CONTROL_CCCD, fake_gq_write(0U)->handle);
	TEST_ASSERT_EQUAL_UINT8(BLE_GATT_OP_WRITE_REQ, fake_gq_write(0U)->write_op);
	TEST_ASSERT_EQUAL_UINT16(2U, fake_gq_write(0U)->len);
	TEST_ASSERT_EQUAL_HEX8(0x01U, fake_gq_write(0U)->data[0]);
	TEST_ASSERT_EQUAL_UINT16(TEST_CONN, fake_gq_write(0U)->conn_handle);
	TEST_ASSERT_TRUE(fake_line_seen("+dfu "));
	TEST_ASSERT_TRUE(strstr(fake_last_line(), "state=ready") != NULL);
}

static void test_a_dfu_link_asks_for_a_short_interval(void)
{
	/* 191 s for 298 KB at 30 ms on 5C1712; a Kepler spec allows 180 (#244). */
	test_discover(true);
	TEST_ASSERT_EQUAL_UINT32(1U, fake_gap_param_update_count());
	TEST_ASSERT_EQUAL_UINT16(6U, fake_gap_param_update()->min_conn_interval);
	TEST_ASSERT_EQUAL_UINT16(6U, fake_gap_param_update()->max_conn_interval);
	TEST_ASSERT_EQUAL_UINT16(400U, fake_gap_param_update()->conn_sup_timeout);
}

static void test_a_service_without_its_packet_characteristic_is_not_used(void)
{
	test_discover(false);
	TEST_ASSERT_FALSE(dfu_client_is_ready());
	TEST_ASSERT_TRUE(strstr(fake_last_line(), "state=incomplete") != NULL);
}

static void test_another_service_is_ignored(void)
{
	ble_db_discovery_evt_t evt;

	(void)memset(&evt, 0, sizeof(evt));
	evt.evt_type                           = BLE_DB_DISCOVERY_COMPLETE;
	evt.params.discovered_db.srv_uuid.uuid = 0x0001U;    /* the UART service */
	evt.params.discovered_db.srv_uuid.type = 2U;
	dfu_client_on_db_disc_evt(&evt);
	TEST_ASSERT_FALSE(dfu_client_is_ready());
	TEST_ASSERT_EQUAL_UINT32(0U, fake_gq_write_count());
}

static void test_a_control_point_request_returns_its_response(void)
{
	static const uint8_t	select[] = { 0x06U, 0x01U };
	static const uint8_t	answer[] = { 0x60U, 0x06U, 0x01U, 0x00U, 0x01U, 0x00U, 0x00U };
	uint8_t			response[DFU_CLIENT_MAX_RESPONSE];
	uint16_t		length = 0U;

	test_discover(true);
	(void)memcpy(m_answer, answer, sizeof(answer));
	m_answer_len     = sizeof(answer);
	m_answer_pending = true;

	TEST_ASSERT_EQUAL_UINT32(NRF_SUCCESS,
				 dfu_client_control(select, sizeof(select), 1000U, response, &length));
	TEST_ASSERT_EQUAL_UINT16(sizeof(answer), length);
	TEST_ASSERT_EQUAL_MEMORY(answer, response, sizeof(answer));
	TEST_ASSERT_EQUAL_HEX16(TEST_CONTROL, fake_gq_write(1U)->handle);
	TEST_ASSERT_EQUAL_UINT8(BLE_GATT_OP_WRITE_REQ, fake_gq_write(1U)->write_op);
	TEST_ASSERT_EQUAL_MEMORY(select, fake_gq_write(1U)->data, sizeof(select));
}

static void test_no_response_in_time_is_reported_as_none(void)
{
	static const uint8_t	execute[] = { 0x04U };
	uint8_t			response[DFU_CLIENT_MAX_RESPONSE];
	uint16_t		length = 99U;

	test_discover(true);
	TEST_ASSERT_EQUAL_UINT32(NRF_SUCCESS,
				 dfu_client_control(execute, sizeof(execute), 5U, response, &length));
	TEST_ASSERT_EQUAL_UINT16(0U, length);
}

static void test_a_notification_from_elsewhere_is_not_the_response(void)
{
	static const uint8_t	execute[] = { 0x04U };
	static const uint8_t	stray[]   = { 0xAAU };
	uint8_t			response[DFU_CLIENT_MAX_RESPONSE];
	uint16_t		length = 0U;

	test_discover(true);
	test_notify(TEST_CONTROL, stray, sizeof(stray));      /* before the request */
	TEST_ASSERT_EQUAL_UINT32(NRF_SUCCESS,
				 dfu_client_control(execute, sizeof(execute), 5U, response, &length));
	TEST_ASSERT_EQUAL_UINT16(0U, length);
}

static void test_a_packet_is_written_without_a_response(void)
{
	static const uint8_t data[] = { 0x01U, 0x02U, 0x03U };

	test_discover(true);
	TEST_ASSERT_EQUAL_UINT32(NRF_SUCCESS, dfu_client_packet(data, sizeof(data), 100U));
	TEST_ASSERT_EQUAL_HEX16(TEST_PACKET, fake_gq_write(1U)->handle);
	TEST_ASSERT_EQUAL_UINT8(BLE_GATT_OP_WRITE_CMD, fake_gq_write(1U)->write_op);
	TEST_ASSERT_EQUAL_MEMORY(data, fake_gq_write(1U)->data, sizeof(data));
}

static void test_a_packet_is_split_to_fit_the_mtu(void)
{
	/* Before the MTU exchange the link carries 20 bytes a write: a 144-byte
	 * init packet in one write was refused on 5C1712 (#244). */
	uint8_t		data[DFU_CLIENT_MAX_WRITE];
	uint32_t	index;

	for (index = 0U; index < sizeof(data); index++)
	{
		data[index] = (uint8_t)index;
	}
	test_discover(true);
	fake_gatt_set_eff_mtu(23U);
	TEST_ASSERT_EQUAL_UINT32(NRF_SUCCESS, dfu_client_packet(data, 144U, 100U));
	TEST_ASSERT_EQUAL_UINT32(1U + 8U, fake_gq_write_count());    /* CCCD, 7 x 20 and 4 */
	TEST_ASSERT_EQUAL_UINT16(20U, fake_gq_write(1U)->len);
	TEST_ASSERT_EQUAL_UINT16(4U, fake_gq_write(8U)->len);
	TEST_ASSERT_EQUAL_MEMORY(&data[140], fake_gq_write(8U)->data, 4U);
}

static void test_with_a_receipt_interval_each_receipt_is_waited_for(void)
{
	static const uint8_t	prn_set[] = { 0x02U, 0x02U, 0x00U };        /* every 2 */
	static const uint8_t	answer[]  = { 0x60U, 0x02U, 0x01U };
	static const uint8_t	receipt[] = { 0x60U, 0x03U, 0x01U, 0x10U, 0x00U, 0x00U, 0x00U };
	uint8_t			response[DFU_CLIENT_MAX_RESPONSE];
	uint16_t		length = 0U;
	uint8_t			data[16];

	(void)memset(data, 0xA5, sizeof(data));
	test_discover(true);
	(void)memcpy(m_answer, answer, sizeof(answer));
	m_answer_len     = sizeof(answer);
	m_answer_pending = true;
	(void)dfu_client_control(prn_set, sizeof(prn_set), 100U, response, &length);

	/* The first packet owes nothing; the second owes a receipt. */
	TEST_ASSERT_EQUAL_UINT32(NRF_SUCCESS, dfu_client_packet(data, 8U, 100U));
	(void)memcpy(m_answer, receipt, sizeof(receipt));
	m_answer_len     = sizeof(receipt);
	m_answer_pending = true;
	TEST_ASSERT_EQUAL_UINT32(NRF_SUCCESS, dfu_client_packet(data, 8U, 100U));
	TEST_ASSERT_FALSE(m_answer_pending);                 /* it was waited for */

	/* A receipt that never comes is a timeout, not a silent loss. */
	TEST_ASSERT_EQUAL_UINT32(NRF_SUCCESS, dfu_client_packet(data, 8U, 5U));
	TEST_ASSERT_EQUAL_UINT32(NRF_ERROR_TIMEOUT, dfu_client_packet(data, 8U, 5U));
}

static void test_a_refused_receipt_interval_is_not_waited_on(void)
{
	/* A reduced bootloader may not support it: then nothing is owed. */
	static const uint8_t	prn_set[] = { 0x02U, 0x02U, 0x00U };
	static const uint8_t	refused[] = { 0x60U, 0x02U, 0x02U };        /* not supported */
	uint8_t			response[DFU_CLIENT_MAX_RESPONSE];
	uint16_t		length = 0U;
	uint8_t			data[8];

	(void)memset(data, 0, sizeof(data));
	test_discover(true);
	(void)memcpy(m_answer, refused, sizeof(refused));
	m_answer_len     = sizeof(refused);
	m_answer_pending = true;
	(void)dfu_client_control(prn_set, sizeof(prn_set), 100U, response, &length);
	TEST_ASSERT_EQUAL_UINT32(NRF_SUCCESS, dfu_client_packet(data, sizeof(data), 5U));
	TEST_ASSERT_EQUAL_UINT32(NRF_SUCCESS, dfu_client_packet(data, sizeof(data), 5U));
	TEST_ASSERT_EQUAL_UINT32(NRF_SUCCESS, dfu_client_packet(data, sizeof(data), 5U));
}

static void test_a_full_queue_is_waited_out(void)
{
	static const uint8_t data[] = { 0x01U };

	test_discover(true);
	fake_gq_fail_next(3U, NRF_ERROR_RESOURCES);
	TEST_ASSERT_EQUAL_UINT32(NRF_SUCCESS, dfu_client_packet(data, sizeof(data), 100U));
	TEST_ASSERT_EQUAL_UINT32(2U, fake_gq_write_count());
}

static void test_a_queue_that_stays_full_is_reported(void)
{
	static const uint8_t data[] = { 0x01U };

	test_discover(true);
	fake_gq_fail_next(100000U, NRF_ERROR_RESOURCES);
	TEST_ASSERT_EQUAL_UINT32(NRF_ERROR_RESOURCES, dfu_client_packet(data, sizeof(data), 2U));
}

static void test_nothing_is_written_without_a_dfu_service(void)
{
	static const uint8_t	data[] = { 0x01U };
	uint8_t			response[DFU_CLIENT_MAX_RESPONSE];
	uint16_t		length;

	TEST_ASSERT_EQUAL_UINT32(NRF_ERROR_INVALID_STATE,
				 dfu_client_control(data, 1U, 5U, response, &length));
	TEST_ASSERT_EQUAL_UINT32(NRF_ERROR_INVALID_STATE, dfu_client_packet(data, 1U, 5U));
}

static void test_an_over_long_write_is_refused(void)
{
	uint8_t			data[DFU_CLIENT_MAX_WRITE + 1U];
	uint8_t			response[DFU_CLIENT_MAX_RESPONSE];
	uint16_t		length;

	(void)memset(data, 0, sizeof(data));
	test_discover(true);
	TEST_ASSERT_EQUAL_UINT32(NRF_ERROR_DATA_SIZE,
				 dfu_client_control(data, sizeof(data), 5U, response, &length));
	TEST_ASSERT_EQUAL_UINT32(NRF_ERROR_DATA_SIZE, dfu_client_packet(data, sizeof(data), 5U));
}

static void test_a_disconnection_forgets_the_service(void)
{
	test_discover(true);
	test_disconnect();
	TEST_ASSERT_FALSE(dfu_client_is_ready());
}

int main(void)
{
	UNITY_BEGIN();
	RUN_TEST(test_the_dfu_service_is_registered_with_discovery);
	RUN_TEST(test_a_found_service_turns_notifications_on_and_says_so);
	RUN_TEST(test_a_dfu_link_asks_for_a_short_interval);
	RUN_TEST(test_a_service_without_its_packet_characteristic_is_not_used);
	RUN_TEST(test_another_service_is_ignored);
	RUN_TEST(test_a_control_point_request_returns_its_response);
	RUN_TEST(test_no_response_in_time_is_reported_as_none);
	RUN_TEST(test_a_notification_from_elsewhere_is_not_the_response);
	RUN_TEST(test_a_packet_is_written_without_a_response);
	RUN_TEST(test_a_packet_is_split_to_fit_the_mtu);
	RUN_TEST(test_with_a_receipt_interval_each_receipt_is_waited_for);
	RUN_TEST(test_a_refused_receipt_interval_is_not_waited_on);
	RUN_TEST(test_a_full_queue_is_waited_out);
	RUN_TEST(test_a_queue_that_stays_full_is_reported);
	RUN_TEST(test_nothing_is_written_without_a_dfu_service);
	RUN_TEST(test_an_over_long_write_is_refused);
	RUN_TEST(test_a_disconnection_forgets_the_service);
	return UNITY_END();
}
