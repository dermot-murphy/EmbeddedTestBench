/** Host-test stand-in for the GATT queue. Traces to: BLE-DD-TEST. */
#ifndef NRF_BLE_GQ_H__
#define NRF_BLE_GQ_H__

#include <stdint.h>

#include "ble.h"

typedef struct { int unused; } nrf_ble_gq_t;
#define NRF_BLE_GQ_DEF(name, links, size)	static nrf_ble_gq_t name

typedef enum
{
	NRF_BLE_GQ_REQ_GATTC_READ,
	NRF_BLE_GQ_REQ_GATTC_WRITE,
	NRF_BLE_GQ_REQ_SRV_DISCOVERY,
	NRF_BLE_GQ_REQ_CHAR_DISCOVERY,
	NRF_BLE_GQ_REQ_DESC_DISCOVERY,
	NRF_BLE_GQ_REQ_GATTS_HVX
} nrf_ble_gq_req_type_t;

typedef void (*nrf_ble_gq_req_error_cb_t)(uint32_t nrf_error, void * p_context,
					  uint16_t conn_handle);

typedef struct
{
	nrf_ble_gq_req_error_cb_t	cb;
	void *				p_ctx;
} nrf_ble_gq_req_error_handler_t;

typedef struct
{
	nrf_ble_gq_req_type_t		type;
	nrf_ble_gq_req_error_handler_t	error_handler;
	union
	{
		ble_gattc_write_params_t gattc_write;
	} params;
} nrf_ble_gq_req_t;

uint32_t nrf_ble_gq_item_add(nrf_ble_gq_t const * p_gatt_queue, nrf_ble_gq_req_t * p_req,
			     uint16_t conn_handle);

/** One write the queue was given, as the fake records it. */
typedef struct
{
	uint16_t	conn_handle;
	uint16_t	handle;
	uint8_t		write_op;
	uint16_t	len;
	uint8_t		data[244];
} fake_gq_write_t;

uint32_t		fake_gq_write_count(void);
const fake_gq_write_t *	fake_gq_write(uint32_t index);
/** The next @p count adds return @p result instead of succeeding. */
void			fake_gq_fail_next(uint32_t count, uint32_t result);
void			fake_gq_reset(void);

#endif
