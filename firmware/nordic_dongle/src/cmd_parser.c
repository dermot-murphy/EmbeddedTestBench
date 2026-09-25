/**
 * @file cmd_parser.c
 * @brief The command dispatcher.
 *
 * Traces to: BLE-FR-002, BLE-FR-020 .. BLE-FR-044, BLE-DD-CMD.
 */

#include "cmd_parser.h"

#include <stdarg.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "app_error.h"
#include "app_util_platform.h"
#include "nrf_sdh.h"
#include "nrf_soc.h"

#include "ble_scanner.h"
#include "bootloader.h"
#include "cdc_acm.h"
#include "firmware_version.h"
#include "nus_client.h"
#include "timestamp.h"

/** Default time to wait for a sensor's reply to @c cmd. */
#define CMD_DEFAULT_TIMEOUT_MS		2000U

/** The sensor chosen by @c select, if any. */
static ble_gap_addr_t	m_selected;
static bool		m_have_selected;
static char		m_selected_name[PROTO_MAX_NAME];

const char * proto_error_text(proto_error_t error)
{
#define X(symbol, code, text)	case symbol: return text;
	switch (error)
	{
	PROTO_ERROR_TABLE
	default:
		break;
	}
#undef X

	return "unspecified";
}

/**
 * @brief Send the failure reply for a command.
 */
static void reply_error(proto_error_t error)
{
	(void)cdc_acm_send_format("err %u %s", (unsigned)error, proto_error_text(error));
}

/**
 * @brief Send a successful reply with printf formatting.
 */
static void reply_ok(const char * format, ...)
{
	char	body[PROTO_MAX_EVENT];
	va_list	arguments;

	if (format == NULL)
	{
		(void)cdc_acm_send_line("ok");
		return;
	}

	va_start(arguments, format);
	(void)vsnprintf(body, sizeof(body) - 4U, format, arguments);
	va_end(arguments);

	(void)cdc_acm_send_format("ok %s", body);
}

/**
 * @brief Split @p line into tokens on spaces.
 *
 * @return Token count, including the command word.
 */
static uint32_t tokenise(char * line, char * tokens[], uint32_t max_tokens)
{
	uint32_t	count = 0U;
	char *		cursor = line;

	while ((*cursor != '\0') && (count < max_tokens))
	{
		while (*cursor == ' ')
		{
			*cursor = '\0';
			cursor++;
		}
		if (*cursor == '\0')
		{
			break;
		}
		tokens[count] = cursor;
		count++;
		while ((*cursor != '\0') && (*cursor != ' '))
		{
			cursor++;
		}
	}

	return count;
}

/**
 * @brief Value of a @c key=value token, or NULL when the key does not match.
 */
static const char * key_value(const char * token, const char * key)
{
	uint32_t length = (uint32_t)strlen(key);

	if ((strncmp(token, key, length) == 0) && (token[length] == '='))
	{
		return &token[length + 1U];
	}

	return NULL;
}

/**
 * @brief Decode hex text into bytes.
 *
 * @return Bytes decoded, or -1 if the text is not valid hex or is too long.
 */
static int32_t decode_hex(const char * text, uint8_t * buffer, uint32_t capacity)
{
	uint32_t	length = (uint32_t)strlen(text);
	uint32_t	index;

	if (((length % 2U) != 0U) || ((length / 2U) > capacity))
	{
		return -1;
	}

	for (index = 0U; index < (length / 2U); index++)
	{
		unsigned int value;

		if (sscanf(&text[index * 2U], "%2x", &value) != 1)
		{
			return -1;
		}
		buffer[index] = (uint8_t)value;
	}

	return (int32_t)(length / 2U);
}

/**
 * @brief Encode bytes as hex text.
 */
static void encode_hex(const uint8_t * data, uint32_t length, char * text)
{
	uint32_t index;

	for (index = 0U; index < length; index++)
	{
		(void)sprintf(&text[index * 2U], "%02x", data[index]);
	}
	text[length * 2U] = '\0';
}

/* ------------------------------------------------------------------ */

static void command_ver(char * tokens[], uint32_t count)
{
	UNUSED_PARAMETER(tokens);
	UNUSED_PARAMETER(count);

	/* The version and the build date together: the version is what changes
	 * deliberately, the date is what distinguishes two builds of the same
	 * version - which is the case during development, and exactly when a
	 * stale dongle misleads. */
	reply_ok("%s %s fw=%s built=%s proto=%s uptime_us=%llu dropped=%lu",
		 PROTO_MANUFACTURER,
		 PROTO_MODEL,
		 firmware_version_string,
		 firmware_build_date_string,
		 PROTO_VERSION,
		 (unsigned long long)timestamp_now_us(),
		 (unsigned long)cdc_acm_dropped());
}

static void command_scan(char * tokens[], uint32_t count)
{
	scanner_filter_t	filter;
	uint32_t		duration_ms = 0U;
	uint32_t		index;
	uint32_t		error;

	if (strcmp(tokens[1], "stop") == 0)
	{
		(void)scanner_stop();
		reply_ok("scanning=0 sensors=%lu", (unsigned long)scanner_count());
		return;
	}
	if (strcmp(tokens[1], "start") != 0)
	{
		reply_error(PROTO_ERR_VALUE);
		return;
	}
	if (count < 3U)
	{
		reply_error(PROTO_ERR_ARGS);
		return;
	}

	(void)memset(&filter, 0, sizeof(filter));
	duration_ms = (uint32_t)strtoul(tokens[2], NULL, 10);

	for (index = 3U; index < count; index++)
	{
		const char * value;

		value = key_value(tokens[index], "name");
		if (value != NULL)
		{
			(void)strncpy(filter.name, value, PROTO_MAX_NAME - 1U);
			filter.name[PROTO_MAX_NAME - 1U] = '\0';
			filter.by_name = true;
			continue;
		}
		value = key_value(tokens[index], "addr");
		if (value != NULL)
		{
			if (!scanner_parse_address(value, &filter.address))
			{
				reply_error(PROTO_ERR_VALUE);
				return;
			}
			filter.by_address = true;
			continue;
		}
		value = key_value(tokens[index], "active");
		if (value != NULL)
		{
			filter.active = (strtoul(value, NULL, 10) != 0U);
			continue;
		}
		value = key_value(tokens[index], "rssi");
		if (value != NULL)
		{
			filter.min_rssi = (int8_t)strtol(value, NULL, 10);
			continue;
		}

		reply_error(PROTO_ERR_VALUE);
		return;
	}

	scanner_clear();
	error = scanner_start(&filter, duration_ms);
	if (error != NRF_SUCCESS)
	{
		reply_error(PROTO_ERR_BLE);
		return;
	}

	reply_ok("scanning=1 ms=%lu", (unsigned long)duration_ms);
}

static void command_list(char * tokens[], uint32_t count)
{
	uint32_t	found = scanner_count();
	uint32_t	index;
	uint64_t	now_us = timestamp_now_us();

	UNUSED_PARAMETER(tokens);
	UNUSED_PARAMETER(count);

	for (index = 0U; index < found; index++)
	{
		const scanner_sensor_t *	p_sensor = scanner_get(index);
		char				address[18];

		scanner_format_address(&p_sensor->address, address);
		(void)cdc_acm_send_format(
			"+sensor t=%llu idx=%lu addr=%s type=%u rssi=%d seen=%lu name=%s",
			(unsigned long long)now_us,
			(unsigned long)index,
			address,
			(unsigned)p_sensor->address.addr_type,
			(int)p_sensor->rssi,
			(unsigned long)p_sensor->seen,
			p_sensor->name);
	}

	reply_ok("sensors=%lu", (unsigned long)found);
}

static void command_select(char * tokens[], uint32_t count)
{
	const char * argument = tokens[1];

	UNUSED_PARAMETER(count);

	const scanner_sensor_t *	p_sensor = NULL;
	char				address[18];

	if ((argument[0] >= '0') && (argument[0] <= '9') && (strchr(argument, ':') == NULL))
	{
		p_sensor = scanner_get((uint32_t)strtoul(argument, NULL, 10));
	}
	else
	{
		ble_gap_addr_t	wanted;
		uint32_t	index;

		if (!scanner_parse_address(argument, &wanted))
		{
			reply_error(PROTO_ERR_VALUE);
			return;
		}
		index = scanner_find(&wanted);
		if (index < PROTO_MAX_SENSORS)
		{
			p_sensor = scanner_get(index);
		}
		else
		{
			/* Not in the table: accept the address as given. The host
			 * may know it from an earlier run, and refusing would make
			 * a scan mandatory before every connection. */
			m_selected         = wanted;
			m_have_selected    = true;
			m_selected_name[0] = '\0';
			scanner_format_address(&m_selected, address);
			reply_ok("addr=%s type=%u name= known=0",
				 address, (unsigned)m_selected.addr_type);
			return;
		}
	}

	if (p_sensor == NULL)
	{
		reply_error(PROTO_ERR_VALUE);
		return;
	}

	m_selected      = p_sensor->address;
	m_have_selected = true;
	(void)strncpy(m_selected_name, p_sensor->name, PROTO_MAX_NAME - 1U);
	m_selected_name[PROTO_MAX_NAME - 1U] = '\0';

	scanner_format_address(&m_selected, address);
	reply_ok("addr=%s type=%u name=%s known=1",
		 address, (unsigned)m_selected.addr_type, m_selected_name);
}

static void command_selected(char * tokens[], uint32_t count)
{
	UNUSED_PARAMETER(tokens);
	UNUSED_PARAMETER(count);

	char address[18];

	if (!m_have_selected)
	{
		reply_error(PROTO_ERR_NO_SENSOR);
		return;
	}

	scanner_format_address(&m_selected, address);
	reply_ok("addr=%s type=%u name=%s connected=%u",
		 address,
		 (unsigned)m_selected.addr_type,
		 m_selected_name,
		 (unsigned)(nus_client_is_ready() ? 1U : 0U));
}

static void command_connect(char * tokens[], uint32_t count)
{
	ble_gap_addr_t	target;
	uint32_t	error;
	char		address[18];

	if (count > 1U)
	{
		if (!scanner_parse_address(tokens[1], &target))
		{
			reply_error(PROTO_ERR_VALUE);
			return;
		}
	}
	else if (m_have_selected)
	{
		target = m_selected;
	}
	else
	{
		reply_error(PROTO_ERR_NO_SENSOR);
		return;
	}

	if (nus_client_is_connected())
	{
		reply_error(PROTO_ERR_STATE);
		return;
	}

	/* Scanning and connecting both own the radio's scanner; stop first so the
	 * connection attempt is not refused for a reason the host cannot see. */
	(void)scanner_stop();

	error = nus_client_connect(&target);
	if (error != NRF_SUCCESS)
	{
		reply_error(PROTO_ERR_BLE);
		return;
	}

	scanner_format_address(&target, address);
	reply_ok("connecting=1 addr=%s", address);
}

static void command_disconnect(char * tokens[], uint32_t count)
{
	UNUSED_PARAMETER(tokens);
	UNUSED_PARAMETER(count);

	if (nus_client_disconnect() != NRF_SUCCESS)
	{
		reply_error(PROTO_ERR_NOT_CONN);
		return;
	}

	reply_ok(NULL);
}

static void command_uart(char * tokens[], uint32_t count)
{
	const char * argument = tokens[1];

	uint8_t		payload[PROTO_MAX_PAYLOAD];
	int32_t		length;
	uint32_t	error;

	UNUSED_PARAMETER(count);

	length = decode_hex(argument, payload, sizeof(payload));
	if (length < 0)
	{
		reply_error(PROTO_ERR_TOO_LONG);
		return;
	}

	error = nus_client_write(payload, (uint16_t)length);
	if (error == NRF_ERROR_INVALID_STATE)
	{
		reply_error(PROTO_ERR_NOT_CONN);
		return;
	}
	if (error != NRF_SUCCESS)
	{
		reply_error(PROTO_ERR_BLE);
		return;
	}

	reply_ok("len=%ld t=%llu",
		 (long)length,
		 (unsigned long long)timestamp_now_us());
}

static void command_cmd(char * tokens[], uint32_t count)
{
	const char * argument = tokens[1];

	uint8_t		payload[PROTO_MAX_PAYLOAD];
	char		hex[(PROTO_MAX_PAYLOAD * 2U) + 1U];
	nus_response_t	response;
	int32_t		length;
	uint32_t	error;

	UNUSED_PARAMETER(count);

	length = decode_hex(argument, payload, sizeof(payload));
	if (length < 0)
	{
		reply_error(PROTO_ERR_TOO_LONG);
		return;
	}

	error = nus_client_command(payload, (uint16_t)length,
				   CMD_DEFAULT_TIMEOUT_MS, &response);
	if (error == NRF_ERROR_INVALID_STATE)
	{
		reply_error(PROTO_ERR_NOT_CONN);
		return;
	}
	if (error != NRF_SUCCESS)
	{
		reply_error(PROTO_ERR_BLE);
		return;
	}
	if (!response.replied)
	{
		/* A timeout is reported as an error rather than as a round trip of
		 * the timeout length, which would enter the log as a measurement. */
		reply_error(PROTO_ERR_TIMEOUT);
		return;
	}

	encode_hex(response.data, response.length, hex);
	reply_ok("t_tx=%llu t_rx=%llu dt_us=%llu interval_us=%lu len=%u data=%s",
		 (unsigned long long)response.tx_us,
		 (unsigned long long)response.rx_us,
		 (unsigned long long)response.round_trip_us,
		 (unsigned long)nus_client_interval_us(),
		 (unsigned)response.length,
		 hex);
}

static void command_adv(char * tokens[], uint32_t count)
{
	ble_gap_addr_t	target;
	uint32_t	received;
	uint32_t	reported;
	char		address[18];

	if (strcmp(tokens[1], "stats") == 0)
	{
		scanner_profile_counters(&received, &reported);
		reply_ok("received=%lu reported=%lu dropped=%lu profiling=%u",
			 (unsigned long)received,
			 (unsigned long)reported,
			 (unsigned long)cdc_acm_dropped(),
			 (unsigned)(scanner_profile_is_active() ? 1U : 0U));
		return;
	}
	if (strcmp(tokens[1], "stop") == 0)
	{
		scanner_profile_stop();
		scanner_profile_counters(&received, &reported);
		reply_ok("profiling=0 received=%lu reported=%lu",
			 (unsigned long)received, (unsigned long)reported);
		return;
	}
	if (strcmp(tokens[1], "start") != 0)
	{
		reply_error(PROTO_ERR_VALUE);
		return;
	}

	if (count > 2U)
	{
		if (!scanner_parse_address(tokens[2], &target))
		{
			reply_error(PROTO_ERR_VALUE);
			return;
		}
	}
	else if (m_have_selected)
	{
		target = m_selected;
	}
	else
	{
		reply_error(PROTO_ERR_NO_SENSOR);
		return;
	}

	scanner_profile_start(&target);
	scanner_format_address(&target, address);
	reply_ok("profiling=1 addr=%s scanning=%u",
		 address, (unsigned)(scanner_is_active() ? 1U : 0U));
}

static void command_time(char * tokens[], uint32_t count)
{
	UNUSED_PARAMETER(tokens);
	UNUSED_PARAMETER(count);

	reply_ok("t=%llu hz=%lu",
		 (unsigned long long)timestamp_now_us(),
		 (unsigned long)TIMESTAMP_HZ);
}

/** Longest the dfu command waits for its reply to leave, before resetting. */
#define CMD_PARSER_DFU_REPLY_TIMEOUT_US		250000U

/**
 * How long the dfu command keeps servicing USB after its reply has left the
 * transmit queue. A transfer is complete for the dongle once the USB peripheral
 * has it, which is not the same as the host having read it: on a PCA10059
 * under Windows, resetting as soon as the queue emptied still lost the reply.
 */
#define CMD_PARSER_DFU_REPLY_GRACE_US		50000U

static void command_dfu(char * tokens[], uint32_t count)
{
	UNUSED_PARAMETER(tokens);
	UNUSED_PARAMETER(count);

	uint64_t	start;
	uint64_t	elapsed;

	reply_ok("dfu=1 fw=%s", firmware_version_string);
	/* Let the reply reach the host: after this the USB link goes down and
	 * comes back as the bootloader's, and a host waiting for a reply it will
	 * never get cannot tell that from a dongle that has crashed. One pass of
	 * cdc_acm_process() only starts the transfer - observed on a PCA10059,
	 * the reply was lost every time - so keep servicing USB until the queue
	 * is empty and the grace period has passed, but not for ever: a host that
	 * has stopped reading must not keep the dongle out of its bootloader. */
	start = timestamp_now_us();
	do
	{
		cdc_acm_process();
		elapsed = timestamp_elapsed_us(start, timestamp_now_us());
	} while ((!cdc_acm_tx_idle() || (elapsed < CMD_PARSER_DFU_REPLY_GRACE_US)) &&
		 (elapsed < CMD_PARSER_DFU_REPLY_TIMEOUT_US));

	bootloader_enter_dfu();
}

static void command_reset(char * tokens[], uint32_t count)
{
	UNUSED_PARAMETER(tokens);
	UNUSED_PARAMETER(count);

	reply_ok("resetting=1");
	/* Let the reply reach the host before the reset takes the USB link down. */
	cdc_acm_process();
	NVIC_SystemReset();
}

/* ------------------------------------------------------------------ */

/**
 * One command: its name, its argument bounds, and what it does.
 *
 * The bounds come from @ref PROTO_COMMAND_TABLE so that the checks and the
 * documented command set cannot drift apart; the handler is attached by name
 * rather than by position, so re-ordering the protocol table cannot silently
 * point a command at the wrong implementation.
 */
typedef void (*cmd_handler_t)(char * tokens[], uint32_t count);

typedef struct
{
	const char *	name;
	uint32_t	min_args;
	uint32_t	max_args;
	cmd_handler_t	handler;
} cmd_entry_t;

/** Argument bounds, generated from the protocol table. */
#define X(name, min_args, max_args, help)	{ #name, (min_args), (max_args), NULL },
static cmd_entry_t m_commands[] =
{
	PROTO_COMMAND_TABLE
};
#undef X

#define CMD_COUNT	(sizeof(m_commands) / sizeof(m_commands[0]))

/** Name to handler. Every name here must exist in the protocol table, which
 *  @ref cmd_parser_init checks at start-up rather than trusting. */
static const struct
{
	const char *	name;
	cmd_handler_t	handler;
} m_handlers[] =
{
	{ "ver",        command_ver        },
	{ "scan",       command_scan       },
	{ "list",       command_list       },
	{ "select",     command_select     },
	{ "selected",   command_selected   },
	{ "connect",    command_connect    },
	{ "disconnect", command_disconnect },
	{ "uart",       command_uart       },
	{ "cmd",        command_cmd        },
	{ "adv",        command_adv        },
	{ "time",       command_time       },
	{ "reset",      command_reset      },
	{ "dfu",        command_dfu        }
};

#define HANDLER_COUNT	(sizeof(m_handlers) / sizeof(m_handlers[0]))

bool cmd_parser_init(void)
{
	uint32_t	index;
	uint32_t	attached = 0U;

	/* Start from a known state: no sensor selected. On the target this runs
	 * once at boot, where the state is zero anyway; it matters after a soft
	 * restart, and it is what lets the unit tests be order-independent. */
	m_have_selected    = false;
	m_selected_name[0] = '\0';
	(void)memset(&m_selected, 0, sizeof(m_selected));

	for (index = 0U; index < CMD_COUNT; index++)
	{
		uint32_t candidate;

		for (candidate = 0U; candidate < HANDLER_COUNT; candidate++)
		{
			if (strcmp(m_commands[index].name, m_handlers[candidate].name) == 0)
			{
				m_commands[index].handler = m_handlers[candidate].handler;
				attached++;
				break;
			}
		}
	}

	/* A command documented in the protocol header with no implementation
	 * behind it would answer "unknown command" at the bench. Saying so here
	 * turns that into a start-up failure the developer sees instead. */
	return (attached == CMD_COUNT) && (HANDLER_COUNT == CMD_COUNT);
}

void cmd_parser_handle(char * line)
{
	char *		tokens[CMD_MAX_ARGS + 1U];
	uint32_t	count;
	uint32_t	index;
	uint32_t	arguments;

	count = tokenise(line, tokens, CMD_MAX_ARGS + 1U);
	if (count == 0U)
	{
		return;			/* a blank line is not a command */
	}
	arguments = count - 1U;

	for (index = 0U; index < CMD_COUNT; index++)
	{
		if (strcmp(tokens[0], m_commands[index].name) != 0)
		{
			continue;
		}
		if ((arguments < m_commands[index].min_args) ||
		    (arguments > m_commands[index].max_args))
		{
			reply_error(PROTO_ERR_ARGS);
			return;
		}
		if (m_commands[index].handler == NULL)
		{
			reply_error(PROTO_ERR_UNKNOWN);
			return;
		}
		m_commands[index].handler(tokens, count);
		return;
	}

	reply_error(PROTO_ERR_UNKNOWN);
}
