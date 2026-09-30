/**
 * @file test_firmware_version.c
 * @brief The build date a build reports when nothing injected one.
 *
 * test_cmd_parser covers the injected date. This binary is compiled without
 * FIRMWARE_BUILD_DATE, as an IDE build is, so it sees the fallback that
 * firmware_version.c assembles from the compiler's own macros.
 *
 * Traces to: BLE-FR-012, BLE-DD-VERSION, SWE4-UT-FWUNIT.
 */

#include <string.h>

#include "unity.h"

#include "firmware_version.h"

void setUp(void)
{
}

void tearDown(void)
{
}

static void test_the_fallback_date_carries_no_spaces(void)
{
	/* The link splits fields on spaces; the compiler's macros contain them,
	 * and a day before the tenth contains two. Observed on a dongle built by
	 * SES: the host reported the build date as "local:Sep". */
	TEST_ASSERT_NULL(strchr(firmware_build_date(), ' '));
}

static void test_the_fallback_date_is_tagged_as_local_time(void)
{
	TEST_ASSERT_EQUAL_INT(0, strncmp(firmware_build_date(), "local:", 6));
}

static void test_the_fallback_date_keeps_every_part_of_the_macros(void)
{
	/* "local:Sep-05-2026T20:13:52". The shape is checked rather than the
	 * value: firmware_version.c was compiled at its own moment, and comparing
	 * against this file's __TIME__ would fail whenever the two straddled a
	 * second. */
	static const char	shape[] = "local:aaa-99-9999T99:99:99";
	size_t			index;

	TEST_ASSERT_EQUAL_size_t(strlen(shape), strlen(firmware_build_date()));
	for (index = 6U; index < strlen(shape); index++)
	{
		const char	want = shape[index];
		const char	got = firmware_build_date()[index];

		if (want == '9')
		{
			TEST_ASSERT_TRUE_MESSAGE((got >= '0') && (got <= '9'), "digit expected");
		}
		else if (want == 'a')
		{
			TEST_ASSERT_TRUE_MESSAGE(((got >= 'A') && (got <= 'Z')) || ((got >= 'a') && (got <= 'z')),
						 "month letter expected");
		}
		else
		{
			TEST_ASSERT_EQUAL_CHAR(want, got);
		}
	}
}

int main(void)
{
	UNITY_BEGIN();
	RUN_TEST(test_the_fallback_date_carries_no_spaces);
	RUN_TEST(test_the_fallback_date_is_tagged_as_local_time);
	RUN_TEST(test_the_fallback_date_keeps_every_part_of_the_macros);
	return UNITY_END();
}
