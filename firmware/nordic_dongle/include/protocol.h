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
 * 1.8 - ``dfupkt`` answers with the piece size it wrote in, the number of
 *       pieces and the ATT MTU that write used (``piece=``, ``pieces=``,
 *       ``att_mtu=``), and ``+dfu`` reports the link's effective ATT MTU
 *       (``att_mtu=``) (#274).
 * 1.7 - ``dfucp`` and ``dfupkt`` carry a Secure DFU transfer to a target in its
 *       bootloader, and ``+dfu`` reports its DFU service (#244).
 * 1.6 - ``+sensor`` reports the manufacturer ID (``mfr=``) and, after an active
 *       scan, the scan-response payload (``sr=``); names up to 31 bytes (#241).
 * 1.5 - ``disconnect`` also stops a connection still being made, reported as
 *       ``+disc reason=cancelled``; ``connect`` during one answers ``err 7``,
 *       and a stack refusal carries its code as ``nrf=0x..`` (#251).
 * 1.1 - ``ver`` reports the firmware version and build date; ``dfu`` added.
 * 1.0 - first release.
 */
#define PROTOCOL_VERSION			"1.8"

/** How long a connection attempt listens for the sensor, by default and at
 *  most, in milliseconds. A sensor advertising every 9 s was missed by a
 *  5 s window more often than not (#39). */
#define PROTOCOL_CONNECT_DEFAULT_MS	15000U
#define PROTOCOL_CONNECT_MIN_MS		1000U
#define PROTOCOL_CONNECT_MAX_MS		60000U

/** How long cmd waits for the sensor's reply, by default and within bounds, in
 *  milliseconds (protocol 1.3). Some commands take longer than others. */
#define PROTOCOL_CMD_DEFAULT_MS		2000U
#define PROTOCOL_CMD_MIN_MS		100U
#define PROTOCOL_CMD_MAX_MS		60000U

/** Manufacturer and model reported by @c ver, in the host's identity fields. */
#define PROTOCOL_MANUFACTURER		"Nordic"
#define PROTOCOL_MODEL			"PCA10059"

/** Longest command line accepted, including the terminator: "cmd ", a
 *  PROTOCOL_MAX_PAYLOAD payload in hex, and " timeout=60000". */
#define PROTOCOL_MAX_LINE			512U

/** Longest reply or event line produced. The longest is cmd's "ok t_tx= t_rx=
 *  dt_us= interval_us= len= data=" with a PROTOCOL_MAX_PAYLOAD reply in hex, about
 *  600 characters; at 192 a reply over ~60 bytes was cut short. */
#define PROTOCOL_MAX_EVENT			640U

/** Sensors retained by a scan. Bounded because the firmware allocates nothing. */
#define PROTOCOL_MAX_SENSORS		16U

/** Longest advertising or scan-response payload: 31 bytes in legacy
 *  advertising. */
#define PROTOCOL_MAX_ADV_DATA		31U

/** Longest device name kept, with its terminator: PROTOCOL_MAX_ADV_DATA and
 *  one, since a name can fill an advertising payload. At 24 a sensor's
 *  25-character name lost its last two characters (#241). */
#define PROTOCOL_MAX_NAME			32U

/** Longest UART payload in one direction, in bytes before hex encoding: the
 *  ATT MTU of 247 less the 3-byte write header, the most one NUS write carries
 *  (#52). A sensor that negotiates a smaller MTU refuses a longer write. */
#define PROTOCOL_MAX_PAYLOAD		244U

/**
 * Command table: X(name, min_args, max_args, help)
 *
 * @c min_args and @c max_args count the tokens after the command word.
 *
 * All three tables take their entry macro as the argument @c X, so each user
 * passes a macro of its own and none is undefined afterwards (MISRA 20.5).
 */
#define PROTOCOL_COMMAND_TABLE(X) \
	X(ver,		0U, 0U, "identity: firmware version, build date, protocol, uptime") \
	X(scan,		1U, 5U, "scan start <ms> [name=<text>] [addr=<a>] [active=<0|1>] [rssi=<min>] | scan stop") \
	X(list,		0U, 0U, "sensors seen by the last scan, one event per sensor") \
	X(select,	1U, 1U, "select <index|addr> as the sensor for later commands") \
	X(selected,	0U, 0U, "report the selected sensor") \
	X(connect,	0U, 2U, "connect to the selected sensor, or to <addr>; timeout=<ms> bounds the attempt") \
	X(disconnect,	0U, 0U, "disconnect") \
	X(uart,		1U, 1U, "uart <hex> - write raw bytes to the sensor's UART service") \
	X(cmd,		1U, 2U, "cmd <hex> [timeout=<ms>] - write, await the reply, and report the round trip") \
	X(adv,		1U, 2U, "adv start [<addr>] | adv stop | adv stats") \
	X(time,		0U, 0U, "the dongle's microsecond timestamp now") \
	X(reset,	0U, 0U, "reset the dongle") \
	X(dfu,		0U, 0U, "reset into the bootloader, to accept a firmware update") \
	X(dfucp,	1U, 2U, "dfucp <hex> [timeout=<ms>] - write a target's DFU Control Point, report its response") \
	X(dfupkt,	1U, 1U, "dfupkt <hex> - write a target's DFU Packet characteristic, report the pieces written")

/**
 * Event table: X(name, help)
 *
 * Events are unsolicited. Every one begins with '+' and carries @c t=.
 */
#define PROTOCOL_EVENT_TABLE(X) \
	X(adv,	"+adv t= addr= type= rssi= pdu= ch= name= data= - one advertising report") \
	X(sensor, "+sensor t= idx= addr= type= rssi= name= - one entry of the scan result") \
	X(rx,	"+rx t= data= - bytes notified by the sensor's UART service") \
	X(conn,	"+conn t= addr= interval_us= latency= timeout_ms= - connected") \
	X(disc,	"+disc t= reason= - disconnected, with the HCI reason code") \
	X(scan,	"+scan t= state= - scanning started or stopped") \
	X(drop,	"+drop t= count= - events discarded because the USB queue was full") \
	X(dfu,	"+dfu t= state= error= att_mtu= - the link's DFU service: ready, incomplete, failed or error")

/**
 * Error table: X(symbol, code, text)
 *
 * A reply of "err <code> <text>" is a refusal by the firmware. The code is what
 * the host matches on; the text is for whoever is reading the log.
 */
#define PROTOCOL_ERROR_TABLE(X) \
	X(PROTO_ERR_NONE,	0U, "ok") \
	X(PROTO_ERR_UNKNOWN,	1U, "unknown command") \
	X(PROTO_ERR_ARGS,	2U, "wrong number of arguments") \
	X(PROTO_ERR_VALUE,	3U, "bad argument value") \
	X(PROTO_ERR_STATE,	4U, "not valid in this state") \
	X(PROTO_ERR_NO_SENSOR,	5U, "no sensor selected") \
	X(PROTO_ERR_NOT_CONN,	6U, "not connected") \
	X(PROTO_ERR_BUSY,	7U, "busy") \
	X(PROTO_ERR_TIMEOUT,	8U, "the sensor did not reply") \
	X(PROTO_ERR_TOO_LONG,	9U, "payload too long") \
	X(PROTO_ERR_BLE,	10U, "the BLE stack refused the request")

/** One enumerator of proto_error_t, from a row of PROTOCOL_ERROR_TABLE. */
#define PROTOCOL_ERROR_ENUMERATOR(symbol, code, text)	symbol = (code),

/** Error codes, generated from the table above. */
typedef enum
{
	PROTOCOL_ERROR_TABLE(PROTOCOL_ERROR_ENUMERATOR)
	PROTO_ERR_LIMIT
} proto_error_t;

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
