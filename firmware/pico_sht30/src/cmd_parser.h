/**
 * @file cmd_parser.h
 * @brief Line assembly and command dispatch for the host link.
 *
 * Characters arrive one at a time from USB. cmd_line_push() assembles them
 * into a line; cmd_execute() splits a complete line into tokens, looks the
 * first one up in PROTO_COMMAND_TABLE, checks the argument count, runs the
 * handler and sends exactly one "ok ..." or "err ..." reply.
 *
 * Traces to: PICO-FR-001, PICO-FR-003, PICO-FR-004, PICO-DD-PARSER.
 */

#ifndef CMD_PARSER_H__
#define CMD_PARSER_H__

#include <stdbool.h>
#include <stdint.h>

#include "protocol.h"

#ifdef __cplusplus
extern "C" {
#endif

/** What a character did to the line being assembled. */
typedef enum
{
	CMD_LINE_PENDING = 0,	/**< More characters needed. */
	CMD_LINE_READY,		/**< A complete line is in @c text. */
	CMD_LINE_OVERFLOW	/**< A line ended that was too long; it was dropped. */
} cmd_line_result_t;

/** A line being assembled. */
typedef struct
{
	char		text[PROTO_MAX_LINE];	/**< NUL terminated when READY. */
	uint32_t	length;			/**< Characters held. */
	bool		discarding;		/**< Over length: drop to the next LF. */
} cmd_line_t;

/**
 * @brief Start an empty line.
 */
void cmd_line_init(cmd_line_t *line);

/**
 * @brief Add one received character.
 *
 * CR is ignored, so CRLF and LF both end a line. A line longer than
 * PROTO_MAX_LINE - 1 characters is discarded whole - never executed in part -
 * and reported as CMD_LINE_OVERFLOW when its LF arrives.
 */
cmd_line_result_t cmd_line_push(cmd_line_t *line, char ch);

/**
 * @brief Execute one complete command line, sending its reply.
 *
 * @p line is tokenised in place. A blank line produces no reply.
 */
void cmd_execute(char *line);

/**
 * @brief Send the reply for a line that was too long.
 */
void cmd_report_overflow(void);

#ifdef __cplusplus
}
#endif

#endif /* CMD_PARSER_H__ */
