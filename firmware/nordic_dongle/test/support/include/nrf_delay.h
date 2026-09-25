/**
 * @file nrf_delay.h
 * @brief Host-test stand-in: a delay is recorded, not waited.
 *
 * Traces to: BLE-DD-TEST.
 */

#ifndef NRF_DELAY_H__
#define NRF_DELAY_H__

#include <stdint.h>

void nrf_delay_ms(uint32_t ms_time);

/** Total milliseconds the firmware asked to wait. */
uint32_t fake_delay_total_ms(void);

#endif /* NRF_DELAY_H__ */
