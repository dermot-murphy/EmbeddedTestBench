/**
 * @file ble_nus_c.h
 * @brief Host-test stand-in for the UART service client (SDK 17 shape).
 *
 * The initialisation structure carries ``p_gatt_queue`` and ``error_handler``,
 * as SDK 17's does - the members whose absence in SDK 15.2 exposed defect D-26.
 *
 * Traces to: BLE-DD-TEST.
 */

#ifndef BLE_NUS_C_H__
#define BLE_NUS_C_H__

#include <stdbool.h>
#include <stdint.h>

#include "ble.h"
#include "nrf_ble_gq.h"

#define BLE_NUS_MAX_DATA_LEN	244

typedef enum
{
	BLE_NUS_C_EVT_DISCOVERY_COMPLETE = 0,
	BLE_NUS_C_EVT_NUS_TX_EVT,
	BLE_NUS_C_EVT_DISCONNECTED
} ble_nus_c_evt_type_t;

typedef struct
{
	uint16_t nus_rx_handle;
	uint16_t nus_tx_handle;
	uint16_t nus_tx_cccd_handle;
} ble_nus_c_handles_t;

typedef struct
{
	ble_nus_c_evt_type_t	evt_type;
	uint16_t		conn_handle;
	ble_nus_c_handles_t	handles;
	const uint8_t *		p_data;
	uint16_t		data_len;
} ble_nus_c_evt_t;

typedef struct ble_nus_c_s ble_nus_c_t;
typedef void (*ble_nus_c_evt_handler_t)(ble_nus_c_t * p_nus_c, ble_nus_c_evt_t const * p_evt);
typedef void (*ble_nus_c_error_handler_t)(uint32_t error);

struct ble_nus_c_s
{
	uint16_t		conn_handle;
	ble_nus_c_handles_t	handles;
	ble_nus_c_evt_handler_t	evt_handler;
};

typedef struct
{
	ble_nus_c_evt_handler_t		evt_handler;
	nrf_ble_gq_t *			p_gatt_queue;
	ble_nus_c_error_handler_t	error_handler;
} ble_nus_c_init_t;

#define BLE_NUS_C_DEF(_name)	static ble_nus_c_t _name

uint32_t ble_nus_c_init(ble_nus_c_t * p_nus_c, ble_nus_c_init_t * p_init);
uint32_t ble_nus_c_handles_assign(ble_nus_c_t * p_nus_c, uint16_t conn_handle,
				  const ble_nus_c_handles_t * p_peer_handles);
uint32_t ble_nus_c_tx_notif_enable(ble_nus_c_t * p_nus_c);
uint32_t ble_nus_c_string_send(ble_nus_c_t * p_nus_c, uint8_t * p_string, uint16_t length);
void     ble_nus_c_on_ble_evt(ble_evt_t const * p_ble_evt, void * p_context);
void     ble_nus_c_on_db_disc_evt(ble_nus_c_t * p_nus_c, void * p_evt);

/* --- test control ------------------------------------------------- */

/** The last payload the firmware sent, and how many sends there have been. */
const uint8_t * fake_nus_sent(void);
uint16_t        fake_nus_sent_length(void);
uint32_t        fake_nus_send_count(void);
/** Make the next send fail. */
void            fake_nus_set_send_result(uint32_t result);
/** True once the firmware enabled notifications. */
bool            fake_nus_notifications_enabled(void);
/** Deliver an event to the handler the firmware registered. */
void            fake_nus_fire(ble_nus_c_evt_type_t type, const uint8_t * data, uint16_t length);
void            fake_nus_reset(void);

#endif /* BLE_NUS_C_H__ */
