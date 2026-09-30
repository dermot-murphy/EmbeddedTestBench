/**
 * @file nrf_gpio.h
 * @brief Host-test stand-in: pin writes are recorded, not performed.
 *
 * Traces to: BLE-DD-TEST.
 */

#ifndef NRF_GPIO_H__
#define NRF_GPIO_H__

#include <stdint.h>

#define NRF_GPIO_PIN_MAP(port, pin)	(((port) << 5) | ((pin) & 0x1F))

void nrf_gpio_cfg_output(uint32_t pin_number);
void nrf_gpio_pin_clear(uint32_t pin_number);

/** The last pin configured as an output, or UINT32_MAX if none. */
uint32_t fake_gpio_output_pin(void);
/** The last pin driven low, or UINT32_MAX if none. */
uint32_t fake_gpio_cleared_pin(void);
void     fake_gpio_reset(void);

#endif /* NRF_GPIO_H__ */
