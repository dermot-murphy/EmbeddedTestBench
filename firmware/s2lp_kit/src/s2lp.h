/**
 * @file s2lp.h
 * @brief S2-LP register, FIFO and command access over SPI (#84).
 *
 * Written from the S2-LP's SPI protocol: a header byte (0x00 write, 0x01
 * read, 0x80 command), then an address or a command code, then the data.
 * The radio returns its two status bytes while the header is clocked.
 * No ST source is used.
 */

#ifndef S2LP_H
#define S2LP_H

#include <stdint.h>

/** Address of the FIFO, for s2lp_read and s2lp_write. */
#define S2LP_FIFO               (0xFFU)

/** Registers this firmware uses. */
#define S2LP_GPIO3_CONF         (0x03U)
#define S2LP_IRQ_MASK3          (0x50U)
#define S2LP_RX_FIFO_STATUS     (0x90U)
#define S2LP_DEVICE_INFO0       (0xF1U)
#define S2LP_IRQ_STATUS3        (0xFAU)

/** Command strobes. */
#define S2LP_CMD_RX             (0x61U)
#define S2LP_CMD_READY          (0x62U)
#define S2LP_CMD_SABORT         (0x67U)
#define S2LP_CMD_FLUSHRXFIFO    (0x71U)

/** Interrupt bits, in the 32-bit word read from IRQ_STATUS3 .. 0. */
#define S2LP_IRQ_RX_DATA_READY  (1UL << 0)
#define S2LP_IRQ_RX_DATA_DISC   (1UL << 1)
#define S2LP_IRQ_CRC_ERROR      (1UL << 4)
#define S2LP_IRQ_RX_FIFO_ERROR  (1UL << 6)

/** GPIO_CONF value: nIRQ out, digital output, low power (mode 2). */
#define S2LP_GPIO_NIRQ          (0x02U)

/** Read count bytes from address on, into data. */
void s2lp_read(uint8_t address, uint8_t *data, uint32_t count);

/** Write count bytes from data to address on. */
void s2lp_write(uint8_t address, const uint8_t *data, uint32_t count);

/** Write a 32-bit value to four registers from address on, most significant first. */
void s2lp_write_word(uint8_t address, uint32_t value);

/** Send a command strobe. */
void s2lp_command(uint8_t command);

/** The two status bytes of the last transaction: MC_STATE1 high, MC_STATE0 low. */
uint16_t s2lp_status(void);

/** The 32-bit interrupt status; reading it clears it in the radio. */
uint32_t s2lp_irq_status(void);

#endif /* S2LP_H */
