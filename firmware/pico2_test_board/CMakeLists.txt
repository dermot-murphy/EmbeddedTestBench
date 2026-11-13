# Raspberry Pi Pico 2 + SHT30-D thermometer firmware.
#
#   export PICO_SDK_PATH=/path/to/pico-sdk        # 2.1.1 or later
#   cmake -S firmware/pico2_test_board -B build/pico2_test_board
#   cmake --build build/pico2_test_board -j
#
# produces build/pico2_test_board/pico2_test_board.uf2. Flash it with
#
#   benchtools pico2 -r <port> flash build/pico2_test_board/pico2_test_board.uf2
#
# which needs no button press. If the firmware has crashed or the Pico does
# not appear on USB, hold BOOTSEL while plugging the Pico 2 in and copy the
# .uf2 to the RP2350 drive that appears.
#
# Without PICO_SDK_PATH, configure with -DPICO_SDK_FETCH_FROM_GIT=ON to fetch
# the pinned SDK release.
#
# Traces to: PICO-NFR-003, PICO-FR-006, PICO-DD-BUILD.

cmake_minimum_required(VERSION 3.13)

set(PICO_BOARD pico2 CACHE STRING "Board type")
set(PICO_PLATFORM rp2350-arm-s CACHE STRING "Platform: the Pico 2's Cortex-M33 cores")

include(${CMAKE_CURRENT_LIST_DIR}/pico_sdk_import.cmake)

project(pico2_test_board C CXX ASM)
set(CMAKE_C_STANDARD 11)   # the SDK uses static_assert; MISRA C:2012 Amd 3 covers C11
set(CMAKE_C_STANDARD_REQUIRED ON)

pico_sdk_init()

# The commit the image is built from is injected as its short SHA, reported by
# "rd sha". Outside a git checkout, or without git, it is "unknown".
#
# The SHA is read at configure time, so CMake is told which files hold HEAD:
# when a commit, checkout or reset moves HEAD, the next build re-configures and
# the image carries the new SHA. "git rev-parse --git-path" resolves each file
# to where it really is, which in a worktree (where .git is a file, not a
# directory) is not under the source tree's .git. A branch ref may live in its
# own file or in packed-refs, so both are watched, and so is HEAD's reflog,
# which git appends to on every commit even when the ref is only packed.
set(FIRMWARE_GIT_SHA "unknown")
find_package(Git QUIET)
if(GIT_FOUND)
	execute_process(
		COMMAND ${GIT_EXECUTABLE} rev-parse --short=7 HEAD
		WORKING_DIRECTORY ${CMAKE_CURRENT_LIST_DIR}
		RESULT_VARIABLE FIRMWARE_GIT_RESULT
		OUTPUT_VARIABLE FIRMWARE_GIT_OUTPUT
		OUTPUT_STRIP_TRAILING_WHITESPACE
		ERROR_QUIET
	)
	if(FIRMWARE_GIT_RESULT EQUAL 0 AND NOT FIRMWARE_GIT_OUTPUT STREQUAL "")
		set(FIRMWARE_GIT_SHA "${FIRMWARE_GIT_OUTPUT}")

		# HEAD and its reflog, and the ref HEAD points at when a branch
		# is checked out (nothing more when HEAD is detached).
		set(FIRMWARE_GIT_WATCH HEAD logs/HEAD)
		execute_process(
			COMMAND ${GIT_EXECUTABLE} symbolic-ref -q HEAD
			WORKING_DIRECTORY ${CMAKE_CURRENT_LIST_DIR}
			RESULT_VARIABLE FIRMWARE_GIT_RESULT
			OUTPUT_VARIABLE FIRMWARE_GIT_REF
			OUTPUT_STRIP_TRAILING_WHITESPACE
			ERROR_QUIET
		)
		if(FIRMWARE_GIT_RESULT EQUAL 0 AND NOT FIRMWARE_GIT_REF STREQUAL "")
			list(APPEND FIRMWARE_GIT_WATCH ${FIRMWARE_GIT_REF} packed-refs)
		endif()

		foreach(FIRMWARE_GIT_NAME IN LISTS FIRMWARE_GIT_WATCH)
			execute_process(
				COMMAND ${GIT_EXECUTABLE} rev-parse --git-path ${FIRMWARE_GIT_NAME}
				WORKING_DIRECTORY ${CMAKE_CURRENT_LIST_DIR}
				RESULT_VARIABLE FIRMWARE_GIT_RESULT
				OUTPUT_VARIABLE FIRMWARE_GIT_PATH
				OUTPUT_STRIP_TRAILING_WHITESPACE
				ERROR_QUIET
			)
			# The path is relative to the working directory in a plain
			# checkout and absolute in a worktree. A file that does not
			# exist (a branch with no loose ref, a repository never
			# packed) cannot be watched; the others still are.
			get_filename_component(FIRMWARE_GIT_PATH "${FIRMWARE_GIT_PATH}"
				ABSOLUTE BASE_DIR ${CMAKE_CURRENT_LIST_DIR})
			if(FIRMWARE_GIT_RESULT EQUAL 0 AND EXISTS "${FIRMWARE_GIT_PATH}")
				set_property(DIRECTORY APPEND PROPERTY
					CMAKE_CONFIGURE_DEPENDS "${FIRMWARE_GIT_PATH}")
			endif()
		endforeach()
	endif()
endif()
message(STATUS "pico2_test_board: FIRMWARE_GIT_SHA=${FIRMWARE_GIT_SHA}")

set(FIRMWARE_SOURCES
	${CMAKE_CURRENT_LIST_DIR}/src/cmd_fgen.c
	${CMAKE_CURRENT_LIST_DIR}/src/cmd_parser.c
	${CMAKE_CURRENT_LIST_DIR}/src/fgen.c
	${CMAKE_CURRENT_LIST_DIR}/src/firmware_version.c
	${CMAKE_CURRENT_LIST_DIR}/src/hal_pico.c
	${CMAKE_CURRENT_LIST_DIR}/src/main.c
	${CMAKE_CURRENT_LIST_DIR}/src/sht30.c
	${CMAKE_CURRENT_LIST_DIR}/src/text.c
)

add_executable(pico2_test_board ${FIRMWARE_SOURCES})

target_include_directories(pico2_test_board PRIVATE
	${CMAKE_CURRENT_LIST_DIR}/include
	${CMAKE_CURRENT_LIST_DIR}/src
)

target_compile_definitions(pico2_test_board PRIVATE
	FIRMWARE_GIT_SHA="${FIRMWARE_GIT_SHA}"
)

# Warnings as errors for this firmware's own sources only: the SDK's sources
# are compiled into the same target and are not ours to hold to that.
set_source_files_properties(${FIRMWARE_SOURCES} PROPERTIES
	COMPILE_OPTIONS "-Wall;-Wextra;-Wconversion;-Wshadow;-Wstrict-prototypes;-Werror"
)

target_link_libraries(pico2_test_board
	pico_stdlib
	pico_unique_id
	pico_bootrom
	hardware_dma
	hardware_i2c
	hardware_pio
	hardware_pwm
	hardware_watchdog
)

# USB CDC for the host link; the UART stays free for a debug probe.
pico_enable_stdio_usb(pico2_test_board 1)
pico_enable_stdio_uart(pico2_test_board 0)

pico_set_program_name(pico2_test_board "PICO2 Test Board")
pico_set_program_description(pico2_test_board "SHT30-D temperature over USB CDC")

pico_add_extra_outputs(pico2_test_board)
