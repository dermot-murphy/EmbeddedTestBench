/**
 * @file test_sht30.c
 * @brief The SHT30 driver against a scripted bus.
 *
 * Reference values are computed from the datasheet formulas, rounded to the
 * nearest thousandth:
 *
 *   S_T  0x0000 -> -45.000 C      S_RH 0x0000 ->   0.000 %
 *   S_T  0xFFFF -> 130.000 C      S_RH 0xFFFF -> 100.000 %
 *   S_T  0x6666 ->  25.000 C      S_RH 0x6666 ->  40.000 %
 *   S_T  0x4000 ->  -1.249 C      S_RH 0x8000 ->  50.001 %
 *
 * Traces to: PICO-FR-020 .. PICO-FR-026, PICO-DD-SHT30, SWE4-UT-PICOFW.
 */

#include "unity.h"

#include "fake_hal.h"
#include "sht30.h"

#define TEST_ADDRESS		0x44U

void setUp(void)
{
	fake_hal_reset();
}

void tearDown(void)
{
}

/* --- CRC ---------------------------------------------------------------- */
static void test_crc_matches_the_datasheet_check_value(void)
{
	static const uint8_t	data[2] = { 0xBEU, 0xEFU };

	TEST_ASSERT_EQUAL_HEX8(0x92U, sht30_crc8(data, 2U));
}

static void test_crc_of_nothing_is_the_initial_value(void)
{
	TEST_ASSERT_EQUAL_HEX8(0xFFU, sht30_crc8(NULL, 2U));
	TEST_ASSERT_EQUAL_HEX8(0xFFU, sht30_crc8((const uint8_t *)"", 0U));
}

/* --- conversion --------------------------------------------------------- */
static void test_temperature_end_points(void)
{
	TEST_ASSERT_EQUAL_INT32(-45000, sht30_ticks_to_millicelsius(0x0000U));
	TEST_ASSERT_EQUAL_INT32(130000, sht30_ticks_to_millicelsius(0xFFFFU));
}

static void test_temperature_mid_scale(void)
{
	TEST_ASSERT_EQUAL_INT32(25000, sht30_ticks_to_millicelsius(0x6666U));
	TEST_ASSERT_EQUAL_INT32(-1249, sht30_ticks_to_millicelsius(0x4000U));
}

static void test_temperature_rounds_to_nearest(void)
{
	/* One tick is 2.67 mC: rounded, not truncated, to 3. */
	TEST_ASSERT_EQUAL_INT32(-44997, sht30_ticks_to_millicelsius(0x0001U));
}

static void test_humidity_end_points_and_mid_scale(void)
{
	TEST_ASSERT_EQUAL_INT32(0, sht30_ticks_to_millipercent(0x0000U));
	TEST_ASSERT_EQUAL_INT32(100000, sht30_ticks_to_millipercent(0xFFFFU));
	TEST_ASSERT_EQUAL_INT32(40000, sht30_ticks_to_millipercent(0x6666U));
	TEST_ASSERT_EQUAL_INT32(50001, sht30_ticks_to_millipercent(0x8000U));
}

/* --- decode ------------------------------------------------------------- */
static void test_decode_a_good_frame(void)
{
	uint8_t		frame[6] = { 0x66U, 0x66U, 0x93U, 0x80U, 0x00U, 0x00U };
	sht30_reading_t	reading;

	frame[5] = sht30_crc8(&frame[3], 2U);
	TEST_ASSERT_EQUAL(SHT30_STATUS_OK, sht30_decode(frame, &reading));
	TEST_ASSERT_EQUAL_INT32(25000, reading.temperature_mc);
	TEST_ASSERT_EQUAL_INT32(50001, reading.humidity_mpct);
	TEST_ASSERT_EQUAL_HEX16(0x6666U, reading.raw_temperature);
	TEST_ASSERT_EQUAL_HEX16(0x8000U, reading.raw_humidity);
}

static void test_a_bad_temperature_crc_leaves_the_reading_untouched(void)
{
	uint8_t		frame[6] = { 0x66U, 0x66U, 0x00U, 0x66U, 0x66U, 0x93U };
	sht30_reading_t	reading = { 1, 2, 3U, 4U };

	TEST_ASSERT_EQUAL(SHT30_STATUS_ERR_CRC, sht30_decode(frame, &reading));
	TEST_ASSERT_EQUAL_INT32(1, reading.temperature_mc);
	TEST_ASSERT_EQUAL_INT32(2, reading.humidity_mpct);
}

static void test_a_bad_humidity_crc_leaves_the_reading_untouched(void)
{
	/* The temperature word is good: it must still not be half-written. */
	uint8_t		frame[6] = { 0x66U, 0x66U, 0x93U, 0x66U, 0x66U, 0x00U };
	sht30_reading_t	reading = { 1, 2, 3U, 4U };

	TEST_ASSERT_EQUAL(SHT30_STATUS_ERR_CRC, sht30_decode(frame, &reading));
	TEST_ASSERT_EQUAL_INT32(1, reading.temperature_mc);
	TEST_ASSERT_EQUAL_HEX16(3U, reading.raw_temperature);
}

static void test_decode_refuses_null(void)
{
	uint8_t		frame[6] = { 0U };
	sht30_reading_t	reading;

	TEST_ASSERT_EQUAL(SHT30_STATUS_ERR_PARAM, sht30_decode(NULL, &reading));
	TEST_ASSERT_EQUAL(SHT30_STATUS_ERR_PARAM, sht30_decode(frame, NULL));
}

/* --- measure ------------------------------------------------------------ */
static void test_measure_sends_the_high_repeatability_command(void)
{
	sht30_reading_t	reading;

	fake_hal_queue_measurement(0x6666U, 0x6666U);
	TEST_ASSERT_EQUAL(SHT30_STATUS_OK, sht30_measure(TEST_ADDRESS, &reading));

	TEST_ASSERT_EQUAL_UINT32(1U, fake_hal_write_count());
	TEST_ASSERT_EQUAL_HEX8(TEST_ADDRESS, fake_hal_write_address(0U));
	TEST_ASSERT_EQUAL_UINT32(2U, fake_hal_write_length(0U));
	TEST_ASSERT_EQUAL_HEX8(0x24U, fake_hal_write_bytes(0U)[0]);
	TEST_ASSERT_EQUAL_HEX8(0x00U, fake_hal_write_bytes(0U)[1]);
}

static void test_measure_waits_out_the_conversion_then_reads_six_bytes(void)
{
	sht30_reading_t	reading;

	fake_hal_queue_measurement(0x6666U, 0x6666U);
	(void)sht30_measure(TEST_ADDRESS, &reading);

	TEST_ASSERT_GREATER_OR_EQUAL_UINT32(15U, fake_hal_delay_total_ms());
	TEST_ASSERT_EQUAL_UINT32(1U, fake_hal_read_count());
	TEST_ASSERT_EQUAL_HEX8(TEST_ADDRESS, fake_hal_read_address(0U));
	TEST_ASSERT_EQUAL_UINT32(6U, fake_hal_read_length(0U));
	TEST_ASSERT_EQUAL_INT32(25000, reading.temperature_mc);
	TEST_ASSERT_EQUAL_INT32(40000, reading.humidity_mpct);
}

static void test_measure_reports_an_absent_sensor(void)
{
	sht30_reading_t	reading;

	fake_hal_fail_next_write(HAL_STATUS_ERR_NACK);
	TEST_ASSERT_EQUAL(SHT30_STATUS_ERR_NACK, sht30_measure(TEST_ADDRESS, &reading));
	TEST_ASSERT_EQUAL_UINT32(0U, fake_hal_read_count());
}

static void test_measure_reports_a_bus_timeout(void)
{
	sht30_reading_t	reading;

	fake_hal_fail_next_write(HAL_STATUS_ERR_TIMEOUT);
	TEST_ASSERT_EQUAL(SHT30_STATUS_ERR_TIMEOUT, sht30_measure(TEST_ADDRESS, &reading));
}

static void test_measure_reports_a_nack_on_the_read(void)
{
	sht30_reading_t	reading;

	/* Nothing queued: the sensor NACKs the read header. */
	TEST_ASSERT_EQUAL(SHT30_STATUS_ERR_NACK, sht30_measure(TEST_ADDRESS, &reading));
}

static void test_measure_reports_a_corrupted_frame(void)
{
	static const uint8_t	frame[6] = { 0x66U, 0x66U, 0x00U, 0x66U, 0x66U, 0x93U };
	sht30_reading_t		reading;

	fake_hal_queue_read(frame, 6U, HAL_STATUS_OK);
	TEST_ASSERT_EQUAL(SHT30_STATUS_ERR_CRC, sht30_measure(TEST_ADDRESS, &reading));
}

static void test_measure_refuses_null(void)
{
	TEST_ASSERT_EQUAL(SHT30_STATUS_ERR_PARAM, sht30_measure(TEST_ADDRESS, NULL));
	TEST_ASSERT_EQUAL_UINT32(0U, fake_hal_write_count());
}

/* --- status and reset --------------------------------------------------- */
static void test_read_status(void)
{
	uint8_t		word[3] = { 0x80U, 0x10U, 0x00U };
	uint16_t	status = 0U;

	word[2] = sht30_crc8(word, 2U);
	fake_hal_queue_read(word, 3U, HAL_STATUS_OK);
	TEST_ASSERT_EQUAL(SHT30_STATUS_OK, sht30_read_status(TEST_ADDRESS, &status));
	TEST_ASSERT_EQUAL_HEX16(0x8010U, status);
	TEST_ASSERT_EQUAL_HEX8(0xF3U, fake_hal_write_bytes(0U)[0]);
	TEST_ASSERT_EQUAL_HEX8(0x2DU, fake_hal_write_bytes(0U)[1]);
	TEST_ASSERT_EQUAL_UINT32(3U, fake_hal_read_length(0U));
}

static void test_read_status_checks_the_crc(void)
{
	static const uint8_t	word[3] = { 0x80U, 0x10U, 0x00U };
	uint16_t		status = 0x1234U;

	fake_hal_queue_read(word, 3U, HAL_STATUS_OK);
	TEST_ASSERT_EQUAL(SHT30_STATUS_ERR_CRC, sht30_read_status(TEST_ADDRESS, &status));
	TEST_ASSERT_EQUAL_HEX16(0x1234U, status);
}

static void test_read_status_refuses_null(void)
{
	TEST_ASSERT_EQUAL(SHT30_STATUS_ERR_PARAM, sht30_read_status(TEST_ADDRESS, NULL));
}

static void test_soft_reset_sends_the_command_and_waits(void)
{
	TEST_ASSERT_EQUAL(SHT30_STATUS_OK, sht30_soft_reset(TEST_ADDRESS));
	TEST_ASSERT_EQUAL_HEX8(0x30U, fake_hal_write_bytes(0U)[0]);
	TEST_ASSERT_EQUAL_HEX8(0xA2U, fake_hal_write_bytes(0U)[1]);
	TEST_ASSERT_GREATER_OR_EQUAL_UINT32(2U, fake_hal_delay_total_ms());
}

static void test_soft_reset_of_an_absent_sensor_does_not_wait(void)
{
	fake_hal_fail_next_write(HAL_STATUS_ERR_NACK);
	TEST_ASSERT_EQUAL(SHT30_STATUS_ERR_NACK, sht30_soft_reset(TEST_ADDRESS));
	TEST_ASSERT_EQUAL_UINT32(0U, fake_hal_delay_total_ms());
}

int main(void)
{
	UNITY_BEGIN();
	RUN_TEST(test_crc_matches_the_datasheet_check_value);
	RUN_TEST(test_crc_of_nothing_is_the_initial_value);
	RUN_TEST(test_temperature_end_points);
	RUN_TEST(test_temperature_mid_scale);
	RUN_TEST(test_temperature_rounds_to_nearest);
	RUN_TEST(test_humidity_end_points_and_mid_scale);
	RUN_TEST(test_decode_a_good_frame);
	RUN_TEST(test_a_bad_temperature_crc_leaves_the_reading_untouched);
	RUN_TEST(test_a_bad_humidity_crc_leaves_the_reading_untouched);
	RUN_TEST(test_decode_refuses_null);
	RUN_TEST(test_measure_sends_the_high_repeatability_command);
	RUN_TEST(test_measure_waits_out_the_conversion_then_reads_six_bytes);
	RUN_TEST(test_measure_reports_an_absent_sensor);
	RUN_TEST(test_measure_reports_a_bus_timeout);
	RUN_TEST(test_measure_reports_a_nack_on_the_read);
	RUN_TEST(test_measure_reports_a_corrupted_frame);
	RUN_TEST(test_measure_refuses_null);
	RUN_TEST(test_read_status);
	RUN_TEST(test_read_status_checks_the_crc);
	RUN_TEST(test_read_status_refuses_null);
	RUN_TEST(test_soft_reset_sends_the_command_and_waits);
	RUN_TEST(test_soft_reset_of_an_absent_sensor_does_not_wait);
	return UNITY_END();
}
