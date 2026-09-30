#!/bin/sh
# Download the Pico 2 + SHT30-D reference documents into datasheets/.
#
# Run from any directory:  sh docs/pico_sht30/fetch_datasheets.sh
# Then commit the downloaded files (PICO-OPEN-04). Sources: References.md.
#
# Traces to: PICO-OPEN-04.
set -eu

cd "$(dirname "$0")/datasheets"

fetch() {
	name=$1
	url=$2
	if [ -s "$name" ]; then
		echo "have   $name"
		return 0
	fi
	echo "fetch  $name"
	curl -fsSL --retry 3 -o "$name.part" "$url" && mv "$name.part" "$name" \
		|| { rm -f "$name.part"; echo "FAILED $name  <- $url" >&2; status=1; }
}

status=0
fetch pico-2-datasheet.pdf            https://datasheets.raspberrypi.com/pico/pico-2-datasheet.pdf
fetch Pico-2-Pinout.pdf               https://datasheets.raspberrypi.com/pico/Pico-2-Pinout.pdf
fetch RPi-Pico-2-PUBLIC-20240708.zip  https://datasheets.raspberrypi.com/pico/RPi-Pico-2-PUBLIC-20240708.zip
fetch rp2350-datasheet.pdf            https://datasheets.raspberrypi.com/rp2350/rp2350-datasheet.pdf
fetch getting-started-with-pico.pdf   https://datasheets.raspberrypi.com/pico/getting-started-with-pico.pdf
fetch raspberry-pi-pico-c-sdk.pdf     https://datasheets.raspberrypi.com/pico/raspberry-pi-pico-c-sdk.pdf
fetch Datasheet_SHT3x_DIS.pdf         https://sensirion.com/media/documents/213E6A3B/63A5A569/Datasheet_SHT3x_DIS.pdf
exit $status
