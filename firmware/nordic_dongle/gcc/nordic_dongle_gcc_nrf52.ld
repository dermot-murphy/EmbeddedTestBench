/* Linker script for the bench dongle: application only.
 *
 * FLASH starts at 0x27000 because the S140 SoftDevice occupies the space below
 * it; the region stops short of 0x100000 to leave the dongle's factory
 * bootloader and its settings pages alone. RAM starts above the SoftDevice's
 * requirement for the configuration in config/sdk_config.h.
 *
 * These figures are repeated in ses/nordic_dongle_pca10059.emProject; if the
 * SoftDevice changes, both must change together.
 *
 * Traces to: BLE-DD-BUILD.
 */

SEARCH_DIR(.)
GROUP(-lgcc -lc -lnosys)

MEMORY
{
  FLASH (rx) : ORIGIN = 0x27000, LENGTH = 0xd9000
  RAM (rwx) :  ORIGIN = 0x20002ae8, LENGTH = 0x3d518
}

SECTIONS
{
  . = ALIGN(4);
  .mem_section_dummy_ram :
  {
  }
  .log_dynamic_data :
  {
    PROVIDE(__start_log_dynamic_data = .);
    KEEP(*(SORT(.log_dynamic_data*)))
    PROVIDE(__stop_log_dynamic_data = .);
  } > RAM
  .log_filter_data :
  {
    PROVIDE(__start_log_filter_data = .);
    KEEP(*(SORT(.log_filter_data*)))
    PROVIDE(__stop_log_filter_data = .);
  } > RAM
} INSERT AFTER .data;

SECTIONS
{
  .mem_section_dummy_rom :
  {
  }
  .sdh_ble_observers :
  {
    PROVIDE(__start_sdh_ble_observers = .);
    KEEP(*(SORT(.sdh_ble_observers*)))
    PROVIDE(__stop_sdh_ble_observers = .);
  } > FLASH
  .sdh_soc_observers :
  {
    PROVIDE(__start_sdh_soc_observers = .);
    KEEP(*(SORT(.sdh_soc_observers*)))
    PROVIDE(__stop_sdh_soc_observers = .);
  } > FLASH
  .sdh_req_observers :
  {
    PROVIDE(__start_sdh_req_observers = .);
    KEEP(*(SORT(.sdh_req_observers*)))
    PROVIDE(__stop_sdh_req_observers = .);
  } > FLASH
  .sdh_state_observers :
  {
    PROVIDE(__start_sdh_state_observers = .);
    KEEP(*(SORT(.sdh_state_observers*)))
    PROVIDE(__stop_sdh_state_observers = .);
  } > FLASH
  .sdh_stack_observers :
  {
    PROVIDE(__start_sdh_stack_observers = .);
    KEEP(*(SORT(.sdh_stack_observers*)))
    PROVIDE(__stop_sdh_stack_observers = .);
  } > FLASH
  .nrf_queue :
  {
    PROVIDE(__start_nrf_queue = .);
    KEEP(*(.nrf_queue))
    PROVIDE(__stop_nrf_queue = .);
  } > FLASH
  .nrf_balloc :
  {
    PROVIDE(__start_nrf_balloc = .);
    KEEP(*(.nrf_balloc))
    PROVIDE(__stop_nrf_balloc = .);
  } > FLASH
  .log_const_data :
  {
    PROVIDE(__start_log_const_data = .);
    KEEP(*(SORT(.log_const_data*)))
    PROVIDE(__stop_log_const_data = .);
  } > FLASH
  .log_backends :
  {
    PROVIDE(__start_log_backends = .);
    KEEP(*(SORT(.log_backends*)))
    PROVIDE(__stop_log_backends = .);
  } > FLASH
} INSERT AFTER .text

INCLUDE "nrf_common.ld"
