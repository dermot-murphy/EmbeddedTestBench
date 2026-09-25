# Host-side unit tests for the dongle firmware.
#
# The firmware's own sources are compiled here, unchanged, against fake SDK
# headers in support/include. The seam is the SDK boundary: everything above it
# - line assembly, the outgoing queue, the sensor table, the command dispatcher,
# the round-trip timing - is the code that runs on the dongle.
#
#   cmake -S firmware/nordic_dongle/test -B build/firmware-tests
#   cmake --build build/firmware-tests
#   ctest --test-dir build/firmware-tests --output-on-failure
#
# Unity is fetched at configure time; set UNITY_DIR to use a local copy instead.
#
# Traces to: BLE-DD-TEST, SWE4-UT-FWUNIT.

cmake_minimum_required(VERSION 3.16)
project(nordic_dongle_tests C)

set(CMAKE_C_STANDARD 99)
set(CMAKE_C_STANDARD_REQUIRED ON)
enable_testing()

set(FIRMWARE_DIR ${CMAKE_CURRENT_SOURCE_DIR}/..)
set(SUPPORT_DIR  ${CMAKE_CURRENT_SOURCE_DIR}/support)

# --- Unity -------------------------------------------------------------
# Pinned to a release tag: a test framework that moves under the suite is a
# source of failures that have nothing to do with the firmware.
set(UNITY_DIR "" CACHE PATH "Local Unity checkout; fetched from GitHub when empty")

if(UNITY_DIR STREQUAL "")
	include(FetchContent)
	FetchContent_Declare(
		unity
		GIT_REPOSITORY https://github.com/ThrowTheSwitch/Unity.git
		GIT_TAG        v2.6.0
		GIT_SHALLOW    TRUE
	)
	FetchContent_MakeAvailable(unity)      # provides the `unity` target
else()
	add_library(unity STATIC ${UNITY_DIR}/src/unity.c)
	target_include_directories(unity PUBLIC ${UNITY_DIR}/src)
endif()

# 64-bit assertions must be enabled where unity.c itself is compiled, not only
# where it is used, or TEST_ASSERT_EQUAL_UINT64 links against nothing. The
# timestamp is a 64-bit microsecond count, so this is not optional here.
target_compile_definitions(unity PUBLIC UNITY_SUPPORT_64 UNITY_INCLUDE_DOUBLE)

# --- what every test needs ---------------------------------------------
add_library(test_support INTERFACE)
target_include_directories(test_support INTERFACE
	${SUPPORT_DIR}
	${SUPPORT_DIR}/include        # fake SDK headers, ahead of everything
	${FIRMWARE_DIR}/include
	${FIRMWARE_DIR}/src
)
target_link_libraries(test_support INTERFACE unity)

# The firmware is built with warnings as errors here: it cannot be built that
# way against the real SDK, whose headers are not warning-clean, but its own
# sources can and should be.
add_compile_options(-Wall -Wextra -Wno-unused-parameter)

# Sources that stand in for the SDK, and for the firmware's own modules when one
# is faked to test another. A binary links only what it needs: linking a fake
# beside the module it replaces is a duplicate symbol.
set(FAKE_SDK       ${SUPPORT_DIR}/fake_sdk.c)
set(FAKE_HOST_LINK ${SUPPORT_DIR}/fake_host_link.c)
set(FAKE_SCANNER   ${SUPPORT_DIR}/fake_scanner.c)
set(FAKE_NUS       ${SUPPORT_DIR}/fake_nus_client.c)

function(add_firmware_test name)
	cmake_parse_arguments(ARG "" "" "SOURCES" ${ARGN})
	add_executable(${name} ${CMAKE_CURRENT_SOURCE_DIR}/${name}.c ${ARG_SOURCES})
	target_link_libraries(${name} PRIVATE test_support)
	add_test(NAME ${name} COMMAND ${name})
	set_tests_properties(${name} PROPERTIES TIMEOUT 30)
endfunction()

add_firmware_test(test_timestamp
	SOURCES ${FIRMWARE_DIR}/src/timestamp.c ${FAKE_SDK})

add_firmware_test(test_cdc_acm
	SOURCES ${FIRMWARE_DIR}/src/cdc_acm.c ${FAKE_SDK})

add_firmware_test(test_ble_scanner
	SOURCES ${FIRMWARE_DIR}/src/ble_scanner.c ${FAKE_SDK} ${FAKE_HOST_LINK})

add_firmware_test(test_nus_client
	SOURCES ${FIRMWARE_DIR}/src/nus_client.c ${FAKE_SDK} ${FAKE_HOST_LINK} ${FAKE_SCANNER})

# Compiled without FIRMWARE_BUILD_DATE, as an IDE build is, to see the fallback.
add_firmware_test(test_firmware_version
	SOURCES ${FIRMWARE_DIR}/src/firmware_version.c)

add_firmware_test(test_cmd_parser
	SOURCES ${FIRMWARE_DIR}/src/cmd_parser.c ${FIRMWARE_DIR}/src/cmd_args.c ${FIRMWARE_DIR}/src/bootloader.c
	        ${FIRMWARE_DIR}/src/firmware_version.c
	        ${FAKE_SDK} ${FAKE_HOST_LINK} ${FAKE_SCANNER} ${FAKE_NUS})

# A fixed build date, injected exactly as the real build injects one, so the
# test can assert the whole field rather than that it merely looks plausible.
set(TEST_BUILD_DATE "2000-01-01T00:00:00Z")
target_compile_definitions(test_cmd_parser
	PRIVATE FIRMWARE_BUILD_DATE="${TEST_BUILD_DATE}")
