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

#include <string.h>

const char	firmware_version_string[] = FIRMWARE_VERSION;

#ifdef FIRMWARE_BUILD_DATE

const char * firmware_build_date(void)
{
	return FIRMWARE_BUILD_DATE;
}

#else

/* Not injected - an IDE build, say. The compiler's own macros read
 * "Sep  5 2026" and "20:13:52", with spaces the line protocol would split into
 * separate fields, so the host would see only "local:Sep". They are rearranged
 * into "local:Sep-05-2026T20:13:52": one field, still tagged as local time.
 * C does not allow indexing a string literal in a static initializer, so this
 * is done once, at the first call. */
const char * firmware_build_date(void)
{
	static const char	compiled_on[] = __DATE__;	/* "Sep  5 2026" */
	static const char	compiled_at[] = __TIME__;	/* "20:13:52" */
	static char		text[sizeof "local:Sep-05-2026T20:13:52"];

	if (text[0] == '\0')
	{
		(void)memcpy(&text[0], "local:", 6U);
		(void)memcpy(&text[6], &compiled_on[0], 3U);
		text[9] = '-';
		text[10] = (compiled_on[4] == ' ') ? '0' : compiled_on[4];
		text[11] = compiled_on[5];
		text[12] = '-';
		(void)memcpy(&text[13], &compiled_on[7], 4U);
		text[17] = 'T';
		(void)memcpy(&text[18], &compiled_at[0], 8U);
		text[26] = '\0';
	}

	return text;
}

#endif
