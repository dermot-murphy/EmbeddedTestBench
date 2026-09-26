/**
 * @file firmware_version.h
 * @brief What this build of the firmware is, so the host can tell builds apart.
 *
 * Two facts, and both are needed:
 *
 * * **The version** is what a person changes deliberately when behaviour
 *   changes. It is edited here, and nowhere else.
 * * **The build date** is what distinguishes two builds of the *same* version -
 *   which is the usual case during development, and precisely when a stale
 *   dongle is most misleading. The host compares both.
 *
 * The date is injected by the build system as an ISO 8601 UTC instant, so that
 * it is unambiguous and sorts correctly. A build that does not inject one - an
 * IDE build, say - falls back to the compiler's own macros, which are local
 * time in an awkward format; the host reports that as an imprecise date rather
 * than pretending it is UTC.
 *
 * Traces to: BLE-FR-012, BLE-DD-VERSION.
 */

#ifndef FIRMWARE_VERSION_H__
#define FIRMWARE_VERSION_H__

/** Firmware version. Change it when behaviour changes; the host compares it. */
#define FIRMWARE_VERSION		"1.4.0"

/* FIRMWARE_BUILD_DATE is injected by the build system, and deliberately not
 * defaulted here. Without it, firmware_version.c falls back to the compiler's
 * macros, rearranged as "local:Sep-13-2026T14:22:31": local time and not
 * sortable, so tagged to keep it from being read as an ISO instant, and free of
 * spaces because the link protocol splits fields on them. */

/** The version this image was built as, e.g. "1.1.0". */
extern const char	firmware_version_string[];

/**
 * @brief When this image was built.
 *
 * ISO 8601 UTC when the build system injected one, otherwise the compiler's own
 * macros as "local:Sep-13-2026T14:22:31". Read this rather than the macro: see
 * firmware_version.c for why the distinction matters.
 *
 * @return A string with no spaces, valid for the life of the program.
 */
const char * firmware_build_date(void);

#endif /* FIRMWARE_VERSION_H__ */
