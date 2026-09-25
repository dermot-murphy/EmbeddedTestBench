/**
 * @file cmd_args.c
 * @brief Reading the optional arguments of host commands.
 *
 * Traces to: BLE-DD-CMD.
 */

#include "cmd_args.h"

#include <stdlib.h>
#include <string.h>

#include "ble_scanner.h"
#include "protocol.h"

#define CMD_ARGS_DECIMAL_BASE		10U	/**< for numbers in arguments */

bool cmd_args_timeout(const char * token, uint32_t min_ms, uint32_t max_ms,
		      uint32_t * p_timeout_ms, bool * p_ok)
{
	static const char	key[] = "timeout=";
	char *			end;
	unsigned long		value;

	if (strncmp(token, key, sizeof(key) - 1U) != 0)
	{
		return false;
	}
	value = strtoul(&token[sizeof(key) - 1U], &end, (int)CMD_ARGS_DECIMAL_BASE);
	*p_ok = (*end == '\0') && (value >= min_ms) && (value <= max_ms);
	*p_timeout_ms = (uint32_t)value;
	return true;
}

bool cmd_args_connect(char * tokens[], uint32_t count, ble_gap_addr_t * p_target,
		      bool * p_have_target, uint32_t * p_timeout_ms)
{
	uint32_t	index;
	bool		valid = true;

	*p_have_target = false;
	*p_timeout_ms  = PROTOCOL_CONNECT_DEFAULT_MS;

	for (index = 1U; index < count; index++)
	{
		if (cmd_args_timeout(tokens[index], PROTOCOL_CONNECT_MIN_MS,
				     PROTOCOL_CONNECT_MAX_MS, p_timeout_ms, &valid))
		{
			if (!valid)
			{
				return false;
			}
		}
		else if (*p_have_target || !scanner_parse_address(tokens[index], p_target))
		{
			return false;
		}
		else
		{
			*p_have_target = true;
		}
	}

	return true;
}
