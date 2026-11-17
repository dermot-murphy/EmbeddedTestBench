/**
 * @file ble_scanner.c
 * @brief Scanning, the sensor table, and advertising-report timestamping.
 *
 * Traces to: BLE-FR-020 .. BLE-FR-023, BLE-FR-030, BLE-DD-SCANNER.
 */

#include "ble_scanner.h"

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
#define BLE_SCANNER_SCAN_INTERVAL_UNITS		160U		/**< 100 ms / 0.625 ms */
#define BLE_SCANNER_SCAN_WINDOW_UNITS		160U		/**< 100 ms / 0.625 ms */

/** The GAP scan timeout counts in 10 ms units. */
#define BLE_SCANNER_TIMEOUT_UNIT_MS		10U

/** Characters in a formatted address, "AA:BB:CC:DD:EE:FF", with its terminator. */
#define BLE_SCANNER_ADDRESS_TEXT		18U

/** Octets in an address, as an unsigned count. */
#define BLE_SCANNER_ADDRESS_OCTETS		((uint32_t)BLE_GAP_ADDR_LEN)

/** Bits in one hex digit, and the low digit of a byte. */
#define BLE_SCANNER_NIBBLE_BITS			4U
#define BLE_SCANNER_NIBBLE_MASK			0x0FU

/** Bases a digit is read in, and what a character that is no digit reads as. */
#define BLE_SCANNER_BASE_DECIMAL		10U
#define BLE_SCANNER_BASE_HEX			16U
#define BLE_SCANNER_NOT_A_DIGIT			0xFFU

/** Hex digits: addresses are written in upper case, payloads in lower case. */
static const char	m_ble_scanner_hex_upper[] = "0123456789ABCDEF";
static const char	m_ble_scanner_hex_lower[] = "0123456789abcdef";

NRF_BLE_SCAN_DEF(m_scan);

static ble_scanner_sensor_t	m_sensors[PROTOCOL_MAX_SENSORS];
static uint32_t		m_sensor_count;
static ble_scanner_filter_t	m_filter;
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
static void ble_scanner_extract_name(const ble_data_t * p_data, char * name, uint8_t * p_length)
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
	if ((length != 0U) && (offset != 0U))
	{
		if (length > (PROTOCOL_MAX_NAME - 1U))
		{
			length = PROTOCOL_MAX_NAME - 1U;
		}
		(void)memcpy(name, &p_data->p_data[offset], length);
		name[length] = '\0';
		*p_length    = (uint8_t)length;
	}
}

/**
 * @brief The company ID that opens a manufacturer-specific record, if any.
 *
 * The ID is the record's first two bytes, least significant first.
 */
static bool ble_scanner_manufacturer_id(const ble_data_t * p_data, uint16_t * p_id)
{
	uint16_t	offset = 0U;
	uint16_t	length;
	bool		found;

	length = ble_advdata_search(p_data->p_data, p_data->len, &offset,
				    BLE_GAP_AD_TYPE_MANUFACTURER_SPECIFIC_DATA);
	found  = (length >= 2U) && (offset != 0U);
	if (found)
	{
		*p_id = (uint16_t)((uint16_t)p_data->p_data[offset] |
				   (uint16_t)((uint16_t)p_data->p_data[offset + 1U] << 8U));
	}

	return found;
}

/**
 * @brief True when a report passes the active filter.
 */
static bool ble_scanner_passes_filter(const ble_gap_evt_adv_report_t * p_report,
				      const char *                     name)
{
	bool passes = true;

	if (m_filter.by_address &&
	    (memcmp(m_filter.address.addr, p_report->peer_addr.addr, BLE_GAP_ADDR_LEN) != 0))
	{
		passes = false;
	}
	else if (m_filter.by_name && (strstr(name, m_filter.name) == NULL))
	{
		passes = false;
	}
	else if ((m_filter.min_rssi != 0) && (p_report->rssi < m_filter.min_rssi))
	{
		passes = false;
	}
	else
	{
		/* Every test passed. */
	}

	return passes;
}

/**
 * @brief Record one report against an entry of the sensor table.
 */
static void ble_scanner_update(ble_scanner_sensor_t *           p_sensor,
			       const ble_gap_evt_adv_report_t * p_report,
			       const char *                     name,
			       uint8_t                          name_length,
			       uint64_t                         when_us)
{
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

	/* A Kepler sensor moved its company ID into the scan response (TX-941),
	 * so both payloads are searched, and the scan response is kept whole for
	 * a test to inspect (#241). */
	if (ble_scanner_manufacturer_id(&p_report->data, &p_sensor->manufacturer_id))
	{
		p_sensor->has_manufacturer = true;
	}
	if (p_report->type.scan_response != 0U)
	{
		uint16_t kept = p_report->data.len;

		if (kept > PROTOCOL_MAX_ADV_DATA)
		{
			kept = PROTOCOL_MAX_ADV_DATA;
		}
		(void)memcpy(p_sensor->scan_response, p_report->data.p_data, kept);
		p_sensor->scan_response_length = (uint8_t)kept;
	}
}

/**
 * @brief Add or update the sensor table from one report.
 *
 * The table is bounded and does not evict: once full, a new address is ignored
 * rather than displacing one the host may already have selected.
 */
static void ble_scanner_remember(const ble_gap_evt_adv_report_t * p_report,
				 const char *                     name,
				 uint8_t                          name_length,
				 uint64_t                         when_us)
{
	uint32_t		index    = ble_scanner_find(&p_report->peer_addr);
	ble_scanner_sensor_t *	p_sensor = NULL;

	if (index < PROTOCOL_MAX_SENSORS)
	{
		p_sensor = &m_sensors[index];
	}
	else if (m_sensor_count < PROTOCOL_MAX_SENSORS)
	{
		p_sensor = &m_sensors[m_sensor_count];
		m_sensor_count++;
		(void)memset(p_sensor, 0, sizeof(*p_sensor));
		p_sensor->address  = p_report->peer_addr;
		p_sensor->first_us = when_us;
	}
	else
	{
		/* The table is full: a new address is not recorded. */
	}

	if (p_sensor != NULL)
	{
		ble_scanner_update(p_sensor, p_report, name, name_length, when_us);
	}
}

/**
 * @brief Write @p byte as two hex digits from @p digits, without a terminator.
 */
static void ble_scanner_hex_byte(uint8_t byte, const char * digits, char * p_text)
{
	p_text[0] = digits[byte >> BLE_SCANNER_NIBBLE_BITS];
	p_text[1] = digits[byte & BLE_SCANNER_NIBBLE_MASK];
}

/**
 * @brief Emit one +adv event for a report being profiled.
 */
static void ble_scanner_report_advertising(const ble_gap_evt_adv_report_t * p_report,
					   const char *                     name,
					   uint64_t                         when_us)
{
	char		time_text[TIMESTAMP_TEXT_SIZE];
	char		address[BLE_SCANNER_ADDRESS_TEXT];
	char		payload[(PROTOCOL_MAX_PAYLOAD * 2U) + 1U];
	uint16_t	length = p_report->data.len;
	uint16_t	index;

	ble_scanner_format_address(&p_report->peer_addr, address);

	if (length > PROTOCOL_MAX_PAYLOAD)
	{
		length = PROTOCOL_MAX_PAYLOAD;
	}
	for (index = 0U; index < length; index++)
	{
		ble_scanner_hex_byte(p_report->data.p_data[index], m_ble_scanner_hex_lower,
				     &payload[index * 2U]);
	}
	payload[length * 2U] = '\0';

	/* Counted only if the queue took it. Counting the attempt would make the
	 * host's reconciliation - reported against received - always agree, which
	 * is precisely the check that exists to detect a lossy link. */
	if (cdc_acm_send_format(
		"+adv t=%s addr=%s type=%u rssi=%d pdu=%u ch=%u name=%s data=%s",
		timestamp_format_us(when_us, time_text),
		address,
		(unsigned)p_report->peer_addr.addr_type,
		(int)p_report->rssi,
		(unsigned)p_report->type.scan_response,
		(unsigned)p_report->ch_index,
		name,
		payload))
	{
		m_profile_reported++;
	}
}

static void ble_scanner_scan_event_handler(scan_evt_t const * p_scan_evt)
{
	char		time_text[TIMESTAMP_TEXT_SIZE];

	switch (p_scan_evt->scan_evt_id)
	{
	case NRF_BLE_SCAN_EVT_SCAN_TIMEOUT:
		m_scanning = false;
		(void)cdc_acm_send_format("+scan t=%s state=stopped",
					  timestamp_format_us(timestamp_now_us(), time_text));
		break;

	default:
		break;
	}
}

uint32_t ble_scanner_init(void)
{
	nrf_ble_scan_init_t	init;
	ble_gap_scan_params_t	params;
	uint32_t		error;

	(void)memset(&init, 0, sizeof(init));
	(void)memset(&params, 0, sizeof(params));

	params.active        = 0U;
	params.interval      = BLE_SCANNER_SCAN_INTERVAL_UNITS;
	params.window        = BLE_SCANNER_SCAN_WINDOW_UNITS;
	params.timeout       = 0U;
	params.scan_phys     = BLE_GAP_PHY_1MBPS;
	params.filter_policy = BLE_GAP_SCAN_FP_ACCEPT_ALL;

	init.p_scan_param     = &params;
	init.connect_if_match = false;

	error = nrf_ble_scan_init(&m_scan, &init, ble_scanner_scan_event_handler);

	ble_scanner_clear();

	return error;
}

uint32_t ble_scanner_start(const ble_scanner_filter_t * p_filter, uint32_t duration_ms)
{
	char		time_text[TIMESTAMP_TEXT_SIZE];
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
	params.interval      = BLE_SCANNER_SCAN_INTERVAL_UNITS;
	params.window        = BLE_SCANNER_SCAN_WINDOW_UNITS;
	/* 0 means scan until stopped. */
	params.timeout       = (uint16_t)(duration_ms / BLE_SCANNER_TIMEOUT_UNIT_MS);
	params.scan_phys     = BLE_GAP_PHY_1MBPS;
	params.filter_policy = BLE_GAP_SCAN_FP_ACCEPT_ALL;

	error = nrf_ble_scan_params_set(&m_scan, &params);
	if (error == NRF_SUCCESS)
	{
		error = nrf_ble_scan_start(&m_scan);
		if (error == NRF_SUCCESS)
		{
			m_scanning = true;
			(void)cdc_acm_send_format("+scan t=%s state=started",
						  timestamp_format_us(timestamp_now_us(), time_text));
		}
	}

	return error;
}

uint32_t ble_scanner_stop(void)
{
	char		time_text[TIMESTAMP_TEXT_SIZE];

	nrf_ble_scan_stop();
	if (m_scanning)
	{
		m_scanning = false;
		(void)cdc_acm_send_format("+scan t=%s state=stopped",
					  timestamp_format_us(timestamp_now_us(), time_text));
	}

	return NRF_SUCCESS;
}

bool ble_scanner_is_active(void)
{
	return m_scanning;
}

void ble_scanner_clear(void)
{
	(void)memset(m_sensors, 0, sizeof(m_sensors));
	m_sensor_count = 0U;
}

uint32_t ble_scanner_count(void)
{
	return m_sensor_count;
}

const ble_scanner_sensor_t * ble_scanner_get(uint32_t index)
{
	return (index < m_sensor_count) ? &m_sensors[index] : NULL;
}

uint32_t ble_scanner_find(const ble_gap_addr_t * p_address)
{
	uint32_t	index;
	uint32_t	found   = PROTOCOL_MAX_SENSORS;
	bool		matched = false;

	for (index = 0U; (index < m_sensor_count) && !matched; index++)
	{
		if (memcmp(m_sensors[index].address.addr, p_address->addr, BLE_GAP_ADDR_LEN) == 0)
		{
			found   = index;
			matched = true;
		}
	}

	return found;
}

void ble_scanner_profile_start(const ble_gap_addr_t * p_address)
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

void ble_scanner_profile_stop(void)
{
	m_profiling = false;
}

bool ble_scanner_profile_is_active(void)
{
	return m_profiling;
}

void ble_scanner_profile_counters(uint32_t * p_received, uint32_t * p_reported)
{
	*p_received = m_profile_received;
	*p_reported = m_profile_reported;
}

/**
 * @brief Report @p p_report to the host if it is from the address being profiled.
 */
static void ble_scanner_profile(const ble_gap_evt_adv_report_t * p_report,
				const char *                     name,
				uint64_t                         when_us)
{
	bool wanted = m_profile_all ||
		      (memcmp(m_profile_address.addr,
			      p_report->peer_addr.addr,
			      BLE_GAP_ADDR_LEN) == 0);

	if (wanted)
	{
		m_profile_received++;
		ble_scanner_report_advertising(p_report, name, when_us);
	}
}

void ble_scanner_on_ble_evt(const ble_evt_t * p_ble_evt)
{
	if (p_ble_evt->header.evt_id == (uint16_t)BLE_GAP_EVT_ADV_REPORT)
	{
		/* Timestamp first, before any parsing: every microsecond spent here
		 * is added to the interval being measured. */
		uint64_t				when_us  = timestamp_now_us();
		const ble_gap_evt_adv_report_t *	p_report = &p_ble_evt->evt.gap_evt.params.adv_report;
		char					name[PROTOCOL_MAX_NAME];
		uint8_t					name_length;

		ble_scanner_extract_name(&p_report->data, name, &name_length);

		if (ble_scanner_passes_filter(p_report, name))
		{
			ble_scanner_remember(p_report, name, name_length, when_us);

			if (m_profiling)
			{
				ble_scanner_profile(p_report, name, when_us);
			}
		}
	}
}

void ble_scanner_format_address(const ble_gap_addr_t * p_address, char * buffer)
{
	uint32_t index;

	/* BLE addresses are conventionally written most significant octet first,
	 * while the stack stores them least significant first. */
	for (index = 0U; index < BLE_SCANNER_ADDRESS_OCTETS; index++)
	{
		ble_scanner_hex_byte(p_address->addr[BLE_SCANNER_ADDRESS_OCTETS - 1U - index],
				     m_ble_scanner_hex_upper, &buffer[index * 3U]);
		buffer[(index * 3U) + 2U] = ':';
	}
	buffer[(BLE_SCANNER_ADDRESS_OCTETS * 3U) - 1U] = '\0';
}

/**
 * @brief The value of @p digit in @p base (10 or 16, either case), or
 *        BLE_SCANNER_NOT_A_DIGIT.
 */
static uint8_t ble_scanner_digit(char digit, uint8_t base)
{
	uint8_t	value = BLE_SCANNER_NOT_A_DIGIT;
	uint8_t	index;
	bool	found = false;

	for (index = 0U; (index < base) && !found; index++)
	{
		if ((digit == m_ble_scanner_hex_upper[index]) || (digit == m_ble_scanner_hex_lower[index]))
		{
			value = index;
			found = true;
		}
	}

	return value;
}

/**
 * @brief Read one address octet, one or two hex digits, and advance past it.
 */
static bool ble_scanner_read_octet(const char ** pp_text, uint8_t * p_octet)
{
	const char *	text  = *pp_text;
	uint8_t		high  = ble_scanner_digit(text[0], BLE_SCANNER_BASE_HEX);
	bool		valid = (high != BLE_SCANNER_NOT_A_DIGIT);

	if (valid)
	{
		uint8_t low = ble_scanner_digit(text[1], BLE_SCANNER_BASE_HEX);

		if (low == BLE_SCANNER_NOT_A_DIGIT)
		{
			*p_octet = high;
			*pp_text = &text[1];
		}
		else
		{
			*p_octet = (uint8_t)((uint8_t)(high << BLE_SCANNER_NIBBLE_BITS) | low);
			*pp_text = &text[2];
		}
	}

	return valid;
}

/**
 * @brief Read the address type after the slash: decimal, at most
 *        BLE_GAP_ADDR_TYPE_RANDOM_PRIVATE_NON_RESOLVABLE.
 */
static bool ble_scanner_read_type(const char * text, uint8_t * p_type)
{
	uint32_t	value  = 0U;
	uint32_t	index  = 0U;
	uint8_t		digit  = ble_scanner_digit(text[0], BLE_SCANNER_BASE_DECIMAL);
	bool		valid  = (digit != BLE_SCANNER_NOT_A_DIGIT);

	while (valid && (digit != BLE_SCANNER_NOT_A_DIGIT))
	{
		value = (value * BLE_SCANNER_BASE_DECIMAL) + digit;
		valid = (value <= (uint32_t)BLE_GAP_ADDR_TYPE_RANDOM_PRIVATE_NON_RESOLVABLE);
		index++;
		digit = ble_scanner_digit(text[index], BLE_SCANNER_BASE_DECIMAL);
	}
	if (valid)
	{
		*p_type = (uint8_t)value;
	}

	return valid;
}

bool ble_scanner_parse_address(const char * text, ble_gap_addr_t * p_address)
{
	uint8_t		octets[BLE_GAP_ADDR_LEN];
	uint8_t		type   = (uint8_t)BLE_GAP_ADDR_TYPE_RANDOM_STATIC;
	const char *	cursor = text;
	const char *	slash;
	uint32_t	index;
	bool		valid  = true;

	for (index = 0U; (index < BLE_SCANNER_ADDRESS_OCTETS) && valid; index++)
	{
		valid = ble_scanner_read_octet(&cursor, &octets[index]);
		if (valid && (index < (BLE_SCANNER_ADDRESS_OCTETS - 1U)))
		{
			valid  = (cursor[0] == ':');
			cursor = &cursor[1];
		}
	}

	/* An address alone does not say whether it is public or random, and
	 * connecting with the wrong type simply never finds the device. The type
	 * may therefore be appended as "AA:BB:CC:DD:EE:FF/0"; the host sends the
	 * type it learned from the scan. Random static is the default because
	 * that is what almost every sensor uses. */
	slash = strchr(text, '/');
	if (valid && (slash != NULL))
	{
		valid = ble_scanner_read_type(&slash[1], &type);
	}

	if (valid)
	{
		for (index = 0U; index < BLE_SCANNER_ADDRESS_OCTETS; index++)
		{
			p_address->addr[BLE_SCANNER_ADDRESS_OCTETS - 1U - index] = octets[index];
		}
		p_address->addr_type = type;
	}

	return valid;
}
