/**
 * @file bootloader.c
 * @brief Entering the dongle's DFU bootloader on command.
 *
 * Traces to: BLE-FR-013, BLE-DD-BOOTLOADER.
 */

#include "bootloader.h"

#include <stdint.h>

#include "nrf_error.h"
#include "nrf_sdh.h"
#include "nrf_soc.h"

/** The value Nordic's bootloader looks for in GPREGRET to stay in DFU mode. */
#define BOOTLOADER_DFU_START		0xB1U

void bootloader_enter_dfu(void)
{
	/* GPREGRET survives a reset, which is the whole point of it. It must be
	 * written through the SoftDevice while that is enabled - writing the
	 * register directly then is undefined - and directly when it is not. */
	if (nrf_sdh_is_enabled())
	{
		(void)sd_power_gpregret_clr(0U, 0xFFFFFFFFU);
		(void)sd_power_gpregret_set(0U, BOOTLOADER_DFU_START);
	}
	else
	{
		NRF_POWER->GPREGRET = BOOTLOADER_DFU_START;
	}

	NVIC_SystemReset();
}
