/**
 * @file cmd_parser.h
 * @brief The command dispatcher: one line in, one "ok" or "err" line out.
 *
 * Every command replies exactly once, even when it fails, so the host can match
 * replies to commands by position and a lost reply is a detectable fault rather
 * than a hang.
 *
 * Traces to: BLE-FR-002, BLE-DD-CMD.
 */

#ifndef CMD_PARSER_H__
#define CMD_PARSER_H__

#include <stdbool.h>
#include <stdint.h>

#include "protocol.h"

#ifdef __cplusplus
extern "C" {
#endif

/** Most tokens accepted after the command word. */
#define CMD_MAX_ARGS			6U

/**
 * @brief Attach the handlers to the command table. Call once at start-up.
 *
 * @retval true   every documented command has an implementation
 * @retval false  the tables disagree; the firmware should refuse to run rather
 *                than answer "unknown command" for a documented command
 */
bool cmd_parser_init(void);

/**
 * @brief Handle one command line from the host and send its reply.
 *
 * @param[in] line  NUL-terminated, without the terminator. Modified in place
 *                  while being split into tokens.
 */
void cmd_parser_handle(char * line);

#ifdef __cplusplus
}
#endif

#endif /* CMD_PARSER_H__ */
