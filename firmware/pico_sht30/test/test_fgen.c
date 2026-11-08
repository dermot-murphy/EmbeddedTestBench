/**
 * @file test_fgen.c
 * @brief The frequency generator and its commands, through the fake HAL.
 *
 * Traces to: PICO-FR-080 .. PICO-FR-089, PICO-DD-FGEN, SWE4-UT-PICOFW.
 */

#include "unity.h"

#include <stdbool.h>
#include <string.h>

#include "cmd_parser.h"
#include "fake_hal.h"
#include "fgen.h"

/* Frames in the buffers the tests render into. */
#define TEST_FRAMES	1024U

/* One 1 kHz cycle at 97 656.25 Hz, rounded up. */
#define TEST_FRAMES_PER_KHZ_CYCLE	98U

static int32_t	test_m_samples[TEST_FRAMES * 2U];

static void test_run(const char *command)
{
	char	buffer[PROTO_MAX_LINE];

	(void)strcpy(buffer, command);
	cmd_execute(buffer);
}

static void test_expect(const char *command, const char *reply)
{
	test_run(command);
	TEST_ASSERT_EQUAL_STRING(reply, fake_hal_last_line());
}

static void test_render(void)
{
	fgen_render(test_m_samples, TEST_FRAMES);
}

/* The largest magnitude in channel @p index (0 is left), as a fraction of
 * full scale. */
static double test_peak(uint32_t index)
{
	double		peak = 0.0;
	uint32_t	frame;

	for (frame = 0U; frame < TEST_FRAMES; frame++)
	{
		double	value = (double)test_m_samples[(frame * 2U) + index] / 2147483648.0;
		double	magnitude = (value < 0.0) ? -value : value;

		if (magnitude > peak)
		{
			peak = magnitude;
		}
	}
	return peak;
}

void setUp(void)
{
	fake_hal_reset();
	fgen_init();
}

void tearDown(void)
{
}

/* --- rate and arithmetic ------------------------------------------------- */
static void test_the_sample_rate_is_an_integer_division_of_the_clock(void)
{
	TEST_ASSERT_EQUAL_UINT64(97656250ULL, FGEN_SAMPLE_RATE_MHZ);
}

static void test_harmonics_stop_at_the_dac_pass_band(void)
{
	TEST_ASSERT_EQUAL_UINT32(3U, fgen_harmonics(12000000UL));
	TEST_ASSERT_EQUAL_UINT32(43U, fgen_harmonics(1000000UL));
}

static void test_harmonics_are_capped_at_low_frequency(void)
{
	TEST_ASSERT_EQUAL_UINT32(256U, fgen_harmonics(10000UL));
}

static void test_pwm_at_the_top_of_the_range_is_exact(void)
{
	hal_pwm_config_t	config;

	TEST_ASSERT_EQUAL_UINT32(12000000UL, fgen_pwm_config(12000000UL, 50000UL, &config));
	TEST_ASSERT_EQUAL_UINT32(16U, config.divider);
	TEST_ASSERT_EQUAL_UINT32(12499U, config.top);
	TEST_ASSERT_EQUAL_UINT32(6250U, config.level);
}

static void test_pwm_reaches_the_bottom_of_the_range(void)
{
	hal_pwm_config_t	config;
	uint32_t		actual = fgen_pwm_config(10000UL, 50000UL, &config);

	TEST_ASSERT_UINT32_WITHIN(10U, 10000UL, actual);
	TEST_ASSERT_TRUE(config.divider <= 4095U);
	TEST_ASSERT_TRUE(config.top <= 65535U);
}

static void test_pwm_duty(void)
{
	hal_pwm_config_t	config;

	(void)fgen_pwm_config(1000000UL, 25000UL, &config);
	TEST_ASSERT_EQUAL_UINT32((config.top + 1U) / 4U, config.level);
}

/* --- wr and rd ----------------------------------------------------------- */
static void test_defaults(void)
{
	test_expect("rd freq", "ACK rd freq 1 = 1000.00");
	test_expect("rd freq2", "ACK rd freq2 1 = 2000.00");
	test_expect("rd wave", "ACK rd wave 1 = square");
	test_expect("rd duty", "ACK rd duty 1 = 50.00");
	test_expect("rd amp", "ACK rd amp 1 = 100.00");
	test_expect("rd ratio", "ACK rd ratio 1 = 0.50");
	test_expect("rd cycles", "ACK rd cycles 1 = 0");
}

static void test_wr_with_no_channel_means_channel_1(void)
{
	test_expect("wr freq 5k", "ACK wr freq 1 = 5000.00");
	test_expect("rd freq 1", "ACK rd freq 1 = 5000.00");
	test_expect("rd freq 2", "ACK rd freq 2 = 1000.00");
}

static void test_wr_a_named_channel(void)
{
	test_expect("wr freq 2 2500", "ACK wr freq 2 = 2500.00");
	test_expect("rd freq 2", "ACK rd freq 2 = 2500.00");
	test_expect("rd freq", "ACK rd freq 1 = 1000.00");
}

static void test_frequency_forms(void)
{
	test_expect("wr freq 1.5k", "ACK wr freq 1 = 1500.00");
	test_expect("wr freq 12K", "ACK wr freq 1 = 12000.00");
	test_expect("wr freq 999.98", "ACK wr freq 1 = 999.98");
	test_expect("wr freq 10", "ACK wr freq 1 = 10.00");
}

static void test_frequency_range_is_refused_not_clamped(void)
{
	test_expect("wr freq 20k", "NAK wr freq 1 = Error");
	test_expect("wr freq 12000.001", "NAK wr freq 1 = Error");
	test_expect("wr freq 9.999", "NAK wr freq 1 = Error");
	test_expect("rd freq", "ACK rd freq 1 = 1000.00");
}

static void test_malformed_numbers_are_refused(void)
{
	test_expect("wr freq k", "NAK wr freq 1 = Error");
	test_expect("wr freq 1k5", "NAK wr freq 1 = Error");
	test_expect("wr freq 1.2.3", "NAK wr freq 1 = Error");
	test_expect("wr freq 1.2345", "NAK wr freq 1 = Error");
	test_expect("wr freq 99999999999999", "NAK wr freq 1 = Error");
	test_expect("wr duty 5k", "NAK wr duty 1 = Error");
	test_expect("wr cycles 1.5", "NAK wr cycles 1 = Error");
	test_expect("wr cycles 4294967296", "NAK wr cycles 1 = Error");
}

static void test_duty_range(void)
{
	test_expect("wr duty 25", "ACK wr duty 1 = 25.00");
	test_expect("wr duty 0.5", "NAK wr duty 1 = Error");
	test_expect("wr duty 99.5", "NAK wr duty 1 = Error");
}

static void test_amp_and_ratio_range(void)
{
	test_expect("wr amp 0", "ACK wr amp 1 = 0.00");
	test_expect("wr amp 100.001", "NAK wr amp 1 = Error");
	test_expect("wr ratio 0.2", "ACK wr ratio 1 = 0.20");
	test_expect("wr ratio 1.001", "NAK wr ratio 1 = Error");
}

static void test_every_wave_name(void)
{
	test_expect("wr wave sine", "ACK wr wave 1 = sine");
	test_expect("wr wave triangle", "ACK wr wave 1 = triangle");
	test_expect("wr wave sawtooth", "ACK wr wave 1 = sawtooth");
	test_expect("wr wave sine2", "ACK wr wave 1 = sine2");
	test_expect("wr wave square", "ACK wr wave 1 = square");
	test_expect("wr wave pulse", "NAK wr wave 1 = Error");
}

static void test_the_gpio_channel_is_square_only(void)
{
	test_expect("wr wave 3 square", "ACK wr wave 3 = square");
	test_expect("wr wave 3 sine", "NAK wr wave 3 = Error");
	test_expect("wr amp 3 50", "NAK wr amp 3 = Error");
	test_expect("wr freq2 3 100", "NAK wr freq2 3 = Error");
	test_expect("wr ratio 3 0.5", "NAK wr ratio 3 = Error");
	test_expect("wr duty 3 10", "ACK wr duty 3 = 10.00");
}

static void test_a_bad_channel_is_refused(void)
{
	test_expect("wr freq 9 1000", "NAK wr freq 9 = Error");
	test_expect("wr freq x 1000", "NAK wr freq x = Error");
	test_expect("rd freq 0", "NAK rd freq 0 = Error");
	test_expect("rd freq 12", "NAK rd freq 12 = Error");
}

static void test_an_unknown_setting_is_refused(void)
{
	test_expect("wr bogus 1", "NAK wr bogus = Error");
}

static void test_wr_argument_counts(void)
{
	test_expect("wr freq", "err 2 wrong number of arguments");
	test_expect("wr freq 1 2 3", "err 2 wrong number of arguments");
}

static void test_rd_identity_takes_no_channel(void)
{
	test_expect("rd name 1", "err 2 wrong number of arguments");
}

/* --- routine ------------------------------------------------------------- */
static void test_results_before_any_start(void)
{
	test_expect("routine freq results 1", "ACK routine freq results 1 = Not Started");
}

static void test_results_for_every_channel(void)
{
	test_run("wr freq 2 500");
	test_run("wr wave 2 sine");
	test_run("routine freq start 2");
	fake_hal_reset();
	test_run("routine freq results");
	TEST_ASSERT_EQUAL_UINT32(3U, fake_hal_line_count());
	TEST_ASSERT_EQUAL_STRING("ACK routine freq results 1 = Not Started", fake_hal_line(0U));
	TEST_ASSERT_EQUAL_STRING("ACK routine freq results 2 = Running, sine, 500.00 Hz", fake_hal_line(1U));
	TEST_ASSERT_EQUAL_STRING("ACK routine freq results 3 = Not Started", fake_hal_line(2U));
}

static void test_start_with_no_channel_means_channel_1(void)
{
	test_expect("routine freq start", "ACK routine freq start 1 = Running");
	test_expect("routine freq results 1", "ACK routine freq results 1 = Running, square, 1000.00 Hz");
}

static void test_a_continuous_run_cannot_be_restarted(void)
{
	test_expect("routine freq start 1", "ACK routine freq start 1 = Running");
	test_expect("routine freq start 1", "NAK routine freq start 1 = Error");
	test_expect("routine freq abort 1", "ACK routine freq abort 1 = Aborted");
	test_expect("routine freq start 1", "ACK routine freq start 1 = Running");
}

static void test_a_finite_run_can_be_restarted_with_new_settings(void)
{
	test_run("wr wave 1 sine");
	test_run("wr cycles 1 1000");
	test_expect("routine freq start 1", "ACK routine freq start 1 = Running");
	test_run("wr freq 1 2000");
	test_expect("routine freq start 1", "ACK routine freq start 1 = Running");
	test_expect("routine freq results 1", "ACK routine freq results 1 = Running, sine, 2000.00 Hz");
}

static void test_wr_does_not_change_a_running_channel(void)
{
	test_run("wr wave 1 sine");
	test_run("routine freq start 1");
	test_expect("wr freq 1 2000", "ACK wr freq 1 = 2000.00");
	test_expect("routine freq results 1", "ACK routine freq results 1 = Running, sine, 1000.00 Hz");
	test_expect("rd freq 1", "ACK rd freq 1 = 2000.00");
}

static void test_abort_leaves_a_channel_aborted(void)
{
	test_run("wr wave 1 sine");
	test_run("routine freq start 1");
	test_expect("routine freq abort 1", "ACK routine freq abort 1 = Aborted");
	test_expect("routine freq results 1", "ACK routine freq results 1 = Aborted, sine, 1000.00 Hz");
}

static void test_abort_does_not_touch_a_channel_that_never_ran(void)
{
	test_run("routine freq abort 2");
	test_expect("routine freq results 2", "ACK routine freq results 2 = Not Started");
}

static void test_abort_with_no_channel_stops_every_channel(void)
{
	test_run("routine freq start 1");
	test_run("routine freq start 3");
	test_expect("routine freq abort", "ACK routine freq abort = Aborted");
	TEST_ASSERT_EQUAL_INT((int)FGEN_STATE_ABORTED, (int)fgen_state(1U));
	TEST_ASSERT_EQUAL_INT((int)FGEN_STATE_ABORTED, (int)fgen_state(3U));
	TEST_ASSERT_FALSE(fake_hal_pwm_running());
}

static void test_routine_all_abort(void)
{
	test_run("routine freq start 2");
	test_expect("routine all abort", "ACK routine all abort = Aborted");
	TEST_ASSERT_EQUAL_INT((int)FGEN_STATE_ABORTED, (int)fgen_state(2U));
}

static void test_bad_routines_are_refused(void)
{
	test_expect("routine freq start 9", "NAK routine freq start 9 = Error");
	test_expect("routine freq abort 9", "NAK routine freq abort 9 = Error");
	test_expect("routine freq results 9", "NAK routine freq results 9 = Error");
	test_expect("routine freq stop", "NAK routine freq stop = Error");
	test_expect("routine temp start", "NAK routine temp start = Error");
	test_expect("routine all start", "NAK routine all start = Error");
	test_expect("routine all abort 1", "NAK routine all abort 1 = Error");
}

static void test_routine_argument_counts(void)
{
	test_expect("routine freq", "err 2 wrong number of arguments");
}

/* --- synthesis ----------------------------------------------------------- */
static void test_outputs_are_silent_before_a_start(void)
{
	test_render();
	TEST_ASSERT_EQUAL_FLOAT(0.0F, (float)test_peak(0U));
	TEST_ASSERT_EQUAL_FLOAT(0.0F, (float)test_peak(1U));
}

static void test_a_full_scale_sine_reaches_full_scale_without_clipping(void)
{
	test_run("wr wave 1 sine");
	test_run("routine freq start 1");
	test_render();
	TEST_ASSERT_FLOAT_WITHIN(0.01F, 1.0F, (float)test_peak(0U));
	TEST_ASSERT_EQUAL_FLOAT(0.0F, (float)test_peak(1U));
}

static void test_amplitude_scales_the_output(void)
{
	test_run("wr wave 2 sine");
	test_run("wr amp 2 25");
	test_run("routine freq start 2");
	test_render();
	TEST_ASSERT_FLOAT_WITHIN(0.01F, 0.25F, (float)test_peak(1U));
	TEST_ASSERT_EQUAL_FLOAT(0.0F, (float)test_peak(0U));
}

/* Every band-limited waveform is normalised, so it reaches full scale and the
 * overshoot of its edges cannot wrap the Q31 sample. */
static void test_band_limited_waves_are_normalised(void)
{
	static const char * const	names[] = { "square", "triangle", "sawtooth" };
	static const char * const	freqs[] = { "10", "1000", "12000" };
	uint32_t			wave;
	uint32_t			freq;

	for (wave = 0U; wave < 3U; wave++)
	{
		for (freq = 0U; freq < 3U; freq++)
		{
			char	command[PROTO_MAX_LINE];

			(void)strcpy(command, "wr wave 1 ");
			(void)strcat(command, names[wave]);
			test_run(command);
			(void)strcpy(command, "wr freq 1 ");
			(void)strcat(command, freqs[freq]);
			test_run(command);
			test_run("routine freq abort 1");
			test_run("routine freq start 1");
			test_render();
			if (freq != 0U)
			{
				TEST_ASSERT_FLOAT_WITHIN(0.03F, 1.0F, (float)test_peak(0U));
			}
			TEST_ASSERT_TRUE(test_peak(0U) <= 1.0);
		}
	}
}

static void test_sine2_never_exceeds_full_scale(void)
{
	test_run("wr wave 1 sine2");
	test_run("wr freq 1 1000");
	test_run("wr freq2 1 1100");
	test_run("wr ratio 1 1");
	test_run("routine freq start 1");
	test_render();
	TEST_ASSERT_TRUE(test_peak(0U) <= 1.0);
	TEST_ASSERT_TRUE(test_peak(0U) > 0.5);
}

static void test_sine2_with_no_second_tone_is_a_sine(void)
{
	test_run("wr wave 1 sine2");
	test_run("wr ratio 1 0");
	test_run("routine freq start 1");
	test_render();
	TEST_ASSERT_FLOAT_WITHIN(0.01F, 1.0F, (float)test_peak(0U));
}

static void test_a_finite_run_completes_after_its_cycles(void)
{
	uint32_t	frame;

	test_run("wr wave 1 sine");
	test_run("wr cycles 1 2");
	test_run("routine freq start 1");
	fgen_render(test_m_samples, TEST_FRAMES_PER_KHZ_CYCLE);
	TEST_ASSERT_EQUAL_INT((int)FGEN_STATE_RUNNING, (int)fgen_state(1U));
	fgen_render(test_m_samples, TEST_FRAMES_PER_KHZ_CYCLE);
	TEST_ASSERT_EQUAL_INT((int)FGEN_STATE_COMPLETE, (int)fgen_state(1U));

	fgen_render(test_m_samples, TEST_FRAMES);
	for (frame = 0U; frame < TEST_FRAMES; frame++)
	{
		TEST_ASSERT_EQUAL_INT32(0, test_m_samples[frame * 2U]);
	}
	test_expect("routine freq results 1", "ACK routine freq results 1 = Complete, sine, 1000.00 Hz");
}

static void test_a_finite_run_can_start_again_once_complete(void)
{
	test_run("wr wave 1 sine");
	test_run("wr cycles 1 1");
	test_run("routine freq start 1");
	fgen_render(test_m_samples, TEST_FRAMES);
	test_expect("routine freq start 1", "ACK routine freq start 1 = Running");
}

/* --- the GPIO channel ---------------------------------------------------- */
static void test_the_gpio_channel_uses_pwm(void)
{
	test_run("wr duty 3 25");
	test_run("wr cycles 3 50");
	test_expect("routine freq start 3", "ACK routine freq start 3 = Running");
	TEST_ASSERT_TRUE(fake_hal_pwm_running());
	TEST_ASSERT_EQUAL_UINT32(50U, fake_hal_pwm_config()->cycles);
}

static void test_the_gpio_channel_completes(void)
{
	test_run("wr cycles 3 5");
	test_run("routine freq start 3");
	fake_hal_pwm_finish();
	test_expect("routine freq results 3", "ACK routine freq results 3 = Complete, square, 1000.00 Hz");
}

static void test_aborting_the_gpio_channel_stops_it(void)
{
	test_run("routine freq start 3");
	test_run("routine freq abort 3");
	TEST_ASSERT_FALSE(fake_hal_pwm_running());
}

/* --- the mute ------------------------------------------------------------ */
static void test_the_dac_starts_muted(void)
{
	TEST_ASSERT_TRUE(fake_hal_dac_muted());
}

static void test_a_start_unmutes_and_settles_first(void)
{
	test_run("wr wave 1 sine");
	test_run("routine freq start 1");
	TEST_ASSERT_FALSE(fake_hal_dac_muted());
	TEST_ASSERT_EQUAL_UINT32(50U, fake_hal_delay_total_ms());
}

static void test_a_gpio_start_leaves_the_dac_muted(void)
{
	test_run("routine freq start 3");
	TEST_ASSERT_TRUE(fake_hal_dac_muted());
}

static void test_the_dac_mutes_only_after_the_hold(void)
{
	test_run("wr wave 1 sine");
	test_run("routine freq start 1");
	fake_hal_set_uptime_us(1000000ULL);
	fgen_poll();
	test_run("routine freq abort 1");
	fake_hal_set_uptime_us(1049999ULL);
	fgen_poll();
	TEST_ASSERT_FALSE(fake_hal_dac_muted());
	fake_hal_set_uptime_us(1050000ULL);
	fgen_poll();
	TEST_ASSERT_TRUE(fake_hal_dac_muted());
}

static void test_init_registers_the_renderer(void)
{
	TEST_ASSERT_TRUE(fake_hal_dac_render() == &fgen_render);
}

int main(void)
{
	UNITY_BEGIN();
	RUN_TEST(test_the_sample_rate_is_an_integer_division_of_the_clock);
	RUN_TEST(test_harmonics_stop_at_the_dac_pass_band);
	RUN_TEST(test_harmonics_are_capped_at_low_frequency);
	RUN_TEST(test_pwm_at_the_top_of_the_range_is_exact);
	RUN_TEST(test_pwm_reaches_the_bottom_of_the_range);
	RUN_TEST(test_pwm_duty);
	RUN_TEST(test_defaults);
	RUN_TEST(test_wr_with_no_channel_means_channel_1);
	RUN_TEST(test_wr_a_named_channel);
	RUN_TEST(test_frequency_forms);
	RUN_TEST(test_frequency_range_is_refused_not_clamped);
	RUN_TEST(test_malformed_numbers_are_refused);
	RUN_TEST(test_duty_range);
	RUN_TEST(test_amp_and_ratio_range);
	RUN_TEST(test_every_wave_name);
	RUN_TEST(test_the_gpio_channel_is_square_only);
	RUN_TEST(test_a_bad_channel_is_refused);
	RUN_TEST(test_an_unknown_setting_is_refused);
	RUN_TEST(test_wr_argument_counts);
	RUN_TEST(test_rd_identity_takes_no_channel);
	RUN_TEST(test_results_before_any_start);
	RUN_TEST(test_results_for_every_channel);
	RUN_TEST(test_start_with_no_channel_means_channel_1);
	RUN_TEST(test_a_continuous_run_cannot_be_restarted);
	RUN_TEST(test_a_finite_run_can_be_restarted_with_new_settings);
	RUN_TEST(test_wr_does_not_change_a_running_channel);
	RUN_TEST(test_abort_leaves_a_channel_aborted);
	RUN_TEST(test_abort_does_not_touch_a_channel_that_never_ran);
	RUN_TEST(test_abort_with_no_channel_stops_every_channel);
	RUN_TEST(test_routine_all_abort);
	RUN_TEST(test_bad_routines_are_refused);
	RUN_TEST(test_routine_argument_counts);
	RUN_TEST(test_outputs_are_silent_before_a_start);
	RUN_TEST(test_a_full_scale_sine_reaches_full_scale_without_clipping);
	RUN_TEST(test_amplitude_scales_the_output);
	RUN_TEST(test_band_limited_waves_are_normalised);
	RUN_TEST(test_sine2_never_exceeds_full_scale);
	RUN_TEST(test_sine2_with_no_second_tone_is_a_sine);
	RUN_TEST(test_a_finite_run_completes_after_its_cycles);
	RUN_TEST(test_a_finite_run_can_start_again_once_complete);
	RUN_TEST(test_the_gpio_channel_uses_pwm);
	RUN_TEST(test_the_gpio_channel_completes);
	RUN_TEST(test_aborting_the_gpio_channel_stops_it);
	RUN_TEST(test_the_dac_starts_muted);
	RUN_TEST(test_a_start_unmutes_and_settles_first);
	RUN_TEST(test_a_gpio_start_leaves_the_dac_muted);
	RUN_TEST(test_the_dac_mutes_only_after_the_hold);
	RUN_TEST(test_init_registers_the_renderer);
	return UNITY_END();
}
