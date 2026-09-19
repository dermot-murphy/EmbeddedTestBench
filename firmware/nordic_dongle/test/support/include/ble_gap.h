/**
 * @file ble_gap.h
 * @brief Host-test stand-in for the SoftDevice GAP types the firmware uses.
 *
 * Only the fields the firmware touches are declared. Anything the firmware does
 * not reference is deliberately absent: a fake that models more than the code
 * uses is a second implementation to keep in step.
 *
 * Traces to: BLE-DD-TEST.
 */

#ifndef BLE_GAP_H__
#define BLE_GAP_H__

#include <stdint.h>

#include "nrf_error.h"

#define BLE_GAP_ADDR_LEN			6
#define BLE_CONN_HANDLE_INVALID			0xFFFF

#define BLE_GAP_ADDR_TYPE_PUBLIC			0x00
#define BLE_GAP_ADDR_TYPE_RANDOM_STATIC			0x01
#define BLE_GAP_ADDR_TYPE_RANDOM_PRIVATE_RESOLVABLE	0x02
#define BLE_GAP_ADDR_TYPE_RANDOM_PRIVATE_NON_RESOLVABLE	0x03

#define BLE_GAP_PHY_AUTO			0x00
#define BLE_GAP_PHY_1MBPS			0x01
#define BLE_GAP_SCAN_FP_ACCEPT_ALL		0x00

#define BLE_GAP_TIMEOUT_SRC_SCAN		0x01
#define BLE_GAP_TIMEOUT_SRC_CONN		0x02

#define BLE_HCI_REMOTE_USER_TERMINATED_CONNECTION	0x13

#define BLE_GAP_AD_TYPE_SHORT_LOCAL_NAME	0x08
#define BLE_GAP_AD_TYPE_COMPLETE_LOCAL_NAME	0x09

typedef struct
{
	uint8_t	addr_id_peer;
	uint8_t	addr_type;
	uint8_t	addr[BLE_GAP_ADDR_LEN];
} ble_gap_addr_t;

typedef struct
{
	uint8_t *	p_data;
	uint16_t	len;
} ble_data_t;

typedef struct
{
	uint8_t	connectable;
	uint8_t	scannable;
	uint8_t	directed;
	uint8_t	scan_response;
	uint8_t	extended_pdu;
	uint8_t	status;
} ble_gap_adv_report_type_t;

typedef struct
{
	ble_gap_addr_t			peer_addr;
	int8_t				rssi;
	uint8_t				ch_index;
	ble_gap_adv_report_type_t	type;
	ble_data_t			data;
} ble_gap_evt_adv_report_t;

typedef struct
{
	uint16_t	min_conn_interval;
	uint16_t	max_conn_interval;
	uint16_t	slave_latency;
	uint16_t	conn_sup_timeout;
} ble_gap_conn_params_t;

typedef struct
{
	uint8_t			active;
	uint8_t			filter_policy;
	uint8_t			scan_phys;
	uint16_t		interval;
	uint16_t		window;
	uint16_t		timeout;
} ble_gap_scan_params_t;

typedef struct
{
	ble_gap_addr_t		peer_addr;
	ble_gap_conn_params_t	conn_params;
} ble_gap_evt_connected_t;

typedef struct { uint8_t reason; } ble_gap_evt_disconnected_t;
typedef struct { ble_gap_conn_params_t conn_params; } ble_gap_evt_conn_param_update_t;
typedef struct { uint8_t src; } ble_gap_evt_timeout_t;

typedef struct
{
	uint16_t	conn_handle;
	union
	{
		ble_gap_evt_adv_report_t		adv_report;
		ble_gap_evt_connected_t			connected;
		ble_gap_evt_disconnected_t		disconnected;
		ble_gap_evt_conn_param_update_t		conn_param_update;
		ble_gap_evt_timeout_t			timeout;
	} params;
} ble_gap_evt_t;

/* SoftDevice calls, recorded by the fake rather than performed. */
uint32_t sd_ble_gap_connect(const ble_gap_addr_t *		p_peer_addr,
			    const ble_gap_scan_params_t *	p_scan_params,
			    const ble_gap_conn_params_t *	p_conn_params,
			    uint8_t				conn_cfg_tag);
uint32_t sd_ble_gap_disconnect(uint16_t conn_handle, uint8_t hci_status_code);

#endif /* BLE_GAP_H__ */
