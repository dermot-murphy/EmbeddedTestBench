/**
 * @file bootloader.h
 * @brief Entering the dongle's DFU bootloader on command.
 *
 * Without this, refreshing the firmware means someone walking to the bench and
 * pressing RESET. With it, the host can update a dongle it finds out of date -
 * which is the difference between a check the test runner can act on and a
 * check it can only complain about.
 *
 * Traces to: BLE-FR-013, BLE-DD-BOOTLOADER.
 */

#ifndef BOOTLOADER_H__
#define BOOTLOADER_H__

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief Reset into the bootloader, ready to accept a DFU package.
 *
 * Writes the magic value the bootloader looks for in the retained register and
 * resets. Does not return.
 */
void bootloader_enter_dfu(void);

#ifdef __cplusplus
}
#endif

#endif /* BOOTLOADER_H__ */
