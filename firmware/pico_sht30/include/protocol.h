/**
 * @file protocol.h
 * @brief The host link contract: commands, replies and error codes.
 *
 * This header is the single definition of the protocol. The firmware builds its
 * dispatch table from it, and the host driver's test suite parses it to confirm
 * that @c benchtools.instruments.pico_sht30.constants still agrees. A command
 * added on one side and forgotten on the other fails the build, not the bench.
 *
 * Form of the link (USB CDC ACM, 8N1, rate ignored), the same as the Nordic
 * dongle's so that one host session class fits both:
 *
 *   host -> pico     one command per line, LF (CR ignored)
 *   pico -> host     one line per reply, LF terminated
 *                    replies begin with "ok", "err <code> <text>", "ACK" or
 *                    "NAK"
 *                    informational lines (help only) begin with '#'
 *
 * The @c rd command reads one named value. Its reply is a whole line in the
 * form shared with the other bench devices, with no "ok" in front, and the
 * value may contain spaces:
 *
 *   rd name         ACK rd name = Pico 2 SHT30 Temperature Sensor
 *   rd copyright    ACK rd copyright = (c) 2026 Dermot Murphy
 *   rd version      ACK rd version = V1.00.0000
 *   rd sha          ACK rd sha = <short commit SHA, or unknown>
 *   rd temperature  ACK rd temperature = <degC, 2 dp>, e.g. 22.85 or -1.23
 *                   ACK rd temperature = Error   when no reading was possible
 *   rd <other>      NAK rd <other> = Error
 *
 * @c rd with no option, or more than one, is refused with "err 2" like any
 * other command with the wrong number of arguments.
 *
 * The remaining commands reply "ok", followed for @c status by one
 * @c key=value token:
 *
 *   status    ok status=0x<hhhh>
 *   sreset    ok
 *   ecureset  ok   (then the Pico reboots)
 *   bootsel   ok   (then the Pico reboots into its USB bootloader)
 *
 * Traces to: PICO-FR-001, PICO-FR-006, PICO-FR-007, PICO-FR-027,
 *            PICO-DD-PROTOCOL.
 */

#ifndef PROTOCOL_H__
#define PROTOCOL_H__

#ifdef __cplusplus
extern "C" {
#endif

/** Protocol revision. Bumped when a command or reply changes shape.
 *
 * 1.0 - first release.
 * 2.0 - rd command set replaces ver and temp; reset renamed ecureset (#131).
 */
#define PROTO_VERSION			"2.0"

/** Sensor part fitted. Not reported on the link since 2.0; the host driver
 *  still checks that it agrees. */
#define PROTO_SENSOR			"SHT30-DIS"

/** Longest command line accepted, including the terminator. */
#define PROTO_MAX_LINE			64U

/** Longest reply line produced, including the terminator. */
#define PROTO_MAX_REPLY			192U

/** Most tokens in a command line, the command word included. */
#define PROTO_MAX_TOKENS		4U

/**
 * Command table: X(name, min_args, max_args, help)
 *
 * @c min_args and @c max_args count the tokens after the command word.
 */
#define PROTO_COMMAND_TABLE \
	X(help,		0, 0, "list the commands") \
	X(rd,		1U, 1U, "read a value: name, copyright, version, sha or temperature") \
	X(status,	0, 0, "the SHT30 status register") \
	X(sreset,	0, 0, "soft-reset the SHT30") \
	X(ecureset,	0, 0, "reboot the Pico") \
	X(bootsel,	0, 0, "reboot into the USB bootloader, to accept a UF2")

/**
 * Error table: X(symbol, code, text)
 *
 * Sent as "err <code> <text>". The code is the contract; the text is for a
 * person reading a terminal.
 */
#define PROTO_ERROR_TABLE \
	X(PROTO_ERR_NONE,	0U, "ok") \
	X(PROTO_ERR_UNKNOWN,	1U, "unknown command") \
	X(PROTO_ERR_ARGS,	2U, "wrong number of arguments") \
	X(PROTO_ERR_TOO_LONG,	3U, "line too long") \
	X(PROTO_ERR_NO_SENSOR,	4U, "the sensor did not acknowledge") \
	X(PROTO_ERR_CRC,	5U, "the sensor checksum did not match") \
	X(PROTO_ERR_BUS,	6U, "I2C bus timeout")

/** Error codes, generated from the table above. */
#define X(symbol, code, text)	symbol = (code),
typedef enum
{
	PROTO_ERROR_TABLE
	PROTO_ERR_LIMIT
} proto_error_t;
#undef X

/**
 * @brief The human-readable text for @p error; never NULL.
 */
const char *proto_error_text(proto_error_t error);

#ifdef __cplusplus
}
#endif

#endif /* PROTOCOL_H__ */
