/**
 * @file fake_hal.c
 * @brief A scripted stand-in for the board. See fake_hal.h.
 *
 * Traces to: PICO-DD-TEST, SWE4-UT-PICOFW.
 */

#include "fake_hal.h"

#include <string.h>

#include "sht30.h"

typedef struct
{
	uint8_t		address;
	uint32_t	length;
	uint8_t		bytes[FAKE_MAX_TRANSFER];
} fake_transfer_t;

typedef struct
{
	uint8_t		bytes[FAKE_MAX_TRANSFER];
	uint32_t	length;
	hal_status_t	status;
} fake_reply_t;

static fake_transfer_t	m_writes[FAKE_MAX_WRITES];
static uint32_t		m_write_total;
static hal_status_t	m_next_write_status;

static fake_transfer_t	m_reads[FAKE_MAX_READS];
static uint32_t		m_read_total;
static fake_reply_t	m_replies[FAKE_MAX_READS];
static uint32_t		m_reply_head;
static uint32_t		m_reply_tail;

static char		m_lines[FAKE_MAX_LINES][FAKE_MAX_LINE];
static uint32_t		m_line_total;

static uint32_t		m_delay_ms;
static uint64_t		m_uptime;
static uint32_t		m_reboots;
static uint32_t		m_lines_at_reboot;
static uint32_t		m_bootloaders;
static uint32_t		m_inits;

void fake_hal_reset(void)
{
	(void)memset(m_writes, 0, sizeof(m_writes));
	(void)memset(m_reads, 0, sizeof(m_reads));
	(void)memset(m_replies, 0, sizeof(m_replies));
	(void)memset(m_lines, 0, sizeof(m_lines));
	m_write_total = 0U;
	m_next_write_status = HAL_STATUS_OK;
	m_read_total = 0U;
	m_reply_head = 0U;
	m_reply_tail = 0U;
	m_line_total = 0U;
	m_delay_ms = 0U;
	m_uptime = 0U;
	m_reboots = 0U;
	m_lines_at_reboot = 0U;
	m_bootloaders = 0U;
	m_inits = 0U;
}

void fake_hal_fail_next_write(hal_status_t status)
{
	m_next_write_status = status;
}

void fake_hal_queue_read(const uint8_t *data, uint32_t length, hal_status_t status)
{
	fake_reply_t	*reply = &m_replies[m_reply_tail % FAKE_MAX_READS];

	reply->length = (length > FAKE_MAX_TRANSFER) ? FAKE_MAX_TRANSFER : length;
	(void)memcpy(reply->bytes, data, reply->length);
	reply->status = status;
	m_reply_tail++;
}

void fake_hal_queue_measurement(uint16_t t, uint16_t rh)
{
	uint8_t	frame[SHT30_FRAME_LENGTH];

	frame[0] = (uint8_t)(t >> 8U);
	frame[1] = (uint8_t)(t & 0xFFU);
	frame[2] = sht30_crc8(&frame[0], 2U);
	frame[3] = (uint8_t)(rh >> 8U);
	frame[4] = (uint8_t)(rh & 0xFFU);
	frame[5] = sht30_crc8(&frame[3], 2U);
	fake_hal_queue_read(frame, SHT30_FRAME_LENGTH, HAL_STATUS_OK);
}

uint32_t fake_hal_write_count(void) { return m_write_total; }
uint8_t fake_hal_write_address(uint32_t n) { return m_writes[n].address; }
uint32_t fake_hal_write_length(uint32_t n) { return m_writes[n].length; }
const uint8_t *fake_hal_write_bytes(uint32_t n) { return m_writes[n].bytes; }
uint32_t fake_hal_read_count(void) { return m_read_total; }
uint8_t fake_hal_read_address(uint32_t n) { return m_reads[n].address; }
uint32_t fake_hal_read_length(uint32_t n) { return m_reads[n].length; }
uint32_t fake_hal_delay_total_ms(void) { return m_delay_ms; }
uint32_t fake_hal_line_count(void) { return m_line_total; }
const char *fake_hal_line(uint32_t n) { return m_lines[n]; }
void fake_hal_set_uptime_us(uint64_t uptime) { m_uptime = uptime; }
uint32_t fake_hal_reboot_count(void) { return m_reboots; }
uint32_t fake_hal_bootloader_count(void) { return m_bootloaders; }
uint32_t fake_hal_init_count(void) { return m_inits; }
uint32_t fake_hal_lines_at_reboot(void) { return m_lines_at_reboot; }

const char *fake_hal_last_line(void)
{
	return (m_line_total == 0U) ? "" : m_lines[m_line_total - 1U];
}

/* ------------------------------------------------------------------------ */
/* The HAL itself. */

void hal_init(void)
{
	m_inits++;
}

hal_status_t hal_i2c_write(uint8_t address, const uint8_t *data, uint32_t length)
{
	hal_status_t	status = m_next_write_status;

	if (m_write_total < FAKE_MAX_WRITES)
	{
		fake_transfer_t	*write = &m_writes[m_write_total];

		write->address = address;
		write->length = length;
		(void)memcpy(write->bytes, data, (length > FAKE_MAX_TRANSFER) ? FAKE_MAX_TRANSFER : length);
	}
	m_write_total++;
	m_next_write_status = HAL_STATUS_OK;
	return status;
}

hal_status_t hal_i2c_read(uint8_t address, uint8_t *data, uint32_t length)
{
	hal_status_t	status = HAL_STATUS_ERR_NACK;

	if (m_read_total < FAKE_MAX_READS)
	{
		m_reads[m_read_total].address = address;
		m_reads[m_read_total].length = length;
	}
	m_read_total++;

	/* An empty queue is a sensor that is not there: it NACKs its address. */
	if (m_reply_head != m_reply_tail)
	{
		const fake_reply_t	*reply = &m_replies[m_reply_head % FAKE_MAX_READS];

		m_reply_head++;
		(void)memcpy(data, reply->bytes, (reply->length < length) ? reply->length : length);
		status = reply->status;
	}
	return status;
}

void hal_delay_ms(uint32_t milliseconds)
{
	m_delay_ms += milliseconds;
}

void hal_write_line(const char *line)
{
	if (m_line_total < FAKE_MAX_LINES)
	{
		(void)strncpy(m_lines[m_line_total], line, FAKE_MAX_LINE - 1U);
	}
	m_line_total++;
}

const char *hal_board_id(void)
{
	return FAKE_BOARD_ID;
}

uint64_t hal_uptime_us(void)
{
	return m_uptime;
}

void hal_reboot(void)
{
	m_lines_at_reboot = m_line_total;
	m_reboots++;
}

void hal_reboot_to_bootloader(void)
{
	m_lines_at_reboot = m_line_total;
	m_bootloaders++;
}
