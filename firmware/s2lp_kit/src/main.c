/**
 * @file main.c
 * @brief ETB S2-LP kit firmware (#84): commands from the host, records to it.
 */

#include <stddef.h>
#include <stdint.h>

#include "cmd.h"
#include "hal.h"
#include "protocol.h"
#include "ring.h"

/** SDN released: wait for the radio's power-on reset. */
#define MAIN_POR_WAIT_US        (2000U)

int main(void)
{
	static char line[PROTO_LINE_MAX + 1U];
	static char out[CMD_OUT_MAX];
	uint32_t length = 0U;
	uint32_t written;
	int32_t byte;
	const ring_record_t *record;

	hal_init();
	hal_radio_shutdown(false);
	hal_delay_us(MAIN_POR_WAIT_US);

	for (;;)
	{
		record = ring_peek();
		if (record != NULL)
		{
			written = cmd_format_record(record, out);
			ring_release();
			hal_uart_write(out, written);
		}

		byte = hal_uart_read();
		if ((byte == (int32_t)'\r') || (byte == (int32_t)'\n'))
		{
			line[length] = '\0';
			cmd_handle_line(line);
			length = 0U;
		}
		else if ((byte >= 0) && (length < PROTO_LINE_MAX))
		{
			line[length] = (char)byte;
			length++;
		}
		else
		{
			/* No input, or a line too long: the excess is dropped. */
		}
	}
}
