/**
 * @file app_util_platform.h
 * @brief Host-test stand-in for critical regions and interrupt priorities.
 *
 * The critical-region macros keep the SDK's brace-pair shape deliberately: the
 * firmware once returned from inside a region (defect D-23), and a flat pair of
 * function calls here would let that compile again.
 *
 * Traces to: BLE-DD-TEST.
 */

#ifndef APP_UTIL_PLATFORM_H__
#define APP_UTIL_PLATFORM_H__

#include "nrf_error.h"

#define APP_IRQ_PRIORITY_HIGHEST	0
#define APP_IRQ_PRIORITY_HIGH		2
#define APP_IRQ_PRIORITY_MID		4
#define APP_IRQ_PRIORITY_LOW		6

#ifndef UNUSED_PARAMETER
#define UNUSED_PARAMETER(x)		(void)(x)
#endif
#ifndef UNUSED_VARIABLE
#define UNUSED_VARIABLE(x)		(void)(x)
#endif

/** Nesting depth, so a test can prove a region was left. */
extern int fake_critical_nesting;
/** Deepest nesting reached, so a test can prove one was entered at all. */
extern int fake_critical_depth_max;

#define CRITICAL_REGION_ENTER()				\
	{						\
		fake_critical_nesting++;		\
		if (fake_critical_nesting > fake_critical_depth_max)	\
		{					\
			fake_critical_depth_max = fake_critical_nesting;	\
		}

#define CRITICAL_REGION_EXIT()				\
		fake_critical_nesting--;		\
	}

#endif /* APP_UTIL_PLATFORM_H__ */
