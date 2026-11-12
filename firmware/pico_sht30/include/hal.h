/**
 * @file hal.h
 * @brief The hardware seam: everything the portable code needs from the board.
 *
 * The sensor driver, the text builder and the command parser call only these
 * functions. On the target they are implemented by hal_pico.c on the Pico SDK;
 * in the host unit tests by test/support/fake_hal.c. That is the whole of the
 * test strategy for the firmware: the code above this line is compiled
 * unchanged in both places.
 *
 * Traces to: PICO-NFR-001, PICO-DD-HAL.
 */

#ifndef HAL_H__
#define HAL_H__

#include <stdbool.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/** The indicator LEDs (#328). */
typedef enum
{
	HAL_LED_RED = 0,		/**< GP18 by default. */
	HAL_LED_YELLOW,			/**< GP19 by default. */
	HAL_LED_GREEN,			/**< GP20 by default. */
	HAL_LED_COUNT
} hal_led_t;

/** Outcome of a bus transfer. */
typedef enum
{
	HAL_STATUS_OK = 0,		/**< Every byte transferred and acknowledged. */
	HAL_STATUS_ERR_NACK,		/**< The address or a data byte was not acknowledged. */
	HAL_STATUS_ERR_TIMEOUT		/**< The transfer did not finish in time. */
} hal_status_t;

/** Length of the board identifier, including the terminator. */
#define HAL_BOARD_ID_LENGTH		17U

/**
 * @brief Bring up the I2C bus and anything else the board needs. The LEDs
 *        are made outputs, all off.
 */
void hal_init(void);

/**
 * @brief Write @p length bytes to the device at 7-bit @p address, with a STOP.
 */
hal_status_t hal_i2c_write(uint8_t address, const uint8_t *data, uint32_t length);

/**
 * @brief Read @p length bytes from the device at 7-bit @p address, with a STOP.
 */
hal_status_t hal_i2c_read(uint8_t address, uint8_t *data, uint32_t length);

/**
 * @brief Light (@p on true) or extinguish an LED. An out-of-range @p led is
 *        ignored.
 */
void hal_led_set(hal_led_t led, bool on);

/**
 * @brief Whether an LED is lit, read back from the pin's output latch rather
 *        than remembered. False for an out-of-range @p led.
 */
bool hal_led_get(hal_led_t led);

/**
 * @brief Block for at least @p milliseconds.
 */
void hal_delay_ms(uint32_t milliseconds);

/**
 * @brief Send one line to the host; the HAL appends the LF terminator.
 */
void hal_write_line(const char *line);

/**
 * @brief The board's unique identifier as upper-case hex, NUL terminated.
 */
const char *hal_board_id(void);

/**
 * @brief Microseconds since boot.
 */
uint64_t hal_uptime_us(void);

/**
 * @brief Reboot the microcontroller. Does not return on the target.
 */
void hal_reboot(void);

/**
 * @brief Reboot into the ROM's USB mass-storage bootloader, ready for a UF2.
 *        Does not return on the target.
 */
void hal_reboot_to_bootloader(void);

#ifdef __cplusplus
}
#endif

#endif /* HAL_H__ */
