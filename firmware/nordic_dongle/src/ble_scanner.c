/**
 * @file ble_scanner.c
 * @brief Scanning, the sensor table, and advertising-report timestamping.
 *
 * Traces to: BLE-FR-020 .. BLE-FR-023, BLE-FR-030, BLE-DD-SCANNER.
 */

#include "ble_scanner.h"

#include <stdio.h>
#include <string.h>

#include "app_error.h"
#include "ble_advdata.h"
#include "nrf_sdh_ble.h"
#include "nrf_ble_scan.h"

#include "app_ble_config.h"
#include "cdc_acm.h"
#include "timestamp.h"

/** Scan parameters. A 100 ms window inside a 100 ms interval is a continuous
 *  scan on one channel at a time: the radio is always listening, which is what
 *  an interval measurement needs. A duty-cycled scan would add its own gaps to
 *  the sensor's, and they would be indistinguishable afterwards. */
#define SCAN_INTERVAL_UNITS		160U		/**< 100 ms / 0.625 ms */
#define SCAN_WINDOW_UNITS		160U		/**< 100 ms / 0.625 ms */

NRF_BLE_SCAN_DEF(m_scan);

static scanner_sensor_t	m_sensors[PROTO_MAX_SENSORS];
static uint32_t		m_sensor_count;
static scanner_filter_t	m_filter;
static bool		m_scanning;

static bool		m_profiling;
static bool		m_profile_all;
static ble_gap_addr_t	m_profile_address;
static uint32_t		m_profile_received;
static uint32_t		m_profile_reported;

/**
 * @brief Extract the device name from an advertising payload.
 *
 * Tries the complete name, then the short one. A sensor that advertises neither
 * is reported with an empty name rather than a placeholder, because "no name"
 * is a fact about the sensor worth seeing.
 */
static void extract_name(const ble_data_t * p_data, char * name, uint8_t * p_length)
{
	uint16_t	offset = 0U;
	uint16_t	length;

	*p_length = 0U;
	name[0]   = '\0';

	length = ble_advdata_search(p_data->p_data, p_data->len, &offset,
				    BLE_GAP_AD_TYPE_COMPLETE_LOCAL_NAME);
	if (length == 0U)
	{
		offset = 0U;
		length = ble_advdata_search(p_data->p_data, p_data->len, &offset,
					    BLE_GAP_AD_TYPE_SHORT_LOCAL_NAME);
	}
	if ((length == 0U) || (offset == 0U))
	{
		return;
	}

	if (length > (PROTO_MAX_NAME - 1U))
	{
		length = PROTO_MAX_NAME - 1U;
	}
	(void)memcpy(name, &p_data->p_data[offset], length);
	name[length] = '\0';
	*p_length    = (uint8_t)length;
}

/**
 * @brief True when a report passes the active filter.
 */
static bool passes_filter(const ble_gap_evt_adv_report_t * p_report,
			  const char *                     name)
{
	if (m_filter.by_address &&
	    (memcmp(m_filter.address.addr, p_report->peer_addr.addr, BLE_GAP_ADDR_LEN) != 0))
	{
		return false;
	}
	if (m_filter.by_name && (strstr(name, m_filter.name) == NULL))
	{
		return false;
	}
	if ((m_filter.min_rssi != 0) && (p_report->rssi < m_filter.min_rssi))
	{
		return false;
	}

	return true;
}

/**
 * @brief Add or update the sensor table from one report.
 *
 * The table is bounded and does not evict: once full, a new address is ignored
 * rather than displacing one the host may already have selected.
 */
static void remember(const ble_gap_evt_adv_report_t * p_report,
		     const char *                     name,
		     uint8_t                          name_length,
		     uint64_t                         when_us)
{
	uint32_t	index = scanner_find(&p_report->peer_addr);
	scanner_sensor_t * p_sensor;

	if (index == PROTO_MAX_SENSORS)
	{
		if (m_sensor_count >= PROTO_MAX_SENSORS)
		{
			return;
		}
		index                    = m_sensor_count;
		m_sensor_count++;
		p_sensor                 = &m_sensors[index];
		(void)memset(p_sensor, 0, sizeof(*p_sensor));
		p_sensor->address        = p_report->peer_addr;
		p_sensor->first_us       = when_us;
	}
	else
	{
		p_sensor = &m_sensors[index];
	}

	p_sensor->rssi    = p_report->rssi;
	p_sensor->last_us = when_us;
	p_sensor->seen++;

	/* Keep the first name seen: a sensor that advertises its name only in a
	 * scan response should not appear to lose it on the next report. */
	if ((p_sensor->name_length == 0U) && (name_length > 0U))
	{
		(void)memcpy(p_sensor->name, name, (uint32_t)name_length + 1U);
		p_sensor->name_length = name_length;
	}
}

/**
 * @brief Emit one +adv event for a report being profiled.
 */
static void report_advertising(const ble_gap_evt_adv_report_t * p_report,
			       const char *                     name,
			       uint64_t                         when_us)
{
	char		address[18];
	char		payload[(PROTO_MAX_PAYLOAD * 2U) + 1U];
	uint16_t	length = p_report->data.len;
	uint16_t	index;

	scanner_format_address(&p_report->peer_addr, address);

	if (length > PROTO_MAX_PAYLOAD)
	{
		length = PROTO_MAX_PAYLOAD;
	}
	for (index = 0U; index < length; index++)
	{
		(void)sprintf(&payload[index * 2U], "%02x", p_report->data.p_data[index]);
	}
	payload[length * 2U] = '\0';

	m_profile_reported++;

	(void)cdc_acm_send_format(
		"+adv t=%llu addr=%s type=%u rssi=%d pdu=%u ch=%u name=%s data=%s",
		(unsigned long long)when_us,
		address,
		(unsigned)p_report->peer_addr.addr_type,
		(int)p_report->rssi,
		(unsigned)p_report->type.scan_response,
		(unsigned)p_report->ch_index,
		name,
		payload);
}

static void scan_event_handler(scan_evt_t const * p_scan_evt)
{
	switch (p_scan_evt->scan_evt_id)
	{
	case NRF_BLE_SCAN_EVT_SCAN_TIMEOUT:
		m_scanning = false;
		(void)cdc_acm_send_format("+scan t=%llu state=stopped",
					  (unsigned long long)timestamp_now_us());
		break;

	default:
		break;
	}
}

uint32_t scanner_init(void)
{
	nrf_ble_scan_init_t	init;
	ble_gap_scan_params_t	params;
	uint32_t		error;

	(void)memset(&init, 0, sizeof(init));
	(void)memset(&params, 0, sizeof(params));

	params.active        = 0U;
	params.interval      = SCAN_INTERVAL_UNITS;
	params.window        = SCAN_WINDOW_UNITS;
	params.timeout       = 0U;
	params.scan_phys     = BLE_GAP_PHY_1MBPS;
	params.filter_policy = BLE_GAP_SCAN_FILTER_POLICY_ACCEPT_ALL;

	init.p_scan_param     = &params;
	init.connect_if_match = false;

	error = nrf_ble_scan_init(&m_scan, &init, scan_event_handler);

	scanner_clear();

	return error;
}

uint32_t scanner_start(const scanner_filter_t * p_filter, uint32_t duration_ms)
{
	ble_gap_scan_params_t	params;
	uint32_t		error;

	if (p_filter != NULL)
	{
		m_filter = *p_filter;
	}
	else
	{
		(void)memset(&m_filter, 0, sizeof(m_filter));
	}

	(void)memset(&params, 0, sizeof(params));
	params.active        = m_filter.active ? 1U : 0U;
	params.interval      = SCAN_INTERVAL_UNITS;
	params.window        = SCAN_WINDOW_UNITS;
	/* GAP timeout counts 10 ms units; 0 means scan until stopped. */
	params.timeout       = (uint16_t)(duration_ms / 10U);
	params.scan_phys     = BLE_GAP_PHY_1MBPS;
	params.filter_policy = BLE_GAP_SCAN_FILTER_POLICY_ACCEPT_ALL;

	error = nrf_ble_scan_params_set(&m_scan, &params);
	if (error != NRF_SUCCESS)
	{
		return error;
	}

	error = nrf_ble_scan_start(&m_scan);
	if (error == NRF_SUCCESS)
	{
		m_scanning = true;
		(void)cdc_acm_send_format("+scan t=%llu state=started",
					  (unsigned long long)timestamp_now_us());
	}

	return error;
}

uint32_t scanner_stop(void)
{
	nrf_ble_scan_stop();
	if (m_scanning)
	{
		m_scanning = false;
		(void)cdc_acm_send_format("+scan t=%llu state=stopped",
					  (unsigned long long)timestamp_now_us());
	}

	return NRF_SUCCESS;
}

bool scanner_is_active(void)
{
	return m_scanning;
}

void scanner_clear(void)
{
	(void)memset(m_sensors, 0, sizeof(m_sensors));
	m_sensor_count = 0U;
}

uint32_t scanner_count(void)
{
	return m_sensor_count;
}

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
	m_profile_received = 0U;
	m_profile_reported = 0U;

	if (p_address != NULL)
	{
		m_profile_address = *p_address;
		m_profile_all     = false;
	}
	else
	{
		m_profile_all = true;
	}
	m_profiling = true;
}

void scanner_profile_stop(void)
{
	m_profiling = false;
}

bool scanner_profile_is_active(void)
{
	return m_profiling;
}

void scanner_profile_counters(uint32_t * p_received, uint32_t * p_reported)
{
	*p_received = m_profile_received;
	*p_reported = m_profile_reported;
}

void scanner_on_ble_evt(const ble_evt_t * p_ble_evt)
{
	const ble_gap_evt_adv_report_t *	p_report;
	uint64_t				when_us;
	char					name[PROTO_MAX_NAME];
	uint8_t					name_length;

	if (p_ble_evt->header.evt_id != BLE_GAP_EVT_ADV_REPORT)
	{
		return;
	}

	/* Timestamp first, before any parsing: every microsecond spent here is
	 * added to the interval being measured. */
	when_us  = timestamp_now_us();
	p_report = &p_ble_evt->evt.gap_evt.params.adv_report;

	extract_name(&p_report->data, name, &name_length);

	if (!passes_filter(p_report, name))
	{
		return;
	}

	remember(p_report, name, name_length, when_us);

	if (m_profiling)
	{
		bool wanted = m_profile_all ||
			      (memcmp(m_profile_address.addr,
				      p_report->peer_addr.addr,
				      BLE_GAP_ADDR_LEN) == 0);

		if (wanted)
		{
			m_profile_received++;
			report_advertising(p_report, name, when_us);
		}
	}
}

void scanner_format_address(const ble_gap_addr_t * p_address, char * buffer)
{
	/* BLE addresses are conventionally written most significant octet first,
	 * while the stack stores them least significant first. */
	(void)sprintf(buffer, "%02X:%02X:%02X:%02X:%02X:%02X",
		      p_address->addr[5], p_address->addr[4], p_address->addr[3],
		      p_address->addr[2], p_address->addr[1], p_address->addr[0]);
}

bool scanner_parse_address(const char * text, ble_gap_addr_t * p_address)
{
	unsigned int	octet[BLE_GAP_ADDR_LEN];
	unsigned int	type = (unsigned int)BLE_GAP_ADDR_TYPE_RANDOM_STATIC;
	int		converted;
	uint32_t	index;
	const char *	slash;

	converted = sscanf(text, "%2x:%2x:%2x:%2x:%2x:%2x",
			   &octet[0], &octet[1], &octet[2],
			   &octet[3], &octet[4], &octet[5]);
	if (converted != (int)BLE_GAP_ADDR_LEN)
	{
		return false;
	}

	/* An address alone does not say whether it is public or random, and
	 * connecting with the wrong type simply never finds the device. The type
	 * may therefore be appended as "AA:BB:CC:DD:EE:FF/0"; the host sends the
	 * type it learned from the scan. Random static is the default because
	 * that is what almost every sensor uses. */
	slash = strchr(text, '/');
	if (slash != NULL)
	{
		if (sscanf(&slash[1], "%u", &type) != 1)
		{
			return false;
		}
		if (type > (unsigned int)BLE_GAP_ADDR_TYPE_RANDOM_PRIVATE_NON_RESOLVABLE)
		{
			return false;
		}
	}

	for (index = 0U; index < BLE_GAP_ADDR_LEN; index++)
	{
		if (octet[index] > 0xFFU)
		{
			return false;
		}
		p_address->addr[BLE_GAP_ADDR_LEN - 1U - index] = (uint8_t)octet[index];
	}
	p_address->addr_type = (uint8_t)type;

	return true;
}
