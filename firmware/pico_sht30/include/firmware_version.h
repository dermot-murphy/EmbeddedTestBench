/**
 * @file firmware_version.h
 * @brief What this build of the thermometer firmware is, so the host can tell
 *        builds apart.
 *
 * Three facts are reported by @c ver:
 *
 * * **The title** names the product. It is one token with no spaces, so it
 *   survives the protocol's @c key=value form without quoting.
 * * **The version** is what a person changes deliberately when behaviour
 *   changes. It is edited here, and nowhere else.
 * * **The build date** distinguishes two builds of the *same* version. The
 *   build system injects it as an ISO 8601 UTC instant; a build that does not
 *   falls back to the compiler's macros and is tagged @c local: so that the
 *   host does not read it as UTC.
 *
 * Traces to: PICO-FR-002, PICO-DD-VERSION.
 */

#ifndef FIRMWARE_VERSION_H__
#define FIRMWARE_VERSION_H__

/** Product title reported by @c ver. One token: no spaces. */
#define FIRMWARE_TITLE			"Pico2-SHT30-Thermometer"

/** Firmware version. Change it when behaviour changes; the host compares it. */
#define FIRMWARE_VERSION		"1.0.0"

#ifndef FIRMWARE_BUILD_DATE
/* Not injected: fall back to the compiler's macros. The spaces in __DATE__ are
 * replaced when the value is sent, so it still arrives as one token. */
#define FIRMWARE_BUILD_DATE		"local:" __DATE__ "T" __TIME__
#endif

/** The title this image was built with. */
extern const char	firmware_g_title[];

/** The version this image was built as, e.g. "1.0.0". */
extern const char	firmware_g_version[];

/** When this image was built. */
extern const char	firmware_g_build_date[];

#endif /* FIRMWARE_VERSION_H__ */
