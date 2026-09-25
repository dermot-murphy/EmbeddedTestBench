/**
 * @file protocol.h
 * @brief The host link contract: commands, events, error codes.
 *
 * This header is the single definition of the protocol. The firmware builds its
 * dispatch table from it, and the host driver's test suite parses it to confirm
 * that @c benchtools.instruments.nordic_dongle.constants still agrees with the
 * firmware. A command added on one side and forgotten on the other is a build
 * failure rather than a mystery at the bench.
 *
 * Form of the link (USB CDC ACM, 8N1, rate ignored):
 *
 *   host -> dongle   one command per line, LF terminated
 *   dongle -> host   one line per reply or event, LF terminated
 *                    replies begin with "ok" or "err"
 *                    unsolicited events begin with '+'
 *
 * Every event carries @c t=, a dongle timestamp in microseconds taken as close
 * to the radio event as the SoftDevice allows. That timestamp is the
 * measurement; the host's own arrival time is recorded beside it as a
 * cross-check, because USB adds a millisecond of jitter that would otherwise be
 * indistinguishable from the sensor's own behaviour.
 *
 * Traces to: BLE-FR-001, BLE-FR-002, BLE-DD-PROTOCOL.
 */

#ifndef PROTOCOL_H__
#define PROTOCOL_H__

#ifdef __cplusplus
extern "C" {
#endif

/** Protocol revision. Bumped when a command or event changes shape.
 *
 * 1.1 - ``ver`` reports the firmware version and build date; ``dfu`` added.
 * 1.0 - first release.
 */
#define PROTO_VERSION			"1.2"

/** How long a connection attempt listens for the sensor, by default and at
 *  most, in milliseconds. A sensor advertising every 9 s was missed by a
 *  5 s window more often than not (#39). */
#define PROTOCOL_CONNECT_DEFAULT_MS	15000U
#define PROTOCOL_CONNECT_MIN_MS		1000U
#define PROTOCOL_CONNECT_MAX_MS		60000U

/** Manufacturer and model reported by @c ver, in the host's identity fields. */
#define PROTO_MANUFACTURER		"Nordic"
#define PROTO_MODEL			"PCA10059"

/** Longest command line accepted, including the terminator. */
#define PROTO_MAX_LINE			256U

/** Longest event line produced. Sized for a 31-byte advertising payload in hex
 *  plus the fixed fields, with room to spare. */
#define PROTO_MAX_EVENT			192U

/** Sensors retained by a scan. Bounded because the firmware allocates nothing. */
#define PROTO_MAX_SENSORS		16U

/** Longest device name kept from an advertising payload. */
#define PROTO_MAX_NAME			24U

/** Longest UART payload in one direction, in bytes before hex encoding. */
#define PROTO_MAX_PAYLOAD		96U

/**
 * Command table: X(name, min_args, max_args, help)
 *
 * @c min_args and @c max_args count the tokens after the command word.
 */
#define PROTO_COMMAND_TABLE \
	X(ver,		0, 0, "identity: firmware version, build date, protocol, uptime") \
	X(scan,		1, 5, "scan start <ms> [name=<text>] [addr=<a>] [active=<0|1>] [rssi=<min>] | scan stop") \
	X(list,		0, 0, "sensors seen by the last scan, one event per sensor") \
	X(select,	1, 1, "select <index|addr> as the sensor for later commands") \
	X(selected,	0, 0, "report the selected sensor") \
	X(connect,	0, 2, "connect to the selected sensor, or to <addr>; timeout=<ms> bounds the attempt") \
	X(disconnect,	0, 0, "disconnect") \
	X(uart,		1, 1, "uart <hex> - write raw bytes to the sensor's UART service") \
	X(cmd,		1, 1, "cmd <hex> - write, await the reply, and report the round trip") \
	X(adv,		1, 2, "adv start [<addr>] | adv stop | adv stats") \
	X(time,		0, 0, "the dongle's microsecond timestamp now") \
	X(reset,	0, 0, "reset the dongle") \
	X(dfu,		0, 0, "reset into the bootloader, to accept a firmware update")

/**
 * Event table: X(name, help)
 *
 * Events are unsolicited. Every one begins with '+' and carries @c t=.
 */
#define PROTO_EVENT_TABLE \
	X(adv,	"+adv t= addr= type= rssi= pdu= ch= name= data= - one advertising report") \
	X(sensor, "+sensor t= idx= addr= type= rssi= name= - one entry of the scan result") \
	X(rx,	"+rx t= data= - bytes notified by the sensor's UART service") \
	X(conn,	"+conn t= addr= interval_us= latency= timeout_ms= - connected") \
	X(disc,	"+disc t= reason= - disconnected, with the HCI reason code") \
	X(scan,	"+scan t= state= - scanning started or stopped") \
	X(drop,	"+drop t= count= - events discarded because the USB queue was full")

/**
 * Error table: X(symbol, code, text)
 *
 * A reply of "err <code> <text>" is a refusal by the firmware. The code is what
 * the host matches on; the text is for whoever is reading the log.
 */
#define PROTO_ERROR_TABLE \
	X(PROTO_ERR_NONE,	0,  "ok") \
	X(PROTO_ERR_UNKNOWN,	1,  "unknown command") \
	X(PROTO_ERR_ARGS,	2,  "wrong number of arguments") \
	X(PROTO_ERR_VALUE,	3,  "bad argument value") \
	X(PROTO_ERR_STATE,	4,  "not valid in this state") \
	X(PROTO_ERR_NO_SENSOR,	5,  "no sensor selected") \
	X(PROTO_ERR_NOT_CONN,	6,  "not connected") \
	X(PROTO_ERR_BUSY,	7,  "busy") \
	X(PROTO_ERR_TIMEOUT,	8,  "the sensor did not reply") \
	X(PROTO_ERR_TOO_LONG,	9,  "payload too long") \
	X(PROTO_ERR_BLE,	10, "the BLE stack refused the request")

/** Error codes, generated from the table above. */
#define X(symbol, code, text)	symbol = (code),
typedef enum
{
	PROTO_ERROR_TABLE
	PROTO_ERR_LIMIT
} proto_error_t;
#undef X

/**
 * @brief The human-readable text for an error code.
 *
 * @param[in] error  Code to describe.
 * @return Static string; never NULL, so a caller cannot print a null pointer.
 */
const char * proto_error_text(proto_error_t error);

#ifdef __cplusplus
}
#endif

#endif /* PROTOCOL_H__ */
