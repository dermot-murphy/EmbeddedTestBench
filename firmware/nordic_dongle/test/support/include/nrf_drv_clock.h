/**
 * @file nrf_drv_clock.h
 * @brief Stand-in for the nRF5 SDK header, declaring what main.c calls.
 *
 * No unit test links main.c. The stand-in is here for the MISRA C:2012 check
 * (.github/workflows/style.yml), which reads main.c against these headers and
 * needs every function it calls declared (Rule 17.3).
 *
 * Traces to: BLE-DD-TEST.
 */

#ifndef NRF_DRV_CLOCK_H__
#define NRF_DRV_CLOCK_H__

#include <stdbool.h>

#include "nrf_error.h"

typedef struct nrf_drv_clock_handler_item_s nrf_drv_clock_handler_item_t;

ret_code_t nrf_drv_clock_init(void);
void       nrf_drv_clock_lfclk_request(nrf_drv_clock_handler_item_t * p_handler_item);
bool       nrf_drv_clock_lfclk_is_running(void);

#endif /* NRF_DRV_CLOCK_H__ */
