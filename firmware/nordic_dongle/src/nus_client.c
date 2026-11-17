/**
 * @file nus_client.c
 * @brief UART over BLE as a command/response channel, with round-trip timing.
 *
 * Traces to: BLE-FR-040 .. BLE-FR-044, BLE-DD-NUS.
 */

#include "nus_client.h"

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
#define NUS_CLIENT_CONN_INTERVAL_MIN_UNITS		6U		/**< 7.5 ms / 1.25 ms */
#define NUS_CLIENT_CONN_INTERVAL_MAX_UNITS		24U		/**< 30 ms / 1.25 ms */
#define NUS_CLIENT_CONN_SLAVE_LATENCY		0U
#define NUS_CLIENT_CONN_SUPERVISION_UNITS		400U		/**< 4 s / 10 ms */

/* While connecting, listen all the time: window equal to interval. Nothing
 * else needs the radio then, and at half duty a sensor advertising every 9 s
 * was missed more often than not (#39). */
#define NUS_CLIENT_SCAN_INTERVAL_UNITS		160U
#define NUS_CLIENT_SCAN_WINDOW_UNITS		160U

/** The SoftDevice counts the connect timeout in 10 ms units. */
#define NUS_CLIENT_CONNECT_TIMEOUT_UNIT_MS		10U

/** Microseconds in one 1.25 ms connection interval unit, and in a millisecond. */
#define NUS_CLIENT_US_PER_INTERVAL_UNIT		1250U
#define NUS_CLIENT_US_PER_MS			1000U

/** No connection, in the type the handles are kept in. */
#define NUS_CLIENT_NO_CONNECTION		((uint16_t)BLE_CONN_HANDLE_INVALID)

/** Bits in one hex digit, and the low digit of a byte. */
#define NUS_CLIENT_NIBBLE_BITS			4U
#define NUS_CLIENT_NIBBLE_MASK			0x0FU

BLE_NUS_C_DEF(m_nus_client);

static uint16_t			m_conn_handle = NUS_CLIENT_NO_CONNECTION;
static ble_db_discovery_t *	m_p_db_discovery;
static uint32_t			m_interval_us;
static bool			m_ready;

/* A connection being made, and whether to drop it as soon as it comes up: set
 * when the host asked to disconnect after the stack had completed the
 * connection but before it was reported (#251). */
static bool			m_connecting;
static bool			m_drop_on_connect;

static volatile bool		m_awaiting_reply;
static volatile bool		m_reply_arrived;
static uint64_t			m_rx_us;
static uint16_t			m_reply_length;
static uint8_t			m_reply[PROTOCOL_MAX_PAYLOAD];

/**
 * @brief Report received bytes to the host as a @c +rx event.
 */
static void nus_client_report_rx(const uint8_t * p_data, uint16_t length, uint64_t when_us)
{
	/* Received bytes are reported in lower-case hex. */
	static const char	digits[] = "0123456789abcdef";
	char		time_text[TIMESTAMP_TEXT_SIZE];
	char		hex[(PROTOCOL_MAX_PAYLOAD * 2U) + 1U];
	uint16_t	index;
	uint16_t	kept = length;

	if (kept > PROTOCOL_MAX_PAYLOAD)
	{
		kept = PROTOCOL_MAX_PAYLOAD;
	}
	for (index = 0U; index < kept; index++)
	{
		hex[index * 2U]        = digits[p_data[index] >> NUS_CLIENT_NIBBLE_BITS];
		hex[(index * 2U) + 1U] = digits[p_data[index] & NUS_CLIENT_NIBBLE_MASK];
	}
	hex[kept * 2U] = '\0';

	(void)cdc_acm_send_format("+rx t=%s len=%u data=%s",
				  timestamp_format_us(when_us, time_text),
				  (unsigned)length,
				  hex);
}

static void nus_c_event_handler(ble_nus_c_t * p_nus_c, ble_nus_c_evt_t const * p_evt)
{
	char		time_text[TIMESTAMP_TEXT_SIZE];
	uint64_t when_us = timestamp_now_us();

	switch (p_evt->evt_type)
	{
	case BLE_NUS_C_EVT_DISCOVERY_COMPLETE:
		(void)ble_nus_c_handles_assign(p_nus_c,
					       p_evt->conn_handle,
					       &p_evt->handles);
		(void)ble_nus_c_tx_notif_enable(p_nus_c);
		m_ready = true;
		(void)cdc_acm_send_format("+conn t=%s state=ready interval_us=%lu",
					  timestamp_format_us(when_us, time_text),
					  (unsigned long)m_interval_us);
		break;

	case BLE_NUS_C_EVT_NUS_TX_EVT:
		/* Timestamp taken on entry, before any formatting, because this is
		 * the arrival the latency measurement is made from. */
		if (m_awaiting_reply && !m_reply_arrived)
		{
			m_reply_length = p_evt->data_len;
			if (m_reply_length > PROTOCOL_MAX_PAYLOAD)
			{
				m_reply_length = PROTOCOL_MAX_PAYLOAD;
			}
			(void)memcpy(m_reply, p_evt->p_data, m_reply_length);
			m_rx_us        = when_us;
			m_reply_arrived = true;
		}
		nus_client_report_rx(p_evt->p_data, p_evt->data_len, when_us);
		break;

	case BLE_NUS_C_EVT_DISCONNECTED:
		m_ready       = false;
		m_conn_handle = NUS_CLIENT_NO_CONNECTION;
		break;

	default:
		break;
	}
}

uint32_t nus_client_init(nrf_ble_gq_t * p_gatt_queue, ble_db_discovery_t * p_db_discovery)
{
	ble_nus_c_init_t init;

	m_p_db_discovery = p_db_discovery;

	(void)memset(&init, 0, sizeof(init));
	init.evt_handler   = nus_c_event_handler;
	init.error_handler = NULL;
	init.p_gatt_queue  = p_gatt_queue;

	return ble_nus_c_init(&m_nus_client, &init);
}

uint32_t nus_client_connect(const ble_gap_addr_t * p_address, uint32_t timeout_ms)
{
	ble_gap_scan_params_t	scan_params;
	ble_gap_conn_params_t	conn_params;
	uint32_t		error;

	if (m_conn_handle != NUS_CLIENT_NO_CONNECTION)
	{
		error = NRF_ERROR_INVALID_STATE;
	}
	else if (m_connecting)
	{
		error = NRF_ERROR_BUSY;
	}
	else
	{
		(void)memset(&scan_params, 0, sizeof(scan_params));
		scan_params.active        = 0U;
		scan_params.interval      = NUS_CLIENT_SCAN_INTERVAL_UNITS;
		scan_params.window        = NUS_CLIENT_SCAN_WINDOW_UNITS;
		scan_params.timeout       = (uint16_t)(timeout_ms / NUS_CLIENT_CONNECT_TIMEOUT_UNIT_MS);
		scan_params.scan_phys     = BLE_GAP_PHY_1MBPS;
		scan_params.filter_policy = BLE_GAP_SCAN_FP_ACCEPT_ALL;

		(void)memset(&conn_params, 0, sizeof(conn_params));
		conn_params.min_conn_interval = NUS_CLIENT_CONN_INTERVAL_MIN_UNITS;
		conn_params.max_conn_interval = NUS_CLIENT_CONN_INTERVAL_MAX_UNITS;
		conn_params.slave_latency     = NUS_CLIENT_CONN_SLAVE_LATENCY;
		conn_params.conn_sup_timeout  = NUS_CLIENT_CONN_SUPERVISION_UNITS;

		error = sd_ble_gap_connect(p_address, &scan_params, &conn_params,
					   APP_BLE_CONFIG_CONN_CFG_TAG);
		if (error == NRF_SUCCESS)
		{
			m_connecting      = true;
			m_drop_on_connect = false;
		}
	}

	return error;
}

uint32_t nus_client_disconnect(void)
{
	char		time_text[TIMESTAMP_TEXT_SIZE];
	uint32_t	error = NRF_SUCCESS;

	if (m_conn_handle != NUS_CLIENT_NO_CONNECTION)
	{
		error = sd_ble_gap_disconnect(m_conn_handle,
					      BLE_HCI_REMOTE_USER_TERMINATED_CONNECTION);
	}
	else if (!m_connecting)
	{
		error = NRF_ERROR_INVALID_STATE;
	}
	else
	{
		/* Without this, a connection the host had given up on went on being
		 * made, every connect was refused until it ended, and if it found
		 * the sensor the dongle was linked without the host knowing (#251). */
		m_connecting = false;
		if (sd_ble_gap_connect_cancel() == NRF_SUCCESS)
		{
			(void)cdc_acm_send_format("+disc t=%s reason=cancelled",
						  timestamp_format_us(timestamp_now_us(), time_text));
		}
		else
		{
			/* The stack has already ended the attempt and its event is
			 * queued: a timeout reports +disc itself, and a link is dropped
			 * on arrival. */
			m_drop_on_connect = true;
		}
	}

	return error;
}

bool nus_client_is_connecting(void)
{
	return m_connecting;
}

bool nus_client_is_ready(void)
{
	return m_ready;
}

bool nus_client_is_connected(void)
{
	return m_conn_handle != NUS_CLIENT_NO_CONNECTION;
}

uint32_t nus_client_interval_us(void)
{
	return m_interval_us;
}

uint32_t nus_client_write(const uint8_t * p_data, uint16_t length)
{
	uint32_t error;

	if (!m_ready)
	{
		error = NRF_ERROR_INVALID_STATE;
	}
	else if (length > PROTOCOL_MAX_PAYLOAD)
	{
		error = NRF_ERROR_DATA_SIZE;
	}
	else
	{
		/* The SDK takes the payload as non-const, though it only reads it. */
		error = ble_nus_c_string_send(&m_nus_client, (uint8_t *)p_data, length);
	}

	return error;
}

/**
 * @brief Wait until the reply arrives or @p deadline_us passes, then fill
 *        @p p_response with what came.
 */
static void nus_client_await_reply(uint64_t tx_us, uint64_t deadline_us, nus_response_t * p_response)
{
	while (!m_reply_arrived && (timestamp_now_us() < deadline_us))
	{
		/* Keep USB alive while waiting: a five second timeout must not
		 * cost the host five seconds of advertising events. */
		cdc_acm_process();
	}

	m_awaiting_reply = false;

	p_response->tx_us = tx_us;
	if (m_reply_arrived)
	{
		p_response->replied       = true;
		p_response->rx_us         = m_rx_us;
		p_response->round_trip_us = timestamp_elapsed_us(tx_us, m_rx_us);
		p_response->length        = m_reply_length;
		(void)memcpy(p_response->data, m_reply, m_reply_length);
	}
}

uint32_t nus_client_command(const uint8_t *  p_data,
			    uint16_t         length,
			    uint32_t         timeout_ms,
			    nus_response_t * p_response)
{
	uint32_t error = NRF_ERROR_INVALID_STATE;

	(void)memset(p_response, 0, sizeof(*p_response));

	if (m_ready)
	{
		uint64_t tx_us;

		m_reply_arrived  = false;
		m_reply_length   = 0U;
		m_awaiting_reply = true;

		/* Timestamp as close to the write as possible. The SoftDevice queues
		 * the packet for the next connection event, so this is the instant
		 * the request left the application, not the instant it left the
		 * antenna; the difference is bounded by the connection interval,
		 * which is reported alongside so the figure can be read correctly.
		 * The SDK takes the payload as non-const, though it only reads it. */
		tx_us = timestamp_now_us();
		error = ble_nus_c_string_send(&m_nus_client, (uint8_t *)p_data, length);
		if (error != NRF_SUCCESS)
		{
			m_awaiting_reply = false;
		}
		else
		{
			nus_client_await_reply(tx_us,
					       tx_us + ((uint64_t)timeout_ms * NUS_CLIENT_US_PER_MS),
					       p_response);
		}
	}

	return error;
}

/**
 * @brief Start looking for the UART service on a new link.
 */
static void nus_client_discover(uint64_t when_us)
{
	char		time_text[TIMESTAMP_TEXT_SIZE];
	uint32_t	error;

	/* The link is not usable until discovery has found the UART service and
	 * reported BLE_NUS_C_EVT_DISCOVERY_COMPLETE. Nothing else starts it:
	 * without this a sensor links and never becomes ready (#38). */
	(void)ble_nus_c_handles_assign(&m_nus_client, m_conn_handle, NULL);
	error = ble_db_discovery_start(m_p_db_discovery, m_conn_handle);
	if (error != NRF_SUCCESS)
	{
		/* Say so and drop the link, rather than leave the host waiting for a
		 * ready that cannot come. */
		(void)cdc_acm_send_format("+conn t=%s state=failed error=0x%lx",
					  timestamp_format_us(when_us, time_text),
					  (unsigned long)error);
		(void)sd_ble_gap_disconnect(m_conn_handle,
					    BLE_HCI_REMOTE_USER_TERMINATED_CONNECTION);
	}
}

/**
 * @brief A link is up: report it, then start looking for the UART service.
 */
static void nus_client_on_connected(const ble_gap_evt_t * p_gap, uint64_t when_us)
{
	char		time_text[TIMESTAMP_TEXT_SIZE];
	char		address[18];

	m_connecting  = false;
	m_conn_handle = p_gap->conn_handle;
	m_interval_us = (uint32_t)p_gap->params.connected.conn_params.min_conn_interval *
			NUS_CLIENT_US_PER_INTERVAL_UNIT;
	ble_scanner_format_address(&p_gap->params.connected.peer_addr, address);
	(void)cdc_acm_send_format(
		"+conn t=%s addr=%s state=linked interval_us=%lu",
		timestamp_format_us(when_us, time_text), address,
		(unsigned long)m_interval_us);

	if (m_drop_on_connect)
	{
		/* The host asked to disconnect before this link was reported. */
		m_drop_on_connect = false;
		(void)sd_ble_gap_disconnect(m_conn_handle,
					    BLE_HCI_REMOTE_USER_TERMINATED_CONNECTION);
	}
	else
	{
		nus_client_discover(when_us);
	}
}

void nus_client_on_ble_evt(const ble_evt_t * p_ble_evt)
{
	char		time_text[TIMESTAMP_TEXT_SIZE];
	const ble_gap_evt_t *	p_gap = &p_ble_evt->evt.gap_evt;
	uint64_t		when_us = timestamp_now_us();

	switch (p_ble_evt->header.evt_id)
	{
	case BLE_GAP_EVT_CONNECTED:
		nus_client_on_connected(p_gap, when_us);
		break;

	case BLE_GAP_EVT_DISCONNECTED:
		m_conn_handle = NUS_CLIENT_NO_CONNECTION;
		m_ready       = false;
		m_interval_us = 0U;
		(void)cdc_acm_send_format("+disc t=%s reason=0x%02x",
					  timestamp_format_us(when_us, time_text),
					  (unsigned)p_gap->params.disconnected.reason);
		break;

	case BLE_GAP_EVT_CONN_PARAM_UPDATE:
		m_interval_us =
			(uint32_t)p_gap->params.conn_param_update.conn_params.max_conn_interval *
			NUS_CLIENT_US_PER_INTERVAL_UNIT;
		break;

	case BLE_GAP_EVT_TIMEOUT:
		if (p_gap->params.timeout.src == (uint8_t)BLE_GAP_TIMEOUT_SRC_CONN)
		{
			m_connecting      = false;
			m_drop_on_connect = false;
			(void)cdc_acm_send_format("+disc t=%s reason=timeout",
						  timestamp_format_us(when_us, time_text));
		}
		break;

	default:
		break;
	}

	/* Not ble_nus_c_on_ble_evt(): BLE_NUS_C_DEF registers its own observer,
	 * and a second delivery repeated every NUS event (#38). */
}

void nus_client_on_db_disc_evt(ble_db_discovery_evt_t * p_evt)
{
	ble_nus_c_on_db_disc_evt(&m_nus_client, p_evt);
}
