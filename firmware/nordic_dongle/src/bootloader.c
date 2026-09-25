/**
 * @file bootloader.c
 * @brief Entering the dongle's DFU bootloader on command.
 *
 * Traces to: BLE-FR-013, BLE-DD-BOOTLOADER.
 */

#include "bootloader.h"

#include <stdint.h>

#include "nrf_delay.h"
#include "nrf_error.h"
#include "nrf_gpio.h"
#include "nrf_sdh.h"
#include "nrf_soc.h"

/** The value Nordic's bootloader looks for in GPREGRET to stay in DFU mode. */
#define BOOTLOADER_DFU_START		0xB1U

/**
 * A GPIO wired to the chip's own reset line. On the PCA10059 P0.19 is joined to
 * nRESET, which is how Nordic's USB DFU trigger resets the dongle
 * (BSP_SELF_PINRESET_PIN in the SDK's pca10059.h).
 */
#define SELF_PINRESET_PIN		NRF_GPIO_PIN_MAP(0, 19)

/** How long to hold the reset pin before concluding it is not wired. */
#define SELF_PINRESET_WAIT_MS		10U

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

	/* The PCA10059 open bootloader in nRF5 SDK 17.1.0 is built with
	 * NRF_BL_DFU_ENTER_METHOD_GPREGRET 0 and NRF_BL_DFU_ENTER_METHOD_PINRESET
	 * 1: it ignores GPREGRET and enters DFU only after a pin reset. A soft
	 * reset alone brings the application straight back, which is what was
	 * observed on hardware. So pull the dongle's own reset pin; GPREGRET is
	 * still written above for a bootloader built to honour it. */
	nrf_gpio_cfg_output(SELF_PINRESET_PIN);
	nrf_gpio_pin_clear(SELF_PINRESET_PIN);
	nrf_delay_ms(SELF_PINRESET_WAIT_MS);

	/* Still running: the pin is not wired to reset on this board. */
	NVIC_SystemReset();
}
