/**
 * @file sht30.h
 * @brief Sensirion SHT30-DIS temperature and humidity sensor, over I2C.
 *
 * The DollaTek "SHT30-D" module is a breakout board for this part: the sensor,
 * a decoupling capacitor, I2C pull-ups and the ADDR strap. Everything the
 * driver depends on comes from the Sensirion SHT3x-DIS datasheet
 * (docs/pico_sht30/References.md):
 *
 * * Commands are 16 bits, sent MSB first, with no CRC.
 * * Every 16-bit word the sensor sends is followed by a CRC-8: polynomial
 *   0x31, initial value 0xFF, no reflection, no final XOR. The datasheet's
 *   check value is CRC(0xBE 0xEF) = 0x92.
 * * Temperature: T[degC] = -45 + 175 * S_T / 65535.
 * * Humidity:    RH[%]   = 100 * S_RH / 65535.
 *
 * The driver uses the *no clock stretching* single-shot command and waits out
 * the conversion itself. With clock stretching the sensor holds SCL low for up
 * to 15 ms, which is legal I2C but needs the controller's timeout to know
 * about it; polling after a fixed wait keeps every transfer short.
 *
 * Arithmetic is integer only: results are in thousandths (milli-degrees
 * Celsius, milli-percent RH), rounded to nearest.
 *
 * Traces to: PICO-FR-020 .. PICO-FR-026, PICO-DD-SHT30.
 */

#ifndef SHT30_H__
#define SHT30_H__

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/** Single shot, high repeatability, clock stretching disabled. */
#define SHT30_CMD_MEASURE_HIGH		0x2400U
/** Read the 16-bit status register. */
#define SHT30_CMD_READ_STATUS		0xF32DU
/** Clear the alert and reset flags in the status register. */
#define SHT30_CMD_CLEAR_STATUS		0x3041U
/** Soft reset: reload calibration and return to idle. */
#define SHT30_CMD_SOFT_RESET		0x30A2U

/** Wait after a high-repeatability measurement command: datasheet max 15 ms,
 *  plus a millisecond for the delay function's granularity. */
#define SHT30_MEASURE_WAIT_MS		16U
/** Wait after a soft reset: datasheet max 1.5 ms, rounded up. */
#define SHT30_RESET_WAIT_MS		2U

/** CRC-8 parameters from the datasheet. */
#define SHT30_CRC_POLYNOMIAL		0x31U
#define SHT30_CRC_INIT			0xFFU

/** Bytes in a measurement frame: T msb, T lsb, CRC, RH msb, RH lsb, CRC. */
#define SHT30_FRAME_LENGTH		6U
/** Bytes in a status reply: msb, lsb, CRC. */
#define SHT30_WORD_LENGTH		3U

/** Status register bits (datasheet Table 17). */
#define SHT30_STATREG_ALERT_PENDING	0x8000U
#define SHT30_STATREG_HEATER_ON		0x2000U
#define SHT30_STATREG_RH_ALERT		0x0800U
#define SHT30_STATREG_T_ALERT		0x0400U
#define SHT30_STATREG_RESET_DETECTED	0x0010U
#define SHT30_STATREG_COMMAND_FAILED	0x0002U
#define SHT30_STATREG_WRITE_CRC_FAILED	0x0001U

/** Outcome of a driver call. */
typedef enum
{
	SHT30_STATUS_OK = 0,		/**< Success. */
	SHT30_STATUS_ERR_NACK,		/**< The sensor did not acknowledge. */
	SHT30_STATUS_ERR_TIMEOUT,	/**< The bus transfer timed out. */
	SHT30_STATUS_ERR_CRC,		/**< A received word failed its checksum. */
	SHT30_STATUS_ERR_PARAM		/**< A NULL pointer was passed. */
} sht30_status_t;

/** One measurement. */
typedef struct
{
	int32_t		temperature_mc;	/**< Temperature, milli-degrees Celsius. */
	int32_t		humidity_mpct;	/**< Relative humidity, milli-percent. */
	uint16_t	raw_temperature;	/**< S_T as received. */
	uint16_t	raw_humidity;		/**< S_RH as received. */
} sht30_reading_t;

/**
 * @brief The sensor's CRC-8 over @p length bytes of @p data.
 */
uint8_t sht30_crc8(const uint8_t *data, uint32_t length);

/**
 * @brief Convert a raw temperature word to milli-degrees Celsius.
 */
int32_t sht30_ticks_to_millicelsius(uint16_t ticks);

/**
 * @brief Convert a raw humidity word to milli-percent RH.
 */
int32_t sht30_ticks_to_millipercent(uint16_t ticks);

/**
 * @brief Check and convert a six-byte measurement frame.
 *
 * @p reading is written only on success, so a failed check can never leave a
 * half-updated value behind for a caller to report.
 */
sht30_status_t sht30_decode(const uint8_t *frame, sht30_reading_t *reading);

/**
 * @brief Take one high-repeatability measurement from the sensor at @p address.
 */
sht30_status_t sht30_measure(uint8_t address, sht30_reading_t *reading);

/**
 * @brief Read the status register of the sensor at @p address.
 */
sht30_status_t sht30_read_status(uint8_t address, uint16_t *status);

/**
 * @brief Soft-reset the sensor at @p address and wait for it to be ready.
 */
sht30_status_t sht30_soft_reset(uint8_t address);

#ifdef __cplusplus
}
#endif

#endif /* SHT30_H__ */
