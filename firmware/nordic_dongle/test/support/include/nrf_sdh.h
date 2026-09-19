/**
 * @file nrf_sdh.h
 * @brief Host-test stand-in for SoftDevice enablement.
 *
 * Traces to: BLE-DD-TEST.
 */

#ifndef NRF_SDH_H__
#define NRF_SDH_H__

#include <stdbool.h>

#include "nrf_error.h"

uint32_t nrf_sdh_enable_request(void);
bool     nrf_sdh_is_enabled(void);

#endif /* NRF_SDH_H__ */
