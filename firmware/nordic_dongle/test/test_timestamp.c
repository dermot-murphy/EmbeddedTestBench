/**
 * @file test_timestamp.c
 * @brief The microsecond clock, including the wrap it takes 71 minutes to reach.
 *
 * Traces to: BLE-FR-010, BLE-DD-TIMESTAMP, SWE4-UT-FWUNIT.
 */

#include "unity.h"

#include "nrfx_timer.h"
#include "timestamp.h"

/* The module initialises once, as it does on the target: there is no way to
 * un-initialise it, and inventing one for the tests would be testing something
 * the firmware does not do. So the fake is *not* wiped between tests - that
 * would strand the module with a handler the fake has forgotten - and the two
 * tests that must run before initialisation are run first, deliberately.
 * Everything after them is order-independent, the wrap tests included: they
 * measure a delta rather than an absolute. */
void setUp(void)
{
	fake_timer_set_counter(0U);
}

void tearDown(void)
{
}

static void test_the_clock_runs_at_one_megahertz(void)
{
	/* Not app_timer's 32.768 kHz: 30.5 us is the same order as the jitter
	 * this clock exists to measure. */
	TEST_ASSERT_EQUAL_UINT32(NRF_SUCCESS, timestamp_init());
	TEST_ASSERT_EQUAL(NRF_TIMER_FREQ_1MHz, fake_timer_config()->frequency);
	TEST_ASSERT_EQUAL(NRF_TIMER_MODE_TIMER, fake_timer_config()->mode);
	TEST_ASSERT_EQUAL(NRF_TIMER_BIT_WIDTH_32, fake_timer_config()->bit_width);
	TEST_ASSERT_EQUAL_UINT32(1000000UL, TIMESTAMP_HZ);
}

static void test_the_timer_is_enabled_and_wraps_at_the_full_range(void)
{
	(void)timestamp_init();
	TEST_ASSERT_TRUE(fake_timer_is_enabled());
	TEST_ASSERT_EQUAL_HEX32(0xFFFFFFFFUL, fake_timer_compare_value());
	TEST_ASSERT_EQUAL_HEX32(NRF_TIMER_SHORT_COMPARE0_CLEAR_MASK, fake_timer_compare_shorts());
}

static void test_it_reads_the_hardware_counter(void)
{
	(void)timestamp_init();
	fake_timer_set_counter(123456U);
	TEST_ASSERT_EQUAL_UINT64(123456U, timestamp_now_us());
}

static void test_before_initialisation_it_reads_zero(void)
{
	/* Zero rather than a stale figure: nothing has been timed yet. */
	TEST_ASSERT_EQUAL_UINT64(0U, timestamp_now_us());
}

static void test_initialising_twice_is_harmless(void)
{
	TEST_ASSERT_EQUAL_UINT32(NRF_SUCCESS, timestamp_init());
	fake_timer_set_counter(7U);
	TEST_ASSERT_EQUAL_UINT32(NRF_SUCCESS, timestamp_init());
	TEST_ASSERT_EQUAL_UINT64(7U, timestamp_now_us());
}

static void test_a_driver_failure_is_returned(void)
{
	fake_timer_set_init_result(NRF_ERROR_INVALID_STATE);
	TEST_ASSERT_EQUAL_UINT32(NRF_ERROR_INVALID_STATE, timestamp_init());
	fake_timer_set_init_result(NRF_SUCCESS);
}

static void test_the_counter_is_extended_past_thirty_two_bits(void)
{
	/* At 1 MHz the hardware counter wraps every 71.6 minutes, which is well
	 * inside a soak test. The figures are relative because wraps accumulate
	 * for the life of the process, as they do for the life of the dongle. */
	uint64_t before;

	(void)timestamp_init();
	fake_timer_set_counter(0xFFFFFFFFUL);
	before = timestamp_now_us();

	fake_timer_fire_compare();               /* the wrap interrupt */
	fake_timer_set_counter(5U);
	TEST_ASSERT_EQUAL_UINT64(before + 6ULL, timestamp_now_us());
}

static void test_several_wraps_accumulate(void)
{
	uint64_t before;
	uint32_t index;

	(void)timestamp_init();
	fake_timer_set_counter(0U);
	before = timestamp_now_us();

	for (index = 0U; index < 3U; index++)
	{
		fake_timer_fire_compare();
	}
	fake_timer_set_counter(1U);
	TEST_ASSERT_EQUAL_UINT64(before + (3ULL << 32) + 1ULL, timestamp_now_us());
}

static void test_time_never_goes_backwards_across_a_wrap(void)
{
	uint64_t before;
	uint64_t after;

	(void)timestamp_init();
	fake_timer_set_counter(0xFFFFFFF0UL);
	before = timestamp_now_us();
	fake_timer_fire_compare();
	fake_timer_set_counter(0x10U);
	after = timestamp_now_us();
	TEST_ASSERT_TRUE(after > before);
}

static void test_elapsed_is_the_difference(void)
{
	TEST_ASSERT_EQUAL_UINT64(64000U, timestamp_elapsed_us(1000U, 65000U));
}

static void test_elapsed_backwards_is_zero_not_a_huge_number(void)
{
	/* Unsigned subtraction the other way round yields 18 million years. */
	TEST_ASSERT_EQUAL_UINT64(0U, timestamp_elapsed_us(65000U, 1000U));
	TEST_ASSERT_EQUAL_UINT64(0U, timestamp_elapsed_us(5U, 5U));
}

int main(void)
{
	UNITY_BEGIN();

	/* These two must run before the module is initialised. */
	RUN_TEST(test_before_initialisation_it_reads_zero);
	RUN_TEST(test_a_driver_failure_is_returned);

	RUN_TEST(test_the_clock_runs_at_one_megahertz);
	RUN_TEST(test_the_timer_is_enabled_and_wraps_at_the_full_range);
	RUN_TEST(test_it_reads_the_hardware_counter);
	RUN_TEST(test_initialising_twice_is_harmless);
	RUN_TEST(test_the_counter_is_extended_past_thirty_two_bits);
	RUN_TEST(test_several_wraps_accumulate);
	RUN_TEST(test_time_never_goes_backwards_across_a_wrap);
	RUN_TEST(test_elapsed_is_the_difference);
	RUN_TEST(test_elapsed_backwards_is_zero_not_a_huge_number);
	return UNITY_END();
}
