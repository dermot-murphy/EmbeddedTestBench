/**
 * @file cmd_fgen.h
 * @brief The frequency generator's commands: wr, routine and rd of a setting.
 *
 * Each function writes its whole reply line to the empty @p reply, except that
 * a @c routine @c freq @c results for every channel sends all but its last
 * line itself. protocol.h gives the forms.
 *
 * Traces to: PICO-FR-081 .. PICO-FR-084, PICO-DD-PARSER, PICO-DD-FGEN.
 */

#ifndef CMD_FGEN_H__
#define CMD_FGEN_H__

#include <stdbool.h>
#include <stdint.h>

#include "text.h"

#ifdef __cplusplus
extern "C" {
#endif

/** @return true if @p option names a generator setting. */
bool cmd_fgen_is_setting(const char *option);

/** @brief rd <setting> [<channel>]. @p argv[0] must name a setting. */
void cmd_fgen_rd(uint32_t argc, char *argv[], text_t *reply);

/** @brief wr <setting> [<channel>] <value>. */
void cmd_fgen_wr(uint32_t argc, char *argv[], text_t *reply);

/** @brief routine <routine> <verb> [<channel>]. */
void cmd_fgen_routine(uint32_t argc, char *argv[], text_t *reply);

#ifdef __cplusplus
}
#endif

#endif /* CMD_FGEN_H__ */
