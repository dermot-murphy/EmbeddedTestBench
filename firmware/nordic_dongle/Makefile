# Headless build of the dongle firmware, for CI and for anyone without SES.
#
# SEGGER Embedded Studio is the developer path (ses/nordic_dongle_pca10059.emProject)
# and remains the reference; this Makefile exists because a CI runner cannot
# install and licence an IDE, and "the firmware builds" is worth knowing on
# every push.
#
#   make SDK_ROOT=/path/to/nRF5_SDK_17.1.0
#   make SDK_ROOT=... dfu          # also package it for the bootloader
#
# GNU_INSTALL_ROOT must end with a slash, as Nordic's own makefiles expect.
#
# Traces to: BLE-FR-090, BLE-DD-BUILD.

PROJECT_NAME     := nordic_dongle_pca10059
TARGETS          := $(PROJECT_NAME)
OUTPUT_DIRECTORY := _build

# The build's identity. The version is read from the single place it is
# declared, so the Makefile cannot disagree with the firmware about it. The date
# is UTC and ISO 8601, and honours SOURCE_DATE_EPOCH, so a reproducible build
# stays reproducible - the host compares this string, and a date that changed on
# every rebuild would report every dongle as out of date.
FIRMWARE_VERSION := $(shell sed -n 's/^\#define FIRMWARE_VERSION[ \t]*"\(.*\)".*/\1/p' include/firmware_version.h)
SOURCE_DATE_EPOCH ?= $(shell date -u +%s)
FIRMWARE_BUILD_DATE := $(shell date -u -d @$(SOURCE_DATE_EPOCH) +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || \
                               date -u -r $(SOURCE_DATE_EPOCH) +%Y-%m-%dT%H:%M:%SZ)
MANIFEST := $(OUTPUT_DIRECTORY)/firmware_manifest.json

# The date reaches the image through CFLAGS, and make does not recompile a file
# because a command line changed. Left alone, an incremental build would keep
# the first build's date in the image while the manifest carried today's - and
# the host, which compares the two, would report a dongle as out of date
# immediately after refreshing it, for ever. Deleting this one object costs a
# single compile and makes that disagreement impossible.
$(shell rm -f $(OUTPUT_DIRECTORY)/$(PROJECT_NAME)/firmware_version.c.o)

SDK_ROOT         ?= ../../../nRF5_SDK_17.1.0
PROJ_DIR         := .

GNU_INSTALL_ROOT ?=
GNU_PREFIX       ?= arm-none-eabi

$(OUTPUT_DIRECTORY)/$(PROJECT_NAME).out: \
  LINKER_SCRIPT  := $(PROJ_DIR)/gcc/nordic_dongle_gcc_nrf52.ld

# --- sources -----------------------------------------------------------
SRC_FILES += \
  $(SDK_ROOT)/modules/nrfx/mdk/gcc_startup_nrf52840.S \
  $(SDK_ROOT)/modules/nrfx/mdk/system_nrf52840.c \
  $(PROJ_DIR)/src/main.c \
  $(PROJ_DIR)/src/cdc_acm.c \
  $(PROJ_DIR)/src/cmd_parser.c \
  $(PROJ_DIR)/src/firmware_version.c \
  $(PROJ_DIR)/src/bootloader.c \
  $(PROJ_DIR)/src/ble_scanner.c \
  $(PROJ_DIR)/src/nus_client.c \
  $(PROJ_DIR)/src/timestamp.c \
  $(SDK_ROOT)/components/libraries/atomic/nrf_atomic.c \
  $(SDK_ROOT)/components/libraries/atomic_fifo/nrf_atfifo.c \
  $(SDK_ROOT)/components/libraries/atomic_flags/nrf_atflags.c \
  $(SDK_ROOT)/components/libraries/balloc/nrf_balloc.c \
  $(SDK_ROOT)/components/libraries/memobj/nrf_memobj.c \
  $(SDK_ROOT)/components/libraries/queue/nrf_queue.c \
  $(SDK_ROOT)/components/libraries/ringbuf/nrf_ringbuf.c \
  $(SDK_ROOT)/components/libraries/sortlist/nrf_sortlist.c \
  $(SDK_ROOT)/components/libraries/strerror/nrf_strerror.c \
  $(SDK_ROOT)/components/libraries/timer/app_timer2.c \
  $(SDK_ROOT)/components/libraries/timer/drv_rtc.c \
  $(SDK_ROOT)/components/libraries/util/app_error.c \
  $(SDK_ROOT)/components/libraries/util/app_error_handler_gcc.c \
  $(SDK_ROOT)/components/libraries/util/app_error_weak.c \
  $(SDK_ROOT)/components/libraries/util/app_util_platform.c \
  $(SDK_ROOT)/components/libraries/util/nrf_assert.c \
  $(SDK_ROOT)/components/libraries/usbd/app_usbd.c \
  $(SDK_ROOT)/components/libraries/usbd/app_usbd_core.c \
  $(SDK_ROOT)/components/libraries/usbd/app_usbd_serial_num.c \
  $(SDK_ROOT)/components/libraries/usbd/app_usbd_string_desc.c \
  $(SDK_ROOT)/components/libraries/usbd/class/cdc/acm/app_usbd_cdc_acm.c \
  $(SDK_ROOT)/integration/nrfx/legacy/nrf_drv_clock.c \
  $(SDK_ROOT)/modules/nrfx/drivers/src/nrfx_clock.c \
  $(SDK_ROOT)/modules/nrfx/drivers/src/nrfx_power.c \
  $(SDK_ROOT)/modules/nrfx/drivers/src/nrfx_systick.c \
  $(SDK_ROOT)/modules/nrfx/drivers/src/nrfx_timer.c \
  $(SDK_ROOT)/modules/nrfx/drivers/src/nrfx_usbd.c \
  $(SDK_ROOT)/modules/nrfx/soc/nrfx_atomic.c \
  $(SDK_ROOT)/components/ble/common/ble_advdata.c \
  $(SDK_ROOT)/components/ble/common/ble_conn_params.c \
  $(SDK_ROOT)/components/ble/common/ble_conn_state.c \
  $(SDK_ROOT)/components/ble/common/ble_srv_common.c \
  $(SDK_ROOT)/components/ble/ble_db_discovery/ble_db_discovery.c \
  $(SDK_ROOT)/components/ble/ble_services/ble_nus_c/ble_nus_c.c \
  $(SDK_ROOT)/components/ble/nrf_ble_gatt/nrf_ble_gatt.c \
  $(SDK_ROOT)/components/ble/nrf_ble_gq/nrf_ble_gq.c \
  $(SDK_ROOT)/components/ble/nrf_ble_scan/nrf_ble_scan.c \
  $(SDK_ROOT)/components/softdevice/common/nrf_sdh.c \
  $(SDK_ROOT)/components/softdevice/common/nrf_sdh_ble.c \
  $(SDK_ROOT)/components/softdevice/common/nrf_sdh_soc.c \

# --- includes ----------------------------------------------------------
INC_FOLDERS += \
  $(PROJ_DIR)/include \
  $(PROJ_DIR)/src \
  $(PROJ_DIR)/config \
  $(SDK_ROOT)/components \
  $(SDK_ROOT)/components/ble/ble_db_discovery \
  $(SDK_ROOT)/components/ble/ble_link_ctx_manager \
  $(SDK_ROOT)/components/ble/ble_services/ble_nus_c \
  $(SDK_ROOT)/components/ble/common \
  $(SDK_ROOT)/components/ble/nrf_ble_gatt \
  $(SDK_ROOT)/components/ble/nrf_ble_gq \
  $(SDK_ROOT)/components/ble/nrf_ble_scan \
  $(SDK_ROOT)/components/libraries/atomic \
  $(SDK_ROOT)/components/libraries/atomic_fifo \
  $(SDK_ROOT)/components/libraries/atomic_flags \
  $(SDK_ROOT)/components/libraries/balloc \
  $(SDK_ROOT)/components/libraries/delay \
  $(SDK_ROOT)/components/libraries/experimental_section_vars \
  $(SDK_ROOT)/components/libraries/fifo \
  $(SDK_ROOT)/components/libraries/log \
  $(SDK_ROOT)/components/libraries/log/src \
  $(SDK_ROOT)/components/libraries/memobj \
  $(SDK_ROOT)/components/libraries/mutex \
  $(SDK_ROOT)/components/libraries/queue \
  $(SDK_ROOT)/components/libraries/ringbuf \
  $(SDK_ROOT)/components/libraries/sortlist \
  $(SDK_ROOT)/components/libraries/stack_info \
  $(SDK_ROOT)/components/libraries/strerror \
  $(SDK_ROOT)/components/libraries/timer \
  $(SDK_ROOT)/components/libraries/usbd \
  $(SDK_ROOT)/components/libraries/usbd/class/cdc \
  $(SDK_ROOT)/components/libraries/usbd/class/cdc/acm \
  $(SDK_ROOT)/components/libraries/util \
  $(SDK_ROOT)/components/softdevice/common \
  $(SDK_ROOT)/components/softdevice/s140/headers \
  $(SDK_ROOT)/components/softdevice/s140/headers/nrf52 \
  $(SDK_ROOT)/components/toolchain/cmsis/include \
  $(SDK_ROOT)/external/fprintf \
  $(SDK_ROOT)/integration/nrfx \
  $(SDK_ROOT)/integration/nrfx/legacy \
  $(SDK_ROOT)/modules/nrfx \
  $(SDK_ROOT)/modules/nrfx/drivers/include \
  $(SDK_ROOT)/modules/nrfx/hal \
  $(SDK_ROOT)/modules/nrfx/mdk \

LIB_FILES += \

# --- flags -------------------------------------------------------------
OPT = -O3 -g3

CFLAGS += $(OPT)
CFLAGS += -DAPP_TIMER_V2
CFLAGS += -DAPP_TIMER_V2_RTC1_ENABLED
CFLAGS += -DBOARD_PCA10059
CFLAGS += -DCONFIG_GPIO_AS_PINRESET
CFLAGS += -DFLOAT_ABI_HARD
CFLAGS += -DINITIALIZE_USER_SECTIONS
CFLAGS += -DNO_VTOR_CONFIG
CFLAGS += -DFIRMWARE_BUILD_DATE=\"$(FIRMWARE_BUILD_DATE)\"
CFLAGS += -DNRF52840_XXAA
CFLAGS += -DNRF_SD_BLE_API_VERSION=7
CFLAGS += -DS140
CFLAGS += -DSOFTDEVICE_PRESENT
CFLAGS += -mcpu=cortex-m4 -mthumb -mabi=aapcs
CFLAGS += -Wall -Werror
CFLAGS += -mfloat-abi=hard -mfpu=fpv4-sp-d16
CFLAGS += -ffunction-sections -fdata-sections -fno-strict-aliasing
CFLAGS += -fno-builtin -fshort-enums

CXXFLAGS += $(OPT)

ASMFLAGS += -g3
ASMFLAGS += -mcpu=cortex-m4 -mthumb -mabi=aapcs
ASMFLAGS += -mfloat-abi=hard -mfpu=fpv4-sp-d16
ASMFLAGS += -DAPP_TIMER_V2
ASMFLAGS += -DAPP_TIMER_V2_RTC1_ENABLED
ASMFLAGS += -DBOARD_PCA10059
ASMFLAGS += -DCONFIG_GPIO_AS_PINRESET
ASMFLAGS += -DFLOAT_ABI_HARD
ASMFLAGS += -DINITIALIZE_USER_SECTIONS
ASMFLAGS += -DNO_VTOR_CONFIG
ASMFLAGS += -DNRF52840_XXAA
ASMFLAGS += -DNRF_SD_BLE_API_VERSION=7
ASMFLAGS += -DS140
ASMFLAGS += -DSOFTDEVICE_PRESENT

LDFLAGS += $(OPT)
LDFLAGS += -mthumb -mabi=aapcs -L$(SDK_ROOT)/modules/nrfx/mdk -T$(LINKER_SCRIPT)
LDFLAGS += -mcpu=cortex-m4
LDFLAGS += -mfloat-abi=hard -mfpu=fpv4-sp-d16
LDFLAGS += -Wl,--gc-sections
LDFLAGS += --specs=nano.specs

$(PROJECT_NAME): CFLAGS += -D__HEAP_SIZE=2048 -D__STACK_SIZE=8192
$(PROJECT_NAME): ASMFLAGS += -D__HEAP_SIZE=2048 -D__STACK_SIZE=8192

LIB_FILES += -lc -lnosys -lm

.PHONY: default help dfu manifest identity

default: $(PROJECT_NAME)

help:
	@echo	following targets are available:
	@echo	  $(PROJECT_NAME)  - build the firmware
	@echo	  dfu              - package it for the dongle bootloader
	@echo	  manifest         - write the build identity the host compares against
	@echo	  identity         - print the version and build date
	@echo	  flash_softdevice - flash the SoftDevice (needs a debugger)
	@echo	  sdk_config       - open the configuration tool

TEMPLATE_PATH := $(SDK_ROOT)/components/toolchain/gcc

# Nordic's Makefile.common *warns* about a source file it cannot find and then
# builds without it. That is how a missing interrupt handler reaches a linker
# error three screens later, or worse, links because something else defines a
# weak symbol. A source this project names and the SDK does not have is a
# mistake about the SDK, and it is worth saying so here.
#
# The SoftDevice hex is checked separately: it is only needed for flashing.
MISSING_SOURCES := $(strip $(foreach source,$(SRC_FILES),$(if $(wildcard $(source)),,$(source))))
ifneq ($(MISSING_SOURCES),)
  $(info SDK_ROOT is $(SDK_ROOT))
  $(foreach source,$(MISSING_SOURCES),$(info missing source: $(source)))
  $(error $(words $(MISSING_SOURCES)) source file(s) named by this Makefile \
do not exist under SDK_ROOT. Check SDK_ROOT points at an nRF5 SDK 17 tree, and \
that these paths are right for its nrfx version)
endif

include $(TEMPLATE_PATH)/Makefile.common

$(foreach target, $(TARGETS), $(call define_target, $(target)))

# --- packaging ---------------------------------------------------------
# 0xCA is S140 7.2.0. The dongle's factory bootloader does not verify
# signatures, so no key is needed; set DFU_KEY for one that does.
dfu: default manifest
	nrfutil pkg generate \
		--hw-version 52 \
		--application-version 1 \
		--application $(OUTPUT_DIRECTORY)/$(PROJECT_NAME).hex \
		--sd-req 0xCA \
		$(if $(DFU_KEY),--key-file $(DFU_KEY),) \
		$(OUTPUT_DIRECTORY)/nordic_dongle_dfu.zip
	@echo packaged $(OUTPUT_DIRECTORY)/nordic_dongle_dfu.zip

identity:
	@echo version=$(FIRMWARE_VERSION)
	@echo built=$(FIRMWARE_BUILD_DATE)

# The manifest is how the host knows what it built without parsing a hex file or
# guessing from a file date. The dongle reports the same version and date over
# its link, and the driver compares the two.
manifest: default
	@printf '{\n' > $(MANIFEST)
	@printf '  "version": "%s",\n'     "$(FIRMWARE_VERSION)"    >> $(MANIFEST)
	@printf '  "built": "%s",\n'       "$(FIRMWARE_BUILD_DATE)" >> $(MANIFEST)
	@printf '  "protocol": "%s",\n'    "$(shell sed -n 's/^\#define PROTO_VERSION[ \t]*"\(.*\)".*/\1/p' include/protocol.h)" >> $(MANIFEST)
	@printf '  "model": "%s",\n'       "$(shell sed -n 's/^\#define PROTO_MODEL[ \t]*"\(.*\)".*/\1/p' include/protocol.h)" >> $(MANIFEST)
	@printf '  "hex": "%s",\n'         "$(PROJECT_NAME).hex"    >> $(MANIFEST)
	@printf '  "package": "%s",\n'     "nordic_dongle_dfu.zip"  >> $(MANIFEST)
	@printf '  "sha256": "%s"\n'       "$(shell sha256sum $(OUTPUT_DIRECTORY)/$(PROJECT_NAME).hex 2>/dev/null | cut -d" " -f1)" >> $(MANIFEST)
	@printf '}\n' >> $(MANIFEST)
	@echo wrote $(MANIFEST)
