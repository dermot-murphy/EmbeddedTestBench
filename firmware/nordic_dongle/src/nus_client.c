/**
 * @file nus_client.c
 * @brief UART over BLE as a command/response channel, with round-trip timing.
 *
 * Traces to: BLE-FR-040 .. BLE-FR-044, BLE-DD-NUS.
 */

#include "nus_client.h"

#include <stdio.h>
#include <string.h>

#include "app_error.h"
#include "ble_db_discovery.h"
#include "ble_nus_c.h"
#include "nrf_ble_gatt.h"
#include "nrf_sdh_ble.h"

#include "app_ble_config.h"
#include "ble_scanner.h"
#include "cdc_acm.h"
#include "timestamp.h"

/** Connection parameters. The interval bounds the latency that can be measured:
 *  a reply is delivered at a connection event, so a 7.5 ms to 30 ms window is
 *  requested to keep the quantisation small without asking for a rate that a
 *  battery sensor will refuse. */
#define CONN_INTERVAL_MIN_UNITS		6U		/**< 7.5 ms / 1.25 ms */
#define CONN_INTERVAL_MAX_UNITS		24U		/**< 30 ms / 1.25 ms */
#define CONN_SLAVE_LATENCY		0U
#define CONN_SUPERVISION_UNITS		400U		/**< 4 s / 10 ms */

#define SCAN_INTERVAL_UNITS		160U
#define SCAN_WINDOW_UNITS		80U

BLE_NUS_C_DEF(m_nus_client);

static uint16_t			m_conn_handle = BLE_CONN_HANDLE_INVALID;
static uint32_t			m_interval_us;
static bool			m_ready;

static volatile bool		m_awaiting_reply;
static volatile bool		m_reply_arrived;
static uint64_t			m_tx_us;
static uint64_t			m_rx_us;
static uint16_t			m_reply_length;
static uint8_t			m_reply[PROTO_MAX_PAYLOAD];

/**
 * @brief Report received bytes to the host as a @c +rx event.
 */
static void report_rx(const uint8_t * p_data, uint16_t length, uint64_t when_us)
{
	char		hex[(PROTO_MAX_PAYLOAD * 2U) + 1U];
	uint16_t	index;
	uint16_t	kept = length;

	if (kept > PROTO_MAX_PAYLOAD)
	{
		kept = PROTO_MAX_PAYLOAD;
	}
	for (index = 0U; index < kept; index++)
	{
		(void)sprintf(&hex[index * 2U], "%02x", p_data[index]);
	}
	hex[kept * 2U] = '\0';

	(void)cdc_acm_send_format("+rx t=%llu len=%u data=%s",
				  (unsigned long long)when_us,
				  (unsigned)length,
				  hex);
}

static void nus_c_event_handler(ble_nus_c_t * p_nus_c, ble_nus_c_evt_t const * p_evt)
{
	uint64_t when_us = timestamp_now_us();

	switch (p_evt->evt_type)
	{
	case BLE_NUS_C_EVT_DISCOVERY_COMPLETE:
		(void)ble_nus_c_handles_assign(p_nus_c,
					       p_evt->conn_handle,
					       &p_evt->handles);
		(void)ble_nus_c_tx_notif_enable(p_nus_c);
		m_ready = true;
		(void)cdc_acm_send_format("+conn t=%llu state=ready interval_us=%lu",
					  (unsigned long long)when_us,
					  (unsigned long)m_interval_us);
		break;

	case BLE_NUS_C_EVT_NUS_TX_EVT:
		/* Timestamp taken on entry, before any formatting, because this is
		 * the arrival the latency measurement is made from. */
		if (m_awaiting_reply && !m_reply_arrived)
		{
			m_reply_length = p_evt->data_len;
			if (m_reply_length > PROTO_MAX_PAYLOAD)
			{
				m_reply_length = PROTO_MAX_PAYLOAD;
			}
			(void)memcpy(m_reply, p_evt->p_data, m_reply_length);
			m_rx_us        = when_us;
			m_reply_arrived = true;
		}
		report_rx(p_evt->p_data, p_evt->data_len, when_us);
		break;

	case BLE_NUS_C_EVT_DISCONNECTED:
		m_ready       = false;
		m_conn_handle = BLE_CONN_HANDLE_INVALID;
		break;

	default:
		break;
	}
}

uint32_t nus_client_init(nrf_ble_gq_t * p_gatt_queue)
{
	ble_nus_c_init_t init;

	(void)memset(&init, 0, sizeof(init));
	init.evt_handler   = nus_c_event_handler;
	init.error_handler = NULL;
	init.p_gatt_queue  = p_gatt_queue;

	return ble_nus_c_init(&m_nus_client, &init);
}

uint32_t nus_client_connect(const ble_gap_addr_t * p_address)
{
	ble_gap_scan_params_t	scan_params;
	ble_gap_conn_params_t	conn_params;

	if (m_conn_handle != BLE_CONN_HANDLE_INVALID)
	{
		return NRF_ERROR_INVALID_STATE;
	}

	(void)memset(&scan_params, 0, sizeof(scan_params));
	scan_params.active        = 0U;
	scan_params.interval      = SCAN_INTERVAL_UNITS;
	scan_params.window        = SCAN_WINDOW_UNITS;
	scan_params.timeout       = 500U;		/**< 5 s, in 10 ms units */
	scan_params.scan_phys     = BLE_GAP_PHY_1MBPS;
	scan_params.filter_policy = BLE_GAP_SCAN_FP_ACCEPT_ALL;

	(void)memset(&conn_params, 0, sizeof(conn_params));
	conn_params.min_conn_interval = CONN_INTERVAL_MIN_UNITS;
	conn_params.max_conn_interval = CONN_INTERVAL_MAX_UNITS;
	conn_params.slave_latency     = CONN_SLAVE_LATENCY;
	conn_params.conn_sup_timeout  = CONN_SUPERVISION_UNITS;

	return sd_ble_gap_connect(p_address, &scan_params, &conn_params, APP_BLE_CONN_CFG_TAG);
}

uint32_t nus_client_disconnect(void)
{
	if (m_conn_handle == BLE_CONN_HANDLE_INVALID)
	{
		return NRF_ERROR_INVALID_STATE;
	}

	return sd_ble_gap_disconnect(m_conn_handle,
				     BLE_HCI_REMOTE_USER_TERMINATED_CONNECTION);
}

bool nus_client_is_ready(void)
{
	return m_ready;
}

bool nus_client_is_connected(void)
{
	return m_conn_handle != BLE_CONN_HANDLE_INVALID;
}

uint32_t nus_client_interval_us(void)
{
	return m_interval_us;
}

uint32_t nus_client_write(const uint8_t * p_data, uint16_t length)
{
	if (!m_ready)
	{
		return NRF_ERROR_INVALID_STATE;
	}
	if (length > PROTO_MAX_PAYLOAD)
	{
		return NRF_ERROR_DATA_SIZE;
	}

	return ble_nus_c_string_send(&m_nus_client, (uint8_t *)p_data, length);
}

uint32_t nus_client_command(const uint8_t *  p_data,
			    uint16_t         length,
			    uint32_t         timeout_ms,
			    nus_response_t * p_response)
{
	uint32_t	error;
	uint64_t	deadline_us;

	(void)memset(p_response, 0, sizeof(*p_response));

	if (!m_ready)
	{
		return NRF_ERROR_INVALID_STATE;
	}

	m_reply_arrived  = false;
	m_reply_length   = 0U;
	m_awaiting_reply = true;

	/* Timestamp as close to the write as possible. The SoftDevice queues the
	 * packet for the next connection event, so this is the instant the
	 * request left the application, not the instant it left the antenna; the
	 * difference is bounded by the connection interval, which is reported
	 * alongside so the figure can be read correctly. */
	m_tx_us = timestamp_now_us();
	error   = ble_nus_c_string_send(&m_nus_client, (uint8_t *)p_data, length);
	if (error != NRF_SUCCESS)
	{
		m_awaiting_reply = false;
		return error;
	}

	deadline_us = m_tx_us + ((uint64_t)timeout_ms * 1000U);
	while (!m_reply_arrived && (timestamp_now_us() < deadline_us))
	{
		/* Keep USB alive while waiting: a five second timeout must not
		 * cost the host five seconds of advertising events. */
		cdc_acm_process();
	}

	m_awaiting_reply = false;

	p_response->tx_us = m_tx_us;
	if (m_reply_arrived)
	{
		p_response->replied       = true;
		p_response->rx_us         = m_rx_us;
		p_response->round_trip_us = timestamp_elapsed_us(m_tx_us, m_rx_us);
		p_response->length        = m_reply_length;
		(void)memcpy(p_response->data, m_reply, m_reply_length);
	}

	return NRF_SUCCESS;
}

void nus_client_on_ble_evt(const ble_evt_t * p_ble_evt)
{
	const ble_gap_evt_t *	p_gap = &p_ble_evt->evt.gap_evt;
	uint64_t		when_us = timestamp_now_us();
	char			address[18];

	switch (p_ble_evt->header.evt_id)
	{
	case BLE_GAP_EVT_CONNECTED:
		m_conn_handle = p_gap->conn_handle;
		m_interval_us = (uint32_t)p_gap->params.connected.conn_params.min_conn_interval * 1250U;
		scanner_format_address(&p_gap->params.connected.peer_addr, address);
		(void)cdc_acm_send_format(
			"+conn t=%llu addr=%s state=linked interval_us=%lu",
			(unsigned long long)when_us, address,
			(unsigned long)m_interval_us);
		break;

	case BLE_GAP_EVT_DISCONNECTED:
		m_conn_handle = BLE_CONN_HANDLE_INVALID;
		m_ready       = false;
		m_interval_us = 0U;
		(void)cdc_acm_send_format("+disc t=%llu reason=0x%02x",
					  (unsigned long long)when_us,
					  (unsigned)p_gap->params.disconnected.reason);
		break;

	case BLE_GAP_EVT_CONN_PARAM_UPDATE:
		m_interval_us =
			(uint32_t)p_gap->params.conn_param_update.conn_params.max_conn_interval * 1250U;
		break;

	case BLE_GAP_EVT_TIMEOUT:
		if (p_gap->params.timeout.src == BLE_GAP_TIMEOUT_SRC_CONN)
		{
			(void)cdc_acm_send_format("+disc t=%llu reason=timeout",
						  (unsigned long long)when_us);
		}
		break;

	default:
		break;
	}

	ble_nus_c_on_ble_evt(p_ble_evt, &m_nus_client);
}

void nus_client_on_db_disc_evt(void * p_evt)
{
	ble_nus_c_on_db_disc_evt(&m_nus_client, (ble_db_discovery_evt_t *)p_evt);
}
