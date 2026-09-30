/**
 * @file test_text.c
 * @brief The bounded line builder: formats, and what happens when it is full.
 *
 * Traces to: PICO-NFR-002, PICO-DD-TEXT, SWE4-UT-PICOFW.
 */

#include "unity.h"

#include <stdint.h>

#include "text.h"

static char	m_buffer[32];
static text_t	text;

void setUp(void)
{
	text_init(&text, m_buffer, (uint32_t)sizeof(m_buffer));
}

void tearDown(void)
{
}

static void test_a_new_line_is_empty_and_terminated(void)
{
	TEST_ASSERT_EQUAL_STRING("", m_buffer);
	TEST_ASSERT_EQUAL_UINT32(0U, text.length);
	TEST_ASSERT_FALSE(text.overflow);
}

static void test_strings_and_characters_append(void)
{
	text_str(&text, "ok");
	text_char(&text, ' ');
	text_str(&text, "t=");
	TEST_ASSERT_EQUAL_STRING("ok t=", m_buffer);
}

static void test_a_token_has_no_spaces(void)
{
	/* The fallback build date is "local:Sep 30 2026T12:00:00". */
	text_token(&text, "local:Sep 30 2026T12:00:00");
	TEST_ASSERT_EQUAL_STRING("local:Sep_30_2026T12:00:00", m_buffer);
}

static void test_unsigned_decimals(void)
{
	text_u32(&text, 0U);
	text_char(&text, ' ');
	text_u32(&text, 7U);
	text_char(&text, ' ');
	text_u32(&text, 4294967295UL);
	TEST_ASSERT_EQUAL_STRING("0 7 4294967295", m_buffer);
}

static void test_milli_units_have_three_places(void)
{
	text_milli(&text, 23451);
	text_char(&text, ' ');
	text_milli(&text, 5);
	text_char(&text, ' ');
	text_milli(&text, 0);
	TEST_ASSERT_EQUAL_STRING("23.451 0.005 0.000", m_buffer);
}

static void test_negative_milli_units_carry_the_sign(void)
{
	/* -0.5 must not print as "0.500": the sign is on the whole value. */
	text_milli(&text, -500);
	text_char(&text, ' ');
	text_milli(&text, -45000);
	text_char(&text, ' ');
	text_milli(&text, -1249);
	TEST_ASSERT_EQUAL_STRING("-0.500 -45.000 -1.249", m_buffer);
}

static void test_the_most_negative_value_is_formatted(void)
{
	text_milli(&text, INT32_MIN);
	TEST_ASSERT_EQUAL_STRING("-2147483.648", m_buffer);
}

static void test_hex_is_upper_case_and_fixed_width(void)
{
	text_hex16(&text, 0x6A3CU);
	text_char(&text, ' ');
	text_hex16(&text, 0x0010U);
	text_char(&text, ' ');
	text_hex8(&text, 0x44U);
	TEST_ASSERT_EQUAL_STRING("0x6A3C 0x0010 0x44", m_buffer);
}

static void test_overflow_is_bounded_and_remembered(void)
{
	char	small[6];
	text_t	tiny;

	text_init(&tiny, small, (uint32_t)sizeof(small));
	text_str(&tiny, "abcdefgh");
	TEST_ASSERT_EQUAL_STRING("abcde", small);
	TEST_ASSERT_EQUAL_UINT32(5U, tiny.length);
	TEST_ASSERT_TRUE(tiny.overflow);
}

static void test_null_arguments_are_ignored(void)
{
	text_str(&text, NULL);
	text_token(&text, NULL);
	text_char(NULL, 'x');
	text_init(NULL, m_buffer, 4U);
	TEST_ASSERT_EQUAL_STRING("", m_buffer);
}

int main(void)
{
	UNITY_BEGIN();
	RUN_TEST(test_a_new_line_is_empty_and_terminated);
	RUN_TEST(test_strings_and_characters_append);
	RUN_TEST(test_a_token_has_no_spaces);
	RUN_TEST(test_unsigned_decimals);
	RUN_TEST(test_milli_units_have_three_places);
	RUN_TEST(test_negative_milli_units_carry_the_sign);
	RUN_TEST(test_the_most_negative_value_is_formatted);
	RUN_TEST(test_hex_is_upper_case_and_fixed_width);
	RUN_TEST(test_overflow_is_bounded_and_remembered);
	RUN_TEST(test_null_arguments_are_ignored);
	return UNITY_END();
}
