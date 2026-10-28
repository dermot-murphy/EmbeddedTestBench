/**
 * @file cmd_dfu.c
 * @brief The host commands that carry a DFU transfer: dfucp and dfupkt.
 *
 * Traces to: BLE-FR-121, BLE-DD-DFU.
 */

#include "cmd_dfu.h"

#include "nrf_error.h"

#include "cdc_acm.h"
#include "cmd_args.h"
#include "dfu_client.h"
#include "protocol.h"

/** How long a Packet write waits for a transmit buffer. */
#define CMD_DFU_PACKET_WAIT_MS		2000U

/**
 * @brief Report a refused command, as cmd_parser.c does.
 */
static void cmd_dfu_refuse(proto_error_t error)
{
	(void)cdc_acm_send_format("err %u %s", (unsigned)error, proto_error_text(error));
}

void cmd_dfu_control(char * tokens[], uint32_t count)
{
	uint8_t		request[DFU_CLIENT_MAX_WRITE];
	uint8_t		response[DFU_CLIENT_MAX_RESPONSE];
	char		hex[(DFU_CLIENT_MAX_RESPONSE * 2U) + 1U];
	uint16_t	response_len = 0U;
	uint32_t	timeout_ms   = PROTOCOL_CMD_DEFAULT_MS;
	bool		valid        = false;
	uint16_t	length = 0U;

	if ((count > 2U) && (!cmd_args_timeout(tokens[2], PROTOCOL_CMD_MIN_MS,
						       PROTOCOL_CMD_MAX_MS, &timeout_ms, &valid) || !valid))
	{
		cmd_dfu_refuse(PROTO_ERR_VALUE);
		return;
	}
	if (!cmd_args_decode_hex(tokens[1], request, sizeof(request), &length) || (length == 0U))
	{
		cmd_dfu_refuse(PROTO_ERR_TOO_LONG);
		return;
	}
	if (!dfu_client_is_ready())
	{
		cmd_dfu_refuse(PROTO_ERR_STATE);
		return;
	}
	if (dfu_client_control(request, length, timeout_ms,
			       response, &response_len) != NRF_SUCCESS)
	{
		cmd_dfu_refuse(PROTO_ERR_BLE);
		return;
	}
	if (response_len == 0U)
	{
		/* No response is a failure of the target, not an empty answer. */
		cmd_dfu_refuse(PROTO_ERR_TIMEOUT);
		return;
	}

	cmd_args_encode_hex(response, response_len, hex);
	(void)cdc_acm_send_format("ok len=%u data=%s", (unsigned)response_len, hex);
}

void cmd_dfu_packet(char * tokens[], uint32_t count)
{
	uint8_t		data[DFU_CLIENT_MAX_WRITE];
	uint16_t	length = 0U;
	uint16_t	piece  = 0U;
	uint16_t	pieces = 0U;
	uint32_t	error;

	(void)count;
	if (!cmd_args_decode_hex(tokens[1], data, sizeof(data), &length) || (length == 0U))
	{
		cmd_dfu_refuse(PROTO_ERR_TOO_LONG);
		return;
	}
	if (!dfu_client_is_ready())
	{
		cmd_dfu_refuse(PROTO_ERR_STATE);
		return;
	}
	error = dfu_client_packet(data, length, CMD_DFU_PACKET_WAIT_MS, &piece, &pieces);
	if (error == NRF_ERROR_RESOURCES)
	{
		cmd_dfu_refuse(PROTO_ERR_BUSY);
		return;
	}
	if (error == NRF_ERROR_TIMEOUT)
	{
		cmd_dfu_refuse(PROTO_ERR_TIMEOUT);
		return;
	}
	if (error != NRF_SUCCESS)
	{
		cmd_dfu_refuse(PROTO_ERR_BLE);
		return;
	}
	/* The piece size is what the link allowed: without it, receipts every
	 * 144 bytes were read as losses in #271. The ATT MTU is the one this
	 * write used, which can be larger than +dfu state=ready reported if the
	 * MTU exchange ended after it (protocol 1.8, #274). A refused write
	 * answers err as every command does; the host ends the transfer on it. */
	(void)cdc_acm_send_format("ok len=%u piece=%u pieces=%u att_mtu=%u", (unsigned)length,
				  (unsigned)piece, (unsigned)pieces,
				  (unsigned)(piece + DFU_CLIENT_ATT_OVERHEAD));
}
