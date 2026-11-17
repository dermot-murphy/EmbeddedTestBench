/**
 * @file app_timer.h
 * @brief Stand-in for the nRF5 SDK header, declaring what main.c calls.
 *
 * No unit test links main.c. The stand-in is here for the MISRA C:2012 check
 * (.github/workflows/style.yml), which reads main.c against these headers and
 * needs every function it calls declared (Rule 17.3).
 *
 * Traces to: BLE-DD-TEST.
 */

#ifndef APP_TIMER_H__
#define APP_TIMER_H__

#include "nrf_error.h"

ret_code_t app_timer_init(void);

#endif /* APP_TIMER_H__ */
