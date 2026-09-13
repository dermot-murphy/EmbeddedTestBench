/**
 * @file cdc_acm.h
 * @brief The USB CDC ACM link to the host: line in, line out.
 *
 * Output is queued rather than written straight to the endpoint. A burst of
 * advertising reports - three channels, several sensors, 20 ms apart - arrives
 * faster than USB will take it, and blocking in the BLE event handler until the
 * endpoint drains would delay the next radio event and corrupt the very
 * measurement being made. So the handler queues and returns, the main loop
 * drains, and when the queue is full the line is *dropped and counted* rather
 * than silently truncated. A host that receives 480 of 500 events must be told,
 * because a profile computed from a lossy stream is wrong in a way that looks
 * plausible.
 *
 * Traces to: BLE-FR-003, BLE-FR-004, BLE-DD-CDC.
 */

#ifndef CDC_ACM_H__
#define CDC_ACM_H__

#include <stdbool.h>
#include <stdint.h>

#include "protocol.h"

#ifdef __cplusplus
extern "C" {
#endif

/** Lines buffered towards the host. */
#define CDC_TX_QUEUE_LINES		32U

/**
 * @brief Bring up USB and the CDC ACM class.
 *
 * @retval NRF_SUCCESS on success, otherwise the USB driver's error.
 */
uint32_t cdc_acm_init(void);

/**
 * @brief Service USB. Call from the main loop; never from an event handler.
 */
void cdc_acm_process(void);

/**
 * @brief Queue one line towards the host. The terminator is added here.
 *
 * Safe from any context. Never blocks.
 *
 * @param[in] line  NUL-terminated text without a terminator.
 * @retval true   queued
 * @retval false  dropped because the queue was full; the drop is counted
 */
bool cdc_acm_send_line(const char * line);

/**
 * @brief Queue a line built with printf formatting.
 *
 * @return As @ref cdc_acm_send_line. A result that would exceed
 *         @ref PROTO_MAX_EVENT is truncated rather than overrunning, and the
 *         truncation is visible in the log rather than silent.
 */
bool cdc_acm_send_format(const char * format, ...);

/**
 * @brief Take one complete line received from the host.
 *
 * @param[out] buffer  Destination, NUL terminated on success.
 * @param[in]  size    Size of @p buffer in bytes.
 * @retval true   a line was returned
 * @retval false  no complete line is waiting
 */
bool cdc_acm_take_line(char * buffer, uint32_t size);

/**
 * @brief Lines dropped because the transmit queue was full, since power-up.
 */
uint32_t cdc_acm_dropped(void);

/**
 * @brief True once the host has opened the port.
 */
bool cdc_acm_is_open(void);

#ifdef __cplusplus
}
#endif

#endif /* CDC_ACM_H__ */
