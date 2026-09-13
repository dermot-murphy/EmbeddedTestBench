/**
 * @file nrf_ble_scan.h
 * @brief Host-test stand-in for the scanning module.
 *
 * Traces to: BLE-DD-TEST.
 */

#ifndef NRF_BLE_SCAN_H__
#define NRF_BLE_SCAN_H__

#include <stdbool.h>
#include <stdint.h>

#include "ble.h"
#include "ble_gap.h"

typedef enum
{
	NRF_BLE_SCAN_EVT_FILTER_MATCH = 0,
	NRF_BLE_SCAN_EVT_WHITELIST_REQUEST,
	NRF_BLE_SCAN_EVT_NOT_FOUND,
	NRF_BLE_SCAN_EVT_SCAN_TIMEOUT,
	NRF_BLE_SCAN_EVT_CONNECTING_ERROR,
	NRF_BLE_SCAN_EVT_CONNECTED
} nrf_ble_scan_evt_t;

typedef struct
{
	nrf_ble_scan_evt_t	scan_evt_id;
	const ble_gap_evt_t *	p_gap_evt;
} scan_evt_t;

typedef struct { int unused; } nrf_ble_scan_t;

typedef struct
{
	const ble_gap_scan_params_t *	p_scan_param;
	bool				connect_if_match;
	const ble_gap_conn_params_t *	p_conn_param;
	uint8_t				conn_cfg_tag;
} nrf_ble_scan_init_t;

typedef void (*nrf_ble_scan_evt_handler_t)(scan_evt_t const * p_scan_evt);

#define NRF_BLE_SCAN_DEF(_name)		static nrf_ble_scan_t _name

uint32_t nrf_ble_scan_init(nrf_ble_scan_t *		p_scan_ctx,
			   nrf_ble_scan_init_t const *	p_init,
			   nrf_ble_scan_evt_handler_t	evt_handler);
uint32_t nrf_ble_scan_params_set(nrf_ble_scan_t * p_scan_ctx, ble_gap_scan_params_t const * p_scan_param);
uint32_t nrf_ble_scan_start(nrf_ble_scan_t * p_scan_ctx);
void     nrf_ble_scan_stop(void);

/* --- test control ------------------------------------------------- */

/** Scan parameters last given to nrf_ble_scan_params_set. */
const ble_gap_scan_params_t * fake_scan_params(void);
/** Calls to start and stop, so a test can check the radio was released. */
uint32_t fake_scan_start_count(void);
uint32_t fake_scan_stop_count(void);
/** Make the next start fail, to exercise the error path. */
void     fake_scan_set_start_result(uint32_t result);
/** Fire the handler the firmware registered. */
void     fake_scan_fire(nrf_ble_scan_evt_t event);
void     fake_scan_reset(void);

#endif /* NRF_BLE_SCAN_H__ */
