/**
 * @file nrfx_timer.h
 * @brief Host-test stand-in for the TIMER driver.
 *
 * The counter is settable, and the compare handler the firmware registers is
 * exposed, so a test can drive a 32-bit wrap without waiting 71 minutes for one.
 *
 * Traces to: BLE-DD-TEST.
 */

#ifndef NRFX_TIMER_H__
#define NRFX_TIMER_H__

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "nrf_error.h"

typedef enum
{
	NRF_TIMER_FREQ_16MHz = 0,
	NRF_TIMER_FREQ_8MHz,
	NRF_TIMER_FREQ_4MHz,
	NRF_TIMER_FREQ_2MHz,
	NRF_TIMER_FREQ_1MHz
} nrf_timer_frequency_t;

typedef enum { NRF_TIMER_MODE_TIMER = 0, NRF_TIMER_MODE_COUNTER } nrf_timer_mode_t;

typedef enum
{
	NRF_TIMER_BIT_WIDTH_16 = 0,
	NRF_TIMER_BIT_WIDTH_08,
	NRF_TIMER_BIT_WIDTH_24,
	NRF_TIMER_BIT_WIDTH_32
} nrf_timer_bit_width_t;

typedef enum
{
	NRF_TIMER_CC_CHANNEL0 = 0,
	NRF_TIMER_CC_CHANNEL1,
	NRF_TIMER_CC_CHANNEL2,
	NRF_TIMER_CC_CHANNEL3
} nrf_timer_cc_channel_t;

typedef enum
{
	NRF_TIMER_EVENT_COMPARE0 = 0,
	NRF_TIMER_EVENT_COMPARE1,
	NRF_TIMER_EVENT_COMPARE2,
	NRF_TIMER_EVENT_COMPARE3
} nrf_timer_event_t;

#define NRF_TIMER_SHORT_COMPARE0_CLEAR_MASK	(1UL << 0)

typedef struct { uint8_t instance_id; } nrfx_timer_t;

typedef struct
{
	nrf_timer_frequency_t	frequency;
	nrf_timer_mode_t	mode;
	nrf_timer_bit_width_t	bit_width;
	uint8_t			interrupt_priority;
	void *			p_context;
} nrfx_timer_config_t;

#define NRFX_TIMER_INSTANCE(id)		{ (uint8_t)(id) }
#define NRFX_TIMER_DEFAULT_CONFIG	{ NRF_TIMER_FREQ_16MHz, NRF_TIMER_MODE_TIMER, \
					  NRF_TIMER_BIT_WIDTH_16, 6, NULL }

typedef void (*nrfx_timer_event_handler_t)(nrf_timer_event_t event_type, void * p_context);

uint32_t nrfx_timer_init(const nrfx_timer_t *		p_instance,
			 const nrfx_timer_config_t *	p_config,
			 nrfx_timer_event_handler_t	handler);
void     nrfx_timer_enable(const nrfx_timer_t * p_instance);
void     nrfx_timer_extended_compare(const nrfx_timer_t *	p_instance,
				     nrf_timer_cc_channel_t	cc_channel,
				     uint32_t			cc_value,
				     uint32_t			shorts_mask,
				     bool			enable_interrupt);
uint32_t nrfx_timer_capture(const nrfx_timer_t * p_instance, nrf_timer_cc_channel_t cc_channel);

/* --- test control ------------------------------------------------- */

/** Set the value the next capture returns. */
void     fake_timer_set_counter(uint32_t ticks);
/** Fire the registered compare handler, as a hardware wrap would. */
void     fake_timer_fire_compare(void);
/** Configuration the firmware asked for, so a test can check the rate. */
const nrfx_timer_config_t * fake_timer_config(void);
/** True once the firmware enabled the timer. */
bool     fake_timer_is_enabled(void);
/** Compare value and shorts the firmware programmed. */
uint32_t fake_timer_compare_value(void);
uint32_t fake_timer_compare_shorts(void);
/** Return this from the next nrfx_timer_init, to exercise the failure path. */
void     fake_timer_set_init_result(uint32_t result);
void     fake_timer_reset(void);

#endif /* NRFX_TIMER_H__ */
