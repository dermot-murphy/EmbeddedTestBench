/**
 * @file firmware_version.h
 * @brief What this build of the thermometer firmware is, so the host can tell
 *        builds apart.
 *
 * Four facts are reported by the @c rd command:
 *
 * * **The name** (@c rd @c name) names the product.
 * * **The copyright** (@c rd @c copyright) names the owner.
 * * **The version** (@c rd @c version) is what a person changes deliberately
 *   when behaviour changes. It is edited here, and nowhere else.
 * * **The commit** (@c rd @c sha) is the short SHA of the commit the image was
 *   built from. The build system injects it; a build that does not reports
 *   @c unknown.
 *
 * The version has the form V<major>.<minor>.<patch>, with the minor number as
 * two digits and the patch number as four, e.g. V1.00.0000. It follows
 * semantic versioning and is bumped with every change to the firmware or to
 * its host driver:
 *
 * * major - a breaking change to the protocol;
 * * minor - an added command or feature;
 * * patch - a fix.
 *
 * Each value is a single quoted string, because the host driver's test suite
 * reads them from this file as text.
 *
 * Traces to: PICO-FR-006, PICO-DD-VERSION.
 */

#ifndef FIRMWARE_VERSION_H__
#define FIRMWARE_VERSION_H__

/** Product name reported by @c rd @c name. */
#define FIRMWARE_NAME			"Pico 2 SHT30 Temperature Sensor"

/** Copyright notice reported by @c rd @c copyright. */
#define FIRMWARE_COPYRIGHT		"(c) 2026 Dermot Murphy"

/** Firmware version reported by @c rd @c version. Bump it with every change;
 *  the host compares it. */
#define FIRMWARE_VERSION		"V1.00.0000"

#ifndef FIRMWARE_GIT_SHA
/* Not injected by the build: say so rather than guess. */
#define FIRMWARE_GIT_SHA		"unknown"
#endif

/** The name this image was built with. */
extern const char	firmware_g_name[];

/** The copyright notice this image was built with. */
extern const char	firmware_g_copyright[];

/** The version this image was built as, e.g. "V1.00.0000". */
extern const char	firmware_g_version[];

/** The short SHA of the commit this image was built from, or "unknown". */
extern const char	firmware_g_sha[];

#endif /* FIRMWARE_VERSION_H__ */
