/**
 * @file sht30.c
 * @brief Sensirion SHT30-DIS driver. See sht30.h.
 *
 * Traces to: PICO-FR-020 .. PICO-FR-026, PICO-DD-SHT30.
 */

#include "sht30.h"

#include <stddef.h>

#include "hal.h"

/** Full scale of a raw word, 2^16 - 1. */
#define SHT30_FULL_SCALE		65535U

/** Temperature span and offset, in milli-degrees Celsius. */
#define SHT30_T_SPAN_MC			175000U
#define SHT30_T_OFFSET_MC		45000

/** Humidity span, in milli-percent. */
#define SHT30_RH_SPAN_MPCT		100000U

static sht30_status_t sht30_from_hal(hal_status_t status)
{
	sht30_status_t	result;

	switch (status)
	{
	case HAL_OK:
		result = SHT30_OK;
		break;
	case HAL_ERR_TIMEOUT:
		result = SHT30_ERR_TIMEOUT;
		break;
	case HAL_ERR_NACK:
	default:
		result = SHT30_ERR_NACK;
		break;
	}
	return result;
}

static sht30_status_t sht30_send_command(uint8_t address, uint16_t command)
{
	uint8_t	bytes[2];

	bytes[0] = (uint8_t)(command >> 8);
	bytes[1] = (uint8_t)(command & 0xFFU);
	return sht30_from_hal(hal_i2c_write(address, bytes, 2U));
}

/* Check the CRC of the word at @p bytes (two data bytes then the CRC) and
 * return it in @p word. */
static sht30_status_t sht30_take_word(const uint8_t *bytes, uint16_t *word)
{
	sht30_status_t	result = SHT30_ERR_CRC;

	if (sht30_crc8(bytes, 2U) == bytes[2])
	{
		*word = (uint16_t)(((uint16_t)bytes[0] << 8) | (uint16_t)bytes[1]);
		result = SHT30_OK;
	}
	return result;
}

/* Scale @p ticks to @p span over the full-scale range, rounded to nearest.
 * 64-bit: 175000 * 65535 does not fit in 32 bits. */
static uint32_t sht30_scale(uint16_t ticks, uint32_t span)
{
	uint64_t	product = ((uint64_t)span * (uint64_t)ticks) + ((uint64_t)SHT30_FULL_SCALE / 2U);

	return (uint32_t)(product / (uint64_t)SHT30_FULL_SCALE);
}

uint8_t sht30_crc8(const uint8_t *data, uint32_t length)
{
	uint8_t		crc = (uint8_t)SHT30_CRC_INIT;
	uint32_t	index;
	uint32_t	bit;

	if (data != NULL)
	{
		for (index = 0U; index < length; index++)
		{
			crc ^= data[index];
			for (bit = 0U; bit < 8U; bit++)
			{
				if ((crc & 0x80U) != 0U)
				{
					crc = (uint8_t)((uint8_t)(crc << 1) ^ (uint8_t)SHT30_CRC_POLYNOMIAL);
				}
				else
				{
					crc = (uint8_t)(crc << 1);
				}
			}
		}
	}
	return crc;
}

int32_t sht30_ticks_to_millicelsius(uint16_t ticks)
{
	/* At most 175000, so the conversion to int32_t is exact. */
	return (int32_t)sht30_scale(ticks, SHT30_T_SPAN_MC) - SHT30_T_OFFSET_MC;
}

int32_t sht30_ticks_to_millipercent(uint16_t ticks)
{
	return (int32_t)sht30_scale(ticks, SHT30_RH_SPAN_MPCT);
}

sht30_status_t sht30_decode(const uint8_t *frame, sht30_reading_t *reading)
{
	sht30_status_t	result = SHT30_ERR_PARAM;
	uint16_t	raw_t = 0U;
	uint16_t	raw_rh = 0U;

	if ((frame != NULL) && (reading != NULL))
	{
		result = sht30_take_word(&frame[0], &raw_t);
		if (result == SHT30_OK)
		{
			result = sht30_take_word(&frame[3], &raw_rh);
		}
		if (result == SHT30_OK)
		{
			reading->raw_temperature = raw_t;
			reading->raw_humidity = raw_rh;
			reading->temperature_mc = sht30_ticks_to_millicelsius(raw_t);
			reading->humidity_mpct = sht30_ticks_to_millipercent(raw_rh);
		}
	}
	return result;
}

sht30_status_t sht30_measure(uint8_t address, sht30_reading_t *reading)
{
	sht30_status_t	result = SHT30_ERR_PARAM;
	uint8_t		frame[SHT30_FRAME_LENGTH] = { 0U };

	if (reading != NULL)
	{
		result = sht30_send_command(address, (uint16_t)SHT30_CMD_MEASURE_HIGH);
		if (result == SHT30_OK)
		{
			hal_delay_ms(SHT30_MEASURE_WAIT_MS);
			result = sht30_from_hal(hal_i2c_read(address, frame, SHT30_FRAME_LENGTH));
		}
		if (result == SHT30_OK)
		{
			result = sht30_decode(frame, reading);
		}
	}
	return result;
}

sht30_status_t sht30_read_status(uint8_t address, uint16_t *status)
{
	sht30_status_t	result = SHT30_ERR_PARAM;
	uint8_t		word[SHT30_WORD_LENGTH] = { 0U };

	if (status != NULL)
	{
		result = sht30_send_command(address, (uint16_t)SHT30_CMD_READ_STATUS);
		if (result == SHT30_OK)
		{
			result = sht30_from_hal(hal_i2c_read(address, word, SHT30_WORD_LENGTH));
		}
		if (result == SHT30_OK)
		{
			result = sht30_take_word(word, status);
		}
	}
	return result;
}

sht30_status_t sht30_soft_reset(uint8_t address)
{
	sht30_status_t	result = sht30_send_command(address, (uint16_t)SHT30_CMD_SOFT_RESET);

	if (result == SHT30_OK)
	{
		hal_delay_ms(SHT30_RESET_WAIT_MS);
	}
	return result;
}
