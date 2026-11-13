/**
 * @file cmd_fgen.c
 * @brief The frequency generator's commands. See cmd_fgen.h.
 *
 * Traces to: PICO-FR-081 .. PICO-FR-084, PICO-DD-PARSER, PICO-DD-FGEN.
 */

#include "cmd_fgen.h"

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

#include "fgen.h"
#include "hal.h"
#include "protocol.h"

/** The value a NAK carries. */
#define CMD_FGEN_ERROR			"Error"

/** How much a @c k suffix multiplies a frequency by. */
#define CMD_FGEN_KILO			1000ULL

/** Values on the host link have up to three decimal places. */
#define CMD_FGEN_MILLI_DIGITS		3U
#define CMD_FGEN_DECIMAL		10ULL

/** What a reply names when the command omitted the channel. */
#define CMD_FGEN_DEFAULT_CHANNEL	"1"

/** Argument count of a command that names its channel. */
#define CMD_FGEN_WR_WITH_CHANNEL	3U
#define CMD_FGEN_RD_WITH_CHANNEL	2U
#define CMD_FGEN_ROUTINE_WITH_CHANNEL	3U

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

#define CMD_FGEN_FGEN_FIELD_COUNT	((uint32_t)(sizeof(cmd_fgen_fields) / sizeof(cmd_fgen_fields[0])))

/** Names in fgen_wave_t order. */
static const char * const	cmd_wave_names[] =
{
	"square", "sine", "triangle", "sawtooth", "sine2"
};

#define CMD_FGEN_WAVE_COUNT		((uint32_t)(sizeof(cmd_wave_names) / sizeof(cmd_wave_names[0])))

/** Routine status names, in fgen_state_t order. */
static const char * const	cmd_state_names[] =
{
	"Not Started", "Running", "Aborted", "Complete"
};

/* The generator setting named @p option, or NULL. */
static const cmd_fgen_field_t *cmd_fgen_lookup(const char *option)
{
	const cmd_fgen_field_t	*field = NULL;
	uint32_t		index;

	for (index = 0U; (index < CMD_FGEN_FGEN_FIELD_COUNT) && (field == NULL); index++)
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
			total = (total * CMD_FGEN_DECIMAL) + ((uint64_t)*cursor - (uint64_t)'0');
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
			total = (total * CMD_FGEN_DECIMAL) + ((uint64_t)*cursor - (uint64_t)'0');
			digits++;
			places += in_fraction ? 1U : 0U;
			valid = (places <= CMD_FGEN_MILLI_DIGITS) && (total <= UINT32_MAX);
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
		total *= CMD_FGEN_KILO;
	}
	valid = valid && (digits > 0U);
	while (valid && (places < CMD_FGEN_MILLI_DIGITS))
	{
		total *= CMD_FGEN_DECIMAL;
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

	for (index = 0U; (index < CMD_FGEN_WAVE_COUNT) && !found; index++)
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

bool cmd_fgen_is_setting(const char *option)
{
	return cmd_fgen_lookup(option) != NULL;
}

void cmd_fgen_rd(uint32_t argc, char *argv[], text_t *reply)
{
	const cmd_fgen_field_t	*field = cmd_fgen_lookup(argv[0]);
	const char		*channel_text = (argc == CMD_FGEN_RD_WITH_CHANNEL) ? argv[1] : CMD_FGEN_DEFAULT_CHANNEL;
	uint32_t		channel = cmd_parse_channel(channel_text);

	if (fgen_channel_valid(channel))
	{
		cmd_fgen_begin(reply, "ACK", "rd", field->option, channel_text);
		cmd_show_value(reply, field, fgen_read(channel, field->param));
	}
	else
	{
		cmd_fgen_begin(reply, "NAK", "rd", field->option, channel_text);
		text_str(reply, CMD_FGEN_ERROR);
	}
}

/* wr <setting> [<channel>] <value>. Parsing and range checks both end in the
 * same NAK; nothing is stored unless all of it is good. */
void cmd_fgen_wr(uint32_t argc, char *argv[], text_t *reply)
{
	const cmd_fgen_field_t	*field = cmd_fgen_lookup(argv[0]);
	bool			named = (argc == CMD_FGEN_WR_WITH_CHANNEL);
	const char		*channel_text = named ? argv[1] : CMD_FGEN_DEFAULT_CHANNEL;
	const char		*value_text = named ? argv[2] : argv[1];
	uint32_t		channel = cmd_parse_channel(channel_text);
	uint32_t		value = 0U;

	if (field == NULL)
	{
		text_str(reply, "NAK wr ");
		text_str(reply, argv[0]);
		text_str(reply, " = ");
		text_str(reply, CMD_FGEN_ERROR);
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
		text_str(reply, CMD_FGEN_ERROR);
	}
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
	bool		named = (argc == CMD_FGEN_ROUTINE_WITH_CHANNEL);
	const char	*channel_text = named ? argv[2] : CMD_FGEN_DEFAULT_CHANNEL;

	if (fgen_start(cmd_parse_channel(channel_text)))
	{
		cmd_fgen_begin(reply, "ACK", "routine freq", "start", channel_text);
		text_str(reply, cmd_state_names[(uint32_t)FGEN_STATE_RUNNING]);
	}
	else
	{
		cmd_fgen_begin(reply, "NAK", "routine freq", "start", channel_text);
		text_str(reply, CMD_FGEN_ERROR);
	}
}

/* routine freq abort [<channel>]; with no channel, every channel. */
static void cmd_routine_abort(uint32_t argc, char *argv[], text_t *reply)
{
	bool		named = (argc == CMD_FGEN_ROUTINE_WITH_CHANNEL);
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
		cmd_routine_reply(reply, "NAK", argc, argv, CMD_FGEN_ERROR);
	}
}

/* routine freq results [<channel>]; with no channel, every channel. */
static void cmd_routine_results(uint32_t argc, char *argv[], text_t *reply)
{
	bool		named = (argc == CMD_FGEN_ROUTINE_WITH_CHANNEL);
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
		cmd_routine_reply(reply, "NAK", argc, argv, CMD_FGEN_ERROR);
	}
}

/* routine <routine> <verb> [<channel>]. */
void cmd_fgen_routine(uint32_t argc, char *argv[], text_t *reply)
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
		cmd_routine_reply(reply, "NAK", argc, argv, CMD_FGEN_ERROR);
	}
}
