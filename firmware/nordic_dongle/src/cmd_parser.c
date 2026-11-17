/**
 * @file cmd_parser.c
 * @brief The command dispatcher.
 *
 * Each handler replies once, from its one exit (ETB-STD-002 section 23.1).
 *
 * Traces to: BLE-FR-002, BLE-FR-020 .. BLE-FR-044, BLE-DD-CMD.
 */

#include "cmd_parser.h"

#include <stdarg.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>

#include "app_error.h"
#include "app_util_platform.h"
#include "nrf_sdh.h"
#include "nrf_soc.h"

#include "ble_scanner.h"
#include "bootloader.h"
#include "cmd_args.h"
#include "cmd_dfu.h"
#include "cdc_acm.h"
#include "firmware_version.h"
#include "nus_client.h"
#include "timestamp.h"

/** Characters, with the terminator, in an address ("AA:BB:CC:DD:EE:FF"), in a
 *  manufacturer ID ("0xFFFF"), and kept free for the "ok " before a reply. */
#define CMD_PARSER_ADDRESS_TEXT		18U
#define CMD_PARSER_MANUFACTURER_TEXT	7U
#define CMD_PARSER_OK_PREFIX		4U

/** The sensor chosen by @c select, if any. */
static ble_gap_addr_t	m_selected;
static bool		m_have_selected;
static char		m_selected_name[PROTOCOL_MAX_NAME];

/** One row of the error text table, from a row of PROTOCOL_ERROR_TABLE. */
#define CMD_PARSER_ERROR_ENTRY(symbol, code, text)	{ (symbol), (text) },

const char * proto_error_text(proto_error_t error)
{
	static const struct
	{
		proto_error_t	code;
		const char *	text;
	} texts[] =
	{
		PROTOCOL_ERROR_TABLE(CMD_PARSER_ERROR_ENTRY)
	};
	const char *	text = "unspecified";
	uint32_t	index;
	bool		found = false;

	for (index = 0U; (index < (sizeof(texts) / sizeof(texts[0]))) && !found; index++)
	{
		if (texts[index].code == error)
		{
			text  = texts[index].text;
			found = true;
		}
	}

	return text;
}

/**
 * @brief Send the failure reply for a command.
 */
static void cmd_parser_reply_error(proto_error_t error)
{
	(void)cdc_acm_send_format("err %u %s", (unsigned)error, proto_error_text(error));
}

/**
 * @brief Send a successful reply with printf formatting.
 */
static void cmd_parser_reply_ok(const char * format, ...)
{
	if (format == NULL)
	{
		(void)cdc_acm_send_line("ok");
	}
	else
	{
		char	body[PROTOCOL_MAX_EVENT];
		va_list	arguments;

		va_start(arguments, format);
		(void)vsnprintf(body, sizeof(body) - CMD_PARSER_OK_PREFIX, format, arguments);
		va_end(arguments);

		(void)cdc_acm_send_format("ok %s", body);
	}
}

/**
 * @brief Split @p line into tokens on spaces.
 *
 * @return Token count, including the command word.
 */
static uint32_t cmd_parser_tokenise(char * line, char * tokens[], uint32_t max_tokens)
{
	uint32_t	count = 0U;
	char *		cursor = line;
	bool		ended = false;

	while ((*cursor != '\0') && (count < max_tokens) && !ended)
	{
		while (*cursor == ' ')
		{
			*cursor = '\0';
			cursor++;
		}
		if (*cursor == '\0')
		{
			ended = true;
		}
		else
		{
			tokens[count] = cursor;
			count++;
			while ((*cursor != '\0') && (*cursor != ' '))
			{
				cursor++;
			}
		}
	}

	return count;
}

/* ------------------------------------------------------------------ */

static void cmd_parser_command_ver(const char * const tokens[], uint32_t count)
{
	char		time_text[TIMESTAMP_TEXT_SIZE];

	UNUSED_PARAMETER(tokens);
	UNUSED_PARAMETER(count);

	/* The version and the build date together: the version is what changes
	 * deliberately, the date is what distinguishes two builds of the same
	 * version - which is the case during development, and exactly when a
	 * stale dongle misleads. */
	cmd_parser_reply_ok("%s %s fw=%s built=%s proto=%s uptime_us=%s dropped=%lu",
			    PROTOCOL_MANUFACTURER,
			    PROTOCOL_MODEL,
			    firmware_version_g_string,
			    firmware_build_date(),
			    PROTOCOL_VERSION,
			    timestamp_format_us(timestamp_now_us(), time_text),
			    (unsigned long)cdc_acm_dropped());
}

static void cmd_parser_command_scan(const char * const tokens[], uint32_t count)
{
	ble_scanner_filter_t	filter;
	uint32_t		duration_ms = 0U;
	proto_error_t		refusal     = PROTO_ERR_NONE;

	if (strcmp(tokens[1], "stop") == 0)
	{
		(void)ble_scanner_stop();
		cmd_parser_reply_ok("scanning=0 sensors=%lu", (unsigned long)ble_scanner_count());
	}
	else
	{
		if (strcmp(tokens[1], "start") != 0)
		{
			refusal = PROTO_ERR_VALUE;
		}
		else if (count < 3U)
		{
			refusal = PROTO_ERR_ARGS;
		}
		else if (!cmd_args_unsigned(tokens[2], &duration_ms) ||
			 !cmd_args_scan_filter(tokens, count, &filter))
		{
			refusal = PROTO_ERR_VALUE;
		}
		else
		{
			ble_scanner_clear();
			if (ble_scanner_start(&filter, duration_ms) != NRF_SUCCESS)
			{
				refusal = PROTO_ERR_BLE;
			}
		}

		if (refusal == PROTO_ERR_NONE)
		{
			cmd_parser_reply_ok("scanning=1 ms=%lu", (unsigned long)duration_ms);
		}
		else
		{
			cmd_parser_reply_error(refusal);
		}
	}
}

static void cmd_parser_command_list(const char * const tokens[], uint32_t count)
{
	char		time_text[TIMESTAMP_TEXT_SIZE];
	uint32_t	found = ble_scanner_count();
	uint32_t	index;
	uint64_t	now_us = timestamp_now_us();

	UNUSED_PARAMETER(tokens);
	UNUSED_PARAMETER(count);

	for (index = 0U; index < found; index++)
	{
		const ble_scanner_sensor_t *	p_sensor = ble_scanner_get(index);
		char				address[CMD_PARSER_ADDRESS_TEXT];
		char				manufacturer[CMD_PARSER_MANUFACTURER_TEXT];
		char				scan_response[(PROTOCOL_MAX_ADV_DATA * 2U) + 1U];

		ble_scanner_format_address(&p_sensor->address, address);
		manufacturer[0] = '\0';
		if (p_sensor->has_manufacturer)
		{
			(void)snprintf(manufacturer, sizeof(manufacturer), "0x%04X",
				       (unsigned)p_sensor->manufacturer_id);
		}
		cmd_args_encode_hex(p_sensor->scan_response, p_sensor->scan_response_length, scan_response);

		/* The name stays last: it is the one field that may hold a space. */
		(void)cdc_acm_send_format(
			"+sensor t=%s idx=%lu addr=%s type=%u rssi=%d seen=%lu mfr=%s sr=%s name=%s",
			timestamp_format_us(now_us, time_text),
			(unsigned long)index,
			address,
			(unsigned)p_sensor->address.addr_type,
			(int)p_sensor->rssi,
			(unsigned long)p_sensor->seen,
			manufacturer,
			scan_response,
			p_sensor->name);
	}

	cmd_parser_reply_ok("sensors=%lu", (unsigned long)found);
}

/**
 * @brief Make @p p_address the selected sensor and reply as @c select does.
 *
 * @param[in] known  1 when the address is in the scan table, 0 when it was
 *                   accepted as given.
 */
static void cmd_parser_select(const ble_gap_addr_t * p_address, const char * name, uint32_t known)
{
	char address[CMD_PARSER_ADDRESS_TEXT];

	m_selected      = *p_address;
	m_have_selected = true;
	(void)strncpy(m_selected_name, name, PROTOCOL_MAX_NAME - 1U);
	m_selected_name[PROTOCOL_MAX_NAME - 1U] = '\0';

	ble_scanner_format_address(&m_selected, address);
	cmd_parser_reply_ok("addr=%s type=%u name=%s known=%lu",
			    address, (unsigned)m_selected.addr_type, m_selected_name,
			    (unsigned long)known);
}

static void cmd_parser_command_select(const char * const tokens[], uint32_t count)
{
	const char *			argument = tokens[1];
	const ble_scanner_sensor_t *	p_sensor = NULL;
	ble_gap_addr_t			wanted;
	uint32_t			index    = PROTOCOL_MAX_SENSORS;
	bool				unlisted = false;

	UNUSED_PARAMETER(count);

	(void)memset(&wanted, 0, sizeof(wanted));
	if ((argument[0] >= '0') && (argument[0] <= '9') && (strchr(argument, ':') == NULL))
	{
		if (cmd_args_unsigned(argument, &index))
		{
			p_sensor = ble_scanner_get(index);
		}
	}
	else if (ble_scanner_parse_address(argument, &wanted))
	{
		index = ble_scanner_find(&wanted);
		if (index < PROTOCOL_MAX_SENSORS)
		{
			p_sensor = ble_scanner_get(index);
		}
		else
		{
			/* Not in the table: accept the address as given. The host
			 * may know it from an earlier run, and refusing would make
			 * a scan mandatory before every connection. */
			unlisted = true;
		}
	}
	else
	{
		/* Neither an index nor an address: refused below. */
	}

	if (p_sensor != NULL)
	{
		cmd_parser_select(&p_sensor->address, p_sensor->name, 1U);
	}
	else if (unlisted)
	{
		cmd_parser_select(&wanted, "", 0U);
	}
	else
	{
		cmd_parser_reply_error(PROTO_ERR_VALUE);
	}
}

static void cmd_parser_command_selected(const char * const tokens[], uint32_t count)
{
	UNUSED_PARAMETER(tokens);
	UNUSED_PARAMETER(count);

	if (!m_have_selected)
	{
		cmd_parser_reply_error(PROTO_ERR_NO_SENSOR);
	}
	else
	{
		char address[CMD_PARSER_ADDRESS_TEXT];

		ble_scanner_format_address(&m_selected, address);
		cmd_parser_reply_ok("addr=%s type=%u name=%s connected=%u",
				    address,
				    (unsigned)m_selected.addr_type,
				    m_selected_name,
				    (unsigned)(nus_client_is_ready() ? 1U : 0U));
	}
}

/**
 * @brief Start a connection to @p p_target and report how it began.
 */
static void cmd_parser_connect_to(const ble_gap_addr_t * p_target, uint32_t timeout_ms)
{
	uint32_t	error;

	/* Scanning and connecting both own the radio's scanner; stop first so the
	 * connection attempt is not refused for a reason the host cannot see. */
	(void)ble_scanner_stop();

	error = nus_client_connect(p_target, timeout_ms);
	if (error != NRF_SUCCESS)
	{
		(void)cdc_acm_send_format("err %u %s nrf=0x%lx",
					  (unsigned)PROTO_ERR_BLE,
					  proto_error_text(PROTO_ERR_BLE),
					  (unsigned long)error);
	}
	else
	{
		char address[CMD_PARSER_ADDRESS_TEXT];

		ble_scanner_format_address(p_target, address);
		cmd_parser_reply_ok("connecting=1 addr=%s timeout_ms=%lu", address,
				    (unsigned long)timeout_ms);
	}
}

static void cmd_parser_command_connect(const char * const tokens[], uint32_t count)
{
	ble_gap_addr_t	target;
	bool		have_target = false;
	uint32_t	timeout_ms  = PROTOCOL_CONNECT_DEFAULT_MS;
	proto_error_t	refusal     = PROTO_ERR_NONE;

	(void)memset(&target, 0, sizeof(target));
	if (!cmd_args_connect(tokens, count, &target, &have_target, &timeout_ms))
	{
		refusal = PROTO_ERR_VALUE;
	}
	else if (!have_target && !m_have_selected)
	{
		refusal = PROTO_ERR_NO_SENSOR;
	}
	else if (nus_client_is_connected())
	{
		refusal = PROTO_ERR_STATE;
	}
	else if (nus_client_is_connecting())
	{
		/* Said plainly rather than left to the stack, whose refusal read as
		 * "the BLE stack refused the request" (#251). disconnect ends it. */
		refusal = PROTO_ERR_BUSY;
	}
	else
	{
		if (!have_target)
		{
			target = m_selected;
		}
		cmd_parser_connect_to(&target, timeout_ms);
	}

	if (refusal != PROTO_ERR_NONE)
	{
		cmd_parser_reply_error(refusal);
	}
}

static void cmd_parser_command_disconnect(const char * const tokens[], uint32_t count)
{
	UNUSED_PARAMETER(tokens);
	UNUSED_PARAMETER(count);

	if (nus_client_disconnect() != NRF_SUCCESS)
	{
		cmd_parser_reply_error(PROTO_ERR_NOT_CONN);
	}
	else
	{
		cmd_parser_reply_ok(NULL);
	}
}

/**
 * @brief The refusal a failed write or command to the sensor is reported as.
 */
static proto_error_t cmd_parser_link_refusal(uint32_t error)
{
	proto_error_t refusal = PROTO_ERR_NONE;

	if (error == NRF_ERROR_INVALID_STATE)
	{
		refusal = PROTO_ERR_NOT_CONN;
	}
	else if (error != NRF_SUCCESS)
	{
		refusal = PROTO_ERR_BLE;
	}
	else
	{
		/* Success: no refusal. */
	}

	return refusal;
}

static void cmd_parser_command_uart(const char * const tokens[], uint32_t count)
{
	char		time_text[TIMESTAMP_TEXT_SIZE];
	const char *	argument = tokens[1];
	uint8_t		payload[PROTOCOL_MAX_PAYLOAD];
	uint16_t	length  = 0U;
	proto_error_t	refusal = PROTO_ERR_TOO_LONG;

	UNUSED_PARAMETER(count);

	if (cmd_args_decode_hex(argument, payload, sizeof(payload), &length))
	{
		refusal = cmd_parser_link_refusal(nus_client_write(payload, length));
	}

	if (refusal != PROTO_ERR_NONE)
	{
		cmd_parser_reply_error(refusal);
	}
	else
	{
		cmd_parser_reply_ok("len=%ld t=%s",
				    (long)length,
				    timestamp_format_us(timestamp_now_us(), time_text));
	}
}

/**
 * @brief Report the round trip of a @c cmd the sensor answered.
 */
static void cmd_parser_report_round_trip(const nus_response_t * p_response)
{
	char	tx_text[TIMESTAMP_TEXT_SIZE];
	char	rx_text[TIMESTAMP_TEXT_SIZE];
	char	dt_text[TIMESTAMP_TEXT_SIZE];
	char	hex[(PROTOCOL_MAX_PAYLOAD * 2U) + 1U];

	cmd_args_encode_hex(p_response->data, p_response->length, hex);
	cmd_parser_reply_ok("t_tx=%s t_rx=%s dt_us=%s interval_us=%lu len=%u data=%s",
			    timestamp_format_us(p_response->tx_us, tx_text),
			    timestamp_format_us(p_response->rx_us, rx_text),
			    timestamp_format_us(p_response->round_trip_us, dt_text),
			    (unsigned long)nus_client_interval_us(),
			    (unsigned)p_response->length,
			    hex);
}

static void cmd_parser_command_cmd(const char * const tokens[], uint32_t count)
{
	uint8_t		payload[PROTOCOL_MAX_PAYLOAD];
	nus_response_t	response;
	uint16_t	length     = 0U;
	uint32_t	timeout_ms = PROTOCOL_CMD_DEFAULT_MS;
	bool		valid      = false;
	proto_error_t	refusal    = PROTO_ERR_NONE;

	(void)memset(&response, 0, sizeof(response));

	/* cmd <hex> [timeout=<ms>]: some commands take longer than others. */
	if ((count > 2U) && (!cmd_args_timeout(tokens[2], PROTOCOL_CMD_MIN_MS,
					       PROTOCOL_CMD_MAX_MS, &timeout_ms, &valid) || !valid))
	{
		refusal = PROTO_ERR_VALUE;
	}
	else if (!cmd_args_decode_hex(tokens[1], payload, sizeof(payload), &length))
	{
		refusal = PROTO_ERR_TOO_LONG;
	}
	else
	{
		refusal = cmd_parser_link_refusal(nus_client_command(payload, length,
								     timeout_ms, &response));
		if ((refusal == PROTO_ERR_NONE) && !response.replied)
		{
			/* A timeout is reported as an error rather than as a round
			 * trip of the timeout length, which would enter the log as a
			 * measurement. */
			refusal = PROTO_ERR_TIMEOUT;
		}
	}

	if (refusal != PROTO_ERR_NONE)
	{
		cmd_parser_reply_error(refusal);
	}
	else
	{
		cmd_parser_report_round_trip(&response);
	}
}

/**
 * @brief @c adv @c start: profile @p p_target's advertising.
 */
static void cmd_parser_adv_start(const ble_gap_addr_t * p_target)
{
	char address[CMD_PARSER_ADDRESS_TEXT];

	ble_scanner_profile_start(p_target);
	ble_scanner_format_address(p_target, address);
	cmd_parser_reply_ok("profiling=1 addr=%s scanning=%u",
			    address, (unsigned)(ble_scanner_is_active() ? 1U : 0U));
}

static void cmd_parser_command_adv(const char * const tokens[], uint32_t count)
{
	ble_gap_addr_t	target;
	uint32_t	received = 0U;
	uint32_t	reported = 0U;

	if (strcmp(tokens[1], "stats") == 0)
	{
		ble_scanner_profile_counters(&received, &reported);
		cmd_parser_reply_ok("received=%lu reported=%lu dropped=%lu profiling=%u",
				    (unsigned long)received,
				    (unsigned long)reported,
				    (unsigned long)cdc_acm_dropped(),
				    (unsigned)(ble_scanner_profile_is_active() ? 1U : 0U));
	}
	else if (strcmp(tokens[1], "stop") == 0)
	{
		ble_scanner_profile_stop();
		ble_scanner_profile_counters(&received, &reported);
		cmd_parser_reply_ok("profiling=0 received=%lu reported=%lu",
				    (unsigned long)received, (unsigned long)reported);
	}
	else if (strcmp(tokens[1], "start") != 0)
	{
		cmd_parser_reply_error(PROTO_ERR_VALUE);
	}
	else if (count > 2U)
	{
		if (ble_scanner_parse_address(tokens[2], &target))
		{
			cmd_parser_adv_start(&target);
		}
		else
		{
			cmd_parser_reply_error(PROTO_ERR_VALUE);
		}
	}
	else if (m_have_selected)
	{
		cmd_parser_adv_start(&m_selected);
	}
	else
	{
		cmd_parser_reply_error(PROTO_ERR_NO_SENSOR);
	}
}

static void cmd_parser_command_time(const char * const tokens[], uint32_t count)
{
	char		time_text[TIMESTAMP_TEXT_SIZE];

	UNUSED_PARAMETER(tokens);
	UNUSED_PARAMETER(count);

	cmd_parser_reply_ok("t=%s hz=%lu",
			    timestamp_format_us(timestamp_now_us(), time_text),
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

static void cmd_parser_command_dfu(const char * const tokens[], uint32_t count)
{
	uint64_t	start;
	uint64_t	elapsed;

	UNUSED_PARAMETER(tokens);
	UNUSED_PARAMETER(count);

	cmd_parser_reply_ok("dfu=1 fw=%s", firmware_version_g_string);
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

static void cmd_parser_command_reset(const char * const tokens[], uint32_t count)
{
	UNUSED_PARAMETER(tokens);
	UNUSED_PARAMETER(count);

	cmd_parser_reply_ok("resetting=1");
	/* Let the reply reach the host before the reset takes the USB link down. */
	cdc_acm_process();
	NVIC_SystemReset();
}

/* ------------------------------------------------------------------ */

/**
 * One command: its name, its argument bounds, and what it does.
 *
 * The bounds come from @ref PROTOCOL_COMMAND_TABLE so that the checks and the
 * documented command set cannot drift apart; the handler is attached by name
 * rather than by position, so re-ordering the protocol table cannot silently
 * point a command at the wrong implementation.
 */
typedef void (*cmd_handler_t)(const char * const tokens[], uint32_t count);

typedef struct
{
	const char *	name;
	uint32_t	min_args;
	uint32_t	max_args;
	cmd_handler_t	handler;
} cmd_entry_t;

/** One row of the command table, from a row of PROTOCOL_COMMAND_TABLE. The
 *  name is the table's own token, so it cannot be spelt differently here. */
#define CMD_PARSER_COMMAND_ENTRY(name, min_args, max_args, help)	\
	{ #name, (min_args), (max_args), NULL },

/** Argument bounds, generated from the protocol table. */
static cmd_entry_t m_commands[] =
{
	PROTOCOL_COMMAND_TABLE(CMD_PARSER_COMMAND_ENTRY)
};

#define CMD_PARSER_COMMAND_COUNT	(sizeof(m_commands) / sizeof(m_commands[0]))

bool cmd_parser_init(void)
{
	/* Name to handler. Every name here must exist in the protocol table,
	 * which is checked below rather than trusted. */
	static const struct
	{
		const char *	name;
		cmd_handler_t	handler;
	} handlers[] =
	{
		{ "ver",        cmd_parser_command_ver        },
		{ "scan",       cmd_parser_command_scan       },
		{ "list",       cmd_parser_command_list       },
		{ "select",     cmd_parser_command_select     },
		{ "selected",   cmd_parser_command_selected   },
		{ "connect",    cmd_parser_command_connect    },
		{ "disconnect", cmd_parser_command_disconnect },
		{ "uart",       cmd_parser_command_uart       },
		{ "cmd",        cmd_parser_command_cmd        },
		{ "adv",        cmd_parser_command_adv        },
		{ "time",       cmd_parser_command_time       },
		{ "reset",      cmd_parser_command_reset      },
		{ "dfu",        cmd_parser_command_dfu        },
		{ "dfucp",      cmd_dfu_control               },
		{ "dfupkt",     cmd_dfu_packet                }
	};
	const uint32_t	handler_count = (uint32_t)(sizeof(handlers) / sizeof(handlers[0]));
	uint32_t	index;
	uint32_t	attached = 0U;

	/* Start from a known state: no sensor selected. On the target this runs
	 * once at boot, where the state is zero anyway; it matters after a soft
	 * restart, and it is what lets the unit tests be order-independent. */
	m_have_selected    = false;
	m_selected_name[0] = '\0';
	(void)memset(&m_selected, 0, sizeof(m_selected));

	for (index = 0U; index < CMD_PARSER_COMMAND_COUNT; index++)
	{
		uint32_t	candidate;
		bool		matched = false;

		for (candidate = 0U; (candidate < handler_count) && !matched; candidate++)
		{
			if (strcmp(m_commands[index].name, handlers[candidate].name) == 0)
			{
				m_commands[index].handler = handlers[candidate].handler;
				attached++;
				matched = true;
			}
		}
	}

	/* A command documented in the protocol header with no implementation
	 * behind it would answer "unknown command" at the bench. Saying so here
	 * turns that into a start-up failure the developer sees instead. */
	return (attached == CMD_PARSER_COMMAND_COUNT) && (handler_count == CMD_PARSER_COMMAND_COUNT);
}

void cmd_parser_handle(char * line)
{
	char *		tokens[CMD_PARSER_MAX_ARGS + 1U];
	uint32_t	count;

	count = cmd_parser_tokenise(line, tokens, CMD_PARSER_MAX_ARGS + 1U);

	/* A blank line is not a command, and has no reply. */
	if (count > 0U)
	{
		uint32_t	arguments = count - 1U;
		uint32_t	index;
		uint32_t	found     = 0U;
		bool		matched   = false;

		for (index = 0U; (index < CMD_PARSER_COMMAND_COUNT) && !matched; index++)
		{
			if (strcmp(tokens[0], m_commands[index].name) == 0)
			{
				found   = index;
				matched = true;
			}
		}

		if (!matched)
		{
			cmd_parser_reply_error(PROTO_ERR_UNKNOWN);
		}
		else if ((arguments < m_commands[found].min_args) ||
			 (arguments > m_commands[found].max_args))
		{
			cmd_parser_reply_error(PROTO_ERR_ARGS);
		}
		else if (m_commands[found].handler == NULL)
		{
			cmd_parser_reply_error(PROTO_ERR_UNKNOWN);
		}
		else
		{
			m_commands[found].handler((const char * const *)tokens, count);
		}
	}
}
