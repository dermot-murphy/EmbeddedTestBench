/**
 * @file startup.c
 * @brief Reset and the vector table for the STM32L053R8 (Cortex-M0+) (#84).
 *
 * Written for this firmware rather than taken from a vendor: copy .data from
 * flash, clear .bss, then run main. The vector table names only the handlers
 * the firmware uses; every other entry stops in startup_default_isr.
 */

#include <stdint.h>

#include "hal.h"

/** Symbols from stm32l053r8.ld. */
extern uint32_t _sidata;
extern uint32_t _sdata;
extern uint32_t _edata;
extern uint32_t _sbss;
extern uint32_t _ebss;
extern uint32_t _estack;

extern int main(void);

void startup_reset(void);
void startup_default_isr(void);

/** Vector table entries: 16 core, 32 device. */
#define STARTUP_VECTORS         (48U)

extern const uintptr_t startup_g_vectors[STARTUP_VECTORS];

void startup_reset(void)
{
	const uint32_t *source = &_sidata;
	uint32_t *target = &_sdata;

	while (target < &_edata)
	{
		*target = *source;
		target++;
		source++;
	}
	target = &_sbss;
	while (target < &_ebss)
	{
		*target = 0U;
		target++;
	}
	(void)main();
	for (;;)
	{
		/* main does not return. */
	}
}

void startup_default_isr(void)
{
	for (;;)
	{
		/* An exception or interrupt with no handler: stop here for the debugger. */
	}
}

/** The vector table, placed at the start of flash by the linker script. */
__attribute__((section(".isr_vector"), used))
const uintptr_t startup_g_vectors[STARTUP_VECTORS] =
{
	(uintptr_t)&_estack,
	(uintptr_t)&startup_reset,
	(uintptr_t)&startup_default_isr,    /* NMI */
	(uintptr_t)&startup_default_isr,    /* HardFault */
	0U, 0U, 0U, 0U, 0U, 0U, 0U,
	(uintptr_t)&startup_default_isr,    /* SVCall */
	0U, 0U,
	(uintptr_t)&startup_default_isr,    /* PendSV */
	(uintptr_t)&startup_default_isr,    /* SysTick */
	/* Device interrupts 0 .. 31. */
	(uintptr_t)&startup_default_isr,    /* 0  WWDG */
	(uintptr_t)&startup_default_isr,    /* 1  PVD */
	(uintptr_t)&startup_default_isr,    /* 2  RTC */
	(uintptr_t)&startup_default_isr,    /* 3  FLASH */
	(uintptr_t)&startup_default_isr,    /* 4  RCC_CRS */
	(uintptr_t)&hal_exti0_1_isr,        /* 5  EXTI0_1 */
	(uintptr_t)&startup_default_isr,    /* 6  EXTI2_3 */
	(uintptr_t)&startup_default_isr,    /* 7  EXTI4_15 */
	(uintptr_t)&startup_default_isr,    /* 8  TSC */
	(uintptr_t)&startup_default_isr,    /* 9  DMA1_Channel1 */
	(uintptr_t)&startup_default_isr,    /* 10 DMA1_Channel2_3 */
	(uintptr_t)&startup_default_isr,    /* 11 DMA1_Channel4_7 */
	(uintptr_t)&startup_default_isr,    /* 12 ADC1_COMP */
	(uintptr_t)&startup_default_isr,    /* 13 LPTIM1 */
	(uintptr_t)&startup_default_isr,    /* 14 reserved */
	(uintptr_t)&hal_tim2_isr,           /* 15 TIM2 */
	(uintptr_t)&startup_default_isr,    /* 16 reserved */
	(uintptr_t)&startup_default_isr,    /* 17 TIM6_DAC */
	(uintptr_t)&startup_default_isr,    /* 18 reserved */
	(uintptr_t)&startup_default_isr,    /* 19 reserved */
	(uintptr_t)&startup_default_isr,    /* 20 TIM21 */
	(uintptr_t)&startup_default_isr,    /* 21 reserved */
	(uintptr_t)&startup_default_isr,    /* 22 TIM22 */
	(uintptr_t)&startup_default_isr,    /* 23 I2C1 */
	(uintptr_t)&startup_default_isr,    /* 24 I2C2 */
	(uintptr_t)&startup_default_isr,    /* 25 SPI1 */
	(uintptr_t)&startup_default_isr,    /* 26 SPI2 */
	(uintptr_t)&startup_default_isr,    /* 27 USART1 */
	(uintptr_t)&hal_usart2_isr,         /* 28 USART2 */
	(uintptr_t)&startup_default_isr,    /* 29 RNG_LPUART1 */
	(uintptr_t)&startup_default_isr,    /* 30 LCD */
	(uintptr_t)&startup_default_isr,    /* 31 USB */
};
