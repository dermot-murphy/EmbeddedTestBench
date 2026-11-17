/**
 * @file cmd.c
 * @brief The host's commands, and the records sent while receiving (#84).
 *
 * Traces to: S2LP-DD-KITFW.
 */

#include "cmd.h"

#include <stdbool.h>
#include <stddef.h>
#include <string.h>

#include "firmware_version.h"
#include "hal.h"
#include "protocol.h"
#include "rx.h"
#include "s2lp.h"

/** Most words in a command line. */
#define CMD_MAX_WORDS           (4U)

/** Number bases, and the bits in one hexadecimal digit. */
#define CMD_DECIMAL             (10U)
#define CMD_HEXADECIMAL         (16U)
#define CMD_NIBBLE_BITS         (4U)
#define CMD_BYTE_BITS           (8U)

/** Bytes in the widest value cmd_put_hex_word writes. */
#define CMD_WORD_BYTES          (4U)

static const char m_hex_digits[] = "0123456789abcdef";

/**
 * @brief Text being built for the host.
 */
typedef struct
{
	char text[CMD_OUT_MAX];
	uint32_t length;
} cmd_out_t;

static void cmd_put_text(cmd_out_t *out, const char *text)
{
	const char *cursor = text;

	while ((*cursor != '\0') && (out->length < (CMD_OUT_MAX - 2U)))
	{
		out->text[out->length] = *cursor;
		out->length++;
		cursor++;
	}
}

static void cmd_put_decimal(cmd_out_t *out, uint32_t value)
{
	char digits[CMD_DECIMAL];
	uint32_t count = 0U;
	uint32_t rest = value;

	do
	{
		digits[count] = m_hex_digits[rest % CMD_DECIMAL];
		count++;
		rest = rest / CMD_DECIMAL;
	} while (rest != 0U);

	while ((count > 0U) && (out->length < (CMD_OUT_MAX - 2U)))
	{
		count--;
		out->text[out->length] = digits[count];
		out->length++;
	}
}

static void cmd_put_hex(cmd_out_t *out, const uint8_t *bytes, uint32_t count)
{
	uint32_t index;

	for (index = 0U; (index < count) && (out->length < (CMD_OUT_MAX - 3U)); index++)
	{
		out->text[out->length] = m_hex_digits[bytes[index] >> CMD_NIBBLE_BITS];
		out->text[out->length + 1U] = m_hex_digits[bytes[index] & 0x0FU];
		out->length += 2U;
	}
}

static void cmd_put_hex_word(cmd_out_t *out, uint32_t value, uint32_t bytes)
{
	uint8_t data[CMD_WORD_BYTES] = {0U, 0U, 0U, 0U};
	uint32_t index;

	for (index = 0U; (index < bytes) && (index < CMD_WORD_BYTES); index++)
	{
		data[index] = (uint8_t)(value >> (CMD_BYTE_BITS * (bytes - 1U - index)));
	}
	cmd_put_hex(out, data, bytes);
}

static void cmd_send(cmd_out_t *out)
{
	out->text[out->length] = '\r';
	out->text[out->length + 1U] = '\n';
	out->length += 2U;
	hal_uart_write(out->text, out->length);
}

static void cmd_send_text(const char *text)
{
	cmd_out_t out;

	out.length = 0U;
	cmd_put_text(&out, text);
	cmd_send(&out);
}

/**
 * @brief The value of one hexadecimal digit, or -1.
 */
static int32_t cmd_hex_value(char digit)
{
	int32_t value = -1;

	if ((digit >= '0') && (digit <= '9'))
	{
		value = ((int32_t)digit - (int32_t)'0');
	}
	else if ((digit >= 'a') && (digit <= 'f'))
	{
		value = ((int32_t)digit - (int32_t)'a') + (int32_t)CMD_DECIMAL;
	}
	else if ((digit >= 'A') && (digit <= 'F'))
	{
		value = ((int32_t)digit - (int32_t)'A') + (int32_t)CMD_DECIMAL;
	}
	else
	{
		/* Not a hexadecimal digit. */
	}
	return value;
}

/**
 * @brief Parse a number of 1 to 8 digits in base 10 or 16; false if it is not one.
 */
static bool cmd_parse_number(const char *text, uint32_t base, uint32_t *value)
{
	bool valid = (text != NULL) && (*text != '\0') && (strlen(text) <= 8U);
	uint32_t result = 0U;
	const char *cursor = text;

	while (valid && (*cursor != '\0'))
	{
		int32_t digit = cmd_hex_value(*cursor);

		if ((digit < 0) || ((uint32_t)digit >= base))
		{
			valid = false;
		}
		else
		{
			result = (result * base) + (uint32_t)digit;
		}
		cursor++;
	}
	if (valid)
	{
		*value = result;
	}
	return valid;
}

/**
 * @brief Parse a byte address in hexadecimal.
 */
static bool cmd_parse_address(const char *text, uint8_t *address)
{
	uint32_t value = 0U;
	bool valid = cmd_parse_number(text, CMD_HEXADECIMAL, &value) && (value <= 0xFFU);

	if (valid)
	{
		*address = (uint8_t)value;
	}
	return valid;
}

/**
 * @brief Parse a hexadecimal byte string of 1 .. PROTO_MAX_PAYLOAD bytes.
 */
static bool cmd_parse_bytes(const char *text, uint8_t *bytes, uint32_t *count)
{
	uint32_t length = (text != NULL) ? (uint32_t)strlen(text) : 0U;
	bool valid = (length > 0U) && ((length % 2U) == 0U)
		&& ((length / 2U) <= PROTO_MAX_PAYLOAD);
	uint32_t index;

	for (index = 0U; valid && (index < (length / 2U)); index++)
	{
		int32_t high = cmd_hex_value(text[2U * index]);
		int32_t low = cmd_hex_value(text[(2U * index) + 1U]);

		if ((high < 0) || (low < 0))
		{
			valid = false;
		}
		else
		{
			bytes[index] = (uint8_t)(((uint32_t)high << CMD_NIBBLE_BITS) | (uint32_t)low);
		}
	}
	if (valid)
	{
		*count = length / 2U;
	}
	return valid;
}

/**
 * @brief Split a line at spaces into at most CMD_MAX_WORDS words.
 */
static uint32_t cmd_split(char *line, char *words[CMD_MAX_WORDS])
{
	uint32_t count = 0U;
	char *cursor = line;

	while (*cursor != '\0')
	{
		while (*cursor == ' ')
		{
			*cursor = '\0';
			cursor++;
		}
		if (*cursor != '\0')
		{
			if (count == CMD_MAX_WORDS)
			{
				count = CMD_MAX_WORDS + 1U;
				break;
			}
			words[count] = cursor;
			count++;
			while ((*cursor != ' ') && (*cursor != '\0'))
			{
				cursor++;
			}
		}
	}
	return count;
}

static void cmd_id(void)
{
	cmd_out_t out;
	uint8_t silicon = 0U;
	uint32_t state = hal_irq_save();

	s2lp_read(S2LP_DEVICE_INFO0, &silicon, 1U);
	hal_irq_restore(state);

	out.length = 0U;
	cmd_put_text(&out, "ok " FIRMWARE_NAME " " FIRMWARE_VERSION " proto=");
	cmd_put_decimal(&out, PROTO_VERSION);
	cmd_put_text(&out, " silicon=");
	cmd_put_hex(&out, &silicon, 1U);
	cmd_send(&out);
}

static void cmd_rd(char *words[], uint32_t count)
{
	uint8_t address = 0U;
	uint32_t length = 0U;

	if ((count != 3U) || !cmd_parse_address(words[1], &address)
		|| !cmd_parse_number(words[2], CMD_DECIMAL, &length)
		|| (length == 0U) || (length > PROTO_MAX_PAYLOAD))
	{
		cmd_send_text("err bad argument");
	}
	else
	{
		cmd_out_t out;
		uint8_t data[PROTO_MAX_PAYLOAD];

		s2lp_read(address, data, length);
		out.length = 0U;
		cmd_put_text(&out, "ok ");
		cmd_put_hex(&out, data, length);
		cmd_send(&out);
	}
}

static void cmd_wr(char *words[], uint32_t count)
{
	uint8_t address = 0U;
	uint32_t length = 0U;
	uint8_t data[PROTO_MAX_PAYLOAD];

	if ((count != 3U) || !cmd_parse_address(words[1], &address)
		|| !cmd_parse_bytes(words[2], data, &length))
	{
		cmd_send_text("err bad argument");
	}
	else
	{
		s2lp_write(address, data, length);
		cmd_send_text("ok");
	}
}

static void cmd_cmd(char *words[], uint32_t count)
{
	cmd_out_t out;
	uint8_t code = 0U;

	if ((count != 2U) || !cmd_parse_address(words[1], &code))
	{
		cmd_send_text("err bad argument");
	}
	else
	{
		s2lp_command(code);
		out.length = 0U;
		cmd_put_text(&out, "ok ");
		cmd_put_hex_word(&out, s2lp_status(), 2U);
		cmd_send(&out);
	}
}

static void cmd_sdn(const char *setting, uint32_t count)
{
	if ((count != 2U) || ((strcmp(setting, "0") != 0) && (strcmp(setting, "1") != 0)))
	{
		cmd_send_text("err bad argument");
	}
	else
	{
		hal_radio_shutdown(setting[0] == '1');
		if (setting[0] == '0')
		{
			hal_delay_us(2000U);
		}
		cmd_send_text("ok");
	}
}

static void cmd_counters(cmd_out_t *out)
{
	cmd_put_text(out, "frames=");
	cmd_put_decimal(out, rx_frames());
	cmd_put_text(out, " rejects=");
	cmd_put_decimal(out, rx_rejects());
	cmd_put_text(out, " overflows=");
	cmd_put_decimal(out, ring_overflows());
	cmd_put_text(out, " deaf_max_us=");
	cmd_put_decimal(out, rx_deaf_max_us());
}

/**
 * @brief Parse "aa,bb,..." into register addresses.
 */
static bool cmd_parse_address_list(char *text, uint8_t *addresses, uint32_t *count)
{
	bool valid = true;
	uint32_t found = 0U;
	char *start = text;
	char *cursor = text;
	bool last = false;

	while (valid && !last)
	{
		if ((*cursor == ',') || (*cursor == '\0'))
		{
			last = (*cursor == '\0');
			*cursor = '\0';
			if (found >= PROTO_MAX_REGISTERS)
			{
				valid = false;
			}
			else
			{
				valid = cmd_parse_address(start, &addresses[found]);
				found++;
			}
			start = &cursor[1];
		}
		cursor++;
	}
	if (valid)
	{
		*count = found;
	}
	return valid;
}

static void cmd_rx(char *words[], uint32_t count)
{
	cmd_out_t out;
	uint8_t addresses[PROTO_MAX_REGISTERS];
	uint32_t address_count = 0U;

	if ((count >= 2U) && (strcmp(words[1], "start") == 0) && (count <= 3U))
	{
		if ((count == 3U) && !cmd_parse_address_list(words[2], addresses, &address_count))
		{
			cmd_send_text("err bad argument");
		}
		else if (rx_start(addresses, address_count))
		{
			cmd_send_text("ok");
		}
		else
		{
			cmd_send_text("err bad argument");
		}
	}
	else if ((count == 2U) && (strcmp(words[1], "stop") == 0))
	{
		rx_stop();
		cmd_send_queued();
		out.length = 0U;
		cmd_put_text(&out, "ok ");
		cmd_counters(&out);
		cmd_send(&out);
	}
	else
	{
		cmd_send_text("err bad argument");
	}
}

static void cmd_stat(void)
{
	cmd_out_t out;

	out.length = 0U;
	cmd_put_text(&out, "ok running=");
	cmd_put_decimal(&out, rx_running() ? 1U : 0U);
	cmd_put_text(&out, " ");
	cmd_counters(&out);
	cmd_put_text(&out, " queued=");
	cmd_put_decimal(&out, ring_count());
	cmd_put_text(&out, " uart_overruns=");
	cmd_put_decimal(&out, hal_uart_overruns());
	cmd_send(&out);
}

void cmd_line_too_long(void)
{
	cmd_send_text("err line too long");
}

void cmd_send_queued(void)
{
	char line[CMD_OUT_MAX];
	const ring_record_t *record = ring_peek();

	while (record != NULL)
	{
		uint32_t length = cmd_format_record(record, line);

		ring_release();
		hal_uart_write(line, length);
		record = ring_peek();
	}
}

void cmd_handle_line(char *line)
{
	char *words[CMD_MAX_WORDS] = {NULL, NULL, NULL, NULL};
	uint32_t count = cmd_split(line, words);

	if (count == 0U)
	{
		/* An empty line answers nothing. */
	}
	else if (count > CMD_MAX_WORDS)
	{
		cmd_send_text("err bad argument");
	}
	else if (strcmp(words[0], "id") == 0)
	{
		cmd_id();
	}
	else if (strcmp(words[0], "stat") == 0)
	{
		cmd_stat();
	}
	else if (strcmp(words[0], "rx") == 0)
	{
		cmd_rx(words, count);
	}
	else if ((strcmp(words[0], "rd") != 0) && (strcmp(words[0], "wr") != 0)
		&& (strcmp(words[0], "cmd") != 0) && (strcmp(words[0], "sdn") != 0))
	{
		cmd_send_text("err unknown command");
	}
	else if (rx_running())
	{
		cmd_send_text("err receiving");
	}
	else if (strcmp(words[0], "rd") == 0)
	{
		cmd_rd(words, count);
	}
	else if (strcmp(words[0], "wr") == 0)
	{
		cmd_wr(words, count);
	}
	else if (strcmp(words[0], "cmd") == 0)
	{
		cmd_cmd(words, count);
	}
	else
	{
		cmd_sdn(words[1], count);
	}
}

uint32_t cmd_format_record(const ring_record_t *record, char *out)
{
	cmd_out_t line;

	line.length = 0U;
	line.text[0] = (char)record->kind;
	line.text[1] = ' ';
	line.length = 2U;
	cmd_put_decimal(&line, record->seq);
	cmd_put_text(&line, " ");
	cmd_put_decimal(&line, record->time_us);
	cmd_put_text(&line, " ");
	if (record->kind == (uint8_t)PROTO_KIND_FRAME)
	{
		cmd_put_decimal(&line, record->length);
		cmd_put_text(&line, " ");
		if (record->register_count == 0U)
		{
			cmd_put_text(&line, "-");
		}
		cmd_put_hex(&line, record->registers, record->register_count);
		cmd_put_text(&line, " ");
		cmd_put_hex(&line, record->payload, record->length);
	}
	else
	{
		cmd_put_hex_word(&line, record->irq, 4U);
	}
	line.text[line.length] = '\r';
	line.text[line.length + 1U] = '\n';
	line.length += 2U;
	(void)memcpy(out, line.text, line.length);
	return line.length;
}
