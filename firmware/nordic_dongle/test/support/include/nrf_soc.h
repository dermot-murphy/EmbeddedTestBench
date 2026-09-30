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
extern uint32_t fake_g_system_resets;

void NVIC_SystemReset(void);

uint32_t sd_power_gpregret_set(uint8_t gpregret_id, uint32_t gpregret_msk);
uint32_t sd_power_gpregret_clr(uint8_t gpregret_id, uint32_t gpregret_msk);

/** Stand-in for the POWER peripheral: only the retained register is modelled,
 *  because that is the only part the firmware touches. */
typedef struct { uint32_t GPREGRET; } fake_power_t;
extern fake_power_t * const NRF_POWER;

/** What the bootloader would find in the retained register after a reset. */
uint32_t fake_retained_register(void);
void     fake_retained_register_reset(void);

#endif /* NRF_SOC_H__ */
