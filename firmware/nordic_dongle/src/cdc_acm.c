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
#include "timestamp.h"

#define CDC_ACM_COMM_INTERFACE		0
#define CDC_ACM_COMM_EPIN		NRF_DRV_USBD_EPIN2
#define CDC_ACM_DATA_INTERFACE		1
#define CDC_ACM_DATA_EPIN		NRF_DRV_USBD_EPIN1
#define CDC_ACM_DATA_EPOUT		NRF_DRV_USBD_EPOUT1

/** Bytes read from the endpoint at a time. One is deliberate: the CDC driver
 *  reports each byte as it arrives, which is what lets a line be assembled
 *  without waiting for a buffer to fill or a timeout to expire. */
#define CDC_ACM_RX_CHUNK		1U

static void cdc_acm_event_handler(app_usbd_class_inst_t const * p_inst,
				  app_usbd_cdc_acm_user_event_t     event);

APP_USBD_CDC_ACM_GLOBAL_DEF(m_app_cdc_acm,
			    cdc_acm_event_handler,
			    CDC_ACM_COMM_INTERFACE,
			    CDC_ACM_DATA_INTERFACE,
			    CDC_ACM_COMM_EPIN,
			    CDC_ACM_DATA_EPIN,
			    CDC_ACM_DATA_EPOUT,
			    APP_USBD_CDC_COMM_PROTOCOL_AT_V250);

/** One queued output line. */
typedef struct
{
	char		text[PROTOCOL_MAX_EVENT];
	uint16_t	length;
} cdc_line_t;

static cdc_line_t	m_tx_queue[CDC_ACM_TX_QUEUE_LINES];
static volatile uint32_t m_tx_head;		/**< next slot to fill */
static volatile uint32_t m_tx_tail;		/**< next slot to send */
static volatile bool	m_tx_busy;		/**< an endpoint write is in flight */
static volatile uint32_t m_dropped;

static uint32_t		m_rx_length;
static bool		m_rx_overflow;		/**< discarding to the terminator */
static volatile bool	m_rx_ready;		/**< a complete line is waiting */
static char		m_rx_complete[PROTOCOL_MAX_LINE];

static volatile bool	m_port_open;

/**
 * @brief Start the next queued write, if any and if the endpoint is free.
 */
static void cdc_acm_tx_pump(void)
{
	uint32_t	tail  = 0U;
	bool		start = false;

	/* CRITICAL_REGION_ENTER() opens a scope that CRITICAL_REGION_EXIT()
	 * closes, so the two must be balanced in the same block and there can be
	 * no return between them. The decision is therefore taken inside the
	 * region and acted on outside it. */
	CRITICAL_REGION_ENTER();
	if (!m_tx_busy && (m_tx_head != m_tx_tail) && m_port_open)
	{
		tail      = m_tx_tail;
		m_tx_busy = true;
		start     = true;
	}
	CRITICAL_REGION_EXIT();

	if (start)
	{
		ret_code_t error = app_usbd_cdc_acm_write(&m_app_cdc_acm,
					       m_tx_queue[tail].text,
					       m_tx_queue[tail].length);
		if (error != NRF_SUCCESS)
		{
			/* The endpoint refused the write: release the slot and count
			 * the line as dropped, so the host's total still reconciles. */
			CRITICAL_REGION_ENTER();
			m_tx_busy = false;
			m_tx_tail = (tail + 1U) % CDC_ACM_TX_QUEUE_LINES;
			m_dropped++;
			CRITICAL_REGION_EXIT();
		}
	}
}

/**
 * @brief Add one received byte to the line being assembled.
 */
static void cdc_acm_rx_byte(char received)
{
	static char line[PROTOCOL_MAX_LINE];

	if ((received == '\n') || (received == '\r'))
	{
		if ((m_rx_length > 0U) && !m_rx_ready && !m_rx_overflow)
		{
			line[m_rx_length] = '\0';
			(void)memcpy(m_rx_complete, line, m_rx_length + 1U);
			m_rx_ready = true;
		}
		m_rx_length   = 0U;
		m_rx_overflow = false;
	}
	else if (m_rx_overflow)
	{
		/* Still discarding the remains of an over-long line. */
	}
	else if (m_rx_length < (PROTOCOL_MAX_LINE - 1U))
	{
		line[m_rx_length] = received;
		m_rx_length++;
	}
	else
	{
		/* Over-long line: discard it, and keep discarding until the
		 * terminator. Starting a new line here would make the *tail* of a
		 * too-long command a command in its own right - and the tail of
		 * anything is not what the host asked for. The host sees no reply
		 * and times out, which is the honest outcome. */
		m_rx_length   = 0U;
		m_rx_overflow = true;
	}
}

static void cdc_acm_event_handler(app_usbd_class_inst_t const * p_inst,
				  app_usbd_cdc_acm_user_event_t     event)
{
	static char rx_byte[CDC_ACM_RX_CHUNK];

	UNUSED_PARAMETER(p_inst);

	switch (event)
	{
	case APP_USBD_CDC_ACM_USER_EVT_PORT_OPEN:
		m_port_open   = true;
		m_rx_length   = 0U;
		m_rx_overflow = false;
		(void)app_usbd_cdc_acm_read(&m_app_cdc_acm, rx_byte, CDC_ACM_RX_CHUNK);
		break;

	case APP_USBD_CDC_ACM_USER_EVT_PORT_CLOSE:
		m_port_open = false;
		break;

	case APP_USBD_CDC_ACM_USER_EVT_TX_DONE:
		CRITICAL_REGION_ENTER();
		m_tx_tail = (m_tx_tail + 1U) % CDC_ACM_TX_QUEUE_LINES;
		m_tx_busy = false;
		CRITICAL_REGION_EXIT();
		cdc_acm_tx_pump();
		break;

	case APP_USBD_CDC_ACM_USER_EVT_RX_DONE:
		do
		{
			cdc_acm_rx_byte(rx_byte[0]);
		} while (app_usbd_cdc_acm_read(&m_app_cdc_acm, rx_byte, CDC_ACM_RX_CHUNK) == NRF_SUCCESS);
		break;

	default:
		break;
	}
}

static void cdc_acm_usbd_event_handler(app_usbd_event_type_t event)
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
		.ev_state_proc = cdc_acm_usbd_event_handler
	};
	ret_code_t error;

	app_usbd_serial_num_generate();

	error = app_usbd_init(&config);
	if (error == NRF_SUCCESS)
	{
		app_usbd_class_inst_t const * class_cdc_acm =
			app_usbd_cdc_acm_class_inst_get(&m_app_cdc_acm);

		error = app_usbd_class_append(class_cdc_acm);
	}
	if (error == NRF_SUCCESS)
	{
		error = app_usbd_power_events_enable();
	}

	return error;
}

/**
 * @brief Tell the host about lines dropped since the last report.
 *
 * Main-loop context only. The report is queued only when a slot is free, so a
 * full queue does not turn every pass of the main loop into one more dropped
 * line. If an event handler takes that slot first, the report is dropped and
 * counted like any other line, and the next pass reports it with the rest.
 * The count is lines lost since the previous @c +drop, so the host's sum of
 * the counts equals the total in @c ver and @c adv @c stats (#396).
 */
static void cdc_acm_report_drops(void)
{
	static uint32_t	reported;	/* m_dropped when +drop last went out */
	uint32_t	dropped;
	bool		room;
	char		time_text[TIMESTAMP_TEXT_SIZE];

	CRITICAL_REGION_ENTER();
	dropped = m_dropped;
	room    = (((m_tx_head + 1U) % CDC_ACM_TX_QUEUE_LINES) != m_tx_tail);
	CRITICAL_REGION_EXIT();

	if ((dropped != reported) && room)
	{
		if (cdc_acm_send_format("+drop t=%s count=%lu",
					timestamp_format_us(timestamp_now_us(), time_text),
					(unsigned long)(dropped - reported)))
		{
			reported = dropped;
		}
	}
}

void cdc_acm_process(void)
{
	while (app_usbd_event_queue_process())
	{
		/* Each call handles one queued USB event. */
	}
	cdc_acm_tx_pump();
	cdc_acm_report_drops();
}

bool cdc_acm_send_line(const char * line)
{
	bool queued = false;

	if (line != NULL)
	{
		uint32_t	head;
		uint32_t	next;
		uint32_t	length = (uint32_t)strlen(line);

		if (length > (PROTOCOL_MAX_EVENT - 2U))
		{
			length = PROTOCOL_MAX_EVENT - 2U;
		}

		CRITICAL_REGION_ENTER();
		head = m_tx_head;
		next = (head + 1U) % CDC_ACM_TX_QUEUE_LINES;
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

		cdc_acm_tx_pump();
	}

	return queued;
}

bool cdc_acm_send_format(const char * format, ...)
{
	char	line[PROTOCOL_MAX_EVENT];
	va_list	arguments;
	int	written;
	bool	queued = false;

	va_start(arguments, format);
	written = vsnprintf(line, sizeof(line) - 1U, format, arguments);
	va_end(arguments);

	if (written >= 0)
	{
		line[sizeof(line) - 1U] = '\0';
		queued = cdc_acm_send_line(line);
	}

	return queued;
}

bool cdc_acm_take_line(char * buffer, uint32_t size)
{
	bool taken = false;

	if ((buffer != NULL) && (size != 0U))
	{
		CRITICAL_REGION_ENTER();
		if (m_rx_ready)
		{
			(void)strncpy(buffer, m_rx_complete, size - 1U);
			buffer[size - 1U] = '\0';
			m_rx_ready        = false;
			taken             = true;
		}
		CRITICAL_REGION_EXIT();
	}

	return taken;
}

uint32_t cdc_acm_dropped(void)
{
	return m_dropped;
}

bool cdc_acm_tx_idle(void)
{
	return (m_tx_head == m_tx_tail) && !m_tx_busy;
}
