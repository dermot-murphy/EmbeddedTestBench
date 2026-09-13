/**
 * @file ble_scanner.h
 * @brief Scanning, the sensor table, and advertising-report timestamping.
 *
 * Two modes share one scan:
 *
 *  * **Discovery** builds a table of the sensors seen, deduplicated by address,
 *    so the host can list them and select one.
 *  * **Profiling** reports every advertising event from one address, with a
 *    microsecond timestamp, so the host can derive intervals, gaps and duty
 *    cycle.
 *
 * Both are the same radio activity; only the reporting differs. Profiling
 * filters to one address in the firmware rather than on the host, because
 * forwarding every packet from a busy room over USB is what causes the drops
 * that would then be misread as the sensor missing an advertising event.
 *
 * Traces to: BLE-FR-020 .. BLE-FR-023, BLE-FR-030, BLE-DD-SCANNER.
 */

#ifndef BLE_SCANNER_H__
#define BLE_SCANNER_H__

#include <stdbool.h>
#include <stdint.h>

#include "ble.h"
#include "ble_gap.h"
#include "protocol.h"

#ifdef __cplusplus
extern "C" {
#endif

/** One sensor seen while scanning. */
typedef struct
{
	ble_gap_addr_t	address;
	int8_t		rssi;				/**< most recent */
	uint8_t		name_length;
	char		name[PROTO_MAX_NAME];		/**< empty if not advertised */
	uint32_t	seen;				/**< reports from this address */
	uint64_t	first_us;
	uint64_t	last_us;
} scanner_sensor_t;

/** Filter applied while scanning. A zeroed filter accepts everything. */
typedef struct
{
	bool		by_name;
	char		name[PROTO_MAX_NAME];		/**< substring match */
	bool		by_address;
	ble_gap_addr_t	address;
	bool		active;				/**< request scan responses */
	int8_t		min_rssi;			/**< 0 means no limit */
} scanner_filter_t;

/**
 * @brief Initialise the scanner. Call once, after the SoftDevice is enabled.
 */
uint32_t scanner_init(void);

/**
 * @brief Start scanning with a filter, for @p duration_ms (0 = until stopped).
 */
uint32_t scanner_start(const scanner_filter_t * p_filter, uint32_t duration_ms);

/**
 * @brief Stop scanning. Safe to call when not scanning.
 */
uint32_t scanner_stop(void);

/**
 * @brief True while the radio is scanning.
 */
bool scanner_is_active(void);

/**
 * @brief Forget every sensor found so far.
 */
void scanner_clear(void);

/**
 * @brief Number of sensors in the table.
 */
uint32_t scanner_count(void);

/**
 * @brief The sensor at @p index, or NULL if @p index is past the end.
 */
const scanner_sensor_t * scanner_get(uint32_t index);

/**
 * @brief Find a sensor by address.
 *
 * @return Its index, or @ref PROTO_MAX_SENSORS if it is not in the table.
 */
uint32_t scanner_find(const ble_gap_addr_t * p_address);

/**
 * @brief Report every advertising event from @p p_address as a @c +adv event.
 *
 * @param[in] p_address  Address to profile, or NULL to profile whatever the
 *                       current filter admits.
 */
void scanner_profile_start(const ble_gap_addr_t * p_address);

/**
 * @brief Stop reporting advertising events.
 */
void scanner_profile_stop(void);

/**
 * @brief True while advertising events are being reported.
 */
bool scanner_profile_is_active(void);

/**
 * @brief Counters for reconciling the host's view with the radio's.
 *
 * @param[out] p_received  Advertising reports the radio delivered.
 * @param[out] p_reported  Reports forwarded to the host.
 */
void scanner_profile_counters(uint32_t * p_received, uint32_t * p_reported);

/**
 * @brief Feed a BLE stack event to the scanner.
 */
void scanner_on_ble_evt(const ble_evt_t * p_ble_evt);

/**
 * @brief Format an address as AA:BB:CC:DD:EE:FF.
 *
 * @param[in]  p_address  Address to format.
 * @param[out] buffer     At least 18 bytes.
 */
void scanner_format_address(const ble_gap_addr_t * p_address, char * buffer);

/**
 * @brief Parse AA:BB:CC:DD:EE:FF into an address.
 *
 * @retval true   parsed
 * @retval false  malformed; @p p_address is untouched
 */
bool scanner_parse_address(const char * text, ble_gap_addr_t * p_address);

#ifdef __cplusplus
}
#endif

#endif /* BLE_SCANNER_H__ */
