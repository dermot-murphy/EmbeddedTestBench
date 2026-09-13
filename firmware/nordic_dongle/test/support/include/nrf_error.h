/**
 * @file nrf_error.h
 * @brief Host-test stand-in for the SDK's error codes.
 *
 * Part of the unit-test scaffolding, not of the firmware. The values match the
 * SDK's, so a test asserting on a return code is asserting on the same number
 * the target would produce.
 *
 * Traces to: BLE-DD-TEST.
 */

#ifndef NRF_ERROR_H__
#define NRF_ERROR_H__

#include <stdint.h>

#define NRF_SUCCESS			0UL
#define NRF_ERROR_INTERNAL		3UL
#define NRF_ERROR_NO_MEM		4UL
#define NRF_ERROR_NOT_FOUND		5UL
#define NRF_ERROR_INVALID_PARAM		7UL
#define NRF_ERROR_INVALID_STATE		8UL
#define NRF_ERROR_INVALID_LENGTH	9UL
#define NRF_ERROR_DATA_SIZE		12UL
#define NRF_ERROR_TIMEOUT		13UL
#define NRF_ERROR_NULL			14UL
#define NRF_ERROR_BUSY			17UL
#define NRF_ERROR_RESOURCES		19UL
#define NRF_ERROR_IO_PENDING		0x2000UL

typedef uint32_t ret_code_t;

#endif /* NRF_ERROR_H__ */
