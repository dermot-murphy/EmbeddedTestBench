/**
 * @file fake_nus_client.c
 * @brief The UART client, for tests of the command parser.
 *
 * Traces to: BLE-DD-TEST, SWE4-UT-FWUNIT.
 */

#include <stdarg.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "fakes.h"
#include "nus_client.h"
#include "timestamp.h"


/* ------------------------------------------------------------------ */
/* The UART client                                                     */
/* ------------------------------------------------------------------ */

static bool	m_ready;
static bool	m_connected;
static uint32_t	m_interval_us;
static char	m_reply[PROTO_MAX_PAYLOAD];
static uint64_t	m_round_trip_us;
static bool	m_replies;
static uint32_t	m_write_result;
static uint32_t	m_writes;
static uint32_t	m_commands;
static uint8_t	m_payload[PROTO_MAX_PAYLOAD];
static uint16_t	m_payload_length;
static uint32_t	m_connects;
static uint32_t	m_disconnects;
static uint32_t	m_connect_result;

uint32_t nus_client_init(nrf_ble_gq_t * p_gatt_queue, ble_db_discovery_t * p_db_discovery)
{
	(void)p_gatt_queue;
	(void)p_db_discovery;
	return 0U;
}

static uint32_t	m_connect_timeout_ms;

uint32_t nus_client_connect(const ble_gap_addr_t * p_address, uint32_t timeout_ms)
{
	(void)p_address;
	m_connect_timeout_ms = timeout_ms;
	if (m_connect_result != 0U)
	{
		return m_connect_result;
	}
	m_connects++;
	return 0U;
}

uint32_t nus_client_disconnect(void)
{
	if (!m_connected)
	{
		return NRF_ERROR_INVALID_STATE;
	}
	m_disconnects++;
	return 0U;
}

bool     nus_client_is_ready(void)	{ return m_ready; }
bool     nus_client_is_connected(void)	{ return m_connected; }
uint32_t nus_client_interval_us(void)	{ return m_interval_us; }

uint32_t nus_client_write(const uint8_t * p_data, uint16_t length)
{
	if (!m_ready)
	{
		return NRF_ERROR_INVALID_STATE;
	}
	if (m_write_result != 0U)
	{
		return m_write_result;
	}
	m_writes++;
	m_payload_length = (length <= PROTO_MAX_PAYLOAD) ? length : PROTO_MAX_PAYLOAD;
	(void)memcpy(m_payload, p_data, m_payload_length);
	return 0U;
}

static uint32_t	m_command_timeout_ms;

uint32_t fake_nus_client_command_timeout_ms(void)	{ return m_command_timeout_ms; }

uint32_t nus_client_command(const uint8_t * p_data, uint16_t length,
			    uint32_t timeout_ms, nus_response_t * p_response)
{
	m_command_timeout_ms = timeout_ms;

	if (!m_ready)
	{
		return NRF_ERROR_INVALID_STATE;
	}
	m_commands++;
	m_payload_length = (length <= PROTO_MAX_PAYLOAD) ? length : PROTO_MAX_PAYLOAD;
	(void)memcpy(m_payload, p_data, m_payload_length);

	(void)memset(p_response, 0, sizeof(*p_response));
	p_response->tx_us = timestamp_now_us();
	if (m_replies)
	{
		p_response->replied       = true;
		p_response->rx_us         = p_response->tx_us + m_round_trip_us;
		p_response->round_trip_us = m_round_trip_us;
		p_response->length        = (uint16_t)strlen(m_reply);
		(void)memcpy(p_response->data, m_reply, p_response->length);
	}

	return 0U;
}

void nus_client_on_ble_evt(const ble_evt_t * p_ble_evt)	{ (void)p_ble_evt; }
void nus_client_on_db_disc_evt(void * p_evt)		{ (void)p_evt; }

void fake_nus_client_set_ready(bool ready)		{ m_ready = ready; m_connected = ready || m_connected; }
void fake_nus_client_set_connected(bool connected)	{ m_connected = connected; }
void fake_nus_client_set_interval_us(uint32_t interval_us)	{ m_interval_us = interval_us; }

void fake_nus_client_set_reply(const char * text, uint64_t round_trip_us)
{
	(void)strncpy(m_reply, text, PROTO_MAX_PAYLOAD - 1U);
	m_reply[PROTO_MAX_PAYLOAD - 1U] = '\0';
	m_round_trip_us                 = round_trip_us;
	m_replies                       = true;
}

void fake_nus_client_set_no_reply(void)			{ m_replies = false; }
void fake_nus_client_set_write_result(uint32_t result)	{ m_write_result = result; }
uint32_t fake_nus_client_writes(void)			{ return m_writes; }
uint32_t fake_nus_client_commands(void)			{ return m_commands; }
const uint8_t * fake_nus_client_last_payload(void)	{ return m_payload; }
uint16_t fake_nus_client_last_length(void)		{ return m_payload_length; }
uint32_t fake_nus_client_connects(void)			{ return m_connects; }
uint32_t fake_nus_client_connect_timeout_ms(void)	{ return m_connect_timeout_ms; }
uint32_t fake_nus_client_disconnects(void)		{ return m_disconnects; }
void     fake_nus_client_set_connect_result(uint32_t result)	{ m_connect_result = result; }

void fake_nus_client_reset(void)
{
	m_ready          = false;
	m_connected      = false;
	m_connect_timeout_ms = 0U;
	m_interval_us    = 0U;
	m_reply[0]       = '\0';
	m_round_trip_us  = 0U;
	m_replies        = false;
	m_write_result   = 0U;
	m_writes         = 0U;
	m_commands       = 0U;
	m_payload_length = 0U;
	m_connects       = 0U;
	m_disconnects    = 0U;
	m_connect_result = 0U;
}

