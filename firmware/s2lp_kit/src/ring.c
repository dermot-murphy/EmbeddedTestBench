/**
 * @file ring.c
 * @brief The queue of received records (#84).
 *
 * The interrupt only advances m_head and the main loop only advances m_tail,
 * so neither needs a lock on a single-core part.
 *
 * Traces to: S2LP-DD-KITFW.
 */

#include "ring.h"

#include <stddef.h>

static ring_record_t m_records[RING_SIZE];
static volatile uint32_t m_head;
static volatile uint32_t m_tail;
static uint32_t m_next_seq;
static volatile uint32_t m_overflows;

void ring_reset(void)
{
	m_head = 0U;
	m_tail = 0U;
	m_next_seq = 0U;
	m_overflows = 0U;
}

ring_record_t *ring_claim(void)
{
	ring_record_t *record = NULL;
	uint32_t seq = m_next_seq;

	m_next_seq = seq + 1U;
	if ((m_head - m_tail) >= RING_SIZE)
	{
		m_overflows = m_overflows + 1U;
	}
	else
	{
		record = &m_records[m_head & (RING_SIZE - 1U)];
		record->seq = seq;
	}
	return record;
}

void ring_commit(void)
{
	m_head = m_head + 1U;
}

const ring_record_t *ring_peek(void)
{
	const ring_record_t *record = NULL;

	if (m_head != m_tail)
	{
		record = &m_records[m_tail & (RING_SIZE - 1U)];
	}
	return record;
}

void ring_release(void)
{
	if (m_head != m_tail)
	{
		m_tail = m_tail + 1U;
	}
}

uint32_t ring_overflows(void)
{
	return m_overflows;
}

uint32_t ring_count(void)
{
	return m_head - m_tail;
}
