/**
 * @file firmware_version.c
 * @brief The identity strings, defined once so every reader sees the same text.
 *
 * Traces to: PICO-FR-002, PICO-DD-VERSION.
 */

#include "firmware_version.h"

const char	firmware_title_string[] = FIRMWARE_TITLE;
const char	firmware_version_string[] = FIRMWARE_VERSION;
const char	firmware_build_date_string[] = FIRMWARE_BUILD_DATE;
