/**
 * @file hal_pico.c
 * @brief The hardware seam on the Raspberry Pi Pico 2, over the Pico C SDK.
 *
 * This is the only file that includes SDK headers, and it is not compiled
 * into the host unit tests: test/support/fake_hal.c stands in for it there.
 *
 * MISRA C:2012 deviations confined to this file (docs/pico_sht30/
 * Pico_SHT30_Notes.md section 6, MISRA):
 *
 * * Rule 21.6 - the SDK's stdio_puts_raw() is the USB CDC output path.
 *   It is the SDK's own routine, not <stdio.h> formatting; no printf family
 *   function is used anywhere in the firmware.
 * * Dir 4.6 - SDK prototypes use the SDK's own "uint" and "int" types.
 *
 * Traces to: PICO-FR-010, PICO-FR-030, PICO-FR-031, PICO-DD-HAL.
 */

#include "hal.h"

#include "board_config.h"

#include <stddef.h>

#include "hardware/dma.h"
#include "hardware/gpio.h"
#include "hardware/i2c.h"
#include "hardware/irq.h"
#include "hardware/pio.h"
#include "hardware/pwm.h"
#include "hardware/sync.h"
#include "hardware/watchdog.h"
#include "pico/bootrom.h"
#include "pico/stdlib.h"
#include "pico/unique_id.h"

#if (BOARD_I2C_INSTANCE == 0U)
#define HAL_I2C_PORT		i2c0
#else
#define HAL_I2C_PORT		i2c1
#endif

/** Time allowed for the reply to leave over USB before a reboot drops it. */
#define HAL_REBOOT_DRAIN_MS	50U

/** Frames in one DMA buffer: 2.6 ms at the DAC's sample rate. */
#define HAL_DAC_FRAMES		256U

/** Words in one DMA buffer: two per stereo frame. */
#define HAL_DAC_WORDS		(HAL_DAC_FRAMES * 2U)

#define HAL_DAC_BUFFERS		2U

/** Bits in a word of the I2S stream, and what the loop counter is set to. */
#define HAL_DAC_WORD_BITS	32U
#define HAL_DAC_LOOP_COUNT	(HAL_DAC_WORD_BITS - 2U)

/** Side-set values: word select in bit 1, bit clock in bit 0. */
#define HAL_SIDE_BITS		2U
#define HAL_SIDE_00		0U
#define HAL_SIDE_01		1U
#define HAL_SIDE_10		2U
#define HAL_SIDE_11		3U

/** The I2S program's length, where its loops are, and where it is entered.
 *  Entry at the instruction that drops word select sends the left word first. */
#define HAL_I2S_LENGTH		8U
#define HAL_I2S_LOOP_RIGHT	0U
#define HAL_I2S_LOOP_LEFT	4U
#define HAL_I2S_ENTRY		3U
#define HAL_I2S_WRAP_TARGET	0U

#define HAL_PIO			pio0
#define HAL_PIO_SM		0U
#define HAL_PWM_FRAC_BITS	4U
#define HAL_PWM_FRAC_MASK	15U

/** The word-select pin follows the bit clock. */
#define HAL_DAC_WS_PIN		(BOARD_DAC_BCK_PIN + 1U)

static char			m_board_id_text[HAL_BOARD_ID_LENGTH];
static int32_t			m_dac_buffers[HAL_DAC_BUFFERS][HAL_DAC_WORDS];
static int			m_dac_channels[HAL_DAC_BUFFERS];
static hal_dac_render_t		m_dac_render;
static uint32_t			m_critical_state;

static uint			m_pwm_slice;
static volatile uint32_t	m_pwm_target;
static volatile uint32_t	m_pwm_done_count;
static hal_pwm_done_t		m_pwm_done;

static hal_status_t hal_from_sdk(int result, uint32_t expected)
{
	hal_status_t	status;

	if (result == PICO_ERROR_TIMEOUT)
	{
		status = HAL_STATUS_ERR_TIMEOUT;
	}
	else if ((result < 0) || ((uint32_t)result != expected))
	{
		status = HAL_STATUS_ERR_NACK;
	}
	else
	{
		status = HAL_STATUS_OK;
	}
	return status;
}

void hal_init(void)
{
	(void)i2c_init(HAL_I2C_PORT, (uint)BOARD_I2C_BAUD_HZ);
	gpio_set_function((uint)BOARD_I2C_SDA_PIN, GPIO_FUNC_I2C);
	gpio_set_function((uint)BOARD_I2C_SCL_PIN, GPIO_FUNC_I2C);
	/* The module carries its own pull-ups; the internal ones are enabled as
	 * well so that a bare sensor on a breadboard still sees a defined bus. */
	gpio_pull_up((uint)BOARD_I2C_SDA_PIN);
	gpio_pull_up((uint)BOARD_I2C_SCL_PIN);

	/* Muted from the first instruction that can reach the pin; the external
	 * pull-up covers the time before it. */
	gpio_init((uint)BOARD_DAC_MUTE_PIN);
	gpio_put((uint)BOARD_DAC_MUTE_PIN, true);
	gpio_set_dir((uint)BOARD_DAC_MUTE_PIN, GPIO_OUT);

	gpio_init((uint)BOARD_FGEN_GPIO_PIN);
	gpio_put((uint)BOARD_FGEN_GPIO_PIN, false);
	gpio_set_dir((uint)BOARD_FGEN_GPIO_PIN, GPIO_OUT);
	m_pwm_slice = pwm_gpio_to_slice_num((uint)BOARD_FGEN_GPIO_PIN);

	pico_get_unique_board_id_string(m_board_id_text, (uint)HAL_BOARD_ID_LENGTH);
}

void hal_critical_enter(void)
{
	m_critical_state = save_and_disable_interrupts();
}

void hal_critical_exit(void)
{
	restore_interrupts(m_critical_state);
}

/* Refill the buffer DMA has just finished and rewind its channel, ready for
 * the chain to come back to it. */
static void hal_dac_irq(void)
{
	uint32_t	index;

	for (index = 0U; index < HAL_DAC_BUFFERS; index++)
	{
		uint	channel = (uint)m_dac_channels[index];

		if (dma_channel_get_irq0_status(channel))
		{
			dma_channel_acknowledge_irq0(channel);
			m_dac_render(m_dac_buffers[index], HAL_DAC_FRAMES);
			dma_channel_set_read_addr(channel, m_dac_buffers[index], false);
		}
	}
}

/* Each bit takes two PIO cycles. Word select changes on the falling edge of
 * the bit clock, one bit before the word it selects, as I2S requires. */
static void hal_dac_load_program(void)
{
	static uint16_t	program[HAL_I2S_LENGTH];
	pio_program_t	description;
	pio_sm_config	config = pio_get_default_sm_config();

	program[0] = (uint16_t)(pio_encode_out(pio_pins, 1U) | pio_encode_sideset(HAL_SIDE_BITS, HAL_SIDE_10));
	program[1] = (uint16_t)(pio_encode_jmp_x_dec(HAL_I2S_LOOP_RIGHT) | pio_encode_sideset(HAL_SIDE_BITS, HAL_SIDE_11));
	program[2] = (uint16_t)(pio_encode_out(pio_pins, 1U) | pio_encode_sideset(HAL_SIDE_BITS, HAL_SIDE_00));
	program[3] = (uint16_t)(pio_encode_set(pio_x, HAL_DAC_LOOP_COUNT) | pio_encode_sideset(HAL_SIDE_BITS, HAL_SIDE_01));
	program[4] = (uint16_t)(pio_encode_out(pio_pins, 1U) | pio_encode_sideset(HAL_SIDE_BITS, HAL_SIDE_00));
	program[5] = (uint16_t)(pio_encode_jmp_x_dec(HAL_I2S_LOOP_LEFT) | pio_encode_sideset(HAL_SIDE_BITS, HAL_SIDE_01));
	program[6] = (uint16_t)(pio_encode_out(pio_pins, 1U) | pio_encode_sideset(HAL_SIDE_BITS, HAL_SIDE_10));
	program[7] = (uint16_t)(pio_encode_set(pio_x, HAL_DAC_LOOP_COUNT) | pio_encode_sideset(HAL_SIDE_BITS, HAL_SIDE_11));

	description.instructions = program;
	description.length = (uint8_t)HAL_I2S_LENGTH;
	description.origin = 0;
	(void)pio_add_program_at_offset(HAL_PIO, &description, 0U);

	sm_config_set_wrap(&config, HAL_I2S_WRAP_TARGET, HAL_I2S_LENGTH - 1U);
	sm_config_set_sideset(&config, HAL_SIDE_BITS, false, false);
	sm_config_set_sideset_pins(&config, (uint)BOARD_DAC_BCK_PIN);
	sm_config_set_out_pins(&config, (uint)BOARD_DAC_DATA_PIN, 1U);
	sm_config_set_out_shift(&config, false, true, HAL_DAC_WORD_BITS);
	sm_config_set_fifo_join(&config, PIO_FIFO_JOIN_TX);
	sm_config_set_clkdiv_int_frac8(&config, (uint32_t)BOARD_DAC_PIO_DIVIDER, 0U);

	pio_gpio_init(HAL_PIO, (uint)BOARD_DAC_BCK_PIN);
	pio_gpio_init(HAL_PIO, (uint)HAL_DAC_WS_PIN);
	pio_gpio_init(HAL_PIO, (uint)BOARD_DAC_DATA_PIN);
	(void)pio_sm_set_consecutive_pindirs(HAL_PIO, HAL_PIO_SM, (uint)BOARD_DAC_BCK_PIN, HAL_SIDE_BITS, true);
	(void)pio_sm_set_consecutive_pindirs(HAL_PIO, HAL_PIO_SM, (uint)BOARD_DAC_DATA_PIN, 1U, true);
	(void)pio_sm_init(HAL_PIO, HAL_PIO_SM, HAL_I2S_ENTRY, &config);
}

void hal_dac_start(hal_dac_render_t render)
{
	uint32_t	index;

	m_dac_render = render;
	hal_dac_load_program();

	for (index = 0U; index < HAL_DAC_BUFFERS; index++)
	{
		m_dac_channels[index] = dma_claim_unused_channel(true);
	}
	for (index = 0U; index < HAL_DAC_BUFFERS; index++)
	{
		uint			channel = (uint)m_dac_channels[index];
		dma_channel_config	config = dma_channel_get_default_config(channel);

		channel_config_set_transfer_data_size(&config, DMA_SIZE_32);
		channel_config_set_read_increment(&config, true);
		channel_config_set_write_increment(&config, false);
		channel_config_set_dreq(&config, pio_get_dreq(HAL_PIO, HAL_PIO_SM, true));
		channel_config_set_chain_to(&config,
					    (uint)m_dac_channels[(index + 1U) % HAL_DAC_BUFFERS]);
		dma_channel_configure(channel, &config, &HAL_PIO->txf[HAL_PIO_SM],
				      m_dac_buffers[index], HAL_DAC_WORDS, false);
		dma_channel_set_irq0_enabled(channel, true);
	}

	irq_set_exclusive_handler(DMA_IRQ_0, &hal_dac_irq);
	irq_set_enabled(DMA_IRQ_0, true);
	dma_channel_start((uint)m_dac_channels[0]);
	pio_sm_set_enabled(HAL_PIO, HAL_PIO_SM, true);
}

void hal_dac_mute(bool mute)
{
	gpio_put((uint)BOARD_DAC_MUTE_PIN, mute);
}

/* Leave the pin an ordinary output, driven low. */
static void hal_pwm_release_pin(void)
{
	pwm_set_enabled(m_pwm_slice, false);
	pwm_set_irq_enabled(m_pwm_slice, false);
	gpio_put((uint)BOARD_FGEN_GPIO_PIN, false);
	gpio_set_function((uint)BOARD_FGEN_GPIO_PIN, GPIO_FUNC_SIO);
}

/* A run of N cycles: the compare level written during cycle N takes effect at
 * the wrap that ends it, so cycle N + 1 starts low and the pin is released at
 * that wrap with no extra pulse. */
static void hal_pwm_irq(void)
{
	pwm_clear_irq(m_pwm_slice);
	m_pwm_done_count++;
	if (m_pwm_done_count >= m_pwm_target)
	{
		hal_pwm_release_pin();
		if (m_pwm_done != NULL)
		{
			m_pwm_done();
		}
	}
	else if ((m_pwm_done_count + 1U) == m_pwm_target)
	{
		pwm_set_gpio_level((uint)BOARD_FGEN_GPIO_PIN, 0U);
	}
	else
	{
		/* Mid-run. */
	}
}

void hal_pwm_start(const hal_pwm_config_t *config, hal_pwm_done_t done)
{
	static bool	irq_installed = false;

	hal_pwm_release_pin();
	if (!irq_installed)
	{
		irq_set_exclusive_handler(PWM_DEFAULT_IRQ_NUM(), &hal_pwm_irq);
		irq_set_enabled(PWM_DEFAULT_IRQ_NUM(), true);
		irq_installed = true;
	}

	m_pwm_done = done;
	m_pwm_target = config->cycles;
	m_pwm_done_count = 0U;

	pwm_set_clkdiv_int_frac4(m_pwm_slice, (uint8_t)(config->divider >> HAL_PWM_FRAC_BITS),
				 (uint8_t)(config->divider & HAL_PWM_FRAC_MASK));
	pwm_set_wrap(m_pwm_slice, (uint16_t)config->top);
	pwm_set_gpio_level((uint)BOARD_FGEN_GPIO_PIN, (uint16_t)config->level);
	pwm_set_counter(m_pwm_slice, 0U);
	gpio_set_function((uint)BOARD_FGEN_GPIO_PIN, GPIO_FUNC_PWM);

	if (config->cycles != 0U)
	{
		pwm_clear_irq(m_pwm_slice);
		pwm_set_irq_enabled(m_pwm_slice, true);
	}
	pwm_set_enabled(m_pwm_slice, true);
	if (config->cycles == 1U)
	{
		pwm_set_gpio_level((uint)BOARD_FGEN_GPIO_PIN, 0U);
	}
}

void hal_pwm_stop(void)
{
	hal_pwm_release_pin();
}

hal_status_t hal_i2c_write(uint8_t address, const uint8_t *data, uint32_t length)
{
	int	result = i2c_write_timeout_us(HAL_I2C_PORT, address, data, (size_t)length,
					      false, (uint)BOARD_I2C_TIMEOUT_US);

	return hal_from_sdk(result, length);
}

hal_status_t hal_i2c_read(uint8_t address, uint8_t *data, uint32_t length)
{
	int	result = i2c_read_timeout_us(HAL_I2C_PORT, address, data, (size_t)length,
					     false, (uint)BOARD_I2C_TIMEOUT_US);

	return hal_from_sdk(result, length);
}

void hal_delay_ms(uint32_t milliseconds)
{
	sleep_ms(milliseconds);
}

void hal_write_line(const char *line)
{
	/* stdio_puts_raw appends '\n' and does no CRLF translation. */
	(void)stdio_puts_raw(line);
}

const char *hal_board_id(void)
{
	return m_board_id_text;
}

uint64_t hal_uptime_us(void)
{
	return time_us_64();
}

void hal_reboot(void)
{
	stdio_flush();
	sleep_ms(HAL_REBOOT_DRAIN_MS);
	watchdog_reboot(0U, 0U, 0U);
	for (;;)
	{
		tight_loop_contents();
	}
}

void hal_reboot_to_bootloader(void)
{
	stdio_flush();
	sleep_ms(HAL_REBOOT_DRAIN_MS);
	reset_usb_boot(0U, 0U);
}
