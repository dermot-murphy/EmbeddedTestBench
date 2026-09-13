#!/bin/bash
# Compile the dongle firmware against real SDK headers, without a bench.
#
# Runs inside the canembed/canembed-arm image, which carries arm-none-eabi-gcc
# 10.2.1, SEGGER Embedded Studio and nRF5 SDK 15.2.0. The delivered firmware
# targets SDK 17.1.0, so this is a *cross-version* check:
#
#   what it proves      syntax, types, SDK API usage, sdk_config keys the SDK's
#                       own headers assert on, and every call this firmware
#                       makes that exists in both SDKs
#   what it cannot      that the firmware links, fits, or runs; and the four
#                       lines using SDK 17's GATT queue, which 15.2 has no
#                       equivalent for - those are listed, not silently skipped
#
# Usage, from the repository root:
#
#   docker run --rm -v "$PWD":/work:ro canembed/canembed-arm \
#          bash /work/firmware/nordic_dongle/scripts/compile_check.sh
#
# Discharging BLE-OPEN-01 means building the real SES project against SDK
# 17.1.0. This check is what can be done without it, and it has already found
# seven defects: see BENCHTOOLS-SWE4-002 §10, D-20 to D-26.
#
# Traces to: BLE-NFR-001, BLE-FR-090, BLE-DD-BUILD.
set -u

SDK=${SDK:-/nordic/sdk/nRF5_SDK_15.2.0_9412b96}
FW=$(cd "$(dirname "$0")/.." && pwd)
OUT=${OUT:-/tmp/dongle-compile-check}
SHIM=$OUT/shim
mkdir -p "$OUT" "$SHIM"

if [ ! -d "$SDK" ]; then
	echo "no SDK at $SDK - set SDK=/path/to/nRF5_SDK_x" >&2
	exit 2
fi

# SDK 17's ble_nus_c and ble_db_discovery submit GATT operations through a queue
# that SDK 15.2 does not have. Declaring the two symbols lets the compiler check
# the rest of those files. Anything declared here is, by definition, unverified.
cat > "$SHIM/nrf_ble_gq.h" <<'SHIMEOF'
#ifndef NRF_BLE_GQ_SHIM_H__
#define NRF_BLE_GQ_SHIM_H__
typedef struct { int unused; } nrf_ble_gq_t;
#define NRF_BLE_GQ_DEF(name, links, size) static nrf_ble_gq_t name
#endif
SHIMEOF

INC="-I$FW/include -I$FW/src -I$FW/config -I$SHIM"
for directory in \
	components/ble/ble_db_discovery components/ble/ble_services/ble_nus_c \
	components/ble/common components/ble/nrf_ble_gatt components/ble/nrf_ble_scan \
	components/ble/nrf_ble_gq components/ble/ble_link_ctx_manager \
	components/libraries/atomic components/libraries/atomic_fifo \
	components/libraries/atomic_flags components/libraries/balloc \
	components/libraries/delay components/libraries/experimental_section_vars \
	components/libraries/log components/libraries/log/src components/libraries/memobj \
	components/libraries/mutex components/libraries/queue components/libraries/ringbuf \
	components/libraries/scheduler components/libraries/sortlist \
	components/libraries/stack_info components/libraries/strerror \
	components/libraries/timer components/libraries/usbd \
	components/libraries/usbd/class/cdc components/libraries/usbd/class/cdc/acm \
	components/libraries/util components/libraries/fifo components/drivers_nrf/usbd \
	components/softdevice/s140/headers components/softdevice/s140/headers/nrf52 \
	components/softdevice/common components/toolchain/cmsis/include \
	integration/nrfx integration/nrfx/legacy modules/nrfx \
	modules/nrfx/drivers/include modules/nrfx/hal modules/nrfx/mdk ; do
	[ -d "$SDK/$directory" ] && INC="$INC -I$SDK/$directory"
done

# NRF_SD_BLE_API_VERSION follows the SoftDevice in the SDK being compiled
# against: 6 for S140 6.1 (SDK 15.2), 7 for S140 7.2 (SDK 17.1).
API=${API:-6}
DEFS="-DNRF52840_XXAA -DS140 -DSOFTDEVICE_PRESENT -DNRF_SD_BLE_API_VERSION=$API \
      -DAPP_TIMER_V2 -DAPP_TIMER_V2_RTC1_ENABLED -DBOARD_PCA10059 \
      -DCONFIG_GPIO_AS_PINRESET -DFLOAT_ABI_HARD -D__HEAP_SIZE=2048 -D__STACK_SIZE=8192"
ARCH="-mcpu=cortex-m4 -mthumb -mabi=aapcs -mfloat-abi=hard -mfpu=fpv4-sp-d16"
WARN="-Wall -Wextra -Wno-unused-parameter -Wno-expansion-to-defined"

status=0
for unit in timestamp cdc_acm ble_scanner nus_client bootloader firmware_version cmd_parser main; do
	printf '%-16s ' "$unit.c"
	if arm-none-eabi-gcc -c $ARCH $DEFS $WARN -std=c99 -O2 $INC \
	       "$FW/src/$unit.c" -o "$OUT/$unit.o" 2> "$OUT/$unit.err"; then
		echo "OK ($(grep -c 'warning:' "$OUT/$unit.err") warning(s))"
	else
		# Errors naming SDK 17 API that this SDK does not have are expected
		# on an older SDK; anything else is a defect in this firmware.
		# The last pattern is the cascade from the unknown init type: it can
		# only arise from that, so allowing it hides nothing else.
		expected="p_gatt_queue|error_handler|ble_db_discovery_init_t"
		expected="$expected|request for member 'evt_handler' in something not a structure"
		if grep -q "error:" "$OUT/$unit.err" && \
		   ! grep "error:" "$OUT/$unit.err" | grep -qvE "$expected"; then
			echo "OK apart from SDK 17 API absent from this SDK:"
			grep "error:" "$OUT/$unit.err" | sed 's|.*error:|      |' | sort -u
		else
			echo "FAILED"
			grep "error:" "$OUT/$unit.err" | head -10
			status=1
		fi
	fi
done

echo
echo "object files in $OUT"
exit $status
