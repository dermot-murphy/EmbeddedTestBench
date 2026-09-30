# Host-side unit tests for the Pico 2 + SHT30-D firmware.
#
# The firmware's portable sources are compiled here unchanged; the board is
# replaced at the hal.h seam by support/fake_hal.c.
#
#   cmake -S firmware/pico_sht30/test -B build/pico-tests
#   cmake --build build/pico-tests
#   ctest --test-dir build/pico-tests --output-on-failure
#
# Unity is fetched at configure time; set UNITY_DIR to use a local copy instead.
#
# Traces to: PICO-DD-TEST, SWE4-UT-PICOFW.

cmake_minimum_required(VERSION 3.16)
project(pico_sht30_tests C)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
enable_testing()

set(FIRMWARE_DIR ${CMAKE_CURRENT_SOURCE_DIR}/..)
set(SUPPORT_DIR  ${CMAKE_CURRENT_SOURCE_DIR}/support)

# --- Unity -------------------------------------------------------------
set(UNITY_DIR "" CACHE PATH "Local Unity checkout; fetched from GitHub when empty")

if(UNITY_DIR STREQUAL "")
	include(FetchContent)
	FetchContent_Declare(
		unity
		GIT_REPOSITORY https://github.com/ThrowTheSwitch/Unity.git
		GIT_TAG        v2.6.0
		GIT_SHALLOW    TRUE
	)
	FetchContent_MakeAvailable(unity)
else()
	add_library(unity STATIC ${UNITY_DIR}/src/unity.c)
	target_include_directories(unity PUBLIC ${UNITY_DIR}/src)
endif()

# --- the firmware under test -------------------------------------------
# Built with the same warnings as the target build, as errors, plus the
# sanitisers: an out-of-bounds write in a line buffer is exactly the defect a
# bench would never show.
add_library(firmware STATIC
	${FIRMWARE_DIR}/src/cmd_parser.c
	${FIRMWARE_DIR}/src/firmware_version.c
	${FIRMWARE_DIR}/src/sht30.c
	${FIRMWARE_DIR}/src/text.c
	${SUPPORT_DIR}/fake_hal.c
)
target_include_directories(firmware PUBLIC
	${FIRMWARE_DIR}/include
	${FIRMWARE_DIR}/src
	${SUPPORT_DIR}
)
target_compile_definitions(firmware PUBLIC FIRMWARE_BUILD_DATE="2026-01-01T00:00:00Z")
target_compile_options(firmware PRIVATE
	-Wall -Wextra -Wconversion -Wshadow -Wstrict-prototypes -Werror
)

set(SANITIZE -fsanitize=address,undefined -fno-omit-frame-pointer -fno-sanitize-recover=all)
target_compile_options(firmware PUBLIC ${SANITIZE})
target_link_options(firmware PUBLIC ${SANITIZE})

foreach(name text sht30 cmd_parser)
	add_executable(test_${name} ${CMAKE_CURRENT_SOURCE_DIR}/test_${name}.c)
	target_link_libraries(test_${name} firmware unity)
	add_test(NAME ${name} COMMAND test_${name})
endforeach()
