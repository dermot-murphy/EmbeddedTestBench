/**
 * @file dfu_client.c
 * @brief A GATT client for Nordic's Secure DFU service, for updating a sensor.
 *
 * Traces to: BLE-FR-121, BLE-DD-DFU.
 */

#include "dfu_client.h"

#include <string.h>

#include "app_error.h"
#include "app_util_platform.h"
#include "ble_db_discovery.h"
#include "nrf_ble_gq.h"

#include "cdc_acm.h"
#include "timestamp.h"

/** The DFU service, a Bluetooth SIG UUID assigned to Nordic. */
#define DFU_CLIENT_SERVICE_UUID		0xFE59U

/** The characteristics, in Nordic's base 8EC9xxxx-F315-4F60-9FB8-838830DAEA50. */
#define DFU_CLIENT_CONTROL_UUID		0x0001U
#define DFU_CLIENT_PACKET_UUID		0x0002U

/** Writing this to a CCCD turns notifications on. */
#define DFU_CLIENT_CCCD_NOTIFY		0x0001U

/** Bytes in a CCCD value. */
#define DFU_CLIENT_CCCD_LENGTH		2U

/** Microseconds in a millisecond. */
#define DFU_CLIENT_US_PER_MS		1000U

/** An ATT write's opcode and handle: what the MTU carries besides the value. */
#define DFU_CLIENT_ATT_OVERHEAD		3U

/** The connection interval a DFU link asks for: 7.5 ms, in 1.25 ms units. At
 *  the 30 ms a UART link uses, a 298 KB application took 191 s to send to
 *  5C1712, past the 180 s a Kepler specification allows (#244). */
#define DFU_CLIENT_INTERVAL_UNITS	6U

/** Supervision timeout of a DFU link: 4 s, in 10 ms units, as a UART link's. */
#define DFU_CLIENT_SUPERVISION_UNITS	400U

/** Control Point opcodes the client watches: creating an object restarts the
 *  bootloader's packet count, and this one sets how many packets it receipts. */
#define DFU_CLIENT_OP_CREATE		0x01U
#define DFU_CLIENT_OP_PRN_SET		0x02U
/** Bytes of a request that sets the receipt interval: opcode and 16 bits. */
#define DFU_CLIENT_PRN_SET_LENGTH	3U
/** Bit position of a 16-bit value's upper byte. */
#define DFU_CLIENT_UPPER_BYTE_SHIFT	8U
/** A response: 0x60, the request's opcode, then the result, 0x01 for success. */
#define DFU_CLIENT_RESPONSE_HEADER	3U
#define DFU_CLIENT_RESULT_INDEX		2U
#define DFU_CLIENT_RESULT_SUCCESS	0x01U

/** The vendor base UUID, least significant byte first. */
static const ble_uuid128_t	m_dfu_client_base =
{
	{
		0x50U, 0xEAU, 0xDAU, 0x30U, 0x88U, 0x83U, 0xB8U, 0x9FU,
		0x60U, 0x4FU, 0x15U, 0xF3U, 0x00U, 0x00U, 0xC9U, 0x8EU
	}
};

static nrf_ble_gq_t *		m_dfu_client_queue;
static nrf_ble_gatt_t *		m_dfu_client_gatt;
static uint8_t			m_dfu_client_uuid_type;
static uint16_t			m_dfu_client_conn = BLE_CONN_HANDLE_INVALID;
static uint16_t			m_dfu_client_control;
static uint16_t			m_dfu_client_cccd;
static uint16_t			m_dfu_client_packet_handle;
static bool			m_dfu_client_ready;

static volatile bool		m_dfu_client_waiting;
static volatile bool		m_dfu_client_answered;
static uint16_t			m_dfu_client_answer_len;
static uint8_t			m_dfu_client_answer[DFU_CLIENT_MAX_RESPONSE];
static uint8_t			m_dfu_client_cccd_value[DFU_CLIENT_CCCD_LENGTH];

/* Flow control. At a 7.5 ms interval writes without response outran the
 * bootloader, which keeps 17 packet buffers, and 3348 bytes of a 4096-byte
 * object arrived on 5C1712 (#244). With a receipt interval set, the client
 * waits for the receipt after every m_dfu_client_prn packets. */
static uint16_t			m_dfu_client_prn;
static uint16_t			m_dfu_client_unreceipted;

/**
 * @brief Report the client's state to the host as a @c +dfu event.
 */
static void dfu_client_report(const char * p_state, uint32_t nrf_error)
{
	char time_text[TIMESTAMP_TEXT_SIZE];

	(void)cdc_acm_send_format("+dfu t=%s state=%s error=0x%lx",
				  timestamp_format_us(timestamp_now_us(), time_text),
				  p_state, (unsigned long)nrf_error);
}

/**
 * @brief A queued request that failed is reported, not lost.
 */
static void dfu_client_queue_error(uint32_t nrf_error, void * p_context, uint16_t conn_handle)
{
	UNUSED_PARAMETER(p_context);
	UNUSED_PARAMETER(conn_handle);
	dfu_client_report("error", nrf_error);
}

/**
 * @brief Queue one write on the DFU link.
 */
static uint32_t dfu_client_write(uint16_t handle, uint8_t operation,
				 const uint8_t * p_data, uint16_t length)
{
	nrf_ble_gq_req_t request;

	(void)memset(&request, 0, sizeof(request));
	request.type                        = NRF_BLE_GQ_REQ_GATTC_WRITE;
	request.error_handler.cb            = dfu_client_queue_error;
	request.params.gattc_write.write_op = operation;
	request.params.gattc_write.handle   = handle;
	request.params.gattc_write.len      = length;
	request.params.gattc_write.p_value  = p_data;

	return nrf_ble_gq_item_add(m_dfu_client_queue, &request, m_dfu_client_conn);
}

/**
 * @brief Forget the link: its handles mean nothing on the next one.
 */
static void dfu_client_forget(void)
{
	m_dfu_client_conn           = BLE_CONN_HANDLE_INVALID;
	m_dfu_client_control        = 0U;
	m_dfu_client_cccd           = 0U;
	m_dfu_client_packet_handle  = 0U;
	m_dfu_client_ready          = false;
	m_dfu_client_waiting        = false;
	m_dfu_client_prn            = 0U;
	m_dfu_client_unreceipted    = 0U;
}

uint32_t dfu_client_init(nrf_ble_gq_t * p_gatt_queue, nrf_ble_gatt_t * p_gatt)
{
	ble_uuid_t	service;
	uint32_t	error;

	m_dfu_client_queue = p_gatt_queue;
	m_dfu_client_gatt  = p_gatt;
	dfu_client_forget();

	error = sd_ble_uuid_vs_add(&m_dfu_client_base, &m_dfu_client_uuid_type);
	if (error != NRF_SUCCESS)
	{
		return error;
	}

	service.uuid = DFU_CLIENT_SERVICE_UUID;
	service.type = BLE_UUID_TYPE_BLE;
	return ble_db_discovery_evt_register(&service);
}

bool dfu_client_is_ready(void)
{
	return m_dfu_client_ready;
}

/**
 * @brief Take the Control Point and Packet handles from a discovered service.
 */
static void dfu_client_take_handles(const ble_gatt_db_srv_t * p_db)
{
	uint32_t index;

	for (index = 0U; index < p_db->char_count; index++)
	{
		const ble_gatt_db_char_t * p_char = &p_db->charateristics[index];

		if (p_char->characteristic.uuid.type != m_dfu_client_uuid_type)
		{
			continue;
		}
		if (p_char->characteristic.uuid.uuid == DFU_CLIENT_CONTROL_UUID)
		{
			m_dfu_client_control = p_char->characteristic.handle_value;
			m_dfu_client_cccd    = p_char->cccd_handle;
		}
		else if (p_char->characteristic.uuid.uuid == DFU_CLIENT_PACKET_UUID)
		{
			m_dfu_client_packet_handle = p_char->characteristic.handle_value;
		}
		else
		{
			/* Buttonless and other characteristics are not used. */
		}
	}
}

/**
 * @brief Ask for a short connection interval on the DFU link.
 *
 * Only a DFU link is made faster: a UART link's interval is the floor under
 * every latency measured on it, and stays as it was. A target that refuses
 * still carries the transfer, more slowly.
 */
static void dfu_client_speed_up(void)
{
	ble_gap_conn_params_t params;

	(void)memset(&params, 0, sizeof(params));
	params.min_conn_interval = DFU_CLIENT_INTERVAL_UNITS;
	params.max_conn_interval = DFU_CLIENT_INTERVAL_UNITS;
	params.slave_latency     = 0U;
	params.conn_sup_timeout  = DFU_CLIENT_SUPERVISION_UNITS;
	(void)sd_ble_gap_conn_param_update(m_dfu_client_conn, &params);
}

void dfu_client_on_db_disc_evt(ble_db_discovery_evt_t * p_evt)
{
	uint32_t error;

	if ((p_evt->evt_type != BLE_DB_DISCOVERY_COMPLETE) ||
	    (p_evt->params.discovered_db.srv_uuid.uuid != DFU_CLIENT_SERVICE_UUID) ||
	    (p_evt->params.discovered_db.srv_uuid.type != BLE_UUID_TYPE_BLE))
	{
		return;
	}

	m_dfu_client_conn = p_evt->conn_handle;
	dfu_client_take_handles(&p_evt->params.discovered_db);
	if ((m_dfu_client_control == 0U) || (m_dfu_client_cccd == 0U) ||
	    (m_dfu_client_packet_handle == 0U))
	{
		dfu_client_report("incomplete", NRF_SUCCESS);
		return;
	}

	/* The queue keeps requests in order, so a Control Point write queued after
	 * this one cannot overtake it. */
	m_dfu_client_cccd_value[0] = (uint8_t)DFU_CLIENT_CCCD_NOTIFY;
	m_dfu_client_cccd_value[1] = 0U;
	error = dfu_client_write(m_dfu_client_cccd, BLE_GATT_OP_WRITE_REQ,
				 m_dfu_client_cccd_value, DFU_CLIENT_CCCD_LENGTH);
	if (error != NRF_SUCCESS)
	{
		dfu_client_report("failed", error);
		return;
	}

	dfu_client_speed_up();
	m_dfu_client_ready = true;
	dfu_client_report("ready", NRF_SUCCESS);
}

/**
 * @brief Keep a Control Point notification as the answer being waited for.
 */
static void dfu_client_on_hvx(const ble_gattc_evt_t * p_gattc)
{
	const ble_gattc_evt_hvx_t *	p_hvx = &p_gattc->params.hvx;
	uint16_t			kept  = p_hvx->len;

	/* Kept even when nothing waits for it: a receipt can arrive before the
	 * packet write that waits for it has looked. A request clears it. */
	if ((p_gattc->conn_handle != m_dfu_client_conn) ||
	    (p_hvx->handle != m_dfu_client_control) || m_dfu_client_answered)
	{
		return;
	}
	if (kept > DFU_CLIENT_MAX_RESPONSE)
	{
		kept = DFU_CLIENT_MAX_RESPONSE;
	}
	(void)memcpy(m_dfu_client_answer, p_hvx->data, kept);
	m_dfu_client_answer_len = kept;
	m_dfu_client_answered   = true;
}

void dfu_client_on_ble_evt(const ble_evt_t * p_ble_evt)
{
	if ((p_ble_evt->header.evt_id == BLE_GAP_EVT_DISCONNECTED) &&
	    (p_ble_evt->evt.gap_evt.conn_handle == m_dfu_client_conn))
	{
		dfu_client_forget();
	}
	else if (p_ble_evt->header.evt_id == BLE_GATTC_EVT_HVX)
	{
		dfu_client_on_hvx(&p_ble_evt->evt.gattc_evt);
	}
	else
	{
		/* Nothing else concerns the DFU client. */
	}
}

/**
 * @brief Note what a request the bootloader accepted means for flow control.
 */
static void dfu_client_track(const uint8_t * p_data, uint16_t length)
{
	if ((m_dfu_client_answer_len < DFU_CLIENT_RESPONSE_HEADER) ||
	    (m_dfu_client_answer[DFU_CLIENT_RESULT_INDEX] != DFU_CLIENT_RESULT_SUCCESS))
	{
		return;
	}
	if ((p_data[0] == DFU_CLIENT_OP_PRN_SET) && (length >= DFU_CLIENT_PRN_SET_LENGTH))
	{
		m_dfu_client_prn = (uint16_t)((uint16_t)p_data[1] |
					      (uint16_t)((uint16_t)p_data[2] << DFU_CLIENT_UPPER_BYTE_SHIFT));
		m_dfu_client_unreceipted = 0U;
	}
	else if (p_data[0] == DFU_CLIENT_OP_CREATE)
	{
		m_dfu_client_unreceipted = 0U;
	}
	else
	{
		/* Nothing else changes the count. */
	}
}

/**
 * @brief Wait for, and drop, the receipt the bootloader owes for the last packets.
 */
static uint32_t dfu_client_await_receipt(uint64_t deadline_us)
{
	m_dfu_client_waiting = true;
	while (!m_dfu_client_answered && (timestamp_now_us() < deadline_us))
	{
		cdc_acm_process();
	}
	m_dfu_client_waiting = false;
	if (!m_dfu_client_answered)
	{
		return NRF_ERROR_TIMEOUT;
	}
	m_dfu_client_answered    = false;
	m_dfu_client_unreceipted = 0U;
	return NRF_SUCCESS;
}

uint32_t dfu_client_control(const uint8_t * p_data, uint16_t length, uint32_t timeout_ms,
			    uint8_t * p_response, uint16_t * p_response_len)
{
	uint64_t	deadline_us;
	uint32_t	error;

	*p_response_len = 0U;
	if (!m_dfu_client_ready)
	{
		return NRF_ERROR_INVALID_STATE;
	}
	if (length > DFU_CLIENT_MAX_WRITE)
	{
		return NRF_ERROR_DATA_SIZE;
	}

	m_dfu_client_answered = false;
	m_dfu_client_waiting  = true;
	error = dfu_client_write(m_dfu_client_control, BLE_GATT_OP_WRITE_REQ, p_data, length);
	if (error != NRF_SUCCESS)
	{
		m_dfu_client_waiting = false;
		return error;
	}

	deadline_us = timestamp_now_us() + ((uint64_t)timeout_ms * DFU_CLIENT_US_PER_MS);
	while (!m_dfu_client_answered && (timestamp_now_us() < deadline_us))
	{
		/* Keep USB alive while the bootloader works: validating an init
		 * packet or executing an image takes seconds. */
		cdc_acm_process();
	}
	m_dfu_client_waiting = false;

	if (m_dfu_client_answered)
	{
		(void)memcpy(p_response, m_dfu_client_answer, m_dfu_client_answer_len);
		*p_response_len = m_dfu_client_answer_len;
		dfu_client_track(p_data, length);
		m_dfu_client_answered = false;
	}
	return NRF_SUCCESS;
}

/**
 * @brief Give one Packet write to the SoftDevice, waiting for a transmit
 *        buffer until @p deadline_us.
 *
 * Not through the GATT queue: it passes NRF_ERROR_RESOURCES for a write
 * without response to its error handler rather than retrying, and on
 * 5C1712's bootloader 704 bytes of a 4096-byte object arrived (#244). The
 * SoftDevice copies the value and sends in order, so a Control Point request
 * the host sends after these follows them.
 */
static uint32_t dfu_client_packet_piece(const uint8_t * p_data, uint16_t length,
					uint64_t deadline_us)
{
	ble_gattc_write_params_t	params;
	uint32_t			error;

	(void)memset(&params, 0, sizeof(params));
	params.write_op = BLE_GATT_OP_WRITE_CMD;
	params.handle   = m_dfu_client_packet_handle;
	params.len      = length;
	params.p_value  = p_data;
	do
	{
		error = sd_ble_gattc_write(m_dfu_client_conn, &params);
		if (error != NRF_ERROR_RESOURCES)
		{
			break;
		}
		cdc_acm_process();
	} while (timestamp_now_us() < deadline_us);

	return error;
}

uint32_t dfu_client_packet(const uint8_t * p_data, uint16_t length, uint32_t timeout_ms)
{
	uint64_t	deadline_us;
	uint32_t	error = NRF_SUCCESS;
	uint16_t	piece;
	uint16_t	offset;

	if (!m_dfu_client_ready)
	{
		return NRF_ERROR_INVALID_STATE;
	}
	if (length > DFU_CLIENT_MAX_WRITE)
	{
		return NRF_ERROR_DATA_SIZE;
	}

	piece = (uint16_t)(nrf_ble_gatt_eff_mtu_get(m_dfu_client_gatt, m_dfu_client_conn) -
			   DFU_CLIENT_ATT_OVERHEAD);
	deadline_us = timestamp_now_us() + ((uint64_t)timeout_ms * DFU_CLIENT_US_PER_MS);
	for (offset = 0U; (offset < length) && (error == NRF_SUCCESS); offset += piece)
	{
		uint16_t size = (uint16_t)(length - offset);

		if (size > piece)
		{
			size = piece;
		}
		error = dfu_client_packet_piece(&p_data[offset], size, deadline_us);
		if (error != NRF_SUCCESS)
		{
			break;
		}
		m_dfu_client_unreceipted++;
		if ((m_dfu_client_prn != 0U) && (m_dfu_client_unreceipted >= m_dfu_client_prn))
		{
			error = dfu_client_await_receipt(deadline_us);
		}
	}

	return error;
}
