/**
 * @file cmd_dfu.h
 * @brief The host commands that carry a DFU transfer: dfucp and dfupkt.
 *
 * Kept apart from cmd_parser.c so that stays under the 800-line limit.
 *
 * Traces to: BLE-FR-121, BLE-DD-DFU.
 */

#ifndef CMD_DFU_H__
#define CMD_DFU_H__

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief @c dfucp @c <hex> @c [timeout=<ms>]: write the Control Point and
 *        report its response as @c ok @c len=<n> @c data=<hex>.
 */
void cmd_dfu_control(char * tokens[], uint32_t count);

/**
 * @brief @c dfupkt @c <hex>: write the Packet characteristic.
 */
void cmd_dfu_packet(char * tokens[], uint32_t count);

#ifdef __cplusplus
}
#endif

#endif /* CMD_DFU_H__ */
