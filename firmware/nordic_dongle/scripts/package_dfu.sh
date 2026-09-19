#!/bin/sh
# Package the built firmware as a DFU zip and, optionally, flash it.
#
# The PCA10059 dongle has no onboard debugger, so it is programmed over USB
# through the bootloader it ships with. Put the dongle in bootloader mode by
# pressing the small RESET button on the side; the red LED pulses when it is
# ready.
#
# Usage:
#   ./package_dfu.sh                    # package only
#   ./package_dfu.sh /dev/ttyACM0       # package and flash (COM5 on Windows)
#
# Traces to: BLE-FR-090, BLE-DD-BUILD.
set -e

HERE=$(cd "$(dirname "$0")" && pwd)
BUILD="$HERE/../ses/Output/Release/Exe"
HEX="$BUILD/nordic_dongle_pca10059.hex"
PACKAGE="$HERE/../ses/Output/nordic_dongle_dfu.zip"

APP_VERSION=1

# SoftDevice the application requires. 0xCA is S140 7.2.0, which is what nRF5
# SDK 17.1.0 ships and what the dongle's factory bootloader has. If a DFU is
# rejected as incompatible, list the identifiers with
#   nrfutil pkg generate --help
# and use the one matching the SoftDevice actually on the dongle.
SD_REQ=0xCA

# Signing key. The dongle's factory bootloader does not verify signatures, so
# this is normally left unset; set DFU_KEY to sign for a bootloader that does.
KEY_ARGUMENTS=""
if [ -n "$DFU_KEY" ]; then
	KEY_ARGUMENTS="--key-file $DFU_KEY"
fi

if [ ! -f "$HEX" ]; then
	echo "no build output at $HEX - build the SES project first" >&2
	exit 1
fi

nrfutil pkg generate \
	--hw-version 52 \
	--application-version "$APP_VERSION" \
	--application "$HEX" \
	--sd-req "$SD_REQ" \
	$KEY_ARGUMENTS \
	"$PACKAGE"

echo "packaged $PACKAGE"

if [ -n "$1" ]; then
	echo "flashing via $1 - press RESET on the dongle first"
	nrfutil dfu usb-serial -pkg "$PACKAGE" -p "$1"
fi
