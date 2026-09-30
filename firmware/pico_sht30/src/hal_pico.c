/**
 * @file hal_pico.c
 * @brief The hardware seam on the Raspberry Pi Pico 2, over the Pico C SDK.
 *
 * This is the only file that includes SDK headers, and it is not compiled
 * into the host unit tests: test/support/fake_hal.c stands in for it there.
 *
 * MISRA C:2012 deviations confined to this file (docs/pico_sht30/
 * Pico_SHT30_Notes.md §MISRA):
 *
 * * Rule 21.6 - the SDK's stdio_puts_raw() is the USB CDC output path.
 *   It is the SDK's own routine, not <stdio.h> formatting; no printf family
 *   function is used anywhere in the firmware.
 * * Dir 4.6 - SDK prototypes use the SDK's own "uint" and "int" types.
 *
 * Traces to: PICO-FR-010, PICO-FR-030, PICO-FR-031, PICO-DD-HAL.
 */

#include "hal.h"

#include "board_config.h"

#include "hardware/gpio.h"
#include "hardware/i2c.h"
#include "hardware/watchdog.h"
#include "pico/bootrom.h"
#include "pico/stdlib.h"
#include "pico/unique_id.h"

#if (BOARD_I2C_INSTANCE == 0U)
#define HAL_I2C_PORT		i2c0
#else
#define HAL_I2C_PORT		i2c1
#endif

/** Time allowed for the reply to leave over USB before a reboot drops it. */
#define HAL_REBOOT_DRAIN_MS	50U

static char	hal_board_id_text[HAL_BOARD_ID_LENGTH];

static hal_status_t hal_from_sdk(int result, uint32_t expected)
{
	hal_status_t	status;

	if (result == PICO_ERROR_TIMEOUT)
	{
		status = HAL_ERR_TIMEOUT;
	}
	else if ((result < 0) || ((uint32_t)result != expected))
	{
		status = HAL_ERR_NACK;
	}
	else
	{
		status = HAL_OK;
	}
	return status;
}

void hal_init(void)
{
	(void)i2c_init(HAL_I2C_PORT, (uint)BOARD_I2C_BAUD_HZ);
	gpio_set_function((uint)BOARD_I2C_SDA_PIN, GPIO_FUNC_I2C);
	gpio_set_function((uint)BOARD_I2C_SCL_PIN, GPIO_FUNC_I2C);
	/* The module carries its own pull-ups; the internal ones are enabled as
	 * well so that a bare sensor on a breadboard still sees a defined bus. */
	gpio_pull_up((uint)BOARD_I2C_SDA_PIN);
	gpio_pull_up((uint)BOARD_I2C_SCL_PIN);

	pico_get_unique_board_id_string(hal_board_id_text, (uint)HAL_BOARD_ID_LENGTH);
}

hal_status_t hal_i2c_write(uint8_t address, const uint8_t *data, uint32_t length)
{
	int	result = i2c_write_timeout_us(HAL_I2C_PORT, address, data, (size_t)length,
					      false, (uint)BOARD_I2C_TIMEOUT_US);

	return hal_from_sdk(result, length);
}

hal_status_t hal_i2c_read(uint8_t address, uint8_t *data, uint32_t length)
{
	int	result = i2c_read_timeout_us(HAL_I2C_PORT, address, data, (size_t)length,
					     false, (uint)BOARD_I2C_TIMEOUT_US);

	return hal_from_sdk(result, length);
}

void hal_delay_ms(uint32_t milliseconds)
{
	sleep_ms(milliseconds);
}

void hal_write_line(const char *line)
{
	/* stdio_puts_raw appends '\n' and does no CRLF translation. */
	(void)stdio_puts_raw(line);
}

const char *hal_board_id(void)
{
	return hal_board_id_text;
}

uint64_t hal_uptime_us(void)
{
	return time_us_64();
}

void hal_reboot(void)
{
	stdio_flush();
	sleep_ms(HAL_REBOOT_DRAIN_MS);
	watchdog_reboot(0U, 0U, 0U);
	for (;;)
	{
		tight_loop_contents();
	}
}

void hal_reboot_to_bootloader(void)
{
	stdio_flush();
	sleep_ms(HAL_REBOOT_DRAIN_MS);
	reset_usb_boot(0U, 0U);
}
