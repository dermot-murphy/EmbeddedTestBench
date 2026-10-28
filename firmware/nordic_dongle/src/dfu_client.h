/**
 * @file dfu_client.h
 * @brief A GATT client for Nordic's Secure DFU service, for updating a sensor.
 *
 * The dongle only carries bytes: the host runs the DFU procedure (#244). A
 * target in its bootloader exposes service 0xFE59 with a Control Point
 * (8EC90001-...), written with a response and answering by notification, and a
 * Packet characteristic (8EC90002-...), written without one. When discovery
 * finds them on a link, notifications are enabled on the Control Point and
 * @c +dfu state=ready is reported, with the link's effective ATT MTU.
 *
 * Traces to: BLE-FR-121, BLE-DD-DFU.
 */

#ifndef DFU_CLIENT_H__
#define DFU_CLIENT_H__

#include <stdbool.h>
#include <stdint.h>

#include "ble.h"
#include "ble_db_discovery.h"
#include "nrf_ble_gatt.h"
#include "nrf_ble_gq.h"

#ifdef __cplusplus
extern "C" {
#endif

/** Longest Control Point response kept, in bytes. */
#define DFU_CLIENT_MAX_RESPONSE		20U

/** Longest write to either characteristic: an ATT MTU of 247 less 3. */
#define DFU_CLIENT_MAX_WRITE		244U

/**
 * @brief Register the DFU service with discovery. Call once, after the
 *        SoftDevice is enabled and before any link.
 */
uint32_t dfu_client_init(nrf_ble_gq_t * p_gatt_queue, nrf_ble_gatt_t * p_gatt);

/**
 * @brief True once the link's DFU service is found and notifications are on.
 */
bool dfu_client_is_ready(void);

/**
 * @brief The effective ATT MTU of the DFU link; 0 when there is none.
 *
 * A Packet write is split into pieces of this less 3. On 5C1712 both Kepler
 * bootloaders linked at 23, the minimum, which the host could only work out
 * backwards from the receipts (#271, #274).
 */
uint16_t dfu_client_att_mtu(void);

/**
 * @brief Write a Control Point request and wait for its response.
 *
 * @param[in]  p_data         Request bytes, opcode first.
 * @param[in]  length         Request length.
 * @param[in]  timeout_ms     Longest wait for the notification.
 * @param[out] p_response     At least DFU_CLIENT_MAX_RESPONSE bytes.
 * @param[out] p_response_len Bytes received; 0 when none came in time.
 *
 * @retval NRF_ERROR_INVALID_STATE  No DFU service on the link.
 * @retval NRF_ERROR_DATA_SIZE      Request longer than DFU_CLIENT_MAX_WRITE.
 */
uint32_t dfu_client_control(const uint8_t * p_data, uint16_t length, uint32_t timeout_ms,
			    uint8_t * p_response, uint16_t * p_response_len);

/**
 * @brief Write to the Packet characteristic, waiting for a transmit buffer
 *        for up to @p timeout_ms.
 *
 * The bytes are split into pieces the link can carry: its ATT MTU less 3. A
 * transfer can start before the MTU exchange has finished, on the 23-byte
 * default; a longer write was refused with NRF_ERROR_DATA_SIZE on the
 * bootloader of sensor 5C1712 (#244).
 *
 * @param[out] p_piece   The piece size used, in bytes.
 * @param[out] p_pieces  Pieces written, including any written before a failure.
 *
 * @retval NRF_ERROR_INVALID_STATE  No DFU service on the link.
 * @retval NRF_ERROR_DATA_SIZE      Longer than DFU_CLIENT_MAX_WRITE.
 * @retval NRF_ERROR_RESOURCES      No transmit buffer came free in time.
 * @retval NRF_ERROR_TIMEOUT        A receipt the bootloader owed did not come.
 *
 * When a Control Point request has set a receipt interval (opcode 0x02), the
 * client waits for the bootloader's receipt after every that many packets,
 * counted from the last object created, before it writes more.
 */
uint32_t dfu_client_packet(const uint8_t * p_data, uint16_t length, uint32_t timeout_ms,
			   uint16_t * p_piece, uint16_t * p_pieces);

/**
 * @brief Feed a BLE stack event to the client.
 */
void dfu_client_on_ble_evt(const ble_evt_t * p_ble_evt);

/**
 * @brief Feed a database-discovery event to the client.
 */
void dfu_client_on_db_disc_evt(ble_db_discovery_evt_t * p_evt);

#ifdef __cplusplus
}
#endif

#endif /* DFU_CLIENT_H__ */
