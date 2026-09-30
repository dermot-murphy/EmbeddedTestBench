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

/** Board name reported by @c ver. */
#define BOARD_NAME			"pico2"

#endif /* BOARD_CONFIG_H__ */
