/**
 * @file main.c
 * @brief Pico 2 + SHT30-D thermometer: USB command loop.
 *
 * Brings up USB CDC and the I2C bus, soft-resets the sensor so that it starts
 * from a known state, then assembles command lines from USB and executes them
 * for ever. A sensor that is absent at boot is not fatal: @c ver must still
 * answer, so that the host can tell "no sensor" from "no Pico".
 *
 * Traces to: PICO-FR-001, PICO-FR-025, PICO-DD-MAIN.
 */

#include <stdint.h>

#include "board_config.h"
#include "cmd_parser.h"
#include "hal.h"
#include "sht30.h"

#include "pico/stdlib.h"

/** How long one poll of the USB input waits, in microseconds. */
#define MAIN_POLL_US		1000U

int main(void)
{
	static cmd_line_t	line;
	int			received;

	(void)stdio_init_all();
	hal_init();
	(void)sht30_soft_reset((uint8_t)BOARD_SHT30_ADDRESS);
	cmd_line_init(&line);

	for (;;)
	{
		received = getchar_timeout_us(MAIN_POLL_US);
		if ((received >= 0) && (received <= 0x7F))
		{
			cmd_line_result_t	result = cmd_line_push(&line, (char)received);

			if (result == CMD_LINE_READY)
			{
				cmd_execute(line.text);
			}
			else if (result == CMD_LINE_OVERFLOW)
			{
				cmd_report_overflow();
			}
			else
			{
				/* Still assembling. */
			}
		}
	}
}
