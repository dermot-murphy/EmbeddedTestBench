/**
 * @file test_cdc_acm.c
 * @brief The host link: line assembly in, a bounded queue out.
 *
 * The queue is where this firmware's timing integrity is won or lost. A radio
 * event handler that blocked on USB would delay the next radio event, so output
 * is queued; and when the queue is full a whole line is dropped and counted,
 * because half a line would reach the host as a protocol error rather than as
 * congestion. Both behaviours are pinned here.
 *
 * Traces to: BLE-FR-003, BLE-FR-004, BLE-DD-CDC, SWE4-UT-FWUNIT.
 */

#include <string.h>

#include "unity.h"

#include "app_usbd_cdc_acm.h"
#include "app_util_platform.h"
#include "cdc_acm.h"

/* The queue is module state with no reset - as on the dongle, where the only
 * reset is a reset. So each test starts by draining whatever the last one left
 * in flight, which also exercises the drain path rather more than a dedicated
 * reset would. */
void setUp(void)
{
	uint32_t guard;

	fake_cdc_open_port();
	for (guard = 0U; guard < (CDC_TX_QUEUE_LINES + 4U); guard++)
	{
		fake_cdc_complete_write();
	}

	fake_cdc_reset();
	fake_usbd_reset();
	fake_critical_nesting   = 0;
	fake_critical_depth_max = 0;
	fake_cdc_open_port();
}

void tearDown(void)
{
	/* Every test is also a check that no path leaves a critical region open. */
	TEST_ASSERT_EQUAL_INT_MESSAGE(0, fake_critical_nesting,
				      "a critical region was left open");
}

/* ------------------------------------------------------------------ */
/* Sending                                                             */
/* ------------------------------------------------------------------ */

static void test_a_line_is_written_with_a_terminator(void)
{
	TEST_ASSERT_TRUE(cdc_acm_send_line("ok"));
	TEST_ASSERT_EQUAL_STRING("ok\n", fake_cdc_written());
}

static void test_formatting(void)
{
	TEST_ASSERT_TRUE(cdc_acm_send_format("ok t=%u hz=%u", 42U, 1000000U));
	TEST_ASSERT_EQUAL_STRING("ok t=42 hz=1000000\n", fake_cdc_written());
}

static void test_a_null_line_is_refused_rather_than_dereferenced(void)
{
	TEST_ASSERT_FALSE(cdc_acm_send_line(NULL));
}

static void test_writes_are_serialised_one_at_a_time(void)
{
	/* The endpoint takes one write at a time; the rest wait in the queue. */
	cdc_acm_send_line("first");
	cdc_acm_send_line("second");
	TEST_ASSERT_EQUAL_UINT32(1U, fake_cdc_write_count());
	TEST_ASSERT_EQUAL_STRING("first\n", fake_cdc_written());

	fake_cdc_complete_write();
	TEST_ASSERT_EQUAL_UINT32(2U, fake_cdc_write_count());
	TEST_ASSERT_EQUAL_STRING("first\nsecond\n", fake_cdc_written());
}

static void test_idle_only_once_every_line_has_been_handed_over(void)
{
	/* The dfu command waits on this before resetting; a reset with a line
	 * still queued or in flight loses it. */
	TEST_ASSERT_TRUE(cdc_acm_tx_idle());

	cdc_acm_send_line("first");
	cdc_acm_send_line("second");
	TEST_ASSERT_FALSE(cdc_acm_tx_idle());

	fake_cdc_complete_write();
	TEST_ASSERT_FALSE(cdc_acm_tx_idle());

	fake_cdc_complete_write();
	TEST_ASSERT_TRUE(cdc_acm_tx_idle());
}

static void test_the_queue_drains_in_order(void)
{
	uint32_t index;

	for (index = 0U; index < 5U; index++)
	{
		(void)cdc_acm_send_format("line=%u", index);
	}
	for (index = 0U; index < 5U; index++)
	{
		fake_cdc_complete_write();
	}
	TEST_ASSERT_EQUAL_STRING("line=0\nline=1\nline=2\nline=3\nline=4\n", fake_cdc_written());
}

static void test_a_full_queue_drops_whole_lines_and_counts_them(void)
{
	uint32_t index;
	uint32_t before = cdc_acm_dropped();
	uint32_t accepted = 0U;

	/* Nothing completes, so the queue fills. */
	for (index = 0U; index < (CDC_TX_QUEUE_LINES + 8U); index++)
	{
		if (cdc_acm_send_format("line=%u", index))
		{
			accepted++;
		}
	}

	TEST_ASSERT_TRUE_MESSAGE(accepted < (CDC_TX_QUEUE_LINES + 8U), "the queue never filled");
	TEST_ASSERT_GREATER_THAN_UINT32(before, cdc_acm_dropped());
	/* Whole lines only: what was written must still parse as complete lines. */
	TEST_ASSERT_GREATER_THAN_UINT32(0U, fake_cdc_written_length());
	TEST_ASSERT_EQUAL_CHAR('\n', fake_cdc_written()[fake_cdc_written_length() - 1U]);
}

static void test_an_over_long_line_is_truncated_not_overrun(void)
{
	char	long_line[PROTO_MAX_EVENT * 2U];
	uint32_t written;

	(void)memset(long_line, 'x', sizeof(long_line) - 1U);
	long_line[sizeof(long_line) - 1U] = '\0';

	TEST_ASSERT_TRUE(cdc_acm_send_line(long_line));
	written = fake_cdc_written_length();
	TEST_ASSERT_GREATER_THAN_UINT32(0U, written);
	TEST_ASSERT_TRUE(written <= PROTO_MAX_EVENT);
	TEST_ASSERT_EQUAL_CHAR('\n', fake_cdc_written()[written - 1U]);
}

static void test_a_refused_write_releases_the_slot(void)
{
	/* Otherwise one refusal would wedge the queue for good. */
	fake_cdc_set_write_result(NRF_ERROR_BUSY);
	cdc_acm_send_line("first");
	fake_cdc_set_write_result(NRF_SUCCESS);
	cdc_acm_send_line("second");
	TEST_ASSERT_TRUE(fake_cdc_write_count() > 0U);
}

static void test_nothing_is_written_before_the_port_opens(void)
{
	fake_cdc_reset();
	fake_cdc_close_port();
	cdc_acm_send_line("early");
	TEST_ASSERT_EQUAL_UINT32(0U, fake_cdc_write_count());

	fake_cdc_open_port();
	cdc_acm_process();
	TEST_ASSERT_EQUAL_STRING("early\n", fake_cdc_written());
}

static void test_the_port_state_is_reported(void)
{
	TEST_ASSERT_TRUE(cdc_acm_is_open());
	fake_cdc_close_port();
	TEST_ASSERT_FALSE(cdc_acm_is_open());
	fake_cdc_open_port();
}

/* ------------------------------------------------------------------ */
/* Receiving                                                           */
/* ------------------------------------------------------------------ */

static void test_a_line_is_assembled_from_bytes(void)
{
	char buffer[PROTO_MAX_LINE];

	fake_cdc_receive_text("ver\n");
	TEST_ASSERT_TRUE(cdc_acm_take_line(buffer, sizeof(buffer)));
	TEST_ASSERT_EQUAL_STRING("ver", buffer);
}

static void test_carriage_return_also_ends_a_line(void)
{
	char buffer[PROTO_MAX_LINE];

	fake_cdc_receive_text("ver\r\n");
	TEST_ASSERT_TRUE(cdc_acm_take_line(buffer, sizeof(buffer)));
	TEST_ASSERT_EQUAL_STRING("ver", buffer);
	TEST_ASSERT_FALSE(cdc_acm_take_line(buffer, sizeof(buffer)));
}

static void test_a_partial_line_is_not_offered(void)
{
	char buffer[PROTO_MAX_LINE];

	fake_cdc_receive_text("sca");
	TEST_ASSERT_FALSE(cdc_acm_take_line(buffer, sizeof(buffer)));
	fake_cdc_receive_text("n stop\n");
	TEST_ASSERT_TRUE(cdc_acm_take_line(buffer, sizeof(buffer)));
	TEST_ASSERT_EQUAL_STRING("scan stop", buffer);
}

static void test_an_empty_line_is_ignored(void)
{
	char buffer[PROTO_MAX_LINE];

	fake_cdc_receive_text("\n\n");
	TEST_ASSERT_FALSE(cdc_acm_take_line(buffer, sizeof(buffer)));
}

static void test_a_line_is_taken_only_once(void)
{
	char buffer[PROTO_MAX_LINE];

	fake_cdc_receive_text("time\n");
	TEST_ASSERT_TRUE(cdc_acm_take_line(buffer, sizeof(buffer)));
	TEST_ASSERT_FALSE(cdc_acm_take_line(buffer, sizeof(buffer)));
}

static void test_an_over_long_command_is_discarded_not_acted_on_in_part(void)
{
	char		buffer[PROTO_MAX_LINE];
	uint32_t	index;

	for (index = 0U; index < (PROTO_MAX_LINE + 32U); index++)
	{
		fake_cdc_receive_byte('x');
	}
	fake_cdc_receive_byte('\n');
	TEST_ASSERT_FALSE(cdc_acm_take_line(buffer, sizeof(buffer)));
}

static void test_the_tail_of_an_over_long_command_is_not_a_command(void)
{
	/* Regression for D-28: the firmware used to start a new line where the
	 * buffer overflowed, so "xxx...xxxreset" would have executed `reset`. */
	char		buffer[PROTO_MAX_LINE];
	uint32_t	index;

	for (index = 0U; index < PROTO_MAX_LINE; index++)
	{
		fake_cdc_receive_byte('x');
	}
	fake_cdc_receive_text("reset\n");
	TEST_ASSERT_FALSE(cdc_acm_take_line(buffer, sizeof(buffer)));

	/* And the line after it is read normally. */
	fake_cdc_receive_text("ver\n");
	TEST_ASSERT_TRUE(cdc_acm_take_line(buffer, sizeof(buffer)));
	TEST_ASSERT_EQUAL_STRING("ver", buffer);
}

static void test_taking_into_no_buffer_is_refused(void)
{
	char buffer[PROTO_MAX_LINE];

	fake_cdc_receive_text("ver\n");
	TEST_ASSERT_FALSE(cdc_acm_take_line(NULL, sizeof(buffer)));
	TEST_ASSERT_FALSE(cdc_acm_take_line(buffer, 0U));
	TEST_ASSERT_TRUE(cdc_acm_take_line(buffer, sizeof(buffer)));
}

static void test_processing_drains_the_usb_event_queue(void)
{
	fake_usbd_set_queue_depth(3U);
	cdc_acm_process();
	TEST_ASSERT_TRUE(fake_usbd_queue_process_calls() >= 4U);
}

static void test_sending_enters_and_leaves_a_critical_region(void)
{
	/* The queue is touched from a radio event handler, so the indices must be
	 * updated inside one - and defect D-23 was an early return from inside it. */
	fake_critical_depth_max = 0;
	cdc_acm_send_line("ok");
	TEST_ASSERT_GREATER_THAN_INT(0, fake_critical_depth_max);
	TEST_ASSERT_EQUAL_INT(0, fake_critical_nesting);
}

int main(void)
{
	UNITY_BEGIN();
	RUN_TEST(test_a_line_is_written_with_a_terminator);
	RUN_TEST(test_formatting);
	RUN_TEST(test_a_null_line_is_refused_rather_than_dereferenced);
	RUN_TEST(test_writes_are_serialised_one_at_a_time);
	RUN_TEST(test_idle_only_once_every_line_has_been_handed_over);
	RUN_TEST(test_the_queue_drains_in_order);
	RUN_TEST(test_a_full_queue_drops_whole_lines_and_counts_them);
	RUN_TEST(test_an_over_long_line_is_truncated_not_overrun);
	RUN_TEST(test_a_refused_write_releases_the_slot);
	RUN_TEST(test_nothing_is_written_before_the_port_opens);
	RUN_TEST(test_the_port_state_is_reported);
	RUN_TEST(test_a_line_is_assembled_from_bytes);
	RUN_TEST(test_carriage_return_also_ends_a_line);
	RUN_TEST(test_a_partial_line_is_not_offered);
	RUN_TEST(test_an_empty_line_is_ignored);
	RUN_TEST(test_a_line_is_taken_only_once);
	RUN_TEST(test_an_over_long_command_is_discarded_not_acted_on_in_part);
	RUN_TEST(test_the_tail_of_an_over_long_command_is_not_a_command);
	RUN_TEST(test_taking_into_no_buffer_is_refused);
	RUN_TEST(test_processing_drains_the_usb_event_queue);
	RUN_TEST(test_sending_enters_and_leaves_a_critical_region);
	return UNITY_END();
}
