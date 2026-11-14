/**
 * @file hal_l053.c
 * @brief hal.h on the NUCLEO-L053R8 with the S2-LP board (#84).
 *
 * Wiring, as the S2-LP DK boards are fitted to the Nucleo's Arduino headers:
 *
 *   SPI1   SCK PB3, MISO PA6, MOSI PA7 (AF0), mode 0, 8 MHz
 *   PA1    S2-LP chip select (low selects)
 *   PB4    board EEPROM chip select, held high (deselected)
 *   PA8    S2-LP SDN (high holds the radio in shutdown)
 *   PC0    S2-LP GPIO3, its nIRQ: EXTI line 0, falling edge
 *   PC7    TCXO enable, driven high
 *   PA2/3  USART2 TX/RX (AF4) to the ST-LINK's virtual COM port, 115200 8N1
 *   PA5    the Nucleo's green LED: on while receiving
 *
 * The core runs at 32 MHz from HSI16 through the PLL (x4, /2); TIM2 counts
 * microseconds.
 */

#include "hal.h"

#include "l053.h"
#include "rx.h"

/** Pin modes. */
#define HAL_MODE_INPUT          (0U)
#define HAL_MODE_OUTPUT         (1U)
#define HAL_MODE_AF             (2U)

/** Bytes of host input held while the main loop is busy. */
#define HAL_RX_SIZE             (128U)

/** USART2 divider for 115200 baud from 32 MHz. */
#define HAL_USART_BRR_115200    (278U)

/** Most passes of the nIRQ handler while the line stays low. */
#define HAL_IRQ_PASSES          (4U)

static volatile uint32_t m_time_high;
static volatile uint8_t m_rx_bytes[HAL_RX_SIZE];
static volatile uint32_t m_rx_head;
static volatile uint32_t m_rx_tail;

static void hal_pin_mode(uint32_t base, uint32_t pin, uint32_t mode)
{
	uint32_t moder = L053_GPIO_MODER(base);

	moder &= ~(3UL << (2U * pin));
	moder |= (uint32_t)mode << (2U * pin);
	L053_GPIO_MODER(base) = moder;
}

static void hal_pin_af(uint32_t base, uint32_t pin, uint32_t function)
{
	uint32_t afrl = L053_GPIO_AFRL(base);

	afrl &= ~(0xFUL << (4U * pin));
	afrl |= function << (4U * pin);
	L053_GPIO_AFRL(base) = afrl;
	L053_GPIO_OSPEEDR(base) |= 3UL << (2U * pin);
	hal_pin_mode(base, pin, HAL_MODE_AF);
}

static void hal_pin_write(uint32_t base, uint32_t pin, bool high)
{
	L053_GPIO_BSRR(base) = high ? (1UL << pin) : (1UL << (pin + 16U));
}

static void hal_nvic_enable(uint32_t irq, bool enable)
{
	if (enable)
	{
		L053_REG(L053_NVIC_ICPR) = 1UL << irq;
		L053_REG(L053_NVIC_ISER) = 1UL << irq;
	}
	else
	{
		L053_REG(L053_NVIC_ICER) = 1UL << irq;
	}
}

/**
 * @brief 32 MHz from HSI16: voltage range 1, one flash wait state, PLL x4 /2.
 */
static void hal_clock_init(void)
{
	L053_RCC_APB1ENR |= L053_RCC_APB1ENR_PWR;
	L053_PWR_CR = (L053_PWR_CR & ~L053_PWR_CR_VOS_MASK) | L053_PWR_CR_VOS_RANGE1;
	while ((L053_PWR_CSR & L053_PWR_CSR_VOSF) != 0U)
	{
		/* Wait for the regulator. */
	}
	L053_RCC_CR = (L053_RCC_CR & ~L053_RCC_CR_HSIDIVEN) | L053_RCC_CR_HSION;
	while ((L053_RCC_CR & L053_RCC_CR_HSIRDY) == 0U)
	{
		/* Wait for HSI16. */
	}
	L053_FLASH_ACR |= L053_FLASH_ACR_LATENCY;
	while ((L053_FLASH_ACR & L053_FLASH_ACR_LATENCY) == 0U)
	{
		/* Wait for the wait state to take. */
	}
	L053_RCC_CFGR = (L053_RCC_CFGR & ~(L053_RCC_CFGR_PLLSRC | L053_RCC_CFGR_PLLMUL_MASK
		| L053_RCC_CFGR_PLLDIV_MASK)) | L053_RCC_CFGR_PLLMUL4 | L053_RCC_CFGR_PLLDIV2;
	L053_RCC_CR |= L053_RCC_CR_PLLON;
	while ((L053_RCC_CR & L053_RCC_CR_PLLRDY) == 0U)
	{
		/* Wait for the PLL. */
	}
	L053_RCC_CFGR = (L053_RCC_CFGR & ~L053_RCC_CFGR_SW_MASK) | L053_RCC_CFGR_SW_PLL;
	while ((L053_RCC_CFGR & L053_RCC_CFGR_SWS_MASK) != L053_RCC_CFGR_SWS_PLL)
	{
		/* Wait for the switch. */
	}
}

static void hal_pins_init(void)
{
	L053_RCC_IOPENR |= L053_RCC_IOPENR_GPIOA | L053_RCC_IOPENR_GPIOB | L053_RCC_IOPENR_GPIOC;

	hal_pin_write(L053_GPIOA_BASE, 1U, true);       /* S2-LP CS deselected */
	hal_pin_mode(L053_GPIOA_BASE, 1U, HAL_MODE_OUTPUT);
	hal_pin_write(L053_GPIOB_BASE, 4U, true);       /* EEPROM CS deselected */
	hal_pin_mode(L053_GPIOB_BASE, 4U, HAL_MODE_OUTPUT);
	hal_pin_write(L053_GPIOA_BASE, 8U, true);       /* SDN: radio shut down */
	hal_pin_mode(L053_GPIOA_BASE, 8U, HAL_MODE_OUTPUT);
	hal_pin_write(L053_GPIOC_BASE, 7U, true);       /* TCXO on */
	hal_pin_mode(L053_GPIOC_BASE, 7U, HAL_MODE_OUTPUT);
	hal_pin_write(L053_GPIOA_BASE, 5U, false);      /* LED off */
	hal_pin_mode(L053_GPIOA_BASE, 5U, HAL_MODE_OUTPUT);

	hal_pin_af(L053_GPIOB_BASE, 3U, 0U);            /* SPI1 SCK */
	hal_pin_af(L053_GPIOA_BASE, 6U, 0U);            /* SPI1 MISO */
	hal_pin_af(L053_GPIOA_BASE, 7U, 0U);            /* SPI1 MOSI */
	hal_pin_af(L053_GPIOA_BASE, 2U, 4U);            /* USART2 TX */
	hal_pin_af(L053_GPIOA_BASE, 3U, 4U);            /* USART2 RX */

	hal_pin_mode(L053_GPIOC_BASE, 0U, HAL_MODE_INPUT);   /* nIRQ */
	L053_GPIO_PUPDR(L053_GPIOC_BASE) = (L053_GPIO_PUPDR(L053_GPIOC_BASE) & ~3UL) | 1UL;
}

static void hal_peripherals_init(void)
{
	L053_RCC_APB2ENR |= L053_RCC_APB2ENR_SPI1 | L053_RCC_APB2ENR_SYSCFG;
	L053_RCC_APB1ENR |= L053_RCC_APB1ENR_USART2 | L053_RCC_APB1ENR_TIM2;

	L053_SPI1_CR1 = L053_SPI_CR1_MSTR | L053_SPI_CR1_BR_DIV4 | L053_SPI_CR1_SSM
		| L053_SPI_CR1_SSI;
	L053_SPI1_CR1 |= L053_SPI_CR1_SPE;

	L053_USART2_BRR = HAL_USART_BRR_115200;
	L053_USART2_CR1 = L053_USART_CR1_TE | L053_USART_CR1_RE | L053_USART_CR1_RXNEIE
		| L053_USART_CR1_UE;
	hal_nvic_enable(L053_IRQ_USART2, true);

	L053_TIM2_PSC = 31U;                            /* 32 MHz / 32 = 1 MHz */
	L053_TIM2_ARR = 0xFFFFU;
	L053_TIM2_EGR = L053_TIM_EGR_UG;
	L053_TIM2_SR = 0U;
	L053_TIM2_DIER = L053_TIM_DIER_UIE;
	L053_TIM2_CR1 = L053_TIM_CR1_CEN;
	hal_nvic_enable(L053_IRQ_TIM2, true);

	/* EXTI line 0 from port C, falling edge; masked until reception starts. */
	L053_SYSCFG_EXTICR1 = (L053_SYSCFG_EXTICR1 & ~0xFUL) | 0x2UL;
	L053_EXTI_FTSR |= 1UL;
	L053_EXTI_IMR &= ~1UL;
}

void hal_init(void)
{
	hal_clock_init();
	hal_pins_init();
	hal_peripherals_init();
}

void hal_spi_select(bool selected)
{
	while ((L053_SPI1_SR & L053_SPI_SR_BSY) != 0U)
	{
		/* Let the last byte finish. */
	}
	hal_pin_write(L053_GPIOA_BASE, 1U, !selected);
}

uint8_t hal_spi_transfer(uint8_t byte)
{
	while ((L053_SPI1_SR & L053_SPI_SR_TXE) == 0U)
	{
		/* Wait for room. */
	}
	*(volatile uint8_t *)(uintptr_t)(L053_SPI1_BASE + 0x0CUL) = byte;
	while ((L053_SPI1_SR & L053_SPI_SR_RXNE) == 0U)
	{
		/* Wait for the byte in. */
	}
	return *(volatile uint8_t *)(uintptr_t)(L053_SPI1_BASE + 0x0CUL);
}

void hal_radio_shutdown(bool shutdown)
{
	hal_pin_write(L053_GPIOA_BASE, 8U, shutdown);
}

void hal_radio_irq_enable(bool enable)
{
	if (enable)
	{
		L053_EXTI_PR = 1UL;
		L053_EXTI_IMR |= 1UL;
	}
	else
	{
		L053_EXTI_IMR &= ~1UL;
	}
	hal_nvic_enable(L053_IRQ_EXTI0_1, enable);
	hal_pin_write(L053_GPIOA_BASE, 5U, enable);
}

uint32_t hal_time_us(void)
{
	uint32_t state = hal_irq_save();
	uint32_t high = m_time_high;
	uint32_t count = L053_TIM2_CNT & 0xFFFFU;

	if (((L053_TIM2_SR & L053_TIM_SR_UIF) != 0U) && (count < 0x8000U))
	{
		high++;
	}
	hal_irq_restore(state);
	return (high << 16) | count;
}

void hal_delay_us(uint32_t micros)
{
	uint32_t start = hal_time_us();

	while ((hal_time_us() - start) < micros)
	{
		/* Wait. */
	}
}

void hal_uart_write(const char *text, uint32_t length)
{
	uint32_t index;

	for (index = 0U; index < length; index++)
	{
		while ((L053_USART2_ISR & L053_USART_ISR_TXE) == 0U)
		{
			/* Wait for room. */
		}
		L053_USART2_TDR = (uint32_t)(uint8_t)text[index];
	}
}

int32_t hal_uart_read(void)
{
	int32_t byte = -1;

	if (m_rx_head != m_rx_tail)
	{
		byte = (int32_t)m_rx_bytes[m_rx_tail % HAL_RX_SIZE];
		m_rx_tail = m_rx_tail + 1U;
	}
	return byte;
}

uint32_t hal_irq_save(void)
{
	uint32_t state;

	__asm volatile ("mrs %0, primask" : "=r" (state));
	__asm volatile ("cpsid i" : : : "memory");
	return state;
}

void hal_irq_restore(uint32_t state)
{
	__asm volatile ("msr primask, %0" : : "r" (state) : "memory");
}

/** EXTI lines 0 and 1: the radio's nIRQ on line 0. */
void hal_exti0_1_isr(void)
{
	uint32_t passes = 0U;

	do
	{
		L053_EXTI_PR = 1UL;
		rx_on_irq();
		passes++;
	} while (((L053_GPIO_IDR(L053_GPIOC_BASE) & 1UL) == 0U) && (passes < HAL_IRQ_PASSES));
}

/** TIM2 update: the upper half of the microsecond timer. */
void hal_tim2_isr(void)
{
	if ((L053_TIM2_SR & L053_TIM_SR_UIF) != 0U)
	{
		L053_TIM2_SR = ~L053_TIM_SR_UIF;
		m_time_high = m_time_high + 1U;
	}
}

/** USART2: a byte from the host. */
void hal_usart2_isr(void)
{
	uint32_t status = L053_USART2_ISR;
	uint8_t byte;

	if ((status & L053_USART_ISR_ORE) != 0U)
	{
		L053_USART2_ICR = L053_USART_ICR_ORECF;
	}
	if ((status & L053_USART_ISR_RXNE) != 0U)
	{
		byte = (uint8_t)L053_USART2_RDR;
		if ((m_rx_head - m_rx_tail) < HAL_RX_SIZE)
		{
			m_rx_bytes[m_rx_head % HAL_RX_SIZE] = byte;
			m_rx_head = m_rx_head + 1U;
		}
	}
}
