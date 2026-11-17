/**
 * @file test_rx.c
 * @brief Interrupt-driven reception and the record queue (#84).
 *
 * Traces to: S2LP-DD-KITFW.
 */

#include <string.h>

#include "unity.h"

#include "fake_hal.h"
#include "protocol.h"
#include "ring.h"
#include "rx.h"
#include "s2lp.h"

static const uint8_t m_registers[] = {0xA2U, 0x9FU, 0xA0U, 0x9EU};

/** IRQ_STATUS bit 4, CRC error. The firmware passes the IRQ word on as it is
 *  and tests no CRC bit itself, so the bit is named here, not in s2lp.h. */
#define TEST_RX_IRQ_CRC_ERROR   (1UL << 4)

void setUp(void)
{
	fake_hal_reset();
	ring_reset();
}

void tearDown(void)
{
	rx_stop();
}

static void test_start_routes_nirq_masks_irqs_and_arms(void)
{
	TEST_ASSERT_TRUE(rx_start(m_registers, 4U));
	TEST_ASSERT_EQUAL_HEX8(S2LP_GPIO_NIRQ, fake_hal_register(S2LP_GPIO3_CONF));
	TEST_ASSERT_EQUAL_HEX8(0x00U, fake_hal_register(0x50U));
	TEST_ASSERT_EQUAL_HEX8(0x00U, fake_hal_register(0x52U));
	TEST_ASSERT_EQUAL_HEX8(0x43U, fake_hal_register(0x53U));   /* bits 0, 1, 6 */
	TEST_ASSERT_TRUE(fake_hal_irq_enabled());
	TEST_ASSERT_TRUE(rx_running());
	TEST_ASSERT_EQUAL_HEX8(S2LP_CMD_RX,
		fake_hal_command(fake_hal_command_count() - 1U));
}

static void test_too_many_registers_is_refused(void)
{
	uint8_t many[PROTO_MAX_REGISTERS + 1U] = {0};

	TEST_ASSERT_FALSE(rx_start(many, PROTO_MAX_REGISTERS + 1U));
	TEST_ASSERT_FALSE(rx_running());
	TEST_ASSERT_EQUAL_UINT32(0U, fake_hal_command_count());
}

static void test_a_frame_is_queued_with_time_and_registers_then_rearmed(void)
{
	const uint8_t payload[] = {0x5CU, 0x17U, 0x12U, 0x03U};
	const ring_record_t *record;
	uint32_t commands;

	(void)rx_start(m_registers, 4U);
	commands = fake_hal_command_count();
	fake_hal_queue_frame(payload, sizeof(payload));
	fake_hal_set_register(0xA2U, 0x41U);
	fake_hal_set_register(0x9FU, 0x30U);
	fake_hal_set_register(0xA0U, 0x9AU);
	fake_hal_set_register(0x9EU, 0xFEU);
	fake_hal_set_time(123456U);
	fake_hal_raise_irq(S2LP_IRQ_RX_DATA_READY);

	rx_on_irq();

	record = ring_peek();
	TEST_ASSERT_NOT_NULL(record);
	TEST_ASSERT_EQUAL_INT(PROTO_KIND_FRAME, record->kind);
	TEST_ASSERT_EQUAL_UINT32(0U, record->seq);
	TEST_ASSERT_EQUAL_UINT32(123456U, record->time_us);
	TEST_ASSERT_EQUAL_UINT8(4U, record->length);
	TEST_ASSERT_EQUAL_HEX8_ARRAY(payload, record->payload, 4U);
	TEST_ASSERT_EQUAL_UINT8(4U, record->register_count);
	TEST_ASSERT_EQUAL_HEX8(0x41U, record->registers[0]);
	TEST_ASSERT_EQUAL_HEX8(0xFEU, record->registers[3]);
	TEST_ASSERT_EQUAL_UINT32(1U, rx_frames());
	/* Flushed and armed again inside the interrupt. */
	TEST_ASSERT_EQUAL_UINT32(commands + 2U, fake_hal_command_count());
	TEST_ASSERT_EQUAL_HEX8(S2LP_CMD_FLUSHRXFIFO, fake_hal_command(commands));
	TEST_ASSERT_EQUAL_HEX8(S2LP_CMD_RX, fake_hal_command(commands + 1U));
	/* Reading the status cleared it. */
	TEST_ASSERT_EQUAL_HEX8(0x00U, fake_hal_register(0xFDU));
}

static void test_a_full_fifo_is_read_whole(void)
{
	uint8_t payload[PROTO_MAX_PAYLOAD];
	const ring_record_t *record;
	uint32_t index;

	for (index = 0U; index < PROTO_MAX_PAYLOAD; index++)
	{
		payload[index] = (uint8_t)index;
	}
	(void)rx_start(m_registers, 0U);
	fake_hal_queue_frame(payload, PROTO_MAX_PAYLOAD);   /* RX_FIFO_STATUS reads 0x80 */
	fake_hal_raise_irq(S2LP_IRQ_RX_DATA_READY);
	rx_on_irq();
	record = ring_peek();
	TEST_ASSERT_NOT_NULL(record);
	TEST_ASSERT_EQUAL_UINT8(PROTO_MAX_PAYLOAD, record->length);
	TEST_ASSERT_EQUAL_HEX8(0x7FU, record->payload[127]);
}

static void test_a_count_beyond_the_fifo_is_held_to_it(void)
{
	const uint8_t payload[] = {0x01U};

	(void)rx_start(m_registers, 0U);
	fake_hal_queue_frame(payload, 1U);
	fake_hal_set_register(S2LP_RX_FIFO_STATUS, 0xFFU);
	fake_hal_raise_irq(S2LP_IRQ_RX_DATA_READY);
	rx_on_irq();
	TEST_ASSERT_EQUAL_UINT8(PROTO_MAX_PAYLOAD, ring_peek()->length);
}

static void test_the_longest_deaf_time_is_kept(void)
{
	const uint8_t payload[] = {0x01U, 0x02U, 0x03U, 0x04U, 0x05U, 0x06U, 0x07U, 0x08U};

	(void)rx_start(m_registers, 4U);
	TEST_ASSERT_EQUAL_UINT32(0U, rx_deaf_max_us());
	fake_hal_queue_frame(payload, 8U);
	fake_hal_raise_irq(S2LP_IRQ_RX_DATA_READY);
	rx_on_irq();
	/* The fake takes 1 us per SPI byte, after the interrupt's time is taken:
	   status 6, FIFO count 3, FIFO 10, four registers 12, flush and RX 4. */
	TEST_ASSERT_EQUAL_UINT32(35U, rx_deaf_max_us());
	fake_hal_raise_irq(S2LP_IRQ_RX_DATA_DISC);
	rx_on_irq();
	/* A rejection: status 6, flush and RX 4 - shorter, so the longest stays. */
	TEST_ASSERT_EQUAL_UINT32(35U, rx_deaf_max_us());
}

static void test_a_discarded_reception_is_queued_as_a_rejection(void)
{
	const ring_record_t *record;

	(void)rx_start(m_registers, 4U);
	fake_hal_raise_irq(S2LP_IRQ_RX_DATA_DISC | TEST_RX_IRQ_CRC_ERROR);

	rx_on_irq();

	record = ring_peek();
	TEST_ASSERT_NOT_NULL(record);
	TEST_ASSERT_EQUAL_INT(PROTO_KIND_REJECT, record->kind);
	TEST_ASSERT_EQUAL_HEX32(S2LP_IRQ_RX_DATA_DISC | TEST_RX_IRQ_CRC_ERROR, record->irq);
	TEST_ASSERT_EQUAL_UINT32(1U, rx_rejects());
	TEST_ASSERT_EQUAL_HEX8(S2LP_CMD_RX, fake_hal_command(fake_hal_command_count() - 1U));
}

static void test_an_interrupt_with_nothing_asked_for_changes_nothing(void)
{
	uint32_t commands;

	(void)rx_start(m_registers, 0U);
	commands = fake_hal_command_count();
	fake_hal_raise_irq(1UL << 13);                  /* VALID_SYNC */

	rx_on_irq();

	TEST_ASSERT_NULL(ring_peek());
	TEST_ASSERT_EQUAL_UINT32(commands, fake_hal_command_count());
}

static void test_an_interrupt_after_stop_queues_nothing(void)
{
	const uint8_t payload[] = {0x01U};

	(void)rx_start(m_registers, 0U);
	rx_stop();
	fake_hal_queue_frame(payload, 1U);
	fake_hal_raise_irq(S2LP_IRQ_RX_DATA_READY);

	rx_on_irq();

	TEST_ASSERT_NULL(ring_peek());
	TEST_ASSERT_FALSE(fake_hal_irq_enabled());
	TEST_ASSERT_EQUAL_HEX8(0x00U, fake_hal_register(0xFDU));
}

static void test_a_full_queue_counts_overflows_and_keeps_numbering(void)
{
	const uint8_t payload[] = {0xAAU, 0xBBU};
	uint32_t index;
	const ring_record_t *record;

	(void)rx_start(m_registers, 0U);
	for (index = 0U; index < (RING_SIZE + 2U); index++)
	{
		fake_hal_queue_frame(payload, 2U);
		fake_hal_raise_irq(S2LP_IRQ_RX_DATA_READY);
		rx_on_irq();
	}
	TEST_ASSERT_EQUAL_UINT32(RING_SIZE, ring_count());
	TEST_ASSERT_EQUAL_UINT32(2U, ring_overflows());
	TEST_ASSERT_EQUAL_UINT32(RING_SIZE + 2U, rx_frames());

	for (index = 0U; index < RING_SIZE; index++)
	{
		ring_release();
	}
	fake_hal_queue_frame(payload, 2U);
	fake_hal_raise_irq(S2LP_IRQ_RX_DATA_READY);
	rx_on_irq();
	record = ring_peek();
	TEST_ASSERT_NOT_NULL(record);
	/* The two dropped records used numbers 16 and 17: the host sees the gap. */
	TEST_ASSERT_EQUAL_UINT32(RING_SIZE + 2U, record->seq);
}

static void test_restart_resets_counters_and_numbering(void)
{
	const uint8_t payload[] = {0x01U};

	(void)rx_start(m_registers, 0U);
	fake_hal_queue_frame(payload, 1U);
	fake_hal_raise_irq(S2LP_IRQ_RX_DATA_READY);
	rx_on_irq();
	(void)rx_start(m_registers, 0U);
	TEST_ASSERT_EQUAL_UINT32(0U, rx_frames());
	TEST_ASSERT_EQUAL_UINT32(0U, ring_count());
	TEST_ASSERT_NOT_NULL(ring_claim());
	TEST_ASSERT_EQUAL_UINT32(0U, ring_peek() == NULL ? 0U : 1U);
}

int main(void)
{
	UNITY_BEGIN();
	RUN_TEST(test_start_routes_nirq_masks_irqs_and_arms);
	RUN_TEST(test_too_many_registers_is_refused);
	RUN_TEST(test_a_frame_is_queued_with_time_and_registers_then_rearmed);
	RUN_TEST(test_a_full_fifo_is_read_whole);
	RUN_TEST(test_a_count_beyond_the_fifo_is_held_to_it);
	RUN_TEST(test_the_longest_deaf_time_is_kept);
	RUN_TEST(test_a_discarded_reception_is_queued_as_a_rejection);
	RUN_TEST(test_an_interrupt_with_nothing_asked_for_changes_nothing);
	RUN_TEST(test_an_interrupt_after_stop_queues_nothing);
	RUN_TEST(test_a_full_queue_counts_overflows_and_keeps_numbering);
	RUN_TEST(test_restart_resets_counters_and_numbering);
	return UNITY_END();
}
