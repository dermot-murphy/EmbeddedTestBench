/**
 * @file cmd_parser.c
 * @brief Line assembly and command dispatch. See cmd_parser.h.
 *
 * Traces to: PICO-FR-001 .. PICO-FR-005, PICO-FR-020, PICO-FR-024,
 *            PICO-FR-030, PICO-DD-PARSER.
 */

#include "cmd_parser.h"

#include <stddef.h>
#include <string.h>

#include "board_config.h"
#include "firmware_version.h"
#include "hal.h"
#include "sht30.h"
#include "text.h"

/** What to do once the reply has been sent. A reboot must follow the "ok",
 *  or the host never learns that the command was accepted. */
typedef enum
{
	CMD_AFTER_NOTHING = 0,
	CMD_AFTER_REBOOT,
	CMD_AFTER_BOOTLOADER
} cmd_after_t;

typedef proto_error_t (*cmd_handler_t)(uint32_t argc, char *argv[], text_t *reply);

typedef struct
{
	const char	*name;
	uint32_t	min_args;
	uint32_t	max_args;
	const char	*help;
	cmd_handler_t	handler;
} cmd_entry_t;

/* Handler prototypes, one per row of the command table. */
#define X(name, min_args, max_args, help) \
	static proto_error_t cmd_##name(uint32_t argc, char *argv[], text_t *reply);
PROTO_COMMAND_TABLE
#undef X

static const cmd_entry_t	cmd_table[] =
{
#define X(name, min_args, max_args, help) \
	{ #name, (uint32_t)(min_args), (uint32_t)(max_args), (help), &cmd_##name },
	PROTO_COMMAND_TABLE
#undef X
};

#define CMD_TABLE_LENGTH	((uint32_t)(sizeof(cmd_table) / sizeof(cmd_table[0])))

#define X(symbol, code, text)	(text),
static const char * const	cmd_error_text[] =
{
	PROTO_ERROR_TABLE
};
#undef X

static cmd_after_t	cmd_after = CMD_AFTER_NOTHING;

/* ------------------------------------------------------------------------ */
const char *proto_error_text(proto_error_t error)
{
	const char	*result = "unknown error";

	if ((uint32_t)error < (uint32_t)PROTO_ERR_LIMIT)
	{
		result = cmd_error_text[(uint32_t)error];
	}
	return result;
}

static proto_error_t cmd_from_sht30(sht30_status_t status)
{
	proto_error_t	result;

	switch (status)
	{
	case SHT30_OK:
		result = PROTO_ERR_NONE;
		break;
	case SHT30_ERR_CRC:
		result = PROTO_ERR_CRC;
		break;
	case SHT30_ERR_TIMEOUT:
		result = PROTO_ERR_BUS;
		break;
	case SHT30_ERR_NACK:
	case SHT30_ERR_PARAM:
	default:
		result = PROTO_ERR_NO_SENSOR;
		break;
	}
	return result;
}

static void cmd_send_error(proto_error_t error)
{
	char	buffer[PROTO_MAX_REPLY];
	text_t	reply;

	text_init(&reply, buffer, PROTO_MAX_REPLY);
	text_str(&reply, "err ");
	text_u32(&reply, (uint32_t)error);
	text_char(&reply, ' ');
	text_str(&reply, proto_error_text(error));
	hal_write_line(buffer);
}

/* ------------------------------------------------------------------------ */
/* Handlers. Each appends its reply body - without the leading "ok" - to
 * @p reply, and returns PROTO_ERR_NONE or the error to send instead. */

static proto_error_t cmd_help(uint32_t argc, char *argv[], text_t *reply)
{
	uint32_t	index;

	(void)argc;
	(void)argv;
	(void)reply;
	for (index = 0U; index < CMD_TABLE_LENGTH; index++)
	{
		char	buffer[PROTO_MAX_REPLY];
		text_t	line;

		text_init(&line, buffer, PROTO_MAX_REPLY);
		text_str(&line, "# ");
		text_str(&line, cmd_table[index].name);
		text_str(&line, " - ");
		text_str(&line, cmd_table[index].help);
		hal_write_line(buffer);
	}
	return PROTO_ERR_NONE;
}

static proto_error_t cmd_ver(uint32_t argc, char *argv[], text_t *reply)
{
	(void)argc;
	(void)argv;
	text_str(reply, " title=");
	text_token(reply, firmware_title_string);
	text_str(reply, " fw=");
	text_token(reply, firmware_version_string);
	text_str(reply, " built=");
	text_token(reply, firmware_build_date_string);
	text_str(reply, " proto=");
	text_str(reply, PROTO_VERSION);
	text_str(reply, " board=");
	text_str(reply, BOARD_NAME);
	text_str(reply, " serial=");
	text_token(reply, hal_board_id());
	text_str(reply, " sensor=");
	text_str(reply, PROTO_SENSOR);
	text_str(reply, " addr=");
	text_hex8(reply, (uint8_t)BOARD_SHT30_ADDRESS);
	text_str(reply, " uptime_s=");
	text_u32(reply, (uint32_t)(hal_uptime_us() / 1000000ULL));
	return PROTO_ERR_NONE;
}

static proto_error_t cmd_temp(uint32_t argc, char *argv[], text_t *reply)
{
	sht30_reading_t	reading;
	proto_error_t	result;

	(void)argc;
	(void)argv;
	result = cmd_from_sht30(sht30_measure((uint8_t)BOARD_SHT30_ADDRESS, &reading));
	if (result == PROTO_ERR_NONE)
	{
		text_str(reply, " t=");
		text_milli(reply, reading.temperature_mc);
		text_str(reply, " rh=");
		text_milli(reply, reading.humidity_mpct);
		text_str(reply, " raw_t=");
		text_hex16(reply, reading.raw_temperature);
		text_str(reply, " raw_rh=");
		text_hex16(reply, reading.raw_humidity);
	}
	return result;
}

static proto_error_t cmd_status(uint32_t argc, char *argv[], text_t *reply)
{
	uint16_t	status = 0U;
	proto_error_t	result;

	(void)argc;
	(void)argv;
	result = cmd_from_sht30(sht30_read_status((uint8_t)BOARD_SHT30_ADDRESS, &status));
	if (result == PROTO_ERR_NONE)
	{
		text_str(reply, " status=");
		text_hex16(reply, status);
	}
	return result;
}

static proto_error_t cmd_sreset(uint32_t argc, char *argv[], text_t *reply)
{
	(void)argc;
	(void)argv;
	(void)reply;
	return cmd_from_sht30(sht30_soft_reset((uint8_t)BOARD_SHT30_ADDRESS));
}

static proto_error_t cmd_reset(uint32_t argc, char *argv[], text_t *reply)
{
	(void)argc;
	(void)argv;
	(void)reply;
	cmd_after = CMD_AFTER_REBOOT;
	return PROTO_ERR_NONE;
}

static proto_error_t cmd_bootsel(uint32_t argc, char *argv[], text_t *reply)
{
	(void)argc;
	(void)argv;
	(void)reply;
	cmd_after = CMD_AFTER_BOOTLOADER;
	return PROTO_ERR_NONE;
}

/* ------------------------------------------------------------------------ */
void cmd_line_init(cmd_line_t *line)
{
	if (line != NULL)
	{
		line->length = 0U;
		line->discarding = false;
		line->text[0] = '\0';
	}
}

cmd_line_result_t cmd_line_push(cmd_line_t *line, char ch)
{
	cmd_line_result_t	result = CMD_LINE_PENDING;

	if (line == NULL)
	{
		/* Nothing to assemble into. */
	}
	else if (ch == '\r')
	{
		/* CRLF and LF both end a line: the CR is dropped. */
	}
	else if (ch == '\n')
	{
		if (line->discarding)
		{
			result = CMD_LINE_OVERFLOW;
			line->text[0] = '\0';
		}
		else
		{
			result = CMD_LINE_READY;
			line->text[line->length] = '\0';
		}
		line->length = 0U;
		line->discarding = false;
	}
	else if (line->discarding)
	{
		/* Dropping the rest of an over-length line. */
	}
	else if ((line->length + 1U) < PROTO_MAX_LINE)
	{
		line->text[line->length] = ch;
		line->length++;
	}
	else
	{
		line->discarding = true;
	}
	return result;
}

/* Split @p line in place on spaces and tabs. Returns the token count; tokens
 * beyond PROTO_MAX_TOKENS are counted but not stored, so that an over-long
 * command is refused on its argument count rather than silently truncated. */
static uint32_t cmd_tokenise(char *line, char *tokens[])
{
	uint32_t	count = 0U;
	char		*cursor = line;
	bool		in_token = false;

	while (*cursor != '\0')
	{
		if ((*cursor == ' ') || (*cursor == '\t'))
		{
			*cursor = '\0';
			in_token = false;
		}
		else if (!in_token)
		{
			if (count < PROTO_MAX_TOKENS)
			{
				tokens[count] = cursor;
			}
			count++;
			in_token = true;
		}
		else
		{
			/* Inside a token. */
		}
		cursor++;
	}
	return count;
}

void cmd_execute(char *line)
{
	char		*tokens[PROTO_MAX_TOKENS] = { NULL };
	char		buffer[PROTO_MAX_REPLY];
	text_t		reply;
	uint32_t	count;
	uint32_t	index;
	const cmd_entry_t	*entry = NULL;
	proto_error_t	result = PROTO_ERR_UNKNOWN;

	if (line == NULL)
	{
		return;
	}
	count = cmd_tokenise(line, tokens);
	if (count == 0U)
	{
		return;
	}

	for (index = 0U; (index < CMD_TABLE_LENGTH) && (entry == NULL); index++)
	{
		if (strcmp(tokens[0], cmd_table[index].name) == 0)
		{
			entry = &cmd_table[index];
		}
	}

	cmd_after = CMD_AFTER_NOTHING;
	text_init(&reply, buffer, PROTO_MAX_REPLY);
	text_str(&reply, "ok");

	if (entry == NULL)
	{
		result = PROTO_ERR_UNKNOWN;
	}
	else if (((count - 1U) < entry->min_args) || ((count - 1U) > entry->max_args))
	{
		result = PROTO_ERR_ARGS;
	}
	else
	{
		result = entry->handler(count - 1U, &tokens[1], &reply);
	}

	if ((result == PROTO_ERR_NONE) && reply.overflow)
	{
		/* Sized so that this cannot happen (unit tested); if it ever does,
		 * a truncated reply must not reach the host as a valid one. */
		result = PROTO_ERR_TOO_LONG;
		cmd_after = CMD_AFTER_NOTHING;
	}

	if (result == PROTO_ERR_NONE)
	{
		hal_write_line(buffer);
		if (cmd_after == CMD_AFTER_REBOOT)
		{
			hal_reboot();
		}
		else if (cmd_after == CMD_AFTER_BOOTLOADER)
		{
			hal_reboot_to_bootloader();
		}
		else
		{
			/* Nothing further. */
		}
	}
	else
	{
		cmd_send_error(result);
	}
	cmd_after = CMD_AFTER_NOTHING;
}

void cmd_report_overflow(void)
{
	cmd_send_error(PROTO_ERR_TOO_LONG);
}
