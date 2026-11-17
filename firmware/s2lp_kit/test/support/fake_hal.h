/**
 * @file fake_hal.h
 * @brief A stand-in for the board and the S2-LP, for the host unit tests (#84).
 *
 * The fake radio answers the S2-LP's SPI protocol from a register file: reads
 * of the interrupt status clear it, reads of the FIFO take the queued payload,
 * and command strobes are logged. Everything the firmware sends to the host
 * is kept as text. A test sets the radio up, runs firmware code, and checks
 * what the firmware did.
 */

#ifndef FAKE_HAL_H
#define FAKE_HAL_H

#include <stdbool.h>
#include <stdint.h>

#include "hal.h"

#define FAKE_HAL_MAX_COMMANDS   (32U)
#define FAKE_HAL_MAX_OUTPUT     (4096U)

/** Forget everything: registers zero, no FIFO, no output, time zero. */
void fake_hal_reset(void);

/** The register file, as the firmware wrote it or the test set it. */
uint8_t fake_hal_register(uint8_t address);
void fake_hal_set_register(uint8_t address, uint8_t value);

/** Raise interrupt bits, as IRQ_STATUS3 .. 0 will report them. */
void fake_hal_raise_irq(uint32_t bits);

/** Put a frame in the receive FIFO (RX_FIFO_STATUS follows its length). */
void fake_hal_queue_frame(const uint8_t *payload, uint32_t length);

/** Command strobes sent, in order. */
uint32_t fake_hal_command_count(void);
uint8_t fake_hal_command(uint32_t index);

/** Everything sent to the host, as one string. */
const char *fake_hal_output(void);
void fake_hal_clear_output(void);

/** The microsecond timer's next value. */
void fake_hal_set_time(uint32_t micros);

/** Whether the firmware has the nIRQ interrupt enabled, and SDN asserted. */
bool fake_hal_irq_enabled(void);
bool fake_hal_shutdown(void);

#endif /* FAKE_HAL_H */
