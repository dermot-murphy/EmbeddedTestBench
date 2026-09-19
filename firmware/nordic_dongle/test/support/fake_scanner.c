/**
 * @file fake_scanner.c
 * @brief The scanner, for tests of the units that drive it.\n *\n * Address formatting and parsing are *not* faked: replies contain addresses,\n * and a fake that formatted them differently would make those assertions\n * meaningless.
 *
 * Traces to: BLE-DD-TEST, SWE4-UT-FWUNIT.
 */

#include <stdarg.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "fakes.h"
#include "ble_scanner.h"


/* ------------------------------------------------------------------ */
/* The scanner                                                         */
/* ------------------------------------------------------------------ */

static scanner_sensor_t	m_sensors[PROTO_MAX_SENSORS];
static uint32_t		m_sensor_count;
static bool		m_scanning;
static bool		m_profiling;
static char		m_profile_address[20];
static uint32_t		m_starts;
static uint32_t		m_stops;
static uint32_t		m_clears;
static uint32_t		m_start_result;
static uint32_t		m_duration_ms;
static scanner_filter_t	m_filter;
static uint32_t		m_received;
static uint32_t		m_reported;

uint32_t scanner_init(void)	{ return 0U; }

uint32_t scanner_start(const scanner_filter_t * p_filter, uint32_t duration_ms)
{
	if (p_filter != NULL)
	{
		m_filter = *p_filter;
	}
	m_duration_ms = duration_ms;
	if (m_start_result != 0U)
	{
		return m_start_result;
	}
	m_starts++;
	m_scanning = true;
	return 0U;
}

uint32_t scanner_stop(void)
{
	m_stops++;
	m_scanning = false;
	return 0U;
}

bool     scanner_is_active(void)	{ return m_scanning; }
void     scanner_clear(void)		{ m_clears++; m_sensor_count = 0U; }
uint32_t scanner_count(void)		{ return m_sensor_count; }

const scanner_sensor_t * scanner_get(uint32_t index)
{
	return (index < m_sensor_count) ? &m_sensors[index] : NULL;
}

uint32_t scanner_find(const ble_gap_addr_t * p_address)
{
	uint32_t index;

	for (index = 0U; index < m_sensor_count; index++)
	{
		if (memcmp(m_sensors[index].address.addr, p_address->addr, BLE_GAP_ADDR_LEN) == 0)
		{
			return index;
		}
	}

	return PROTO_MAX_SENSORS;
}

void scanner_profile_start(const ble_gap_addr_t * p_address)
{
	m_profiling = true;
	if (p_address != NULL)
	{
		scanner_format_address(p_address, m_profile_address);
	}
	else
	{
		m_profile_address[0] = '\0';
	}
}

void scanner_profile_stop(void)		{ m_profiling = false; }
bool scanner_profile_is_active(void)	{ return m_profiling; }

void scanner_profile_counters(uint32_t * p_received, uint32_t * p_reported)
{
	*p_received = m_received;
	*p_reported = m_reported;
}

void scanner_on_ble_evt(const ble_evt_t * p_ble_evt)	{ (void)p_ble_evt; }

/* Address formatting is not faked: the command parser's replies contain
 * addresses, and a fake that formatted them differently from the firmware would
 * make those assertions meaningless. */
void scanner_format_address(const ble_gap_addr_t * p_address, char * buffer)
{
	(void)sprintf(buffer, "%02X:%02X:%02X:%02X:%02X:%02X",
		      p_address->addr[5], p_address->addr[4], p_address->addr[3],
		      p_address->addr[2], p_address->addr[1], p_address->addr[0]);
}

bool scanner_parse_address(const char * text, ble_gap_addr_t * p_address)
{
	unsigned int	octet[BLE_GAP_ADDR_LEN];
	unsigned int	type = 1U;
	const char *	slash;
	uint32_t	index;

	if (sscanf(text, "%2x:%2x:%2x:%2x:%2x:%2x",
		   &octet[0], &octet[1], &octet[2], &octet[3], &octet[4], &octet[5]) != 6)
	{
		return false;
	}
	slash = strchr(text, '/');
	if ((slash != NULL) && (sscanf(&slash[1], "%u", &type) != 1))
	{
		return false;
	}
	for (index = 0U; index < BLE_GAP_ADDR_LEN; index++)
	{
		p_address->addr[BLE_GAP_ADDR_LEN - 1U - index] = (uint8_t)octet[index];
	}
	p_address->addr_type = (uint8_t)type;

	return true;
}

void fake_scanner_add(const char * address, uint8_t address_type, const char * name, int8_t rssi)
{
	scanner_sensor_t * p_sensor;

	if (m_sensor_count >= PROTO_MAX_SENSORS)
	{
		return;
	}
	p_sensor = &m_sensors[m_sensor_count];
	(void)memset(p_sensor, 0, sizeof(*p_sensor));
	(void)scanner_parse_address(address, &p_sensor->address);
	p_sensor->address.addr_type = address_type;
	p_sensor->rssi              = rssi;
	p_sensor->seen              = 1U;
	(void)strncpy(p_sensor->name, name, PROTO_MAX_NAME - 1U);
	p_sensor->name_length       = (uint8_t)strlen(p_sensor->name);
	m_sensor_count++;
}

void fake_scanner_set_active(bool active)		{ m_scanning = active; }
void fake_scanner_set_profiling(bool profiling)		{ m_profiling = profiling; }
void fake_scanner_set_counters(uint32_t received, uint32_t reported)
{
	m_received = received;
	m_reported = reported;
}
uint32_t     fake_scanner_starts(void)			{ return m_starts; }
uint32_t     fake_scanner_stops(void)			{ return m_stops; }
uint32_t     fake_scanner_clears(void)			{ return m_clears; }
const char * fake_scanner_profile_address(void)		{ return m_profile_address; }
uint32_t     fake_scanner_last_duration_ms(void)	{ return m_duration_ms; }
const char * fake_scanner_filter_name(void)		{ return m_filter.name; }
int8_t       fake_scanner_filter_rssi(void)		{ return m_filter.min_rssi; }
bool         fake_scanner_filter_active(void)		{ return m_filter.active; }
void         fake_scanner_set_start_result(uint32_t result)	{ m_start_result = result; }

void fake_scanner_reset(void)
{
	m_sensor_count       = 0U;
	m_scanning           = false;
	m_profiling          = false;
	m_profile_address[0] = '\0';
	m_starts             = 0U;
	m_stops              = 0U;
	m_clears             = 0U;
	m_start_result       = 0U;
	m_duration_ms        = 0U;
	m_received           = 0U;
	m_reported           = 0U;
	(void)memset(&m_filter, 0, sizeof(m_filter));
}
