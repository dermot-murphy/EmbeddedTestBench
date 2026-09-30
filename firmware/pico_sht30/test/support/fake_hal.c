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

static fake_transfer_t	fake_writes[FAKE_MAX_WRITES];
static uint32_t		fake_write_total;
static hal_status_t	fake_next_write_status;

static fake_transfer_t	fake_reads[FAKE_MAX_READS];
static uint32_t		fake_read_total;
static fake_reply_t	fake_replies[FAKE_MAX_READS];
static uint32_t		fake_reply_head;
static uint32_t		fake_reply_tail;

static char		fake_lines[FAKE_MAX_LINES][FAKE_MAX_LINE];
static uint32_t		fake_line_total;

static uint32_t		fake_delay_ms;
static uint64_t		fake_uptime;
static uint32_t		fake_reboots;
static uint32_t		fake_lines_at_reboot;
static uint32_t		fake_bootloaders;
static uint32_t		fake_inits;

void fake_hal_reset(void)
{
	(void)memset(fake_writes, 0, sizeof(fake_writes));
	(void)memset(fake_reads, 0, sizeof(fake_reads));
	(void)memset(fake_replies, 0, sizeof(fake_replies));
	(void)memset(fake_lines, 0, sizeof(fake_lines));
	fake_write_total = 0U;
	fake_next_write_status = HAL_OK;
	fake_read_total = 0U;
	fake_reply_head = 0U;
	fake_reply_tail = 0U;
	fake_line_total = 0U;
	fake_delay_ms = 0U;
	fake_uptime = 0U;
	fake_reboots = 0U;
	fake_lines_at_reboot = 0U;
	fake_bootloaders = 0U;
	fake_inits = 0U;
}

void fake_hal_fail_next_write(hal_status_t status)
{
	fake_next_write_status = status;
}

void fake_hal_queue_read(const uint8_t *data, uint32_t length, hal_status_t status)
{
	fake_reply_t	*reply = &fake_replies[fake_reply_tail % FAKE_MAX_READS];

	reply->length = (length > FAKE_MAX_TRANSFER) ? FAKE_MAX_TRANSFER : length;
	(void)memcpy(reply->bytes, data, reply->length);
	reply->status = status;
	fake_reply_tail++;
}

void fake_hal_queue_measurement(uint16_t t, uint16_t rh)
{
	uint8_t	frame[SHT30_FRAME_LENGTH];

	frame[0] = (uint8_t)(t >> 8);
	frame[1] = (uint8_t)(t & 0xFFU);
	frame[2] = sht30_crc8(&frame[0], 2U);
	frame[3] = (uint8_t)(rh >> 8);
	frame[4] = (uint8_t)(rh & 0xFFU);
	frame[5] = sht30_crc8(&frame[3], 2U);
	fake_hal_queue_read(frame, SHT30_FRAME_LENGTH, HAL_OK);
}

uint32_t fake_hal_write_count(void) { return fake_write_total; }
uint8_t fake_hal_write_address(uint32_t n) { return fake_writes[n].address; }
uint32_t fake_hal_write_length(uint32_t n) { return fake_writes[n].length; }
const uint8_t *fake_hal_write_bytes(uint32_t n) { return fake_writes[n].bytes; }
uint32_t fake_hal_read_count(void) { return fake_read_total; }
uint8_t fake_hal_read_address(uint32_t n) { return fake_reads[n].address; }
uint32_t fake_hal_read_length(uint32_t n) { return fake_reads[n].length; }
uint32_t fake_hal_delay_total_ms(void) { return fake_delay_ms; }
uint32_t fake_hal_line_count(void) { return fake_line_total; }
const char *fake_hal_line(uint32_t n) { return fake_lines[n]; }
void fake_hal_set_uptime_us(uint64_t uptime) { fake_uptime = uptime; }
uint32_t fake_hal_reboot_count(void) { return fake_reboots; }
uint32_t fake_hal_bootloader_count(void) { return fake_bootloaders; }
uint32_t fake_hal_init_count(void) { return fake_inits; }
uint32_t fake_hal_lines_at_reboot(void) { return fake_lines_at_reboot; }

const char *fake_hal_last_line(void)
{
	return (fake_line_total == 0U) ? "" : fake_lines[fake_line_total - 1U];
}

/* ------------------------------------------------------------------------ */
/* The HAL itself. */

void hal_init(void)
{
	fake_inits++;
}

hal_status_t hal_i2c_write(uint8_t address, const uint8_t *data, uint32_t length)
{
	hal_status_t	status = fake_next_write_status;

	if (fake_write_total < FAKE_MAX_WRITES)
	{
		fake_transfer_t	*write = &fake_writes[fake_write_total];

		write->address = address;
		write->length = length;
		(void)memcpy(write->bytes, data, (length > FAKE_MAX_TRANSFER) ? FAKE_MAX_TRANSFER : length);
	}
	fake_write_total++;
	fake_next_write_status = HAL_OK;
	return status;
}

hal_status_t hal_i2c_read(uint8_t address, uint8_t *data, uint32_t length)
{
	hal_status_t	status = HAL_ERR_NACK;

	if (fake_read_total < FAKE_MAX_READS)
	{
		fake_reads[fake_read_total].address = address;
		fake_reads[fake_read_total].length = length;
	}
	fake_read_total++;

	/* An empty queue is a sensor that is not there: it NACKs its address. */
	if (fake_reply_head != fake_reply_tail)
	{
		const fake_reply_t	*reply = &fake_replies[fake_reply_head % FAKE_MAX_READS];

		fake_reply_head++;
		(void)memcpy(data, reply->bytes, (reply->length < length) ? reply->length : length);
		status = reply->status;
	}
	return status;
}

void hal_delay_ms(uint32_t milliseconds)
{
	fake_delay_ms += milliseconds;
}

void hal_write_line(const char *line)
{
	if (fake_line_total < FAKE_MAX_LINES)
	{
		(void)strncpy(fake_lines[fake_line_total], line, FAKE_MAX_LINE - 1U);
	}
	fake_line_total++;
}

const char *hal_board_id(void)
{
	return FAKE_BOARD_ID;
}

uint64_t hal_uptime_us(void)
{
	return fake_uptime;
}

void hal_reboot(void)
{
	fake_lines_at_reboot = fake_line_total;
	fake_reboots++;
}

void hal_reboot_to_bootloader(void)
{
	fake_lines_at_reboot = fake_line_total;
	fake_bootloaders++;
}
