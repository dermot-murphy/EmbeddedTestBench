/** Host-test stand-in for database discovery. Traces to: BLE-DD-TEST. */
#ifndef BLE_DB_DISCOVERY_H__
#define BLE_DB_DISCOVERY_H__

#include "ble.h"
#include "nrf_ble_gq.h"

#define BLE_GATT_DB_MAX_CHARS	6

typedef enum
{
	BLE_DB_DISCOVERY_COMPLETE,
	BLE_DB_DISCOVERY_ERROR,
	BLE_DB_DISCOVERY_SRV_NOT_FOUND,
	BLE_DB_DISCOVERY_AVAILABLE
} ble_db_discovery_evt_type_t;

typedef struct
{
	ble_uuid_t	uuid;
	uint16_t	handle_decl;
	uint16_t	handle_value;
} ble_gattc_char_t;

typedef struct
{
	ble_gattc_char_t	characteristic;
	uint16_t		cccd_handle;
	uint16_t		ext_prop_handle;
	uint16_t		user_desc_handle;
	uint16_t		report_ref_handle;
} ble_gatt_db_char_t;

typedef struct
{
	ble_uuid_t		srv_uuid;
	uint8_t			char_count;
	ble_gatt_db_char_t	charateristics[BLE_GATT_DB_MAX_CHARS];
} ble_gatt_db_srv_t;

typedef struct
{
	ble_db_discovery_evt_type_t	evt_type;
	uint16_t			conn_handle;
	union
	{
		ble_gatt_db_srv_t	discovered_db;
		uint32_t		err_code;
	} params;
} ble_db_discovery_evt_t;

uint32_t ble_db_discovery_evt_register(ble_uuid_t const * p_uuid);
/** The service UUIDs registered, in order. */
uint32_t		fake_db_discovery_registered_count(void);
const ble_uuid_t *	fake_db_discovery_registered(uint32_t index);
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
uint32_t ble_db_discovery_start(ble_db_discovery_t * p_db_discovery, uint16_t conn_handle);

/** Times discovery was started, and on which link the last time. */
uint32_t fake_db_discovery_starts(void);
uint16_t fake_db_discovery_conn_handle(void);
void     fake_db_discovery_set_start_result(uint32_t result);
void     fake_db_discovery_reset(void);

#endif
