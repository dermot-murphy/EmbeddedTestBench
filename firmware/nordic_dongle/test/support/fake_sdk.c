/**
 * @file fake_sdk.c
 * @brief The SDK, as far as the firmware can tell, on a host.
 *
 * Each fake does the least that keeps the firmware's own logic honest: the
 * timer counts what a test tells it to, the CDC class records what was written
 * and hands back what a test feeds it, the scan module records its parameters.
 * Where the firmware's behaviour depends on the SDK's semantics rather than its
 * signature - the advertising-data search offset, for instance - the fake
 * implements the semantics rather than returning a constant, because a constant
 * would hide exactly the mistakes worth finding.
 *
 * Traces to: BLE-DD-TEST, SWE4-UT-FWUNIT.
 */

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

#include "app_error.h"
#include "app_usbd.h"
#include "app_usbd_cdc_acm.h"
#include "app_usbd_serial_num.h"
#include "ble_advdata.h"
#include "ble_db_discovery.h"
#include "ble_gap.h"
#include "ble_nus_c.h"
#include "nrf_ble_gatt.h"
#include "nrf_ble_scan.h"
#include "nrf_drv_usbd.h"
#include "nrf_sdh.h"
#include "nrf_soc.h"
#include "nrfx_timer.h"

uint32_t	fake_last_checked_error;
int		fake_critical_nesting;
int		fake_critical_depth_max;
uint32_t	fake_system_resets;

/* ------------------------------------------------------------------ */
/* TIMER                                                               */
/* ------------------------------------------------------------------ */

static nrfx_timer_event_handler_t	m_timer_handler;
static nrfx_timer_config_t		m_timer_config;
static uint32_t				m_timer_counter;
static uint32_t				m_timer_compare_value;
static uint32_t				m_timer_compare_shorts;
static uint32_t				m_timer_init_result;
static bool				m_timer_enabled;

uint32_t nrfx_timer_init(const nrfx_timer_t *		p_instance,
			 const nrfx_timer_config_t *	p_config,
			 nrfx_timer_event_handler_t	handler)
{
	(void)p_instance;
	if (m_timer_init_result != NRF_SUCCESS)
	{
		return m_timer_init_result;
	}
	m_timer_config  = *p_config;
	m_timer_handler = handler;
	return NRF_SUCCESS;
}

void nrfx_timer_enable(const nrfx_timer_t * p_instance)
{
	(void)p_instance;
	m_timer_enabled = true;
}

void nrfx_timer_extended_compare(const nrfx_timer_t *		p_instance,
				 nrf_timer_cc_channel_t		cc_channel,
				 uint32_t			cc_value,
				 uint32_t			shorts_mask,
				 bool				enable_interrupt)
{
	(void)p_instance;
	(void)cc_channel;
	(void)enable_interrupt;
	m_timer_compare_value  = cc_value;
	m_timer_compare_shorts = shorts_mask;
}

uint32_t nrfx_timer_capture(const nrfx_timer_t * p_instance, nrf_timer_cc_channel_t cc_channel)
{
	(void)p_instance;
	(void)cc_channel;
	return m_timer_counter;
}

void fake_timer_set_counter(uint32_t ticks)
{
	m_timer_counter = ticks;
}

void fake_timer_fire_compare(void)
{
	if (m_timer_handler != NULL)
	{
		m_timer_handler(NRF_TIMER_EVENT_COMPARE0, NULL);
	}
}

const nrfx_timer_config_t * fake_timer_config(void)		{ return &m_timer_config; }
bool     fake_timer_is_enabled(void)				{ return m_timer_enabled; }
uint32_t fake_timer_compare_value(void)				{ return m_timer_compare_value; }
uint32_t fake_timer_compare_shorts(void)			{ return m_timer_compare_shorts; }
void     fake_timer_set_init_result(uint32_t result)		{ m_timer_init_result = result; }

void fake_timer_reset(void)
{
	m_timer_handler        = NULL;
	m_timer_counter        = 0U;
	m_timer_compare_value  = 0U;
	m_timer_compare_shorts = 0U;
	m_timer_init_result    = NRF_SUCCESS;
	m_timer_enabled        = false;
	(void)memset(&m_timer_config, 0, sizeof(m_timer_config));
}

/* ------------------------------------------------------------------ */
/* USB CDC ACM                                                         */
/* ------------------------------------------------------------------ */

#define FAKE_CDC_CAPACITY	8192U

app_usbd_cdc_acm_user_ev_handler_t	fake_cdc_handler;

static char		m_cdc_written[FAKE_CDC_CAPACITY];
static uint32_t		m_cdc_written_length;
static uint32_t		m_cdc_write_count;
static uint32_t		m_cdc_write_result;
static bool		m_cdc_write_pending;
static char *		m_cdc_rx_buffer;
static size_t		m_cdc_rx_length;
static app_usbd_class_inst_t	m_cdc_instance;
static uint32_t		m_usbd_queue_depth;
static uint32_t		m_usbd_queue_calls;
static bool		m_usbd_enabled;

uint32_t app_usbd_cdc_acm_write(app_usbd_cdc_acm_t const * p_cdc_acm, const void * p_buf, size_t length)
{
	(void)p_cdc_acm;
	if (m_cdc_write_result != NRF_SUCCESS)
	{
		return m_cdc_write_result;
	}
	if ((m_cdc_written_length + length) < FAKE_CDC_CAPACITY)
	{
		(void)memcpy(&m_cdc_written[m_cdc_written_length], p_buf, length);
		m_cdc_written_length += (uint32_t)length;
		m_cdc_written[m_cdc_written_length] = '\0';
	}
	m_cdc_write_count++;
	m_cdc_write_pending = true;
	return NRF_SUCCESS;
}

uint32_t app_usbd_cdc_acm_read(app_usbd_cdc_acm_t const * p_cdc_acm, void * p_buf, size_t length)
{
	(void)p_cdc_acm;
	/* The real driver completes a read when a byte arrives; here the test
	 * supplies bytes, so a read only registers where to put the next one. */
	m_cdc_rx_buffer = (char *)p_buf;
	m_cdc_rx_length = length;
	return NRF_ERROR_IO_PENDING;
}

app_usbd_class_inst_t const * app_usbd_cdc_acm_class_inst_get(app_usbd_cdc_acm_t const * p_cdc_acm)
{
	(void)p_cdc_acm;
	return &m_cdc_instance;
}

const char * fake_cdc_written(void)		{ return m_cdc_written; }
uint32_t     fake_cdc_written_length(void)	{ return m_cdc_written_length; }
uint32_t     fake_cdc_write_count(void)		{ return m_cdc_write_count; }
void         fake_cdc_set_write_result(uint32_t result)	{ m_cdc_write_result = result; }

void fake_cdc_receive_byte(char byte)
{
	if ((m_cdc_rx_buffer == NULL) || (m_cdc_rx_length == 0U) || (fake_cdc_handler == NULL))
	{
		return;
	}
	m_cdc_rx_buffer[0] = byte;
	fake_cdc_handler(&m_cdc_instance, APP_USBD_CDC_ACM_USER_EVT_RX_DONE);
}

void fake_cdc_receive_text(const char * text)
{
	while (*text != '\0')
	{
		fake_cdc_receive_byte(*text);
		text++;
	}
}

void fake_cdc_complete_write(void)
{
	if (m_cdc_write_pending && (fake_cdc_handler != NULL))
	{
		m_cdc_write_pending = false;
		fake_cdc_handler(&m_cdc_instance, APP_USBD_CDC_ACM_USER_EVT_TX_DONE);
	}
}

void fake_cdc_open_port(void)
{
	if (fake_cdc_handler != NULL)
	{
		fake_cdc_handler(&m_cdc_instance, APP_USBD_CDC_ACM_USER_EVT_PORT_OPEN);
	}
}

void fake_cdc_close_port(void)
{
	if (fake_cdc_handler != NULL)
	{
		fake_cdc_handler(&m_cdc_instance, APP_USBD_CDC_ACM_USER_EVT_PORT_CLOSE);
	}
}

void fake_cdc_reset(void)
{
	m_cdc_written[0]     = '\0';
	m_cdc_written_length = 0U;
	m_cdc_write_count    = 0U;
	m_cdc_write_result   = NRF_SUCCESS;
	m_cdc_write_pending  = false;
	m_cdc_rx_buffer      = NULL;
	m_cdc_rx_length      = 0U;
}

/* --- the USB device stack ----------------------------------------- */

uint32_t app_usbd_init(const app_usbd_config_t * p_config)		{ (void)p_config; return NRF_SUCCESS; }
uint32_t app_usbd_class_append(app_usbd_class_inst_t const * p_inst)	{ (void)p_inst; return NRF_SUCCESS; }
uint32_t app_usbd_power_events_enable(void)				{ return NRF_SUCCESS; }
void     app_usbd_enable(void)						{ m_usbd_enabled = true; }
void     app_usbd_disable(void)						{ m_usbd_enabled = false; }
void     app_usbd_start(void)						{ }
void     app_usbd_stop(void)						{ }
void     app_usbd_serial_num_generate(void)				{ }
bool     nrf_drv_usbd_is_enabled(void)					{ return m_usbd_enabled; }
void     fake_usbd_set_enabled(bool enabled)				{ m_usbd_enabled = enabled; }

bool app_usbd_event_queue_process(void)
{
	m_usbd_queue_calls++;
	if (m_usbd_queue_depth > 0U)
	{
		m_usbd_queue_depth--;
		return true;
	}
	return false;
}

uint32_t fake_usbd_queue_process_calls(void)		{ return m_usbd_queue_calls; }
void     fake_usbd_set_queue_depth(uint32_t events)	{ m_usbd_queue_depth = events; }

void fake_usbd_reset(void)
{
	m_usbd_queue_depth = 0U;
	m_usbd_queue_calls = 0U;
	m_usbd_enabled     = false;
}

/* ------------------------------------------------------------------ */
/* Advertising data                                                    */
/* ------------------------------------------------------------------ */

uint16_t ble_advdata_search(const uint8_t *	p_encoded_data,
			    uint16_t		data_len,
			    uint16_t *		p_offset,
			    uint8_t		ad_type)
{
	uint16_t index = (p_offset != NULL) ? *p_offset : 0U;

	/* Advertising data is a sequence of (length, type, payload) records. The
	 * SDK returns the length of the payload and sets the offset to its first
	 * byte - not to the length byte, which is the mistake worth catching. */
	while ((index + 1U) < data_len)
	{
		uint8_t field_length = p_encoded_data[index];
		uint8_t field_type;

		if (field_length == 0U)
		{
			break;
		}
		field_type = p_encoded_data[index + 1U];
		if (field_type == ad_type)
		{
			if (p_offset != NULL)
			{
				*p_offset = (uint16_t)(index + 2U);
			}
			return (uint16_t)(field_length - 1U);
		}
		index = (uint16_t)(index + field_length + 1U);
	}

	return 0U;
}

/* ------------------------------------------------------------------ */
/* Scanning                                                            */
/* ------------------------------------------------------------------ */

static nrf_ble_scan_evt_handler_t	m_scan_handler;
static ble_gap_scan_params_t		m_scan_params;
static uint32_t				m_scan_start_count;
static uint32_t				m_scan_stop_count;
static uint32_t				m_scan_start_result;

uint32_t nrf_ble_scan_init(nrf_ble_scan_t *		p_scan_ctx,
			   nrf_ble_scan_init_t const *	p_init,
			   nrf_ble_scan_evt_handler_t	evt_handler)
{
	(void)p_scan_ctx;
	if ((p_init != NULL) && (p_init->p_scan_param != NULL))
	{
		m_scan_params = *p_init->p_scan_param;
	}
	m_scan_handler = evt_handler;
	return NRF_SUCCESS;
}

uint32_t nrf_ble_scan_params_set(nrf_ble_scan_t * p_scan_ctx, ble_gap_scan_params_t const * p_scan_param)
{
	(void)p_scan_ctx;
	m_scan_params = *p_scan_param;
	return NRF_SUCCESS;
}

uint32_t nrf_ble_scan_start(nrf_ble_scan_t * p_scan_ctx)
{
	(void)p_scan_ctx;
	if (m_scan_start_result != NRF_SUCCESS)
	{
		return m_scan_start_result;
	}
	m_scan_start_count++;
	return NRF_SUCCESS;
}

void nrf_ble_scan_stop(void)
{
	m_scan_stop_count++;
}

const ble_gap_scan_params_t * fake_scan_params(void)	{ return &m_scan_params; }
uint32_t fake_scan_start_count(void)			{ return m_scan_start_count; }
uint32_t fake_scan_stop_count(void)			{ return m_scan_stop_count; }
void     fake_scan_set_start_result(uint32_t result)	{ m_scan_start_result = result; }

void fake_scan_fire(nrf_ble_scan_evt_t event)
{
	scan_evt_t evt;

	(void)memset(&evt, 0, sizeof(evt));
	evt.scan_evt_id = event;
	if (m_scan_handler != NULL)
	{
		m_scan_handler(&evt);
	}
}

void fake_scan_reset(void)
{
	m_scan_start_count  = 0U;
	m_scan_stop_count   = 0U;
	m_scan_start_result = NRF_SUCCESS;
	(void)memset(&m_scan_params, 0, sizeof(m_scan_params));
}

/* ------------------------------------------------------------------ */
/* SoftDevice, GATT, discovery, reset                                  */
/* ------------------------------------------------------------------ */

static ble_gap_addr_t	m_connect_address;
static uint32_t		m_connect_count;
static uint32_t		m_connect_result;
static uint32_t		m_disconnect_count;
static uint16_t		m_disconnect_handle;

uint32_t sd_ble_gap_connect(const ble_gap_addr_t *	p_peer_addr,
			    const ble_gap_scan_params_t *	p_scan_params,
			    const ble_gap_conn_params_t *	p_conn_params,
			    uint8_t				conn_cfg_tag)
{
	(void)p_scan_params;
	(void)p_conn_params;
	(void)conn_cfg_tag;
	if (m_connect_result != NRF_SUCCESS)
	{
		return m_connect_result;
	}
	m_connect_address = *p_peer_addr;
	m_connect_count++;
	return NRF_SUCCESS;
}

uint32_t sd_ble_gap_disconnect(uint16_t conn_handle, uint8_t hci_status_code)
{
	(void)hci_status_code;
	m_disconnect_handle = conn_handle;
	m_disconnect_count++;
	return NRF_SUCCESS;
}

const ble_gap_addr_t * fake_gap_connect_address(void)	{ return &m_connect_address; }
uint32_t fake_gap_connect_count(void)			{ return m_connect_count; }
uint32_t fake_gap_disconnect_count(void)		{ return m_disconnect_count; }
void     fake_gap_set_connect_result(uint32_t result)	{ m_connect_result = result; }

void fake_gap_reset(void)
{
	m_connect_count    = 0U;
	m_disconnect_count = 0U;
	m_connect_result   = NRF_SUCCESS;
	(void)memset(&m_connect_address, 0, sizeof(m_connect_address));
}

uint32_t nrf_sdh_enable_request(void)	{ return NRF_SUCCESS; }
bool     nrf_sdh_is_enabled(void)	{ return true; }

uint32_t nrf_ble_gatt_init(nrf_ble_gatt_t * p_gatt, void * evt_handler)
{
	(void)p_gatt;
	(void)evt_handler;
	return NRF_SUCCESS;
}

uint32_t nrf_ble_gatt_att_mtu_central_set(nrf_ble_gatt_t * p_gatt, uint16_t desired_mtu)
{
	(void)p_gatt;
	(void)desired_mtu;
	return NRF_SUCCESS;
}

uint32_t ble_db_discovery_init(const ble_db_discovery_init_t * p_init)
{
	(void)p_init;
	return NRF_SUCCESS;
}

void ble_db_discovery_on_ble_evt(ble_evt_t const * p_ble_evt, void * p_context)
{
	(void)p_ble_evt;
	(void)p_context;
}

void NVIC_SystemReset(void)
{
	fake_system_resets++;
}

/* ------------------------------------------------------------------ */
/* UART service client                                                 */
/* ------------------------------------------------------------------ */

static ble_nus_c_evt_handler_t	m_nus_handler;
static ble_nus_c_t *		mp_nus_instance;
static uint8_t			m_nus_sent[256];
static uint16_t			m_nus_sent_length;
static uint32_t			m_nus_send_count;
static uint32_t			m_nus_send_result;
static bool			m_nus_notifications;

uint32_t ble_nus_c_init(ble_nus_c_t * p_nus_c, ble_nus_c_init_t * p_init)
{
	mp_nus_instance     = p_nus_c;
	m_nus_handler       = p_init->evt_handler;
	p_nus_c->evt_handler = p_init->evt_handler;
	return NRF_SUCCESS;
}

uint32_t ble_nus_c_handles_assign(ble_nus_c_t * p_nus_c, uint16_t conn_handle,
				  const ble_nus_c_handles_t * p_peer_handles)
{
	p_nus_c->conn_handle = conn_handle;
	if (p_peer_handles != NULL)
	{
		p_nus_c->handles = *p_peer_handles;
	}
	return NRF_SUCCESS;
}

uint32_t ble_nus_c_tx_notif_enable(ble_nus_c_t * p_nus_c)
{
	(void)p_nus_c;
	m_nus_notifications = true;
	return NRF_SUCCESS;
}

uint32_t ble_nus_c_string_send(ble_nus_c_t * p_nus_c, uint8_t * p_string, uint16_t length)
{
	(void)p_nus_c;
	if (m_nus_send_result != NRF_SUCCESS)
	{
		return m_nus_send_result;
	}
	m_nus_sent_length = (length < sizeof(m_nus_sent)) ? length : (uint16_t)sizeof(m_nus_sent);
	(void)memcpy(m_nus_sent, p_string, m_nus_sent_length);
	m_nus_send_count++;
	return NRF_SUCCESS;
}

void ble_nus_c_on_ble_evt(ble_evt_t const * p_ble_evt, void * p_context)
{
	(void)p_ble_evt;
	(void)p_context;
}

void ble_nus_c_on_db_disc_evt(ble_nus_c_t * p_nus_c, void * p_evt)
{
	(void)p_nus_c;
	(void)p_evt;
}

const uint8_t * fake_nus_sent(void)		{ return m_nus_sent; }
uint16_t        fake_nus_sent_length(void)	{ return m_nus_sent_length; }
uint32_t        fake_nus_send_count(void)	{ return m_nus_send_count; }
void            fake_nus_set_send_result(uint32_t result)	{ m_nus_send_result = result; }
bool            fake_nus_notifications_enabled(void)		{ return m_nus_notifications; }

void fake_nus_fire(ble_nus_c_evt_type_t type, const uint8_t * data, uint16_t length)
{
	ble_nus_c_evt_t evt;

	(void)memset(&evt, 0, sizeof(evt));
	evt.evt_type    = type;
	evt.conn_handle = 0U;
	evt.p_data      = data;
	evt.data_len    = length;
	if (m_nus_handler != NULL)
	{
		m_nus_handler(mp_nus_instance, &evt);
	}
}

void fake_nus_reset(void)
{
	m_nus_sent_length   = 0U;
	m_nus_send_count    = 0U;
	m_nus_send_result   = NRF_SUCCESS;
	m_nus_notifications = false;
}
