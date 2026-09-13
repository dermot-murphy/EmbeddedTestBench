/**
 * @file ble_advdata.h
 * @brief Host-test stand-in for advertising-payload search.
 *
 * Implemented for real in the fake, rather than stubbed: the firmware's name
 * extraction depends on the offset convention (the offset of the *data*, not of
 * the length byte), and a stub returning a constant would hide a mistake there.
 *
 * Traces to: BLE-DD-TEST.
 */

#ifndef BLE_ADVDATA_H__
#define BLE_ADVDATA_H__

#include <stdint.h>

#include "ble_gap.h"

uint16_t ble_advdata_search(const uint8_t *	p_encoded_data,
			    uint16_t		data_len,
			    uint16_t *		p_offset,
			    uint8_t		ad_type);

#endif /* BLE_ADVDATA_H__ */
