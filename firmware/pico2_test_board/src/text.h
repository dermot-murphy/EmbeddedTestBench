/**
 * @file text.h
 * @brief A bounded line builder, so that no reply needs the C library's stdio.
 *
 * MISRA C:2012 Rule 21.6 excludes <stdio.h> from production code, and
 * snprintf's variadic interface (Rule 17.1) is the usual reason. Replies here
 * need only strings, unsigned decimals, fixed-point decimals and hex, so those
 * are provided and nothing else.
 *
 * Every append is bounded by the buffer. Text that does not fit is dropped and
 * the builder remembers that it overflowed, so a caller can refuse to send a
 * truncated reply rather than send a plausible-looking wrong one.
 *
 * Traces to: PICO-NFR-002, PICO-FR-027, PICO-DD-TEXT.
 */

#ifndef TEXT_H__
#define TEXT_H__

#include <stdbool.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/** A line being built into a caller-owned buffer. */
typedef struct
{
	char		*buffer;	/**< Destination, always NUL terminated. */
	uint32_t	capacity;	/**< Size of @c buffer, terminator included. */
	uint32_t	length;		/**< Characters written, terminator excluded. */
	bool		overflow;	/**< Something did not fit. */
} text_t;

/** Start an empty line in @p buffer of @p capacity bytes (at least 1). */
void text_init(text_t *text, char *buffer, uint32_t capacity);

/** Append one character. */
void text_char(text_t *text, char ch);

/** Append a NUL-terminated string. */
void text_str(text_t *text, const char *str);

/** Append a string with every space replaced by '_', so it stays one token. */
void text_token(text_t *text, const char *str);

/** Append an unsigned decimal. */
void text_u32(text_t *text, uint32_t value);

/** Append a signed value in thousandths as a decimal with three places,
 *  e.g. -1234 -> "-1.234", 5 -> "0.005". */
void text_milli(text_t *text, int32_t value);

/** Append a signed value in thousandths as a decimal with two places,
 *  rounded half away from zero, e.g. 22848 -> "22.85", -1234 -> "-1.23",
 *  -4 -> "0.00". A value that rounds to zero is never given a minus sign. */
void text_centi(text_t *text, int32_t milli);

/** Append "0x" and two upper-case hex digits. */
void text_hex8(text_t *text, uint8_t value);

/** Append "0x" and four upper-case hex digits. */
void text_hex16(text_t *text, uint16_t value);

#ifdef __cplusplus
}
#endif

#endif /* TEXT_H__ */
