/**
 * @file app_usbd_cdc_acm.h
 * @brief Host-test stand-in for the CDC ACM class.
 *
 * The instance macro records the event handler the firmware registers, which is
 * how a test delivers PORT_OPEN, TX_DONE and RX_DONE without a USB host.
 * ``fake_cdc_*`` exposes what was written and lets writes be made to fail.
 *
 * Traces to: BLE-DD-TEST.
 */

#ifndef APP_USBD_CDC_ACM_H__
#define APP_USBD_CDC_ACM_H__

#include <stdint.h>

#include "app_usbd.h"

#define APP_USBD_CDC_COMM_PROTOCOL_AT_V250	1

typedef enum
{
	APP_USBD_CDC_ACM_USER_EVT_RX_DONE = 0,
	APP_USBD_CDC_ACM_USER_EVT_TX_DONE,
	APP_USBD_CDC_ACM_USER_EVT_PORT_OPEN,
	APP_USBD_CDC_ACM_USER_EVT_PORT_CLOSE
} app_usbd_cdc_acm_user_event_t;

typedef struct { int unused; } app_usbd_cdc_acm_t;

typedef void (*app_usbd_cdc_acm_user_ev_handler_t)(app_usbd_class_inst_t const *  p_inst,
						   app_usbd_cdc_acm_user_event_t  event);

/** Records the handler so a test can deliver events to the real firmware. */
extern app_usbd_cdc_acm_user_ev_handler_t fake_cdc_handler;

#define APP_USBD_CDC_ACM_GLOBAL_DEF(name, handler, comm_if, data_if,	\
				    comm_ep, data_ep_in, data_ep_out, protocol) \
	static app_usbd_cdc_acm_t name;					\
	static void name ## _register(void) __attribute__((constructor));	\
	static void name ## _register(void) { fake_cdc_handler = (handler); }

uint32_t app_usbd_cdc_acm_write(app_usbd_cdc_acm_t const * p_cdc_acm, const void * p_buf, size_t length);
uint32_t app_usbd_cdc_acm_read(app_usbd_cdc_acm_t const * p_cdc_acm, void * p_buf, size_t length);
app_usbd_class_inst_t const * app_usbd_cdc_acm_class_inst_get(app_usbd_cdc_acm_t const * p_cdc_acm);

/* --- test control ------------------------------------------------- */

/** Everything the firmware has written, concatenated. */
const char * fake_cdc_written(void);
/** Bytes written, and writes issued. */
uint32_t     fake_cdc_written_length(void);
uint32_t     fake_cdc_write_count(void);
/** Make the next write fail with this code (0 restores success). */
void         fake_cdc_set_write_result(uint32_t result);
/** Feed one byte to the firmware's receive path, as the driver would. */
void         fake_cdc_receive_byte(char byte);
/** Feed a whole line, terminator included. */
void         fake_cdc_receive_text(const char * text);
/** Complete the outstanding write, as the endpoint would. */
void         fake_cdc_complete_write(void);
/** Open or close the port. */
void         fake_cdc_open_port(void);
void         fake_cdc_close_port(void);
void         fake_cdc_reset(void);

#endif /* APP_USBD_CDC_ACM_H__ */
