/**
 * @file fake_hal.h
 * @brief A scripted stand-in for the board, for the host unit tests.
 *
 * The fake records every I2C write and every line sent to the host, and
 * answers reads from a queue the test fills. A test scripts what the sensor
 * does, runs the firmware code, and inspects what the firmware did.
 *
 * Traces to: PICO-DD-TEST, SWE4-UT-PICOFW.
 */

#ifndef FAKE_HAL_H__
#define FAKE_HAL_H__

#include <stdint.h>

#include "hal.h"

#define FAKE_MAX_TRANSFER	8U
#define FAKE_MAX_WRITES		8U
#define FAKE_MAX_READS		8U
#define FAKE_MAX_LINES		16U
#define FAKE_MAX_LINE		256U

#define FAKE_BOARD_ID		"E6614C311B7F2A21"

/** Forget everything: no writes, no lines, no scripted reads. */
void fake_hal_reset(void);

/** Make the next write return @p status instead of HAL_OK. */
void fake_hal_fail_next_write(hal_status_t status);

/** Queue a read reply of @p length bytes, returned with @p status. */
void fake_hal_queue_read(const uint8_t *data, uint32_t length, hal_status_t status);

/** Queue the six-byte measurement frame for raw words @p t and @p rh, with
 *  correct CRCs. */
void fake_hal_queue_measurement(uint16_t t, uint16_t rh);

/** Writes recorded, and the n-th write's address, length and bytes. */
uint32_t fake_hal_write_count(void);
uint8_t fake_hal_write_address(uint32_t n);
uint32_t fake_hal_write_length(uint32_t n);
const uint8_t *fake_hal_write_bytes(uint32_t n);

/** Reads performed, and the n-th read's address and requested length. */
uint32_t fake_hal_read_count(void);
uint8_t fake_hal_read_address(uint32_t n);
uint32_t fake_hal_read_length(uint32_t n);

/** Milliseconds of delay requested in total, and the delay calls in order. */
uint32_t fake_hal_delay_total_ms(void);

/** Lines sent to the host, and the n-th of them. */
uint32_t fake_hal_line_count(void);
const char *fake_hal_line(uint32_t n);
const char *fake_hal_last_line(void);

/** Set what hal_uptime_us() returns. */
void fake_hal_set_uptime_us(uint64_t uptime);

/** How often each reboot was requested. */
uint32_t fake_hal_reboot_count(void);
uint32_t fake_hal_bootloader_count(void);

/** Lines that had been sent when a reboot of either kind was requested. */
uint32_t fake_hal_lines_at_reboot(void);

/** hal_init() calls. */
uint32_t fake_hal_init_count(void);

#endif /* FAKE_HAL_H__ */
