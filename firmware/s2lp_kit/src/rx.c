/**
 * @file rx.c
 * @brief Interrupt-driven reception (#84).
 *
 * The radio is re-armed inside the interrupt, before anything is sent to the
 * host, so the time it is deaf is the interrupt's SPI traffic alone, not the
 * USB link's latency nor the host's.
 */

#include "rx.h"

#include <stddef.h>

#include "hal.h"
#include "protocol.h"
#include "ring.h"
#include "s2lp.h"

/** The interrupts reception uses. */
#define RX_IRQ_MASK  (S2LP_IRQ_RX_DATA_READY | S2LP_IRQ_RX_DATA_DISC | S2LP_IRQ_RX_FIFO_ERROR)

static volatile bool m_running;
static uint8_t m_addresses[PROTO_MAX_REGISTERS];
static uint32_t m_address_count;
static volatile uint32_t m_frames;
static volatile uint32_t m_rejects;
static volatile uint32_t m_deaf_max_us;

/**
 * @brief Flush the receive FIFO and arm the radio for the next frame.
 */
static void rx_arm(void)
{
	s2lp_command(S2LP_CMD_FLUSHRXFIFO);
	s2lp_command(S2LP_CMD_RX);
}

bool rx_start(const uint8_t *addresses, uint32_t count)
{
	bool started = false;
	uint32_t index;
	uint8_t value;

	if (count <= PROTO_MAX_REGISTERS)
	{
		hal_radio_irq_enable(false);
		m_running = false;
		s2lp_command(S2LP_CMD_SABORT);
		s2lp_command(S2LP_CMD_READY);
		for (index = 0U; index < count; index++)
		{
			m_addresses[index] = addresses[index];
		}
		m_address_count = count;
		m_frames = 0U;
		m_rejects = 0U;
		m_deaf_max_us = 0U;
		ring_reset();

		value = S2LP_GPIO_NIRQ;
		s2lp_write(S2LP_GPIO3_CONF, &value, 1U);
		s2lp_write_word(S2LP_IRQ_MASK3, RX_IRQ_MASK);
		(void)s2lp_irq_status();

		m_running = true;
		hal_radio_irq_enable(true);
		rx_arm();
		started = true;
	}
	return started;
}

void rx_stop(void)
{
	hal_radio_irq_enable(false);
	m_running = false;
	s2lp_command(S2LP_CMD_SABORT);
	s2lp_command(S2LP_CMD_FLUSHRXFIFO);
	(void)s2lp_irq_status();
}

bool rx_running(void)
{
	return m_running;
}

/**
 * @brief Queue the frame in the FIFO, with the registers read after it.
 */
static void rx_take_frame(uint32_t irq, uint32_t time_us)
{
	ring_record_t *record;
	uint8_t length;
	uint32_t index;

	s2lp_read(S2LP_RX_FIFO_STATUS, &length, 1U);
	length = (uint8_t)(length & 0x7FU);
	record = ring_claim();
	if (record != NULL)
	{
		record->kind = PROTO_KIND_FRAME;
		record->time_us = time_us;
		record->irq = irq;
		record->length = length;
		if (length > 0U)
		{
			s2lp_read(S2LP_FIFO, record->payload, length);
		}
		record->register_count = (uint8_t)m_address_count;
		for (index = 0U; index < m_address_count; index++)
		{
			s2lp_read(m_addresses[index], &record->registers[index], 1U);
		}
		ring_commit();
	}
	m_frames = m_frames + 1U;
}

/**
 * @brief Queue a reception the radio discarded, with its interrupt status.
 */
static void rx_take_reject(uint32_t irq, uint32_t time_us)
{
	ring_record_t *record = ring_claim();

	if (record != NULL)
	{
		record->kind = PROTO_KIND_REJECT;
		record->time_us = time_us;
		record->irq = irq;
		record->length = 0U;
		record->register_count = 0U;
		ring_commit();
	}
	m_rejects = m_rejects + 1U;
}

/**
 * @brief Arm the radio again, and keep the longest time it was deaf.
 */
static void rx_rearm(uint32_t since_us)
{
	uint32_t deaf_us;

	rx_arm();
	deaf_us = hal_time_us() - since_us;
	if (deaf_us > m_deaf_max_us)
	{
		m_deaf_max_us = deaf_us;
	}
}

void rx_on_irq(void)
{
	uint32_t time_us = hal_time_us();
	uint32_t irq = s2lp_irq_status();

	if (m_running)
	{
		if ((irq & S2LP_IRQ_RX_DATA_READY) != 0U)
		{
			rx_take_frame(irq, time_us);
			rx_rearm(time_us);
		}
		else if ((irq & (S2LP_IRQ_RX_DATA_DISC | S2LP_IRQ_RX_FIFO_ERROR)) != 0U)
		{
			rx_take_reject(irq, time_us);
			rx_rearm(time_us);
		}
		else
		{
			/* Nothing reception asked for: the radio is still receiving. */
		}
	}
}

uint32_t rx_frames(void)
{
	return m_frames;
}

uint32_t rx_rejects(void)
{
	return m_rejects;
}

uint32_t rx_deaf_max_us(void)
{
	return m_deaf_max_us;
}
