/**
 * @file cmd.h
 * @brief The host's commands, and the records sent while receiving (#84).
 *
 *   id                      ok etb-s2lp-kit <version> proto=<n> silicon=<hex>
 *   rd <addr> <count>       ok <hex>              count 1 .. 128
 *   wr <addr> <hex>         ok                    1 .. 128 bytes
 *   cmd <code>              ok <status hex>       a command strobe
 *   sdn <0|1>               ok                    1 holds the radio in shutdown
 *   rx start [<addr>,...]   ok                    registers read after each frame
 *   rx stop                 ok frames=<n> rejects=<n> overflows=<n> deaf_max_us=<n>
 *   stat                    ok running=<0|1> frames=<n> rejects=<n> overflows=<n> deaf_max_us=<n> queued=<n>
 *
 * Addresses, codes and data are hexadecimal; counts are decimal. While
 * receiving, only rx, stat and id are taken; the others answer "err receiving".
 */

#ifndef CMD_H
#define CMD_H

#include <stdint.h>

#include "ring.h"

/** Longest line the firmware sends, line end included. */
#define CMD_OUT_MAX             (340U)

/** Carry out one command line (without its line end) and send the answer. */
void cmd_handle_line(char *line);

/**
 * @brief Format a record as the line the host reads, line end included.
 * @return The length written to out, which holds CMD_OUT_MAX bytes.
 */
uint32_t cmd_format_record(const ring_record_t *record, char *out);

#endif /* CMD_H */
