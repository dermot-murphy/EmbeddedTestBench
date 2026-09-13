/**
 * @file firmware_version.c
 * @brief The build's identity, in one translation unit on purpose.
 *
 * The version and the build date are held here rather than expanded wherever
 * they are used, for one reason: this file is recompiled on every build (the
 * Makefile deletes its object first), so the date the image reports is always
 * the date the build system recorded in the manifest beside it.
 *
 * Expanding the macros at each use would not survive an incremental build. The
 * date arrives through CFLAGS, and make does not recompile a file because a
 * command line changed; the image would keep the date of the first build while
 * the manifest carried today's, and the host - comparing the two - would report
 * a dongle as out of date immediately after refreshing it, for ever.
 *
 * Traces to: BLE-FR-012, BLE-DD-VERSION.
 */

#include "firmware_version.h"

const char	firmware_version_string[] = FIRMWARE_VERSION;
const char	firmware_build_date_string[] = FIRMWARE_BUILD_DATE;
