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

#ifdef __cplusplus
extern "C" {
#endif

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
bool cmd_args_connect(char * tokens[], uint32_t count, ble_gap_addr_t * p_target,
		      bool * p_have_target, uint32_t * p_timeout_ms);

#ifdef __cplusplus
}
#endif

#endif /* CMD_ARGS_H__ */
