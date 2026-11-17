/**
 * @file s2lp.c
 * @brief S2-LP register, FIFO and command access over SPI (#84).
 *
 * Traces to: S2LP-DD-KITFW.
 */

#include "s2lp.h"

#include "hal.h"

/** SPI header bytes. */
#define S2LP_HEADER_WRITE       (0x00U)
#define S2LP_HEADER_READ        (0x01U)
#define S2LP_HEADER_COMMAND     (0x80U)

/** Bytes in a 32-bit word, and bits in a byte. */
#define S2LP_WORD_BYTES         (4U)
#define S2LP_BYTE_BITS          (8U)

/** Status bytes clocked out with the last header. */
static uint16_t m_status;

/**
 * @brief Select the radio and send a header and an address or command.
 */
static void s2lp_header(uint8_t header, uint8_t operand)
{
	uint8_t high;
	uint8_t low;

	hal_spi_select(true);
	high = hal_spi_transfer(header);
	low = hal_spi_transfer(operand);
	m_status = (uint16_t)(((uint32_t)high << S2LP_BYTE_BITS) | (uint32_t)low);
}

void s2lp_read(uint8_t address, uint8_t *data, uint32_t count)
{
	uint32_t index;

	s2lp_header(S2LP_HEADER_READ, address);
	for (index = 0U; index < count; index++)
	{
		data[index] = hal_spi_transfer(0x00U);
	}
	hal_spi_select(false);
}

void s2lp_write(uint8_t address, const uint8_t *data, uint32_t count)
{
	uint32_t index;

	s2lp_header(S2LP_HEADER_WRITE, address);
	for (index = 0U; index < count; index++)
	{
		(void)hal_spi_transfer(data[index]);
	}
	hal_spi_select(false);
}

void s2lp_command(uint8_t command)
{
	s2lp_header(S2LP_HEADER_COMMAND, command);
	hal_spi_select(false);
}

uint16_t s2lp_status(void)
{
	return m_status;
}

void s2lp_write_word(uint8_t address, uint32_t value)
{
	uint8_t bytes[S2LP_WORD_BYTES];
	uint32_t index;

	for (index = 0U; index < S2LP_WORD_BYTES; index++)
	{
		bytes[index] = (uint8_t)(value >> (S2LP_BYTE_BITS * (S2LP_WORD_BYTES - 1U - index)));
	}
	s2lp_write(address, bytes, S2LP_WORD_BYTES);
}

uint32_t s2lp_irq_status(void)
{
	uint8_t bytes[S2LP_WORD_BYTES];
	uint32_t value = 0U;
	uint32_t index;

	s2lp_read(S2LP_IRQ_STATUS3, bytes, S2LP_WORD_BYTES);
	for (index = 0U; index < S2LP_WORD_BYTES; index++)
	{
		value = (value << S2LP_BYTE_BITS) | (uint32_t)bytes[index];
	}
	return value;
}
