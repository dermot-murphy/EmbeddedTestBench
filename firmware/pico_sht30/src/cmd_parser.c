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
#include "fgen.h"
#include "firmware_version.h"
#include "hal.h"
#include "sht30.h"
#include "text.h"

/** The value an @c rd reply carries when there is no value to give: an
 *  unknown option, or a temperature that could not be measured. */
#define CMD_PARSER_RD_ERROR		"Error"

/** The @c rd option that is measured rather than looked up. */
#define CMD_PARSER_RD_TEMPERATURE	"temperature"

/** How much a @c k suffix multiplies a frequency by. */
#define CMD_PARSER_KILO			1000ULL

/** Values on the host link have up to three decimal places. */
#define CMD_PARSER_MILLI_DIGITS		3U
#define CMD_PARSER_DECIMAL		10ULL

/** Longest line of a generator reply's channel argument: the omitted channel. */
#define CMD_PARSER_DEFAULT_CHANNEL	"1"

/** Argument count of a command that names its channel. */
#define CMD_PARSER_WR_WITH_CHANNEL	3U
#define CMD_PARSER_RD_WITH_CHANNEL	2U
#define CMD_PARSER_ROUTINE_WITH_CHANNEL	3U

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
static proto_error_t cmd_wr(uint32_t argc, char *argv[], text_t *reply);
static proto_error_t cmd_routine(uint32_t argc, char *argv[], text_t *reply);
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

#define CMD_PARSER_RD_FIELD_COUNT	((uint32_t)(sizeof(cmd_rd_fields) / sizeof(cmd_rd_fields[0])))

/** How a generator setting is written on the host link. */
typedef enum
{
	CMD_VALUE_FREQ = 0,	/**< Hz to 3 places, k suffix; shown to 2 places. */
	CMD_VALUE_DECIMAL,	/**< A decimal to 3 places; shown to 2 places. */
	CMD_VALUE_COUNT,	/**< An unsigned integer. */
	CMD_VALUE_WAVE		/**< A waveform name. */
} cmd_value_t;

typedef struct
{
	const char	*option;
	fgen_param_t	param;
	cmd_value_t	kind;
} cmd_fgen_field_t;

static const cmd_fgen_field_t	cmd_fgen_fields[] =
{
	{ "freq",	FGEN_PARAM_FREQ,	CMD_VALUE_FREQ },
	{ "freq2",	FGEN_PARAM_FREQ2,	CMD_VALUE_FREQ },
	{ "wave",	FGEN_PARAM_WAVE,	CMD_VALUE_WAVE },
	{ "duty",	FGEN_PARAM_DUTY,	CMD_VALUE_DECIMAL },
	{ "amp",	FGEN_PARAM_AMP,		CMD_VALUE_DECIMAL },
	{ "ratio",	FGEN_PARAM_RATIO,	CMD_VALUE_DECIMAL },
	{ "cycles",	FGEN_PARAM_CYCLES,	CMD_VALUE_COUNT }
};

#define CMD_PARSER_FGEN_FIELD_COUNT	((uint32_t)(sizeof(cmd_fgen_fields) / sizeof(cmd_fgen_fields[0])))

/** Names in fgen_wave_t order. */
static const char * const	cmd_wave_names[] =
{
	"square", "sine", "triangle", "sawtooth", "sine2"
};

#define CMD_PARSER_WAVE_COUNT		((uint32_t)(sizeof(cmd_wave_names) / sizeof(cmd_wave_names[0])))

/** Routine status names, in fgen_state_t order. */
static const char * const	cmd_state_names[] =
{
	"Not Started", "Running", "Aborted", "Complete"
};

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

	cmd_rd_begin(reply, "ACK", CMD_PARSER_RD_TEMPERATURE);
	if (sht30_measure((uint8_t)BOARD_SHT30_ADDRESS, &reading) == SHT30_STATUS_OK)
	{
		text_centi(reply, reading.temperature_mc);
	}
	else
	{
		text_str(reply, CMD_PARSER_RD_ERROR);
	}
}

/* The generator setting named @p option, or NULL. */
static const cmd_fgen_field_t *cmd_fgen_lookup(const char *option)
{
	const cmd_fgen_field_t	*field = NULL;
	uint32_t		index;

	for (index = 0U; (index < CMD_PARSER_FGEN_FIELD_COUNT) && (field == NULL); index++)
	{
		if (strcmp(option, cmd_fgen_fields[index].option) == 0)
		{
			field = &cmd_fgen_fields[index];
		}
	}
	return field;
}

/* Parse a channel number, one digit. Returns 0 for anything else, which is
 * not a channel. */
static uint32_t cmd_parse_channel(const char *text)
{
	uint32_t	channel = 0U;

	if ((text[0] >= '0') && (text[0] <= '9') && (text[1] == '\0'))
	{
		channel = (uint32_t)text[0] - (uint32_t)'0';
	}
	return channel;
}

/* Parse an unsigned integer; false for anything else or for an overflow. */
static bool cmd_parse_count(const char *text, uint32_t *value)
{
	const char	*cursor = text;
	uint64_t	total = 0ULL;
	bool		valid = (*cursor != '\0');

	while (valid && (*cursor != '\0'))
	{
		valid = (*cursor >= '0') && (*cursor <= '9');
		if (valid)
		{
			total = (total * CMD_PARSER_DECIMAL) + ((uint64_t)*cursor - (uint64_t)'0');
			valid = (total <= UINT32_MAX);
		}
		cursor++;
	}
	*value = (uint32_t)total;
	return valid;
}

/* Parse a decimal with up to three places into thousandths. With @p allow_kilo
 * a trailing k or K multiplies it by 1000, so "20k" and "1.5k" are frequencies.
 * Exact integer arithmetic; false for anything else or for an overflow. */
static bool cmd_parse_milli(const char *text, bool allow_kilo, uint32_t *value)
{
	const char	*cursor = text;
	uint64_t	total = 0ULL;
	uint32_t	places = 0U;
	uint32_t	digits = 0U;
	bool		in_fraction = false;
	bool		valid = true;

	while (valid && (*cursor != '\0') && (*cursor != 'k') && (*cursor != 'K'))
	{
		if ((*cursor == '.') && !in_fraction)
		{
			in_fraction = true;
		}
		else if ((*cursor >= '0') && (*cursor <= '9'))
		{
			total = (total * CMD_PARSER_DECIMAL) + ((uint64_t)*cursor - (uint64_t)'0');
			digits++;
			places += in_fraction ? 1U : 0U;
			valid = (places <= CMD_PARSER_MILLI_DIGITS) && (total <= UINT32_MAX);
		}
		else
		{
			valid = false;
		}
		cursor++;
	}

	if (valid && (*cursor != '\0'))
	{
		valid = allow_kilo && (cursor[1] == '\0');
		total *= CMD_PARSER_KILO;
	}
	valid = valid && (digits > 0U);
	while (valid && (places < CMD_PARSER_MILLI_DIGITS))
	{
		total *= CMD_PARSER_DECIMAL;
		places++;
	}
	valid = valid && (total <= UINT32_MAX);
	*value = (uint32_t)total;
	return valid;
}

/* The fgen_wave_t named @p text; false if it names none. */
static bool cmd_parse_wave(const char *text, uint32_t *value)
{
	uint32_t	index;
	bool		found = false;

	for (index = 0U; (index < CMD_PARSER_WAVE_COUNT) && !found; index++)
	{
		if (strcmp(text, cmd_wave_names[index]) == 0)
		{
			*value = index;
			found = true;
		}
	}
	return found;
}

static bool cmd_parse_value(const cmd_fgen_field_t *field, const char *text, uint32_t *value)
{
	bool	valid;

	switch (field->kind)
	{
	case CMD_VALUE_FREQ:
		valid = cmd_parse_milli(text, true, value);
		break;
	case CMD_VALUE_DECIMAL:
		valid = cmd_parse_milli(text, false, value);
		break;
	case CMD_VALUE_COUNT:
		valid = cmd_parse_count(text, value);
		break;
	case CMD_VALUE_WAVE:
	default:
		valid = cmd_parse_wave(text, value);
		break;
	}
	return valid;
}

/* A setting as the host reads it. Thousandths are shown to two places. */
static void cmd_show_value(text_t *reply, const cmd_fgen_field_t *field, uint32_t value)
{
	if (field->kind == CMD_VALUE_WAVE)
	{
		text_str(reply, cmd_wave_names[value]);
	}
	else if (field->kind == CMD_VALUE_COUNT)
	{
		text_u32(reply, value);
	}
	else
	{
		text_centi(reply, (int32_t)value);
	}
}

/* "<ACK|NAK> <verb> <option> <channel> = ", the channel echoed as given. */
static void cmd_fgen_begin(text_t *reply, const char *verdict, const char *verb,
			   const char *option, const char *channel)
{
	text_str(reply, verdict);
	text_char(reply, ' ');
	text_str(reply, verb);
	text_char(reply, ' ');
	text_str(reply, option);
	text_char(reply, ' ');
	text_str(reply, channel);
	text_str(reply, " = ");
}

/* rd <setting> [<channel>]. */
static void cmd_rd_setting(const cmd_fgen_field_t *field, const char *channel_text,
			   text_t *reply)
{
	uint32_t	channel = cmd_parse_channel(channel_text);

	if (fgen_channel_valid(channel))
	{
		cmd_fgen_begin(reply, "ACK", "rd", field->option, channel_text);
		cmd_show_value(reply, field, fgen_read(channel, field->param));
	}
	else
	{
		cmd_fgen_begin(reply, "NAK", "rd", field->option, channel_text);
		text_str(reply, CMD_PARSER_RD_ERROR);
	}
}

/* wr <setting> [<channel>] <value>. Parsing and range checks both end in the
 * same NAK; nothing is stored unless all of it is good. */
static proto_error_t cmd_wr(uint32_t argc, char *argv[], text_t *reply)
{
	const cmd_fgen_field_t	*field = cmd_fgen_lookup(argv[0]);
	bool			named = (argc == CMD_PARSER_WR_WITH_CHANNEL);
	const char		*channel_text = named ? argv[1] : CMD_PARSER_DEFAULT_CHANNEL;
	const char		*value_text = named ? argv[2] : argv[1];
	uint32_t		channel = cmd_parse_channel(channel_text);
	uint32_t		value = 0U;

	if (field == NULL)
	{
		text_str(reply, "NAK wr ");
		text_str(reply, argv[0]);
		text_str(reply, " = ");
		text_str(reply, CMD_PARSER_RD_ERROR);
	}
	else if (cmd_parse_value(field, value_text, &value) &&
		 fgen_write(channel, field->param, value))
	{
		cmd_fgen_begin(reply, "ACK", "wr", field->option, channel_text);
		cmd_show_value(reply, field, value);
	}
	else
	{
		cmd_fgen_begin(reply, "NAK", "wr", field->option, channel_text);
		text_str(reply, CMD_PARSER_RD_ERROR);
	}
	return PROTO_ERR_NONE;
}

/* One channel's results: status, then waveform and frequency once it has run. */
static void cmd_results_line(text_t *reply, uint32_t channel)
{
	fgen_state_t	state = fgen_state(channel);

	text_str(reply, "ACK routine freq results ");
	text_u32(reply, channel);
	text_str(reply, " = ");
	text_str(reply, cmd_state_names[(uint32_t)state]);
	if (state != FGEN_STATE_NOT_STARTED)
	{
		text_str(reply, ", ");
		text_str(reply, cmd_wave_names[(uint32_t)fgen_actual_wave(channel)]);
		text_str(reply, ", ");
		text_centi(reply, (int32_t)fgen_actual_mhz(channel));
		text_str(reply, " Hz");
	}
}

/* routine freq results with no channel: one line per channel, the last of them
 * as the command's reply. */
static void cmd_results_all(text_t *reply)
{
	uint32_t	channel;

	for (channel = 1U; channel < FGEN_CHANNEL_COUNT; channel++)
	{
		char	buffer[PROTO_MAX_REPLY];
		text_t	line;

		text_init(&line, buffer, PROTO_MAX_REPLY);
		cmd_results_line(&line, channel);
		hal_write_line(buffer);
	}
	cmd_results_line(reply, FGEN_CHANNEL_COUNT);
}

/* "<ACK|NAK> routine <a> <b>[ <c>] = <value>", the tokens echoed as received. */
static void cmd_routine_reply(text_t *reply, const char *verdict, uint32_t argc, char *argv[],
			      const char *value)
{
	uint32_t	index;

	text_str(reply, verdict);
	text_str(reply, " routine");
	for (index = 0U; index < argc; index++)
	{
		text_char(reply, ' ');
		text_str(reply, argv[index]);
	}
	text_str(reply, " = ");
	text_str(reply, value);
}

/* routine freq start [<channel>]; a command with no channel means channel 1. */
static void cmd_routine_start(uint32_t argc, char *argv[], text_t *reply)
{
	bool		named = (argc == CMD_PARSER_ROUTINE_WITH_CHANNEL);
	const char	*channel_text = named ? argv[2] : CMD_PARSER_DEFAULT_CHANNEL;

	if (fgen_start(cmd_parse_channel(channel_text)))
	{
		cmd_fgen_begin(reply, "ACK", "routine freq", "start", channel_text);
		text_str(reply, cmd_state_names[(uint32_t)FGEN_STATE_RUNNING]);
	}
	else
	{
		cmd_fgen_begin(reply, "NAK", "routine freq", "start", channel_text);
		text_str(reply, CMD_PARSER_RD_ERROR);
	}
}

/* routine freq abort [<channel>]; with no channel, every channel. */
static void cmd_routine_abort(uint32_t argc, char *argv[], text_t *reply)
{
	bool		named = (argc == CMD_PARSER_ROUTINE_WITH_CHANNEL);
	uint32_t	channel = named ? cmd_parse_channel(argv[2]) : 0U;

	if (!named)
	{
		fgen_abort_all();
		cmd_routine_reply(reply, "ACK", argc, argv, cmd_state_names[(uint32_t)FGEN_STATE_ABORTED]);
	}
	else if (fgen_channel_valid(channel))
	{
		fgen_abort(channel);
		cmd_routine_reply(reply, "ACK", argc, argv, cmd_state_names[(uint32_t)FGEN_STATE_ABORTED]);
	}
	else
	{
		cmd_routine_reply(reply, "NAK", argc, argv, CMD_PARSER_RD_ERROR);
	}
}

/* routine freq results [<channel>]; with no channel, every channel. */
static void cmd_routine_results(uint32_t argc, char *argv[], text_t *reply)
{
	bool		named = (argc == CMD_PARSER_ROUTINE_WITH_CHANNEL);
	uint32_t	channel = named ? cmd_parse_channel(argv[2]) : 0U;

	if (!named)
	{
		cmd_results_all(reply);
	}
	else if (fgen_channel_valid(channel))
	{
		cmd_results_line(reply, channel);
	}
	else
	{
		cmd_routine_reply(reply, "NAK", argc, argv, CMD_PARSER_RD_ERROR);
	}
}

/* routine <routine> <verb> [<channel>]. */
static proto_error_t cmd_routine(uint32_t argc, char *argv[], text_t *reply)
{
	bool	is_freq = (strcmp(argv[0], "freq") == 0);

	if (is_freq && (strcmp(argv[1], "start") == 0))
	{
		cmd_routine_start(argc, argv, reply);
	}
	else if (is_freq && (strcmp(argv[1], "abort") == 0))
	{
		cmd_routine_abort(argc, argv, reply);
	}
	else if (is_freq && (strcmp(argv[1], "results") == 0))
	{
		cmd_routine_results(argc, argv, reply);
	}
	else if ((argc == 2U) && (strcmp(argv[0], "all") == 0) && (strcmp(argv[1], "abort") == 0))
	{
		fgen_abort_all();
		cmd_routine_reply(reply, "ACK", argc, argv, cmd_state_names[(uint32_t)FGEN_STATE_ABORTED]);
	}
	else
	{
		cmd_routine_reply(reply, "NAK", argc, argv, CMD_PARSER_RD_ERROR);
	}
	return PROTO_ERR_NONE;
}

/* rd of an identity value or the temperature: one token only. */
static void cmd_rd_plain(const char *option, text_t *reply)
{
	const char	*value = NULL;
	uint32_t	index;

	for (index = 0U; (index < CMD_PARSER_RD_FIELD_COUNT) && (value == NULL); index++)
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
	else if (strcmp(option, CMD_PARSER_RD_TEMPERATURE) == 0)
	{
		cmd_rd_temperature(reply);
	}
	else
	{
		cmd_rd_begin(reply, "NAK", option);
		text_str(reply, CMD_PARSER_RD_ERROR);
	}
}

/* rd <option> [<channel>]. The option is matched exactly, case included. The
 * identity options never touch the sensor, so a Pico with no sensor still says
 * what it is (PICO-FR-005, PICO-FR-006). An unknown option is answered with a
 * NAK that echoes it as received (PICO-FR-007). Only a generator setting takes
 * a channel. */
static proto_error_t cmd_rd(uint32_t argc, char *argv[], text_t *reply)
{
	const cmd_fgen_field_t	*field = cmd_fgen_lookup(argv[0]);
	bool			named = (argc == CMD_PARSER_RD_WITH_CHANNEL);
	proto_error_t		result = PROTO_ERR_NONE;

	if (field != NULL)
	{
		cmd_rd_setting(field, named ? argv[1] : CMD_PARSER_DEFAULT_CHANNEL, reply);
	}
	else if (named)
	{
		result = PROTO_ERR_ARGS;
	}
	else
	{
		cmd_rd_plain(argv[0], reply);
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
