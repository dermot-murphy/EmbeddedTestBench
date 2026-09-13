/**
 * @file cdc_acm.c
 * @brief USB CDC ACM line transport.
 *
 * Traces to: BLE-FR-003, BLE-FR-004, BLE-DD-CDC.
 */

#include "cdc_acm.h"

#include <stdarg.h>
#include <stdio.h>
#include <string.h>

#include "app_error.h"
#include "app_usbd.h"
#include "app_usbd_cdc_acm.h"
#include "app_usbd_core.h"
#include "app_usbd_serial_num.h"
#include "app_usbd_string_desc.h"
#include "app_util_platform.h"
#include "nrf_drv_usbd.h"

#define CDC_ACM_COMM_INTERFACE		0
#define CDC_ACM_COMM_EPIN		NRF_DRV_USBD_EPIN2
#define CDC_ACM_DATA_INTERFACE		1
#define CDC_ACM_DATA_EPIN		NRF_DRV_USBD_EPIN1
#define CDC_ACM_DATA_EPOUT		NRF_DRV_USBD_EPOUT1

/** Bytes read from the endpoint at a time. One is deliberate: the CDC driver
 *  reports each byte as it arrives, which is what lets a line be assembled
 *  without waiting for a buffer to fill or a timeout to expire. */
#define CDC_RX_CHUNK			1U

static void cdc_event_handler(app_usbd_class_inst_t const * p_inst,
			      app_usbd_cdc_acm_user_event_t     event);

APP_USBD_CDC_ACM_GLOBAL_DEF(m_app_cdc_acm,
			    cdc_event_handler,
			    CDC_ACM_COMM_INTERFACE,
			    CDC_ACM_DATA_INTERFACE,
			    CDC_ACM_COMM_EPIN,
			    CDC_ACM_DATA_EPIN,
			    CDC_ACM_DATA_EPOUT,
			    APP_USBD_CDC_COMM_PROTOCOL_AT_V250);

/** One queued output line. */
typedef struct
{
	char		text[PROTO_MAX_EVENT];
	uint16_t	length;
} cdc_line_t;

static cdc_line_t	m_tx_queue[CDC_TX_QUEUE_LINES];
static volatile uint32_t m_tx_head;		/**< next slot to fill */
static volatile uint32_t m_tx_tail;		/**< next slot to send */
static volatile bool	m_tx_busy;		/**< an endpoint write is in flight */
static volatile uint32_t m_dropped;

static char		m_rx_byte[CDC_RX_CHUNK];
static char		m_rx_line[PROTO_MAX_LINE];
static uint32_t		m_rx_length;
static volatile bool	m_rx_ready;		/**< a complete line is waiting */
static char		m_rx_complete[PROTO_MAX_LINE];

static volatile bool	m_port_open;

/**
 * @brief Start the next queued write, if any and if the endpoint is free.
 */
static void tx_pump(void)
{
	ret_code_t	error;
	uint32_t	tail;

	CRITICAL_REGION_ENTER();
	if (m_tx_busy || (m_tx_head == m_tx_tail) || !m_port_open)
	{
		CRITICAL_REGION_EXIT();
		return;
	}
	tail      = m_tx_tail;
	m_tx_busy = true;
	CRITICAL_REGION_EXIT();

	error = app_usbd_cdc_acm_write(&m_app_cdc_acm,
				       m_tx_queue[tail].text,
				       m_tx_queue[tail].length);
	if (error != NRF_SUCCESS)
	{
		/* The endpoint refused the write: release the slot and count the
		 * line as dropped, so the host's total still reconciles. */
		CRITICAL_REGION_ENTER();
		m_tx_busy = false;
		m_tx_tail = (tail + 1U) % CDC_TX_QUEUE_LINES;
		m_dropped++;
		CRITICAL_REGION_EXIT();
	}
}

static void cdc_event_handler(app_usbd_class_inst_t const * p_inst,
			      app_usbd_cdc_acm_user_event_t     event)
{
	UNUSED_PARAMETER(p_inst);

	switch (event)
	{
	case APP_USBD_CDC_ACM_USER_EVT_PORT_OPEN:
		m_port_open = true;
		m_rx_length = 0U;
		(void)app_usbd_cdc_acm_read(&m_app_cdc_acm, m_rx_byte, CDC_RX_CHUNK);
		break;

	case APP_USBD_CDC_ACM_USER_EVT_PORT_CLOSE:
		m_port_open = false;
		break;

	case APP_USBD_CDC_ACM_USER_EVT_TX_DONE:
		CRITICAL_REGION_ENTER();
		m_tx_tail = (m_tx_tail + 1U) % CDC_TX_QUEUE_LINES;
		m_tx_busy = false;
		CRITICAL_REGION_EXIT();
		tx_pump();
		break;

	case APP_USBD_CDC_ACM_USER_EVT_RX_DONE:
		do
		{
			char received = m_rx_byte[0];

			if ((received == '\n') || (received == '\r'))
			{
				if ((m_rx_length > 0U) && !m_rx_ready)
				{
					m_rx_line[m_rx_length] = '\0';
					(void)memcpy(m_rx_complete, m_rx_line, m_rx_length + 1U);
					m_rx_ready = true;
				}
				m_rx_length = 0U;
			}
			else if (m_rx_length < (PROTO_MAX_LINE - 1U))
			{
				m_rx_line[m_rx_length] = received;
				m_rx_length++;
			}
			else
			{
				/* Over-long line: discard it rather than acting on
				 * half a command. The host sees no reply and
				 * times out, which is the honest outcome. */
				m_rx_length = 0U;
			}
		} while (app_usbd_cdc_acm_read(&m_app_cdc_acm, m_rx_byte, CDC_RX_CHUNK) == NRF_SUCCESS);
		break;

	default:
		break;
	}
}

static void usbd_user_event_handler(app_usbd_event_type_t event)
{
	switch (event)
	{
	case APP_USBD_EVT_DRV_SUSPEND:
	case APP_USBD_EVT_DRV_RESUME:
		break;

	case APP_USBD_EVT_STARTED:
		break;

	case APP_USBD_EVT_STOPPED:
		app_usbd_disable();
		m_port_open = false;
		break;

	case APP_USBD_EVT_POWER_DETECTED:
		if (!nrf_drv_usbd_is_enabled())
		{
			app_usbd_enable();
		}
		break;

	case APP_USBD_EVT_POWER_REMOVED:
		app_usbd_stop();
		break;

	case APP_USBD_EVT_POWER_READY:
		app_usbd_start();
		break;

	default:
		break;
	}
}

uint32_t cdc_acm_init(void)
{
	static const app_usbd_config_t config =
	{
		.ev_state_proc = usbd_user_event_handler
	};
	app_usbd_class_inst_t const *	class_cdc_acm;
	ret_code_t			error;

	app_usbd_serial_num_generate();

	error = app_usbd_init(&config);
	if (error != NRF_SUCCESS)
	{
		return error;
	}

	class_cdc_acm = app_usbd_cdc_acm_class_inst_get(&m_app_cdc_acm);
	error = app_usbd_class_append(class_cdc_acm);
	if (error != NRF_SUCCESS)
	{
		return error;
	}

	error = app_usbd_power_events_enable();

	return error;
}

void cdc_acm_process(void)
{
	while (app_usbd_event_queue_process())
	{
		/* Each call handles one queued USB event. */
	}
	tx_pump();
}

bool cdc_acm_send_line(const char * line)
{
	uint32_t	head;
	uint32_t	next;
	uint32_t	length;
	bool		queued = false;

	if (line == NULL)
	{
		return false;
	}

	length = (uint32_t)strlen(line);
	if (length > (PROTO_MAX_EVENT - 2U))
	{
		length = PROTO_MAX_EVENT - 2U;
	}

	CRITICAL_REGION_ENTER();
	head = m_tx_head;
	next = (head + 1U) % CDC_TX_QUEUE_LINES;
	if (next != m_tx_tail)
	{
		(void)memcpy(m_tx_queue[head].text, line, length);
		m_tx_queue[head].text[length]      = '\n';
		m_tx_queue[head].text[length + 1U] = '\0';
		m_tx_queue[head].length            = (uint16_t)(length + 1U);
		m_tx_head                          = next;
		queued                             = true;
	}
	else
	{
		m_dropped++;
	}
	CRITICAL_REGION_EXIT();

	tx_pump();

	return queued;
}

bool cdc_acm_send_format(const char * format, ...)
{
	char	line[PROTO_MAX_EVENT];
	va_list	arguments;
	int	written;

	va_start(arguments, format);
	written = vsnprintf(line, sizeof(line) - 1U, format, arguments);
	va_end(arguments);

	if (written < 0)
	{
		return false;
	}
	line[sizeof(line) - 1U] = '\0';

	return cdc_acm_send_line(line);
}

bool cdc_acm_take_line(char * buffer, uint32_t size)
{
	bool taken = false;

	if ((buffer == NULL) || (size == 0U))
	{
		return false;
	}

	CRITICAL_REGION_ENTER();
	if (m_rx_ready)
	{
		(void)strncpy(buffer, m_rx_complete, size - 1U);
		buffer[size - 1U] = '\0';
		m_rx_ready        = false;
		taken             = true;
	}
	CRITICAL_REGION_EXIT();

	return taken;
}

uint32_t cdc_acm_dropped(void)
{
	return m_dropped;
}

bool cdc_acm_is_open(void)
{
	return m_port_open;
}
