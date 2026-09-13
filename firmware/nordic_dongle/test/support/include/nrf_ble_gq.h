/** Host-test stand-in for the GATT queue. Traces to: BLE-DD-TEST. */
#ifndef NRF_BLE_GQ_H__
#define NRF_BLE_GQ_H__
typedef struct { int unused; } nrf_ble_gq_t;
#define NRF_BLE_GQ_DEF(name, links, size)	static nrf_ble_gq_t name
#endif
