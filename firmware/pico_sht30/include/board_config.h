/**
 * @file board_config.h
 * @brief How the SHT30-D module is wired to the Pico 2.
 *
 * Default wiring (docs/pico_sht30/Pico_SHT30_Notes.md):
 *
 *   SHT30-D   Pico 2
 *   -------   -----------------------------
 *   VIN       3V3(OUT), pin 36
 *   GND       GND, pin 38
 *   SDA       GP4 = I2C0 SDA, pin 6
 *   SCL       GP5 = I2C0 SCL, pin 7
 *   ADDR      GND -> I2C address 0x44
 *
 * Frequency generator (docs/pico_sht30/Pico_SHT30_Notes.md):
 *
 *   CJMCU-1334     Pico 2
 *   ----------     -----------------------------
 *   VIN            3V3(OUT), pin 36
 *   GND            GND, pin 18
 *   BCLK           GP10, pin 14
 *   WSEL           GP11, pin 15
 *   DIN            GP12, pin 16
 *   MUTE           GP13, pin 17, with 10 kOhm to 3V3 so it is muted before
 *                  the firmware runs
 *   SCLK           3V3(OUT): selects the 50 to 100 kHz sample-rate range
 *   PLL, SF0, SF1  GND: audio mode, I2S format
 *
 *   Channel 3 (GPIO square wave): GP15, pin 20
 *
 * Each value may be overridden from the build (-DBOARD_I2C_SDA_PIN=...), so a
 * bench wired differently needs no source edit.
 *
 * Traces to: PICO-FR-010, PICO-DD-BOARD.
 */

#ifndef BOARD_CONFIG_H__
#define BOARD_CONFIG_H__

/** I2C controller instance: 0 for i2c0, 1 for i2c1. */
#ifndef BOARD_I2C_INSTANCE
#define BOARD_I2C_INSTANCE		0U
#endif

/** GPIO carrying SDA. GP4 is I2C0 SDA on the Pico 2. */
#ifndef BOARD_I2C_SDA_PIN
#define BOARD_I2C_SDA_PIN		4U
#endif

/** GPIO carrying SCL. GP5 is I2C0 SCL on the Pico 2. */
#ifndef BOARD_I2C_SCL_PIN
#define BOARD_I2C_SCL_PIN		5U
#endif

/** Bus rate in Hz. Standard mode: the module's pull-ups are sized for it. */
#ifndef BOARD_I2C_BAUD_HZ
#define BOARD_I2C_BAUD_HZ		100000UL
#endif

/** Longest a single I2C transfer may take before it is abandoned, in us.
 *  Six bytes at 100 kHz take about 0.6 ms; ten times that is generous. */
#ifndef BOARD_I2C_TIMEOUT_US
#define BOARD_I2C_TIMEOUT_US		10000UL
#endif

/** 7-bit address of the SHT30: 0x44 with ADDR low, 0x45 with ADDR high. */
#ifndef BOARD_SHT30_ADDRESS
#define BOARD_SHT30_ADDRESS		0x44U
#endif

/** System clock in Hz, the Pico 2's default. */
#ifndef BOARD_SYS_CLOCK_HZ
#define BOARD_SYS_CLOCK_HZ		150000000UL
#endif

/** PIO clock divider for the I2S stream. Integer, so that the bit clock has
 *  no fractional-divider jitter: 150 MHz / 12 / 2 = 6.25 MHz = 64 fs. */
#ifndef BOARD_DAC_PIO_DIVIDER
#define BOARD_DAC_PIO_DIVIDER		12U
#endif

/** GPIO carrying the I2S bit clock. The word select is the next GPIO up,
 *  because PIO side-set drives consecutive pins. */
#ifndef BOARD_DAC_BCK_PIN
#define BOARD_DAC_BCK_PIN		10U
#endif

/** GPIO carrying the I2S data. */
#ifndef BOARD_DAC_DATA_PIN
#define BOARD_DAC_DATA_PIN		12U
#endif

/** GPIO driving the DAC's MUTE input; high mutes. */
#ifndef BOARD_DAC_MUTE_PIN
#define BOARD_DAC_MUTE_PIN		13U
#endif

/** GPIO carrying generator channel 3. */
#ifndef BOARD_FGEN_GPIO_PIN
#define BOARD_FGEN_GPIO_PIN		15U
#endif

/** Board name. Not reported on the link since protocol 2.0. */
#define BOARD_NAME			"pico2"

#endif /* BOARD_CONFIG_H__ */
