/**
 * @file app_error.h
 * @brief Host-test stand-in: records the last checked error instead of resetting.
 *
 * Traces to: BLE-DD-TEST.
 */

#ifndef APP_ERROR_H__
#define APP_ERROR_H__

#include "nrf_error.h"

/** Last value passed to APP_ERROR_CHECK, for a test to inspect. */
extern uint32_t fake_last_checked_error;

#define APP_ERROR_CHECK(code)	do { fake_last_checked_error = (uint32_t)(code); } while (0)
#define APP_ERROR_CHECK_BOOL(b)	do { (void)(b); } while (0)

#endif /* APP_ERROR_H__ */
