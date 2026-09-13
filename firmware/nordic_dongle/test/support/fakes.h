/**
 * @file fakes.h
 * @brief Controls the tests use to drive the fakes.
 *
 * The per-module controls live with their fake headers (``fake_cdc_*`` in
 * app_usbd_cdc_acm.h, ``fake_timer_*`` in nrfx_timer.h, and so on). This header
 * carries the ones with no natural home, and the recorders for the firmware's
 * own modules where a test fakes one to exercise another.
 *
 * Traces to: BLE-DD-TEST, SWE4-UT-FWUNIT.
 */

#ifndef FAKES_H__
#define FAKES_H__

#include <stdbool.h>
#include <stdint.h>

#include "ble_gap.h"

/* --- SoftDevice GAP ------------------------------------------------ */
const ble_gap_addr_t *	fake_gap_connect_address(void);
uint32_t		fake_gap_connect_count(void);
uint32_t		fake_gap_disconnect_count(void);
void			fake_gap_set_connect_result(uint32_t result);
void			fake_gap_reset(void);

/* --- the firmware's own modules, when one is faked to test another -- */

/** Lines the unit under test sent towards the host, in order. */
uint32_t	fake_line_count(void);
const char *	fake_line(uint32_t index);
/** The most recent line, or "" when none was sent. */
const char *	fake_last_line(void);
/** True if any line sent so far begins with @p prefix. */
bool		fake_line_seen(const char * prefix);
/** Make the next queue attempt report failure, as a full queue does. */
void		fake_lines_set_full(bool full);
void		fake_lines_reset(void);

/** The clock the unit under test reads. Set it; it does not run. */
void		fake_clock_set(uint64_t microseconds);
void		fake_clock_advance(uint64_t microseconds);
/** Advance by this much on every read, to model time passing in a wait loop. */
void		fake_clock_set_step(uint64_t microseconds);
void		fake_clock_reset(void);

/* --- scanner, when faked for the command parser --------------------- */
void		fake_scanner_add(const char * address, uint8_t address_type,
				 const char * name, int8_t rssi);
void		fake_scanner_set_active(bool active);
void		fake_scanner_set_profiling(bool profiling);
void		fake_scanner_set_counters(uint32_t received, uint32_t reported);
uint32_t	fake_scanner_starts(void);
uint32_t	fake_scanner_stops(void);
uint32_t	fake_scanner_clears(void);
const char *	fake_scanner_profile_address(void);
uint32_t	fake_scanner_last_duration_ms(void);
const char *	fake_scanner_filter_name(void);
int8_t		fake_scanner_filter_rssi(void);
bool		fake_scanner_filter_active(void);
void		fake_scanner_set_start_result(uint32_t result);
void		fake_scanner_reset(void);

/* --- UART client, when faked for the command parser ----------------- */
void		fake_nus_client_set_ready(bool ready);
void		fake_nus_client_set_connected(bool connected);
void		fake_nus_client_set_interval_us(uint32_t interval_us);
void		fake_nus_client_set_reply(const char * text, uint64_t round_trip_us);
void		fake_nus_client_set_no_reply(void);
void		fake_nus_client_set_write_result(uint32_t result);
uint32_t	fake_nus_client_writes(void);
uint32_t	fake_nus_client_commands(void);
const uint8_t *	fake_nus_client_last_payload(void);
uint16_t	fake_nus_client_last_length(void);
uint32_t	fake_nus_client_connects(void);
uint32_t	fake_nus_client_disconnects(void);
void		fake_nus_client_set_connect_result(uint32_t result);
void		fake_nus_client_reset(void);

/* Each test's setUp resets the fakes that test links. There is deliberately no
 * reset-everything helper: a binary links only the fakes it needs, so one would
 * be an undefined symbol in every binary but the largest. */

#endif /* FAKES_H__ */
