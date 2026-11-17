/**
 * @file cmd_args.h
 * @brief Reading the optional arguments of host commands.
 *
 * Kept apart from cmd_parser.c, which dispatches the commands, so that each
 * stays a size one person can read in a sitting.
 *
 * Traces to: BLE-DD-CMD.
 */

#ifndef CMD_ARGS_H__
#define CMD_ARGS_H__

#include <stdbool.h>
#include <stdint.h>

#include "ble_gap.h"
#include "ble_scanner.h"

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief Read @p text as an unsigned decimal number, as strtoul() would.
 *
 * Reading stops at the first character that is not part of the number, and
 * text with no number in it reads as 0.
 *
 * @param[out] p_value  The number read.
 * @return False when the number does not fit in 32 bits.
 */
bool cmd_args_unsigned(const char * text, uint32_t * p_value);

/**
 * @brief Read @p token as timeout=<ms>, if it is one.
 *
 * @param[out] p_timeout_ms  The value, when the token is a timeout.
 * @param[out] p_ok          False when the value is not a whole number in
 *                           [@p min_ms, @p max_ms].
 * @return True if the token is a timeout=, whether or not its value is good.
 */
bool cmd_args_timeout(const char * token, uint32_t min_ms, uint32_t max_ms,
		      uint32_t * p_timeout_ms, bool * p_ok);

/**
 * @brief Read connect's optional address and timeout=<ms>, in either order.
 *
 * @return False if a token is malformed, repeated or out of range.
 */
bool cmd_args_connect(const char * const tokens[], uint32_t count, ble_gap_addr_t * p_target,
		      bool * p_have_target, uint32_t * p_timeout_ms);

/**
 * @brief Read the options of @c scan start, which follow the duration:
 *        name=, addr=, active= and rssi=, in any order.
 *
 * @param[in]  tokens    The command's tokens; the options start at the fourth.
 * @param[out] p_filter  Cleared, then filled in from the options.
 * @return False when a token is not a known option or its value is bad.
 */
bool cmd_args_scan_filter(const char * const tokens[], uint32_t count,
			  ble_scanner_filter_t * p_filter);

/**
 * @brief Decode hex text into bytes.
 *
 * @param[out] p_length  Bytes decoded.
 * @return False if the text is not valid hex or is too long for @p capacity.
 */
bool cmd_args_decode_hex(const char * text, uint8_t * buffer, uint32_t capacity,
			 uint16_t * p_length);

/**
 * @brief Encode bytes as hex text; @p text holds 2 * @p length + 1 characters.
 */
void cmd_args_encode_hex(const uint8_t * data, uint32_t length, char * text);

#ifdef __cplusplus
}
#endif

#endif /* CMD_ARGS_H__ */
