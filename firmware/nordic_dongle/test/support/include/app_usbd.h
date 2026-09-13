/**
 * @file app_usbd.h
 * @brief Host-test stand-in for the USB device stack.
 *
 * Traces to: BLE-DD-TEST.
 */

#ifndef APP_USBD_H__
#define APP_USBD_H__

#include <stdbool.h>
#include <stdint.h>

#include "nrf_error.h"

typedef enum
{
	APP_USBD_EVT_DRV_SUSPEND = 0,
	APP_USBD_EVT_DRV_RESUME,
	APP_USBD_EVT_STARTED,
	APP_USBD_EVT_STOPPED,
	APP_USBD_EVT_POWER_DETECTED,
	APP_USBD_EVT_POWER_REMOVED,
	APP_USBD_EVT_POWER_READY
} app_usbd_event_type_t;

typedef struct { int unused; } app_usbd_class_inst_t;

typedef struct
{
	void (* ev_state_proc)(app_usbd_event_type_t event);
} app_usbd_config_t;

uint32_t app_usbd_init(const app_usbd_config_t * p_config);
uint32_t app_usbd_class_append(app_usbd_class_inst_t const * p_class_inst);
uint32_t app_usbd_power_events_enable(void);
bool     app_usbd_event_queue_process(void);
void     app_usbd_enable(void);
void     app_usbd_disable(void);
void     app_usbd_start(void);
void     app_usbd_stop(void);

/* --- test control ------------------------------------------------- */
uint32_t fake_usbd_queue_process_calls(void);
void     fake_usbd_set_queue_depth(uint32_t events);
void     fake_usbd_reset(void);

#endif /* APP_USBD_H__ */
