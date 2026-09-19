/**
 * @file timestamp.c
 * @brief A free-running microsecond clock, 64-bit by software extension.
 *
 * Traces to: BLE-FR-010, BLE-DD-TIMESTAMP.
 */

#include "timestamp.h"

#include <stdbool.h>

#include "nrfx_timer.h"
#include "app_util_platform.h"

/** TIMER instance. TIMER0 belongs to the SoftDevice; TIMER1 and TIMER2 are used
 *  by other SDK components in some configurations, so TIMER3 is taken here. */
#define TIMESTAMP_TIMER_INSTANCE	3

static const nrfx_timer_t	m_timer = NRFX_TIMER_INSTANCE(TIMESTAMP_TIMER_INSTANCE);
static volatile uint32_t	m_overflows;
static bool			m_started;

/**
 * @brief Timer interrupt: count one wrap of the 32-bit hardware counter.
 *
 * Nothing else happens here. The handler must stay short because it runs at a
 * higher priority than the command processing, and a long handler would show up
 * as jitter in exactly the measurement this clock exists to make.
 */
static void timer_event_handler(nrf_timer_event_t event_type, void * p_context)
{
	UNUSED_PARAMETER(p_context);

	if (event_type == NRF_TIMER_EVENT_COMPARE0)
	{
		m_overflows++;
	}
}

uint32_t timestamp_init(void)
{
	nrfx_timer_config_t config = NRFX_TIMER_DEFAULT_CONFIG;
	uint32_t            error;

	if (m_started)
	{
		return NRF_SUCCESS;
	}

	config.frequency          = NRF_TIMER_FREQ_1MHz;
	config.mode               = NRF_TIMER_MODE_TIMER;
	config.bit_width          = NRF_TIMER_BIT_WIDTH_32;
	config.interrupt_priority = APP_IRQ_PRIORITY_HIGH;

	error = nrfx_timer_init(&m_timer, &config, timer_event_handler);
	if (error != NRF_SUCCESS)
	{
		return error;
	}

	/* Compare at the full 32-bit range, clearing on match, so the interrupt
	 * fires exactly once per wrap and the counter stays continuous. */
	nrfx_timer_extended_compare(&m_timer,
				    NRF_TIMER_CC_CHANNEL0,
				    0xFFFFFFFFUL,
				    NRF_TIMER_SHORT_COMPARE0_CLEAR_MASK,
				    true);
	nrfx_timer_enable(&m_timer);

	m_overflows = 0U;
	m_started   = true;

	return NRF_SUCCESS;
}

uint64_t timestamp_now_us(void)
{
	uint32_t overflows;
	uint32_t ticks;

	if (!m_started)
	{
		return 0U;
	}

	/* Read the overflow count either side of the capture. If it changed, the
	 * counter wrapped between the two reads and the pair cannot be combined,
	 * so take the capture again against the new count. At most one retry is
	 * needed: a wrap is 71 minutes apart. */
	do
	{
		overflows = m_overflows;
		ticks     = nrfx_timer_capture(&m_timer, NRF_TIMER_CC_CHANNEL1);
	} while (overflows != m_overflows);

	return ((uint64_t)overflows << 32) + (uint64_t)ticks;
}

uint64_t timestamp_elapsed_us(uint64_t start, uint64_t end)
{
	return (end > start) ? (end - start) : 0U;
}
