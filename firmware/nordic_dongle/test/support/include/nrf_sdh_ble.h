/**
 * @file nrf_sdh_ble.h
 * @brief Host-test stand-in: observer registration becomes a no-op.
 *
 * Traces to: BLE-DD-TEST.
 */

#ifndef NRF_SDH_BLE_H__
#define NRF_SDH_BLE_H__

#include <stdint.h>

#include "ble.h"
#include "nrf_error.h"

#ifndef NRF_SDH_BLE_CENTRAL_LINK_COUNT
#define NRF_SDH_BLE_CENTRAL_LINK_COUNT	1
#endif

/* Called only by main.c, which no unit test links; declared for the MISRA
 * C:2012 check, which needs every function main.c calls declared (17.3). */
ret_code_t nrf_sdh_ble_default_cfg_set(uint8_t conn_cfg_tag, uint32_t * p_ram_start);
ret_code_t nrf_sdh_ble_enable(uint32_t * p_app_ram_start);

/* On the target this places an observer in a linker section. On the host the
 * test calls the handler directly, which is the point of the seam. The
 * priority is kept beside the handler, as the SDK's section name keeps it. */
#define NRF_SDH_BLE_OBSERVER(_name, _prio, _handler, _context)		\
	static const struct						\
	{								\
		void (* handler)(ble_evt_t const *, void *);		\
		void *		p_context;				\
		uint32_t	priority;				\
	} _name = { (_handler), (_context), (_prio) }

#endif /* NRF_SDH_BLE_H__ */
