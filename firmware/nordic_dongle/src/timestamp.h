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

/** Characters needed for any 64-bit count: 20 digits and the terminator. */
#define TIMESTAMP_TEXT_SIZE		21U

/**
 * @brief Write a microsecond count as decimal text, for a @c %s in a format.
 *
 * Every timestamp the host reads is a 64-bit count, and a long long
 * conversion cannot carry it: newlib-nano's printf, which the Makefile build
 * links, has no long long support and prints "lu" (#256). Formatting here keeps the image
 * small and correct whatever library it links.
 *
 * @param[in]  value_us  The count to write.
 * @param[out] p_text    At least @ref TIMESTAMP_TEXT_SIZE characters.
 * @return @p p_text, so the call can stand in a format's argument list.
 */
static inline const char * timestamp_format_us(uint64_t value_us, char * p_text)
{
	char		reversed[TIMESTAMP_TEXT_SIZE];
	uint32_t	count = 0U;
	uint32_t	index;

	do
	{
		reversed[count] = (char)('0' + (char)(value_us % 10U));
		value_us /= 10U;
		count++;
	} while (value_us != 0U);

	for (index = 0U; index < count; index++)
	{
		p_text[index] = reversed[count - 1U - index];
	}
	p_text[count] = '\0';

	return p_text;
}

#ifdef __cplusplus
}
#endif

#endif /* TIMESTAMP_H__ */
