/**
 * @file ring.h
 * @brief The queue of received records between the radio's interrupt and the
 *        main loop (#84): one producer (the interrupt), one consumer.
 */

#ifndef RING_H
#define RING_H

#include <stdbool.h>
#include <stdint.h>

#include "protocol.h"

/** Records the queue holds; a power of two. */
#define RING_SIZE               (16U)

/** One record: a frame or a rejection. */
typedef struct
{
	uint32_t seq;
	uint32_t time_us;
	uint32_t irq;
	uint8_t kind;
	uint8_t register_count;
	uint8_t registers[PROTO_MAX_REGISTERS];
	uint8_t length;
	uint8_t payload[PROTO_MAX_PAYLOAD];
} ring_record_t;

/** Empty the queue and zero its counters. */
void ring_reset(void);

/**
 * @brief The next free record, numbered, for the producer to fill; NULL when
 *        the queue is full, which counts an overflow and still uses a number.
 */
ring_record_t *ring_claim(void);

/** Publish the record ring_claim gave. */
void ring_commit(void);

/** The oldest published record, or NULL. */
const ring_record_t *ring_peek(void);

/** Free the record ring_peek gave. */
void ring_release(void);

/** Records dropped because the queue was full. */
uint32_t ring_overflows(void);

/** Records waiting. */
uint32_t ring_count(void);

#endif /* RING_H */
