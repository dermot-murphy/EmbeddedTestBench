/**
 * @file nrf_soc.h
 * @brief Host-test stand-in: a reset is recorded, not performed.
 *
 * Traces to: BLE-DD-TEST.
 */

#ifndef NRF_SOC_H__
#define NRF_SOC_H__

#include "nrf_error.h"

/** Times NVIC_SystemReset was called. */
extern uint32_t fake_system_resets;

void NVIC_SystemReset(void);

#endif /* NRF_SOC_H__ */
