/**
 * @file protocol.h
 * @brief The host link contract: commands, replies and error codes.
 *
 * This header is the single definition of the protocol. The firmware builds its
 * dispatch table from it, and the host driver's test suite parses it to confirm
 * that @c benchtools.instruments.pico2_test_board.constants still agrees. A command
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
 *   rd name         ACK rd name = PICO2 Test Board
 *   rd copyright    ACK rd copyright = (c) 2026 Dermot Murphy
 *   rd version      ACK rd version = V1.00.0000
 *   rd sha          ACK rd sha = <short commit SHA, or unknown>
 *   rd temperature  ACK rd temperature = <degC, 2 dp>, e.g. 22.85 or -1.23
 *                   ACK rd temperature = Error   when no reading was possible
 *   rd led-red      ACK rd led-red = on|off      (also led-yellow, led-green)
 *   rd <other>      NAK rd <other> = Error
 *
 * The @c wr command writes one named value. For an LED (#328) the only
 * values are "on" and "off", and the reply carries the state read back from
 * the pin after the write; an LED takes no channel:
 *
 *   wr led-red on   ACK wr led-red = on          (also led-yellow, led-green)
 *   wr led-red off  ACK wr led-red = off
 *   wr led-red <v>  NAK wr led-red = Error       (a value other than on/off;
 *                                                 nothing changes)
 *   wr <other> ...  NAK wr <other> = Error       (an option that is neither an
 *                                                 LED nor a generator setting)
 *
 * @c rd with no option is refused with "err 2", as is a second token after
 * any option that takes no channel, and @c wr of an LED with other than an
 * option and a value.
 *
 * The frequency generator is controlled in the style of UDS: @c wr stores a
 * setting, @c rd reads it back and @c routine runs it. <ch> is 1, 2 or 3; a
 * command that omits it means channel 1, and the reply always names it. A
 * @c wr changes nothing being generated: it takes effect at the next start.
 *
 *   wr freq [<ch>] <hz>        ACK wr freq 1 = 1000.00     10 to 12k; k suffix
 *   wr freq2 [<ch>] <hz>       ACK wr freq2 1 = 2000.00    sine2's second sine
 *   wr wave [<ch>] <wave>      ACK wr wave 1 = sine
 *                              square sine triangle sawtooth sine2
 *   wr duty [<ch>] <percent>   ACK wr duty 1 = 25.00       1 to 99
 *   wr amp [<ch>] <percent>    ACK wr amp 1 = 50.00        0 to 100
 *   wr ratio [<ch>] <0..1>     ACK wr ratio 1 = 0.20       sine2's second amplitude
 *   wr cycles [<ch>] <count>   ACK wr cycles 1 = 50        0 runs until aborted
 *   rd <setting> [<ch>]        ACK rd freq 1 = 1000.00
 *   wr or rd refused           NAK wr freq 1 = Error
 *
 *   routine freq start [<ch>]    ACK routine freq start 1 = Running
 *                                NAK routine freq start 1 = Error
 *   routine freq abort [<ch>]    ACK routine freq abort 1 = Aborted
 *   routine freq abort           ACK routine freq abort = Aborted   (every channel)
 *   routine freq results <ch>    ACK routine freq results 1 = Running, sine, 999.98 Hz
 *                                ACK routine freq results 3 = Not Started
 *   routine freq results         one such line per channel
 *   routine all abort            ACK routine all abort = Aborted
 *
 * Channel 3 is a GPIO: square wave only, so @c wr @c wave of anything else, and
 * @c freq2, @c amp and @c ratio on it, are refused with NAK.
 *
 * The remaining commands reply "ok", followed for @c status by one
 * @c key=value token:
 *
 *   status    ok status=0x<hhhh>
 *   sreset    ok
 *   ecureset  ok   (then the Pico reboots)
 *   bootsel   ok   (then the Pico reboots into its USB bootloader)
 *
 * Traces to: PICO-FR-001, PICO-FR-006, PICO-FR-007, PICO-FR-008,
 *            PICO-FR-009, PICO-FR-027,
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
 * 2.1 - wr command and the led-red, led-yellow and led-green options (#328).
 * 2.2 - routine, and wr and rd of the frequency generator's settings (#202).
 */
#define PROTO_VERSION			"2.2"

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
	X(rd,		1U, 2U, "read a value: name, copyright, version, sha, temperature, led-<red|yellow|green>, freq, freq2, wave, duty, amp, ratio or cycles") \
	X(wr,		2U, 3U, "write a value: led-<red|yellow|green> on|off, or a generator setting: freq, freq2, wave, duty, amp, ratio or cycles") \
	X(routine,	2U, 3U, "routine freq start|abort|results [channel], or routine all abort") \
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
