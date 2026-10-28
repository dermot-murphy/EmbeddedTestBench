/**
 * @file fake_dfu_client.c
 * @brief The DFU client, for tests of the dfucp and dfupkt commands (#244).
 *
 * Traces to: BLE-DD-TEST, SWE4-UT-FWUNIT.
 */

#include <string.h>

#include "dfu_client.h"
#include "fakes.h"
#include "nrf_error.h"

static bool	m_ready;
static uint8_t	m_response[DFU_CLIENT_MAX_RESPONSE];
static uint16_t	m_response_len;
static uint8_t	m_last[DFU_CLIENT_MAX_WRITE];
static uint16_t	m_last_len;
static uint32_t	m_last_timeout_ms;
static uint32_t	m_packets;
static uint32_t	m_packet_result;
static uint16_t	m_att_mtu = 247U;

uint32_t dfu_client_init(nrf_ble_gq_t * p_gatt_queue, nrf_ble_gatt_t * p_gatt)
{
	(void)p_gatt_queue;
	(void)p_gatt;
	return NRF_SUCCESS;
}
bool     dfu_client_is_ready(void)			{ return m_ready; }
uint16_t dfu_client_att_mtu(void)			{ return m_att_mtu; }
void     dfu_client_on_ble_evt(const ble_evt_t * p_ble_evt)	{ (void)p_ble_evt; }
void     dfu_client_on_db_disc_evt(ble_db_discovery_evt_t * p_evt)	{ (void)p_evt; }

uint32_t dfu_client_control(const uint8_t * p_data, uint16_t length, uint32_t timeout_ms,
			    uint8_t * p_response, uint16_t * p_response_len)
{
	(void)memcpy(m_last, p_data, length);
	m_last_len        = length;
	m_last_timeout_ms = timeout_ms;
	(void)memcpy(p_response, m_response, m_response_len);
	*p_response_len = m_response_len;
	return NRF_SUCCESS;
}

uint32_t dfu_client_packet(const uint8_t * p_data, uint16_t length, uint32_t timeout_ms,
			   uint16_t * p_piece, uint16_t * p_pieces)
{
	uint16_t piece = (uint16_t)(m_att_mtu - 3U);

	(void)timeout_ms;
	*p_piece  = piece;
	*p_pieces = 0U;
	if (m_packet_result != NRF_SUCCESS)
	{
		return m_packet_result;
	}
	(void)memcpy(m_last, p_data, length);
	m_last_len = length;
	m_packets++;
	*p_pieces = (uint16_t)((length + piece - 1U) / piece);
	return NRF_SUCCESS;
}

void fake_dfu_set_ready(bool ready)	{ m_ready = ready; }

void fake_dfu_set_response(const uint8_t * p_data, uint16_t length)
{
	(void)memcpy(m_response, p_data, length);
	m_response_len = length;
}

const uint8_t * fake_dfu_last(void)		{ return m_last; }
uint16_t        fake_dfu_last_length(void)	{ return m_last_len; }
uint32_t        fake_dfu_last_timeout_ms(void)	{ return m_last_timeout_ms; }
uint32_t        fake_dfu_packets(void)		{ return m_packets; }
void            fake_dfu_set_packet_result(uint32_t result)	{ m_packet_result = result; }
void            fake_dfu_set_att_mtu(uint16_t mtu)	{ m_att_mtu = mtu; }

void fake_dfu_reset(void)
{
	m_ready           = false;
	m_response_len    = 0U;
	m_last_len        = 0U;
	m_last_timeout_ms = 0U;
	m_packets         = 0U;
	m_packet_result   = NRF_SUCCESS;
	m_att_mtu         = 247U;
}
