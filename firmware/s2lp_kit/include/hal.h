/**
 * @file hal.h
 * @brief What the firmware needs from the board (#84).
 *
 * hal_l053.c implements it on the NUCLEO-L053R8; test/support/fake_hal.c
 * implements it for the unit tests, which run on the host.
 */

#ifndef HAL_H
#define HAL_H

#include <stdbool.h>
#include <stdint.h>

/** Clocks, pins, SPI, UART, timer and interrupts; the radio held in shutdown. */
void hal_init(void);

/** Drive the S2-LP's chip select: true selects it. */
void hal_spi_select(bool selected);

/** Exchange one byte with the selected SPI device. */
uint8_t hal_spi_transfer(uint8_t byte);

/** Drive the S2-LP's SDN pin: true holds the radio in shutdown. */
void hal_radio_shutdown(bool shutdown);

/** Allow or stop the interrupt from the radio's nIRQ pin (S2-LP GPIO3). */
void hal_radio_irq_enable(bool enable);

/** Wait at least this many microseconds. */
void hal_delay_us(uint32_t micros);

/** The board's microsecond timer, modulo 2^32. */
uint32_t hal_time_us(void);

/** Send these bytes to the host; returns when they are all queued or sent. */
void hal_uart_write(const char *text, uint32_t length);

/** The next byte from the host, or -1 when none has arrived. */
int32_t hal_uart_read(void);

/** Bytes from the host lost: the UART overran, or its queue was full. */
uint32_t hal_uart_overruns(void);

/** Mask interrupts; returns the state to give hal_irq_restore. */
uint32_t hal_irq_save(void);

/** Restore the interrupt state hal_irq_save returned. */
void hal_irq_restore(uint32_t state);

#endif /* HAL_H */
