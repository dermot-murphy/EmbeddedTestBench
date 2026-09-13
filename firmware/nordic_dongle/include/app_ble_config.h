/**
 * @file app_ble_config.h
 * @brief Constants shared by every module that touches the BLE stack.
 *
 * Kept out of protocol.h deliberately: that header is the contract with the
 * host and is parsed by the host's test suite, so it must contain nothing that
 * is merely an internal choice.
 *
 * Traces to: BLE-DD-SCANNER, BLE-DD-NUS.
 */

#ifndef APP_BLE_CONFIG_H__
#define APP_BLE_CONFIG_H__

/** Connection configuration tag, as passed to @c sd_ble_cfg_set. */
#define APP_BLE_CONN_CFG_TAG		1

/** Observer priorities. Lower runs earlier; the scanner is first so that an
 *  advertising report is timestamped before anything else looks at it. */
#define APP_BLE_OBSERVER_PRIO		3

/** ATT MTU requested. 247 carries a 244-byte UART payload in one packet, so a
 *  command and its reply are each one radio event and the measured round trip
 *  is not inflated by fragmentation. */
#define APP_BLE_MAX_ATT_MTU		247

#endif /* APP_BLE_CONFIG_H__ */
