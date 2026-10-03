/**
 * @file firmware_version.c
 * @brief The identity strings, defined once so every reader sees the same text.
 *
 * Traces to: PICO-FR-006, PICO-DD-VERSION.
 */

#include "firmware_version.h"

const char	firmware_g_name[] = FIRMWARE_NAME;
const char	firmware_g_copyright[] = FIRMWARE_COPYRIGHT;
const char	firmware_g_version[] = FIRMWARE_VERSION;
const char	firmware_g_sha[] = FIRMWARE_GIT_SHA;
