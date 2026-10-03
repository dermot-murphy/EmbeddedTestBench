/**
 * @file cmd_parser.c
 * @brief Line assembly and command dispatch. See cmd_parser.h.
 *
 * Traces to: PICO-FR-001, PICO-FR-003, PICO-FR-004, PICO-FR-005,
 *            PICO-FR-006, PICO-FR-007, PICO-FR-020, PICO-FR-024,
 *            PICO-FR-027, PICO-FR-030, PICO-DD-PARSER.
 */

#include "cmd_parser.h"

#include <stddef.h>
#include <string.h>

#include "board_config.h"
#include "firmware_version.h"
#include "hal.h"
#include "sht30.h"
#include "text.h"

/** The value an @c rd reply carries when there is no value to give: an
 *  unknown option, or a temperature that could not be measured. */
#define CMD_RD_ERROR		"Error"

/** The @c rd option that is measured rather than looked up. */
#define CMD_RD_TEMPERATURE	"temperature"

/** What to do once the reply has been sent. A reboot must follow the reply,
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

/* Handler prototypes, one per row of PROTO_COMMAND_TABLE. Written out rather
 * than generated: a macro ending in ';' is CERT PRE11-C. A row with no handler
 * still fails to build, because the table below takes each one's address. */
static proto_error_t cmd_help(uint32_t argc, char *argv[], text_t *reply);
static proto_error_t cmd_rd(uint32_t argc, char *argv[], text_t *reply);
static proto_error_t cmd_status(uint32_t argc, char *argv[], text_t *reply);
static proto_error_t cmd_sreset(uint32_t argc, char *argv[], text_t *reply);
static proto_error_t cmd_ecureset(uint32_t argc, char *argv[], text_t *reply);
static proto_error_t cmd_bootsel(uint32_t argc, char *argv[], text_t *reply);

static const cmd_entry_t	cmd_table[] =
{
#define X(name, min_args, max_args, help) \
	{ #name, (uint32_t)(min_args), (uint32_t)(max_args), (help), &cmd_##name },
	PROTO_COMMAND_TABLE
#undef X
};

#define CMD_PARSER_TABLE_LENGTH	((uint32_t)(sizeof(cmd_table) / sizeof(cmd_table[0])))

/** An @c rd option whose value is a fixed string. The temperature is not in
 *  this table: it is measured, so it is handled on its own. */
typedef struct
{
	const char	*option;
	const char	*value;
} cmd_rd_field_t;

static const cmd_rd_field_t	cmd_rd_fields[] =
{
	{ "name",	firmware_g_name },
	{ "copyright",	firmware_g_copyright },
	{ "version",	firmware_g_version },
	{ "sha",	firmware_g_sha }
};

#define CMD_RD_FIELD_COUNT	((uint32_t)(sizeof(cmd_rd_fields) / sizeof(cmd_rd_fields[0])))

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
	case SHT30_STATUS_OK:
		result = PROTO_ERR_NONE;
		break;
	case SHT30_STATUS_ERR_CRC:
		result = PROTO_ERR_CRC;
		break;
	case SHT30_STATUS_ERR_TIMEOUT:
		result = PROTO_ERR_BUS;
		break;
	case SHT30_STATUS_ERR_NACK:
	case SHT30_STATUS_ERR_PARAM:
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
/* Handlers. Each writes its whole reply line - "ok ...", or for rd "ACK ..."
 * or "NAK ..." - to the empty @p reply, and returns PROTO_ERR_NONE, or the
 * error to send instead. On an error, whatever was written is discarded. */

static proto_error_t cmd_help(uint32_t argc, char *argv[], text_t *reply)
{
	uint32_t	index;

	(void)argc;
	(void)argv;
	for (index = 0U; index < CMD_PARSER_TABLE_LENGTH; index++)
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
	text_str(reply, "ok");
	return PROTO_ERR_NONE;
}

/* "<ACK|NAK> rd <option> = " - the part every rd reply shares. */
static void cmd_rd_begin(text_t *reply, const char *verdict, const char *option)
{
	text_str(reply, verdict);
	text_str(reply, " rd ");
	text_str(reply, option);
	text_str(reply, " = ");
}

/* rd temperature: one measurement, in degrees Celsius to two places. Any
 * failure - no acknowledge, a bad checksum, a bus timeout - is reported as
 * the value "Error" in an ACK, not as an err reply: the command was
 * understood, and the reading is what failed (PICO-FR-027). */
static void cmd_rd_temperature(text_t *reply)
{
	sht30_reading_t	reading;

	cmd_rd_begin(reply, "ACK", CMD_RD_TEMPERATURE);
	if (sht30_measure((uint8_t)BOARD_SHT30_ADDRESS, &reading) == SHT30_STATUS_OK)
	{
		text_centi(reply, reading.temperature_mc);
	}
	else
	{
		text_str(reply, CMD_RD_ERROR);
	}
}

/* rd <option>. The option is matched exactly, case included. The identity
 * options never touch the sensor, so a Pico with no sensor still says what it
 * is (PICO-FR-005, PICO-FR-006). An unknown option is answered with a NAK
 * that echoes it as received (PICO-FR-007). */
static proto_error_t cmd_rd(uint32_t argc, char *argv[], text_t *reply)
{
	const char	*option = argv[0];
	const char	*value = NULL;
	uint32_t	index;

	(void)argc;
	for (index = 0U; (index < CMD_RD_FIELD_COUNT) && (value == NULL); index++)
	{
		if (strcmp(option, cmd_rd_fields[index].option) == 0)
		{
			value = cmd_rd_fields[index].value;
		}
	}

	if (value != NULL)
	{
		cmd_rd_begin(reply, "ACK", option);
		text_str(reply, value);
	}
	else if (strcmp(option, CMD_RD_TEMPERATURE) == 0)
	{
		cmd_rd_temperature(reply);
	}
	else
	{
		cmd_rd_begin(reply, "NAK", option);
		text_str(reply, CMD_RD_ERROR);
	}
	return PROTO_ERR_NONE;
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
		text_str(reply, "ok status=");
		text_hex16(reply, status);
	}
	return result;
}

static proto_error_t cmd_sreset(uint32_t argc, char *argv[], text_t *reply)
{
	proto_error_t	result;

	(void)argc;
	(void)argv;
	result = cmd_from_sht30(sht30_soft_reset((uint8_t)BOARD_SHT30_ADDRESS));
	if (result == PROTO_ERR_NONE)
	{
		text_str(reply, "ok");
	}
	return result;
}

static proto_error_t cmd_ecureset(uint32_t argc, char *argv[], text_t *reply)
{
	(void)argc;
	(void)argv;
	text_str(reply, "ok");
	cmd_after = CMD_AFTER_REBOOT;
	return PROTO_ERR_NONE;
}

static proto_error_t cmd_bootsel(uint32_t argc, char *argv[], text_t *reply)
{
	(void)argc;
	(void)argv;
	text_str(reply, "ok");
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
	cmd_line_result_t	result = CMD_LINE_RESULT_PENDING;

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
			result = CMD_LINE_RESULT_OVERFLOW;
			line->text[0] = '\0';
		}
		else
		{
			result = CMD_LINE_RESULT_READY;
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

/* The table entry named @p name, or NULL. */
static const cmd_entry_t *cmd_lookup(const char *name)
{
	const cmd_entry_t	*entry = NULL;
	uint32_t		index;

	for (index = 0U; (index < CMD_PARSER_TABLE_LENGTH) && (entry == NULL); index++)
	{
		if (strcmp(name, cmd_table[index].name) == 0)
		{
			entry = &cmd_table[index];
		}
	}
	return entry;
}

/* Check the argument count and run the handler for @p entry, which may be
 * NULL for an unknown command. The handler writes to @p reply. */
static proto_error_t cmd_run(const cmd_entry_t *entry, uint32_t count, char *tokens[],
			     text_t *reply)
{
	proto_error_t	result;

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
		result = entry->handler(count - 1U, &tokens[1], reply);
	}

	if ((result == PROTO_ERR_NONE) && reply->overflow)
	{
		/* Sized so that this cannot happen (unit tested); if it ever does,
		 * a truncated reply must not reach the host as a valid one. */
		result = PROTO_ERR_TOO_LONG;
	}
	return result;
}

/* Send the reply, then carry out any reboot the command asked for: the host
 * must see the reply before the link goes away. */
static void cmd_finish(proto_error_t result, const char *reply_text)
{
	if (result == PROTO_ERR_NONE)
	{
		hal_write_line(reply_text);
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

void cmd_execute(char *line)
{
	char		*tokens[PROTO_MAX_TOKENS] = { NULL };
	char		buffer[PROTO_MAX_REPLY];
	text_t		reply;
	uint32_t	count = 0U;

	if (line != NULL)
	{
		count = cmd_tokenise(line, tokens);
	}
	if (count > 0U)
	{
		cmd_after = CMD_AFTER_NOTHING;
		text_init(&reply, buffer, PROTO_MAX_REPLY);
		cmd_finish(cmd_run(cmd_lookup(tokens[0]), count, tokens, &reply), buffer);
	}
}

void cmd_report_overflow(void)
{
	cmd_send_error(PROTO_ERR_TOO_LONG);
}
