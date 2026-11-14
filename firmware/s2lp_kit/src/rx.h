/**
 * @file rx.h
 * @brief Interrupt-driven reception (#84): on each radio interrupt, queue the
 *        frame or the rejection with its time and registers, and re-arm at once.
 */

#ifndef RX_H
#define RX_H

#include <stdbool.h>
#include <stdint.h>

/**
 * @brief Start receiving until rx_stop.
 *
 * Routes nIRQ to S2-LP GPIO3 and sets the interrupt mask to data ready, data
 * discarded and FIFO error; everything else (frequency, modulation, packet
 * handler, filters) is the host's register setup.
 *
 * @param addresses Registers to read after each frame, at most
 *                  PROTO_MAX_REGISTERS.
 * @param count     How many.
 * @return false when count is too large; nothing is started.
 */
bool rx_start(const uint8_t *addresses, uint32_t count);

/** Stop receiving: the radio is aborted to READY and its FIFO flushed. */
void rx_stop(void);

/** Whether a reception is running. */
bool rx_running(void);

/** The radio's interrupt: called by the board's handler for nIRQ. */
void rx_on_irq(void);

/** Frames queued or dropped since rx_start. */
uint32_t rx_frames(void);

/** Rejections queued or dropped since rx_start. */
uint32_t rx_rejects(void);

/**
 * @brief The longest time, in microseconds, from taking a frame's or a
 *        rejection's interrupt to the radio being armed again, since rx_start:
 *        how long the radio was deaf after a reception.
 */
uint32_t rx_deaf_max_us(void);

#endif /* RX_H */
