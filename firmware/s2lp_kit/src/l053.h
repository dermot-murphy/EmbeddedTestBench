/**
 * @file l053.h
 * @brief The STM32L053R8 registers and bits this firmware uses (#84).
 *
 * Addresses and bit positions are the part's, from its reference manual
 * (RM0367) and device header; only those needed are listed. No vendor header
 * is included, so the firmware builds from this repository alone.
 */

#ifndef L053_H
#define L053_H

#include <stdint.h>

/** A memory-mapped 32-bit register. */
#define L053_REG(address)       (*(volatile uint32_t *)(address))

/** A memory-mapped register accessed a byte at a time. */
#define L053_REG8(address)      (*(volatile uint8_t *)(address))

/* Base addresses. */
#define L053_TIM2_BASE          (0x40000000UL)
#define L053_USART2_BASE        (0x40004400UL)
#define L053_PWR_BASE           (0x40007000UL)
#define L053_SYSCFG_BASE        (0x40010000UL)
#define L053_EXTI_BASE          (0x40010400UL)
#define L053_SPI1_BASE          (0x40013000UL)
#define L053_RCC_BASE           (0x40021000UL)
#define L053_FLASH_BASE         (0x40022000UL)
#define L053_GPIOA_BASE         (0x50000000UL)
#define L053_GPIOB_BASE         (0x50000400UL)
#define L053_GPIOC_BASE         (0x50000800UL)
#define L053_NVIC_ISER          (0xE000E100UL)
#define L053_NVIC_ICER          (0xE000E180UL)
#define L053_NVIC_ICPR          (0xE000E280UL)
#define L053_NVIC_IPR0          (0xE000E400UL)

/* RCC. */
#define L053_RCC_CR             L053_REG(L053_RCC_BASE + 0x00UL)
#define L053_RCC_CFGR           L053_REG(L053_RCC_BASE + 0x0CUL)
#define L053_RCC_IOPENR         L053_REG(L053_RCC_BASE + 0x2CUL)
#define L053_RCC_APB2ENR        L053_REG(L053_RCC_BASE + 0x34UL)
#define L053_RCC_APB1ENR        L053_REG(L053_RCC_BASE + 0x38UL)
#define L053_RCC_CR_HSION       (1UL << 0)
#define L053_RCC_CR_HSIRDY      (1UL << 2)
#define L053_RCC_CR_HSIDIVEN    (1UL << 3)
#define L053_RCC_CR_PLLON       (1UL << 24)
#define L053_RCC_CR_PLLRDY      (1UL << 25)
#define L053_RCC_CFGR_SW_MASK   (3UL << 0)
#define L053_RCC_CFGR_SW_PLL    (3UL << 0)
#define L053_RCC_CFGR_SWS_MASK  (3UL << 2)
#define L053_RCC_CFGR_SWS_PLL   (3UL << 2)
#define L053_RCC_CFGR_PLLSRC    (1UL << 16)
#define L053_RCC_CFGR_PLLMUL_MASK (0xFUL << 18)
#define L053_RCC_CFGR_PLLMUL4   (1UL << 18)
#define L053_RCC_CFGR_PLLDIV_MASK (3UL << 22)
#define L053_RCC_CFGR_PLLDIV2   (1UL << 22)
#define L053_RCC_IOPENR_GPIOA   (1UL << 0)
#define L053_RCC_IOPENR_GPIOB   (1UL << 1)
#define L053_RCC_IOPENR_GPIOC   (1UL << 2)
#define L053_RCC_APB2ENR_SYSCFG (1UL << 0)
#define L053_RCC_APB2ENR_SPI1   (1UL << 12)
#define L053_RCC_APB1ENR_TIM2   (1UL << 0)
#define L053_RCC_APB1ENR_USART2 (1UL << 17)
#define L053_RCC_APB1ENR_PWR    (1UL << 28)

/* PWR and FLASH. */
#define L053_PWR_CR             L053_REG(L053_PWR_BASE + 0x00UL)
#define L053_PWR_CSR            L053_REG(L053_PWR_BASE + 0x04UL)
#define L053_PWR_CR_VOS_MASK    (3UL << 11)
#define L053_PWR_CR_VOS_RANGE1  (1UL << 11)
#define L053_PWR_CSR_VOSF       (1UL << 4)
#define L053_FLASH_ACR          L053_REG(L053_FLASH_BASE + 0x00UL)
#define L053_FLASH_ACR_LATENCY  (1UL << 0)

/* GPIO, by port base. */
#define L053_GPIO_MODER(base)   L053_REG((base) + 0x00UL)
#define L053_GPIO_OSPEEDR(base) L053_REG((base) + 0x08UL)
#define L053_GPIO_PUPDR(base)   L053_REG((base) + 0x0CUL)
#define L053_GPIO_IDR(base)     L053_REG((base) + 0x10UL)
#define L053_GPIO_BSRR(base)    L053_REG((base) + 0x18UL)
#define L053_GPIO_AFRL(base)    L053_REG((base) + 0x20UL)

/* SPI1. */
#define L053_SPI1_CR1           L053_REG(L053_SPI1_BASE + 0x00UL)
#define L053_SPI1_SR            L053_REG(L053_SPI1_BASE + 0x08UL)
/* SPI1's data register, accessed as a byte: wider access packs two frames. */
#define L053_SPI1_DR8           L053_REG8(L053_SPI1_BASE + 0x0CUL)
#define L053_SPI_CR1_MSTR       (1UL << 2)
#define L053_SPI_CR1_BR_DIV4    (1UL << 3)
#define L053_SPI_CR1_SPE        (1UL << 6)
#define L053_SPI_CR1_SSI        (1UL << 8)
#define L053_SPI_CR1_SSM        (1UL << 9)
#define L053_SPI_SR_RXNE        (1UL << 0)
#define L053_SPI_SR_TXE         (1UL << 1)
#define L053_SPI_SR_BSY         (1UL << 7)

/* USART2. */
#define L053_USART2_CR1         L053_REG(L053_USART2_BASE + 0x00UL)
#define L053_USART2_BRR         L053_REG(L053_USART2_BASE + 0x0CUL)
#define L053_USART2_ISR         L053_REG(L053_USART2_BASE + 0x1CUL)
#define L053_USART2_ICR         L053_REG(L053_USART2_BASE + 0x20UL)
#define L053_USART2_RDR         L053_REG(L053_USART2_BASE + 0x24UL)
#define L053_USART2_TDR         L053_REG(L053_USART2_BASE + 0x28UL)
#define L053_USART_CR1_UE       (1UL << 0)
#define L053_USART_CR1_RE       (1UL << 2)
#define L053_USART_CR1_TE       (1UL << 3)
#define L053_USART_CR1_RXNEIE   (1UL << 5)
#define L053_USART_ISR_ORE      (1UL << 3)
#define L053_USART_ISR_RXNE     (1UL << 5)
#define L053_USART_ISR_TXE      (1UL << 7)
#define L053_USART_ICR_ORECF    (1UL << 3)

/* SYSCFG and EXTI. */
#define L053_SYSCFG_EXTICR1     L053_REG(L053_SYSCFG_BASE + 0x08UL)
#define L053_EXTI_IMR           L053_REG(L053_EXTI_BASE + 0x00UL)
#define L053_EXTI_FTSR          L053_REG(L053_EXTI_BASE + 0x0CUL)
#define L053_EXTI_PR            L053_REG(L053_EXTI_BASE + 0x14UL)

/* TIM2: a 16-bit timer on this part. */
#define L053_TIM2_CR1           L053_REG(L053_TIM2_BASE + 0x00UL)
#define L053_TIM2_DIER          L053_REG(L053_TIM2_BASE + 0x0CUL)
#define L053_TIM2_SR            L053_REG(L053_TIM2_BASE + 0x10UL)
#define L053_TIM2_EGR           L053_REG(L053_TIM2_BASE + 0x14UL)
#define L053_TIM2_CNT           L053_REG(L053_TIM2_BASE + 0x24UL)
#define L053_TIM2_PSC           L053_REG(L053_TIM2_BASE + 0x28UL)
#define L053_TIM2_ARR           L053_REG(L053_TIM2_BASE + 0x2CUL)
#define L053_TIM_CR1_CEN        (1UL << 0)
#define L053_TIM_DIER_UIE       (1UL << 0)
#define L053_TIM_SR_UIF         (1UL << 0)
#define L053_TIM_EGR_UG         (1UL << 0)

/* Interrupt numbers. */
#define L053_IRQ_EXTI0_1        (5U)
#define L053_IRQ_TIM2           (15U)
#define L053_IRQ_USART2         (28U)

#endif /* L053_H */
