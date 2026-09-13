/**
 * @file timestamp.h
 * @brief A free-running microsecond clock for timing radio events.
 *
 * Why not @c app_timer: it counts 32.768 kHz RTC ticks, so it resolves 30.5 us
 * and is the same order as the jitter being measured. A TIMER peripheral at
 * 1 MHz resolves one microsecond, which is two orders below a 20 ms
 * advertising interval - enough for the interval statistics to be about the
 * sensor rather than about the instrument.
 *
 * The hardware counter is 32-bit and wraps every 71.6 minutes at 1 MHz. It is
 * extended to 64 bits by counting overflows in the interrupt, so a profile
 * lasting hours does not fold back on itself.
 *
 * Traces to: BLE-FR-010, BLE-DD-TIMESTAMP.
 */

#ifndef TIMESTAMP_H__
#define TIMESTAMP_H__

#include <stdint.h>
#include "nrf_error.h"

#ifdef __cplusplus
extern "C" {
#endif

/** Ticks per second of the timestamp clock. One tick is one microsecond. */
#define TIMESTAMP_HZ			1000000UL

/**
 * @brief Start the timestamp clock. Idempotent.
 *
 * @retval NRF_SUCCESS on success, otherwise the driver's error.
 */
uint32_t timestamp_init(void);

/**
 * @brief The current timestamp in microseconds since @ref timestamp_init.
 *
 * Safe from any context, including an interrupt of higher priority than the
 * timer's own: the overflow count is re-read and the capture repeated if it
 * changed, so a read that straddles an overflow cannot return a stale figure.
 */
uint64_t timestamp_now_us(void);

/**
 * @brief Microseconds elapsed between two timestamps.
 *
 * @param[in] start  Earlier timestamp.
 * @param[in] end    Later timestamp.
 * @return @c end - @c start, or 0 if @c end precedes @c start.
 */
uint64_t timestamp_elapsed_us(uint64_t start, uint64_t end);

#ifdef __cplusplus
}
#endif

#endif /* TIMESTAMP_H__ */
