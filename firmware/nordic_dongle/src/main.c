/**
 * @file main.c
 * @brief BLE bench dongle: scan, select, UART over BLE, advertising profile.
 *
 * Runs on an nRF52840 USB dongle (PCA10059) with the S140 SoftDevice, built
 * against nRF5 SDK 17.1.0. The dongle is a bench instrument, not a product: it
 * exists so that a host test can see what a sensor is doing on the air, and
 * time what it does, with the timestamps taken close enough to the radio to
 * mean something.
 *
 * Shape of the program:
 *
 *   main loop           USB service, then one command line if one has arrived
 *   BLE event handler   timestamp, then queue an event line; never blocks
 *   TIMER3 interrupt    extends the microsecond counter past 32 bits
 *
 * Nothing is allocated after start-up, there is no recursion, and every buffer
 * is a fixed size declared in protocol.h, so the worst case is the only case.
 *
 * Traces to: BLE-FR-001 .. BLE-FR-044, BLE-ARC-001, BLE-DD-MAIN.
 */

#include <stdbool.h>
#include <stdint.h>
#include <string.h>

#include "app_error.h"
#include "app_timer.h"
#include "ble_db_discovery.h"
#include "nrf_ble_gatt.h"
#include "nrf_delay.h"
#include "nrf_drv_clock.h"
#include "nrf_sdh.h"
#include "nrf_sdh_ble.h"
#include "nrf_sdh_soc.h"

#include "app_ble_config.h"
#include "ble_scanner.h"
#include "cdc_acm.h"
#include "cmd_parser.h"
#include "nus_client.h"
#include "protocol.h"
#include "timestamp.h"

NRF_BLE_GATT_DEF(m_gatt);
BLE_DB_DISCOVERY_DEF(m_db_discovery);

/**
 * @brief Dispatch a BLE stack event to the modules that care about it.
 *
 * The scanner runs first so that an advertising report is timestamped before
 * anything else has had a chance to spend time on it.
 */
static void ble_evt_handler(ble_evt_t const * p_ble_evt, void * p_context)
{
	UNUSED_PARAMETER(p_context);

	scanner_on_ble_evt(p_ble_evt);
	nus_client_on_ble_evt(p_ble_evt);
	ble_db_discovery_on_ble_evt(p_ble_evt, &m_db_discovery);
}

NRF_SDH_BLE_OBSERVER(m_ble_observer, APP_BLE_OBSERVER_PRIO, ble_evt_handler, NULL);

static void db_discovery_handler(ble_db_discovery_evt_t * p_evt)
{
	nus_client_on_db_disc_evt(p_evt);
}

/**
 * @brief Start the SoftDevice and configure the BLE stack.
 */
static void ble_stack_init(void)
{
	uint32_t	ram_start = 0U;
	ret_code_t	error;

	error = nrf_sdh_enable_request();
	APP_ERROR_CHECK(error);

	error = nrf_sdh_ble_default_cfg_set(APP_BLE_CONN_CFG_TAG, &ram_start);
	APP_ERROR_CHECK(error);

	error = nrf_sdh_ble_enable(&ram_start);
	APP_ERROR_CHECK(error);
}

static void gatt_init(void)
{
	ret_code_t error;

	error = nrf_ble_gatt_init(&m_gatt, NULL);
	APP_ERROR_CHECK(error);

	error = nrf_ble_gatt_att_mtu_central_set(&m_gatt, APP_BLE_MAX_ATT_MTU);
	APP_ERROR_CHECK(error);
}

static void db_discovery_init(void)
{
	ble_db_discovery_init_t init;
	ret_code_t              error;

	(void)memset(&init, 0, sizeof(init));
	init.evt_handler  = db_discovery_handler;
	init.p_gatt_queue = NULL;

	error = ble_db_discovery_init(&init);
	APP_ERROR_CHECK(error);
}

/**
 * @brief Start the low-frequency clock, which app_timer and the SoftDevice need.
 */
static void clock_init(void)
{
	ret_code_t error;

	error = nrf_drv_clock_init();
	APP_ERROR_CHECK(error);

	nrf_drv_clock_lfclk_request(NULL);
	while (!nrf_drv_clock_lfclk_is_running())
	{
		/* The SoftDevice cannot be enabled before the clock is up. */
	}
}

int main(void)
{
	char line[PROTO_MAX_LINE];

	clock_init();

	APP_ERROR_CHECK(app_timer_init());
	APP_ERROR_CHECK(timestamp_init());
	APP_ERROR_CHECK(cdc_acm_init());

	ble_stack_init();
	gatt_init();
	db_discovery_init();
	APP_ERROR_CHECK(scanner_init());
	APP_ERROR_CHECK(nus_client_init());

	if (!cmd_parser_init())
	{
		/* A documented command with no implementation behind it. Better to
		 * stop here, where a developer sees it, than to answer "unknown
		 * command" on a bench six weeks later. */
		APP_ERROR_CHECK(NRF_ERROR_INTERNAL);
	}

	for (;;)
	{
		cdc_acm_process();

		if (cdc_acm_take_line(line, sizeof(line)))
		{
			cmd_parser_handle(line);
		}
	}
}
