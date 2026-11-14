/* Linker script for the ETB S2-LP kit firmware on the STM32L053R8 (#84).
 * 64 KB of flash at 0x08000000, 8 KB of RAM at 0x20000000.
 * Written for this firmware; no vendor script is used.
 */

ENTRY(startup_reset)

MEMORY
{
	FLASH (rx)  : ORIGIN = 0x08000000, LENGTH = 64K
	RAM   (rwx) : ORIGIN = 0x20000000, LENGTH = 8K
}

_estack = ORIGIN(RAM) + LENGTH(RAM);

SECTIONS
{
	.isr_vector :
	{
		KEEP(*(.isr_vector))
	} > FLASH

	.text :
	{
		*(.text*)
		*(.rodata*)
		. = ALIGN(4);
	} > FLASH

	_sidata = LOADADDR(.data);

	.data :
	{
		. = ALIGN(4);
		_sdata = .;
		*(.data*)
		. = ALIGN(4);
		_edata = .;
	} > RAM AT > FLASH

	.bss (NOLOAD) :
	{
		. = ALIGN(4);
		_sbss = .;
		*(.bss*)
		*(COMMON)
		. = ALIGN(4);
		_ebss = .;
	} > RAM

	/* At least 1 KB left for the stack. */
	ASSERT(_ebss + 1024 <= _estack, "RAM overflow: less than 1 KB left for the stack")

	/DISCARD/ :
	{
		*(.ARM.exidx*)
	}
}
