/**
 * @file firmware_version.c
 * @brief The identity strings, defined once so every reader sees the same text.
 *
 * Traces to: PICO-FR-002, PICO-DD-VERSION.
 */

#include "firmware_version.h"

const char	firmware_g_title[] = FIRMWARE_TITLE;
const char	firmware_g_version[] = FIRMWARE_VERSION;
const char	firmware_g_build_date[] = FIRMWARE_BUILD_DATE;
