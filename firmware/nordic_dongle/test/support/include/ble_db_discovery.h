/** Host-test stand-in for database discovery. Traces to: BLE-DD-TEST. */
#ifndef BLE_DB_DISCOVERY_H__
#define BLE_DB_DISCOVERY_H__

#include "ble.h"
#include "nrf_ble_gq.h"

typedef struct { uint16_t conn_handle; uint8_t evt_type; } ble_db_discovery_evt_t;
typedef struct { int unused; } ble_db_discovery_t;
typedef void (*ble_db_discovery_evt_handler_t)(ble_db_discovery_evt_t * p_evt);

typedef struct
{
	ble_db_discovery_evt_handler_t	evt_handler;
	nrf_ble_gq_t *			p_gatt_queue;
} ble_db_discovery_init_t;

#define BLE_DB_DISCOVERY_DEF(_name)	static ble_db_discovery_t _name

uint32_t ble_db_discovery_init(const ble_db_discovery_init_t * p_init);
void     ble_db_discovery_on_ble_evt(ble_evt_t const * p_ble_evt, void * p_context);

#endif
