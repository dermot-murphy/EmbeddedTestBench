@echo off
rem Package the built firmware as a DFU zip and, optionally, flash it.
rem
rem The PCA10059 dongle has no onboard debugger, so it is programmed over USB
rem through its bootloader. Press the small RESET button on the side of the
rem dongle first; the red LED pulses when the bootloader is ready.
rem
rem   package_dfu.bat            package only
rem   package_dfu.bat COM5       package and flash
rem
rem Traces to: BLE-FR-090, BLE-DD-BUILD.
setlocal
set HERE=%~dp0
set HEX=%HERE%..\ses\Output\Release\Exe\nordic_dongle_pca10059.hex
set PACKAGE=%HERE%..\ses\Output\nordic_dongle_dfu.zip

if not exist "%HEX%" (
	echo no build output at %HEX% - build the SES project first
	exit /b 1
)

rem 0xCA is S140 7.2.0, shipped with nRF5 SDK 17.1.0 and on the dongle from the
rem factory. If a DFU is rejected as incompatible, run
rem   nrfutil pkg generate --help
rem and use the identifier matching the SoftDevice actually on the dongle.
nrfutil pkg generate --hw-version 52 --application-version 1 ^
	--application "%HEX%" --sd-req 0xCA "%PACKAGE%"
if errorlevel 1 exit /b 1
echo packaged %PACKAGE%

if not "%~1"=="" (
	echo flashing via %1 - press RESET on the dongle first
	nrfutil dfu usb-serial -pkg "%PACKAGE%" -p %1
)
endlocal
