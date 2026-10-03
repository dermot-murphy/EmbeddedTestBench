# Raspberry Pi Pico 2 + SHT30-D thermometer firmware.
#
#   export PICO_SDK_PATH=/path/to/pico-sdk        # 2.1.1 or later
#   cmake -S firmware/pico_sht30 -B build/pico_sht30
#   cmake --build build/pico_sht30 -j
#
# produces build/pico_sht30/pico_sht30.uf2. Flash it with
#
#   benchtools thermo -r <port> flash build/pico_sht30/pico_sht30.uf2
#
# which needs no button press. If the firmware has crashed or the Pico does
# not appear on USB, hold BOOTSEL while plugging the Pico 2 in and copy the
# .uf2 to the RP2350 drive that appears.
#
# Without PICO_SDK_PATH, configure with -DPICO_SDK_FETCH_FROM_GIT=ON to fetch
# the pinned SDK release.
#
# Traces to: PICO-NFR-003, PICO-DD-BUILD.

cmake_minimum_required(VERSION 3.13)

set(PICO_BOARD pico2 CACHE STRING "Board type")
set(PICO_PLATFORM rp2350-arm-s CACHE STRING "Platform: the Pico 2's Cortex-M33 cores")

include(${CMAKE_CURRENT_LIST_DIR}/pico_sdk_import.cmake)

project(pico_sht30 C CXX ASM)
set(CMAKE_C_STANDARD 11)   # the SDK uses static_assert; MISRA C:2012 Amd 3 covers C11
set(CMAKE_C_STANDARD_REQUIRED ON)

pico_sdk_init()

# The build date is injected as an ISO 8601 UTC instant, so that two builds of
# the same version can be told apart and the value sorts correctly.
string(TIMESTAMP FIRMWARE_BUILD_DATE "%Y-%m-%dT%H:%M:%SZ" UTC)

set(FIRMWARE_SOURCES
	${CMAKE_CURRENT_LIST_DIR}/src/cmd_parser.c
	${CMAKE_CURRENT_LIST_DIR}/src/firmware_version.c
	${CMAKE_CURRENT_LIST_DIR}/src/hal_pico.c
	${CMAKE_CURRENT_LIST_DIR}/src/main.c
	${CMAKE_CURRENT_LIST_DIR}/src/sht30.c
	${CMAKE_CURRENT_LIST_DIR}/src/text.c
)

add_executable(pico_sht30 ${FIRMWARE_SOURCES})

target_include_directories(pico_sht30 PRIVATE
	${CMAKE_CURRENT_LIST_DIR}/include
	${CMAKE_CURRENT_LIST_DIR}/src
)

target_compile_definitions(pico_sht30 PRIVATE
	FIRMWARE_BUILD_DATE="${FIRMWARE_BUILD_DATE}"
)

# Warnings as errors for this firmware's own sources only: the SDK's sources
# are compiled into the same target and are not ours to hold to that.
set_source_files_properties(${FIRMWARE_SOURCES} PROPERTIES
	COMPILE_OPTIONS "-Wall;-Wextra;-Wconversion;-Wshadow;-Wstrict-prototypes;-Werror"
)

target_link_libraries(pico_sht30
	pico_stdlib
	pico_unique_id
	pico_bootrom
	hardware_i2c
	hardware_watchdog
)

# USB CDC for the host link; the UART stays free for a debug probe.
pico_enable_stdio_usb(pico_sht30 1)
pico_enable_stdio_uart(pico_sht30 0)

pico_set_program_name(pico_sht30 "Pico2-SHT30-Thermometer")
pico_set_program_description(pico_sht30 "SHT30-D temperature over USB CDC")

pico_add_extra_outputs(pico_sht30)
