# ETB S2-LP kit firmware (#84): build with arm-none-eabi-gcc.
#
#   make                  build/s2lp_kit.elf, .hex, .bin and .map
#   make ARM_PREFIX=<dir>/arm-none-eabi-   use a toolchain that is not on PATH
#
# Needs no vendor package: the startup, linker script and register
# definitions are this firmware's own.

ARM_PREFIX ?= arm-none-eabi-
CC      := $(ARM_PREFIX)gcc
OBJCOPY := $(ARM_PREFIX)objcopy
SIZE    := $(ARM_PREFIX)size

BUILD   := build
TARGET  := $(BUILD)/s2lp_kit

SOURCES := src/startup.c src/main.c src/hal_l053.c src/s2lp.c src/rx.c src/ring.c src/cmd.c
OBJECTS := $(patsubst src/%.c,$(BUILD)/%.o,$(SOURCES))

CPU     := -mcpu=cortex-m0plus -mthumb
CFLAGS  := $(CPU) -std=c11 -Os -g -ffunction-sections -fdata-sections \
           -Wall -Wextra -Wconversion -Wshadow -Wstrict-prototypes -Werror \
           -Iinclude -Isrc
LDFLAGS := $(CPU) -nostartfiles -Tstm32l053r8.ld -Wl,--gc-sections \
           -Wl,-Map=$(TARGET).map --specs=nano.specs --specs=nosys.specs

.PHONY: all clean

all: $(TARGET).hex $(TARGET).bin
	$(SIZE) $(TARGET).elf

$(BUILD):
	mkdir -p $(BUILD)

$(BUILD)/%.o: src/%.c | $(BUILD)
	$(CC) $(CFLAGS) -c $< -o $@

$(TARGET).elf: $(OBJECTS) stm32l053r8.ld
	$(CC) $(LDFLAGS) $(OBJECTS) -o $@

$(TARGET).hex: $(TARGET).elf
	$(OBJCOPY) -O ihex $< $@

$(TARGET).bin: $(TARGET).elf
	$(OBJCOPY) -O binary $< $@

clean:
	rm -rf $(BUILD)
