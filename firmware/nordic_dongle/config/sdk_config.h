/**
 * @file sdk_config.h
 * @brief nRF5 SDK 17.1.0 configuration for the bench dongle.
 *
 * Deliberately minimal. SDK components test their own switch with
 * @c NRF_MODULE_ENABLED, which evaluates an undefined symbol as disabled, so
 * only what this application uses appears here. A component enabled without its
 * required settings fails to compile and names the missing symbol, which is a
 * better failure than a ten-thousand-line configuration nobody reads.
 *
 * Traces to: BLE-DD-BUILD.
 */

#ifndef SDK_CONFIG_H__
#define SDK_CONFIG_H__

/* The GATT queue has to carry this protocol's payloads, so it is sized from
 * them rather than from a number that looks about right. protocol.h includes
 * nothing, so it is safe to pull in this early. */
#include "protocol.h"

/* ---------------------------------------------------------------- clocks */
#define NRF_CLOCK_ENABLED			1
#define CLOCK_CONFIG_LF_SRC			1	/**< XTAL on the dongle */
#define CLOCK_CONFIG_LF_CAL_ENABLED		0
#define CLOCK_CONFIG_IRQ_PRIORITY		6
#define NRFX_CLOCK_ENABLED			1
#define NRFX_CLOCK_CONFIG_LF_SRC		1
#define NRFX_CLOCK_CONFIG_IRQ_PRIORITY		6
/* nrf_drv_clock registers a SoC observer and a SoftDevice state observer, and
 * static asserts that each priority is below its PRIO_LEVELS. Both are
 * required even though both are the SDK's own default. */
#define CLOCK_CONFIG_SOC_OBSERVER_PRIO		0
#define CLOCK_CONFIG_STATE_OBSERVER_PRIO	0

/* ---------------------------------------------------------------- power */
/* The USB stack runs on POWER events: app_usbd asserts that the USBD and POWER
 * interrupt priorities match, and nrfx asserts that POWER and CLOCK match. All
 * three are 6. */
#define POWER_ENABLED				1
#define POWER_CONFIG_IRQ_PRIORITY		6
#define POWER_CONFIG_DEFAULT_DCDCEN		0
#define POWER_CONFIG_DEFAULT_DCDCENHV		0
#define NRFX_POWER_ENABLED			1
#define NRFX_POWER_CONFIG_IRQ_PRIORITY		6
#define NRFX_POWER_CONFIG_DEFAULT_DCDCEN	0
#define NRFX_POWER_CONFIG_DEFAULT_DCDCENHV	0

/* ------------------------------------------------------- app_timer / RTC */
#define APP_TIMER_ENABLED			1
#define APP_TIMER_CONFIG_RTC_FREQUENCY		0
#define APP_TIMER_CONFIG_IRQ_PRIORITY		6
#define APP_TIMER_CONFIG_OP_QUEUE_SIZE		10
#define APP_TIMER_CONFIG_USE_SCHEDULER		0
#define APP_TIMER_KEEPS_RTC_ACTIVE		0
#define APP_TIMER_SAFE_WINDOW_MS		300000
#define APP_TIMER_WITH_PROFILER			0

/* ---------------------------------------- TIMER3: the microsecond clock */
#define NRFX_TIMER_ENABLED			1
#define NRFX_TIMER3_ENABLED			1
#define NRFX_TIMER_DEFAULT_CONFIG_FREQUENCY	0	/**< 16 MHz base */
#define NRFX_TIMER_DEFAULT_CONFIG_MODE		0	/**< timer, not counter */
#define NRFX_TIMER_DEFAULT_CONFIG_BIT_WIDTH	3	/**< 32-bit */
#define NRFX_TIMER_DEFAULT_CONFIG_IRQ_PRIORITY	2	/**< above USB and BLE */
#define TIMER_ENABLED				1
#define TIMER3_ENABLED				1

/* ------------------------------------------------------------------ USB */
#define USBD_ENABLED				1
#define NRFX_USBD_ENABLED			1
#define NRFX_USBD_CONFIG_IRQ_PRIORITY		6
#define NRFX_USBD_CONFIG_DMASCHEDULER_MODE	0
#define NRFX_USBD_CONFIG_DMASCHEDULER_ISO_BOOST	1
#define NRFX_USBD_CONFIG_ISO_IN_ZLP		0
#define USBD_CONFIG_IRQ_PRIORITY		6

#define APP_USBD_ENABLED			1
#define APP_USBD_VID				0x1915	/**< Nordic Semiconductor */
#define APP_USBD_PID				0x521A	/**< Nordic's CDC ACM example PID */
#define APP_USBD_DEVICE_VER_MAJOR		1
#define APP_USBD_DEVICE_VER_MINOR		0
#define APP_USBD_DEVICE_VER_SUB			0
#define APP_USBD_CONFIG_LOG_ENABLED		0
#define APP_USBD_CONFIG_SELF_POWERED		0
#define APP_USBD_CONFIG_MAX_POWER		100
#define APP_USBD_CONFIG_POWER_EVENTS_PROCESS	1
#define APP_USBD_CONFIG_EVENT_QUEUE_ENABLE	1
#define APP_USBD_CONFIG_EVENT_QUEUE_SIZE	32
#define APP_USBD_CONFIG_SOF_HANDLING_MODE	1
#define APP_USBD_CONFIG_DESC_STRING_SIZE	31
#define APP_USBD_CONFIG_DESC_STRING_UTF_ENABLED	0
/* Each string needs its descriptor *and* its index: app_usbd_core.c reads the
 * index macros when it builds the device descriptor, and they are configuration
 * here rather than an enumeration the SDK derives. The descriptors are wrapped
 * in APP_USBD_STRING_DESC because the UTF conversion is off; the macro is
 * defined by the time these are expanded. */
#define APP_USBD_STRING_ID_MANUFACTURER		1
#define APP_USBD_STRINGS_MANUFACTURER		APP_USBD_STRING_DESC("Nordic Semiconductor")
#define APP_USBD_STRING_ID_PRODUCT		2
#define APP_USBD_STRINGS_PRODUCT		APP_USBD_STRING_DESC("BenchTools BLE dongle")
/* The serial number is generated at run time from the device's FICR by
 * app_usbd_serial_num.c, so its descriptor is that module's array rather than
 * a literal: two dongles on one host must not present the same USB serial.
 *
 * Note the singular APP_USBD_STRING_SERIAL - app_usbd_string_desc.c indexes
 * its table with that spelling, while every other string uses the plural
 * APP_USBD_STRINGS_. The switch that makes the SDK declare the array is
 * spelled both ways across SDK versions, so both are set; the SDK then
 * declares it with its own type, and declaring it here as well only produces
 * a conflicting declaration. */
#define APP_USBD_STRING_ID_SERIAL		3
#define APP_USBD_STRING_SERIAL_EXTERN		1
#define APP_USBD_STRINGS_SERIAL_EXTERN		1
#define APP_USBD_STRING_SERIAL			g_extern_serial_number
#define APP_USBD_STRING_ID_CONFIGURATION	4
/* The languages the string descriptors are offered in. 0x0409 is the USB
 * LANGID for English (United States), which is what
 * APP_USBD_LANG_AND_SUBLANG(ENGLISH, ENGLISH_US) evaluates to; the number is
 * used directly so this does not depend on two SDK enumeration spellings. */
#define APP_USBD_STRINGS_LANGIDS		0x0409
#define APP_USBD_STRINGS_CONFIGURATION		APP_USBD_STRING_DESC("Default configuration")
/* APP_USBD_STRINGS_USER is an X-macro list, not a descriptor: defining it as
 * one breaks app_usbd_string_desc.h. No user strings are needed. */
#define APP_USBD_STRINGS_USER

#define APP_USBD_CDC_ACM_ENABLED		1
#define APP_USBD_CDC_ACM_ZLP_ON_EPSIZE_WRITE	1

/* ------------------------------------------------------------ SoftDevice */
#define NRF_SDH_ENABLED				1
#define NRF_SDH_DISPATCH_MODEL			0	/**< interrupt context */
#define NRF_SDH_CLOCK_LF_SRC			1
#define NRF_SDH_CLOCK_LF_RC_CTIV		0
#define NRF_SDH_CLOCK_LF_RC_TEMP_CTIV		0
#define NRF_SDH_CLOCK_LF_ACCURACY		7
#define NRF_SDH_BLE_ENABLED			1
#define NRF_SDH_SOC_ENABLED			1

/** One central link, no peripheral links: this dongle only ever connects
 *  outwards to a sensor. */
#define NRF_SDH_BLE_PERIPHERAL_LINK_COUNT	0
#define NRF_SDH_BLE_CENTRAL_LINK_COUNT		1
#define NRF_SDH_BLE_TOTAL_LINK_COUNT		1
#define NRF_SDH_BLE_GAP_EVENT_LENGTH		6
/* Data length extension, to match the 247-byte MTU below: without it every
 * long write is fragmented across connection events, which is exactly the
 * timing this dongle exists to measure. The SDK static asserts this is < 252. */
#define NRF_SDH_BLE_GAP_DATA_LENGTH		251
#define NRF_SDH_BLE_GATT_MAX_MTU_SIZE		247
#define NRF_SDH_BLE_GATTS_ATTR_TAB_SIZE		248
#define NRF_SDH_BLE_VS_UUID_COUNT		2	/**< the NUS base UUID */
#define NRF_SDH_BLE_SERVICE_CHANGED		0
#define NRF_SDH_BLE_OBSERVER_PRIO_LEVELS	4
#define NRF_SDH_SOC_OBSERVER_PRIO_LEVELS	2
#define NRF_SDH_STACK_OBSERVER_PRIO_LEVELS	2
#define NRF_SDH_BLE_STACK_OBSERVER_PRIO		0
#define NRF_SDH_SOC_STACK_OBSERVER_PRIO		0
#define NRF_SDH_CLOCK_LF_XTAL_ACCURACY		7
#define NRF_SDH_REQ_OBSERVER_PRIO_LEVELS	2
#define NRF_SDH_STATE_OBSERVER_PRIO_LEVELS	2

/* ------------------------------------------------------- BLE components */
#define NRF_BLE_SCAN_ENABLED			1
#define NRF_BLE_SCAN_BUFFER			31
#define NRF_BLE_SCAN_NAME_MAX_LEN		32
#define NRF_BLE_SCAN_SHORT_NAME_MAX_LEN		32
#define NRF_BLE_SCAN_SCAN_INTERVAL		160
#define NRF_BLE_SCAN_SCAN_WINDOW		160
#define NRF_BLE_SCAN_SCAN_DURATION		0
#define NRF_BLE_SCAN_MIN_CONNECTION_INTERVAL	6
#define NRF_BLE_SCAN_MAX_CONNECTION_INTERVAL	24
#define NRF_BLE_SCAN_SLAVE_LATENCY		0
#define NRF_BLE_SCAN_SUPERVISION_TIMEOUT	400
#define NRF_BLE_SCAN_FILTER_ENABLE		0
#define NRF_BLE_SCAN_ADDRESS_CNT		1
#define NRF_BLE_SCAN_NAME_CNT			1
#define NRF_BLE_SCAN_SHORT_NAME_CNT		1
#define NRF_BLE_SCAN_UUID_CNT			1
#define NRF_BLE_SCAN_APPEARANCE_CNT		1

#define NRF_BLE_GATT_ENABLED			1
#define BLE_DB_DISCOVERY_ENABLED		1
#define BLE_NUS_C_ENABLED			1
#define BLE_ADVDATA_ENABLED			1
#define BLE_CONN_STATE_ENABLED			1

/** GATT queue. SDK 17's ble_nus_c and ble_db_discovery queue their GATT
 *  operations rather than issuing them directly, so a queue must exist and be
 *  handed to both. One entry per operation in flight; four is what Nordic's own
 *  central examples use. */
#define NRF_BLE_GQ_ENABLED			1
#define NRF_BLE_GQ_QUEUE_SIZE			4
/** Sized from the protocol, not from the SDK's default of 20. Every UART
 *  command this dongle sends goes through this queue, and the queue *rejects*
 *  a write longer than this with NRF_ERROR_DATA_SIZE - so a default of 20
 *  would have refused every command over 20 bytes at run time, with nothing
 *  in the build to say so. */
#define NRF_BLE_GQ_DATAPOOL_ELEMENT_SIZE	PROTO_MAX_PAYLOAD
#define NRF_BLE_GQ_DATAPOOL_ELEMENT_COUNT	8
#define NRF_BLE_GQ_GATTC_WRITE_MAX_DATA_LEN	PROTO_MAX_PAYLOAD
/** This dongle is a central and never sends notifications, but nrf_ble_gq.c
 *  declares a stack buffer of this size unconditionally. The SDK's default. */
#define NRF_BLE_GQ_GATTS_HVX_MAX_DATA_LEN	20

/** Observer priorities. Every SDK module that registers a BLE observer static
 *  asserts on its own priority macro, so each must be defined even though the
 *  values are the SDK defaults: a missing one is a compile error in the SDK's
 *  header, several levels away from the cause. */
#define NRF_BLE_SCAN_OBSERVER_PRIO		1
#define NRF_BLE_GATT_BLE_OBSERVER_PRIO		1
#define NRF_BLE_GQ_BLE_OBSERVER_PRIO		1
/* The SDK's own header reads BLE_DB_DISC_BLE_OBSERVER_PRIO - the abbreviated
 * spelling - and static asserts on it. The longer name compiles and does
 * nothing, which is the worst kind of configuration error. */
#define BLE_DB_DISC_BLE_OBSERVER_PRIO		1
#define BLE_NUS_C_BLE_OBSERVER_PRIO		2
#define BLE_CONN_STATE_BLE_OBSERVER_PRIO	0
#define NRF_SDH_BLE_OBSERVER_PRIO_MAX		4

/* --------------------------------------------------------------- common */
#define APP_UTIL_PLATFORM_ENABLED		1
#define NRF_STRERROR_ENABLED			1
#define NRF_FPRINTF_ENABLED			1
#define NRF_BALLOC_ENABLED			1
#define NRF_BALLOC_CLI_CMDS			0
#define NRF_MEMOBJ_ENABLED			1
#define NRF_ATFIFO_ENABLED			1
#define NRF_ATOMIC_ENABLED			1
#define NRF_QUEUE_ENABLED			1
#define NRF_SECTION_ITER_ENABLED		1
#define NRF_SORTLIST_ENABLED			1	/**< app_timer v2 needs it */
/* nrf_sortlist.h expands its instance name through a *ternary in C code*
 * - (NRF_LOG_ENABLED && NRF_SORTLIST_CONFIG_LOG_ENABLED) ? name : NULL -
 * rather than through the logging macros that compile away. So the key has to
 * exist even with logging off, or every NRF_SORTLIST_DEF fails to compile, and
 * the error appears inside app_timer2.c with no mention of sortlist logging. */
#define NRF_SORTLIST_CONFIG_LOG_ENABLED		0
#define NRF_SORTLIST_CONFIG_LOG_LEVEL		3
#define NRF_SORTLIST_CONFIG_INFO_COLOR		0
#define NRF_SORTLIST_CONFIG_DEBUG_COLOR		0
#define NRF_ATFLAGS_ENABLED			1	/**< ble_conn_state needs it */
#define NRF_BALLOC_CLI_CMDS			0
#define APP_SCHEDULER_ENABLED			0
#define NRF_PWR_MGMT_ENABLED			0	/**< USB must stay awake */
#define NRF_LOG_ENABLED				0	/**< the host link is the log */

#endif /* SDK_CONFIG_H__ */
