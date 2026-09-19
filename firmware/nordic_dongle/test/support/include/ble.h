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

typedef struct
{
	ble_evt_hdr_t	header;
	union
	{
		ble_gap_evt_t gap_evt;
	} evt;
} ble_evt_t;

#endif /* BLE_H__ */
