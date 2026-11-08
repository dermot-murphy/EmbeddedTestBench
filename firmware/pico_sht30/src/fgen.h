/**
 * @file fgen.h
 * @brief The frequency generator: settings, routine state and sample synthesis.
 *
 * Three channels. Channels 1 and 2 are the left and right outputs of a
 * UDA1334A I2S DAC and generate every waveform. Channel 3 is a 3.3 V GPIO
 * driven by a PWM slice and generates only a square wave.
 *
 * Settings are written with fgen_write() and take effect at the next
 * fgen_start(): a @c wr while a channel runs changes nothing that is being
 * generated. All values are integers: frequencies in millihertz, duty and
 * amplitude in thousandths of a percent, the sine2 ratio in thousandths.
 *
 * This file is portable. The board is reached only through hal.h, so the unit
 * tests compile it unchanged.
 *
 * Traces to: PICO-FR-080 .. PICO-FR-089, PICO-DD-FGEN.
 */

#ifndef FGEN_H__
#define FGEN_H__

#include <stdbool.h>
#include <stdint.h>

#include "board_config.h"
#include "hal.h"

#ifdef __cplusplus
extern "C" {
#endif

/** Channels, numbered from 1 on the host link. */
#define FGEN_CHANNEL_COUNT		3U

/** The GPIO channel: square wave only. */
#define FGEN_CHANNEL_GPIO		3U

/** Lowest and highest frequency, in millihertz: 10 Hz and 12 kHz. */
#define FGEN_FREQ_MIN_MHZ		10000UL
#define FGEN_FREQ_MAX_MHZ		12000000UL

/** Duty range, in thousandths of a percent: 1 % to 99 %. */
#define FGEN_DUTY_MIN			1000UL
#define FGEN_DUTY_MAX			99000UL

/** Largest amplitude, in thousandths of a percent of full scale. */
#define FGEN_AMP_MAX			100000UL

/** Largest sine2 ratio, in thousandths. */
#define FGEN_RATIO_MAX			1000UL

/** DAC sample rate in millihertz: the system clock over the PIO divider, two
 *  PIO cycles per bit and 64 bits per frame. 97 656.25 Hz at 150 MHz. */
#define FGEN_SAMPLE_RATE_MHZ		(((uint64_t)BOARD_SYS_CLOCK_HZ * 1000ULL) / \
					 ((uint64_t)BOARD_DAC_PIO_DIVIDER * 2ULL * 64ULL))

/** What a channel generates. */
typedef enum
{
	FGEN_WAVE_SQUARE = 0,
	FGEN_WAVE_SINE,
	FGEN_WAVE_TRIANGLE,
	FGEN_WAVE_SAWTOOTH,
	FGEN_WAVE_SINE2,
	FGEN_WAVE_COUNT
} fgen_wave_t;

/** The settings @c wr changes and @c rd reports. */
typedef enum
{
	FGEN_PARAM_FREQ = 0,		/**< Millihertz. */
	FGEN_PARAM_FREQ2,		/**< sine2's second sine, millihertz. */
	FGEN_PARAM_DUTY,		/**< Square wave, thousandths of a percent. */
	FGEN_PARAM_AMP,			/**< Thousandths of a percent of full scale. */
	FGEN_PARAM_RATIO,		/**< sine2's second amplitude, thousandths. */
	FGEN_PARAM_CYCLES,		/**< Cycles to generate; 0 runs until aborted. */
	FGEN_PARAM_WAVE,		/**< An fgen_wave_t. */
	FGEN_PARAM_COUNT
} fgen_param_t;

/** Routine status, reported by @c routine @c freq @c results. */
typedef enum
{
	FGEN_STATE_NOT_STARTED = 0,
	FGEN_STATE_RUNNING,
	FGEN_STATE_ABORTED,
	FGEN_STATE_COMPLETE
} fgen_state_t;

/**
 * @brief Set the defaults, build the sine table and start the DAC stream.
 *
 * Call once, after hal_init(). Every channel is @c Not @c Started and silent.
 */
void fgen_init(void);

/**
 * @brief Store one setting for @p channel.
 * @return false, changing nothing, for a channel or value that is out of range
 *         or that the channel cannot generate.
 */
bool fgen_write(uint32_t channel, fgen_param_t param, uint32_t value);

/**
 * @brief Read back one setting of @p channel, which must be valid.
 */
uint32_t fgen_read(uint32_t channel, fgen_param_t param);

/** @return true if @p channel is a channel number. */
bool fgen_channel_valid(uint32_t channel);

/**
 * @brief Start @p channel with its current settings.
 *
 * A channel running a finite number of cycles restarts. A channel running
 * continuously is refused.
 *
 * @return false for an invalid channel or a refused restart.
 */
bool fgen_start(uint32_t channel);

/** @brief Stop @p channel if it is running. An invalid channel is ignored. */
void fgen_abort(uint32_t channel);

/** @brief Stop every channel. */
void fgen_abort_all(void);

/** @return The routine status of @p channel, which must be valid. */
fgen_state_t fgen_state(uint32_t channel);

/** @return The frequency last generated on @p channel, in millihertz. */
uint32_t fgen_actual_mhz(uint32_t channel);

/** @return The waveform last generated on @p channel. */
fgen_wave_t fgen_actual_wave(uint32_t channel);

/**
 * @brief Housekeeping from the main loop: mutes the DAC once it has been idle
 *        long enough for the last samples to have left it.
 */
void fgen_poll(void);

/**
 * @brief Fill @p samples with @p frames stereo frames, left then right.
 *
 * Called from the DMA interrupt on the target. Integer arithmetic only.
 */
void fgen_render(int32_t *samples, uint32_t frames);

/**
 * @brief Work out the PWM setting for a square wave.
 *
 * @param freq_mhz   Frequency, in millihertz.
 * @param duty       Duty, in thousandths of a percent.
 * @param config     Receives the divider, the wrap and the compare level.
 * @return The frequency that setting produces, in millihertz.
 */
uint32_t fgen_pwm_config(uint32_t freq_mhz, uint32_t duty, hal_pwm_config_t *config);

/**
 * @brief The number of harmonics a band-limited waveform at @p freq_mhz keeps.
 */
uint32_t fgen_harmonics(uint32_t freq_mhz);

#ifdef __cplusplus
}
#endif

#endif /* FGEN_H__ */
