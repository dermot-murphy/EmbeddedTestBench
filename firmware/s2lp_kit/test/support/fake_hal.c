/**
 * @file fake_hal.c
 * @brief A stand-in for the board and the S2-LP, for the host unit tests (#84).
 */

#include "fake_hal.h"

#include <string.h>

/** IRQ_STATUS3, the first of the four status registers; bytes and bits. */
#define FAKE_HAL_IRQ_STATUS3    (0xFAU)
#define FAKE_HAL_WORD_BYTES     (4U)
#define FAKE_HAL_BYTE_BITS      (8U)

/** Where the fake SPI transaction is. */
typedef enum
{
	FAKE_HAL_PHASE_IDLE,
	FAKE_HAL_PHASE_HEADER,
	FAKE_HAL_PHASE_READING,
	FAKE_HAL_PHASE_WRITING,
	FAKE_HAL_PHASE_COMMAND,
	FAKE_HAL_PHASE_DONE
} fake_hal_phase_t;

static uint8_t m_registers[256];
static uint8_t m_fifo[256];
static uint32_t m_fifo_length;
static uint32_t m_fifo_read;
static uint8_t m_commands[FAKE_HAL_MAX_COMMANDS];
static uint32_t m_command_count;
static char m_output[FAKE_HAL_MAX_OUTPUT];
static uint32_t m_output_length;
static uint32_t m_time_us;
static bool m_irq_enabled;
static bool m_shutdown;
static fake_hal_phase_t m_phase;
static uint8_t m_header;
static uint8_t m_address;

void fake_hal_reset(void)
{
	(void)memset(m_registers, 0, sizeof(m_registers));
	m_registers[0xF1] = 0xC1U;
	m_fifo_length = 0U;
	m_fifo_read = 0U;
	m_command_count = 0U;
	fake_hal_clear_output();
	m_time_us = 0U;
	m_irq_enabled = false;
	m_shutdown = true;
	m_phase = FAKE_HAL_PHASE_IDLE;
}

uint8_t fake_hal_register(uint8_t address)
{
	return m_registers[address];
}

void fake_hal_set_register(uint8_t address, uint8_t value)
{
	m_registers[address] = value;
}

void fake_hal_raise_irq(uint32_t bits)
{
	uint32_t index;

	for (index = 0U; index < FAKE_HAL_WORD_BYTES; index++)
	{
		m_registers[FAKE_HAL_IRQ_STATUS3 + index] |=
			(uint8_t)(bits >> (FAKE_HAL_BYTE_BITS * (FAKE_HAL_WORD_BYTES - 1U - index)));
	}
}

void fake_hal_queue_frame(const uint8_t *payload, uint32_t length)
{
	(void)memcpy(m_fifo, payload, length);
	m_fifo_length = length;
	m_fifo_read = 0U;
	m_registers[0x90] = (uint8_t)length;
}

uint32_t fake_hal_command_count(void)
{
	return m_command_count;
}

uint8_t fake_hal_command(uint32_t index)
{
	return m_commands[index];
}

const char *fake_hal_output(void)
{
	return m_output;
}

void fake_hal_clear_output(void)
{
	m_output_length = 0U;
	m_output[0] = '\0';
}

void fake_hal_set_time(uint32_t micros)
{
	m_time_us = micros;
}

bool fake_hal_irq_enabled(void)
{
	return m_irq_enabled;
}

bool fake_hal_shutdown(void)
{
	return m_shutdown;
}

void hal_init(void)
{
}

void hal_spi_select(bool selected)
{
	m_phase = selected ? FAKE_HAL_PHASE_HEADER : FAKE_HAL_PHASE_IDLE;
}

/**
 * @brief One byte read from the radio at the current address.
 */
static uint8_t fake_hal_read_byte(void)
{
	uint8_t value;

	if (m_address == 0xFFU)
	{
		value = (m_fifo_read < m_fifo_length) ? m_fifo[m_fifo_read] : 0U;
		m_fifo_read++;
		m_registers[0x90] = (uint8_t)((m_fifo_read < m_fifo_length)
			? (m_fifo_length - m_fifo_read) : 0U);
	}
	else
	{
		value = m_registers[m_address];
		if (m_address >= 0xFAU)
		{
			m_registers[m_address] = 0U;        /* reading the status clears it */
		}
		m_address++;
	}
	return value;
}

uint8_t hal_spi_transfer(uint8_t byte)
{
	uint8_t reply = 0U;

	m_time_us++;                                /* each byte takes a microsecond */

	switch (m_phase)
	{
	case FAKE_HAL_PHASE_HEADER:
		m_header = byte;
		m_phase = FAKE_HAL_PHASE_COMMAND;
		reply = 0x52U;                          /* MC_STATE1-like byte */
		break;
	case FAKE_HAL_PHASE_COMMAND:
		if (m_header == 0x80U)
		{
			if (m_command_count < FAKE_HAL_MAX_COMMANDS)
			{
				m_commands[m_command_count] = byte;
				m_command_count++;
			}
			if (byte == 0x71U)
			{
				m_fifo_length = 0U;
				m_fifo_read = 0U;
				m_registers[0x90] = 0U;
			}
			m_phase = FAKE_HAL_PHASE_DONE;
		}
		else
		{
			m_address = byte;
			m_phase = (m_header == 0x01U) ? FAKE_HAL_PHASE_READING : FAKE_HAL_PHASE_WRITING;
		}
		reply = 0x07U;                          /* MC_STATE0-like byte */
		break;
	case FAKE_HAL_PHASE_READING:
		reply = fake_hal_read_byte();
		break;
	case FAKE_HAL_PHASE_WRITING:
		m_registers[m_address] = byte;
		m_address++;
		break;
	default:
		break;
	}
	return reply;
}

void hal_radio_shutdown(bool shutdown)
{
	m_shutdown = shutdown;
}

void hal_radio_irq_enable(bool enable)
{
	m_irq_enabled = enable;
}

void hal_delay_us(uint32_t micros)
{
	m_time_us += micros;
}

uint32_t hal_time_us(void)
{
	return m_time_us;
}

void hal_uart_write(const char *text, uint32_t length)
{
	uint32_t index;

	for (index = 0U; (index < length) && (m_output_length < (FAKE_HAL_MAX_OUTPUT - 1U)); index++)
	{
		m_output[m_output_length] = text[index];
		m_output_length++;
	}
	m_output[m_output_length] = '\0';
}

int32_t hal_uart_read(void)
{
	return -1;
}

uint32_t hal_uart_overruns(void)
{
	return 0U;
}

uint32_t hal_irq_save(void)
{
	return 0U;
}

void hal_irq_restore(uint32_t state)
{
	(void)state;
}
