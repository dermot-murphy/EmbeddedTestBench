/**
 * @file text.c
 * @brief A bounded line builder. See text.h.
 *
 * Traces to: PICO-NFR-002, PICO-FR-027, PICO-DD-TEXT.
 */

#include "text.h"

#include <stddef.h>

/** Digits in the largest uint32_t, 4294967295. */
#define TEXT_U32_DIGITS		10U

static const char	m_hex_digits[] = "0123456789ABCDEF";

void text_init(text_t *text, char *buffer, uint32_t capacity)
{
	if ((text != NULL) && (buffer != NULL) && (capacity > 0U))
	{
		text->buffer = buffer;
		text->capacity = capacity;
		text->length = 0U;
		text->overflow = false;
		text->buffer[0] = '\0';
	}
}

void text_char(text_t *text, char ch)
{
	if (text != NULL)
	{
		if ((text->length + 1U) < text->capacity)
		{
			text->buffer[text->length] = ch;
			text->length++;
			text->buffer[text->length] = '\0';
		}
		else
		{
			text->overflow = true;
		}
	}
}

void text_str(text_t *text, const char *str)
{
	if (str != NULL)
	{
		const char	*cursor = str;

		while (*cursor != '\0')
		{
			text_char(text, *cursor);
			cursor++;
		}
	}
}

void text_token(text_t *text, const char *str)
{
	if (str != NULL)
	{
		const char	*cursor = str;

		while (*cursor != '\0')
		{
			text_char(text, (*cursor == ' ') ? '_' : *cursor);
			cursor++;
		}
	}
}

void text_u32(text_t *text, uint32_t value)
{
	char		digits[TEXT_U32_DIGITS];
	uint32_t	count = 0U;
	uint32_t	remaining = value;

	/* Least significant first, then emitted in reverse. do-while so that
	 * zero produces one digit. */
	do
	{
		digits[count] = (char)('0' + (char)(remaining % 10U));
		count++;
		remaining /= 10U;
	} while ((remaining > 0U) && (count < TEXT_U32_DIGITS));

	while (count > 0U)
	{
		count--;
		text_char(text, digits[count]);
	}
}

void text_milli(text_t *text, int32_t value)
{
	uint32_t	magnitude;
	uint32_t	fraction;

	if (value < 0)
	{
		text_char(text, '-');
		/* Negate in unsigned arithmetic: well defined for INT32_MIN too. */
		magnitude = 0U - (uint32_t)value;
	}
	else
	{
		magnitude = (uint32_t)value;
	}

	text_u32(text, magnitude / 1000U);
	text_char(text, '.');
	fraction = magnitude % 1000U;
	text_char(text, (char)('0' + (char)(fraction / 100U)));
	text_char(text, (char)('0' + (char)((fraction / 10U) % 10U)));
	text_char(text, (char)('0' + (char)(fraction % 10U)));
}

void text_centi(text_t *text, int32_t milli)
{
	uint32_t	magnitude;
	uint32_t	centi;

	/* Round the magnitude, then decide the sign, so that -0.004 is "0.00"
	 * and not "-0.00". Negated in unsigned arithmetic: well defined for
	 * INT32_MIN, and 2147483648 + 5 still fits in a uint32_t. */
	magnitude = (milli < 0) ? (0U - (uint32_t)milli) : (uint32_t)milli;
	centi = (magnitude + 5U) / 10U;

	if ((milli < 0) && (centi > 0U))
	{
		text_char(text, '-');
	}
	text_u32(text, centi / 100U);
	text_char(text, '.');
	text_char(text, (char)('0' + (char)((centi / 10U) % 10U)));
	text_char(text, (char)('0' + (char)(centi % 10U)));
}

/* "0x" then the low @p bits of @p value, most significant nibble first. */
static void text_hex(text_t *text, uint32_t value, uint32_t bits)
{
	uint32_t	shift = bits;

	text_str(text, "0x");
	while (shift > 0U)
	{
		shift -= 4U;
		text_char(text, m_hex_digits[(value >> shift) & 0x0FU]);
	}
}

void text_hex8(text_t *text, uint8_t value)
{
	text_hex(text, (uint32_t)value, 8U);
}

void text_hex16(text_t *text, uint16_t value)
{
	text_hex(text, (uint32_t)value, 16U);
}
