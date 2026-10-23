/**
 * @file fake_gattc.c
 * @brief GATT client stand-ins: vendor UUIDs, discovery registration and the
 *        GATT queue, recording what the DFU client asks for (#244).
 *
 * Traces to: BLE-DD-TEST, SWE4-UT-FWUNIT.
 */

#include <string.h>

#include "ble.h"
#include "ble_db_discovery.h"
#include "nrf_ble_gatt.h"
#include "nrf_ble_gq.h"
#include "nrf_error.h"

#define FAKE_GATTC_MAX_UUIDS	4U
#define FAKE_GATTC_MAX_WRITES	64U
/** The type the SoftDevice gives the first vendor UUID after the NUS one. */
#define FAKE_GATTC_VS_TYPE	3U

static uint32_t		m_vs_added;
static ble_uuid_t	m_registered[FAKE_GATTC_MAX_UUIDS];
static uint32_t		m_registered_count;
static fake_gq_write_t	m_writes[FAKE_GATTC_MAX_WRITES];
static uint32_t		m_write_count;
static uint32_t		m_fail_count;
static uint32_t		m_fail_result;
static uint16_t		m_eff_mtu = 247U;

uint16_t nrf_ble_gatt_eff_mtu_get(nrf_ble_gatt_t const * p_gatt, uint16_t conn_handle)
{
	(void)p_gatt;
	(void)conn_handle;
	return m_eff_mtu;
}

void fake_gatt_set_eff_mtu(uint16_t mtu)	{ m_eff_mtu = mtu; }

uint32_t sd_ble_uuid_vs_add(ble_uuid128_t const * p_vs_uuid, uint8_t * p_uuid_type)
{
	(void)p_vs_uuid;
	*p_uuid_type = (uint8_t)(FAKE_GATTC_VS_TYPE + m_vs_added);
	m_vs_added++;
	return NRF_SUCCESS;
}

uint32_t ble_db_discovery_evt_register(ble_uuid_t const * p_uuid)
{
	if (m_registered_count < FAKE_GATTC_MAX_UUIDS)
	{
		m_registered[m_registered_count] = *p_uuid;
		m_registered_count++;
	}
	return NRF_SUCCESS;
}

uint32_t fake_db_discovery_registered_count(void)
{
	return m_registered_count;
}

const ble_uuid_t * fake_db_discovery_registered(uint32_t index)
{
	return &m_registered[index];
}

uint32_t nrf_ble_gq_item_add(nrf_ble_gq_t const * p_gatt_queue, nrf_ble_gq_req_t * p_req,
			     uint16_t conn_handle)
{
	fake_gq_write_t * p_write;

	(void)p_gatt_queue;
	if (m_fail_count > 0U)
	{
		m_fail_count--;
		return m_fail_result;
	}
	if ((p_req->type != NRF_BLE_GQ_REQ_GATTC_WRITE) || (m_write_count >= FAKE_GATTC_MAX_WRITES))
	{
		return NRF_ERROR_NO_MEM;
	}
	p_write              = &m_writes[m_write_count];
	p_write->conn_handle = conn_handle;
	p_write->handle      = p_req->params.gattc_write.handle;
	p_write->write_op    = p_req->params.gattc_write.write_op;
	p_write->len         = p_req->params.gattc_write.len;
	(void)memcpy(p_write->data, p_req->params.gattc_write.p_value, p_write->len);
	m_write_count++;
	return NRF_SUCCESS;
}

/* Packet writes go to the SoftDevice directly; they are recorded with the
 * queued ones, in order, and fail as the queue's do. */
uint32_t sd_ble_gattc_write(uint16_t conn_handle, ble_gattc_write_params_t const * p_write_params)
{
	fake_gq_write_t * p_write;

	if (m_fail_count > 0U)
	{
		m_fail_count--;
		return m_fail_result;
	}
	if (m_write_count >= FAKE_GATTC_MAX_WRITES)
	{
		return NRF_ERROR_RESOURCES;
	}
	p_write              = &m_writes[m_write_count];
	p_write->conn_handle = conn_handle;
	p_write->handle      = p_write_params->handle;
	p_write->write_op    = p_write_params->write_op;
	p_write->len         = p_write_params->len;
	(void)memcpy(p_write->data, p_write_params->p_value, p_write->len);
	m_write_count++;
	return NRF_SUCCESS;
}

static ble_gap_conn_params_t	m_param_update;
static uint32_t			m_param_updates;

uint32_t sd_ble_gap_conn_param_update(uint16_t conn_handle, ble_gap_conn_params_t const * p_conn_params)
{
	(void)conn_handle;
	m_param_update = *p_conn_params;
	m_param_updates++;
	return NRF_SUCCESS;
}

const ble_gap_conn_params_t * fake_gap_param_update(void)	{ return &m_param_update; }
uint32_t fake_gap_param_update_count(void)			{ return m_param_updates; }

uint32_t fake_gq_write_count(void)			{ return m_write_count; }
const fake_gq_write_t * fake_gq_write(uint32_t index)	{ return &m_writes[index]; }

void fake_gq_fail_next(uint32_t count, uint32_t result)
{
	m_fail_count  = count;
	m_fail_result = result;
}

void fake_gq_reset(void)
{
	m_vs_added         = 0U;
	m_registered_count = 0U;
	m_write_count      = 0U;
	m_fail_count       = 0U;
	m_fail_result      = NRF_SUCCESS;
	m_eff_mtu          = 247U;
	m_param_updates    = 0U;
}
