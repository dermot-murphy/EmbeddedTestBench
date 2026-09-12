# SWE.1 — Software Requirements Specification

| Field | Value |
|---|---|
| Document ID | TEK3014B-SWE1-001 |
| Version | 1.0 |
| Date | 2026-09-12 |
| Process reference | Automotive SPICE V4.0, SWE.1 Software Requirements Analysis |
| Item | `tek3014b` — Ethernet driver for the Tektronix TDS3014B oscilloscope |

## 1. Scope

This specification covers a host-side software driver that controls a Tektronix TDS3014B
digital phosphor oscilloscope over Ethernet, for use in automated and semi-automated test
environments. The driver is a **test tool**: it is not part of any delivered vehicle
software and carries no ASIL classification. It is nonetheless developed to the same
process discipline because measurement results derived from it are used as evidence.

Out of scope: GPIB and RS-232 interfaces, front-panel emulation, FFT and other TDS3xxx
application-module features, instrument firmware update.

## 2. Stakeholder requirements

| ID | Requirement |
|---|---|
| STK-01 | Interface to a TDS3014B oscilloscope over Ethernet. |
| STK-02 | Enable up to four channels. |
| STK-03 | Set screen position and volts per division for each channel. |
| STK-04 | Trigger the instrument and capture a plot. |
| STK-05 | Take measurements, for example period, and the spread in time of a number of channels going high. |
| STK-06 | Determine whether VISA must be used. |

## 3. Definitions

| Term | Meaning |
|---|---|
| Skew | Time difference between one channel's edge and a reference channel's edge. |
| Spread | Time between the earliest and latest of a set of channels crossing their thresholds. |
| Record | One acquisition's worth of samples from one channel. |
| Preamble | The `WFMPre` axis description needed to scale a record to seconds and volts. |
| Clipping | A sample at the digitiser's rail, i.e. the trace has left the graticule vertically. |

## 4. Functional requirements

### 4.1 Instrument link

| ID | Requirement | Source | Verification |
|---|---|---|---|
| SWE1-FR-001 | The driver shall establish a link to the instrument using the VXI-11 TCP/IP Instrument Protocol over ONC-RPC, implemented without any third-party library. | STK-01, STK-06 | Test |
| SWE1-FR-002 | The driver shall discover the VXI-11 core channel port via the instrument's portmapper (TCP, falling back to UDP), and shall accept an explicit port override. | STK-01 | Test |
| SWE1-FR-003 | The driver shall provide a raw TCP socket transport for instruments that expose a SCPI socket. | STK-01 | Test |
| SWE1-FR-004 | The driver shall provide an optional PyVISA transport, which shall not be required for normal operation. | STK-06 | Test |
| SWE1-FR-005 | The driver shall accept a host name, an IPv4 address, or a VISA-style resource string, and shall select a transport automatically. | STK-01 | Test |
| SWE1-FR-006 | The driver shall transfer messages of arbitrary length, chunking writes to the link's negotiated maximum and reassembling chunked responses. | STK-01 | Test |
| SWE1-FR-007 | The driver shall probe the VXI-11 logical device names used by both VXI-11.2 and VXI-11.3 devices, and shall report which was accepted. | STK-01 | Test |

### 4.2 Vertical (channel) control

| ID | Requirement | Source | Verification |
|---|---|---|---|
| SWE1-FR-010 | The driver shall enable and disable each of up to four input channels independently. | STK-02 | Test |
| SWE1-FR-011 | The driver shall report which channels are currently displayed. | STK-02 | Test |
| SWE1-FR-012 | The driver shall set the volts per division of each channel over the range 1 mV/div to 10 V/div. | STK-03 | Test |
| SWE1-FR-013 | The driver shall set the vertical screen position of each channel over the range -5 to +5 divisions. | STK-03 | Test |
| SWE1-FR-014 | The driver shall set the input offset, coupling (AC/DC/GND) and bandwidth limit of each channel. | STK-03 | Test |
| SWE1-FR-015 | The driver shall read back the complete vertical setup of a channel. | STK-03 | Test |
| SWE1-FR-016 | The driver shall apply a complete vertical setup in a single instrument message. | STK-03 | Test |

### 4.3 Horizontal and trigger control

| ID | Requirement | Source | Verification |
|---|---|---|---|
| SWE1-FR-020 | The driver shall set the main time base over the range 4 ns/div to 10 s/div. | STK-04 | Test |
| SWE1-FR-021 | The driver shall set the horizontal delay. | STK-04 | Test |
| SWE1-FR-022 | The driver shall set the acquisition record length to a value the instrument supports (500 or 10 000 points). | STK-04 | Test |
| SWE1-FR-030 | The driver shall configure an A-event edge trigger: source, level, slope, coupling and mode. | STK-04 | Test |
| SWE1-FR-031 | The driver shall report the instrument's trigger state and shall be able to force a trigger. | STK-04 | Test |

### 4.4 Acquisition

| ID | Requirement | Source | Verification |
|---|---|---|---|
| SWE1-FR-040 | The driver shall arm a single-sequence acquisition and wait for it to complete within a caller-specified timeout. | STK-04 | Test |
| SWE1-FR-041 | The driver shall start and stop free-running acquisition. | STK-04 | Test |
| SWE1-FR-042 | The driver shall select the acquisition mode and, for averaging, the average count. | STK-04 | Test |
| SWE1-FR-043 | On acquisition timeout the driver shall raise a distinct exception whose message identifies the likely cause and reports the instrument's trigger state. | STK-04 | Test |

### 4.5 Waveform capture

| ID | Requirement | Source | Verification |
|---|---|---|---|
| SWE1-FR-050 | The driver shall transfer waveform records from one or more channels of a single acquisition, so that the channels share a common time base. | STK-04, STK-05 | Test |
| SWE1-FR-051 | The driver shall scale records to seconds and volts using the instrument's preamble, per the relations `Xn = XZEro + XINcr(n - PT_Off)` and `Yn = YZEro + YMUlt(raw - YOFf)`. | STK-04 | Test |
| SWE1-FR-052 | The driver shall detect samples at the digitiser rail and report them, because level estimation and every threshold-derived timing result is invalid on a clipped record. | STK-05 | Test |
| SWE1-FR-053 | The driver shall export captured records to CSV, with one shared time column for a multi-channel capture. | STK-04 | Test |
| SWE1-FR-054 | The driver shall support 1-byte and 2-byte transfer widths and both binary and ASCII encodings, decoding all of them to identical digitiser codes. | STK-04 | Test |
| SWE1-FR-055 | The driver shall transfer a caller-specified sub-range of the record while still reporting absolute record times. | STK-04 | Test |

### 4.6 Measurement

| ID | Requirement | Source | Verification |
|---|---|---|---|
| SWE1-FR-060 | The driver shall take immediate measurements using the instrument's own measurement engine, including period, frequency, amplitude, rise time and two-source delay. | STK-05 | Test |
| SWE1-FR-061 | The driver shall measure, host-side from a captured record, every period present and report mean, minimum, maximum, standard deviation and peak-to-peak jitter. | STK-05 | Test |
| SWE1-FR-062 | The driver shall measure, host-side from one simultaneous capture, the spread in time of an arbitrary number of channels crossing a threshold in a given direction, and shall report per-channel times, per-channel skews relative to a reference, the earliest and latest channel, and the overall spread. | STK-05 | Test |
| SWE1-FR-063 | The driver shall measure host-side pulse widths and transition times. | STK-05 | Test |
| SWE1-FR-064 | Edge times shall be refined by interpolation between the samples straddling the threshold, so that timing resolution is not limited to the sample interval. | STK-05 | Test |
| SWE1-FR-065 | Edge detection shall apply a hysteresis band to suppress duplicate edges caused by noise near the threshold. | STK-05 | Test |
| SWE1-FR-066 | Thresholds shall be derivable either from each channel's own amplitude (percentage) or as one absolute voltage applied to every channel. | STK-05 | Test |
| SWE1-FR-067 | When the instrument cannot compute a measurement it shall be reported as an error, not returned as the instrument's 9.9E37 sentinel. | STK-05 | Test |

### 4.7 Plot and screen capture

| ID | Requirement | Source | Verification |
|---|---|---|---|
| SWE1-FR-070 | The driver shall render captured records to an image file host-side. | STK-04 | Test |
| SWE1-FR-071 | The driver shall annotate a rendered plot with the measured edge of each channel and the resulting spread. | STK-05 | Test |
| SWE1-FR-080 | The driver shall capture the instrument's screen over the instrument link and write it to a file. | STK-04 | Test |
| SWE1-FR-081 | If the instrument does not accept the requested hardcopy format, the driver shall fall back to a format the instrument supports rather than failing. | STK-04 | Test |

### 4.8 Supporting

| ID | Requirement | Source | Verification |
|---|---|---|---|
| SWE1-FR-090 | The driver shall include a behavioural instrument simulator sufficient to exercise every layer above the socket without hardware. | STK-06 | Test |
| SWE1-FR-100 | The driver shall provide a command-line interface covering identification, capture, screen capture, measurement, period statistics and channel spread. | STK-04, STK-05 | Test |
| SWE1-FR-101 | The driver shall report the instrument's event queue and shall raise on any reported event. | STK-01 | Test |

## 5. Non-functional requirements

| ID | Requirement | Verification |
|---|---|---|
| SWE1-NFR-001 | The package shall have no mandatory third-party runtime dependencies. | Inspection, Test |
| SWE1-NFR-002 | The package shall run on CPython 3.8 or later. | Inspection |
| SWE1-NFR-003 | Optional dependencies shall be imported lazily, and their absence shall produce a diagnostic naming the missing extra rather than an `ImportError`. | Test |
| SWE1-NFR-004 | Settings shall be validated against the instrument's capability envelope before transmission; a rejected setting shall leave the instrument unmodified. | Test |
| SWE1-NFR-005 | All errors shall be reported through a single typed exception hierarchy, and diagnostics shall name the probable cause and the corrective action. | Test |
| SWE1-NFR-006 | Every I/O operation shall be bounded by a timeout. | Test, Inspection |
| SWE1-NFR-007 | Statement coverage of the unit test suite shall be at least 90%. | Test |
| SWE1-NFR-008 | The capability envelope shall be data-driven, so that another member of the TDS3000 family can be supported without code change. | Inspection |

## 6. Assumptions and constraints

| ID | Statement |
|---|---|
| ASM-01 | The instrument's Ethernet interface is enabled and has a reachable IPv4 address. |
| ASM-02 | The host can reach the instrument's portmapper on port 111 and the dynamically assigned core channel port; no intervening firewall blocks them. |
| ASM-03 | The instrument supports a limited number of simultaneous VXI-11 links (in practice one). |
| CON-01 | Verification to date is against a protocol simulator, not physical hardware. Bench confirmation items are listed in TEK3014B-VISA-001 §5.1. |
| CON-02 | SCPI command spellings were not transcribed from the programmer manual during development (the manual host was unreachable from the build environment) and require spot-checking on first bench use. |
