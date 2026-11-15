# Host unit tests of the ETB S2-LP kit firmware (#84), with Unity.
#
#   cmake -S firmware/s2lp_kit/test -B build/s2lp-kit-tests
#   cmake --build build/s2lp-kit-tests && ctest --test-dir build/s2lp-kit-tests
#
# hal_l053.c and startup.c are the board's and are not built here; the fake
# HAL in support/ stands in for the board and the radio.

cmake_minimum_required(VERSION 3.16)
project(s2lp_kit_tests C)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
enable_testing()

set(FIRMWARE_DIR ${CMAKE_CURRENT_SOURCE_DIR}/..)
set(SUPPORT_DIR  ${CMAKE_CURRENT_SOURCE_DIR}/support)

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

add_library(firmware STATIC
	${FIRMWARE_DIR}/src/cmd.c
	${FIRMWARE_DIR}/src/ring.c
	${FIRMWARE_DIR}/src/rx.c
	${FIRMWARE_DIR}/src/s2lp.c
	${SUPPORT_DIR}/fake_hal.c
)
target_include_directories(firmware PUBLIC
	${FIRMWARE_DIR}/include
	${FIRMWARE_DIR}/src
	${SUPPORT_DIR}
)
target_compile_options(firmware PRIVATE
	-Wall -Wextra -Wconversion -Wshadow -Wstrict-prototypes -Werror
)

foreach(name rx cmd)
	add_executable(test_${name} test_${name}.c)
	target_link_libraries(test_${name} PRIVATE firmware unity)
	add_test(NAME ${name} COMMAND test_${name})
endforeach()
