/**
 * @file nrf_sdh_ble.h
 * @brief Host-test stand-in: observer registration becomes a no-op.
 *
 * Traces to: BLE-DD-TEST.
 */

#ifndef NRF_SDH_BLE_H__
#define NRF_SDH_BLE_H__

#include "ble.h"

#ifndef NRF_SDH_BLE_CENTRAL_LINK_COUNT
#define NRF_SDH_BLE_CENTRAL_LINK_COUNT	1
#endif

/* On the target this places an observer in a linker section. On the host the
 * test calls the handler directly, which is the point of the seam. */
#define NRF_SDH_BLE_OBSERVER(_name, _prio, _handler, _context)	\
	static void (* const _name ## _unused)(ble_evt_t const *, void *) = (_handler)

#endif /* NRF_SDH_BLE_H__ */
