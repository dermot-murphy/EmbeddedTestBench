/**
 * @file fake_host_link.c
 * @brief The host link and the clock, as every other unit sees them.\n *\n * Most of what this firmware does is observable only as text sent to the\n * host, so these recorders are what the tests assert on. The clock does not\n * run: a test sets it, or gives it a step so that each read advances it -\n * which is how a wait loop is driven without waiting.
 *
 * Traces to: BLE-DD-TEST, SWE4-UT-FWUNIT.
 */

#include <stdarg.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "fakes.h"
#include "cdc_acm.h"
#include "timestamp.h"


/* ------------------------------------------------------------------ */
/* Lines towards the host                                              */
/* ------------------------------------------------------------------ */

#define FAKE_MAX_LINES	64U

static char	m_lines[FAKE_MAX_LINES][PROTO_MAX_EVENT];
static uint32_t	m_line_count;
static bool	m_lines_full;
static uint32_t	m_dropped;

static bool record(const char * line)
{
	if (m_lines_full)
	{
		m_dropped++;
		return false;
	}
	if (m_line_count < FAKE_MAX_LINES)
	{
		(void)strncpy(m_lines[m_line_count], line, PROTO_MAX_EVENT - 1U);
		m_lines[m_line_count][PROTO_MAX_EVENT - 1U] = '\0';
		m_line_count++;
	}
	return true;
}

bool cdc_acm_send_line(const char * line)
{
	return record(line);
}

bool cdc_acm_send_format(const char * format, ...)
{
	char	line[PROTO_MAX_EVENT];
	va_list	arguments;

	va_start(arguments, format);
	(void)vsnprintf(line, sizeof(line), format, arguments);
	va_end(arguments);

	return record(line);
}

uint32_t cdc_acm_init(void)				{ return 0U; }
void     cdc_acm_process(void)				{ }
bool     cdc_acm_take_line(char * buffer, uint32_t size)	{ (void)buffer; (void)size; return false; }
uint32_t cdc_acm_dropped(void)				{ return m_dropped; }
bool     cdc_acm_is_open(void)				{ return true; }

uint32_t     fake_line_count(void)		{ return m_line_count; }
const char * fake_line(uint32_t index)		{ return (index < m_line_count) ? m_lines[index] : ""; }
const char * fake_last_line(void)		{ return (m_line_count > 0U) ? m_lines[m_line_count - 1U] : ""; }
void         fake_lines_set_full(bool full)	{ m_lines_full = full; }

bool fake_line_seen(const char * prefix)
{
	uint32_t index;

	for (index = 0U; index < m_line_count; index++)
	{
		if (strncmp(m_lines[index], prefix, strlen(prefix)) == 0)
		{
			return true;
		}
	}

	return false;
}

void fake_lines_reset(void)
{
	m_line_count = 0U;
	m_lines_full = false;
	m_dropped    = 0U;
}

/* ------------------------------------------------------------------ */
/* The clock                                                           */
/* ------------------------------------------------------------------ */

static uint64_t	m_now_us;
static uint64_t	m_step_us;

uint32_t timestamp_init(void)		{ return 0U; }

uint64_t timestamp_now_us(void)
{
	uint64_t now = m_now_us;

	m_now_us += m_step_us;

	return now;
}

uint64_t timestamp_elapsed_us(uint64_t start, uint64_t end)
{
	return (end > start) ? (end - start) : 0U;
}

void fake_clock_set(uint64_t microseconds)		{ m_now_us = microseconds; }
void fake_clock_advance(uint64_t microseconds)		{ m_now_us += microseconds; }
void fake_clock_set_step(uint64_t microseconds)		{ m_step_us = microseconds; }

void fake_clock_reset(void)
{
	m_now_us  = 1000000U;
	m_step_us = 0U;
}
