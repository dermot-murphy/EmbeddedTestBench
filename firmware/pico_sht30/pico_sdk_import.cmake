# Locate the Raspberry Pi Pico C SDK.
#
# Order of preference:
#   1. -DPICO_SDK_PATH=... on the cmake command line
#   2. the PICO_SDK_PATH environment variable
#   3. -DPICO_SDK_FETCH_FROM_GIT=ON: fetch the pinned release below
#
# A reduced form of the SDK's own external/pico_sdk_import.cmake, kept here so
# that the project configures without a copy of the SDK on the include path.
#
# Traces to: PICO-DD-BUILD.

if (DEFINED ENV{PICO_SDK_PATH} AND (NOT PICO_SDK_PATH))
	set(PICO_SDK_PATH $ENV{PICO_SDK_PATH})
endif ()

set(PICO_SDK_FETCH_FROM_GIT_TAG "2.1.1" CACHE STRING "SDK release fetched when PICO_SDK_FETCH_FROM_GIT is set")

if (NOT PICO_SDK_PATH)
	if (PICO_SDK_FETCH_FROM_GIT)
		include(FetchContent)
		FetchContent_Declare(
			pico_sdk
			GIT_REPOSITORY https://github.com/raspberrypi/pico-sdk
			GIT_TAG        ${PICO_SDK_FETCH_FROM_GIT_TAG}
			GIT_SUBMODULES_RECURSE FALSE
			GIT_SUBMODULES lib/tinyusb
		)
		FetchContent_GetProperties(pico_sdk)
		if (NOT pico_sdk_POPULATED)
			message(STATUS "Fetching Pico SDK ${PICO_SDK_FETCH_FROM_GIT_TAG}")
			FetchContent_Populate(pico_sdk)
		endif ()
		set(PICO_SDK_PATH ${pico_sdk_SOURCE_DIR})
	else ()
		message(FATAL_ERROR
			"Pico SDK not found. Set PICO_SDK_PATH, or configure with -DPICO_SDK_FETCH_FROM_GIT=ON.")
	endif ()
endif ()

get_filename_component(PICO_SDK_PATH "${PICO_SDK_PATH}" REALPATH BASE_DIR "${CMAKE_BINARY_DIR}")
if (NOT EXISTS ${PICO_SDK_PATH}/pico_sdk_init.cmake)
	message(FATAL_ERROR "'${PICO_SDK_PATH}' does not contain the Pico SDK")
endif ()

set(PICO_SDK_PATH ${PICO_SDK_PATH} CACHE PATH "Path to the Raspberry Pi Pico SDK" FORCE)

include(${PICO_SDK_PATH}/pico_sdk_init.cmake)
