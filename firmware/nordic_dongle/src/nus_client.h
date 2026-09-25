/**
 * @file nus_client.h
 * @brief UART over BLE as a command/response channel, with round-trip timing.
 *
 * The sensor exposes Nordic's UART Service. This module connects, discovers it,
 * subscribes to notifications, and provides the two operations the bench needs:
 * write bytes, and write bytes then time the reply.
 *
 * The round trip is timestamped at both ends *in the dongle*: once when the
 * write is handed to the SoftDevice, once when the notification arrives. The
 * host records its own times too, but its figures include USB scheduling, which
 * is around a millisecond and would swamp a link-layer latency of a few
 * connection intervals.
 *
 * Traces to: BLE-FR-040 .. BLE-FR-044, BLE-DD-NUS.
 */

#ifndef NUS_CLIENT_H__
#define NUS_CLIENT_H__

#include <stdbool.h>
#include <stdint.h>

#include "ble.h"
#include "ble_db_discovery.h"
#include "ble_gap.h"
#include "nrf_ble_gq.h"
#include "protocol.h"

#ifdef __cplusplus
extern "C" {
#endif

/** Outcome of a timed command. */
typedef struct
{
	bool		replied;
	uint64_t	tx_us;				/**< write accepted by the stack */
	uint64_t	rx_us;				/**< notification received */
	uint64_t	round_trip_us;
	uint16_t	length;
	uint8_t		data[PROTO_MAX_PAYLOAD];
} nus_response_t;

/**
 * @brief Initialise the client. Call once, after the SoftDevice is enabled.
 *
 * @param[in] p_gatt_queue  Queue the client submits its GATT operations to.
 *     Owned by the caller, because database discovery uses the same one: two
 *     queues would let a discovery and a write race for the same link.
 * @param[in] p_db_discovery  The discovery instance the caller initialised and
 *     forwards BLE events to. The client starts it on every connection: the
 *     link is not usable until it has found the UART service.
 */
uint32_t nus_client_init(nrf_ble_gq_t * p_gatt_queue, ble_db_discovery_t * p_db_discovery);

/**
 * @brief Connect to @p p_address, listening for it for up to @p timeout_ms.
 *
 * The attempt listens continuously: nothing else needs the radio while it
 * runs, and a sensor that advertises rarely is easy to miss otherwise.
 */
uint32_t nus_client_connect(const ble_gap_addr_t * p_address, uint32_t timeout_ms);

/**
 * @brief Disconnect, if connected.
 */
uint32_t nus_client_disconnect(void);

/**
 * @brief True once connected and the UART service has been discovered.
 */
bool nus_client_is_ready(void);

/**
 * @brief True while a link exists, whether or not discovery has finished.
 */
bool nus_client_is_connected(void);

/**
 * @brief The connection interval in microseconds, or 0 when not connected.
 *
 * Reported because it is the quantisation of every latency measured over this
 * link: a reply cannot arrive sooner than the next connection event.
 */
uint32_t nus_client_interval_us(void);

/**
 * @brief Write bytes to the sensor without waiting for a reply.
 */
uint32_t nus_client_write(const uint8_t * p_data, uint16_t length);

/**
 * @brief Write bytes and wait for the first notification.
 *
 * Blocking, bounded by @p timeout_ms. USB is serviced while waiting, so the
 * host does not lose events during a long timeout.
 *
 * @param[out] p_response  Filled in on success; @c replied is false on timeout.
 */
uint32_t nus_client_command(const uint8_t *  p_data,
			    uint16_t         length,
			    uint32_t         timeout_ms,
			    nus_response_t * p_response);

/**
 * @brief Feed a BLE stack event to the client.
 */
void nus_client_on_ble_evt(const ble_evt_t * p_ble_evt);

/**
 * @brief Feed a database-discovery event to the client.
 */
void nus_client_on_db_disc_evt(void * p_evt);

#ifdef __cplusplus
}
#endif

#endif /* NUS_CLIENT_H__ */
