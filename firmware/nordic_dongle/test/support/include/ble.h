/**
 * @file ble.h
 * @brief Host-test stand-in for the SoftDevice event envelope.
 *
 * Traces to: BLE-DD-TEST.
 */

#ifndef BLE_H__
#define BLE_H__

#include <stdint.h>

#include "ble_gap.h"

#define BLE_GAP_EVT_CONNECTED			0x10
#define BLE_GAP_EVT_DISCONNECTED		0x11
#define BLE_GAP_EVT_CONN_PARAM_UPDATE		0x12
#define BLE_GAP_EVT_ADV_REPORT			0x1D
#define BLE_GAP_EVT_TIMEOUT			0x1B

typedef struct
{
	uint16_t	evt_id;
	uint16_t	evt_len;
} ble_evt_hdr_t;

/* GATT client: UUIDs, writes and notifications, with the SoftDevice's names
 * and values, for the DFU client (#244). */
#define BLE_UUID_TYPE_BLE			0x01
#define BLE_GATTC_EVT_HVX			0x38
#define BLE_GATT_OP_WRITE_REQ			0x01
#define BLE_GATT_OP_WRITE_CMD			0x02
#define BLE_GATT_HVX_NOTIFICATION		0x01

typedef struct
{
	uint16_t	uuid;
	uint8_t		type;
} ble_uuid_t;

typedef struct
{
	uint8_t		uuid128[16];
} ble_uuid128_t;

typedef struct
{
	uint8_t		write_op;
	uint8_t		flags;
	uint16_t	handle;
	uint16_t	offset;
	uint16_t	len;
	uint8_t const *	p_value;
} ble_gattc_write_params_t;

typedef struct
{
	uint16_t	handle;
	uint8_t		type;
	uint16_t	len;
	uint8_t		data[244];
} ble_gattc_evt_hvx_t;

typedef struct
{
	uint16_t	conn_handle;
	uint16_t	gatt_status;
	uint16_t	error_handle;
	union
	{
		ble_gattc_evt_hvx_t hvx;
	} params;
} ble_gattc_evt_t;

typedef struct
{
	ble_evt_hdr_t	header;
	union
	{
		ble_gap_evt_t	gap_evt;
		ble_gattc_evt_t	gattc_evt;
	} evt;
} ble_evt_t;

uint32_t sd_ble_uuid_vs_add(ble_uuid128_t const * p_vs_uuid, uint8_t * p_uuid_type);
uint32_t sd_ble_gattc_write(uint16_t conn_handle, ble_gattc_write_params_t const * p_write_params);

#endif /* BLE_H__ */
