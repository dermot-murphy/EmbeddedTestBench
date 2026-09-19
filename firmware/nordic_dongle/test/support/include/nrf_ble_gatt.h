/** Host-test stand-in for the GATT module. Traces to: BLE-DD-TEST. */
#ifndef NRF_BLE_GATT_H__
#define NRF_BLE_GATT_H__

#include "ble.h"
#include "nrf_error.h"

typedef struct { int unused; } nrf_ble_gatt_t;
#define NRF_BLE_GATT_DEF(_name)		static nrf_ble_gatt_t _name

uint32_t nrf_ble_gatt_init(nrf_ble_gatt_t * p_gatt, void * evt_handler);
uint32_t nrf_ble_gatt_att_mtu_central_set(nrf_ble_gatt_t * p_gatt, uint16_t desired_mtu);

#endif
