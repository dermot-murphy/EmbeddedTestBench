/**
 * @file cmd_args.c
 * @brief Reading the optional arguments of host commands.
 *
 * Numbers are read with strtoull() and strtoll(), which set errno on overflow;
 * errno is cleared before each call and tested after it (MISRA C:2012 Rules 22.8
 * and 22.9), so a number too large for 32 bits is refused rather than wrapped.
 *
 * Traces to: BLE-DD-CMD, BLE-DD-CMDARGS.
 */

#include "cmd_args.h"

#include <errno.h>
#include <stdlib.h>
#include <string.h>

#include "ble_scanner.h"
#include "protocol.h"

#define CMD_ARGS_DECIMAL_BASE		10	/**< for numbers in arguments */
#define CMD_ARGS_HEX_DIGITS		16U	/**< digits in base 16 */
#define CMD_ARGS_NIBBLE_BITS		4U	/**< bits in one hex digit */
#define CMD_ARGS_NIBBLE_MASK		0x0FU	/**< the low hex digit of a byte */
#define CMD_ARGS_NOT_HEX		0xFFU	/**< not the value of any hex digit */

/** Hex digits: output is lower case; input may be either case. */
static const char	m_cmd_args_hex_lower[] = "0123456789abcdef";

/**
 * @brief Read @p text as an unsigned decimal number, as strtoull() reads it.
 *
 * @param[out] pp_end  Where the number ended; may be NULL.
 * @return False when the number does not fit in 32 bits.
 */
static bool cmd_args_read_unsigned(const char * text, uint32_t * p_value, const char ** pp_end)
{
	char *			end = NULL;
	unsigned long long	value;
	bool			fits;

	errno = 0;
	value = strtoull(text, &end, CMD_ARGS_DECIMAL_BASE);
	fits  = (errno == 0) && (value <= UINT32_MAX);

	*p_value = (uint32_t)value;
	if (pp_end != NULL)
	{
		*pp_end = end;
	}

	return fits;
}

bool cmd_args_unsigned(const char * text, uint32_t * p_value)
{
	return cmd_args_read_unsigned(text, p_value, NULL);
}

bool cmd_args_signed(const char * text, int32_t * p_value)
{
	long long	value;
	bool		fits;

	errno = 0;
	value = strtoll(text, NULL, CMD_ARGS_DECIMAL_BASE);
	fits  = (errno == 0) && (value >= INT32_MIN) && (value <= INT32_MAX);

	*p_value = (int32_t)value;

	return fits;
}

bool cmd_args_timeout(const char * token, uint32_t min_ms, uint32_t max_ms,
		      uint32_t * p_timeout_ms, bool * p_ok)
{
	static const char	key[] = "timeout=";
	const char *		end   = NULL;
	uint32_t		value = 0U;
	bool			is_timeout;

	is_timeout = (strncmp(token, key, sizeof(key) - 1U) == 0);
	if (is_timeout)
	{
		bool fits = cmd_args_read_unsigned(&token[sizeof(key) - 1U], &value, &end);

		*p_ok         = fits && (*end == '\0') && (value >= min_ms) && (value <= max_ms);
		*p_timeout_ms = value;
	}

	return is_timeout;
}

bool cmd_args_connect(const char * const tokens[], uint32_t count, ble_gap_addr_t * p_target,
		      bool * p_have_target, uint32_t * p_timeout_ms)
{
	uint32_t	index;
	bool		valid = true;

	*p_have_target = false;
	*p_timeout_ms  = PROTOCOL_CONNECT_DEFAULT_MS;

	for (index = 1U; (index < count) && valid; index++)
	{
		bool timeout_ok = true;

		if (cmd_args_timeout(tokens[index], PROTOCOL_CONNECT_MIN_MS,
				     PROTOCOL_CONNECT_MAX_MS, p_timeout_ms, &timeout_ok))
		{
			valid = timeout_ok;
		}
		else if (*p_have_target || !ble_scanner_parse_address(tokens[index], p_target))
		{
			valid = false;
		}
		else
		{
			*p_have_target = true;
		}
	}

	return valid;
}

/**
 * @brief Value of a @c key=value token, or NULL when the key does not match.
 */
static const char * cmd_args_key_value(const char * token, const char * key)
{
	uint32_t	length = (uint32_t)strlen(key);
	const char *	value  = NULL;

	if ((strncmp(token, key, length) == 0) && (token[length] == '='))
	{
		value = &token[length + 1U];
	}

	return value;
}

/**
 * @brief Read one optional argument of @c scan start into @p p_filter.
 *
 * @return False when the token is not a known option or its value is bad.
 */
static bool cmd_args_scan_option(const char * token, ble_scanner_filter_t * p_filter)
{
	const char *	name    = cmd_args_key_value(token, "name");
	const char *	address = cmd_args_key_value(token, "addr");
	const char *	active  = cmd_args_key_value(token, "active");
	const char *	rssi    = cmd_args_key_value(token, "rssi");
	uint32_t	flag    = 0U;
	int32_t		level   = 0;
	bool		valid   = true;

	if (name != NULL)
	{
		(void)strncpy(p_filter->name, name, PROTOCOL_MAX_NAME - 1U);
		p_filter->name[PROTOCOL_MAX_NAME - 1U] = '\0';
		p_filter->by_name = true;
	}
	else if (address != NULL)
	{
		valid                = ble_scanner_parse_address(address, &p_filter->address);
		p_filter->by_address = valid;
	}
	else if (active != NULL)
	{
		valid            = cmd_args_unsigned(active, &flag);
		p_filter->active = (flag != 0U);
	}
	else if (rssi != NULL)
	{
		valid              = cmd_args_signed(rssi, &level);
		p_filter->min_rssi = (int8_t)level;
	}
	else
	{
		valid = false;
	}

	return valid;
}

bool cmd_args_scan_filter(const char * const tokens[], uint32_t count, ble_scanner_filter_t * p_filter)
{
	uint32_t	index;
	bool		valid = true;

	(void)memset(p_filter, 0, sizeof(*p_filter));
	for (index = 3U; (index < count) && valid; index++)
	{
		valid = cmd_args_scan_option(tokens[index], p_filter);
	}

	return valid;
}

/**
 * @brief The value of one hex digit, or CMD_ARGS_NOT_HEX.
 */
static uint8_t cmd_args_hex_value(char digit)
{
	static const char	upper[] = "0123456789ABCDEF";
	uint8_t			value = CMD_ARGS_NOT_HEX;
	uint8_t			index;
	bool			found = false;

	for (index = 0U; (index < CMD_ARGS_HEX_DIGITS) && !found; index++)
	{
		if ((digit == m_cmd_args_hex_lower[index]) || (digit == upper[index]))
		{
			value = index;
			found = true;
		}
	}

	return value;
}

bool cmd_args_decode_hex(const char * text, uint8_t * buffer, uint32_t capacity,
			 uint16_t * p_length)
{
	uint32_t	length = (uint32_t)strlen(text);
	uint32_t	index;
	bool		valid  = ((length % 2U) == 0U) && ((length / 2U) <= capacity);

	for (index = 0U; (index < (length / 2U)) && valid; index++)
	{
		uint8_t high = cmd_args_hex_value(text[index * 2U]);
		uint8_t low  = cmd_args_hex_value(text[(index * 2U) + 1U]);

		if ((high == CMD_ARGS_NOT_HEX) || (low == CMD_ARGS_NOT_HEX))
		{
			valid = false;
		}
		else
		{
			buffer[index] = (uint8_t)((uint8_t)(high << CMD_ARGS_NIBBLE_BITS) | low);
		}
	}

	if (valid)
	{
		*p_length = (uint16_t)(length / 2U);
	}

	return valid;
}

void cmd_args_encode_hex(const uint8_t * data, uint32_t length, char * text)
{
	uint32_t index;

	for (index = 0U; index < length; index++)
	{
		text[index * 2U]        = m_cmd_args_hex_lower[data[index] >> CMD_ARGS_NIBBLE_BITS];
		text[(index * 2U) + 1U] = m_cmd_args_hex_lower[data[index] & CMD_ARGS_NIBBLE_MASK];
	}
	text[length * 2U] = '\0';
}
