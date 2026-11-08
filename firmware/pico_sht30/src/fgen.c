/**
 * @file fgen.c
 * @brief The frequency generator. See fgen.h.
 *
 * Each DAC channel is a phase accumulator reading a one-cycle table. Tables
 * are built when a channel starts, from only the harmonics the DAC can
 * reproduce: its interpolation filter is flat to 0.45 fs (UDA1334ATS data
 * sheet, table 3), and a harmonic above that would alias. Sine and sine2 read
 * the sine table directly.
 *
 * fgen_render() runs in the DMA interrupt. It reads a channel's fields only
 * while the channel is @c Running; the main loop writes them only inside a
 * critical section or while it is not.
 *
 * Traces to: PICO-FR-080 .. PICO-FR-089, PICO-DD-FGEN.
 */

#include "fgen.h"

#include <math.h>
#include <stddef.h>

/** One-cycle table length. */
#define FGEN_TABLE_BITS		12U
#define FGEN_TABLE_SIZE		(1UL << FGEN_TABLE_BITS)
#define FGEN_TABLE_MASK		(FGEN_TABLE_SIZE - 1UL)
#define FGEN_QUARTER_TURN	(FGEN_TABLE_SIZE / 4UL)

/** Bits of the phase accumulator, and the bits below the table index. */
#define FGEN_PHASE_BITS		32U
#define FGEN_PHASE_FRAC_BITS	(FGEN_PHASE_BITS - FGEN_TABLE_BITS)

/** Interpolation fraction: 15 bits, so that a full-range table step times the
 *  fraction fits an int32_t. */
#define FGEN_INTERP_BITS	15U
#define FGEN_INTERP_ONE		(1L << FGEN_INTERP_BITS)
#define FGEN_INTERP_SHIFT	(FGEN_PHASE_FRAC_BITS - FGEN_INTERP_BITS)

/** Peak value of a table entry. */
#define FGEN_TABLE_PEAK		32767.0F

/** Gain for full amplitude, Q15. */
#define FGEN_GAIN_ONE		32768ULL

/** A table entry times a gain is Q30; a sample on the wire is Q31. */
#define FGEN_Q30_TO_Q31		2L

/** Highest frequency the DAC reproduces: 0.45 fs, in millihertz. */
#define FGEN_BAND_LIMIT_MHZ	((FGEN_SAMPLE_RATE_MHZ * 45ULL) / 100ULL)

/** Most harmonics summed, which bounds the time a start takes. Above this the
 *  harmonics of a low-frequency waveform are below -48 dB. */
#define FGEN_MAX_HARMONICS	256UL

#define FGEN_TWO_PI		6.283185307F

/** Time for the DAC to come out of its soft mute. */
#define FGEN_UNMUTE_SETTLE_MS	50U

/** How long the DAC stays unmuted after the last channel stops, so that the
 *  samples still in the buffers and in its filter are not cut off. */
#define FGEN_MUTE_HOLD_US	50000ULL

/** Settings a channel powers up with. */
#define FGEN_DEFAULT_FREQ_MHZ	1000000UL
#define FGEN_DEFAULT_FREQ2_MHZ	2000000UL
#define FGEN_DEFAULT_DUTY	50000UL
#define FGEN_DEFAULT_RATIO	500UL

/** PWM: the divider is fixed point with 4 fractional bits, 1.0 to 255.9375. */
#define FGEN_PWM_DIV_ONE	16ULL
#define FGEN_PWM_DIV_MAX	4095ULL
#define FGEN_PWM_COUNT_MAX	65536ULL
#define FGEN_MILLI_PER_UNIT	1000ULL
#define FGEN_PERCENT_FULL	100000ULL

/** How many channels have a DAC output. */
#define FGEN_DAC_CHANNELS	2UL

typedef struct
{
	uint32_t	values[FGEN_PARAM_COUNT];
} fgen_settings_t;

/** What a channel is generating. */
typedef struct
{
	volatile fgen_state_t	state;
	const int16_t		*table;
	uint32_t		phase;
	uint32_t		step;
	uint32_t		phase2;
	uint32_t		step2;
	int32_t			gain;
	int32_t			gain2;
	uint32_t		remaining;
	bool			finite;
	bool			two_tones;
	uint32_t		actual_mhz;
	fgen_wave_t		actual_wave;
} fgen_channel_t;

static fgen_settings_t	fgen_settings[FGEN_CHANNEL_COUNT];
static fgen_channel_t	fgen_channels[FGEN_CHANNEL_COUNT];
static int16_t		fgen_sine[FGEN_TABLE_SIZE];
static int16_t		fgen_tables[FGEN_DAC_CHANNELS][FGEN_TABLE_SIZE];
static float		fgen_scratch[FGEN_TABLE_SIZE];
static bool		fgen_muted;
static uint64_t		fgen_last_active_us;

/* The PWM interrupt reports the end of a finite run on the GPIO channel. */
static void fgen_gpio_done(void)
{
	fgen_channel_t	*channel = &fgen_channels[FGEN_CHANNEL_GPIO - 1U];

	if (channel->state == FGEN_STATE_RUNNING)
	{
		channel->state = FGEN_STATE_COMPLETE;
	}
}

static uint32_t fgen_step(uint32_t freq_mhz)
{
	uint64_t	rate = FGEN_SAMPLE_RATE_MHZ;

	return (uint32_t)((((uint64_t)freq_mhz << FGEN_PHASE_BITS) + (rate / 2ULL)) / rate);
}

static uint32_t fgen_step_to_mhz(uint32_t step)
{
	uint64_t	half = 1ULL << (FGEN_PHASE_BITS - 1U);

	return (uint32_t)((((uint64_t)step * FGEN_SAMPLE_RATE_MHZ) + half) >> FGEN_PHASE_BITS);
}

static int32_t fgen_lookup(const int16_t *table, uint32_t phase)
{
	uint32_t	index = phase >> FGEN_PHASE_FRAC_BITS;
	int32_t		fraction = (int32_t)((phase >> FGEN_INTERP_SHIFT) & ((uint32_t)FGEN_INTERP_ONE - 1UL));
	int32_t		first = (int32_t)table[index];
	int32_t		second = (int32_t)table[(index + 1UL) & FGEN_TABLE_MASK];

	return first + (((second - first) * fraction) / (int32_t)FGEN_INTERP_ONE);
}

uint32_t fgen_harmonics(uint32_t freq_mhz)
{
	uint64_t	count = FGEN_BAND_LIMIT_MHZ / (uint64_t)freq_mhz;

	if (count > (uint64_t)FGEN_MAX_HARMONICS)
	{
		count = (uint64_t)FGEN_MAX_HARMONICS;
	}
	return (uint32_t)count;
}

/* Add one harmonic to the scratch table: @p amplitude times the sine of
 * @p harmonic turns plus @p offset table steps. */
static void fgen_add_harmonic(uint32_t harmonic, float amplitude, uint32_t offset)
{
	uint32_t	index;

	for (index = 0UL; index < FGEN_TABLE_SIZE; index++)
	{
		uint32_t	position = ((index * harmonic) + offset) & FGEN_TABLE_MASK;

		fgen_scratch[index] += amplitude * (float)fgen_sine[position];
	}
}

/* One harmonic of a pulse wave high from phase 0 to duty D:
 * (1/n) sin(n pi D) cos(n (theta - pi D)). */
static void fgen_add_pulse_harmonic(uint32_t harmonic, uint32_t duty)
{
	uint64_t	turns = ((uint64_t)harmonic * (uint64_t)duty * (uint64_t)FGEN_TABLE_SIZE) /
				(FGEN_PERCENT_FULL * 2ULL);
	uint32_t	shift = (uint32_t)turns & FGEN_TABLE_MASK;
	float		amplitude = (float)fgen_sine[shift] / (float)harmonic;

	fgen_add_harmonic(harmonic, amplitude, (FGEN_QUARTER_TURN - shift) & FGEN_TABLE_MASK);
}

/* Normalise the scratch table to full scale, so that the overshoot of a
 * band-limited edge cannot clip, and store it in @p table. */
static void fgen_store_scratch(int16_t *table)
{
	float		peak = 0.0F;
	uint32_t	index;

	for (index = 0UL; index < FGEN_TABLE_SIZE; index++)
	{
		float	magnitude = fabsf(fgen_scratch[index]);

		if (magnitude > peak)
		{
			peak = magnitude;
		}
	}
	for (index = 0UL; index < FGEN_TABLE_SIZE; index++)
	{
		table[index] = (peak > 0.0F) ? (int16_t)((fgen_scratch[index] * FGEN_TABLE_PEAK) / peak) : (int16_t)0;
	}
}

static void fgen_build_table(int16_t *table, fgen_wave_t wave, uint32_t freq_mhz, uint32_t duty)
{
	uint32_t	limit = fgen_harmonics(freq_mhz);
	uint32_t	harmonic;
	uint32_t	index;

	for (index = 0UL; index < FGEN_TABLE_SIZE; index++)
	{
		fgen_scratch[index] = 0.0F;
	}
	for (harmonic = 1UL; harmonic <= limit; harmonic++)
	{
		float	reciprocal = 1.0F / (float)harmonic;

		if (wave == FGEN_WAVE_SQUARE)
		{
			fgen_add_pulse_harmonic(harmonic, duty);
		}
		else if (wave == FGEN_WAVE_SAWTOOTH)
		{
			/* Rising from the minimum at phase 0. */
			fgen_add_harmonic(harmonic, -reciprocal, 0UL);
		}
		else if ((harmonic & 1UL) != 0UL)
		{
			/* Triangle: odd harmonics, alternating in sign. */
			float	sign = ((harmonic & 2UL) != 0UL) ? -1.0F : 1.0F;

			fgen_add_harmonic(harmonic, sign * reciprocal * reciprocal, 0UL);
		}
		else
		{
			/* A triangle has no even harmonics. */
		}
	}
	fgen_store_scratch(table);
}

/* Stop a running channel, giving it @p state; any other channel is left alone. */
static void fgen_silence(fgen_channel_t *channel, fgen_state_t state)
{
	hal_critical_enter();
	if (channel->state == FGEN_STATE_RUNNING)
	{
		channel->state = state;
	}
	hal_critical_exit();
}

static void fgen_start_dac(uint32_t channel_number)
{
	const uint32_t	*values = fgen_settings[channel_number - 1U].values;
	fgen_channel_t	*channel = &fgen_channels[channel_number - 1U];
	fgen_wave_t	wave = (fgen_wave_t)values[FGEN_PARAM_WAVE];
	uint64_t	gain = ((uint64_t)values[FGEN_PARAM_AMP] * FGEN_GAIN_ONE) / FGEN_PERCENT_FULL;
	uint32_t	step = fgen_step(values[FGEN_PARAM_FREQ]);
	uint64_t	first = gain;
	uint64_t	second = 0ULL;
	const int16_t	*table = fgen_sine;

	fgen_silence(channel, FGEN_STATE_ABORTED);

	if (wave == FGEN_WAVE_SINE2)
	{
		uint64_t	denominator = FGEN_MILLI_PER_UNIT + (uint64_t)values[FGEN_PARAM_RATIO];

		first = (gain * FGEN_MILLI_PER_UNIT) / denominator;
		second = (gain * (uint64_t)values[FGEN_PARAM_RATIO]) / denominator;
	}
	else if (wave != FGEN_WAVE_SINE)
	{
		fgen_build_table(fgen_tables[channel_number - 1U], wave, values[FGEN_PARAM_FREQ],
				 values[FGEN_PARAM_DUTY]);
		table = fgen_tables[channel_number - 1U];
	}
	else
	{
		/* A sine reads the sine table. */
	}

	if (fgen_muted)
	{
		hal_dac_mute(false);
		fgen_muted = false;
		hal_delay_ms(FGEN_UNMUTE_SETTLE_MS);
	}

	hal_critical_enter();
	channel->table = table;
	channel->phase = 0UL;
	channel->step = step;
	channel->phase2 = 0UL;
	channel->step2 = fgen_step(values[FGEN_PARAM_FREQ2]);
	channel->gain = (int32_t)first;
	channel->gain2 = (int32_t)second;
	channel->remaining = values[FGEN_PARAM_CYCLES];
	channel->finite = (values[FGEN_PARAM_CYCLES] != 0UL);
	channel->two_tones = (wave == FGEN_WAVE_SINE2);
	channel->actual_mhz = fgen_step_to_mhz(step);
	channel->actual_wave = wave;
	channel->state = FGEN_STATE_RUNNING;
	hal_critical_exit();
}

static void fgen_start_gpio(void)
{
	const uint32_t		*values = fgen_settings[FGEN_CHANNEL_GPIO - 1U].values;
	fgen_channel_t		*channel = &fgen_channels[FGEN_CHANNEL_GPIO - 1U];
	hal_pwm_config_t	config;
	uint32_t		actual;

	fgen_silence(channel, FGEN_STATE_ABORTED);
	hal_pwm_stop();

	actual = fgen_pwm_config(values[FGEN_PARAM_FREQ], values[FGEN_PARAM_DUTY], &config);
	config.cycles = values[FGEN_PARAM_CYCLES];

	channel->finite = (config.cycles != 0UL);
	channel->actual_mhz = actual;
	channel->actual_wave = FGEN_WAVE_SQUARE;
	channel->state = FGEN_STATE_RUNNING;
	hal_pwm_start(&config, &fgen_gpio_done);
}

/* ------------------------------------------------------------------------ */
void fgen_init(void)
{
	uint32_t	index;

	for (index = 0UL; index < FGEN_CHANNEL_COUNT; index++)
	{
		uint32_t	*values = fgen_settings[index].values;

		values[FGEN_PARAM_FREQ] = FGEN_DEFAULT_FREQ_MHZ;
		values[FGEN_PARAM_FREQ2] = FGEN_DEFAULT_FREQ2_MHZ;
		values[FGEN_PARAM_DUTY] = FGEN_DEFAULT_DUTY;
		values[FGEN_PARAM_AMP] = FGEN_AMP_MAX;
		values[FGEN_PARAM_RATIO] = FGEN_DEFAULT_RATIO;
		values[FGEN_PARAM_CYCLES] = 0UL;
		values[FGEN_PARAM_WAVE] = (uint32_t)FGEN_WAVE_SQUARE;
		fgen_channels[index].state = FGEN_STATE_NOT_STARTED;
		fgen_channels[index].actual_mhz = 0UL;
		fgen_channels[index].actual_wave = FGEN_WAVE_SQUARE;
	}
	for (index = 0UL; index < FGEN_TABLE_SIZE; index++)
	{
		float	angle = (FGEN_TWO_PI * (float)index) / (float)FGEN_TABLE_SIZE;

		fgen_sine[index] = (int16_t)lroundf(sinf(angle) * FGEN_TABLE_PEAK);
	}
	fgen_muted = true;
	fgen_last_active_us = 0ULL;
	hal_dac_mute(true);
	hal_dac_start(&fgen_render);
}

bool fgen_channel_valid(uint32_t channel)
{
	return (channel >= 1UL) && (channel <= FGEN_CHANNEL_COUNT);
}

/* The range check for one value, and what the GPIO channel cannot do. */
static bool fgen_value_valid(uint32_t channel, fgen_param_t param, uint32_t value)
{
	bool	gpio = (channel == FGEN_CHANNEL_GPIO);
	bool	valid;

	switch (param)
	{
	case FGEN_PARAM_FREQ:
		valid = (value >= FGEN_FREQ_MIN_MHZ) && (value <= FGEN_FREQ_MAX_MHZ);
		break;
	case FGEN_PARAM_FREQ2:
		valid = !gpio && (value >= FGEN_FREQ_MIN_MHZ) && (value <= FGEN_FREQ_MAX_MHZ);
		break;
	case FGEN_PARAM_DUTY:
		valid = (value >= FGEN_DUTY_MIN) && (value <= FGEN_DUTY_MAX);
		break;
	case FGEN_PARAM_AMP:
		valid = !gpio && (value <= FGEN_AMP_MAX);
		break;
	case FGEN_PARAM_RATIO:
		valid = !gpio && (value <= FGEN_RATIO_MAX);
		break;
	case FGEN_PARAM_CYCLES:
		valid = true;
		break;
	case FGEN_PARAM_WAVE:
		valid = (value < (uint32_t)FGEN_WAVE_COUNT) &&
			(!gpio || (value == (uint32_t)FGEN_WAVE_SQUARE));
		break;
	case FGEN_PARAM_COUNT:
	default:
		valid = false;
		break;
	}
	return valid;
}

bool fgen_write(uint32_t channel, fgen_param_t param, uint32_t value)
{
	bool	result = fgen_channel_valid(channel) && fgen_value_valid(channel, param, value);

	if (result)
	{
		fgen_settings[channel - 1U].values[param] = value;
	}
	return result;
}

uint32_t fgen_read(uint32_t channel, fgen_param_t param)
{
	return fgen_settings[channel - 1U].values[param];
}

bool fgen_start(uint32_t channel)
{
	bool	result = fgen_channel_valid(channel);

	if (result)
	{
		const fgen_channel_t	*running = &fgen_channels[channel - 1U];

		if ((running->state == FGEN_STATE_RUNNING) && !running->finite)
		{
			result = false;
		}
		else if (channel == FGEN_CHANNEL_GPIO)
		{
			fgen_start_gpio();
		}
		else
		{
			fgen_start_dac(channel);
		}
	}
	return result;
}

void fgen_abort(uint32_t channel)
{
	if (fgen_channel_valid(channel))
	{
		fgen_silence(&fgen_channels[channel - 1U], FGEN_STATE_ABORTED);
		if (channel == FGEN_CHANNEL_GPIO)
		{
			hal_pwm_stop();
		}
	}
}

void fgen_abort_all(void)
{
	uint32_t	channel;

	for (channel = 1UL; channel <= FGEN_CHANNEL_COUNT; channel++)
	{
		fgen_abort(channel);
	}
}

fgen_state_t fgen_state(uint32_t channel)
{
	return fgen_channels[channel - 1U].state;
}

uint32_t fgen_actual_mhz(uint32_t channel)
{
	return fgen_channels[channel - 1U].actual_mhz;
}

fgen_wave_t fgen_actual_wave(uint32_t channel)
{
	return fgen_channels[channel - 1U].actual_wave;
}

void fgen_poll(void)
{
	uint64_t	now = hal_uptime_us();
	uint32_t	index;
	bool		active = false;

	for (index = 0UL; index < FGEN_DAC_CHANNELS; index++)
	{
		active = active || (fgen_channels[index].state == FGEN_STATE_RUNNING);
	}
	if (active)
	{
		fgen_last_active_us = now;
	}
	else if (!fgen_muted && ((now - fgen_last_active_us) >= FGEN_MUTE_HOLD_US))
	{
		hal_dac_mute(true);
		fgen_muted = true;
	}
	else
	{
		/* Muted already, or still holding. */
	}
}

/* The next sample of one DAC channel, as a Q30 value. */
static int32_t fgen_next_sample(fgen_channel_t *channel)
{
	int32_t	sample = 0;

	if (channel->state == FGEN_STATE_RUNNING)
	{
		uint32_t	next = channel->phase + channel->step;

		sample = fgen_lookup(channel->table, channel->phase) * channel->gain;
		if (channel->two_tones)
		{
			sample += fgen_lookup(fgen_sine, channel->phase2) * channel->gain2;
			channel->phase2 += channel->step2;
		}
		if (channel->finite && (next < channel->phase))
		{
			channel->remaining--;
			if (channel->remaining == 0UL)
			{
				channel->state = FGEN_STATE_COMPLETE;
			}
		}
		channel->phase = next;
	}
	return sample;
}

void fgen_render(int32_t *samples, uint32_t frames)
{
	uint32_t	frame;
	uint32_t	index;

	for (frame = 0UL; frame < frames; frame++)
	{
		for (index = 0UL; index < FGEN_DAC_CHANNELS; index++)
		{
			samples[(frame * FGEN_DAC_CHANNELS) + index] =
				fgen_next_sample(&fgen_channels[index]) * FGEN_Q30_TO_Q31;
		}
	}
}

uint32_t fgen_pwm_config(uint32_t freq_mhz, uint32_t duty, hal_pwm_config_t *config)
{
	/* Clock ticks per cycle, in sixteenths: the divider has 4 fractional bits. */
	uint64_t	clock = (uint64_t)BOARD_SYS_CLOCK_HZ * FGEN_PWM_DIV_ONE * FGEN_MILLI_PER_UNIT;
	uint64_t	total = clock / (uint64_t)freq_mhz;
	uint64_t	divider = (total + (FGEN_PWM_COUNT_MAX - 1ULL)) / FGEN_PWM_COUNT_MAX;
	uint64_t	count;
	uint64_t	level;

	if (divider < FGEN_PWM_DIV_ONE)
	{
		divider = FGEN_PWM_DIV_ONE;
	}
	else if (divider > FGEN_PWM_DIV_MAX)
	{
		divider = FGEN_PWM_DIV_MAX;
	}
	else
	{
		/* In range. */
	}

	count = (total + (divider / 2ULL)) / divider;
	if (count > FGEN_PWM_COUNT_MAX)
	{
		count = FGEN_PWM_COUNT_MAX;
	}
	level = ((count * (uint64_t)duty) + (FGEN_PERCENT_FULL / 2ULL)) / FGEN_PERCENT_FULL;

	config->divider = (uint32_t)divider;
	config->top = (uint32_t)(count - 1ULL);
	config->level = (uint32_t)level;
	config->cycles = 0UL;
	return (uint32_t)(((clock / divider) + (count / 2ULL)) / count);
}
